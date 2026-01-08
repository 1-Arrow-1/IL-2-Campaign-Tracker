#!/usr/bin/env python3
"""
Synchronize campaignsstates.txt with on-disk missions.

Removes decoded mission entries that no longer exist on disk, restores
entries for missions found on disk but missing from state, and regenerates
downstream artifacts after updating campaignsstates.txt.
"""

from __future__ import annotations

import os
import re
import json
import shutil
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Set, Tuple

from decode_campaign_usersave1 import main as decode_campaignsstates
from decode_campaign_usersave1 import parse_campaignsstates
from utils.logging import get_logger, log_message
from utils.il2_paths import (
    find_campaignsstates_path,
    read_game_directory,
    resolve_campaigns_dir,
)
from utils.popup_state import load_popup_seen, save_popup_seen

logger = get_logger(__name__)

MISSION_PATTERNS = ("*.Mission*", "*.mission*", "*.msnbin", "*.MSNBIN")


def _sort_mission_ids(mission_ids: Iterable[str]) -> List[str]:
    def sort_key(mission_id: str) -> Tuple[int, int | str, str]:
        match = re.match(r"^(\d+)", mission_id)
        if match:
            return (0, int(match.group(1)), mission_id)
        return (1, mission_id, mission_id)

    return sorted({str(mission_id) for mission_id in mission_ids}, key=sort_key)


def _encode_stats(stats: Dict[str, object]) -> str:
    if not stats:
        return ""
    parts = []
    for stat_key, stat_val in stats.items():
        value_str = "" if stat_val is None else str(stat_val)
        parts.append(f"{stat_key}={value_str}")
    return urllib.parse.quote("&".join(parts), safe="")


def _encode_mission_dict(missions: Dict[str, object], *, is_stats: bool) -> str:
    if not missions:
        return ""
    mission_parts = []
    for mission_id in _sort_mission_ids(missions.keys()):
        encoded_id = urllib.parse.quote(str(mission_id), safe="")
        if is_stats:
            encoded_data = _encode_stats(missions.get(mission_id, {}))
        else:
            raw_value = missions.get(mission_id, "")
            raw_str = "" if raw_value is None else str(raw_value)
            encoded_data = urllib.parse.quote(raw_str, safe="")
        mission_parts.append(f"{encoded_id}={encoded_data}")
    subval_decoded = "&".join(mission_parts)
    return urllib.parse.quote(subval_decoded, safe="")


def _encode_campaignsstates(campaigns: Dict[str, dict]) -> str:
    entries = []
    for campaign_name, params in campaigns.items():
        if not isinstance(params, dict):
            continue
        param_parts = []
        for key, value in params.items():
            if key in ("characterStatisticsByFileName", "completedMissionsByFileName"):
                encoded_value = _encode_mission_dict(
                    value or {}, is_stats=(key == "characterStatisticsByFileName")
                )
                param_parts.append(f"{key}={encoded_value}")
            else:
                value_str = "" if value is None else str(value)
                encoded_value = urllib.parse.quote(value_str, safe="")
                param_parts.append(f"{key}={encoded_value}")
        param_string = "&".join(param_parts)
        encoded_value = urllib.parse.quote(param_string, safe="")
        encoded_name = urllib.parse.quote(str(campaign_name), safe="")
        entries.append(f"campaigns/{encoded_name}={encoded_value}")
    return "&".join(entries)


def _create_sync_backup(states_path: Path) -> Path | None:
    if not states_path.exists():
        log_message(logger, f"⚠️  {states_path} not found - cannot backup")
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{states_path.name}_{timestamp}.backup"
    backup_path = states_path.parent / backup_name

    try:
        shutil.copy2(states_path, backup_path)
        log_message(logger, f"✓ Backup created: {backup_path}")
        return backup_path
    except Exception as exc:
        log_message(logger, f"❌ Backup failed: {exc}")
        return None


def _collect_campaign_missions(campaigns_dir: Path) -> Dict[str, Set[str]]:
    mission_map = {}
    if not campaigns_dir.exists():
        return mission_map
    for folder in campaigns_dir.iterdir():
        if not folder.is_dir():
            continue
        mission_ids = set()
        for pattern in MISSION_PATTERNS:
            for mission_file in folder.glob(pattern):
                mission_ids.add(mission_file.stem)
        mission_map[folder.name.lower()] = mission_ids
    return mission_map


def _update_campaign_mission_dates(
    on_disk: Dict[str, Set[str]],
    mission_dates_path: Path = Path("campaign_mission_dates.json"),
) -> Tuple[bool, List[Tuple[str, List[str]]]]:
    if not mission_dates_path.exists():
        return False, []

    try:
        with open(mission_dates_path, "r", encoding="utf-8") as file:
            mission_dates = json.load(file)
    except Exception as exc:
        log_message(logger, f"⚠️  Could not read {mission_dates_path.name}: {exc}")
        return False, []

    updated = False
    removed_summary: List[Tuple[str, List[str]]] = []

    for campaign_name, data in mission_dates.items():
        if campaign_name == "game_directory":
            continue
        if not isinstance(data, dict):
            continue
        missions = data.get("missions")
        if not isinstance(missions, dict):
            continue
        on_disk_missions = on_disk.get(campaign_name.lower())
        if on_disk_missions is None:
            continue

        removed_missions = [
            mission_id
            for mission_id in list(missions.keys())
            if mission_id not in on_disk_missions
        ]
        if not removed_missions:
            continue

        for mission_id in removed_missions:
            missions.pop(mission_id, None)

        data["mission_count"] = len(missions)
        removed_summary.append((campaign_name, sorted(removed_missions)))
        updated = True

    if not updated:
        return False, []

    try:
        with open(mission_dates_path, "w", encoding="utf-8") as file:
            json.dump(mission_dates, file, indent=2, ensure_ascii=False)
    except Exception as exc:
        log_message(logger, f"⚠️  Could not save {mission_dates_path.name}: {exc}")
        return False, []

    log_message(logger, f"✓ {mission_dates_path.name} updated")
    return True, removed_summary


def _extract_mission_from_popup_key(key: str) -> str | None:
    parts = str(key).split("|")
    if len(parts) == 4:
        return parts[2]
    if len(parts) == 3:
        return parts[1]
    return None


def _prune_campaign_events(
    removed_by_campaign: Dict[str, Set[str]],
    events_path: Path = Path("campaign_events.json"),
) -> bool:
    if not events_path.exists():
        return False

    try:
        with open(events_path, "r", encoding="utf-8") as file:
            events_data = json.load(file)
    except Exception as exc:
        log_message(logger, f"⚠️  Could not read {events_path.name}: {exc}")
        return False

    if not isinstance(events_data, dict):
        log_message(logger, f"⚠️  Invalid {events_path.name} format; skipping cleanup.")
        return False

    updated = False

    for campaign_name, removed_missions in removed_by_campaign.items():
        campaign_data = events_data.get(campaign_name)
        if not isinstance(campaign_data, dict):
            continue
        events_list = campaign_data.get("events")
        if not isinstance(events_list, list):
            continue

        filtered_events = [
            event
            for event in events_list
            if str(event.get("mission", "")) not in removed_missions
        ]

        if len(filtered_events) != len(events_list):
            updated = True
            if filtered_events:
                campaign_data["events"] = filtered_events
            else:
                events_data.pop(campaign_name, None)

    if not updated:
        return False

    try:
        with open(events_path, "w", encoding="utf-8") as file:
            json.dump(events_data, file, indent=2, ensure_ascii=False)
    except Exception as exc:
        log_message(logger, f"⚠️  Could not save {events_path.name}: {exc}")
        return False

    log_message(logger, f"✓ {events_path.name} cleaned")
    return True


def _prune_popup_seen(
    removed_by_campaign: Dict[str, Set[str]],
    popup_seen_path: Path = Path("campaign_popups_seen.json"),
) -> bool:
    if not popup_seen_path.exists():
        return False

    popup_data = load_popup_seen(popup_seen_path)

    updated = False

    for campaign_name, removed_missions in removed_by_campaign.items():
        events = popup_data.get(campaign_name)
        if not isinstance(events, list):
            continue

        filtered_events = [
            key
            for key in events
            if (_extract_mission_from_popup_key(key) or "") not in removed_missions
        ]

        if len(filtered_events) != len(events):
            updated = True
            if filtered_events:
                popup_data[campaign_name] = filtered_events
            else:
                popup_data.pop(campaign_name, None)

    if not updated:
        return False

    save_popup_seen(popup_seen_path, popup_data)

    log_message(logger, f"✓ {popup_seen_path.name} cleaned")
    return True


def _prune_completion_state(
    removed_by_campaign: Dict[str, Set[str]],
    completion_state_path: Path = Path("campaign_completion_state.json"),
) -> bool:
    if not completion_state_path.exists():
        return False

    try:
        with open(completion_state_path, "r", encoding="utf-8") as file:
            state_data = json.load(file)
    except Exception as exc:
        log_message(logger, f"⚠️  Could not read {completion_state_path.name}: {exc}")
        return False

    if not isinstance(state_data, dict):
        log_message(logger, f"⚠️  Invalid {completion_state_path.name} format; skipping cleanup.")
        return False

    updated = False

    for campaign_name, removed_missions in removed_by_campaign.items():
        missions = state_data.get(campaign_name)
        if not isinstance(missions, list):
            continue
        filtered_missions = [
            mission_id for mission_id in missions if mission_id not in removed_missions
        ]
        if len(filtered_missions) != len(missions):
            updated = True
            if filtered_missions:
                state_data[campaign_name] = filtered_missions
            else:
                state_data.pop(campaign_name, None)

    if not updated:
        return False

    try:
        with open(completion_state_path, "w", encoding="utf-8") as file:
            json.dump(state_data, file, indent=2, ensure_ascii=False)
    except Exception as exc:
        log_message(logger, f"⚠️  Could not save {completion_state_path.name}: {exc}")
        return False

    log_message(logger, f"✓ {completion_state_path.name} cleaned")
    return True


def sync_campaign_states(states_path: str | None = None) -> bool:
    base_dir = Path.cwd()
    game_directory = read_game_directory(base_dir)
    if states_path is None:
        states_path_obj = find_campaignsstates_path(game_directory)
    else:
        states_path_obj = Path(states_path)

    if not states_path_obj or not states_path_obj.exists():
        log_message(logger, "❌ campaignsstates.txt not found. Aborting sync.")
        return False

    campaigns_dir = resolve_campaigns_dir(game_directory)
    if not campaigns_dir.exists():
        log_message(logger, f"⚠️  Campaigns directory not found: {campaigns_dir}")
        return False

    log_message(logger, f"Using campaignsstates.txt: {states_path_obj}")
    log_message(logger, f"Using campaigns directory: {campaigns_dir}")

    campaigns = parse_campaignsstates(str(states_path_obj))
    on_disk = _collect_campaign_missions(campaigns_dir)
    mission_dates_updated, mission_dates_removed = _update_campaign_mission_dates(
        on_disk
    )
    
    removed_summary = []
    added_summary = []
    
    for campaign_name, params in campaigns.items():
        if not isinstance(params, dict):
            continue
        folder_key = campaign_name.lower()
        on_disk_missions = on_disk.get(folder_key)
        if on_disk_missions is None:
            log_message(logger, f"⚠️  Campaign folder missing on disk: {campaign_name}")
            continue

        completed = params.get("completedMissionsByFileName", {}) or {}
        stats = params.get("characterStatisticsByFileName", {}) or {}
        decoded_ids = set(completed.keys()) | set(stats.keys())

        missing_on_disk = decoded_ids - on_disk_missions
        missing_in_state = on_disk_missions - decoded_ids

        if missing_on_disk:
            for mission_id in missing_on_disk:
                completed.pop(mission_id, None)
                stats.pop(mission_id, None)
            removed_summary.append((campaign_name, sorted(missing_on_disk)))
            
        if missing_in_state:
            added_summary.append((campaign_name, sorted(missing_in_state)))
            
        params["completedMissionsByFileName"] = completed
        params["characterStatisticsByFileName"] = stats

    if not removed_summary and not added_summary:
        log_message(logger, "✓ No campaign state updates required.")
        if mission_dates_updated:
            log_message(logger, "\nSUMMARY")
            log_message(logger, "=" * 70)
            for campaign_name, mission_ids in mission_dates_removed:
                log_message(logger, 
                    f"Removed {len(mission_ids)} mission(s) from campaign_mission_dates.json for "
                    f"{campaign_name}: {', '.join(mission_ids)}"
                )
            return True
        return False

    if not removed_summary:
        log_message(logger, "✓ No campaign state removals required.")
        log_message(logger, "ℹ️  New missions detected on disk will only update campaign_mission_dates.json.")
        for campaign_name, mission_ids in added_summary:
            log_message(logger, 
                f"Detected {len(mission_ids)} new mission(s) for {campaign_name}: "
                f"{', '.join(mission_ids)}"
            )
        if mission_dates_updated:
            log_message(logger, "\nSUMMARY")
            log_message(logger, "=" * 70)
            for campaign_name, mission_ids in mission_dates_removed:
                log_message(logger, 
                    f"Removed {len(mission_ids)} mission(s) from campaign_mission_dates.json for "
                    f"{campaign_name}: {', '.join(mission_ids)}"
                )
            return True    
        return False
        
    backup_path = _create_sync_backup(states_path_obj)
    if not backup_path:
        log_message(logger, "❌ Backup failed; aborting sync.")
        return False

    encoded = _encode_campaignsstates(campaigns)
    states_path_obj.write_text(encoded, encoding="utf-8")
    log_message(logger, "✓ campaignsstates.txt updated")

    removed_by_campaign = {
        campaign_name: set(mission_ids) for campaign_name, mission_ids in removed_summary
    }

    log_message(logger, "\nCleaning stale campaign state artifacts...")
    _prune_campaign_events(removed_by_campaign)
    _prune_popup_seen(removed_by_campaign)
    _prune_completion_state(removed_by_campaign)

    log_message(logger, "\nSUMMARY")
    log_message(logger, "=" * 70)
    for campaign_name, mission_ids in removed_summary:
        log_message(logger, 
            f"Removed {len(mission_ids)} missing mission(s) from {campaign_name}: "
            f"{', '.join(mission_ids)}"
        )
    for campaign_name, mission_ids in added_summary:
        log_message(logger, 
            f"Detected {len(mission_ids)} new mission(s) for {campaign_name} (no state update): "
            f"{', '.join(mission_ids)}"
        )
    if mission_dates_updated:
        for campaign_name, mission_ids in mission_dates_removed:
            log_message(logger, 
                f"Removed {len(mission_ids)} mission(s) from campaign_mission_dates.json for "
                f"{campaign_name}: {', '.join(mission_ids)}"
            )
            
    log_message(logger, "\nRe-decoding campaignsstates.txt to update campaigns_decoded.json...")
    try:
        if decode_campaignsstates(states_path=str(states_path_obj)):
            log_message(logger, "✓ campaigns_decoded.json successfully regenerated.")
        else:
            log_message(logger, "⚠️  Decoder reported failure; campaigns_decoded.json may be outdated.")
    except Exception as e:
        log_message(logger, f"⚠️  Could not re-decode campaigns_decoded.json: {e}")

    log_message(logger, "\nRegenerating campaign events and reports...")
    os.environ["FORCE_REGENERATE"] = "1"
    try:
        import step3_generate_events

        if step3_generate_events.main(args=["--auto"], show_popups=False):
            log_message(logger, "✓ Event regeneration complete.")
        else:
            log_message(logger, "⚠️  Event regeneration reported failure.")
    except Exception as e:
        log_message(logger, f"⚠️  Could not regenerate events: {e}")

    return True


if __name__ == "__main__":
    success = sync_campaign_states()
    raise SystemExit(0 if success else 1)
