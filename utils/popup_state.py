import json
import shutil
from pathlib import Path
from typing import Dict, List

from utils.logging import get_logger, log_message

logger = get_logger(__name__)

def load_popup_seen(path: Path) -> Dict[str, List[str]]:
    """
    Load already-shown popup event keys. Returns dict: {campaign_name: [keys...]}.

    ✅ IMPROVED: Better error handling and validation
    """
    if not path.exists():
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # ✅ Validate structure
        if not isinstance(data, dict):
            log_message(logger, "[popups] Warning: Invalid popup state structure, resetting")
            return {}

        # ✅ Validate each campaign's data
        validated_data: Dict[str, List[str]] = {}
        for campaign_name, events in data.items():
            if isinstance(events, list):
                validated_data[campaign_name] = events
            else:
                log_message(logger, f"[popups] Warning: Invalid events for '{campaign_name}', skipping")

        return validated_data

    except json.JSONDecodeError as e:
        log_message(logger, f"[popups] ERROR: Corrupted popup state file: {e}")
        log_message(logger, "[popups] Creating backup and resetting...")

        # ✅ Backup corrupted file
        backup_path = path.with_suffix('.corrupted')
        try:
            shutil.copy2(path, backup_path)
            log_message(logger, f"[popups] Corrupted file backed up to: {backup_path}")
        except Exception:
            pass

        return {}

    except Exception as e:
        log_message(logger, f"[popups] Warning: Could not load popup state: {e}")
        return {}


def save_popup_seen(path: Path, data: Dict[str, List[str]]) -> None:
    """
    Save already-shown popup event keys.

    ✅ IMPROVED: Uses atomic write to prevent corruption

    How atomic write works:
    1. Write to temporary file
    2. If successful, replace original file in one operation
    3. If crash happens during write, original file stays intact
    """
    try:
        # ✅ Validate input
        if not isinstance(data, dict):
            log_message(
                logger,
                "[popups] ERROR: Invalid data type for popup state (expected dict, got "
                f"{type(data).__name__})",
            )
            return

        # ✅ FIX: Write to temporary file first (atomic write pattern)
        tmp_file = path.with_suffix('.tmp')

        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True, ensure_ascii=False)

        # ✅ Atomic replace: if we got here, the write was successful
        # This is atomic on most filesystems (POSIX rename, Windows MoveFileEx)
        tmp_file.replace(path)

        # Success - no print needed (too verbose)

    except Exception as e:
        log_message(logger, f"[popups] ERROR: Could not save popup state: {e}")

        # ✅ Cleanup temp file if it exists
        try:
            tmp_file = path.with_suffix('.tmp')
            if tmp_file.exists():
                tmp_file.unlink()
        except Exception:
            pass


def make_event_key(ev: dict) -> str:
    """
    Build a stable key for an event so we can detect if it was already shown as a popup.
    Expected fields (from campaign_events.json structure): type, rank/name, mission, date
    """
    ev_type = str(ev.get("type", "")).strip().lower()
    mission = str(ev.get("mission", "")).strip()
    date = str(ev.get("date", "")).strip()

    if ev_type == "promotion":
        rank = str(ev.get("rank", "")).strip()
        return f"promotion|{rank}|{mission}|{date}"

    if ev_type == "award":
        name = str(ev.get("name", "")).strip()
        return f"award|{name}|{mission}|{date}"

    # fallback for unknown event types
    return f"{ev_type}|{mission}|{date}"
