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
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - handled by runtime caller
    OpenAI = None  # type: ignore[assignment]


BASE_DIR = Path(__file__).resolve().parent
HISTORICAL_CONTEXT_DIR = BASE_DIR / "historical_context"
SQUADRON_CONTEXT_FILE = HISTORICAL_CONTEXT_DIR / "squadrons.json"
SQUADRON_ALIASES_FILE = HISTORICAL_CONTEXT_DIR / "squadron_aliases.json"


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


def _iter_squadron_event_items(squadron_context: Any) -> list[str]:
    if not isinstance(squadron_context, dict):
        return []

    lines: list[str] = []

    promotions = squadron_context.get("promotions", [])
    if isinstance(promotions, list):
        for item in promotions[:4]:
            if not isinstance(item, dict):
                continue
            pilot = _normalize_text(item.get("pilot"))
            rank = _normalize_text(item.get("rank"))
            if pilot and rank:
                lines.append(f"{pilot} promoted to {rank}")

    awards = squadron_context.get("awards", [])
    if isinstance(awards, list):
        for item in awards[:4]:
            if not isinstance(item, dict):
                continue
            pilot = _normalize_text(item.get("pilot"))
            award = _normalize_text(item.get("award"))
            if pilot and award:
                lines.append(f"{pilot} received {award}")

    transfers = squadron_context.get("transfers", [])
    if isinstance(transfers, list):
        for item in transfers[:4]:
            if not isinstance(item, dict):
                continue
            pilot = _normalize_text(item.get("pilot"))
            to_squadron = _normalize_text(item.get("to_squadron"))
            if pilot and to_squadron:
                lines.append(f"{pilot} transferred to {to_squadron}")
            elif pilot:
                lines.append(f"{pilot} was transferred")

    kia = squadron_context.get("kia", [])
    if isinstance(kia, list):
        for pilot in [(_normalize_text(v)) for v in kia[:6] if _normalize_text(v)]:
            lines.append(f"{pilot} was KIA")

    mia = squadron_context.get("mia", [])
    if isinstance(mia, list):
        for pilot in [(_normalize_text(v)) for v in mia[:6] if _normalize_text(v)]:
            lines.append(f"{pilot} was MIA")

    wia = squadron_context.get("wia", [])
    if isinstance(wia, list):
        for pilot in [(_normalize_text(v)) for v in wia[:6] if _normalize_text(v)]:
            lines.append(f"{pilot} was wounded")

    return lines


def _story_mentions_squadron_events(story_text: str, squadron_context: Any) -> bool:
    text = _normalize_text(story_text).lower()
    if not text:
        return False

    # Broad marker check.
    if any(token in text for token in ("squadron", "staffel", "eskadr", "эскадр", "wingman")):
        return True

    if not isinstance(squadron_context, dict):
        return False

    # If any referenced pilot name appears, count it as covered.
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
        for pilot in entries:
            p = _normalize_text(pilot).lower()
            if p and p in text:
                return True
    return False


def _enforce_squadron_event_presence(story_input: Dict[str, Any], story_text: str, output_language: str) -> str:
    squadron_context = story_input.get("squadron_context") if isinstance(story_input, dict) else None
    event_lines = _iter_squadron_event_items(squadron_context)
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


def save_story_chapter_for(
    source: str,
    entry_id: str | int,
    mission_context: Dict[str, Any],
    story_text: str,
    *,
    title: str = "",
    language_code: str = "en",
) -> Path:
    chapters = load_story_chapters_for(source, entry_id)
    chapter_index = len(chapters) + 1
    date_str = _normalize_text(mission_context.get("date")) or "unknown-date"
    filename = f"{chapter_index:04d}_{date_str}.json"
    payload = {
        "chapter_index": chapter_index,
        "mission_id": _normalize_text(mission_context.get("mission_id")),
        "date": date_str,
        "title": title,
        "language": _normalize_text(language_code) or "en",
        "story_text": story_text,
        "aircraft": mission_context.get("pilot", {}).get("aircraft", ""),
        "result": mission_context.get("mission", {}).get("result", ""),
    }
    path = _story_entry_dir(source, entry_id) / "chapters" / filename
    _save_json_file(path, payload)
    return path


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


def resolve_historical_context(
    squadron_name: str,
    mission_date: str,
) -> Dict[str, Any]:
    """
    Resolve squadron/date historical context from local JSON files.

    Returns a normalized dict even when no exact match exists so the caller can
    safely pass it to prompt generation.
    """
    squadron_key = resolve_squadron_key(squadron_name)
    data = _load_json_file(SQUADRON_CONTEXT_FILE, {})
    squadron_block = data.get(squadron_key, {})
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
            "country": squadron_block.get("country", ""),
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
        "country": squadron_block.get("country", ""),
        "theatre": _normalize_text(match.get("theatre")),
        "location": _normalize_text(match.get("location")),
        "summary": _normalize_text(match.get("summary")),
        "facts": list(match.get("facts", []) or []),
        "tone_hints": list(match.get("tone_hints", []) or []),
        "forbidden_claims": list(match.get("forbidden_claims", []) or []),
    }


def _extract_notable_events(mission_json: Dict[str, Any]) -> list[str]:
    notable: list[str] = []
    for event in mission_json.get("events", []):
        event_type = _normalize_text(event.get("type"))
        target = _normalize_text(event.get("target"))
        if event_type == "Kill" and target:
            notable.append(f"Destroyed {target}")
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
) -> Dict[str, Any]:
    """
    Build the structured input payload sent to the LLM for one mission chapter.
    """
    player = mission_json.get("player", {})
    summary = mission_json.get("summary", {})
    historical_context = resolve_historical_context(squadron, mission_date)

    mission = {
        "id": str(mission_id),
        "date": mission_date,
        "result": _normalize_text(summary.get("final_state")),
        "duration": _format_duration_for_story(summary.get("flight_duration")),
        "aircraft_damage": summary.get("aircraft_damage", 0),
        "pilot_damage": summary.get("pilot_damage", 0),
        "air_kills": int(summary.get("air_kills_flying", summary.get("air_kills", 0)) or 0),
        "ground_kills": int(summary.get("ground_kills", 0) or 0),
        "naval_kills": int(summary.get("naval_kills", 0) or 0),
        "notable_events": _extract_notable_events(mission_json),
    }

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
    rank: str = "",
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
) -> Dict[str, Any]:
    result = _normalize_text(mission_summary.get("result"))
    duration = _format_duration_for_story(mission_summary.get("duration"))
    air_kills = int(mission_summary.get("air_kills", 0) or 0)
    ground_kills = int(mission_summary.get("ground_kills", 0) or 0)
    naval_kills = int(mission_summary.get("naval_kills", 0) or 0)
    aircraft_damage = mission_summary.get("aircraft_damage", 0)
    pilot_damage = mission_summary.get("pilot_damage", 0)

    return {
        "career_id": str(campaign_id),
        "mission_id": str(mission_id),
        "date": mission_date,
        "pilot": {
            "name": "",
            "last_name": "",
            "rank": _normalize_text(rank),
            "squadron": "",
            "aircraft": _normalize_text(aircraft),
        },
        "mission": {
            "id": str(mission_id),
            "date": mission_date,
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


def _looks_like_report_style_story(text: str) -> bool:
    value = _normalize_text(text)
    if not value:
        return True
    lower = value.lower()
    report_markers = [
        r"\bm\d{3,5}\b",              # mission ids like M3006
        r"\bair_kills\b",
        r"\bground_kills\b",
        r"\bnaval_kills\b",
        r"\baircraft_damage\b",
        r"\bpilot_damage\b",
        r"\bthe day comprised\b",
        r"\bthe record(?:ed)?\b",
    ]
    for pattern in report_markers:
        if re.search(pattern, lower):
            return True
    # Heuristic: explicit metric dump with many numeric separators.
    if lower.count(",") >= 10 and any(token in lower for token in ("meters", "alt", "duration")):
        return True
    return False


def _looks_truncated_story_text(text: str) -> bool:
    value = _normalize_text(text)
    if not value:
        return True
    if len(value.split()) < 40:
        return True
    tail = value[-1]
    if tail in ".!?\"')":
        return False
    # Common clipped endings: unfinished word/sentence at hard cutoff.
    return True


def _create_story_response(
    client: Any,
    *,
    provider: str,
    model: str,
    prompt: str,
    max_output_tokens: int,
) -> Any:
    provider_key = _normalize_text(provider).lower()
    kwargs: Dict[str, Any] = {
        "model": model,
        "input": prompt,
        "max_output_tokens": max_output_tokens,
    }
    if provider_key == "openrouter":
        # OpenRouter often expects max_tokens via provider-native payload.
        kwargs["extra_body"] = {"max_tokens": max_output_tokens}
    try:
        return client.responses.create(**kwargs)
    except TypeError:
        # Fallback for providers that reject one of these params.
        return client.responses.create(model=model, input=prompt)


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
    chapter_scope = story_input.get("chapter_scope", {}) if isinstance(story_input, dict) else {}
    missions_in_chapter = 1
    if isinstance(chapter_scope, dict):
        try:
            missions_in_chapter = max(1, int(chapter_scope.get("missions_in_chapter", 1) or 1))
        except (TypeError, ValueError):
            missions_in_chapter = 1

    if missions_in_chapter <= 1:
        paragraph_rule = "Write exactly 3 paragraphs."
        word_target = "Target 180-280 words."
        max_output_tokens = 700
    elif missions_in_chapter == 2:
        paragraph_rule = "Write exactly 3 paragraphs."
        word_target = "Target 240-360 words."
        max_output_tokens = 950
    else:
        paragraph_rule = "Write exactly 4 paragraphs."
        word_target = "Target 320-500 words."
        max_output_tokens = 1300

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
        "- Use only the supplied facts.\n"
        "- Do not invent awards, promotions, injuries, victories, locations, or commanders.\n"
        "- Keep the story historically grounded and atmospheric.\n"
        "- If historical_context.summary or historical_context.facts are present, integrate them naturally.\n"
        "- If mission_progression.promotion is non-empty, explicitly mention the promotion in the chapter.\n"
        "- If mission_progression.awards contains one or more entries, explicitly mention those award(s) in the chapter.\n"
        "- If honors_context.promotion.fact is present, include one short historical note tied to that promotion.\n"
        "- If honors_context.awards has facts, include at least one short factual note tied to the award(s) received.\n"
        "- Do not claim a promotion or award for this mission when mission_progression says none occurred.\n"
        "- If mission_progression has no promotion/awards, do not restate old awards unless clearly relevant to this mission.\n"
        "- Treat squadron_context as factual.\n"
        "- Mention at least one squadron_context item when any are present.\n"
        "- Do not invent squadron-member outcomes not present in squadron_context.\n"
        "- Never output internal mission IDs (e.g., M3010, M3011) in the final text.\n"
        "- Mention sortie count naturally (e.g., 'two sorties that day') without technical labels.\n"
        "- Show progression across the day: setup, action, aftermath.\n"
        "- Keep tone restrained and military-historical, not cinematic fantasy.\n"
        "- Avoid bureaucratic phrases like 'the record shows' or 'on record'.\n"
        "- If no promotions/awards/squadron events occurred, omit those topics naturally; do not explicitly list 'none'.\n"
        "- Do not write debrief-style sentences that dump multiple metrics in one line.\n"
        "- If campaign_context.background_excerpt is present, use it as atmosphere only.\n"
        "- Do not quote long chunks from campaign_context.background_excerpt verbatim.\n"
        "- If chapter_scope.scope is 'day', narrate one cohesive day arc across all listed missions in chapter_scope.mission_ids.\n"
        "- If mission duration is mentioned, use only hours and minutes (no seconds).\n"
        f"- Write the entire chapter in {language_label}.\n"
        f"- {paragraph_rule}\n"
        f"- {word_target}\n"
        "- Create a short chapter title (4-8 words).\n"
        "- Return valid JSON only with keys: title, story_text.\n\n"
        "Input JSON:\n"
        f"{json.dumps(story_input, ensure_ascii=False, indent=2)}"
    )
    response = _create_story_response(
        client,
        provider=provider,
        model=model,
        prompt=prompt,
        max_output_tokens=max_output_tokens,
    )

    raw_text = _extract_response_text(response)
    payload = _extract_json_object(raw_text)
    if payload:
        title = _normalize_text(payload.get("title"))
        story_text = _normalize_text(payload.get("story_text"))
        if story_text and not _looks_like_report_style_story(story_text) and not _looks_truncated_story_text(story_text):
            story_text = _enforce_squadron_event_presence(story_input, story_text, output_language)
            return {
                "title": title,
                "story_text": story_text,
            }

    fallback_text = _normalize_text(raw_text)
    if _looks_like_invalid_story_text(fallback_text) or _looks_like_report_style_story(fallback_text) or _looks_truncated_story_text(fallback_text):
        # One retry with plain-text fallback prompt (no JSON contract),
        # then wrap into the expected payload shape.
        retry_prompt = (
            "Write one cohesive wartime chapter using only the supplied JSON facts.\n"
            "Return plain text only, 3-4 paragraphs, no JSON, no markdown.\n"
            "Do not use mission IDs (e.g., M3006). Do not write in report/logbook style.\n"
            "Integrate facts into narrative prose and avoid stat-dump phrasing.\n\n"
            "Input JSON:\n"
            f"{json.dumps(story_input, ensure_ascii=False, indent=2)}"
        )
        retry_response = _create_story_response(
            client,
            provider=provider,
            model=model,
            prompt=retry_prompt,
            max_output_tokens=max_output_tokens,
        )
        fallback_text = _normalize_text(_extract_response_text(retry_response))
        if _looks_like_invalid_story_text(fallback_text) or _looks_like_report_style_story(fallback_text) or _looks_truncated_story_text(fallback_text):
            raise ValueError("Story model returned empty content.")
    return {
        "title": "",
        "story_text": _enforce_squadron_event_presence(story_input, fallback_text, output_language),
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
    _ = provider  # reserved for provider-specific behavior/extensions
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
    response = client.responses.create(model=model, input=prompt)
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
    }

    pilot = story_input.get("pilot", {}) if isinstance(story_input, dict) else {}
    mission = story_input.get("mission", {}) if isinstance(story_input, dict) else {}
    campaign_context = story_input.get("campaign_context", {}) if isinstance(story_input, dict) else {}
    mission_progression = story_input.get("mission_progression", {}) if isinstance(story_input, dict) else {}

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
    try:
        memory = update_narrative_memory(
            story_input,
            story_text,
            model=model,
            api_key=api_key,
            provider=provider,
            base_url=base_url,
        )
    except Exception as exc:
        LOGGER.warning("Narrative memory update failed; keeping previous memory: %s", exc)
        memory = fallback_memory if isinstance(fallback_memory, dict) else {}
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
    try:
        memory = update_narrative_memory(
            story_input,
            story_text,
            model=model,
            api_key=api_key,
            provider=provider,
            base_url=base_url,
        )
    except Exception as exc:
        LOGGER.warning("Narrative memory update failed; keeping previous memory: %s", exc)
        memory = fallback_memory if isinstance(fallback_memory, dict) else {}
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
