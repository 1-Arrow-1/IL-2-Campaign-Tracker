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
from utils.il2_paths import (
    find_campaignsstates_path,
    read_game_directory,
    resolve_campaigns_dir,
)

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
        print(f"⚠️  {states_path} not found - cannot backup")
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{states_path.name}_{timestamp}.backup"
    backup_path = states_path.parent / backup_name

    try:
        shutil.copy2(states_path, backup_path)
        print(f"✓ Backup created: {backup_path}")
        return backup_path
    except Exception as exc:
        print(f"❌ Backup failed: {exc}")
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
        print(f"⚠️  Could not read {mission_dates_path.name}: {exc}")
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
        print(f"⚠️  Could not save {mission_dates_path.name}: {exc}")
        return False, []

    print(f"✓ {mission_dates_path.name} updated")
    return True, removed_summary


def sync_campaign_states(states_path: str | None = None) -> bool:
    base_dir = Path.cwd()
    game_directory = read_game_directory(base_dir)
    if states_path is None:
        states_path_obj = find_campaignsstates_path(game_directory)
    else:
        states_path_obj = Path(states_path)

    if not states_path_obj or not states_path_obj.exists():
        print("❌ campaignsstates.txt not found. Aborting sync.")
        return False

    campaigns_dir = resolve_campaigns_dir(game_directory)
    if not campaigns_dir.exists():
        print(f"⚠️  Campaigns directory not found: {campaigns_dir}")
        return False

    print(f"Using campaignsstates.txt: {states_path_obj}")
    print(f"Using campaigns directory: {campaigns_dir}")

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
            print(f"⚠️  Campaign folder missing on disk: {campaign_name}")
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
        print("✓ No campaign state updates required.")
        if mission_dates_updated:
            print("\nSUMMARY")
            print("=" * 70)
            for campaign_name, mission_ids in mission_dates_removed:
                print(
                    f"Removed {len(mission_ids)} mission(s) from campaign_mission_dates.json for "
                    f"{campaign_name}: {', '.join(mission_ids)}"
                )
            return True
        return False

    if not removed_summary:
        print("✓ No campaign state removals required.")
        print("ℹ️  New missions detected on disk will only update campaign_mission_dates.json.")
        for campaign_name, mission_ids in added_summary:
            print(
                f"Detected {len(mission_ids)} new mission(s) for {campaign_name}: "
                f"{', '.join(mission_ids)}"
            )
        if mission_dates_updated:
            print("\nSUMMARY")
            print("=" * 70)
            for campaign_name, mission_ids in mission_dates_removed:
                print(
                    f"Removed {len(mission_ids)} mission(s) from campaign_mission_dates.json for "
                    f"{campaign_name}: {', '.join(mission_ids)}"
                )
            return True    
        return False
        
    backup_path = _create_sync_backup(states_path_obj)
    if not backup_path:
        print("❌ Backup failed; aborting sync.")
        return False

    encoded = _encode_campaignsstates(campaigns)
    states_path_obj.write_text(encoded, encoding="utf-8")
    print("✓ campaignsstates.txt updated")

    print("\nSUMMARY")
    print("=" * 70)
    for campaign_name, mission_ids in removed_summary:
        print(
            f"Removed {len(mission_ids)} missing mission(s) from {campaign_name}: "
            f"{', '.join(mission_ids)}"
        )
    for campaign_name, mission_ids in added_summary:
        print(
            f"Detected {len(mission_ids)} new mission(s) for {campaign_name} (no state update): "
            f"{', '.join(mission_ids)}"
        )
    if mission_dates_updated:
        for campaign_name, mission_ids in mission_dates_removed:
            print(
                f"Removed {len(mission_ids)} mission(s) from campaign_mission_dates.json for "
                f"{campaign_name}: {', '.join(mission_ids)}"
            )
            
    print("\nRe-decoding campaignsstates.txt to update campaigns_decoded.json...")
    try:
        if decode_campaignsstates(states_path=str(states_path_obj)):
            print("✓ campaigns_decoded.json successfully regenerated.")
        else:
            print("⚠️  Decoder reported failure; campaigns_decoded.json may be outdated.")
    except Exception as e:
        print(f"⚠️  Could not re-decode campaigns_decoded.json: {e}")

    print("\nRegenerating campaign events and reports...")
    os.environ["FORCE_REGENERATE"] = "1"
    try:
        import step3_generate_events

        if step3_generate_events.main(args=["--auto"], show_popups=False):
            print("✓ Event regeneration complete.")
        else:
            print("⚠️  Event regeneration reported failure.")
    except Exception as e:
        print(f"⚠️  Could not regenerate events: {e}")

    return True


if __name__ == "__main__":
    success = sync_campaign_states()
    raise SystemExit(0 if success else 1)
