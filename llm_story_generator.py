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
import os
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

DEFAULT_MODEL = "gpt-5-mini"


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


def _story_career_dir(career_id: str | int) -> Path:
    return STORY_DATA_DIR / str(career_id)


def load_or_create_story_state(career_id: str | int) -> Dict[str, Any]:
    path = _story_career_dir(career_id) / "memory.json"
    if path.exists():
        return _load_json_file(path, {})
    return {
        "career_id": str(career_id),
        "current_rank": "",
        "current_squadron": "",
        "arc_summary": "",
        "key_milestones": [],
        "recurring_themes": [],
        "recent_events": [],
    }


def save_story_state(career_id: str | int, memory: Dict[str, Any]) -> None:
    _save_json_file(_story_career_dir(career_id) / "memory.json", memory)


def load_story_chapters(career_id: str | int) -> list[Dict[str, Any]]:
    chapters_dir = _story_career_dir(career_id) / "chapters"
    if not chapters_dir.exists():
        return []
    chapters = []
    for path in sorted(chapters_dir.glob("*.json")):
        payload = _load_json_file(path, None)
        if isinstance(payload, dict):
            chapters.append(payload)
    return chapters


def save_story_chapter(
    career_id: str | int,
    mission_context: Dict[str, Any],
    story_text: str,
    title: str = "",
) -> Path:
    chapters = load_story_chapters(career_id)
    chapter_index = len(chapters) + 1
    date_str = _normalize_text(mission_context.get("date")) or "unknown-date"
    filename = f"{chapter_index:04d}_{date_str}.json"
    payload = {
        "chapter_index": chapter_index,
        "mission_id": _normalize_text(mission_context.get("mission_id")),
        "date": date_str,
        "title": title,
        "story_text": story_text,
        "aircraft": mission_context.get("pilot", {}).get("aircraft", ""),
        "result": mission_context.get("mission", {}).get("result", ""),
    }
    path = _story_career_dir(career_id) / "chapters" / filename
    _save_json_file(path, payload)
    return path


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
    rank: str = "",
    awards: Optional[Iterable[str]] = None,
    promotion: Optional[str] = None,
    mission_awards: Optional[Iterable[str]] = None,
    mission_promotion: Optional[str] = None,
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
        "duration": _normalize_text(summary.get("flight_duration")),
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
        "historical_context": historical_context,
        "narrative_memory": narrative_memory or {},
    }


def _get_client(api_key: Optional[str] = None) -> Any:
    if OpenAI is None:
        raise RuntimeError("OpenAI SDK is not installed. Run: py -3 -m pip install openai")
    resolved_api_key = _normalize_text(api_key) or os.environ.get("OPENAI_API_KEY")
    if not resolved_api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")
    return OpenAI(api_key=resolved_api_key, timeout=90.0)


def generate_mission_story(
    story_input: Dict[str, Any],
    *,
    model: str = DEFAULT_MODEL,
    api_key: Optional[str] = None,
) -> str:
    client = _get_client(api_key=api_key)
    prompt = (
        "Write the next chapter of a continuous wartime storybook.\n\n"
        "Rules:\n"
        "- Keep continuity with the previous narrative memory.\n"
        "- Use only the supplied facts.\n"
        "- Do not invent awards, promotions, injuries, victories, locations, or commanders.\n"
        "- Keep the story historically grounded and atmospheric.\n"
        "- Integrate the squadron's real historical context for the date naturally.\n"
        "- If mission_progression.promotion is non-empty, explicitly mention the promotion in the chapter.\n"
        "- If mission_progression.awards contains one or more entries, explicitly mention those award(s) in the chapter.\n"
        "- Do not claim a promotion or award for this mission when mission_progression says none occurred.\n"
        "- Write 250-500 words.\n\n"
        "Input JSON:\n"
        f"{json.dumps(story_input, ensure_ascii=False, indent=2)}"
    )
    response = client.responses.create(model=model, input=prompt)
    return response.output_text.strip()


def update_narrative_memory(
    story_input: Dict[str, Any],
    story_text: str,
    *,
    model: str = DEFAULT_MODEL,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    client = _get_client(api_key=api_key)
    prompt = (
        "Update the pilot's narrative memory after this mission.\n\n"
        "Rules:\n"
        "- Keep it compact and factual.\n"
        "- Preserve continuity.\n"
        "- Do not invent facts.\n"
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
    payload = json.loads(response.output_text)
    if not isinstance(payload, dict):
        raise ValueError("Narrative memory response was not a JSON object")
    return payload


def generate_and_store_chapter(
    story_input: Dict[str, Any],
    *,
    career_id: str | int,
    model: str = DEFAULT_MODEL,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    story_text = generate_mission_story(story_input, model=model, api_key=api_key)
    memory = update_narrative_memory(
        story_input,
        story_text,
        model=model,
        api_key=api_key,
    )
    save_story_state(career_id, memory)
    chapter_path = save_story_chapter(career_id, story_input, story_text)
    return {
        "story_text": story_text,
        "memory": memory,
        "chapter_path": str(chapter_path),
    }
