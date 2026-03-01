"""
Other incidences loader for the Career Service Record.

Queries cp.db for three new event types and returns normalised entry dicts
suitable for JSON serialisation and frontend rendering:

    RECOVERY  — collapsed consecutive medical-leave days (event.type = 13)
    COMMAND   — commander/leadership appointment     (event.type =  7)
    TRANSFER  — squadron transfer                    (event.type =  9)

All queries enforce both careerId AND pilotId filters so that events from
other career chains (even with the same pilot id) are never included.

Entry shapes
------------
RECOVERY:
    {
        "type":          "RECOVERY",
        "start_date":    "YYYY-MM-DD",
        "end_date":      "YYYY-MM-DD",
        "duration_days": int,        # inclusive
        "sort_key":      "YYYY-MM-DD",  # = start_date
    }

COMMAND:
    {
        "type":     "COMMAND",
        "date":     "YYYY-MM-DD",
        "sort_key": "YYYY-MM-DD",
    }

TRANSFER:
    {
        "type":          "TRANSFER",
        "date":          "YYYY-MM-DD",
        "squadron_name": str,   # resolved display name or "Squadron <configId>"
        "sort_key":      "YYYY-MM-DD",
    }
"""

import logging
from datetime import date, timedelta
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# Event type constants
_TYPE_RECOVERY = 13
_TYPE_COMMAND = 7
_TYPE_TRANSFER = 9


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

def _parse_iso(raw) -> Optional[date]:
    """
    Parse an event.date value to a Python date object.

    Handles:
        - str "YYYY-MM-DD" or "YYYY.MM.DD" (dots normalised)
        - str with time component "YYYY-MM-DDTHH:MM:SS" (truncated)
        - int / float unix timestamp (converted via date.fromtimestamp)
        - None → None
    """
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        try:
            from datetime import datetime
            return datetime.fromtimestamp(raw).date()
        except (OSError, OverflowError, ValueError):
            return None
    if isinstance(raw, str):
        normalised = raw.replace(".", "-").split("T")[0][:10]
        try:
            return date.fromisoformat(normalised)
        except ValueError:
            return None
    return None


def _iso(d: date) -> str:
    return d.isoformat()


# ---------------------------------------------------------------------------
# Recovery range collapsing
# ---------------------------------------------------------------------------

def collapse_recovery_ranges(date_strings: List[str]) -> List[Dict]:
    """
    Collapse a list of ISO date strings into consecutive ranges.

    Dates that are exactly one day apart are merged into a single range.
    A gap of 2 or more days starts a new range.

    Args:
        date_strings: List of "YYYY-MM-DD" strings (need not be pre-sorted).

    Returns:
        List of range dicts, sorted by start_date ascending:
            {
                "start_date":    "YYYY-MM-DD",
                "end_date":      "YYYY-MM-DD",
                "duration_days": int,           # inclusive
            }

    Example:
        Input:  ['1942-08-01', '1942-08-02', '1942-08-04']
        Output: [
            {"start_date": "1942-08-01", "end_date": "1942-08-02", "duration_days": 2},
            {"start_date": "1942-08-04", "end_date": "1942-08-04", "duration_days": 1},
        ]
    """
    if not date_strings:
        return []

    parsed: List[date] = []
    for s in date_strings:
        d = _parse_iso(s)
        if d is not None:
            parsed.append(d)

    if not parsed:
        return []

    parsed.sort()

    ranges: List[Dict] = []
    range_start = parsed[0]
    range_end = parsed[0]

    for d in parsed[1:]:
        if d == range_end + timedelta(days=1):
            range_end = d
        else:
            ranges.append(_make_range(range_start, range_end))
            range_start = d
            range_end = d

    ranges.append(_make_range(range_start, range_end))
    return ranges


def _make_range(start: date, end: date) -> Dict:
    return {
        "start_date":    _iso(start),
        "end_date":      _iso(end),
        "duration_days": (end - start).days + 1,
    }


# ---------------------------------------------------------------------------
# Main loader
# ---------------------------------------------------------------------------

def load_other_incidences(
    db,
    career_id: int,
    player_id: int,
    resolve_squadron_fn: Callable[[int, int], Optional[str]],
) -> List[Dict]:
    """
    Load and normalise 'Other Incidences' entries for one career segment.

    Args:
        db:                  CareerDatabase instance.
        career_id:           career.id of the theatre segment being queried.
        player_id:           career.playerId for that segment.
        resolve_squadron_fn: Callable(career_id, config_id) → display name or None.
                             When None, the entry falls back to "Squadron <configId>".

    Returns:
        List of normalised entry dicts, sorted ascending by sort_key.
    """
    entries: List[Dict] = []

    # ------------------------------------------------------------------ #
    # Recovery ranges (event.type = 13)
    # ------------------------------------------------------------------ #
    try:
        recovery_rows = db.get_incidence_events_for_career(
            career_id, player_id, [_TYPE_RECOVERY]
        )
        date_strings = [str(row["date"]) for row in recovery_rows if row["date"] is not None]
        for r in collapse_recovery_ranges(date_strings):
            entries.append({
                "type":          "RECOVERY",
                "start_date":    r["start_date"],
                "end_date":      r["end_date"],
                "duration_days": r["duration_days"],
                "sort_key":      r["start_date"],
            })
    except Exception as exc:
        logger.warning(
            "Failed to load recovery events for careerId=%d pilotId=%d: %s",
            career_id, player_id, exc,
        )

    # ------------------------------------------------------------------ #
    # Commander appointments (event.type = 7)
    # ------------------------------------------------------------------ #
    try:
        command_rows = db.get_incidence_events_for_career(
            career_id, player_id, [_TYPE_COMMAND]
        )
        for row in command_rows:
            d = _parse_iso(row["date"])
            if d is None:
                logger.debug("COMMAND event has unparseable date; skipping")
                continue
            iso = _iso(d)
            entries.append({
                "type":     "COMMAND",
                "date":     iso,
                "sort_key": iso,
            })
    except Exception as exc:
        logger.warning(
            "Failed to load command events for careerId=%d pilotId=%d: %s",
            career_id, player_id, exc,
        )

    # ------------------------------------------------------------------ #
    # Squadron transfers (event.type = 9)
    # ------------------------------------------------------------------ #
    try:
        transfer_rows = db.get_incidence_events_for_career(
            career_id, player_id, [_TYPE_TRANSFER]
        )
        for row in transfer_rows:
            d = _parse_iso(row["date"])
            if d is None:
                logger.debug("TRANSFER event has unparseable date; skipping")
                continue

            config_id = _safe_int(row, "squadronId")
            if config_id:
                display_name = resolve_squadron_fn(career_id, config_id)
            else:
                display_name = None

            squadron_name = display_name if display_name else f"Squadron {config_id or '?'}"

            iso = _iso(d)
            entries.append({
                "type":          "TRANSFER",
                "date":          iso,
                "squadron_name": squadron_name,
                "sort_key":      iso,
            })
    except Exception as exc:
        logger.warning(
            "Failed to load transfer events for careerId=%d pilotId=%d: %s",
            career_id, player_id, exc,
        )

    entries.sort(key=lambda e: e["sort_key"])
    return entries


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _safe_int(row, column: str) -> int:
    """Read an int from a sqlite3.Row, returning 0 on any error."""
    try:
        val = row[column]
        return int(val) if val is not None else 0
    except (IndexError, KeyError, TypeError, ValueError):
        return 0
