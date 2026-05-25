"""
LLM-backed mission story generation helpers.

This module keeps the first implementation deliberately standalone:
- resolves squadron/date historical context from local JSON files
- builds a structured story input object from parsed mission data
- generates a mission chapter using the OpenAI API
- updates a compact rolling narrative memory for continuity
- saves per-career story chapters and memory to disk

It is not yet wired into the tracker UI; callers can integrate it gradually.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import threading
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple

import openai

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - handled by runtime caller
    OpenAI = None  # type: ignore[assignment]


BASE_DIR = Path(__file__).resolve().parent
HISTORICAL_CONTEXT_DIR = BASE_DIR / "historical_context"
SQUADRON_CONTEXT_FILE = HISTORICAL_CONTEXT_DIR / "squadrons.json"
SQUADRON_ALIASES_FILE = HISTORICAL_CONTEXT_DIR / "squadron_aliases.json"
_MISSION_TYPES_FILE = BASE_DIR / "campaign_service_record" / "career" / "mission_types.json"

_mission_types_cache: Optional[Dict[str, Any]] = None


def _load_mission_types() -> Dict[str, Any]:
    global _mission_types_cache
    if _mission_types_cache is not None:
        return _mission_types_cache
    try:
        data = json.loads(_MISSION_TYPES_FILE.read_text(encoding="utf-8"))
        _mission_types_cache = data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        _mission_types_cache = {}
    return _mission_types_cache


def resolve_mission_type_labels(
    mission_type_code: Any,
    m_template: Any,
) -> tuple[str, str]:
    """
    Return (type_label, objective_label) from mission.type and mission.mTemplate.

    type_label   — e.g. "Frontline Patrol", "Escort Bombers", "Bomb Bridge"
    objective_label — sub-type detail when it adds context, e.g. "Enemy Territory",
                      "V-1 Launch Site", "Supply Depot Cover".  Empty string when
                      the type label is already self-contained.

    Subtypes that duplicate the type label meaning are suppressed
    (e.g. "Airfield Transfer" for "Fighter Transfer").
    """
    data = _load_mission_types()
    mission_types: Dict[str, str] = data.get("mission_types", {}) if isinstance(data, dict) else {}
    template_subtypes: Dict[str, str] = data.get("template_subtypes", {}) if isinstance(data, dict) else {}

    type_label = _normalize_text(mission_types.get(str(mission_type_code) if mission_type_code is not None else ""))

    raw_template = _normalize_text(m_template)
    prefix = ""
    if "@" in raw_template:
        prefix = raw_template.split("@")[0]
    elif "_p00" in raw_template:
        prefix = raw_template.split("_p00")[0].rstrip("_")

    sub_label = _normalize_text(template_subtypes.get(prefix)) if prefix else ""

    # Suppress sub-labels that carry no new information vs the type label.
    _REDUNDANT_PAIRS = {
        ("Fighter Transfer", "Airfield Transfer"),
        ("Bomber Transfer", "Airfield Transfer"),
        ("Escort Bombers", "Bomber Escort"),
    }
    if (type_label, sub_label) in _REDUNDANT_PAIRS:
        sub_label = ""

    return type_label, sub_label


def _resolve_story_data_dir() -> Path:
    env_dir = str(os.environ.get("IL2_CSR_STORY_DATA_DIR") or "").strip()
    if env_dir:
        return Path(env_dir) / "careers"
    if getattr(sys, "frozen", False):
        base = Path(os.environ.get("LOCALAPPDATA") or str(Path.home()))
        return base / ".il2_campaign_service_record" / "story_data" / "careers"
    return BASE_DIR / "story_data" / "careers"


STORY_DATA_DIR = _resolve_story_data_dir()
LOGGER = logging.getLogger(__name__)

_SQUADRON_FILE_LOCK = threading.Lock()

DEFAULT_MODEL = "gpt-5-mini"
DEFAULT_API_TIMEOUT_SECONDS = 45.0

_LANGUAGE_LABELS = {
    "en": "English",
    "de": "German",
    "fr": "French",
    "es": "Spanish",
    "pl": "Polish",
    "ru": "Russian",
    "zh": "Chinese (Simplified)",
}


# Localized phrase fragments for the squadron-event fallback lines.
# These are only used when the AI did not cover squadron events in the story.
_SQUADRON_EVENT_PHRASES: Dict[str, Dict[str, str]] = {
    "en": {
        "received":         "{pilot} received {award}",
        "promoted_to":      "{pilot} promoted to {rank}",
        "transferred_to":   "{pilot} transferred to {to_squadron}",
        "transferred":      "{pilot} was transferred",
        "kia":              "{pilot} was KIA",
        "mia":              "{pilot} was MIA",
        "wounded":          "{pilot} was wounded",
    },
    "de": {
        "received":         "{pilot} erhielt {award}",
        "promoted_to":      "{pilot} befördert zu {rank}",
        "transferred_to":   "{pilot} versetzt zu {to_squadron}",
        "transferred":      "{pilot} wurde versetzt",
        "kia":              "{pilot} gefallen (KIA)",
        "mia":              "{pilot} vermisst (MIA)",
        "wounded":          "{pilot} verwundet",
    },
    "fr": {
        "received":         "{pilot} a reçu {award}",
        "promoted_to":      "{pilot} promu au rang de {rank}",
        "transferred_to":   "{pilot} muté à {to_squadron}",
        "transferred":      "{pilot} a été muté",
        "kia":              "{pilot} tombé au combat",
        "mia":              "{pilot} porté disparu",
        "wounded":          "{pilot} blessé",
    },
    "es": {
        "received":         "{pilot} recibió {award}",
        "promoted_to":      "{pilot} ascendido a {rank}",
        "transferred_to":   "{pilot} trasladado a {to_squadron}",
        "transferred":      "{pilot} fue trasladado",
        "kia":              "{pilot} caído en combate (KIA)",
        "mia":              "{pilot} desaparecido (MIA)",
        "wounded":          "{pilot} herido",
    },
    "pl": {
        "received":         "{pilot} otrzymał {award}",
        "promoted_to":      "{pilot} awansowany do stopnia {rank}",
        "transferred_to":   "{pilot} przeniesiony do {to_squadron}",
        "transferred":      "{pilot} został przeniesiony",
        "kia":              "{pilot} poległ (KIA)",
        "mia":              "{pilot} zaginął (MIA)",
        "wounded":          "{pilot} ranny",
    },
    "ru": {
        "received":         "{pilot} получил {award}",
        "promoted_to":      "{pilot} повышен до {rank}",
        "transferred_to":   "{pilot} переведён в {to_squadron}",
        "transferred":      "{pilot} был переведён",
        "kia":              "{pilot} погиб (КИА)",
        "mia":              "{pilot} пропал без вести (МИА)",
        "wounded":          "{pilot} ранен",
    },
    "zh": {
        "received":         "{pilot}获得{award}",
        "promoted_to":      "{pilot}晋升为{rank}",
        "transferred_to":   "{pilot}调往{to_squadron}",
        "transferred":      "{pilot}已调动",
        "kia":              "{pilot}阵亡（KIA）",
        "mia":              "{pilot}失踪（MIA）",
        "wounded":          "{pilot}受伤",
    },
}


def _squadron_phrase(lang: str, key: str, **kwargs: str) -> str:
    phrases = _SQUADRON_EVENT_PHRASES.get(lang) or _SQUADRON_EVENT_PHRASES["en"]
    template = phrases.get(key) or _SQUADRON_EVENT_PHRASES["en"][key]
    return template.format(**kwargs)


def _iter_squadron_event_items(squadron_context: Any, output_language: str = "en") -> list[str]:
    if not isinstance(squadron_context, dict):
        return []

    lang = _normalize_text(output_language).lower()[:2] or "en"
    lines: list[str] = []

    promotions = squadron_context.get("promotions", [])
    if isinstance(promotions, list):
        for item in promotions[:4]:
            if not isinstance(item, dict):
                continue
            pilot = _normalize_text(item.get("pilot"))
            rank = _normalize_text(item.get("rank"))
            if pilot and rank:
                lines.append(_squadron_phrase(lang, "promoted_to", pilot=pilot, rank=rank))

    awards = squadron_context.get("awards", [])
    if isinstance(awards, list):
        for item in awards[:4]:
            if not isinstance(item, dict):
                continue
            pilot = _normalize_text(item.get("pilot"))
            award = _normalize_text(item.get("award"))
            if pilot and award:
                lines.append(_squadron_phrase(lang, "received", pilot=pilot, award=award))

    transfers = squadron_context.get("transfers", [])
    if isinstance(transfers, list):
        for item in transfers[:4]:
            if not isinstance(item, dict):
                continue
            pilot = _normalize_text(item.get("pilot"))
            to_squadron = _normalize_text(item.get("to_squadron"))
            if pilot and to_squadron:
                lines.append(_squadron_phrase(lang, "transferred_to", pilot=pilot, to_squadron=to_squadron))
            elif pilot:
                lines.append(_squadron_phrase(lang, "transferred", pilot=pilot))

    def _pilot_name_from_entry(entry: Any) -> str:
        if isinstance(entry, dict):
            return _normalize_text(entry.get("pilot"))
        return _normalize_text(entry)

    kia = squadron_context.get("kia", [])
    if isinstance(kia, list):
        for entry in kia[:6]:
            pilot = _pilot_name_from_entry(entry)
            if pilot:
                lines.append(_squadron_phrase(lang, "kia", pilot=pilot))

    mia = squadron_context.get("mia", [])
    if isinstance(mia, list):
        for entry in mia[:6]:
            pilot = _pilot_name_from_entry(entry)
            if pilot:
                lines.append(_squadron_phrase(lang, "mia", pilot=pilot))

    wia = squadron_context.get("wia", [])
    if isinstance(wia, list):
        for entry in wia[:6]:
            pilot = _pilot_name_from_entry(entry)
            if pilot:
                lines.append(_squadron_phrase(lang, "wounded", pilot=pilot))

    return lines


def _story_mentions_squadron_events(story_text: str, squadron_context: Any) -> bool:
    """Return True only when at least one specific pilot from squadron_context is named in the text."""
    text = _normalize_text(story_text).lower()
    if not text:
        return False

    if not isinstance(squadron_context, dict):
        return False

    for key in ("promotions", "awards", "transfers"):
        entries = squadron_context.get(key, [])
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            pilot = _normalize_text(entry.get("pilot")).lower()
            if pilot and pilot in text:
                return True
    for key in ("kia", "mia", "wia"):
        entries = squadron_context.get(key, [])
        if not isinstance(entries, list):
            continue
        for entry in entries:
            p = (_normalize_text(entry.get("pilot")) if isinstance(entry, dict) else _normalize_text(entry)).lower()
            if p and p in text:
                return True
    return False


def _enforce_squadron_event_presence(story_input: Dict[str, Any], story_text: str, output_language: str) -> str:
    squadron_context = story_input.get("squadron_context") if isinstance(story_input, dict) else None
    event_lines = _iter_squadron_event_items(squadron_context, output_language)
    if not event_lines:
        return story_text
    if _story_mentions_squadron_events(story_text, squadron_context):
        return story_text

    lang = _normalize_text(output_language).lower()
    heading_map = {
        "de": "Staffelmeldung",
        "ru": "Сводка эскадрильи",
    }
    heading = heading_map.get(lang, "Squadron update")
    addition = f"{heading}: " + "; ".join(event_lines[:4]) + "."
    text = _normalize_text(story_text)
    if not text:
        return addition
    return f"{text}\n\n{addition}"


def _load_json_file(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _save_json_file(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _slugify_story_entry(value: str | int) -> str:
    text = _normalize_text(value)
    if not text:
        return "unknown"
    text = re.sub(r"[^a-zA-Z0-9._-]+", "-", text).strip("-")
    return text or "unknown"


def _format_duration_for_story(duration_raw: Any) -> str:
    """
    Convert mission duration to hours/minutes only for narrative output.

    Examples:
      00:34:41 -> 34m
      01:07:10 -> 1h 7m
      00:08    -> 8m
    """
    text = _normalize_text(duration_raw)
    if not text:
        return ""
    parts = text.split(":")
    try:
        if len(parts) >= 2:
            if len(parts) == 2:
                hours = 0
                minutes = int(parts[0])
            else:
                hours = int(parts[0])
                minutes = int(parts[1])
            if hours > 0:
                return f"{hours}h {minutes}m"
            return f"{minutes}m"
    except ValueError:
        return text
    return text


def _normalize_squadron_name(name: str) -> str:
    normalized = _normalize_text(name).lower()
    for old, new in (
        ("ё", "е"),
        ("\"", ""),
        ("'", ""),
        (".", ""),
        (",", ""),
    ):
        normalized = normalized.replace(old, new)
    normalized = " ".join(normalized.split())
    return normalized


def _story_source_dir(source: str) -> Path:
    normalized = _normalize_text(source).lower()
    if normalized == "campaign":
        return STORY_DATA_DIR.parent / "campaigns"
    return STORY_DATA_DIR


def _story_entry_dir(source: str, entry_id: str | int) -> Path:
    return _story_source_dir(source) / _slugify_story_entry(entry_id)


def _story_career_dir(career_id: str | int) -> Path:
    return _story_entry_dir("career", career_id)


def load_or_create_story_state_for(source: str, entry_id: str | int) -> Dict[str, Any]:
    path = _story_entry_dir(source, entry_id) / "memory.json"
    if path.exists():
        return _load_json_file(path, {})
    return {
        "source": _normalize_text(source),
        "entry_id": str(entry_id),
        "current_rank": "",
        "current_squadron": "",
        "arc_summary": "",
        "key_milestones": [],
        "recurring_themes": [],
        "recent_events": [],
    }


def save_story_state_for(source: str, entry_id: str | int, memory: Dict[str, Any]) -> None:
    _save_json_file(_story_entry_dir(source, entry_id) / "memory.json", memory)


def _coerce_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _chapter_sort_key_for_source(
    source: str,
    payload: Dict[str, Any],
    fallback_index: int,
) -> tuple:
    normalized_source = _normalize_text(source).lower()
    if normalized_source == "career":
        mission_order = _coerce_int(payload.get("career_mission_order"))
        if mission_order is not None and mission_order > 0:
            segment_index = _coerce_int(payload.get("career_segment_index"))
            if segment_index is None:
                segment_index = 0
            mission_id_text = _normalize_text(payload.get("mission_id"))
            mission_id_int = _coerce_int(mission_id_text)
            if mission_id_int is None:
                mission_id_int = 0
            return (0, mission_order, segment_index, mission_id_int, mission_id_text)

        chapter_idx = _coerce_int(payload.get("chapter_index"))
        if chapter_idx is None or chapter_idx <= 0:
            chapter_idx = fallback_index
        mission_id_text = _normalize_text(payload.get("mission_id"))
        return (1, chapter_idx, fallback_index, mission_id_text)

    # Campaigns keep chronological date ordering.
    date_key = _normalize_text(payload.get("date")) or ""
    mission_id_int = _coerce_int(payload.get("mission_id"))
    if mission_id_int is None:
        mission_id_int = 0
    return (date_key, mission_id_int, fallback_index)


def reindex_career_story_chapters_for(
    entry_id: str | int,
    mission_order_map: Dict[str, int],
    mission_segment_map: Optional[Dict[str, int]] = None,
) -> int:
    """
    Reindex existing career story chapters using canonical mission order.

    This is used to repair legacy date-sorted chapter files when theatre date
    ranges overlap.
    """
    chapters_dir = _story_entry_dir("career", entry_id) / "chapters"
    if not chapters_dir.exists():
        return 0

    normalized_order: Dict[str, int] = {}
    for mission_key, order in (mission_order_map or {}).items():
        key = _normalize_text(mission_key)
        try:
            order_int = int(order)
        except (TypeError, ValueError):
            continue
        if key and order_int > 0:
            normalized_order[key] = order_int
    if not normalized_order:
        return 0

    normalized_segments: Dict[str, int] = {}
    for mission_key, segment in (mission_segment_map or {}).items():
        key = _normalize_text(mission_key)
        try:
            seg_int = int(segment)
        except (TypeError, ValueError):
            continue
        if key:
            normalized_segments[key] = seg_int

    records: list[tuple[Path, Dict[str, Any], int]] = []
    for fallback_index, path in enumerate(sorted(chapters_dir.glob("*.json")), start=1):
        payload = _load_json_file(path, None)
        if not isinstance(payload, dict):
            continue
        mission_key = _normalize_text(payload.get("mission_id"))
        if mission_key in normalized_order:
            payload["career_mission_order"] = normalized_order[mission_key]
            payload["career_segment_index"] = normalized_segments.get(
                mission_key,
                _coerce_int(payload.get("career_segment_index")) or 0,
            )
        records.append((path, payload, fallback_index))
    if not records:
        return 0

    records.sort(key=lambda item: _chapter_sort_key_for_source("career", item[1], item[2]))

    for old_path, _, _ in records:
        if old_path.exists():
            old_path.unlink()

    for new_index, (_, payload, _) in enumerate(records, start=1):
        payload["chapter_index"] = new_index
        date_part = _normalize_text(payload.get("date")) or "unknown-date"
        new_path = chapters_dir / f"{new_index:04d}_{date_part}.json"
        _save_json_file(new_path, payload)

    return len(records)


def load_story_chapters_for(source: str, entry_id: str | int) -> list[Dict[str, Any]]:
    chapters_dir = _story_entry_dir(source, entry_id) / "chapters"
    if not chapters_dir.exists():
        return []
    chapters = []
    for path in sorted(chapters_dir.glob("*.json")):
        payload = _load_json_file(path, None)
        if isinstance(payload, dict):
            chapters.append(payload)
    return chapters


def purge_orphaned_chapters_for(source: str, entry_id: str | int) -> int:
    """Delete all chapters with an empty/missing mission_id and renumber the rest.

    Returns the number of chapters deleted.
    """
    chapters_dir = _story_entry_dir(source, entry_id) / "chapters"
    if not chapters_dir.exists():
        return 0

    deleted_count = 0
    for path in sorted(chapters_dir.glob("*.json")):
        payload = _load_json_file(path, None)
        if isinstance(payload, dict) and not _normalize_text(payload.get("mission_id")):
            path.unlink()
            deleted_count += 1

    if deleted_count > 0:
        for new_index, path in enumerate(sorted(chapters_dir.glob("*.json")), start=1):
            payload = _load_json_file(path, None)
            if not isinstance(payload, dict):
                continue
            payload["chapter_index"] = new_index
            date_part = _normalize_text(payload.get("date")) or "unknown-date"
            new_name = f"{new_index:04d}_{date_part}.json"
            new_path = chapters_dir / new_name
            _save_json_file(new_path, payload)
            if new_path != path:
                path.unlink()

    return deleted_count


def delete_story_chapter_for(source: str, entry_id: str | int, mission_id: str) -> Optional[str]:
    """Delete a chapter by mission_id and renumber the remaining ones.

    Returns the deleted chapter's date string (for memory cleanup), or None if not found.
    """
    chapters_dir = _story_entry_dir(source, entry_id) / "chapters"
    if not chapters_dir.exists():
        return None

    target_mission_id = _normalize_text(mission_id)
    target_path: Optional[Path] = None
    deleted_date: str = ""

    for path in sorted(chapters_dir.glob("*.json")):
        payload = _load_json_file(path, None)
        if isinstance(payload, dict) and _normalize_text(payload.get("mission_id")) == target_mission_id:
            target_path = path
            deleted_date = _normalize_text(payload.get("date"))
            break

    if target_path is None:
        return None

    target_path.unlink()

    # Renumber remaining chapters sequentially so gaps don't appear in the UI.
    for new_index, path in enumerate(sorted(chapters_dir.glob("*.json")), start=1):
        payload = _load_json_file(path, None)
        if not isinstance(payload, dict):
            continue
        payload["chapter_index"] = new_index
        date_part = _normalize_text(payload.get("date")) or "unknown-date"
        new_name = f"{new_index:04d}_{date_part}.json"
        new_path = chapters_dir / new_name
        _save_json_file(new_path, payload)
        if new_path != path:
            path.unlink()

    return deleted_date


def strip_memory_entries_for_date(source: str, entry_id: str | int, mission_date: str) -> None:
    """Remove recent_events and key_milestones entries tied to *mission_date* and recompute arc_summary."""
    date_prefix = _normalize_text(mission_date)
    if not date_prefix:
        return

    memory = load_or_create_story_state_for(source, entry_id)

    recent_events = memory.get("recent_events", [])
    if isinstance(recent_events, list):
        memory["recent_events"] = [
            e for e in recent_events
            if not _normalize_text(e).startswith(date_prefix + ":")
        ]

    key_milestones = memory.get("key_milestones", [])
    if isinstance(key_milestones, list):
        memory["key_milestones"] = [
            m for m in key_milestones
            if not _normalize_text(m).startswith(date_prefix + ":")
        ]

    arc_bits: list[str] = []
    if memory.get("current_rank"):
        arc_bits.append(f"Rank: {memory['current_rank']}")
    if memory.get("current_squadron"):
        arc_bits.append(f"Unit: {memory['current_squadron']}")
    remaining_recent = memory.get("recent_events", [])
    if remaining_recent:
        arc_bits.append(f"Latest mission: {remaining_recent[-1]}")
    memory["arc_summary"] = "; ".join(bit for bit in arc_bits if bit)[:280]

    save_story_state_for(source, entry_id, memory)


def save_story_chapter_for(
    source: str,
    entry_id: str | int,
    mission_context: Dict[str, Any],
    story_text: str,
    *,
    title: str = "",
    language_code: str = "en",
) -> Path:
    normalized_source = _normalize_text(source).lower()
    chapters_dir = _story_entry_dir(source, entry_id) / "chapters"
    chapters_dir.mkdir(parents=True, exist_ok=True)

    date_str = _normalize_text(mission_context.get("date")) or "unknown-date"
    mission_id_str = _normalize_text(mission_context.get("mission_id")) or ""

    new_payload: Dict[str, Any] = {
        "chapter_index": 0,  # assigned during renumber pass
        "mission_id": mission_id_str,
        "date": date_str,
        "title": title,
        "language": _normalize_text(language_code) or "en",
        "story_text": story_text,
        "aircraft": mission_context.get("pilot", {}).get("aircraft", ""),
        "result": mission_context.get("mission", {}).get("result", ""),
    }
    if normalized_source == "career":
        mission_order = _coerce_int(mission_context.get("career_mission_order"))
        if mission_order is not None and mission_order > 0:
            new_payload["career_mission_order"] = mission_order
        segment_index = _coerce_int(mission_context.get("career_segment_index"))
        if segment_index is not None:
            new_payload["career_segment_index"] = segment_index

    # Load all existing chapters and include the new one (no file yet, marked with None).
    all_chapters: list[tuple[Optional[Path], Dict[str, Any], int]] = []
    for fallback_index, p in enumerate(sorted(chapters_dir.glob("*.json")), start=1):
        data = _load_json_file(p, None)
        if isinstance(data, dict):
            all_chapters.append((p, data, fallback_index))
    all_chapters.append((None, new_payload, len(all_chapters) + 1))

    all_chapters.sort(key=lambda item: _chapter_sort_key_for_source(source, item[1], item[2]))

    # Delete all existing files first to avoid naming collisions during renumber.
    for old_path, _, _ in all_chapters:
        if old_path is not None and old_path.exists():
            old_path.unlink()

    # Write all chapters with sequential names; track the new chapter's final path.
    saved_path = chapters_dir / f"0001_{date_str}.json"
    for new_index, (old_path, data, _) in enumerate(all_chapters, start=1):
        data["chapter_index"] = new_index
        date_part = _normalize_text(data.get("date")) or "unknown-date"
        new_path = chapters_dir / f"{new_index:04d}_{date_part}.json"
        _save_json_file(new_path, data)
        if old_path is None and _normalize_text(data.get("mission_id")) == mission_id_str:
            saved_path = new_path

    return saved_path


def load_or_create_story_state(career_id: str | int) -> Dict[str, Any]:
    return load_or_create_story_state_for("career", career_id)


def save_story_state(career_id: str | int, memory: Dict[str, Any]) -> None:
    save_story_state_for("career", career_id, memory)


def load_story_chapters(career_id: str | int) -> list[Dict[str, Any]]:
    return load_story_chapters_for("career", career_id)


def save_story_chapter(
    career_id: str | int,
    mission_context: Dict[str, Any],
    story_text: str,
    title: str = "",
    language_code: str = "en",
) -> Path:
    return save_story_chapter_for(
        "career",
        career_id,
        mission_context,
        story_text,
        title=title,
        language_code=language_code,
    )


def resolve_squadron_key(squadron_name: str) -> str:
    aliases = _load_json_file(SQUADRON_ALIASES_FILE, {})
    normalized = _normalize_squadron_name(squadron_name)
    if normalized in aliases:
        return aliases[normalized]
    return normalized.replace(" ", "_")


def auto_enrich_squadron(
    squadron_name: str,
    squadron_key: str,
    mission_date: str,
    country: str = "",
    *,
    llm_config: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Call the LLM to generate a historical context entry for an unknown squadron
    and persist it to squadrons.json for future use.

    llm_config is a dict with keys: api_key, provider, base_url, model.
    When absent, falls back to the OPENAI_API_KEY environment variable and
    default model/provider values.

    Returns the newly generated squadron block dict, or None if generation fails
    (no API key, network error, bad JSON response, etc.).
    """
    cfg = llm_config or {}
    api_key = _normalize_text(cfg.get("api_key")) or os.environ.get("OPENAI_API_KEY") or ""
    provider = _normalize_text(cfg.get("provider")) or "openai"
    base_url = _normalize_text(cfg.get("base_url")) or None
    model = _normalize_text(cfg.get("model")) or DEFAULT_MODEL

    if not api_key:
        LOGGER.debug("auto_enrich_squadron: skipping — no API key available")
        return None

    if OpenAI is None:
        LOGGER.debug("auto_enrich_squadron: skipping — openai package not installed")
        return None

    country_hint = f" The squadron's country is '{country}'." if country else ""
    prompt = (
        f"You are a World War II aviation historian.\n\n"
        f"Provide historical context for the squadron '{squadron_name}' around {mission_date}.{country_hint}\n\n"
        "Return ONLY a valid JSON object with this exact schema (no extra keys, no commentary):\n"
        "{\n"
        '  "display_name": "<short human-readable name>",\n'
        '  "country": "<lowercase country, e.g. germany, ussr, uk, usa>",\n'
        '  "periods": [\n'
        "    {\n"
        '      "start": "<YYYY-MM-DD or empty string if unknown>",\n'
        '      "end": "<YYYY-MM-DD or empty string if unknown>",\n'
        '      "theatre": "<operational theatre, e.g. Eastern Front>",\n'
        '      "location": "<specific area or airfield region>",\n'
        '      "summary": "<2-3 sentence factual summary of what the unit was doing in this period>",\n'
        '      "facts": ["<specific verifiable fact>", "..."],\n'
        '      "tone_hints": ["<atmospheric descriptor>", "..."],\n'
        '      "forbidden_claims": [\n'
        '        "Do not name specific commanders unless you are certain.",\n'
        '        "Do not claim exact base names unless you are certain.",\n'
        '        "Do not invent kill tallies or specific pilot names."\n'
        "      ]\n"
        "    }\n"
        "  ]\n"
        "}\n\n"
        "If you have no reliable historical information about this squadron, return an entry with "
        "empty strings for theatre/location/summary and empty arrays for facts and tone_hints, "
        "but still populate display_name and country.\n"
        "Return JSON only — no prose, no markdown fences."
    )

    try:
        client = _get_client(api_key=api_key, base_url=base_url)
        response = _create_story_response(
            client,
            provider=provider,
            model=model,
            prompt=prompt,
            max_output_tokens=800,
        )
        raw_text = _extract_response_text(response)
        payload = _extract_json_object(raw_text)
    except Exception as exc:
        LOGGER.warning("auto_enrich_squadron: LLM call failed for '%s': %s", squadron_name, exc)
        return None

    if not isinstance(payload, dict):
        LOGGER.warning("auto_enrich_squadron: LLM returned non-dict for '%s'", squadron_name)
        return None

    if "display_name" not in payload or "periods" not in payload:
        LOGGER.warning(
            "auto_enrich_squadron: LLM response missing required keys for '%s': %s",
            squadron_name,
            list(payload.keys()),
        )
        return None

    # Persist to squadrons.json under the resolved key.
    with _SQUADRON_FILE_LOCK:
        data = _load_json_file(SQUADRON_CONTEXT_FILE, {})
        if squadron_key not in data:  # Don't overwrite a race-written entry.
            data[squadron_key] = payload
            try:
                _save_json_file(SQUADRON_CONTEXT_FILE, data)
                LOGGER.info(
                    "auto_enrich_squadron: saved new entry '%s' -> '%s'",
                    squadron_name,
                    squadron_key,
                )
            except Exception as exc:
                LOGGER.warning("auto_enrich_squadron: failed to write squadrons.json: %s", exc)

    return payload


def resolve_historical_context(
    squadron_name: str,
    mission_date: str,
    *,
    country: str = "",
    llm_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Resolve squadron/date historical context from local JSON files.

    When the squadron is completely unknown, attempts to auto-enrich by calling
    the LLM and persisting the result to squadrons.json for future use.

    Returns a normalized dict even when no match exists so the caller can
    safely pass it to prompt generation.
    """
    squadron_key = resolve_squadron_key(squadron_name)
    data = _load_json_file(SQUADRON_CONTEXT_FILE, {})
    squadron_block = data.get(squadron_key, {})

    if not squadron_block:
        enriched = auto_enrich_squadron(
            squadron_name, squadron_key, mission_date, country=country, llm_config=llm_config
        )
        if enriched:
            squadron_block = enriched

    periods = squadron_block.get("periods", [])

    match = None
    for period in periods:
        start = _normalize_text(period.get("start"))
        end = _normalize_text(period.get("end"))
        if start and mission_date < start:
            continue
        if end and mission_date > end:
            continue
        match = period
        break

    if match is None:
        return {
            "squadron_key": squadron_key,
            "display_name": squadron_block.get("display_name", squadron_name),
            "country": squadron_block.get("country", country),
            "theatre": "",
            "location": "",
            "summary": "",
            "facts": [],
            "tone_hints": [],
            "forbidden_claims": [],
        }

    return {
        "squadron_key": squadron_key,
        "display_name": squadron_block.get("display_name", squadron_name),
        "country": squadron_block.get("country", country),
        "theatre": _normalize_text(match.get("theatre")),
        "location": _normalize_text(match.get("location")),
        "summary": _normalize_text(match.get("summary")),
        "facts": list(match.get("facts", []) or []),
        "tone_hints": list(match.get("tone_hints", []) or []),
        "forbidden_claims": list(match.get("forbidden_claims", []) or []),
    }


def _derive_time_of_day(start_time: Optional[str]) -> str:
    """Map 'HH:MM' game clock time to a time-of-day label for atmospheric context."""
    if not start_time:
        return ""
    try:
        parts = start_time.split(":")
        minutes = int(parts[0]) * 60 + int(parts[1])
    except (ValueError, IndexError, AttributeError):
        return ""
    if 300 <= minutes < 510:    # 05:00–08:30
        return "dawn"
    if 510 <= minutes < 660:    # 08:30–11:00
        return "morning"
    if 660 <= minutes < 840:    # 11:00–14:00
        return "midday"
    if 840 <= minutes < 1020:   # 14:00–17:00
        return "afternoon"
    if 1020 <= minutes < 1170:  # 17:00–19:30
        return "dusk"
    return "night"


def _derive_season(date_str: Optional[str]) -> str:
    """Map 'YYYY-MM-DD' to a meteorological season label."""
    if not date_str:
        return ""
    try:
        month = int(date_str.split("-")[1])
    except (ValueError, IndexError, AttributeError):
        return ""
    if month in (3, 4, 5):
        return "spring"
    if month in (6, 7, 8):
        return "summer"
    if month in (9, 10, 11):
        return "autumn"
    return "winter"


def _extract_notable_events(mission_json: Dict[str, Any]) -> list[str]:
    notable: list[str] = []
    for event in mission_json.get("events", []):
        event_type = _normalize_text(event.get("type"))
        target = _normalize_text(event.get("target"))
        if event_type == "Kill" and target:
            category = _normalize_text(event.get("category", "")).lower()
            altitude = event.get("altitude")
            detail_parts = []
            if category:
                detail_parts.append(category)
            if altitude is not None:
                try:
                    detail_parts.append(f"{int(altitude)}m")
                except (TypeError, ValueError):
                    pass
            suffix = f" ({', '.join(detail_parts)})" if detail_parts else ""
            notable.append(f"Destroyed {target}{suffix}")
        elif event_type == "Damage Taken":
            damage = _normalize_text(event.get("damage"))
            notable.append(f"Aircraft took damage: {damage}" if damage else "Aircraft took damage")
        elif event_type in {"Bailout", "Crash", "Landing", "Takeoff"}:
            notable.append(event_type)
    return notable[:12]


def build_story_input(
    mission_json: Dict[str, Any],
    *,
    career_id: str | int,
    mission_id: str | int,
    mission_date: str,
    squadron: str,
    mission_theatre: str = "",
    mission_location: str = "",
    country: str = "",
    pilot_last_name: str = "",
    rank: str = "",
    awards: Optional[Iterable[str]] = None,
    promotion: Optional[str] = None,
    mission_awards: Optional[Iterable[str]] = None,
    mission_promotion: Optional[str] = None,
    honors_context: Optional[Dict[str, Any]] = None,
    squadron_context: Optional[Dict[str, Any]] = None,
    missions_completed: Optional[int] = None,
    narrative_memory: Optional[Dict[str, Any]] = None,
    llm_config: Optional[Dict[str, Any]] = None,
    mission_type_code: Any = None,
    m_template: Any = None,
) -> Dict[str, Any]:
    """
    Build the structured input payload sent to the LLM for one mission chapter.
    """
    player = mission_json.get("player", {})
    summary = mission_json.get("summary", {})
    historical_context = resolve_historical_context(squadron, mission_date, country=country, llm_config=llm_config)

    _start_time = _normalize_text(summary.get("mission_start_time"))
    _type_label, _objective_label = resolve_mission_type_labels(mission_type_code, m_template)
    mission = {
        "id": str(mission_id),
        "date": mission_date,
        "theatre": _normalize_text(mission_theatre),
        "location": _normalize_text(mission_location),
        "time_of_day": _derive_time_of_day(_start_time),
        "start_time": _start_time or None,
        "season": _derive_season(mission_date),
        "result": _normalize_text(summary.get("final_state")),
        "duration": _format_duration_for_story(summary.get("flight_duration")),
        "aircraft_damage": summary.get("aircraft_damage", 0),
        "pilot_damage": summary.get("pilot_damage", 0),
        "air_kills": int(summary.get("air_kills_flying", summary.get("air_kills", 0)) or 0),
        "ground_kills": int(summary.get("ground_kills", 0) or 0),
        "naval_kills": int(summary.get("naval_kills", 0) or 0),
        "notable_events": _extract_notable_events(mission_json),
    }
    if _type_label:
        mission["mission_type"] = _type_label
    if _objective_label:
        mission["mission_objective"] = _objective_label

    return {
        "career_id": str(career_id),
        "mission_id": str(mission_id),
        "date": mission_date,
        "pilot": {
            "name": _normalize_text(player.get("name")),
            "last_name": _normalize_text(pilot_last_name),
            "rank": _normalize_text(rank),
            "squadron": _normalize_text(squadron),
            "aircraft": _normalize_text(player.get("aircraft")),
        },
        "mission": mission,
        "career_progress": {
            "missions_completed": missions_completed,
            "awards": list(awards or []),
            "promotion": promotion,
        },
        "mission_progression": {
            "awards": list(mission_awards or []),
            "promotion": _normalize_text(mission_promotion),
        },
        "honors_context": honors_context or {
            "promotion": {},
            "awards": [],
        },
        "squadron_context": squadron_context or {
            "promotions": [],
            "awards": [],
            "transfers": [],
            "kia": [],
            "mia": [],
            "wia": [],
        },
        "historical_context": historical_context,
        "narrative_memory": narrative_memory or {},
    }


def build_campaign_story_input(
    *,
    campaign_id: str,
    mission_id: str,
    mission_date: str,
    mission_summary: Dict[str, Any],
    mission_events: Optional[Iterable[str]] = None,
    mission_start_time: Optional[str] = None,
    mission_type: Optional[str] = None,
    mission_objective: Optional[str] = None,
    rank: str = "",
    pilot_last_name: str = "",
    aircraft: str = "",
    campaign_display_name: str = "",
    campaign_background: str = "",
    country: str = "",
    awards: Optional[Iterable[str]] = None,
    promotion: Optional[str] = None,
    mission_awards: Optional[Iterable[str]] = None,
    mission_promotion: Optional[str] = None,
    honors_context: Optional[Dict[str, Any]] = None,
    missions_completed: Optional[int] = None,
    narrative_memory: Optional[Dict[str, Any]] = None,
    mission_briefing: str = "",
) -> Dict[str, Any]:
    result = _normalize_text(mission_summary.get("result"))
    duration = _format_duration_for_story(mission_summary.get("duration"))
    air_kills = int(mission_summary.get("air_kills", 0) or 0)
    ground_kills = int(mission_summary.get("ground_kills", 0) or 0)
    naval_kills = int(mission_summary.get("naval_kills", 0) or 0)
    aircraft_damage = mission_summary.get("aircraft_damage", 0)
    pilot_damage = mission_summary.get("pilot_damage", 0)

    payload = {
        "career_id": str(campaign_id),
        "mission_id": str(mission_id),
        "date": mission_date,
        "pilot": {
            "name": "",
            "last_name": _normalize_text(pilot_last_name),
            "rank": _normalize_text(rank),
            "squadron": "",
            "aircraft": _normalize_text(aircraft),
        },
        "mission": {
            "id": str(mission_id),
            "date": mission_date,
            "time_of_day": _derive_time_of_day(mission_start_time),
            "start_time": mission_start_time or None,
            "season": _derive_season(mission_date),
            "result": result,
            "duration": duration,
            "aircraft_damage": aircraft_damage,
            "pilot_damage": pilot_damage,
            "air_kills": air_kills,
            "ground_kills": ground_kills,
            "naval_kills": naval_kills,
            "notable_events": list(mission_events or []),
        },
        "career_progress": {
            "missions_completed": missions_completed,
            "awards": list(awards or []),
            "promotion": _normalize_text(promotion),
        },
        "mission_progression": {
            "awards": list(mission_awards or []),
            "promotion": _normalize_text(mission_promotion),
        },
        "honors_context": honors_context or {
            "promotion": {},
            "awards": [],
        },
        "squadron_context": {
            "promotions": [],
            "awards": [],
            "transfers": [],
            "kia": [],
            "mia": [],
            "wia": [],
        },
        "historical_context": {
            "squadron_key": "",
            "display_name": "",
            "country": _normalize_text(country),
            "theatre": "",
            "location": "",
            "summary": "",
            "facts": [],
            "tone_hints": [],
            "forbidden_claims": [],
        },
        "campaign_context": {
            "campaign_id": _normalize_text(campaign_id),
            "campaign_name": _normalize_text(campaign_display_name) or _normalize_text(campaign_id),
            "country": _normalize_text(country),
            "background_excerpt": _normalize_text(campaign_background),
        },
        "narrative_memory": narrative_memory or {},
    }
    mission_block = payload.get("mission", {})
    if isinstance(mission_block, dict):
        resolved_mission_type = _normalize_text(mission_type)
        resolved_mission_objective = _normalize_text(mission_objective)
        if resolved_mission_type:
            mission_block["mission_type"] = resolved_mission_type
        if resolved_mission_objective:
            mission_block["mission_objective"] = resolved_mission_objective
        resolved_briefing = _normalize_text(mission_briefing)
        if resolved_briefing:
            mission_block["briefing"] = resolved_briefing
    return payload


def _get_client(
    api_key: Optional[str] = None,
    *,
    base_url: Optional[str] = None,
    timeout_seconds: float = DEFAULT_API_TIMEOUT_SECONDS,
) -> Any:
    if OpenAI is None:
        raise RuntimeError("OpenAI SDK is not installed. Run: py -3 -m pip install openai")
    resolved_api_key = _normalize_text(api_key) or os.environ.get("OPENAI_API_KEY")
    if not resolved_api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")
    resolved_base_url = _normalize_text(base_url)
    if resolved_base_url:
        return OpenAI(api_key=resolved_api_key, base_url=resolved_base_url, timeout=timeout_seconds)
    return OpenAI(api_key=resolved_api_key, timeout=timeout_seconds)


def _extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    """
    Best-effort extraction of a JSON object from model output.
    """
    raw = _normalize_text(text)
    if not raw:
        return None

    # Strip simple fenced-code wrappers if present.
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        payload = json.loads(raw)
        return payload if isinstance(payload, dict) else None
    except json.JSONDecodeError:
        pass

    # Fallback: extract first object-like block.
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        payload = json.loads(raw[start:end + 1])
        return payload if isinstance(payload, dict) else None
    except json.JSONDecodeError:
        return None


def _extract_response_text(response: Any) -> str:
    # chat.completions response shape (OpenAI, Anthropic, OpenRouter, Google compat)
    choices = getattr(response, "choices", None)
    if isinstance(choices, (list, tuple)) and choices:
        content = getattr(getattr(choices[0], "message", None), "content", None)
        if isinstance(content, str):
            text = _normalize_text(content)
            if text:
                return text

    # responses.create shape (OpenAI Responses API — legacy fallback)
    text = _normalize_text(getattr(response, "output_text", ""))
    if text:
        return text

    output_items = getattr(response, "output", None)
    if isinstance(output_items, (list, tuple)):
        chunks: list[str] = []
        for item in output_items:
            content_items = getattr(item, "content", None)
            if isinstance(content_items, list):
                for part in content_items:
                    part_value = getattr(part, "text", "")
                    part_text = part_value.strip() if isinstance(part_value, str) else ""
                    if part_text:
                        chunks.append(part_text)
                    if not part_text and isinstance(part, dict):
                        maybe_value = part.get("text")
                        maybe = maybe_value.strip() if isinstance(maybe_value, str) else ""
                        if maybe:
                            chunks.append(maybe)
            if isinstance(item, dict):
                content_items = item.get("content")
                if isinstance(content_items, list):
                    for part in content_items:
                        if isinstance(part, dict):
                            maybe_value = part.get("text")
                            maybe = maybe_value.strip() if isinstance(maybe_value, str) else ""
                            if maybe:
                                chunks.append(maybe)
        merged = "\n".join(chunk for chunk in chunks if chunk).strip()
        if merged:
            return merged

    # Last-resort path for SDK variants: inspect dumped dict recursively.
    try:
        dumped = response.model_dump() if hasattr(response, "model_dump") else None
    except Exception:
        dumped = None
    if isinstance(dumped, dict):
        found: list[str] = []

        def _walk(node: Any) -> None:
            if isinstance(node, dict):
                for key, value in node.items():
                    if key == "text":
                        text_val = value.strip() if isinstance(value, str) else ""
                        if text_val:
                            found.append(text_val)
                    else:
                        _walk(value)
            elif isinstance(node, list):
                for item in node:
                    _walk(item)

        _walk(dumped)
        merged = "\n".join(part for part in found if part).strip()
        if merged:
            return merged

    return ""


def _looks_like_invalid_story_text(text: str) -> bool:
    value = _normalize_text(text)
    if not value:
        return True
    lower = value.lower()
    if lower.startswith("{'format':") or lower.startswith('{"format":'):
        return True
    if "verbosity" in lower and "format" in lower and len(value) < 180:
        return True
    return False


_REPORT_STYLE_MARKERS = [
    r"\bm\d{3,5}\b",              # mission ids like M3006
    r"\bair_kills\b",
    r"\bground_kills\b",
    r"\bnaval_kills\b",
    r"\baircraft_damage\b",
    r"\bpilot_damage\b",
    r"\bthe day comprised\b",
    r"\bthe record(?:ed)?\b",
]


def _report_style_reason(text: str) -> str:
    """Return the first matching report-style marker, or empty string if none."""
    value = _normalize_text(text)
    if not value:
        return "empty"
    lower = value.lower()
    for pattern in _REPORT_STYLE_MARKERS:
        if re.search(pattern, lower):
            return pattern
    return ""


def _looks_like_report_style_story(text: str) -> bool:
    return bool(_report_style_reason(text))


def _looks_like_meta_reasoning_text(text: str) -> bool:
    value = _normalize_text(text)
    if not value:
        return False
    lower = value.lower()

    # Typical planning / chain-of-thought leakage markers.
    meta_markers = [
        "i need to",
        "it seems safest",
        "i'll make sure",
        "defining chapter content",
        "determining context usage",
        "using historical context rules",
        "clarifying json requirements",
        "the rules say",
        "json that includes a title",
        "third-person past tense",
    ]
    if any(marker in lower for marker in meta_markers):
        return True

    # Markdown heading-heavy planning text is not valid chapter prose.
    if value.count("**") >= 4 and ("\n" in value):
        return True

    return False


def _looks_truncated_story_text(text: str) -> bool:
    value = _normalize_text(text)
    if not value:
        return True
    if len(value.split()) < 40:
        return True
    tail = value[-1]
    if tail in ".!?\"')\u2019\u201d\u2026\u2014\u2013":
        return False
    # Common clipped endings: unfinished word/sentence at hard cutoff.
    return True


def _build_deterministic_story_fallback(story_input: Dict[str, Any]) -> Dict[str, str]:
    mission = story_input.get("mission", {}) if isinstance(story_input, dict) else {}
    pilot = story_input.get("pilot", {}) if isinstance(story_input, dict) else {}
    mission_progression = story_input.get("mission_progression", {}) if isinstance(story_input, dict) else {}
    campaign_context = story_input.get("campaign_context", {}) if isinstance(story_input, dict) else {}

    mission_date = _normalize_text(story_input.get("date")) or _normalize_text(mission.get("date")) or "Unknown date"
    aircraft = _normalize_text(pilot.get("aircraft")) or "aircraft"
    result = _normalize_text(mission.get("result")) or "Unknown"
    duration = _normalize_text(mission.get("duration"))
    air_kills = int(mission.get("air_kills", 0) or 0)
    ground_kills = int(mission.get("ground_kills", 0) or 0)
    naval_kills = int(mission.get("naval_kills", 0) or 0)
    campaign_name = _normalize_text(campaign_context.get("campaign_name"))
    promotion = _normalize_text(mission_progression.get("promotion"))
    awards = mission_progression.get("awards", [])
    award_text = ", ".join([_normalize_text(a) for a in awards if _normalize_text(a)])

    p1 = (
        f"On {mission_date}, the pilot flew a mission in a {aircraft}"
        + (f" during {campaign_name}." if campaign_name else ".")
    )
    p2 = (
        f"The sortie ended with status: {result}."
        + (f" Flight time was {duration}." if duration else "")
        + f" Recorded combat results were {air_kills} air kills, {ground_kills} ground kills, and {naval_kills} naval kills."
    )

    progression_parts: list[str] = []
    if promotion:
        progression_parts.append(f"The mission included a promotion to {promotion}.")
    if award_text:
        progression_parts.append(f"Awards recorded for this mission: {award_text}.")
    if not progression_parts:
        progression_parts.append("No promotion or mission-specific award event was recorded.")
    p3 = " ".join(progression_parts)

    return {
        "title": "Mission Chronicle",
        "story_text": f"{p1}\n\n{p2}\n\n{p3}",
    }


def _attempt_story_repair(
    client: Any,
    *,
    provider: str,
    model: str,
    story_input: Dict[str, Any],
    partial_text: str,
    max_output_tokens: int,
    output_language: str,
) -> str:
    text = _normalize_text(partial_text)
    if not text:
        return ""
    language_label = _LANGUAGE_LABELS.get(_normalize_text(output_language).lower(), "English")
    repair_prompt = (
        "Rewrite the chapter below into a complete, polished wartime narrative.\n"
        "Use only the supplied mission facts, keep third-person past tense, and write exactly 3 paragraphs.\n"
        "Do not output JSON or markdown.\n"
        f"Write in {language_label}.\n\n"
        "Mission facts JSON:\n"
        f"{json.dumps(story_input, ensure_ascii=False, indent=2)}\n\n"
        "Incomplete chapter text:\n"
        f"{text}"
    )
    repaired = _create_story_response(
        client,
        provider=provider,
        model=model,
        prompt=repair_prompt,
        max_output_tokens=max_output_tokens,
    )
    return _normalize_text(_extract_response_text(repaired))


def _backup_models_for_provider(provider: str, primary_model: str) -> list[str]:
    provider_key = _normalize_text(provider).lower()
    primary = _normalize_text(primary_model)
    candidates: list[str] = []
    if provider_key == "openai":
        candidates = ["gpt-4o-mini", "gpt-4o"]
    elif provider_key == "openrouter":
        candidates = ["openai/gpt-4o-mini", "openai/gpt-4o", "google/gemini-2.0-flash-001"]
    elif provider_key == "anthropic":
        candidates = ["claude-3-5-haiku-20241022", "claude-3-5-sonnet-20241022"]
    elif provider_key == "google":
        candidates = ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]
    elif provider_key == "microsoft":
        candidates = ["gpt-4o-mini", "gpt-4o"]

    ordered: list[str] = []
    seen: set[str] = set()
    for model in [primary] + candidates:
        key = _normalize_text(model)
        if not key or key in seen:
            continue
        seen.add(key)
        ordered.append(key)
    return ordered


def _create_story_response(
    client: Any,
    *,
    provider: str,
    model: str,
    prompt: str,
    max_output_tokens: int,
) -> Any:
    _ = provider  # reserved for provider-specific extensions
    messages = [{"role": "user", "content": prompt}]
    try:
        return client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_output_tokens,
        )
    except TypeError:
        # Some provider SDKs reject unknown kwargs entirely.
        return client.chat.completions.create(model=model, messages=messages)
    except openai.BadRequestError as exc:
        # Newer OpenAI models (o3, o4-mini, etc.) require max_completion_tokens
        # instead of max_tokens and return a 400 if max_tokens is passed.
        if "max_tokens" in str(exc) and "max_completion_tokens" in str(exc):
            return client.chat.completions.create(
                model=model,
                messages=messages,
                max_completion_tokens=max_output_tokens,
            )
        raise


def generate_mission_story(
    story_input: Dict[str, Any],
    *,
    model: str = DEFAULT_MODEL,
    api_key: Optional[str] = None,
    provider: str = "openai",
    base_url: Optional[str] = None,
    output_language: str = "en",
) -> Dict[str, str]:
    client = _get_client(api_key=api_key, base_url=base_url)
    language_label = _LANGUAGE_LABELS.get(_normalize_text(output_language).lower(), "English")

    # Strip PDF-only fields before serialising story_input for the LLM.
    # chapter_scope.mission_jsons embeds the full parsed events.json (squadron_flights, kills, etc.)
    # and is only used by the PDF generator — sending it to the LLM inflates the prompt by
    # tens of thousands of tokens for missions with large formations.
    if isinstance(story_input, dict) and isinstance(story_input.get("chapter_scope"), dict):
        _cs = dict(story_input["chapter_scope"])
        _cs.pop("mission_jsons", None)
        story_input = {**story_input, "chapter_scope": _cs}

    chapter_scope = story_input.get("chapter_scope", {}) if isinstance(story_input, dict) else {}
    missions_in_chapter = 1
    if isinstance(chapter_scope, dict):
        try:
            missions_in_chapter = max(1, int(chapter_scope.get("missions_in_chapter", 1) or 1))
        except (TypeError, ValueError):
            missions_in_chapter = 1

    _has_theatre_transition = isinstance(story_input, dict) and bool(story_input.get("theatre_transition"))
    _sq_ctx = (story_input or {}).get("squadron_context", {}) if isinstance(story_input, dict) else {}
    _inter_acts = (story_input or {}).get("inter_mission_activities", []) if isinstance(story_input, dict) else []
    _is_squadron_day = (
        isinstance(story_input, dict)
        and (story_input.get("chapter_scope") or {}).get("scope") == "squadron_day"
    )
    _has_squadron_honors = bool(
        _sq_ctx.get("promotions") or _sq_ctx.get("awards")
        or _sq_ctx.get("kia") or _sq_ctx.get("mia") or _sq_ctx.get("wia")
        or any(
            int(fr.get("air_kills") or 0) > 0
            or int(fr.get("ground_kills") or 0) > 0
            or (fr.get("outcome") or "") in ("killed", "bailed_survived", "shot_down")
            for fr in (_sq_ctx.get("flight_results") or [])
            if isinstance(fr, dict)
        )
        or any(
            (item.get("casualties") or item.get("awards") or item.get("promotions"))
            for item in (_inter_acts if isinstance(_inter_acts, list) else [])
            if isinstance(item, dict)
        )
    )

    if _is_squadron_day:
        paragraph_rule = "Write exactly 3 paragraphs."
        word_target = "Target 160-320 words."
        max_output_tokens = 850
    elif missions_in_chapter <= 1:
        if _has_theatre_transition:
            paragraph_rule = "Write exactly 4 paragraphs."
            word_target = "Target 250-500 words."
            max_output_tokens = 1300
        elif _has_squadron_honors:
            paragraph_rule = "Write exactly 4 paragraphs."
            word_target = "Target 250-600 words."
            max_output_tokens = 1550
        else:
            paragraph_rule = "Write exactly 3 paragraphs."
            word_target = "Target 180-370 words."
            max_output_tokens = 950
    elif missions_in_chapter == 2:
        paragraph_rule = "Write exactly 3 paragraphs."
        word_target = "Target 240-470 words."
        max_output_tokens = 1200
    else:
        paragraph_rule = "Write exactly 4 paragraphs."
        word_target = "Target 320-650 words."
        max_output_tokens = 1650

    prompt = (
        "Write the next chapter of a continuous wartime storybook.\n\n"
        "Rules:\n"
        "- Use third-person past tense only.\n"
        "- Do not switch narrator perspective.\n"
        "- Write as historical narrative, not as a mission report.\n"
        "- Integrate facts into flowing prose; avoid list-like/stat-dump phrasing.\n"
        "- If pilot.rank and pilot.last_name are present, first mention must use 'rank + last name' (e.g., 'Leutnant Bleiholder').\n"
        "- After first mention, use last name only.\n"
        "- Do not use the pilot's first name unless explicitly required by the input facts.\n"
        "- Keep continuity with the previous narrative memory.\n"
        "- If narrative_memory.recent_events is non-empty, this is not the first chapter. Do not re-introduce the squadron, its strategic role, or the operational context (e.g. Army Group North, drive toward Leningrad) — treat these as already established.\n"
        "- Vary the opening: do not start with the pilot climbing into the cockpit or taking off. Begin in medias res, with a scene, an observation, or a moment from the day.\n"
        "- If narrative_memory.used_titles is non-empty, do not reuse any of those titles. Also avoid the same structural pattern (e.g. if several titles use 'X Over Y', use a different form). If more than two titles already contain weather words (overcast, clouds, drizzle, rain, snow, autumn, winter), choose a title that does not rely on weather imagery.\n"
        "- Use only the supplied facts.\n"
        "- Do not invent awards, promotions, injuries, victories, locations, or commanders.\n"
        "- If narrative_memory.total_aerial_victories is present and greater than zero, use it as the pilot's confirmed kill count at the START of this mission. The count after this mission is narrative_memory.total_aerial_victories plus mission.air_kills. Never invent or estimate the tally — use only these numbers.\n"
        "- Keep the story historically grounded and atmospheric.\n"
        "- If mission.time_of_day is present, use it to set the scene (e.g., 'at dawn', 'under a midday sun'). Do not invent a time if the field is absent or empty.\n"
        "- If mission.season is present, weave it into the atmosphere naturally (e.g., autumn mud, winter frost, summer heat). Do not invent a season if the field is absent or empty.\n"
        "- If mission.weather is present, it contains real historical meteorological data for the mission location and date. Use it for environmental accuracy — temperature, precipitation, cloud cover, wind. Do not describe weather as colder, snowier, or more dramatic than the data supports. For example, if the temperature is above zero and conditions are 'partly cloudy', do not write frozen ground or blizzards.\n"
        "- If mission.theatre or mission.location is present, treat those fields as the authoritative operational setting for this mission.\n"
        "- Do not infer or substitute a different theatre/location from squadron history when mission.theatre or mission.location is provided.\n"
        "- If mission.mission_type is present, it is the official mission category assigned by the air force (e.g., 'Frontline Patrol', 'Escort Bombers', 'Bomb Bridge'). Reflect this in the narrative — a patrol mission reads differently from a bombing raid or an escort. Use mission_type to colour the pilot's role and purpose, not as a label to quote verbatim.\n"
        "- If mission.mission_objective is also present, it refines mission_type with the specific target or area (e.g., 'Enemy Territory' for a patrol, 'V-1 Launch Site' for an escort, 'Supply Depot Cover' for an anti-bomber patrol). Weave this detail into the scene naturally.\n"
        "- If mission.formation_size is present, use it to describe the scale of the operation naturally: 1=solo; 2=pair; 3=three-ship; 4=four-ship flight; larger=formation. Use the terminology appropriate for the pilot's air force and era — e.g. Rotte/Schwarm for Luftwaffe, Para/Zveno for Soviet, Element/Flight for USAAF/RAF. Do not use German terms for non-German pilots.\n"
        "- If mission.formation_role is present, it is either 'leader' (formation commander) or 'wingman'. Reflect this in how you describe the pilot's position — a leader directs the formation, a wingman supports.\n"
        "- If historical_context.summary or historical_context.facts are present, integrate them naturally.\n"
        "- pilot.rank is the rank held DURING the mission. Use it throughout the narrative.\n"
        "- If mission_progression.promotion is non-empty, it is a rank awarded AFTER the pilot landed/returned. You MUST mention it as a post-mission event (e.g., 'upon return he was promoted to...'). Never use the promoted rank to describe the pilot during the sortie.\n"
        "- career_progress.awards is the pilot's full career decoration list — do NOT present these as awarded in this chapter.\n"
        "- Only mission_progression.awards lists decorations actually received after this specific mission. Mention only those as newly awarded.\n"
        "- If mission_progression.awards is empty, no decoration was awarded after this mission. Do not mention any award as newly received, newly earned, or recently bestowed.\n"
        "- If honors_context.promotion.fact is present, include one short historical note tied to that promotion.\n"
        "- If honors_context.awards has facts, include at least one short factual note tied to the award(s) received.\n"
        "- Do not claim a promotion or award for this mission when mission_progression says none occurred.\n"
        "- If pre_service_awards is present, those are training-era decorations the pilot earned before his first operational deployment — they were pinned on during training, not after this mission. You may mention them briefly as established background (e.g. 'already wearing his pilot's badge') but never as newly awarded in this chapter.\n"
        "- If pilot_bio is present, it is the personal background the player chose for this pilot at career creation — his origins, personality, and life before the war. "
        "If first_career_chapter is true, you MUST weave at least one element from the pilot's background into the narrative — his origins, a formative experience, a personality trait, or what brought him to this war. This is the reader's introduction to who he is. "
        "In subsequent chapters (first_career_chapter absent or false), draw from the bio only when something in the chapter connects naturally to his personal history — a place, a memory, a motivation. Do not repeat it verbatim and do not force it where it does not fit.\n"
        "- Treat squadron_context as factual.\n"
        "- If squadron_context.promotions is non-empty, you MUST mention every entry in the narrative. Each entry has 'pilot' (name) and 'promoted_to' (the new rank). Write it as 'X was promoted to [promoted_to]' — do NOT use promoted_to as a name prefix before the pilot's name. A chapter that omits any promotion is factually incomplete.\n"
        "- If squadron_context.awards is non-empty, you MUST mention every award by its full name and the pilot's name — do not omit any. A chapter that omits any award from this list is factually incomplete.\n"
        "- If squadron_context.kia is non-empty, you MUST mention every KIA as a loss in the narrative. "
        "IMPORTANT: squadron_context.kia/mia/wia are casualties that occurred during the player's own mission — narrate them as losses within the player's sortie, NOT as casualties from a separate concurrent flight.\n"
        "- If squadron_context.transfers is non-empty, mention transfers naturally where they fit the narrative.\n"
        "- Do not invent squadron-member outcomes not present in squadron_context.\n"
        "- Do not name any person (pilot, commander, wingman, Staffelkapitän, adjutant, greeting officer, etc.) who does not appear explicitly in squadron_context. Inventing named individuals is strictly forbidden — do not do this even when it would make the prose feel more vivid or personal. Use 'his superior', 'the duty officer', or similar generic references instead.\n"
        "- When referencing a pilot listed in squadron_context, use their name exactly as supplied. If a rank field is present for that pilot entry, you may use it — e.g. 'Unteroffizier Müller was awarded...'. Never invent or assume a rank that is not in the supplied entry.\n"
        "- If squadron_context.flight_results is present and non-empty, weave all significant entries naturally into the narrative — do not recite them as a list. "
        "These entries are from the player's own sortie — do NOT attribute them to a separate concurrent mission. "
        "An entry with outcome 'killed' is a significant loss and worth noting. "
        "An entry with outcome 'bailed_survived' means the pilot was shot down but parachuted to safety. "
        "An entry with outcome 'shot_down' means the aircraft was lost (fate of the pilot was uncertain in the field). "
        "If shot_down_by_type is present, you may name the enemy aircraft type (e.g. 'a Yak-1'). "
        "If kill_cause is present, use it to describe the nature of the loss accurately — do NOT say 'shot down' when kill_cause indicates otherwise: "
        "'shot_down' = destroyed by enemy aircraft gunfire (default); "
        "'collision_enemy' = mid-air collision with an enemy aircraft; "
        "'collision_friendly' = mid-air collision with a friendly aircraft (do NOT frame this as enemy action); "
        "'friendly_fire' = destroyed by friendly aircraft guns (an unfortunate accident of war); "
        "'killed_by_aa' = brought down by anti-aircraft ground fire; "
        "'crashed_combat' = took combat damage and subsequently crashed or burned; "
        "'crashed' = aircraft lost with no enemy involvement — engine failure, accident, or unknown mechanical cause. "
        "If air_kills or ground_kills are non-zero, you may credit that pilot with those kills. "
        "If a rank field is present for that entry, use it as with other squadron_context pilots. "
        "Only mention entries that contribute meaningfully to the story — skip pilots who simply survived without incident unless they scored kills. "
        "Do not name any flight_results pilot not listed in the supplied data.\n"
        "- If squadron_context.escort_context is present, this mission was an escort sortie and escort_context describes the fate of the formation the pilot was protecting. "
        "escort_context.formation is a list of aircraft types with their count and how many were lost. "
        "escort_context.total is the total number of aircraft in the escorted formation; escort_context.lost is how many were lost; escort_context.survived is how many returned. "
        "Weave this into the narrative as the outcome of the escort duty — whether the formation was brought through intact or suffered losses. "
        "If lost > 0, treat it as a mission setback even if the pilot himself scored kills. "
        "If lost == 0, the escort was a success and can be described as such. "
        "Do not invent specifics beyond what escort_context provides.\n"
        "- If inter_mission_activities is non-empty, weave the squadron's off-day or parallel sorties into the narrative. "
        "Entries with same_day=false occurred between the previous chapter and this one — reference them as prior events "
        "('During the intervening days ...', 'While the pilot was grounded, the squadron ...', etc.). "
        "Entries with same_day=true occurred on the same date but in missions the player did not fly — mention them as "
        "concurrent activity happening elsewhere ('That same afternoon, another element of the squadron ...'). "
        "IMPORTANT: casualties listed in inter_mission_activities entries are from those separate concurrent sorties only — "
        "do NOT conflate them with squadron_context.kia/mia/wia/flight_results, which belong to the player's own mission. "
        "Acknowledge casualties (KIA/MIA/WIA) by name if present. Note squadron_air_kills if significant. "
        "Integrate naturally in 1-3 sentences total — do not enumerate each entry as a list item. "
        "Do not invent pilot names or details beyond what is supplied.\n"
        "- If mission.other_incidences is non-empty, mention those facts explicitly in the chapter.\n"
        "- Treat mission.other_incidences as mandatory factual aftermath/context, not optional flavor.\n"
        "- If mission.other_incidences includes 'Recovery from injury', mention that the pilot entered a recovery period after this mission; do not present that recovery as occurring before the sortie ended.\n"
        "- If mission.other_incidences includes 'Appointment as squadron commander ...' or 'Transfer from ... to ...', mention it as a post-mission development or administrative change.\n"
        "- If inter_mission_promotion is present, the pilot was promoted to that rank on a day between missions when he did not fly. You MUST mention it — weave it into the chapter as background that occurred in the days before this sortie (e.g. 'In the days since his last sortie, orders had come through promoting him to Leutnant'). Do not present it as awarded today or after today's mission.\n"
        "- If theatre_transition is present, this is the pilot's first mission in a new theatre of operations. Structure the chapter across four phases: (1) the conclusion of the previous campaign (theatre_transition.previous_theatre) and the squadron being recalled or redeployed; (2) the interim period between postings, during which any transition_awards or transition_promotions were received — treat these as received during that transfer period, not after today's sortie; (3) arrival at the new posting and joining or assuming command of the new formation; (4) the opening sortie in the new theatre (theatre_transition.new_theatre). Give each phase meaningful weight — do not compress the transition into a single sentence.\n"
        "- If theatre_transition.transition_awards is non-empty, you MUST name every decoration in that list by its full name, describing it as received during the transition period between the two campaigns. This is mandatory — a chapter that omits any item from transition_awards is factually incomplete. IMPORTANT: the general rule 'career_progress.awards must not be presented as awarded in this chapter' does NOT apply to decorations that also appear in theatre_transition.transition_awards. Those must be mentioned as received during the transit period.\n"
        "- If theatre_transition.transition_promotions is non-empty, you MUST name each rank explicitly as received during the transition period between postings.\n"
        "- If theatre_transition.new_squadron is present, describe the pilot joining (or taking command of) that specific unit. If theatre_transition.previous_squadron is also present, you may note the change of assignment.\n"
        "- If theatre_transition.role is 'commander', the pilot assumed command of the new unit before or upon arrival. Reflect this as a leadership responsibility — the pilot enters the new theatre bearing command authority, not merely as a new arrival.\n"
        "- Never output internal mission IDs (e.g., M3010, M3011) in the final text.\n"
        "- Mention sortie count naturally (e.g., 'two sorties that day') without technical labels.\n"
        "- Structure the narrative in strict chronological order: (1) pre-mission / departure, (2) outbound flight and approach, (3) combat or mission action, (4) return flight and landing, (5) post-mission events such as promotions, awards, transfers, and squadron losses. "
        "Never mention promotions, awards, transfers, or administrative events before the pilot has landed. These are post-mission developments and must appear only after the return flight is described.\n"
        "- Keep tone military-historical. Some drama and atmosphere are welcome, but stay grounded in the facts supplied.\n"
        "- Avoid bureaucratic phrases like 'the record shows' or 'on record'.\n"
        "- If no promotions/awards/squadron events occurred, omit those topics naturally; do not explicitly list 'none'.\n"
        "- Do not write debrief-style sentences that dump multiple metrics in one line.\n"
        "- When referring to the pilot's confirmed aerial victory total, use career_progress.aerial_victories. This is always authoritative — it overrides any figure in narrative_memory. Ground and naval kills are not part of this count.\n"
        "- If campaign_context.background_excerpt is present, use it as atmosphere only.\n"
        "- Do not quote long chunks from campaign_context.background_excerpt verbatim.\n"
        "- If mission.briefing is present, it is the original briefing text written by the campaign creator for this specific mission. "
        "Draw on it to convey the pilot's sense of purpose, the tactical situation, and the historical atmosphere. "
        "Do not reproduce it verbatim — use it as source material to enrich the narrative.\n"
        "- If chapter_scope.scope is 'day', narrate one cohesive day arc across all listed missions in chapter_scope.mission_ids.\n"
        "- If chapter_scope.scope is 'squadron_day', the player pilot did not fly this day. "
        "Write 3 paragraphs from the pilot's perspective at base. "
        "Paragraph 1: the pilot's situation — grounded for the day (be brief and understated about the reason; invent nothing specific). "
        "Paragraph 2: what the squadron accomplished or suffered, drawn entirely from squadron_context. "
        "You MUST state the number of missions the squadron flew (missions_flown) if present. "
        "You MUST state the exact number of aerial kills as squadron_air_kills if > 0, "
        "and ground kills as squadron_ground_kills if > 0 — use concrete numbers, not vague language. "
        "Name any KIA/MIA/WIA casualties by name and rank. Mention promotions and awards. "
        "If only missions_flown is available (no kills, no casualties), briefly note that the squadron flew without incident. "
        "Paragraph 3: the pilot's reflection on the day — a quiet, grounded close. "
        "Do not present this as a combat sortie. Do not invent mission objectives or enemy activity not in the data.\n"
        "- If mission duration is mentioned, use only hours and minutes (no seconds).\n"
        f"- Write the entire chapter in {language_label}.\n"
        f"- {paragraph_rule}\n"
        f"- {word_target}\n"
        "- Create a short chapter title (4-8 words).\n"
        "- Return valid JSON only with keys: title, story_text.\n\n"
        "Input JSON:\n"
        f"{json.dumps(story_input, ensure_ascii=False, indent=2)}"
    )
    retry_prompt = (
        "Write one cohesive wartime chapter using only the supplied JSON facts.\n"
        "Return plain text only, 3-4 paragraphs, no JSON, no markdown.\n"
        "Do not use mission IDs (e.g., M3006). Do not write in report/logbook style.\n"
        "Integrate facts into narrative prose and avoid stat-dump phrasing.\n\n"
        "Input JSON:\n"
        f"{json.dumps(story_input, ensure_ascii=False, indent=2)}"
    )

    for candidate_model in _backup_models_for_provider(provider, model):
        try:
            response = _create_story_response(
                client,
                provider=provider,
                model=candidate_model,
                prompt=prompt,
                max_output_tokens=max_output_tokens,
            )
        except openai.NotFoundError:
            LOGGER.warning("Model not found, trying next backup: %s", candidate_model)
            continue
        except openai.RateLimitError:
            raise

        raw_text = _extract_response_text(response)
        payload = _extract_json_object(raw_text)
        if payload:
            title = _normalize_text(payload.get("title"))
            story_text = _normalize_text(payload.get("story_text"))
            if (
                story_text
                and not _looks_like_report_style_story(story_text)
                and not _looks_truncated_story_text(story_text)
                and not _looks_like_meta_reasoning_text(story_text)
            ):
                story_text = _enforce_squadron_event_presence(story_input, story_text, output_language)
                LOGGER.info(
                    "Story generated: provider=%s model=%s mission_id=%s",
                    provider, candidate_model, story_input.get("mission_id", "?"),
                )
                return {
                    "title": title,
                    "story_text": story_text,
                }
            _rs_reason = _report_style_reason(story_text or "")
            _reason = (
                "empty story_text" if not story_text
                else f"report-style({_rs_reason})" if _rs_reason
                else "truncated" if _looks_truncated_story_text(story_text)
                else "meta-reasoning"
            )
            LOGGER.warning(
                "Story quality check failed for model=%s (json path): reason=%s; text_preview=%.120r",
                candidate_model, _reason, story_text or "",
            )
        else:
            LOGGER.warning(
                "Story JSON extraction failed for model=%s; raw_preview=%.120r",
                candidate_model, raw_text or "",
            )

        fallback_text = _normalize_text(raw_text)
        if (
            _looks_like_invalid_story_text(fallback_text)
            or _looks_like_report_style_story(fallback_text)
            or _looks_truncated_story_text(fallback_text)
            or _looks_like_meta_reasoning_text(fallback_text)
        ):
            LOGGER.warning(
                "Story fallback text also failed quality check for model=%s; attempting retry prompt",
                candidate_model,
            )
            retry_response = _create_story_response(
                client,
                provider=provider,
                model=candidate_model,
                prompt=retry_prompt,
                max_output_tokens=max_output_tokens,
            )
            fallback_text = _normalize_text(_extract_response_text(retry_response))
            needs_repair = _looks_truncated_story_text(fallback_text) and not _looks_like_invalid_story_text(fallback_text)
            if needs_repair:
                repaired_text = _attempt_story_repair(
                    client,
                    provider=provider,
                    model=candidate_model,
                    story_input=story_input,
                    partial_text=fallback_text,
                    max_output_tokens=max_output_tokens,
                    output_language=output_language,
                )
                if repaired_text and not _looks_like_invalid_story_text(repaired_text) and not _looks_like_report_style_story(repaired_text) and not _looks_truncated_story_text(repaired_text):
                    LOGGER.info(
                        "Story generated (repaired): provider=%s model=%s mission_id=%s",
                        provider, candidate_model, story_input.get("mission_id", "?"),
                    )
                    return {
                        "title": "",
                        "story_text": _enforce_squadron_event_presence(story_input, repaired_text, output_language),
                    }
            if (
                _looks_like_invalid_story_text(fallback_text)
                or _looks_like_report_style_story(fallback_text)
                or _looks_truncated_story_text(fallback_text)
                or _looks_like_meta_reasoning_text(fallback_text)
            ):
                LOGGER.warning(
                    "Retry prompt also rejected for model=%s; trying next candidate",
                    candidate_model,
                )
                continue
        LOGGER.info(
            "Story generated (raw text path): provider=%s model=%s mission_id=%s",
            provider, candidate_model, story_input.get("mission_id", "?"),
        )
        return {
            "title": "",
            "story_text": _enforce_squadron_event_presence(story_input, fallback_text, output_language),
        }

    # Final safety net after exhausting model fallbacks.
    LOGGER.warning(
        "All model candidates exhausted for mission story generation; using deterministic fallback"
    )
    fallback_payload = _build_deterministic_story_fallback(story_input)
    return {
        "title": _normalize_text(fallback_payload.get("title")),
        "story_text": _normalize_text(fallback_payload.get("story_text")),
    }


def update_narrative_memory(
    story_input: Dict[str, Any],
    story_text: str,
    *,
    model: str = DEFAULT_MODEL,
    api_key: Optional[str] = None,
    provider: str = "openai",
    base_url: Optional[str] = None,
) -> Dict[str, Any]:
    client = _get_client(api_key=api_key, base_url=base_url)
    prompt = (
        "Update the pilot's narrative memory after this mission.\n\n"
        "Rules:\n"
        "- Keep it compact and factual.\n"
        "- Preserve continuity.\n"
        "- Do not invent facts.\n"
        "- Return all string values in English.\n"
        "- Return valid JSON only.\n\n"
        "Return keys:\n"
        "- current_rank\n"
        "- current_squadron\n"
        "- arc_summary\n"
        "- key_milestones\n"
        "- recurring_themes\n"
        "- recent_events\n\n"
        "Story input JSON:\n"
        f"{json.dumps(story_input, ensure_ascii=False, indent=2)}\n\n"
        "Generated story:\n"
        f"{story_text}"
    )
    response = _create_story_response(
        client,
        provider=provider,
        model=model,
        prompt=prompt,
        max_output_tokens=800,
    )
    payload = _extract_json_object(_extract_response_text(response))
    if not isinstance(payload, dict):
        raise ValueError("Narrative memory response was not a JSON object")
    return payload


def _append_unique_limited(values: list[str], item: str, *, limit: int) -> list[str]:
    text = _normalize_text(item)
    if not text:
        return values
    deduped = [v for v in values if _normalize_text(v)]
    if text in deduped:
        deduped = [v for v in deduped if v != text]
    deduped.append(text)
    if len(deduped) > limit:
        deduped = deduped[-limit:]
    return deduped


def update_narrative_memory_local(
    story_input: Dict[str, Any],
    previous_memory: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    previous = previous_memory if isinstance(previous_memory, dict) else {}
    memory: Dict[str, Any] = {
        "current_rank": _normalize_text(previous.get("current_rank")),
        "current_squadron": _normalize_text(previous.get("current_squadron")),
        "arc_summary": _normalize_text(previous.get("arc_summary")),
        "key_milestones": list(previous.get("key_milestones") or []),
        "recurring_themes": list(previous.get("recurring_themes") or []),
        "recent_events": list(previous.get("recent_events") or []),
        "used_titles": list(previous.get("used_titles") or []),
        "total_aerial_victories": int(previous.get("total_aerial_victories") or 0),
    }

    pilot = story_input.get("pilot", {}) if isinstance(story_input, dict) else {}
    mission = story_input.get("mission", {}) if isinstance(story_input, dict) else {}
    campaign_context = story_input.get("campaign_context", {}) if isinstance(story_input, dict) else {}
    mission_progression = story_input.get("mission_progression", {}) if isinstance(story_input, dict) else {}
    career_progress = story_input.get("career_progress", {}) if isinstance(story_input, dict) else {}

    # Authoritative cumulative aerial kill count — overwrite from story_input every time.
    aerial_victories = career_progress.get("aerial_victories")
    if aerial_victories is not None:
        try:
            memory["total_aerial_victories"] = int(aerial_victories)
        except (TypeError, ValueError):
            pass

    rank = _normalize_text(mission_progression.get("promotion")) or _normalize_text(pilot.get("rank"))
    if rank:
        memory["current_rank"] = rank

    squadron = _normalize_text(pilot.get("squadron")) or _normalize_text(campaign_context.get("campaign_name"))
    if squadron:
        memory["current_squadron"] = squadron

    mission_date = _normalize_text(story_input.get("date"))
    result = _normalize_text(mission.get("result")) or "Unknown"
    air_kills = int(mission.get("air_kills", 0) or 0)
    ground_kills = int(mission.get("ground_kills", 0) or 0)
    naval_kills = int(mission.get("naval_kills", 0) or 0)
    event_line = f"{mission_date}: {result}; air {air_kills}, ground {ground_kills}, naval {naval_kills}"
    memory["recent_events"] = _append_unique_limited(memory["recent_events"], event_line, limit=10)

    promotion = _normalize_text(mission_progression.get("promotion"))
    if promotion:
        milestone = f"{mission_date}: promoted to {promotion}"
        memory["key_milestones"] = _append_unique_limited(memory["key_milestones"], milestone, limit=20)
        memory["recurring_themes"] = _append_unique_limited(memory["recurring_themes"], "career advancement", limit=8)

    awards = mission_progression.get("awards", [])
    if isinstance(awards, list):
        for award in awards:
            award_name = _normalize_text(award)
            if not award_name:
                continue
            milestone = f"{mission_date}: received {award_name}"
            memory["key_milestones"] = _append_unique_limited(memory["key_milestones"], milestone, limit=20)
        if awards:
            memory["recurring_themes"] = _append_unique_limited(memory["recurring_themes"], "recognized service", limit=8)

    result_theme_map = {
        "landed": "mission survival",
        "bailout": "survival under pressure",
        "kia": "high attrition",
        "mia": "combat uncertainty",
        "wia": "combat injuries",
    }
    lower_result = result.lower()
    for marker, theme in result_theme_map.items():
        if marker in lower_result:
            memory["recurring_themes"] = _append_unique_limited(memory["recurring_themes"], theme, limit=8)
            break

    arc_bits: list[str] = []
    if memory.get("current_rank"):
        arc_bits.append(f"Rank: {memory['current_rank']}")
    if memory.get("current_squadron"):
        arc_bits.append(f"Unit: {memory['current_squadron']}")
    arc_bits.append(f"Latest mission ({mission_date}): {result}")
    memory["arc_summary"] = "; ".join(bit for bit in arc_bits if bit)[:280]
    return memory


def generate_and_store_chapter(
    story_input: Dict[str, Any],
    *,
    career_id: str | int,
    model: str = DEFAULT_MODEL,
    api_key: Optional[str] = None,
    provider: str = "openai",
    base_url: Optional[str] = None,
    output_language: str = "en",
) -> Dict[str, Any]:
    story_payload = generate_mission_story(
        story_input,
        model=model,
        api_key=api_key,
        provider=provider,
        base_url=base_url,
        output_language=output_language,
    )
    story_title = _normalize_text(story_payload.get("title"))
    story_text = _normalize_text(story_payload.get("story_text"))
    fallback_memory = story_input.get("narrative_memory", {}) if isinstance(story_input, dict) else {}
    memory = update_narrative_memory_local(story_input, fallback_memory if isinstance(fallback_memory, dict) else None)
    save_story_state(career_id, memory)
    chapter_path = save_story_chapter(
        career_id,
        story_input,
        story_text,
        title=story_title,
        language_code=output_language,
    )
    return {
        "story_title": story_title,
        "story_text": story_text,
        "memory": memory,
        "chapter_path": str(chapter_path),
    }


def generate_and_store_chapter_for(
    source: str,
    entry_id: str | int,
    story_input: Dict[str, Any],
    *,
    model: str = DEFAULT_MODEL,
    api_key: Optional[str] = None,
    provider: str = "openai",
    base_url: Optional[str] = None,
    output_language: str = "en",
) -> Dict[str, Any]:
    story_payload = generate_mission_story(
        story_input,
        model=model,
        api_key=api_key,
        provider=provider,
        base_url=base_url,
        output_language=output_language,
    )
    story_title = _normalize_text(story_payload.get("title"))
    story_text = _normalize_text(story_payload.get("story_text"))
    fallback_memory = story_input.get("narrative_memory", {}) if isinstance(story_input, dict) else {}
    memory = update_narrative_memory_local(story_input, fallback_memory if isinstance(fallback_memory, dict) else None)
    if story_title:
        memory["used_titles"] = _append_unique_limited(memory.get("used_titles") or [], story_title, limit=20)
    chapters_dir = _story_entry_dir(source, entry_id) / "chapters"
    memory["chapters_written"] = len(list(chapters_dir.glob("*.json"))) if chapters_dir.exists() else 0
    save_story_state_for(source, entry_id, memory)
    chapter_path = save_story_chapter_for(
        source,
        entry_id,
        story_input,
        story_text,
        title=story_title,
        language_code=output_language,
    )
    return {
        "story_title": story_title,
        "story_text": story_text,
        "memory": memory,
        "chapter_path": str(chapter_path),
    }


# ---------------------------------------------------------------------------
# Award citations
# ---------------------------------------------------------------------------

# Maps award code → category key.  One code can appear in multiple nations
# (e.g. "pilots_badge") but always resolves to the same category.
_AWARD_CATEGORY_MAP: Dict[str, str] = {
    # --- Germany ---
    "pilots_badge":                     "qualification",
    "iron_cross_2nd":                   "combat",
    "iron_cross_1st":                   "combat",
    "honor_goblet":                     "combat",
    "honor_clasp":                      "combat",
    "german_cross_gold":                "combat",
    "knights_cross":                    "combat",
    "knights_cross_oak_leaves":         "combat",
    "knights_cross_swords":             "combat",
    "knights_cross_diamonds":           "combat",
    "knights_cross_gold_diamonds":      "combat",
    "grand_cross":                      "combat",
    "star_grand_cross":                 "combat",
    "fighters_bronze":                  "flying_clasp",
    "fighters_silver":                  "flying_clasp",
    "fighters_gold":                    "flying_clasp",
    "fighters_gold_clasp":              "flying_clasp",
    "attack_bronze":                    "flying_clasp",
    "attack_silver":                    "flying_clasp",
    "attack_gold":                      "flying_clasp",
    "attack_gold_clasp":                "flying_clasp",
    "attack_heavy_fighters_bronze":     "flying_clasp",
    "attack_heavy_fighters_silver":     "flying_clasp",
    "attack_heavy_fighters_gold":       "flying_clasp",
    "attack_heavy_fighters_gold_clasp": "flying_clasp",
    "bombers_bronze":                   "flying_clasp",
    "bombers_silver":                   "flying_clasp",
    "bomber_gold":                      "flying_clasp",
    "bombers_gold_clasp":               "flying_clasp",
    "transport_bronze":                 "flying_clasp",
    "transport_silver":                 "flying_clasp",
    "transport_gold":                   "flying_clasp",
    "transport_gold_clasp":             "flying_clasp",
    "eastern_front_medal":              "theatre",
    "kuban_shield":                     "theatre",
    "wound_badge_black":                "wound",
    "wound_badge_silver":               "wound",
    "wound_badge_gold":                 "wound",
    # --- Britain ---
    "raf_pilots_badge":                 "qualification",
    "victoria_cross":                   "combat",
    "dso":                              "combat",
    "dso_bar2":                         "combat",
    "dso_bar3":                         "combat",
    "dfc":                              "combat",
    "dfm":                              "combat",
    "AF_cross":                         "combat",
    "AF_cross_2bars":                   "combat",
    "AF_medal":                         "combat",
    "AF_medal_2bars":                   "combat",
    "France_Germany_star":              "theatre",
    "mentioned_in_despatches":          "mention",
    "wound_stripe":                     "wound",
    "wound_stripe_2":                   "wound",
    "wound_stripe_3":                   "wound",
    # --- USA ---
    "medal_of_honor":                   "combat",
    "medal_of_honor_1_oak":             "combat",
    "distinguished_service_cross":      "combat",
    "dsc_1_oak":                        "combat",
    "dsc_2_oak":                        "combat",
    "dsc_3_oak":                        "combat",
    "dsc_4_oak":                        "combat",
    "silver_star":                      "combat",
    "silver_star_1_oak":                "combat",
    "silver_star_2_oak":                "combat",
    "distinguished_flying_cross":       "combat",
    "dfc_1_oak":                        "combat",
    "dfc_2_oak":                        "combat",
    "dfc_3_oak":                        "combat",
    "dfc_4_oak":                        "combat",
    "legion_of_merit":                  "combat",
    "bronze_star":                      "combat",
    "bronze_star_1_oak":                "combat",
    "bronze_star_2_oak":                "combat",
    "air_medal":                        "flying_clasp",
    "air_medal_1_oak":                  "flying_clasp",
    "air_medal_1silver_oak":            "flying_clasp",
    "air_medal_2_oak":                  "flying_clasp",
    "air_medal_3_oak":                  "flying_clasp",
    "air_medal_4_oak":                  "flying_clasp",
    "purple_heart":                     "wound",
    "purple_heart_1_oak":               "wound",
    "purple_heart_2_oak":               "wound",
    "EU_AF_ME_medal":                   "theatre",
    # --- USSR ---
    "hero_soviet_union":                "combat",
    "order_lenin":                      "combat",
    "order_red_banner":                 "combat",
    "order_red_banner_2":               "combat",
    "order_red_banner_3":               "combat",
    "order_red_star":                   "combat",
    "order_patriotic_war_1st":          "combat",
    "order_patriotic_war_2nd":          "combat",
    "order_suvorov":                    "combat",
    "order_nevsky":                     "combat",
    "DSM":                              "combat",
    "medal_battle_merit":               "combat",
    "medal_courage":                    "combat",
    "DFM_Moscow":                       "theatre",
    "DFM_Stalingrad":                   "theatre",
    "DFM_Caucasus":                     "theatre",
    "red_wound_stripe":                 "wound",
    "yellow_wound_stripe":              "wound",
    "air_kill_bonus":                   "kill_bonus",
    "fighter_kill_bonus":               "kill_bonus",
    "bomber_kill_bonus":                "kill_bonus",
    "bomber_kill_bonus1":               "kill_bonus",
    "transport_kill_bonus":             "kill_bonus",
    "transport_ship_kill_bonus":        "kill_bonus",
    "small_ship_kill_bonus":            "kill_bonus",
    "dest_sub_kill_bonus":              "kill_bonus",
    "bonus_5_sorties":                  "sortie_bonus",
    "bonus_15_sorties":                 "sortie_bonus",
    "bonus_25_sorties":                 "sortie_bonus",
    "bonus_40_sorties":                 "sortie_bonus",
}

# Per-category writing guidance injected into the citation prompt.
# Tuple: (category label shown to LLM, specific writing instruction)
_CITATION_GUIDANCE: Dict[str, Tuple[str, str]] = {
    "qualification": (
        "Qualification badge",
        "Write about the pilot's certification as a military aviator and the beginning of active service. "
        "Tone should be proud and ceremonial. You may mention early missions flown if any.",
    ),
    "combat": (
        "Combat decoration",
        "Focus on acts of gallantry, aerial skill, and specific combat achievements. "
        "Aerial victories and missions flown provide factual context. "
        "Vary your language — do not default to generic closings.",
    ),
    "flying_clasp": (
        "Flying/mission clasp",
        "This clasp is awarded for reaching a specific number of combat sorties. "
        "Make sustained dedication and cumulative effort the heart of the citation — "
        "not individual acts of bravery. Aerial victories are secondary context only.",
    ),
    "wound": (
        "Wound badge",
        "This badge is awarded because the pilot was wounded in combat. "
        "The injury and the sacrifice it represents are the primary reason for this award. "
        "Do NOT make aerial victories the main focus. "
        "Acknowledge the wound, the courage shown despite injury, and resilience in service. "
        "Missions and kills may appear briefly as background only.",
    ),
    "theatre": (
        "Campaign/theatre medal",
        "This medal recognises participation in a specific operational theatre or campaign period. "
        "It is awarded for enduring the hardships of that campaign, not for a single act of bravery. "
        "Focus on the pilot's sustained presence and contribution throughout the named campaign. "
        "Do not make aerial victories the primary justification.",
    ),
    "kill_bonus": (
        "Aerial kill milestone award",
        "This award is given for reaching a specific aerial victory count. "
        "Make the kill milestone the centrepiece; describe the combat skill and determination that led to it.",
    ),
    "sortie_bonus": (
        "Sortie milestone award",
        "This award is given for completing a set number of combat sorties. "
        "Centre the citation on cumulative dedication — the sustained effort of repeated combat flying.",
    ),
    "mention": (
        "Mention in Dispatches",
        "Write a brief, measured commendation — one or two sentences only. "
        "Tone should be understated and factual, not heroic.",
    ),
}

_BANNED_PHRASES = (
    "reflecting the highest traditions",
    "significantly contributing to the success",
    "exemplifying the highest ideals",
    "unwavering dedication",
    "unwavering commitment",
    "unwavering courage",
    "indomitable spirit",
    "unyielding devotion",
)


def _get_citation_guidance(award_code: str) -> Tuple[str, str]:
    """Return (category_label, writing_guidance) for a given award code."""
    category = _AWARD_CATEGORY_MAP.get(award_code, "combat")
    return _CITATION_GUIDANCE.get(category, _CITATION_GUIDANCE["combat"])


def load_citations_for(source: str, entry_id: str) -> Dict[str, Any]:
    path = _story_entry_dir(source, entry_id) / "citations.json"
    return _load_json_file(path, {})


def save_citation_for(source: str, entry_id: str, event_key: str, citation_text: str) -> None:
    path = _story_entry_dir(source, entry_id) / "citations.json"
    citations = _load_json_file(path, {})
    citations[event_key] = citation_text
    _save_json_file(path, citations)


def generate_award_citation(
    award_name: str,
    pilot_name: str,
    rank: str,
    country: str,
    date: str,
    kills: int,
    missions: int,
    theatre: str,
    language: str = "en",
    *,
    api_key: str,
    model: str,
    provider: str,
    base_url: str = "",
) -> str:
    language_label = _LANGUAGE_LABELS.get(_normalize_text(language).lower(), "English")
    category_label, category_guidance = _get_citation_guidance(award_name)
    banned = ", ".join(f'"{p}"' for p in _BANNED_PHRASES)
    prompt = (
        f"You are writing a short official military award citation for a World War II pilot.\n\n"
        f"Award category: {category_label}\n"
        f"Writing guidance: {category_guidance}\n\n"
        f"Award: {award_name}\n"
        f"Pilot: {rank} {pilot_name}\n"
        f"Country: {country}\n"
        f"Date: {date}\n"
        f"Combat theatre: {theatre}\n"
        f"Air kills at time of award: {kills}\n"
        f"Missions flown at time of award: {missions}\n\n"
        f"Write a 2-3 sentence citation in {language_label}. "
        f"Use an authentic, formal military style appropriate to the awarding country and era. "
        f"Do not use any of these overused phrases: {banned}. "
        f"Do not use quotation marks or headings. "
        f"Output only the citation text, nothing else."
    )
    client = _get_client(api_key=api_key, base_url=base_url or None)
    response = _create_story_response(
        client,
        provider=provider,
        model=model,
        prompt=prompt,
        max_output_tokens=200,
    )
    return _extract_response_text(response)
