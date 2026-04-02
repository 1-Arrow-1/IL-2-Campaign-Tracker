"""
Flask API routes for Campaign Service Record.

Endpoints:
- GET /api/campaigns - List all campaigns
- GET /api/campaign/<name> - Get campaign details
- GET /api/pdf/<name> - Check PDF availability
- GET /api/health - Health check
- POST /api/ping - Keep-alive for idle shutdown
"""

import base64
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
import json
import logging
import os
import re
from datetime import datetime
import threading
import time
import traceback
from io import BytesIO
from pathlib import Path
from typing import Any, Optional

from flask import Blueprint, jsonify, request, current_app, send_file, send_from_directory

from campaign_service_record.core.data_loader import DataLoader
from campaign_service_record.core.campaign_aggregator import CampaignAggregator
from campaign_service_record.core.locale_resolver import resolve_detail_page_locale
from campaign_service_record.providers.career_provider import CareerDataProvider
from campaign_service_record.core.medal_showcase import (
    load_coordinates,
    load_career_coordinates,
    resolve_showcase_country,
    resolve_ussr_variant,
    earned_showcase_names_from_events,
    award_image_to_showcase_name,
    build_showcase_data,
    has_german_ext_medals,
    ASSET_FOLDER,
    CAREER_CANVAS_FILENAME,
    CAREER_OVERLAY_FILENAME,
)
from utils.formatting import safe_campaign_filename
from campaign_service_record.utils.path_utils import get_game_directory
from campaign_service_record.utils.image_utils import convert_dds_to_png_bytes, find_existing_image_path
from campaign_service_record.utils.pilot_photo import pilot_photo_path, pilot_photo_filename, pilot_name_path
from utils.locale_config import resolve_locale
from utils.supported_locales import DEFAULT_LOCALE, get_supported_locales, normalize_locale
from campaign_service_record.core.job_store import job_store, CAREER_DEBRIEF_PARSE
from campaign_service_record.career.debriefing_manager import CareerDebriefingManager
from campaign_service_record.weather_lookup import (
    game_coords_to_latlon,
    lookup_historical_weather,
    lookup_historical_weather_by_coords,
    read_eng_weather,
)
from utils.sorting import smart_mission_sort_key
from llm_story_generator import (
    build_campaign_story_input,
    build_story_input,
    delete_story_chapter_for,
    generate_and_store_chapter_for,
    load_or_create_story_state_for,
    load_story_chapters_for,
    save_story_state_for,
    strip_memory_entries_for_date,
    update_narrative_memory_local,
)
from utils.locale_config import load_settings
from utils.supported_locales import APP_TO_IL2_LOCALE, normalize_locale


logger = logging.getLogger(__name__)

# Blueprint
api_bp = Blueprint('api', __name__)

# Global instances (initialized by init_api)
_data_loader: Optional[DataLoader] = None
_aggregator: Optional[CampaignAggregator] = None
_reports_dir: Optional[Path] = None

# Career mode globals (initialized by init_career, optional)
_career_provider: Optional[CareerDataProvider] = None
_career_game_dir: Optional[Path] = None   # <game_dir>/data/swf/CampaignRanksAwards/...
_career_data_dir: Optional[Path] = None   # <data_dir>/CampaignRanksAwards/...

# Last activity timestamp (for idle shutdown)
_last_ping = [time.time()]

_PILOT_DESC_DEFAULT = "campaign_pilot"
_PERSONAL_DATA_FILENAME = "campaign_personal_data.json"

_STORY_EVENT_TYPES = [6, 8]
_STORY_SQUADRON_EVENT_TYPES = [6, 8, 10]
_STORY_MAX_BACKGROUND_CHARS = 1400
_STORY_MAX_NOTABLE_EVENTS = 12
_HONORS_FACTS_PATH = Path(__file__).resolve().parents[2] / "historical_context" / "honors_facts.json"
_HONORS_FACTS_CACHE: dict[str, Any] | None = None


def _sanitize_pilot_name(name: Optional[str]) -> Optional[str]:
    if name is None:
        return None
    cleaned = name.strip()
    return cleaned or None


def _get_personal_data_path() -> Optional[Path]:
    base_dir = current_app.config.get('PERSONAL_DATA_DIR')
    if not base_dir:
        return None
    return Path(base_dir) / _PERSONAL_DATA_FILENAME


def _load_personal_data() -> dict:
    data_path = _get_personal_data_path()
    if not data_path or not data_path.exists():
        return {}
    try:
        with open(data_path, 'r', encoding='utf-8') as file:
            payload = json.load(file)
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("Failed to read personal data file %s: %s", data_path, exc)
        return {}
    if isinstance(payload, dict):
        return payload
    logger.error("Invalid personal data format in %s", data_path)
    return {}


def _save_personal_data(data: dict) -> bool:
    data_path = _get_personal_data_path()
    if not data_path:
        return False
    try:
        data_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = data_path.with_suffix(f"{data_path.suffix}.tmp")
        with open(tmp_path, 'w', encoding='utf-8') as file:
            json.dump(data, file, indent=2, ensure_ascii=False)
        tmp_path.replace(data_path)
        return True
    except OSError as exc:
        logger.error("Failed to save personal data to %s: %s", data_path, exc, exc_info=True)
        return False


def _sanitize_personal_data_value(value: Optional[str]) -> str:
    if value is None:
        return ''
    return str(value).strip()


def _parse_bool(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return value != 0
    text = str(value).strip().lower()
    if not text:
        return default
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def _load_story_settings() -> dict:
    settings = load_settings()
    stories = settings.get("stories", {})
    if not isinstance(stories, dict):
        stories = {}
    provider = str(stories.get("provider") or "openai").strip().lower() or "openai"
    provider_defaults = {
        "openai": "https://api.openai.com/v1",
        "openrouter": "https://openrouter.ai/api/v1",
        "anthropic": "https://api.anthropic.com/v1",
        "google": "https://generativelanguage.googleapis.com/v1beta/openai",
        "microsoft": "https://YOUR-RESOURCE-NAME.openai.azure.com/openai/v1",
        "custom": "",
    }
    base_url = str(stories.get("base_url") or provider_defaults.get(provider, "")).strip()
    provider_keys = stories.get("api_keys", {})
    selected_provider_key = ""
    if isinstance(provider_keys, dict):
        selected_provider_key = str(provider_keys.get(provider) or "").strip()
    api_key = str(selected_provider_key or stories.get("api_key") or os.environ.get("OPENAI_API_KEY") or "").strip()
    model = str(stories.get("model") or "gpt-5-mini").strip() or "gpt-5-mini"
    locale = normalize_locale(str(settings.get("locale") or "en"))
    return {
        "enabled": _parse_bool(stories.get("enabled", False), default=False),
        "configured": bool(api_key and model and (base_url or provider == "openai")),
        "api_key": api_key,
        "provider": provider,
        "base_url": base_url,
        "model": model,
        "story_language": locale,
        "auto_generate": _parse_bool(stories.get("auto_generate", False), default=False),
    }


def _humanize_story_label(value: Optional[str]) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return text.replace("_", " ").strip()


def _normalize_honor_lookup_text(value: object) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    text = re.sub(r"[\s\-_]+", " ", text)
    text = re.sub(r"[^a-z0-9 ]+", "", text)
    return " ".join(text.split())


def _country_to_honors_key(country: object) -> str:
    value = _normalize_honor_lookup_text(country)
    mapping = {
        "germany": "germany",
        "deutschland": "germany",
        "soviet union": "ussr",
        "ussr": "ussr",
        "soviet": "ussr",
        "britain": "uk",
        "great britain": "uk",
        "united kingdom": "uk",
        "uk": "uk",
        "usa": "usa",
        "united states": "usa",
        "united states of america": "usa",
    }
    return mapping.get(value, value)


def _load_honors_facts() -> dict[str, Any]:
    global _HONORS_FACTS_CACHE
    if isinstance(_HONORS_FACTS_CACHE, dict):
        return _HONORS_FACTS_CACHE
    try:
        payload = json.loads(_HONORS_FACTS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {}
    _HONORS_FACTS_CACHE = payload if isinstance(payload, dict) else {}
    return _HONORS_FACTS_CACHE


def _lookup_honor_fact(country: object, category: str, name: object) -> str:
    country_key = _country_to_honors_key(country)
    name_norm = _normalize_honor_lookup_text(name)
    if not country_key or not name_norm:
        return ""

    facts = _load_honors_facts()
    countries = facts.get("countries", {}) if isinstance(facts, dict) else {}
    country_block = countries.get(country_key, {}) if isinstance(countries, dict) else {}
    entries = country_block.get(category, []) if isinstance(country_block, dict) else []
    if not isinstance(entries, list):
        return ""

    best_fact = ""
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        aliases = entry.get("aliases", [])
        if not isinstance(aliases, list):
            continue
        fact = _normalize_story_text(entry.get("fact"))
        if not fact:
            continue
        normalized_aliases = [_normalize_honor_lookup_text(alias) for alias in aliases if _normalize_honor_lookup_text(alias)]
        if not normalized_aliases:
            continue
        if name_norm in normalized_aliases:
            return fact
        if any(alias in name_norm or name_norm in alias for alias in normalized_aliases):
            best_fact = best_fact or fact
    return best_fact


def _build_honors_context(
    country: object,
    mission_promotion: object,
    mission_awards: list[str] | tuple[str, ...] | None,
) -> dict[str, Any]:
    promotion_name = _normalize_story_text(mission_promotion)
    promotion_fact = _lookup_honor_fact(country, "ranks", promotion_name) if promotion_name else ""
    promotion_payload = {"name": promotion_name, "fact": promotion_fact} if promotion_name else {}

    awards_payload: list[dict[str, str]] = []
    seen_awards: set[str] = set()
    for award_name_raw in list(mission_awards or []):
        award_name = _normalize_story_text(award_name_raw)
        if not award_name:
            continue
        key = _normalize_honor_lookup_text(award_name)
        if key in seen_awards:
            continue
        seen_awards.add(key)
        fact = _lookup_honor_fact(country, "awards", award_name)
        awards_payload.append({"name": award_name, "fact": fact})

    return {
        "promotion": promotion_payload,
        "awards": awards_payload,
    }


def _classify_story_error(exc: Exception) -> tuple[str, str]:
    text = str(exc or "").lower()
    if any(fragment in text for fragment in ("api key", "authentication", "unauthorized", "401")):
        return "auth_error", "API authentication failed. Check provider, model, and API key."
    if any(fragment in text for fragment in ("quota", "billing", "insufficient", "429")):
        return "quota_error", "API quota exhausted or billing is unavailable."
    if any(fragment in text for fragment in ("connection", "timeout", "network", "dns", "connect")):
        return "network_error", "Provider API is currently unreachable."
    detail = _normalize_story_text(exc)
    if detail:
        if len(detail) > 220:
            detail = f"{detail[:220].rstrip()}..."
        return "api_error", f"Story generation failed: {detail}"
    return "api_error", "Story generation failed."


def _build_story_status_payload(source: str, entry_id: str) -> dict:
    source = str(source or "").strip().lower()
    settings = _load_story_settings()
    chapters = load_story_chapters_for(source, entry_id) if source in {"career", "campaign"} else []
    if chapters:
        chapters = [chapter for chapter in chapters if _is_valid_story_text(chapter.get("story_text"))]
        def _chapter_sort_key(chapter: dict) -> tuple:
            date_value = _parse_story_date(_normalize_story_text(chapter.get("date")))
            if not date_value:
                mission_id = _normalize_story_text(chapter.get("mission_id"))
                if mission_id.startswith("day:"):
                    date_value = _parse_story_date(_normalize_story_text(mission_id.split(":", 1)[1]))
            mission_id = _normalize_story_text(chapter.get("mission_id"))
            try:
                chapter_idx = int(chapter.get("chapter_index") or 0)
            except (TypeError, ValueError):
                chapter_idx = 0
            return (date_value or "9999-12-31", mission_id, chapter_idx)

        chapters = sorted(chapters, key=_chapter_sort_key)
        for idx, chapter in enumerate(chapters, start=1):
            chapter["chapter_index"] = idx
    if source not in {"career", "campaign"}:
        return {
            "supported": False,
            "enabled": settings["enabled"],
            "configured": settings["configured"],
            "auto_generate": settings["auto_generate"],
            "provider": settings["provider"],
            "model": settings["model"],
            "status": "unsupported",
            "message": "AI stories are not supported for this data source.",
            "chapters": chapters,
        }

    if not settings["enabled"]:
        status = "disabled"
        message = "AI stories are disabled in Settings Manager."
    elif not settings["configured"]:
        status = "not_configured"
        message = "AI stories are enabled, but no OpenAI API key is configured."
    elif chapters:
        status = "ready"
        message = ""
    else:
        status = "ready"
        message = "No story chapters have been generated yet."

    return {
        "supported": True,
        "enabled": settings["enabled"],
        "configured": settings["configured"],
        "auto_generate": settings["auto_generate"],
        "provider": settings["provider"],
        "model": settings["model"],
        "story_language": settings["story_language"],
        "status": status,
        "message": message,
        "chapters": chapters,
    }


def _normalize_story_text(value: object) -> str:
    return str(value or "").strip()


def _canonical_mission_id(value: object) -> str:
    text = _normalize_story_text(value)
    if not text:
        return ""
    if re.fullmatch(r"\d+", text):
        try:
            return str(int(text))
        except ValueError:
            return text
    return text.lower()


def _lookup_by_mission_id(mapping: object, mission_id: object) -> dict:
    if not isinstance(mapping, dict):
        return {}
    mid = _normalize_story_text(mission_id)
    if not mid:
        return {}
    if isinstance(mapping.get(mid), dict):
        return mapping[mid]

    variants = []
    if re.fullmatch(r"\d+", mid):
        try:
            num = int(mid)
            variants.extend([str(num), f"{num:02d}", f"{num:03d}"])
        except ValueError:
            pass
    for key in variants:
        if isinstance(mapping.get(key), dict):
            return mapping[key]
    return {}


def _is_valid_story_text(value: object) -> bool:
    text = _normalize_story_text(value)
    if not text:
        return False
    lower = text.lower()
    if lower.startswith("{'format':") or lower.startswith('{"format":'):
        return False
    if "verbosity" in lower and "format" in lower and len(text) < 180:
        return False
    return True


def _clean_story_html(text: str) -> str:
    if not text:
        return ""
    clean = text
    clean = clean.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    clean = re.sub(r"(?is)</li>", "\n", clean)
    clean = re.sub(r"(?is)<li>", "- ", clean)
    clean = re.sub(r"(?is)<[^>]+>", "", clean)
    clean = clean.replace("&nbsp;", " ")
    clean = re.sub(r"[ \t]+", " ", clean)
    clean = re.sub(r"\n{3,}", "\n\n", clean)
    return clean.strip()


def _extract_story_info_field(content: str, key: str) -> str:
    quoted = re.search(rf"&{key}\s*=\s*\"([\s\S]*?)\"", content, flags=re.IGNORECASE)
    if quoted:
        return _normalize_story_text(quoted.group(1))
    unquoted = re.search(rf"&{key}\s*=\s*([^\r\n]+)", content, flags=re.IGNORECASE)
    if unquoted:
        return _normalize_story_text(unquoted.group(1))
    return ""


def _find_campaign_folder(campaign_name: str) -> Optional[Path]:
    mission_dates = _data_loader.get_campaign_mission_dates() if _data_loader else {}
    game_dir = _normalize_story_text(mission_dates.get("game_directory")) if isinstance(mission_dates, dict) else ""
    if not game_dir:
        return None
    campaigns_root = Path(game_dir) / "data" / "Campaigns"
    if not campaigns_root.exists():
        return None
    direct = campaigns_root / campaign_name
    if direct.exists():
        return direct
    lower = campaign_name.lower()
    for candidate in campaigns_root.iterdir():
        if candidate.is_dir() and candidate.name.lower() == lower:
            return candidate
    return None


def _read_campaign_info_context(campaign_name: str, story_language: str) -> dict:
    folder = _find_campaign_folder(campaign_name)
    if not folder:
        return {"campaign_name": campaign_name, "background_excerpt": ""}

    il2_locale = APP_TO_IL2_LOCALE.get(story_language, "eng")
    candidates = [
        folder / f"info.locale={il2_locale}.txt",
        folder / "info.locale=eng.txt",
    ]

    content = ""
    for path in candidates:
        if path.exists():
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
                break
            except OSError:
                continue
    if not content:
        return {"campaign_name": campaign_name, "background_excerpt": ""}

    campaign_display_name = _extract_story_info_field(content, "name") or campaign_name
    description = _extract_story_info_field(content, "description")
    if not description:
        return {"campaign_name": campaign_display_name, "background_excerpt": ""}

    tracker_split = re.split(r"(?is)\bMission Debriefings\b|\bEvents\b", description, maxsplit=1)
    description = tracker_split[0] if tracker_split else description
    description = _clean_story_html(description)
    if len(description) > _STORY_MAX_BACKGROUND_CHARS:
        description = f"{description[:_STORY_MAX_BACKGROUND_CHARS].rstrip()}..."

    return {
        "campaign_name": campaign_display_name,
        "background_excerpt": description,
    }


def _parse_story_date(text: str) -> str:
    value = _normalize_story_text(text)
    if not value:
        return ""
    for fmt in ("%d %B, %Y", "%d %B %Y", "%B %d, %Y", "%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return ""



def _seconds_to_hms(total_seconds: int) -> str:
    value = max(0, int(total_seconds or 0))
    hours = value // 3600
    remainder = value % 3600
    minutes = remainder // 60
    seconds = remainder % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _extract_career_notable_events(mission_json: dict) -> list[str]:
    events = mission_json.get("events", [])
    if not isinstance(events, list):
        return []
    notable: list[str] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        ev_type = _normalize_story_text(event.get("type")).lower()
        target = _normalize_story_text(event.get("target"))
        if ev_type == "kill" and target:
            category = _normalize_story_text(event.get("category", "")).lower()
            altitude = event.get("altitude")
            detail_parts = []
            if category:
                detail_parts.append(category)
            if altitude is not None:
                try:
                    detail_parts.append(f"{int(altitude)}m altitude")
                except (TypeError, ValueError):
                    pass
            suffix = f" ({', '.join(detail_parts)})" if detail_parts else ""
            notable.append(f"Destroyed {target}{suffix}")
        elif ev_type == "damage taken":
            damage = _normalize_story_text(event.get("damage"))
            attacker = _normalize_story_text(event.get("target"))
            unknown = event.get("attacker_unknown")
            if attacker:
                notable.append(f"Aircraft took damage from {attacker}: {damage}" if damage else f"Aircraft took damage from {attacker}")
            elif unknown:
                notable.append(f"Aircraft took damage (attacker unknown): {damage}" if damage else "Aircraft took damage (attacker unknown)")
            else:
                notable.append(f"Aircraft took damage: {damage}" if damage else "Aircraft took damage")
        elif ev_type in {"bailout", "crash", "landing", "takeoff"}:
            notable.append(ev_type.capitalize())
        if len(notable) >= _STORY_MAX_NOTABLE_EVENTS:
            break
    return notable


def _build_fallback_career_mission_json(result) -> dict:
    duration_seconds = 0
    try:
        duration_seconds = int(float(result.duration_seconds or 0))
    except (TypeError, ValueError):
        duration_seconds = 0

    kills = 0
    try:
        kills = int(result.kills or 0)
    except (TypeError, ValueError):
        kills = 0

    return {
        "player": {
            "name": "",
            "aircraft": _normalize_story_text(getattr(result, "aircraft", "")),
        },
        "summary": {
            "final_state": _normalize_story_text(getattr(result, "final_state", "")) or "Unknown",
            "flight_duration": _seconds_to_hms(duration_seconds),
            "aircraft_damage": 0,
            "pilot_damage": 0,
            "air_kills_flying": kills,
            "ground_kills": 0,
            "naval_kills": 0,
        },
        "events": [],
    }


def _parse_campaign_mission_boxes(debriefings_html: str) -> list[dict]:
    if not debriefings_html:
        return []
    # Avoid regex-nesting pitfalls: mission-box blocks may contain nested <div>.
    # Split by opener and consume until next opener.
    chunks = re.split(r'(?is)<div\s+class="mission-box">', debriefings_html)
    boxes = [chunk for chunk in chunks[1:] if _normalize_story_text(chunk)]
    parsed: list[dict] = []
    for box in boxes:
        header_match = re.search(r"(?is)<b>\s*MISSION\s+(.+?)\s*</b>", box)
        header_text = _clean_story_html(header_match.group(1)) if header_match else ""
        mission_id = ""
        header_date = ""
        if "|" in header_text:
            left, right = header_text.split("|", 1)
            mission_id = _normalize_story_text(left)
            header_date = _normalize_story_text(right)
        else:
            mission_id = _normalize_story_text(header_text)

        aircraft_line_match = re.search(r"(?is)Aircraft:\s*(.+?)<br>", box)
        aircraft_line = _clean_story_html(aircraft_line_match.group(0)) if aircraft_line_match else ""

        aircraft = ""
        duration = ""
        result = ""
        aircraft_damage = 0.0
        pilot_damage = 0.0
        for segment in [seg.strip() for seg in aircraft_line.split("|")]:
            lower = segment.lower()
            if lower.startswith("aircraft:"):
                aircraft = _normalize_story_text(segment.split(":", 1)[1])
            elif lower.startswith("duration:"):
                duration = _normalize_story_text(segment.split(":", 1)[1])
            elif lower.startswith("status:"):
                result = _normalize_story_text(segment.split(":", 1)[1])
            elif lower.startswith("aircraft dmg:"):
                value = _normalize_story_text(segment.split(":", 1)[1]).replace("%", "")
                try:
                    aircraft_damage = float(value)
                except ValueError:
                    pass
            elif lower.startswith("pilot dmg:"):
                value = _normalize_story_text(segment.split(":", 1)[1]).replace("%", "")
                try:
                    pilot_damage = float(value)
                except ValueError:
                    pass

        events_block_match = re.search(r"(?is)<b>\s*FLIGHT LOG\s*</b><br>(.*)$", box)
        events_text = _clean_story_html(events_block_match.group(1)) if events_block_match else ""
        notable_events: list[str] = []
        for raw_line in events_text.splitlines():
            line = _normalize_story_text(re.sub(r"^\d{2}:\d{2}:\d{2}\s+", "", raw_line))
            if not line:
                continue
            lower = line.lower()
            if any(token in lower for token in ("destroyed", "hit by", "takeoff", "landing", "crash", "bailout", "wounded", "injured")):
                notable_events.append(line)
            if len(notable_events) >= _STORY_MAX_NOTABLE_EVENTS:
                break

        parsed.append({
            "mission_id": mission_id,
            "header_date": header_date,
            "parsed_date": _parse_story_date(header_date),
            "aircraft": aircraft,
            "duration": duration,
            "result": result,
            "aircraft_damage": aircraft_damage,
            "pilot_damage": pilot_damage,
            "notable_events": notable_events,
        })
    return parsed


def _build_campaign_story_contexts(campaign_name: str, story_language: str) -> list[dict]:
    if not _data_loader or not _aggregator:
        raise RuntimeError("Campaign data providers are not initialized.")

    personal_data = _load_personal_data()
    campaign_personal = personal_data.get(campaign_name, {}) if isinstance(personal_data, dict) else {}
    pilot_last_name = _sanitize_personal_data_value(campaign_personal.get("name"))

    detail = _aggregator.get_campaign_detail(campaign_name)
    if not detail:
        raise ValueError(f"Campaign not found: {campaign_name}")

    completion_state = _data_loader.get_campaign_completion_state()
    completed_missions = list(completion_state.get(campaign_name, []) or [])
    completed_missions = sorted(
        [_normalize_story_text(mid) for mid in completed_missions if _normalize_story_text(mid)],
        key=smart_mission_sort_key,
    )

    mission_dates = _data_loader.get_mission_dates_for_campaign(campaign_name)
    mission_dates_map = mission_dates.get("missions", {}) if isinstance(mission_dates, dict) else {}
    mission_aircraft_map = _data_loader.get_mission_aircraft_map(campaign_name)
    decoded = _data_loader.get_campaigns_decoded().get(campaign_name, {})
    stats_by_mission = decoded.get("characterStatisticsByFileName", {}) if isinstance(decoded, dict) else {}
    events_data = _data_loader.get_campaign_events()
    campaign_events = events_data.get(campaign_name, {}) if isinstance(events_data, dict) else {}
    progression_events = campaign_events.get("events", []) if isinstance(campaign_events, dict) else []

    info_context = _read_campaign_info_context(campaign_name, story_language)
    mission_boxes = _parse_campaign_mission_boxes(_normalize_story_text(detail.get("debriefings_html")))
    mission_box_by_id = {
        _canonical_mission_id(item.get("mission_id")): item
        for item in mission_boxes
        if _normalize_story_text(item.get("mission_id"))
    }
    mission_box_order = [
        _normalize_story_text(item.get("mission_id"))
        for item in mission_boxes
        if _normalize_story_text(item.get("mission_id"))
    ]

    # Primary ordering source for campaign stories should be the visible debrief order.
    # This avoids skips when completion_state is sparse/out-of-sync.
    ordered_mission_ids: list[str] = []
    seen_mission_ids: set[str] = set()
    # Add mission IDs from decoded stats as an extra reliable source.
    stats_mission_ids = list(stats_by_mission.keys()) if isinstance(stats_by_mission, dict) else []
    for mid in mission_box_order + completed_missions + stats_mission_ids:
        key = _normalize_story_text(mid)
        if not key:
            continue
        canonical = _canonical_mission_id(key)
        if canonical in seen_mission_ids:
            continue
        seen_mission_ids.add(canonical)
        ordered_mission_ids.append(key)
    if not ordered_mission_ids:
        return []

    # Normalize mission processing order to chronological sequence.
    # This guarantees "Generate Missing Stories" advances by earliest date first.
    ordered_mission_ids = sorted(
        ordered_mission_ids,
        key=lambda mid: (
            _normalize_story_text(
                (mission_dates_map.get(mid, {}) if isinstance(mission_dates_map, dict) else {}).get("normalized_date")
            )
            or _normalize_story_text((mission_box_by_id.get(_canonical_mission_id(mid), {}) or {}).get("parsed_date"))
            or "9999-12-31",
            smart_mission_sort_key(mid),
        ),
    )

    cumulative_awards: list[str] = []
    current_rank = ""
    for event in progression_events:
        mission_ref = _normalize_story_text(event.get("mission"))
        if mission_ref.lower() != "initial":
            continue
        event_type = _normalize_story_text(event.get("type")).lower()
        if event_type == "promotion":
            current_rank = _normalize_story_text(event.get("rank"))
        elif event_type == "award":
            award = _humanize_story_label(event.get("name"))
            if award:
                cumulative_awards.append(award)

    _game_dir = get_game_directory(_data_loader.get_campaign_mission_dates()) if _data_loader else ""

    contexts: list[dict] = []
    _accumulated_air_kills_campaign: int = 0

    for index, mission_id in enumerate(ordered_mission_ids, start=1):
        mid = _normalize_story_text(mission_id)
        mission_meta = _lookup_by_mission_id(mission_dates_map, mid)
        mission_box = mission_box_by_id.get(_canonical_mission_id(mid), {})
        mission_stats = _lookup_by_mission_id(stats_by_mission, mid)
        aircraft_entry = _lookup_by_mission_id(mission_aircraft_map, mid)

        mission_awards: list[str] = []
        mission_promotion = ""
        for event in progression_events:
            if _normalize_story_text(event.get("mission")).lower() != mid.lower():
                continue
            event_type = _normalize_story_text(event.get("type")).lower()
            if event_type == "promotion":
                mission_promotion = _normalize_story_text(event.get("rank"))
            elif event_type == "award":
                award = _humanize_story_label(event.get("name"))
                if award:
                    mission_awards.append(award)

        rank_during_mission = current_rank
        if mission_promotion:
            current_rank = mission_promotion
        for award in mission_awards:
            cumulative_awards.append(award)

        mission_date = _normalize_story_text(mission_meta.get("normalized_date"))
        if not mission_date:
            mission_date = _normalize_story_text(mission_box.get("parsed_date"))

        summary = {
            "result": _normalize_story_text(mission_box.get("result")) or "Unknown",
            "duration": _normalize_story_text(mission_box.get("duration")),
            "aircraft_damage": mission_box.get("aircraft_damage", 0),
            "pilot_damage": mission_box.get("pilot_damage", 0),
            "air_kills": int(mission_stats.get("killLightPlane", 0) or 0) + int(mission_stats.get("killMediumPlane", 0) or 0) + int(mission_stats.get("killHeavyPlane", 0) or 0),
            "ground_kills": int(mission_stats.get("killAAAGun", 0) or 0) + int(mission_stats.get("killMachinegun", 0) or 0) + int(mission_stats.get("killCannon", 0) or 0) + int(mission_stats.get("killRadar", 0) or 0) + int(mission_stats.get("killTransportVehicle", 0) or 0) + int(mission_stats.get("killLightArmoredVehicle", 0) or 0) + int(mission_stats.get("killMediumArmoredVehicle", 0) or 0) + int(mission_stats.get("killHeavyArmoredVehicle", 0) or 0) + int(mission_stats.get("killBridge", 0) or 0) + int(mission_stats.get("killFacility", 0) or 0) + int(mission_stats.get("killRailroadStation", 0) or 0) + int(mission_stats.get("killRailroadCarriage", 0) or 0) + int(mission_stats.get("killLocomotive", 0) or 0) + int(mission_stats.get("killRocketLauncher", 0) or 0) + int(mission_stats.get("killSearchlight", 0) or 0) + int(mission_stats.get("killResidentalBuilding", 0) or 0) + int(mission_stats.get("killStaticPlane", 0) or 0),
            "naval_kills": int(mission_stats.get("killLightShip", 0) or 0) + int(mission_stats.get("killDestroyerShip", 0) or 0) + int(mission_stats.get("killLargeCargoShip", 0) or 0) + int(mission_stats.get("killSubmarine", 0) or 0),
        }

        aircraft = _normalize_story_text(mission_box.get("aircraft"))
        if not aircraft:
            aircraft = _normalize_story_text(aircraft_entry.get("aircraft"))

        _accumulated_air_kills_campaign += summary.get("air_kills", 0)

        story_input = build_campaign_story_input(
            campaign_id=campaign_name,
            mission_id=mid,
            mission_date=mission_date,
            mission_summary=summary,
            mission_events=mission_box.get("notable_events", []),
            rank=rank_during_mission,
            pilot_last_name=pilot_last_name,
            aircraft=aircraft,
            campaign_display_name=_normalize_story_text(info_context.get("campaign_name")),
            campaign_background=_normalize_story_text(info_context.get("background_excerpt")),
            country=_normalize_story_text(detail.get("country")),
            awards=list(cumulative_awards),
            promotion=current_rank,
            mission_awards=mission_awards,
            mission_promotion=mission_promotion,
            honors_context=_build_honors_context(
                _normalize_story_text(detail.get("country")),
                mission_promotion,
                mission_awards,
            ),
            missions_completed=index,
        )
        story_input.setdefault("career_progress", {})["aerial_victories"] = _accumulated_air_kills_campaign
        _weather = read_eng_weather(_game_dir, campaign_name, mid)
        if _weather:
            story_input.setdefault("mission", {})["weather"] = _weather
        contexts.append(story_input)

    return contexts


def _normalize_career_sortie_stats(row: dict) -> dict:
    """Translate cp.db sortie column names to KILL_MAPPING canonical names.

    cp.db uses different column names than the campaign characterStatisticsByFileName
    JSON that KILL_MAPPING was originally designed for.  This function sums the
    correct cp.db columns into each canonical key so that _combat_results_flowables()
    and aggregate_kills_from_missions() produce correct results for careers.
    """
    def _g(*keys: str) -> int:
        return sum(int(row.get(k) or 0) for k in keys)

    return {
        # ── Aircraft (column names match campaign format) ────────────────────
        'killLightPlane':          _g('killLightPlane'),
        'killMediumPlane':         _g('killMediumPlane'),
        'killHeavyPlane':          _g('killHeavyPlane'),
        'killStaticPlane':         _g('killStaticPlane'),
        'killMediumAerostat':      _g('killMediumAerostat'),   # balloons; 0 if absent

        # ── Vehicles ────────────────────────────────────────────────────────
        # Use only atomic columns; killLightTransport/killMediumTransport/killHeavyTransport
        # are accumulated rollups that would double-count killTruck/killCar.
        'killTransportVehicle':    _g('killTruck', 'killCar'),
        'killLightArmoredVehicle': _g('killLightTank'),
        'killMediumArmoredVehicle':_g('killMediumTank'),
        'killHeavyArmoredVehicle': _g('killHeavyTank'),

        # ── Railroad ────────────────────────────────────────────────────────
        'killLocomotive':          _g('killTrainLocomotive'),
        'killRailroadCarriage':    _g('killTrainVagon'),
        'killRailroadStation':     _g('killRailwayStationFacility'),

        # ── Armaments ───────────────────────────────────────────────────────
        'killMachinegun':          _g('killMachineGun'),        # capital G in cp.db
        'killCannon':              _g('killFieldGun', 'killHowitzer', 'killNavalGun'),
        # killAirDefence is the accumulated column that already includes all flak/AA types.
        'killAAAGun':              _g('killAirDefence'),
        'killRocketLauncher':      _g('killRocketLauncher'),
        'killSearchlight':         _g('killSearchlight'),
        'killRadar':               _g('killRadar'),             # 0 if absent

        # ── Buildings ───────────────────────────────────────────────────────
        'killResidentalBuilding':  _g('killTownBuilding', 'killRuralYard'),
        'killFacility':            _g('killAirfieldFacility', 'killFactoryBuilding'),
        'killBridge':              _g('killBridge'),

        # ── Marine (column names match campaign format) ──────────────────────
        'killLightShip':           _g('killLightShip'),
        'killLargeCargoShip':      _g('killLargeCargoShip'),
        'killSubmarine':           _g('killSubmarine'),
        'killDestroyerShip':       _g('killDestroyerShip'),
    }


def _build_career_story_contexts(root_career_id: int, llm_config: Optional[dict] = None) -> list[dict]:
    if not _career_provider:
        raise RuntimeError("Career provider not initialized.")

    aggregator = _career_provider._aggregator
    resolver = _career_provider._resolver
    db = _career_provider._db

    career = resolver.get_career(root_career_id)
    if career is None:
        raise ValueError(f"Career not found: {root_career_id}")
    if aggregator._cache_dir is None:
        raise RuntimeError("Career cache directory is not configured.")

    debrief_manager = CareerDebriefingManager(
        db=db,
        career=career,
        linker=aggregator._linker,
        cache_dir=aggregator._cache_dir,
    )
    results = debrief_manager._get_results()
    cache = debrief_manager._load_cache()

    segment_by_pilot = {int(pid): idx for idx, pid in enumerate(career.all_pilot_ids)}
    segment_rows = {int(row["id"]): row for row in career.chain}
    raw_events = db.get_events_for_pilots(career.all_pilot_ids, types=_STORY_EVENT_TYPES)
    raw_events.sort(
        key=lambda row: (
            segment_by_pilot.get(int(row["pilotId"]), 0),
            str(row["date"] or ""),
        )
    )

    mission_rows: list[dict] = []

    def _resolve_career_mission_date(result_obj, mission_row_obj) -> str:
        if mission_row_obj is not None:
            resolved = _normalize_story_text(aggregator._format_date(mission_row_obj["startTime"]))
            if resolved:
                return resolved
        parsed_from_label = _parse_story_date(_normalize_story_text(getattr(result_obj, "mission_date", "")))
        if parsed_from_label:
            return parsed_from_label
        return f"mission-{int(getattr(result_obj, 'mission_id', 0) or 0):08d}"

    for result in results:
        mission_json = None
        cache_entry = cache.get(str(result.mission_id), {})
        report_path_str = str(cache_entry.get("report_path") or "").strip()
        if report_path_str:
            report_path = Path(report_path_str)
            json_path = report_path.with_suffix(".events.json")
            if json_path.exists():
                try:
                    mission_json = json.loads(json_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    mission_json = None
        if mission_json is None:
            mission_json = _build_fallback_career_mission_json(result)

        mission_row = db.get_mission_by_id(result.mission_id)
        mission_date_iso = _resolve_career_mission_date(result, mission_row)

        mission_segment_index = next(
            (idx for idx, row in enumerate(career.chain) if int(row["id"]) == result.career_id),
            0,
        )
        mission_segment = segment_rows.get(result.career_id)
        squadron_name = ""
        if mission_segment is not None:
            try:
                squadron_name = aggregator._resolve_squadron_name(int(mission_segment["squadronId"])) or ""
            except Exception:
                squadron_name = ""

        sortie_stats: dict = {}
        if mission_segment is not None:
            try:
                _pilot_id_for_sortie = int(mission_segment["playerId"])
                _sortie_row = db.get_sortie_for_mission(int(result.mission_id), _pilot_id_for_sortie)
                if _sortie_row:
                    sortie_stats = _normalize_career_sortie_stats(dict(_sortie_row))
            except Exception:
                pass

        mission_rows.append({
            "mission_id": int(result.mission_id),
            "mission_date": mission_date_iso,
            "segment_index": mission_segment_index,
            "segment": dict(mission_segment) if mission_segment is not None else {},
            "squadron_name": squadron_name,
            "mission_json": mission_json,
            "sortie_stats": sortie_stats,
            "sort_key": (
                mission_date_iso,
                mission_segment_index,
                int(result.mission_id),
            ),
        })

    if not mission_rows:
        return []

    mission_rows.sort(key=lambda row: row["sort_key"])

    contexts: list[dict] = []

    # Track awards and promotions that have already been attributed to a mission chapter,
    # so the same award/promotion is not repeated in multiple same-day mission chapters.
    _attributed_awards: set[str] = set()
    _attributed_promotions: set[str] = set()

    # Reconstruct pilot's initial rank from promotion event history.
    # pilot.rankId in the DB reflects the CURRENT rank (updated in-place on each promotion),
    # so we cannot read it for the starting rank. Instead:
    #   - If there is at least one promotion event: the pilot's first rank is one step below
    #     the rank they were first promoted TO (IL-2 careers never skip ranks).
    #   - If there are no promotion events: pilot.rankId IS the starting rank (never promoted).
    _CAREER_COUNTRY_INT = {"germany": 201, "britain": 102, "usa": 103, "ussr": 101}
    initial_career_rank = ""
    try:
        country_int = _CAREER_COUNTRY_INT.get((career.country or "").lower(), 0)
        first_promo_event = next(
            (e for e in raw_events if int(e["type"] or -1) == 6),
            None,
        )
        if first_promo_event is not None:
            initial_rank_id = max(0, int(first_promo_event["rankId"] or 0) - 1)
        else:
            initial_pilot_row = db.get_pilot_by_id(career.pilot_id)
            initial_rank_id = int((initial_pilot_row["rankId"] if initial_pilot_row else None) or 0)
        rank_name = aggregator._rank_resolver.resolve(country_int, initial_rank_id)
        initial_career_rank = _normalize_story_text(rank_name.display if rank_name else "") or ""
    except Exception:
        initial_career_rank = ""

    _accumulated_air_kills: int = 0
    _narrative_memory: dict = {}

    for mission_index, row in enumerate(mission_rows, start=1):
        mission_date = row["mission_date"]
        mission_id = int(row["mission_id"])
        segment_index = int(row["segment_index"])
        squadron_name = _normalize_story_text(row["squadron_name"])
        mission_json = row["mission_json"]

        try:
            awards: list[str] = []
            mission_awards: list[str] = []
            promotions_this_mission: list[str] = []
            rank = initial_career_rank
            rank_before_mission = initial_career_rank
            for raw_event in raw_events:
                try:
                    event_segment_index = segment_by_pilot.get(int(raw_event["pilotId"]), 0)
                except (TypeError, ValueError):
                    continue
                event_date_iso = aggregator._format_date(raw_event["date"])
                include = (
                    event_segment_index < segment_index
                    or (event_segment_index == segment_index and event_date_iso and event_date_iso <= mission_date)
                )
                if not include:
                    continue

                mapped = aggregator._map_event(raw_event, career.country)
                if not mapped:
                    continue
                if mapped.get("type") == "promotion":
                    mapped_rank = _normalize_story_text(mapped.get("rank"))
                    if mapped_rank:
                        if event_date_iso and event_date_iso < mission_date:
                            rank_before_mission = mapped_rank
                        rank = mapped_rank
                        if event_date_iso == mission_date and event_segment_index == segment_index:
                            promotions_this_mission.append(mapped_rank)
                elif mapped.get("type") == "award":
                    award_name = _humanize_story_label(mapped.get("name"))
                    if award_name:
                        awards.append(award_name)
                        if event_date_iso == mission_date and event_segment_index == segment_index:
                            mission_awards.append(award_name)

            # Deduplicate within this mission, then remove any already attributed to a prior chapter.
            promotions_deduped = list(dict.fromkeys(
                [_normalize_story_text(v) for v in promotions_this_mission if _normalize_story_text(v)]
            ))
            new_promotions = [p for p in promotions_deduped if p not in _attributed_promotions]
            _attributed_promotions.update(new_promotions)
            promotion_this_mission = ", ".join(new_promotions)

            mission_awards = list(dict.fromkeys([name for name in mission_awards if name]))
            mission_awards = [a for a in mission_awards if a not in _attributed_awards]
            _attributed_awards.update(mission_awards)

            awards = list(dict.fromkeys([name for name in awards if name]))

            summary = mission_json.get("summary", {}) if isinstance(mission_json, dict) else {}
            aircraft_label = _normalize_story_text(
                (mission_json.get("player", {}) if isinstance(mission_json, dict) else {}).get("aircraft")
            ) or ""
            mission_result = _normalize_story_text(summary.get("final_state")) or "Unknown"

            # Accumulate career air kills (excludes ground/naval).
            _mission_air_kills = int(
                summary.get("air_kills_flying", summary.get("air_kills", 0)) or 0
            )
            _accumulated_air_kills += _mission_air_kills

            notables = _extract_career_notable_events(mission_json)
            notables = notables[:_STORY_MAX_NOTABLE_EVENTS]

            squadron_context = _build_squadron_context_for_mission(
                db,
                aggregator,
                career,
                row["segment"],
                mission_id,
                mission_date,
            )
            for key in ("promotions", "awards", "transfers"):
                squadron_context[key] = squadron_context.get(key, [])[:8]
            for key in ("kia", "mia", "wia"):
                squadron_context[key] = squadron_context.get(key, [])[:12]

            mission_story_input = build_story_input(
                mission_json,
                career_id=root_career_id,
                mission_id=mission_id,
                mission_date=mission_date,
                squadron=squadron_name,
                country=career.country or "",
                llm_config=llm_config,
                pilot_last_name=career.pilot_last_name or "",
                rank=rank_before_mission or rank,
                awards=awards,
                promotion=promotion_this_mission,
                mission_awards=mission_awards,
                mission_promotion=promotion_this_mission,
                honors_context=_build_honors_context(career.country, promotion_this_mission, mission_awards),
                squadron_context=squadron_context,
                missions_completed=mission_index,
                narrative_memory=_narrative_memory,
            )
            mission_story_input["career_progress"]["aerial_victories"] = _accumulated_air_kills
            mission_story_input["mission"]["notable_events"] = notables
            mission_story_input["mission"]["result"] = mission_result
            if aircraft_label:
                mission_story_input["pilot"]["aircraft"] = aircraft_label
            mission_story_input["chapter_scope"] = {
                "scope": "mission",
                "missions_in_chapter": 1,
                "mission_ids": [str(mission_id)],
                "mission_results": [mission_result],
                # Per-mission JSON payload — used by the PDF generator, ignored by LLM prompt builder.
                "mission_jsons": [
                    {
                        "mission_id": str(mission_id),
                        "aircraft": aircraft_label,
                        "json": mission_json if isinstance(mission_json, dict) else {},
                        "sortie_stats": row.get("sortie_stats") or {},
                    }
                ],
            }

            pilot_name = " ".join(
                part for part in (career.pilot_first_name, career.pilot_last_name) if part
            ).strip()
            if pilot_name:
                mission_story_input["pilot"]["name"] = pilot_name
            _narrative_memory = update_narrative_memory_local(mission_story_input, _narrative_memory)
            # Weather: try airfield-level precision from spawn position + map origin.
            # Fall back to theatre-level lookup from infoId / squadron name.
            if mission_date:
                _spawn_x = (mission_json.get("player", {}) if isinstance(mission_json, dict) else {}).get("spawn_x")
                _spawn_z = (mission_json.get("player", {}) if isinstance(mission_json, dict) else {}).get("spawn_z")
                _theatre_id = (row.get("segment") or {}).get("infoId") or ""
                _weather = None
                if _spawn_x is not None and _spawn_z is not None and _theatre_id:
                    _latlon = game_coords_to_latlon(float(_spawn_x), float(_spawn_z), _theatre_id)
                    if _latlon:
                        _lat_c, _lon_c = _latlon
                        _weather = lookup_historical_weather_by_coords(
                            _lat_c, _lon_c, f"{squadron_name} airfield", mission_date
                        )
                if _weather is None:
                    _weather = lookup_historical_weather(_theatre_id or squadron_name, mission_date)
                if _weather:
                    mission_story_input.setdefault("mission", {})["weather"] = _weather
            contexts.append(mission_story_input)
        except Exception as exc:
            logger.warning(
                "Skipping career story mission context for %s (mission %s): %s",
                root_career_id,
                mission_id,
                exc,
                exc_info=True,
            )
            fallback_json = _build_fallback_career_mission_json(
                type(
                    "FallbackResult",
                    (),
                    {
                        "duration_seconds": 0,
                        "kills": 0,
                        "final_state": "Unknown",
                        "aircraft": _normalize_story_text(
                            (mission_json or {}).get("player", {}).get("aircraft", "")
                            if isinstance(mission_json, dict) else ""
                        ),
                    },
                )()
            )
            fallback_input = build_story_input(
                fallback_json,
                career_id=root_career_id,
                mission_id=mission_id,
                mission_date=mission_date,
                squadron="",
                pilot_last_name=career.pilot_last_name or "",
                rank="",
                awards=[],
                promotion="",
                mission_awards=[],
                mission_promotion="",
                honors_context={"promotion": {}, "awards": []},
                squadron_context={
                    "promotions": [],
                    "awards": [],
                    "transfers": [],
                    "kia": [],
                    "mia": [],
                    "wia": [],
                },
                missions_completed=mission_index,
                narrative_memory={},
            )
            fallback_input["chapter_scope"] = {
                "scope": "mission",
                "missions_in_chapter": 1,
                "mission_ids": [str(mission_id)],
                "mission_results": [],
            }
            pilot_name = " ".join(
                part for part in (career.pilot_first_name, career.pilot_last_name) if part
            ).strip()
            if pilot_name:
                fallback_input["pilot"]["name"] = pilot_name
            contexts.append(fallback_input)
            continue

    return contexts


def _pilot_display_name(row) -> str:
    first = str(row["name"] or "").strip() if "name" in row.keys() else ""
    last = str(row["lastName"] or "").strip() if "lastName" in row.keys() else ""
    if first and last:
        return f"{first} {last}"
    return first or last or "Unknown Pilot"


def _build_squadron_context_for_mission(
    db,
    aggregator,
    career,
    mission_segment,
    mission_id: int,
    mission_date_iso: str,
) -> dict:
    """
    Build reliable squadron-context facts for one mission.

    Only uses cp.db-derived facts:
      - member promotions/awards/transfers on mission date
      - member WIA/MIA/KIA sortie states on this mission
    """
    empty = {
        "promotions": [],
        "awards": [],
        "transfers": [],
        "kia": [],
        "mia": [],
        "wia": [],
    }
    if mission_segment is None:
        return empty

    try:
        segment_career_id = int(mission_segment["id"])
        segment_player_id = int(mission_segment["playerId"])
        squadron_id = int(mission_segment["squadronId"])
    except Exception:
        return empty

    members = db.get_squadron_members(squadron_id) if squadron_id else []
    if not members:
        return empty

    member_by_id = {}
    member_ids = []
    for row in members:
        pid = int(row["id"])
        if pid == segment_player_id:
            continue
        member_ids.append(pid)
        member_by_id[pid] = _pilot_display_name(row)
    if not member_ids:
        return empty

    # Event-driven updates (same mission date only)
    member_events = db.get_events_for_pilots(member_ids, types=_STORY_SQUADRON_EVENT_TYPES)
    for ev in member_events:
        ev_date = aggregator._format_date(ev["date"])
        if ev_date != mission_date_iso:
            continue
        pid = int(ev["pilotId"])
        who = member_by_id.get(pid, f"Pilot {pid}")
        mapped = aggregator._map_event(ev, career.country)
        if not mapped:
            continue
        ev_type = mapped.get("type")
        if ev_type == "promotion":
            rank_name = str(mapped.get("rank") or "").strip()
            if rank_name:
                empty["promotions"].append({"pilot": who, "rank": rank_name})
        elif ev_type == "award":
            award_name = _humanize_story_label(mapped.get("name"))
            if award_name:
                empty["awards"].append({"pilot": who, "award": award_name})
        elif ev_type == "transfer":
            to_cfg = int(ev["squadronId"] or 0) if "squadronId" in ev.keys() else 0
            to_name = ""
            if to_cfg:
                to_name = aggregator._resolve_squadron_name_by_config(segment_career_id, to_cfg) or ""
            if not to_name and to_cfg:
                to_name = f"Squadron {to_cfg}"
            empty["transfers"].append({
                "pilot": who,
                "to_squadron": to_name,
            })

    # Sortie status updates (this exact mission)
    # Known mapping in this codebase:
    #   2 = KIA, 3 = MIA, 4 = WIA
    mission_sorties = db.get_sorties_for_mission_pilots(mission_id, member_ids)
    for sortie in mission_sorties:
        pid = int(sortie["pilotId"])
        who = member_by_id.get(pid, f"Pilot {pid}")
        status = int(sortie["status"] or 0)
        if status == 2:
            empty["kia"].append(who)
        elif status == 3:
            empty["mia"].append(who)
        elif status == 4:
            empty["wia"].append(who)

    return empty


def init_api(data_dir: Path, reports_dir: Optional[Path] = None):
    """
    Initialize API with data loader and aggregator.
    
    Args:
        data_dir: Directory containing JSON files
        reports_dir: Directory containing PDF reports (optional)
    """
    global _data_loader, _aggregator, _reports_dir
    
    _data_loader = DataLoader(data_dir, enable_cache=True)
    _aggregator = CampaignAggregator(_data_loader)
    _reports_dir = reports_dir or (data_dir / 'reports')
    
    logger.info(f"API initialized with data_dir={data_dir}")


def init_career(
    db_path: Path,
    reports_dir: Optional[Path] = None,
    game_dir: Optional[Path] = None,
    data_dir: Optional[Path] = None,
) -> bool:
    """
    Initialize the Career mode provider.

    Called from app.py only when cp.db is confirmed present and readable.
    Safe to call multiple times (re-initializes on each call).

    Args:
        db_path:     Absolute path to cp.db.
        reports_dir: Directory to search for missionReport .txt/.mlg files.
                     Defaults to <game_dir>/data/FlightLogs when not supplied.
        game_dir:    IL-2 game root directory (optional; used for FlightLogs
                     auto-detection and squadron name lookups).
                     If omitted, CareerDatabase derives it from db_path
                     (<game_dir>/data/Career/cp.db).
        data_dir:    Tracker data directory (optional; used as fallback for
                     squadron name lookups via <data_dir>/CampaignRanksAwards/).

    Returns:
        True if initialization succeeded, False otherwise.
    """
    global _career_provider, _career_game_dir, _career_data_dir

    from campaign_service_record.career.database import CareerDatabase
    from campaign_service_record.career.chain_resolver import CareerChainResolver
    from campaign_service_record.career.statistics import StatisticsMapper
    from campaign_service_record.career.mission_linker import MissionReportLinker
    from campaign_service_record.career.aggregator import CareerAggregator

    try:
        db = CareerDatabase(db_path)

        # One-time DB maintenance: reconcile AI pilot kill-plane rollup counters.
        # Runs before any data is served so the squadron table is always correct.
        from campaign_service_record.career.db_maintenance import fix_pilot_kill_plane_totals
        fix_pilot_kill_plane_totals(db_path)

        # Resolve reports_dir: prefer explicit arg, fall back to FlightLogs in game_dir,
        # then db.game_dir (derived from cp.db path), then CWD as last resort.
        resolved_reports_dir = reports_dir
        if resolved_reports_dir is None:
            _gd = game_dir or db.game_dir
            if _gd is not None:
                fl = _gd / 'data' / 'FlightLogs'
                if fl.is_dir():
                    resolved_reports_dir = fl
                    logger.info("Career reports_dir auto-detected: %s", fl)
                else:
                    logger.warning(
                        "FlightLogs not found at %s; missionReport linking will be unavailable", fl
                    )
        if resolved_reports_dir is None:
            resolved_reports_dir = Path('.')

        resolver = CareerChainResolver(db)
        stats = StatisticsMapper()
        linker = MissionReportLinker(resolved_reports_dir)
        aggregator = CareerAggregator(
            db, resolver, stats, linker, game_dir=game_dir, data_dir=data_dir
        )
        _career_provider = CareerDataProvider(db, resolver, aggregator)
        _career_game_dir = game_dir
        _career_data_dir = data_dir
        logger.info("Career mode initialized: db=%s", db_path)
        return True
    except Exception as exc:
        logger.error("Failed to initialize career mode: %s", exc, exc_info=True)
        _career_provider = None
        return False


def get_last_ping() -> float:
    """Get last ping timestamp (for idle monitoring)."""
    return _last_ping[0]


@api_bp.route('/api/debug/data')
def debug_data():
    """
    Debug endpoint to see raw data.
    
    Returns raw data from all JSON files for debugging.
    """
    if not _data_loader:
        return jsonify({'error': 'API not initialized'}), 500
    
    try:
        completion_state = _data_loader.get_campaign_completion_state()
        campaigns_with_progress = _data_loader.get_campaigns_with_progress()
        events = _data_loader.get_campaign_events()
        mission_dates = _data_loader.get_campaign_mission_dates()
        
        return jsonify({
            'completion_state': completion_state,
            'campaigns_with_progress': campaigns_with_progress,
            'events_keys': list(events.keys()) if events else [],
            'mission_dates_keys': list(mission_dates.keys()) if isinstance(mission_dates, dict) else [],
            'total_campaigns': len(completion_state) if completion_state else 0,
            'campaigns_with_missions': len(campaigns_with_progress),
        })
    except Exception as e:
        logger.error(f"Debug endpoint error: {e}", exc_info=True)
        return jsonify({
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


@api_bp.route('/api/career/debug')
def career_debug():
    """
    Career mode debug endpoint.

    Returns the current rank resolver mode, game_dir, and the exact
    charactersranks path being checked.  Useful for diagnosing why mod
    ranks are not being detected after moving the folder.
    """
    if not _career_provider:
        return jsonify({'error': 'Career provider not initialized'}), 503

    aggregator = _career_provider._aggregator
    resolver = aggregator._rank_resolver
    game_dir = aggregator._game_dir

    charactersranks_path = (
        str(game_dir / 'data' / 'swf' / 'il2' / 'charactersranks')
        if game_dir else None
    )
    charactersranks_exists = (
        (game_dir / 'data' / 'swf' / 'il2' / 'charactersranks').is_dir()
        if game_dir else False
    )

    return jsonify({
        'rank_mode': 'mod' if resolver._mod_dir else 'standard',
        'mod_dir': str(resolver._mod_dir) if resolver._mod_dir else None,
        'game_dir': str(game_dir) if game_dir else None,
        'charactersranks_path_checked': charactersranks_path,
        'charactersranks_exists_now': charactersranks_exists,
        # Index sizes — 0 means CampaignRanksAwards was not found; detail page
        # events will render without images but should not crash.
        'award_index_entries': len(aggregator._award_index),
        'rank_index_entries': len(aggregator._rank_index),
    })


# ============================================================================
# Health & Status Endpoints
# ============================================================================

@api_bp.route('/api/locale')
def get_locale():
    """
    Get current locale setting.
    
    Returns the locale from environment variable CAMPAIGN_TRACKER_LOCALE,
    or defaults to 'en'.
    
    Returns:
        JSON with locale code:
        {
            "locale": "de"
        }
    """
    locale = resolve_locale()
    return jsonify({'locale': normalize_locale(locale, DEFAULT_LOCALE)})



@api_bp.route('/api/locales')
def get_locales():
    """
    Get list of supported locales.

    Returns:
        JSON with locale list:
        {
            "locales": ["en", "de"]
        }
    """
    return jsonify({'locales': get_supported_locales(), 'default': DEFAULT_LOCALE})


@api_bp.route('/api/health')
def health_check():
    """
    Health check endpoint.
    
    Returns:
        JSON with status and data source info
    """
    if not _data_loader:
        return jsonify({
            'status': 'error',
            'message': 'API not initialized'
        }), 500
    
    # Check if any data is available
    campaigns = _data_loader.get_campaigns_with_progress()
    
    return jsonify({
        'status': 'ok',
        'campaigns_available': len(campaigns),
        'data_dir': str(_data_loader.data_dir),
        'cache_stats': _data_loader.get_cache_stats()
    })


@api_bp.route('/api/ping', methods=['POST'])
def ping():
    """
    Keep-alive ping endpoint.
    
    Updates last activity timestamp to prevent idle shutdown.
    Frontend should ping every 30 seconds while active.
    """
    _last_ping[0] = time.time()
    return jsonify({'ok': True})


# ============================================================================
# Pilot Photo Endpoints
# ============================================================================

@api_bp.route('/api/pilot_photo')
def get_pilot_photo():
    """Get the stored pilot photo path, if available."""
    desc = request.args.get('desc', _PILOT_DESC_DEFAULT)
    photo_dir = current_app.config.get('PILOT_PHOTO_DIR')
    frozen = current_app.config.get('FROZEN', False)

    if not photo_dir:
        return jsonify({'path': None, 'name': None})

    photo_path = pilot_photo_path(Path(photo_dir), desc)
    name_path = pilot_name_path(Path(photo_dir), desc)
    name_value = None
    if name_path.exists():
        try:
            name_value = _sanitize_pilot_name(name_path.read_text(encoding='utf-8'))
        except OSError as exc:
            logger.warning("Failed to read pilot name from %s: %s", name_path, exc)

    if not photo_path.exists():
        return jsonify({'path': None, 'name': name_value})

    filename = pilot_photo_filename(desc)
    if frozen:
        return jsonify({'path': f'/pilot_photos/{filename}', 'name': name_value})
    return jsonify({'path': f'/static/pilot_photos/{filename}', 'name': name_value})


@api_bp.route('/api/save_pilot_photo', methods=['POST'])
def save_pilot_photo():
    """Save a cropped pilot photo from the client."""
    desc = request.form.get('desc', _PILOT_DESC_DEFAULT)
    img_data = request.form.get('img_data')
    pilot_name = request.form.get('pilot_name')
    logger.info(
        "Pilot photo upload received: desc=%s content_type=%s content_length=%s",
        desc,
        request.content_type,
        request.content_length
    )
    if not img_data:
        return jsonify({'error': 'No image data'}), 400

    match = re.match(r'^data:image/(png|jpeg|jpg|bmp|gif|webp);base64,', img_data)
    if not match:
        return jsonify({'error': 'Unsupported image format'}), 400

    try:
        img_str = re.sub(r'^data:image/\w+;base64,', '', img_data)
        img_str = ''.join(img_str.split())
        remainder = len(img_str) % 4
        if remainder == 1:
            raise ValueError("Invalid base64 length")
        if remainder:
            img_str += '=' * (4 - remainder)
        img_bytes = base64.b64decode(img_str, validate=True)
    except (ValueError, base64.binascii.Error) as exc:
        logger.warning("Invalid image payload: %s", exc)
        return jsonify({'error': 'Invalid image data. Please choose a different image.'}), 400

    photo_dir = current_app.config.get('PILOT_PHOTO_DIR')
    frozen = current_app.config.get('FROZEN', False)
    if not photo_dir:
        return jsonify({'error': 'Photo storage not configured'}), 500

    photo_path = pilot_photo_path(Path(photo_dir), desc)
    logger.info("Saving pilot photo to %s (bytes=%s)", photo_path, len(img_bytes))
    try:
        photo_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = photo_path.with_suffix(f"{photo_path.suffix}.tmp")
        with open(tmp_path, 'wb') as tmp_file:
            tmp_file.write(img_bytes)
        tmp_path.replace(photo_path)
    except OSError as exc:
        logger.error(
            "Failed to save pilot photo to %s: %s",
            photo_path,
            exc,
            exc_info=True
        )
        return jsonify({'error': 'Failed to save photo'}), 500

    filename = pilot_photo_filename(desc)
    name_path = pilot_name_path(Path(photo_dir), desc)
    name_value = _sanitize_pilot_name(pilot_name)
    if pilot_name is not None:
        try:
            if name_value:
                name_path.parent.mkdir(parents=True, exist_ok=True)
                name_path.write_text(name_value, encoding='utf-8')
            elif name_path.exists():
                name_path.unlink()
        except OSError as exc:
            logger.error("Failed to save pilot name to %s: %s", name_path, exc, exc_info=True)
            return jsonify({'error': 'Failed to save pilot name'}), 500

    if frozen:
        return jsonify({'path': f'/pilot_photos/{filename}', 'name': name_value})
    return jsonify({'path': f'/static/pilot_photos/{filename}', 'name': name_value})


# ============================================================================
# Campaign Personal Data Endpoints
# ============================================================================

@api_bp.route('/api/campaign/<campaign_name>/personal_data')
def get_campaign_personal_data(campaign_name: str):
    """Get stored personal data for a campaign."""
    data = _load_personal_data()
    return jsonify(data.get(campaign_name, {}))


@api_bp.route('/api/campaign/<campaign_name>/personal_data', methods=['POST'])
def save_campaign_personal_data(campaign_name: str):
    """Save personal data for a campaign."""
    if not request.is_json:
        return jsonify({'error': 'Invalid payload'}), 400
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify({'error': 'Invalid payload'}), 400

    cleaned = {
        'name': _sanitize_personal_data_value(payload.get('name')),
        'first_name': _sanitize_personal_data_value(payload.get('first_name')),
        'birthday': _sanitize_personal_data_value(payload.get('birthday')),
        'birth_place': _sanitize_personal_data_value(payload.get('birth_place')),
        'birth_country': _sanitize_personal_data_value(payload.get('birth_country')),
        'additional_notes': _sanitize_personal_data_value(payload.get('additional_notes'))
    }

    data = _load_personal_data()
    data[campaign_name] = cleaned
    if not _save_personal_data(data):
        return jsonify({'error': 'Failed to save personal data'}), 500
    return jsonify(cleaned)


# ============================================================================
# Career Personal Data Endpoints
# ============================================================================

@api_bp.route('/api/career/<int:root_career_id>/personal_data')
def get_career_personal_data(root_career_id: int):
    """Get stored personal data for a career."""
    data = _load_personal_data()
    return jsonify(data.get(str(root_career_id), {}))


@api_bp.route('/api/career/<int:root_career_id>/personal_data', methods=['POST'])
def save_career_personal_data(root_career_id: int):
    """Save personal data for a career."""
    if not request.is_json:
        return jsonify({'error': 'Invalid payload'}), 400
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify({'error': 'Invalid payload'}), 400

    cleaned = {
        'name': _sanitize_personal_data_value(payload.get('name')),
        'first_name': _sanitize_personal_data_value(payload.get('first_name')),
        'birthday': _sanitize_personal_data_value(payload.get('birthday')),
        'birth_country': _sanitize_personal_data_value(payload.get('birth_country')),
        'additional_notes': _sanitize_personal_data_value(payload.get('additional_notes'))
    }

    data = _load_personal_data()
    data[str(root_career_id)] = cleaned
    if not _save_personal_data(data):
        return jsonify({'error': 'Failed to save personal data'}), 500
    return jsonify(cleaned)


# ============================================================================
# Campaign List Endpoint
# ============================================================================

@api_bp.route('/api/campaigns')
def get_campaigns():
    """
    Get list of all campaigns with progress.
    
    Used by landing page to display campaign list.
    
    Returns:
        JSON array of campaigns:
        [
            {
                "name": "kerch",
                "display_name": "Kerch Peninsula Campaign",
                "country": "ussr",
                "missions_completed": 15,
                "promotions_count": 3,
                "awards_count": 8,
                "final_rank": "Senior Sergeant"
            },
            ...
        ]
    """
    _last_ping[0] = time.time()
    
    try:
        if not _aggregator:
            return jsonify({
                'error': 'API not initialized'
            }), 500
        
        campaigns = _aggregator.get_campaign_list()
        
        logger.info(f"Served campaign list: {len(campaigns)} campaigns")
        return jsonify(campaigns)
        
    except Exception as e:
        logger.error(f"Error getting campaign list: {e}", exc_info=True)
        return jsonify({
            'error': 'Failed to load campaigns',
            'detail': str(e)
        }), 500


# ============================================================================
# Campaign Detail Endpoint
# ============================================================================

@api_bp.route('/api/campaign/<campaign_name>')
def get_campaign_detail(campaign_name: str):
    """
    Get detailed campaign data.
    
    Used by detail page to display full campaign service record.
    
    Args:
        campaign_name: Campaign identifier (e.g., "kerch")
    
    Returns:
        JSON with complete campaign data:
        {
            "name": "kerch",
            "display_name": "Kerch Peninsula Campaign",
            "country": "ussr",
            "missions_completed": 15,
            "events": [...],
            "debriefings_html": "...",
            "summary": {...}
        }
    """
    _last_ping[0] = time.time()
    
    try:
        if not _aggregator:
            return jsonify({
                'error': 'API not initialized'
            }), 500
        
        # Use campaign name directly (Flask already URL-decodes it safely)
        # Note: Campaign names come from JSON keys, so they're trusted
        # Normalize case for consistency
        campaign_name = campaign_name.lower()
        campaign_data = _aggregator.get_campaign_detail(campaign_name)

        if not campaign_data:
            logger.warning(f"Campaign not found: {campaign_name}")
            return jsonify({
                'error': 'Campaign not found',
                'campaign': campaign_name
            }), 404

        # effective_locale = UI locale for the detail page (global or explicit override)
        # Follows the global locale unrestricted; only explicit per-campaign overrides
        # are limited to en/de/ru (stored in campaign_mission_dates.json).
        effective_locale = resolve_detail_page_locale(
            campaign_name,
            data_loader=_data_loader
        )
        campaign_data['effective_locale'] = effective_locale

        # Select the pre-generated debriefings HTML.
        # Pre-generated content only exists for en/de/ru, so the HTML selection
        # is capped independently from the UI locale.
        debriefings_locale = effective_locale if effective_locale in ('en', 'de', 'ru') else 'en'
        localized_key = f'debriefings_html_{debriefings_locale}'
        localized_debriefings = campaign_data.get(localized_key, '')
        if localized_debriefings and localized_debriefings.strip():
            campaign_data['debriefings_html'] = localized_debriefings
            logger.debug(f"Using localized debriefings ({debriefings_locale}) for {campaign_name}")
        elif debriefings_locale != 'en':
            # debriefings_locale was de/ru but no pre-generated content — fall back to English
            logger.info(f"No localized debriefings for '{debriefings_locale}', "
                        f"falling back to English for {campaign_name}")
            en_debriefings = campaign_data.get('debriefings_html_en', '')
            if en_debriefings and en_debriefings.strip():
                campaign_data['debriefings_html'] = en_debriefings
        # effective_locale is intentionally NOT changed here — UI locale stays as global

        # Remove the localized versions from response (no need to send all 3)
        for locale in ('en', 'de', 'ru'):
            campaign_data.pop(f'debriefings_html_{locale}', None)

        logger.info(f"Served campaign detail: {campaign_name}")
        return jsonify(campaign_data)
        
    except Exception as e:
        logger.error(f"Error getting campaign detail for {campaign_name}: {e}", exc_info=True)
        return jsonify({
            'error': 'Failed to load campaign details',
            'detail': str(e)
        }), 500


# ============================================================================
# PDF Report Endpoint
# ============================================================================

@api_bp.route('/api/pdf/<campaign_name>')
def check_pdf_exists(campaign_name: str):
    """
    Check if PDF report exists for campaign.
    
    Returns path if exists, otherwise 404.
    Frontend uses this to show/hide download button.
    
    Args:
        campaign_name: Campaign identifier
    
    Returns:
        JSON with PDF info or 404 if not found
    """
    _last_ping[0] = time.time()
    
    try:
        if not _reports_dir:
            return jsonify({
                'error': 'Reports directory not configured'
            }), 404
        
        # Generate expected PDF filename using campaign name directly
        campaign_name = campaign_name.lower()
        pdf_filename = f"{safe_campaign_filename(campaign_name)}.pdf"
        pdf_path = _reports_dir / pdf_filename
        
        if pdf_path.exists():
            # Return relative path for frontend
            return jsonify({
                'available': True,
                'filename': pdf_filename,
                'path': f'reports/{pdf_filename}',
                'size': pdf_path.stat().st_size
            })
        else:
            return jsonify({
                'available': False,
                'message': 'PDF report not generated yet'
            }), 404
            
    except Exception as e:
        logger.error(f"Error checking PDF for {campaign_name}: {e}", exc_info=True)
    return jsonify({
        'error': 'Failed to check PDF availability',
        'detail': str(e)
    }), 500


# ============================================================================
# Game Assets Endpoint
# ============================================================================

@api_bp.route('/api/game_assets/<path:asset_path>')
def get_game_asset(asset_path: str):
    """Serve game assets from the IL-2 installation swf directory."""
    if not _data_loader:
        return jsonify({'error': 'API not initialized'}), 500

    mission_dates = _data_loader.get_campaign_mission_dates()
    game_directory = get_game_directory(mission_dates)
    if not game_directory:
        return jsonify({'error': 'Game directory not configured'}), 404

    swf_dir = Path(game_directory) / 'data' / 'swf'
    requested = (swf_dir / asset_path).resolve()

    if swf_dir not in requested.parents and swf_dir != requested:
        logger.warning("Blocked invalid asset path: %s", asset_path)
        return jsonify({'error': 'Invalid asset path'}), 400

    existing = find_existing_image_path(requested)
    if not existing:
        logger.warning("Game asset not found: %s", requested)
        return jsonify({'error': 'Asset not found'}), 404

    if existing.suffix.lower() == ".dds":
        png_bytes = convert_dds_to_png_bytes(existing)
        if not png_bytes:
            return jsonify({'error': 'Failed to convert DDS asset'}), 500
        return send_file(
            BytesIO(png_bytes),
            mimetype="image/png",
            download_name=existing.with_suffix(".png").name
        )

    return send_from_directory(swf_dir, asset_path)


# ============================================================================
# Career Assets Endpoint
# ============================================================================

@api_bp.route('/api/career_assets/<path:asset_path>')
def get_career_asset(asset_path: str):
    """
    Serve CampaignRanksAwards images for the Career mode event list and modals.

    Tries candidate roots in order:
      1. <data_dir>/<asset_path>           (tracker's local CampaignRanksAwards copy)
      2. <game_dir>/data/swf/<asset_path>  (IL-2 game installation)

    DDS files are converted to PNG on-the-fly.
    """
    if not _career_provider:
        return jsonify({'error': 'Career mode not initialized'}), 500

    candidate_roots = []
    if _career_data_dir:
        candidate_roots.append(_career_data_dir)
    if _career_game_dir:
        candidate_roots.append(_career_game_dir / 'data' / 'swf')

    if not candidate_roots:
        return jsonify({'error': 'Career assets directory not configured'}), 404

    for root in candidate_roots:
        full_path = (root / asset_path).resolve()
        # Security: prevent path traversal
        try:
            full_path.relative_to(root.resolve())
        except ValueError:
            logger.warning("Blocked path traversal attempt: %s", asset_path)
            return jsonify({'error': 'Invalid asset path'}), 400

        existing = find_existing_image_path(full_path)
        if not existing:
            continue

        if existing.suffix.lower() == '.dds':
            png_bytes = convert_dds_to_png_bytes(existing)
            if not png_bytes:
                return jsonify({'error': 'Failed to convert DDS asset'}), 500
            return send_file(
                BytesIO(png_bytes),
                mimetype='image/png',
                download_name=existing.with_suffix('.png').name,
            )

        return send_file(existing, mimetype='image/png')

    logger.warning("Career asset not found: %s", asset_path)
    return jsonify({'error': 'Asset not found'}), 404


# ============================================================================
# Medal Showcase Endpoint
# ============================================================================

@api_bp.route('/api/campaign/<campaign_name>/showcase')
def get_campaign_showcase(campaign_name: str):
    """
    Build and return medal showcase data for the given campaign.

    Returns:
        JSON:
        {
            "country_key": "germany",
            "canvas_url":  "/api/tracker_assets/CampaignRanksAwards/Germany/Germany_canvas.png",
            "overlay": { "url": "...", "x": 32, "y": 0, "w": 2018, "h": 961 },
            "medals": [
                { "image_url": "...", "x": 141, "y": 134, "w": 363, "h": 503,
                  "name": "iron_cross_2nd_big1" },
                ...
            ]
        }
    """
    _last_ping[0] = __import__('time').time()

    if not _aggregator or not _data_loader:
        return jsonify({'error': 'API not initialized'}), 500

    campaign_name = campaign_name.lower()

    data_dir = _data_loader.data_dir

    # --- Locate JSON coordinate file ---
    # Primary: alongside the EXE / in data_dir (installed build).
    # Fallback: one level up (dev: Flask started from campaign_service_record/ subdir).
    excel_path = data_dir / 'IL-2_Tracker_award_coordinates.json'
    if not excel_path.exists():
        excel_path = data_dir.parent / 'IL-2_Tracker_award_coordinates.json'

    if not excel_path.exists():
        return jsonify({'error': 'Coordinate file not found', 'path': str(excel_path)}), 404

    # --- CampaignRanksAwards lives in the IL-2 game's swf directory ---
    # The installer copies CampaignRanksAwards/* there; we serve via /api/game_assets/.
    mission_dates = _data_loader.get_campaign_mission_dates()
    game_directory = get_game_directory(mission_dates)
    if game_directory:
        assets_dir = Path(game_directory) / 'data' / 'swf' / 'CampaignRanksAwards'
    else:
        assets_dir = data_dir / 'CampaignRanksAwards'  # fallback (no game dir configured)

    # --- Load / cache JSON coordinates ---
    try:
        coordinates = load_coordinates(excel_path)
    except Exception as exc:
        logger.error("Failed to parse medal coordinates: %s", exc, exc_info=True)
        return jsonify({'error': 'Failed to parse coordinate file', 'detail': str(exc)}), 500

    # --- Get campaign events ---
    events_data = _data_loader.get_campaign_events()
    campaign_events = events_data.get(campaign_name, {})
    if not campaign_events:
        return jsonify({'error': 'Campaign not found or no events'}), 404

    events = campaign_events.get('events', [])
    raw_country = campaign_events.get('country', '')

    # --- Resolve country key ---
    showcase_base = resolve_showcase_country(raw_country)
    if not showcase_base:
        return jsonify({'error': f'Unsupported country for showcase: {raw_country}'}), 404

    # For USSR, decide early vs late from the last mission date
    if showcase_base == 'ussr':
        # Find latest mission date among events
        dates = [ev.get('date') for ev in events if ev.get('date')]
        last_date = max(dates) if dates else None
        country_key = resolve_ussr_variant(last_date)
    else:
        country_key = showcase_base

    # --- Build set of earned showcase names ---
    earned = earned_showcase_names_from_events(events)

    # --- Build showcase payload ---
    try:
        payload = build_showcase_data(
            country_key=country_key,
            earned_showcase_names=earned,
            coordinates=coordinates,
            assets_dir=assets_dir,
            tracker_asset_url_prefix='/api/game_assets',
        )
    except Exception as exc:
        logger.error("Failed to build showcase data: %s", exc, exc_info=True)
        return jsonify({'error': 'Failed to build showcase data', 'detail': str(exc)}), 500

    if not payload:
        return jsonify({'error': 'No showcase data available for this country'}), 404

    return jsonify(payload)


# ============================================================================
# Tracker Assets Endpoint
# ============================================================================

@api_bp.route('/api/tracker_assets/<path:asset_path>')
def get_tracker_asset(asset_path: str):
    """
    Serve tracker-bundled assets (CampaignRanksAwards canvas, overlay,
    and *_big1.png medal images).

    These are served from <data_dir>/CampaignRanksAwards/, which is the
    tracker's own asset folder (distinct from the IL-2 game installation).
    """
    if not _data_loader:
        return jsonify({'error': 'API not initialized'}), 500

    data_dir = _data_loader.data_dir
    assets_root = data_dir / 'CampaignRanksAwards'

    requested = (assets_root / asset_path).resolve()

    # Security: prevent path traversal
    try:
        requested.relative_to(assets_root.resolve())
    except ValueError:
        logger.warning("Blocked path traversal attempt: %s", asset_path)
        return jsonify({'error': 'Invalid asset path'}), 400

    if not requested.exists():
        logger.warning("Tracker asset not found: %s", requested)
        return jsonify({'error': 'Asset not found'}), 404

    return send_from_directory(str(assets_root), asset_path)


# ============================================================================
# Mode Endpoint
# ============================================================================

@api_bp.route('/api/mode')
def get_mode():
    """
    Return which data providers are currently active and the configured app mode.

    Used by the frontend to decide which sections to render and which title to show.

    Returns:
        {
            "modes":    ["campaign"] | ["career"] | ["campaign", "career"],
            "app_mode": "campaign" | "career"
        }
    """
    from campaign_service_record.config import get_config
    app_mode = get_config().app_mode

    modes = []
    if _aggregator is not None:
        modes.append("campaign")
    if _career_provider is not None and _career_provider.is_available():
        modes.append("career")
    return jsonify({"modes": modes, "app_mode": app_mode})


# ============================================================================
# Career List Endpoint
# ============================================================================

@api_bp.route('/api/careers')
def get_careers():
    """
    Get list of all virtual pilot careers.

    Returns the same shape as /api/campaigns plus a 'theatre_chain' field
    per entry and 'source': 'career'.

    Returns:
        JSON array of career summary objects.
    """
    _last_ping[0] = time.time()

    if not _career_provider:
        return jsonify({'error': 'Career mode not available'}), 503

    try:
        careers = _career_provider.get_entry_list()
        logger.info("Served career list: %d careers", len(careers))
        return jsonify(careers)
    except Exception as exc:
        logger.error("Error getting career list: %s", exc, exc_info=True)
        return jsonify({'error': 'Failed to load careers', 'detail': str(exc)}), 500


# ============================================================================
# Background Job Endpoints
# ============================================================================

def _career_parse_worker(job, career_id: int) -> None:
    """Background thread: run the full debrief parse for career_id and update job state."""
    try:
        job.status = 'running'
        job.message = 'Scanning missions…'
        job.updated_at = time.time()

        def cb(cur: int, tot: int, msg: str) -> None:
            job.progress_current = cur
            job.progress_total = tot
            job.message = msg
            job.updated_at = time.time()

        _career_provider._aggregator.run_debrief_parse(career_id, cb)
        job.status = 'done'
        job.message = 'Complete'
        job.updated_at = time.time()
    except Exception as exc:
        job.status = 'error'
        job.error = traceback.format_exc()
        job.updated_at = time.time()
        logger.error('Career parse job %s failed: %s', job.id, exc, exc_info=True)


@api_bp.route('/api/jobs/start_career_parse', methods=['POST'])
def start_career_parse():
    """
    Start a background debrief parse job for a career.

    Query param:  ?career_id=<int>
    Returns:      { "job_id": "abc12345" }

    If a job for the same career is already running, returns the existing job_id.
    """
    _last_ping[0] = time.time()

    if not _career_provider:
        return jsonify({'error': 'Career mode not available'}), 503

    try:
        career_id = int(request.args.get('career_id', ''))
    except (TypeError, ValueError):
        return jsonify({'error': 'career_id must be an integer'}), 400

    # Deduplicate: return existing job if one is already running for this career
    existing = job_store.find_running(CAREER_DEBRIEF_PARSE, str(career_id))
    if existing is not None:
        return jsonify({'job_id': existing.id})

    job = job_store.create(CAREER_DEBRIEF_PARSE, extra_key=str(career_id))
    t = threading.Thread(
        target=_career_parse_worker,
        args=(job, career_id),
        daemon=True,
        name=f'career-parse-{career_id}',
    )
    t.start()
    return jsonify({'job_id': job.id})


@api_bp.route('/api/stories/<source>/<entry_id>')
def get_stories(source: str, entry_id: str):
    """Return story status and cached chapters for a service-record entry."""
    _last_ping[0] = time.time()
    return jsonify(_build_story_status_payload(str(source or "").lower(), entry_id))


@api_bp.route('/api/stories/<source>/<entry_id>/chapter', methods=['DELETE'])
def delete_story_chapter(source: str, entry_id: str):
    """Delete a single story chapter by mission_id and clean up its memory entries."""
    _last_ping[0] = time.time()
    source = str(source or "").strip().lower()

    if source not in {'career', 'campaign'}:
        return jsonify({'error': 'AI stories are not supported for this data source.'}), 400

    payload = request.get_json(silent=True) if request.is_json else {}
    if not isinstance(payload, dict):
        return jsonify({'error': 'Invalid payload.'}), 400

    mission_id = _normalize_story_text(payload.get('mission_id'))
    if not mission_id:
        return jsonify({'error': 'mission_id is required.'}), 400

    storage_entry_id = entry_id
    if source == 'career':
        try:
            int(entry_id)
        except (TypeError, ValueError):
            return jsonify({'error': 'Invalid career id.'}), 400

    deleted_date = delete_story_chapter_for(source, storage_entry_id, mission_id)
    if deleted_date is None:
        return jsonify({'error': f'Chapter for mission {mission_id} not found.'}), 404

    strip_memory_entries_for_date(source, storage_entry_id, deleted_date)
    return jsonify(_build_story_status_payload(source, entry_id))


@api_bp.route('/api/stories/<source>/<entry_id>/context_preview')
def get_story_context_preview(source: str, entry_id: str):
    """Return ordered story-generation contexts without calling the LLM."""
    _last_ping[0] = time.time()
    source = str(source or "").strip().lower()

    if source not in {'career', 'campaign'}:
        return jsonify({'error': 'AI stories are not supported for this data source.'}), 400

    try:
        if source == "career":
            try:
                root_career_id = int(entry_id)
            except (TypeError, ValueError):
                return jsonify({'error': 'Invalid career id.'}), 400
            contexts = _build_career_story_contexts(root_career_id)
        else:
            settings = _load_story_settings()
            contexts = _build_campaign_story_contexts(entry_id, settings["story_language"])

        preview_rows: list[dict] = []
        for index, context in enumerate(contexts, start=1):
            mission = context.get("mission", {}) if isinstance(context, dict) else {}
            pilot = context.get("pilot", {}) if isinstance(context, dict) else {}
            chapter_scope = context.get("chapter_scope", {}) if isinstance(context, dict) else {}
            scope = (
                _normalize_story_text(chapter_scope.get("scope")).lower()
                if isinstance(chapter_scope, dict)
                else ""
            ) or "mission"
            preview_rows.append({
                "index": index,
                "mission_id": _normalize_story_text(context.get("mission_id")),
                "date": _normalize_story_text(context.get("date")),
                "scope": scope,
                "missions_in_chapter": int(chapter_scope.get("missions_in_chapter", 1) or 1)
                if isinstance(chapter_scope, dict)
                else 1,
                "mission_ids": list(chapter_scope.get("mission_ids", []))
                if isinstance(chapter_scope, dict) and isinstance(chapter_scope.get("mission_ids"), list)
                else [],
                "aircraft": _normalize_story_text(pilot.get("aircraft")),
                "result": _normalize_story_text(mission.get("result")),
            })

        return jsonify({
            "source": source,
            "entry_id": entry_id,
            "count": len(preview_rows),
            "contexts": preview_rows,
        })
    except Exception as exc:
        logger.error("Story context preview failed for %s/%s: %s", source, entry_id, exc, exc_info=True)
        return jsonify({'error': f'Story context preview failed: {_normalize_story_text(exc)}'}), 500


@api_bp.route('/api/stories/<source>/<entry_id>/generate', methods=['POST'])
def generate_stories(source: str, entry_id: str):
    """Generate and cache missing story chapters for a service-record entry."""
    _last_ping[0] = time.time()
    source = str(source or "").strip().lower()

    if source not in {'career', 'campaign'}:
        return jsonify({'error': 'AI stories are not supported for this data source.'}), 400

    settings = _load_story_settings()
    if not settings["enabled"]:
        return jsonify({'error': 'AI stories are disabled in Settings Manager.'}), 400
    if not settings["configured"]:
        return jsonify({'error': 'No OpenAI API key is configured.'}), 400

    try:
        if source == "career":
            try:
                root_career_id = int(entry_id)
            except (TypeError, ValueError):
                return jsonify({'error': 'Invalid career id.'}), 400
            storage_entry_id: str | int = root_career_id
            contexts = _build_career_story_contexts(
                root_career_id,
                llm_config={
                    "api_key": settings["api_key"],
                    "provider": settings["provider"],
                    "base_url": settings["base_url"],
                    "model": settings["model"],
                },
            )
            if not contexts:
                return jsonify({'error': 'No career mission context could be built yet. Run/update debrief parsing first and retry.'}), 400
        else:
            storage_entry_id = entry_id
            contexts = _build_campaign_story_contexts(entry_id, settings["story_language"])

        if not contexts:
            return jsonify({'error': 'No mission data is available for story generation yet.'}), 400

        payload = request.get_json(silent=True) if request.is_json else {}
        if not isinstance(payload, dict):
            payload = {}
        try:
            max_chapters = int(payload.get("max_chapters", 1) or 1)
        except (TypeError, ValueError):
            max_chapters = 1
        max_chapters = max(1, min(max_chapters, 10))

        existing_chapters = load_story_chapters_for(source, storage_entry_id)
        existing_story_keys: set[str] = set()
        existing_story_canonical_keys: set[str] = set()
        for chapter in existing_chapters:
            if not _is_valid_story_text(chapter.get("story_text")):
                continue
            mission_value = chapter.get("mission_id")
            if mission_value is not None:
                mission_key = str(mission_value)
                existing_story_keys.add(mission_key)
                canonical_key = _canonical_mission_id(mission_key)
                if canonical_key:
                    existing_story_canonical_keys.add(canonical_key)
                if re.fullmatch(r"\d{4}-\d{2}-\d{2}", mission_key):
                    existing_story_keys.add(f"date:{mission_key}")
                elif mission_key.startswith("day:"):
                    day_key = _normalize_story_text(mission_key.split(":", 1)[1])
                    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", day_key):
                        existing_story_keys.add(f"date:{day_key}")
        missing_contexts: list[dict] = []
        for context in contexts:
            mission_key = str(context.get("mission_id"))
            mission_canonical = _canonical_mission_id(mission_key)
            if mission_key in existing_story_keys or (mission_canonical and mission_canonical in existing_story_canonical_keys):
                continue

            # Only day-scoped chapters (career aggregation) should dedupe by date.
            chapter_scope = context.get("chapter_scope")
            is_day_scope = (
                isinstance(chapter_scope, dict)
                and _normalize_story_text(chapter_scope.get("scope")).lower() == "day"
            )
            if is_day_scope:
                date_key = _normalize_story_text(context.get("date"))
                if date_key and f"date:{date_key}" in existing_story_keys:
                    continue

            missing_contexts.append(context)
        if not missing_contexts:
            status_payload = _build_story_status_payload(source, str(storage_entry_id))
            status_payload["generated_count"] = 0
            status_payload["remaining_count"] = 0
            status_payload["message"] = "Stories are already up to date."
            return jsonify(status_payload)

        memory = load_or_create_story_state_for(source, storage_entry_id)
        generated_count = 0
        generation_errors: list[str] = []
        for context in missing_contexts:
            if generated_count >= max_chapters:
                break
            context["narrative_memory"] = memory
            try:
                with ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(
                        generate_and_store_chapter_for,
                        source,
                        storage_entry_id,
                        context,
                        model=settings["model"],
                        api_key=settings["api_key"],
                        provider=settings["provider"],
                        base_url=settings["base_url"],
                        output_language=settings["story_language"],
                    )
                    result = future.result(timeout=120)
                memory = result.get("memory") or memory
                save_story_state_for(source, storage_entry_id, memory)
                generated_count += 1
            except FuturesTimeoutError:
                mission_ref = _normalize_story_text(context.get("mission_id")) or _normalize_story_text(context.get("date")) or "unknown"
                generation_errors.append(f"{mission_ref}: story generation timed out")
                logger.warning(
                    "Story generation timed out for %s/%s mission_ref=%s",
                    source,
                    storage_entry_id,
                    mission_ref,
                )
                # Preserve strict chronology: never skip a failed mission and jump ahead.
                break
            except Exception as chapter_exc:
                mission_ref = _normalize_story_text(context.get("mission_id")) or _normalize_story_text(context.get("date")) or "unknown"
                generation_errors.append(f"{mission_ref}: {chapter_exc}")
                logger.warning(
                    "Story generation failed for %s/%s mission_ref=%s: %s",
                    source,
                    storage_entry_id,
                    mission_ref,
                    chapter_exc,
                    exc_info=True,
                )
                # Preserve strict chronology: never skip a failed mission and jump ahead.
                break

        if generated_count == 0 and generation_errors:
            raise RuntimeError(generation_errors[0])

        status_payload = _build_story_status_payload(source, str(storage_entry_id))
        status_payload["generated_count"] = generated_count
        status_payload["remaining_count"] = max(0, len(missing_contexts) - generated_count)
        return jsonify(status_payload)
    except Exception as exc:
        logger.error("Story generation failed for %s/%s: %s", source, entry_id, exc, exc_info=True)
        error_code, message = _classify_story_error(exc)
        return jsonify({'error': message, 'error_code': error_code}), 502


_JOB_CLEANUP_INTERVAL = 20   # clean up done jobs every 20th poll call


@api_bp.route('/api/jobs/status/<job_id>')
def get_job_status(job_id: str):
    """
    Poll the status of a background job.

    Returns:
        { "id": ..., "type": ..., "status": ..., "message": ...,
          "progress_current": ..., "progress_total": ..., "error": ... }
    or 404 if the job is not found.
    """
    _last_ping[0] = time.time()

    # Periodically remove stale finished jobs
    if job_store.increment_poll() % _JOB_CLEANUP_INTERVAL == 0:
        job_store.cleanup_done()

    job = job_store.get(job_id)
    if job is None:
        return jsonify({'error': 'Job not found', 'job_id': job_id}), 404
    return jsonify(job.to_dict())


# ============================================================================
# Career Detail Endpoint
# ============================================================================

@api_bp.route('/api/career/<int:root_career_id>')
def get_career_detail(root_career_id: int):
    """
    Get full career detail for a virtual pilot.

    Response shape is identical to /api/campaign/<name> with additional
    'theatre_chain', 'birth_date', and 'source' fields.

    Args:
        root_career_id: The id of the career chain root (extends = -1).
    """
    _last_ping[0] = time.time()

    if not _career_provider:
        return jsonify({'error': 'Career mode not available'}), 503

    try:
        aggregator = _career_provider._aggregator
        # Skip the slow debrief parse on first load when no cache exists.
        # The frontend detects debriefings_pending=true and triggers a background job.
        cache_exists = aggregator.has_debrief_cache(root_career_id)
        detail = aggregator.get_career_detail(
            root_career_id, skip_debriefs=not cache_exists
        )
        if detail is None:
            return jsonify({'error': 'Career not found', 'id': root_career_id}), 404
        logger.info(
            "Served career detail: root_id=%d cache_exists=%s debriefings_pending=%s",
            root_career_id, cache_exists, detail.get('debriefings_pending'),
        )
        return jsonify(detail)
    except Exception as exc:
        logger.error(
            "Error getting career detail for id=%d: %s", root_career_id, exc, exc_info=True
        )
        return jsonify({'error': 'Failed to load career details', 'detail': str(exc)}), 500


# ============================================================================
# Career PDF Report Endpoint
# ============================================================================

@api_bp.route('/api/career/<int:root_career_id>/pdf', methods=['POST'])
def generate_career_pdf_report(root_career_id: int):
    """
    Generate a PDF career service record report on demand.

    Assembles career detail, per-day story contexts, and any existing story
    chapters into a formatted PDF, then saves it under:
        <data_dir>/career/<career_id>/pdf_reports/career_<id>_YYYYMMDD_HHmmss.pdf

    Returns:
        JSON: { "filename": str, "path": str (relative), "abs_path": str }
    """
    _last_ping[0] = time.time()

    if not _career_provider:
        return jsonify({'error': 'Career mode not available'}), 503

    try:
        from career_pdf_report import generate_career_pdf
    except ImportError:
        return jsonify({
            'error': 'reportlab is not installed. '
                     'Run: pip install reportlab'
        }), 500

    try:
        aggregator = _career_provider._aggregator

        # Career detail (always with debriefs so the summary is complete)
        detail = aggregator.get_career_detail(root_career_id, skip_debriefs=False)
        if detail is None:
            return jsonify({'error': 'Career not found', 'id': root_career_id}), 404

        # Per-day story contexts (combat stats, events, etc.)
        day_contexts = _build_career_story_contexts(root_career_id)

        # Existing story chapters
        chapters = load_story_chapters_for("career", str(root_career_id))

        # Output directory: <cwd>/career/<id>/pdf_reports/
        base_data_dir = Path.cwd()
        out_dir = base_data_dir / "career" / str(root_career_id) / "pdf_reports"

        # --- Medal showcase data (best-effort; PDF is generated even if this fails) ---
        _showcase_data: Optional[dict] = None
        try:
            from campaign_service_record.core.medal_showcase import (
                CAREER_CANVAS_FILENAME,
                CAREER_OVERLAY_FILENAME,
                build_showcase_data,
                has_german_ext_medals,
                load_career_coordinates,
                resolve_showcase_country,
                resolve_ussr_variant,
            )
            from pathlib import Path as _Path

            _career_json: Optional[_Path] = None
            if _career_data_dir:
                for _cand in (
                    _career_data_dir / 'IL-2_Tracker_career_award_coordinates.json',
                    _career_data_dir.parent / 'IL-2_Tracker_career_award_coordinates.json',
                ):
                    if _cand.exists():
                        _career_json = _cand
                        break

            if _career_json:
                _assets_dir = (
                    _career_game_dir / 'data' / 'swf' / 'CampaignRanksAwards'
                    if _career_game_dir else
                    _career_data_dir / 'CampaignRanksAwards'
                )
                _country_raw  = detail.get('country', '')
                _showcase_base = resolve_showcase_country(_country_raw)
                if _showcase_base:
                    _events = detail.get('events', [])
                    _showcase_events = detail.get('showcase_awards', _events)

                    if _showcase_base == 'ussr':
                        _dates = [ev.get('date') for ev in _events if ev.get('date')]
                        _country_key = resolve_ussr_variant(max(_dates) if _dates else None)
                    elif _showcase_base == 'germany' and _career_game_dir and has_german_ext_medals(_career_game_dir):
                        _country_key = 'germany_ext'
                    else:
                        _country_key = _showcase_base

                    _earned: set = set()
                    for _ev in _showcase_events:
                        if _ev.get('type') != 'award':
                            continue
                        _modal = _ev.get('modal_image_url') or ''
                        if _modal:
                            from campaign_service_record.core.medal_showcase import award_image_to_showcase_name
                            _sn = award_image_to_showcase_name(_Path(_modal).name)
                            if _sn:
                                _earned.add(_sn)

                    _coords = load_career_coordinates(_career_json)
                    _showcase_data = build_showcase_data(
                        country_key=_country_key,
                        earned_showcase_names=_earned,
                        coordinates=_coords,
                        assets_dir=_assets_dir,
                        tracker_asset_url_prefix='/api/career_assets',
                        canvas_filenames=CAREER_CANVAS_FILENAME,
                        overlay_filenames=CAREER_OVERLAY_FILENAME,
                        asset_context='career_detail_showcase',
                    )
        except Exception as _sc_exc:
            logger.warning(
                "PDF generation: could not build showcase data (skipped): %s", _sc_exc
            )

        # --- Pilot photo (best-effort) ---
        _pilot_photo_bytes: Optional[bytes] = None
        try:
            _photo_dir = current_app.config.get('PILOT_PHOTO_DIR')
            if _photo_dir:
                _photo_desc = f"campaign:{root_career_id}"
                _photo_path = pilot_photo_path(Path(_photo_dir), _photo_desc)
                if _photo_path.exists():
                    _pilot_photo_bytes = _photo_path.read_bytes()
        except Exception as _ph_exc:
            logger.warning("PDF generation: could not read pilot photo (skipped): %s", _ph_exc)

        out_path = generate_career_pdf(
            career_id=root_career_id,
            career_detail=detail,
            day_contexts=day_contexts,
            story_chapters=chapters,
            output_dir=out_dir,
            data_dir=_career_data_dir,
            game_dir=_career_game_dir,
            showcase_data=_showcase_data,
            pilot_photo_bytes=_pilot_photo_bytes,
        )

        try:
            rel = out_path.relative_to(base_data_dir)
            rel_str = str(rel).replace("\\", "/")
        except ValueError:
            rel_str = out_path.name

        return jsonify({
            'filename': out_path.name,
            'path':     rel_str,
            'abs_path': str(out_path),
        })

    except Exception as exc:
        logger.error(
            "Error generating career PDF for id=%d: %s", root_career_id, exc, exc_info=True
        )
        return jsonify({'error': 'PDF generation failed', 'detail': str(exc)}), 500


@api_bp.route('/api/career/<int:root_career_id>/pdf/<path:filename>', methods=['GET'])
def download_career_pdf(root_career_id: int, filename: str):
    """Serve a previously generated career PDF file for download."""
    _last_ping[0] = time.time()
    try:
        base_data_dir = Path.cwd()
        pdf_dir = (base_data_dir / "career" / str(root_career_id) / "pdf_reports").resolve()
        pdf_dir.mkdir(parents=True, exist_ok=True)
        # Security: strip directory components; only the bare filename is accepted.
        # Then verify the resolved path stays inside pdf_dir (path-traversal guard).
        safe_name = Path(filename).name
        pdf_path = pdf_dir / safe_name
        try:
            pdf_path.resolve().relative_to(pdf_dir)
        except ValueError:
            return jsonify({'error': 'Invalid filename'}), 400
        if not pdf_path.exists():
            return jsonify({'error': 'PDF not found'}), 404
        return send_file(
            pdf_path,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=safe_name,
        )
    except Exception as exc:
        logger.error("Error serving career PDF: %s", exc, exc_info=True)
        return jsonify({'error': 'Failed to serve PDF'}), 500


# ============================================================================
# Career Showcase Endpoint
# ============================================================================

@api_bp.route('/api/career/<int:root_career_id>/showcase')
def get_career_showcase(root_career_id: int):
    """
    Medal showcase for a career pilot.

    Reads IL-2_Tracker_career_award_coordinates.json for placement data,
    resolves earned awards from career event modal_image_url fields, and
    delegates to build_showcase_data() with career-specific canvas/overlay maps.
    """
    _last_ping[0] = time.time()

    if not _career_provider:
        return jsonify({'error': 'Career mode not available'}), 503

    # --- Locate career JSON coordinate file ---
    career_json: Optional[Path] = None
    if _career_data_dir:
        for candidate in (
            _career_data_dir / 'IL-2_Tracker_career_award_coordinates.json',
            _career_data_dir.parent / 'IL-2_Tracker_career_award_coordinates.json',
        ):
            if candidate.exists():
                career_json = candidate
                break

    if career_json is None:
        candidates_tried = []
        if _career_data_dir:
            candidates_tried = [
                str(_career_data_dir / 'IL-2_Tracker_career_award_coordinates.json'),
                str(_career_data_dir.parent / 'IL-2_Tracker_career_award_coordinates.json'),
            ]
        logger.error(
            "Career coordinate JSON not found. data_dir=%s, tried=%s",
            _career_data_dir, candidates_tried
        )
        return jsonify({
            'error': 'Career coordinate file not found',
            'data_dir': str(_career_data_dir),
            'searched': candidates_tried,
        }), 404

    # --- Assets dir (for _resolve_asset_file file-existence checks) ---
    # Prefer game_dir (where IL-2 stores CampaignRanksAwards PNGs); fall back to data_dir.
    if _career_game_dir:
        assets_dir = _career_game_dir / 'data' / 'swf' / 'CampaignRanksAwards'
    elif _career_data_dir:
        assets_dir = _career_data_dir / 'CampaignRanksAwards'
    else:
        return jsonify({'error': 'Career data directory not configured'}), 500

    # --- Career detail (events + country) ---
    detail = _career_provider.get_entry_detail(str(root_career_id))
    if not detail:
        logger.error("Career not found: root_career_id=%s", root_career_id)
        return jsonify({'error': 'Career not found', 'root_career_id': root_career_id}), 404

    country = detail.get('country', '')
    showcase_base = resolve_showcase_country(country)
    if not showcase_base:
        return jsonify({'error': f'Unsupported country for showcase: {country}'}), 404

    events = detail.get('events', [])
    showcase_events = detail.get('showcase_awards', events)

    # --- USSR early/late / Germany extended ---
    if showcase_base == 'ussr':
        dates = [ev.get('date') for ev in events if ev.get('date')]
        country_key = resolve_ussr_variant(max(dates) if dates else None)
    elif showcase_base == 'germany' and _career_game_dir and has_german_ext_medals(_career_game_dir):
        country_key = 'germany_ext'
    else:
        country_key = showcase_base

    # --- Earned showcase names from modal_image_url (big asset) ---
    # modal_image_url points to the 'big' asset (e.g. iron_cross_2nd_big.dds);
    # award_image_to_showcase_name converts the filename to the big1 showcase key.
    earned: set[str] = set()
    for ev in showcase_events:
        if ev.get('type') != 'award':
            continue
        modal_url = ev.get('modal_image_url') or ''
        if modal_url:
            name = award_image_to_showcase_name(Path(modal_url).name)
            if name:
                earned.add(name)
                logger.debug(
                    "Career showcase earned award: code=%s modal=%s showcase=%s",
                    ev.get('award_code'), Path(modal_url).name, name
                )

    # --- Load career coordinates ---
    try:
        coordinates = load_career_coordinates(career_json)
    except Exception as exc:
        logger.error(
            "Failed to parse career medal coordinates: %s", exc, exc_info=True
        )
        return jsonify({'error': 'Failed to parse coordinate file', 'detail': str(exc)}), 500

    return jsonify(build_showcase_data(
        country_key=country_key,
        earned_showcase_names=earned,
        coordinates=coordinates,
        assets_dir=assets_dir,
        tracker_asset_url_prefix='/api/career_assets',
        canvas_filenames=CAREER_CANVAS_FILENAME,
        overlay_filenames=CAREER_OVERLAY_FILENAME,
        asset_context='career_detail_showcase',
    ))


# ============================================================================
# Error Handlers
# ============================================================================

@api_bp.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({
        'error': 'Not found',
        'path': request.path
    }), 404


@api_bp.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    logger.error(f"Internal error: {error}", exc_info=True)
    return jsonify({
        'error': 'Internal server error',
        'detail': str(error)
    }), 500
