"""
Other incidences loader for the Career Service Record.

Queries cp.db for event types and returns normalised entry dicts suitable for
JSON serialisation and frontend rendering:

    RECOVERY        — collapsed consecutive medical-leave days (event.type = 13)
    COMMAND         — commander/leadership appointment     (event.type =  7)
    SQUADRON_CHANGE — squadron change with from/to names   (event.type = 10)

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
        "source_mission_id": int | None,
        "sort_key":      "YYYY-MM-DD",  # = start_date
    }

COMMAND:
    {
        "type":     "COMMAND",
        "date":     "YYYY-MM-DD",
        "source_mission_id": int | None,
        "sort_key": "YYYY-MM-DD",
    }

SQUADRON_CHANGE:
    {
        "type":          "SQUADRON_CHANGE",
        "date":          "YYYY-MM-DD",
        "old_squadron":  str,   # resolved display name of previous squadron
        "new_squadron":  str,   # resolved display name of new squadron (event.squadronId)
        "source_mission_id": int | None,
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
_TYPE_SQUADRON_CHANGE = 10


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


def _refine_ranges_with_sortie(ranges: List[Dict], db, pilot_ids) -> List[Dict]:
    """
    Refine each recovery range by looking up the preceding status=4 sortie.

    In Rapid Mode the game may skip calendar days so only the final recovery
    day is written as a type-13 event.  collapse_recovery_ranges() then
    produces a 1-day range with duration_days=1 even though the real injury
    lasted several days.

    For each range we search backwards for the most recent injured sortie
    (status=4) that occurred before the last recovery day.  If found:
        start_date    = sortie date  (day the pilot was shot down/wounded)
        end_date      = last type-13 date  (unchanged)
        duration_days = (end - start).days   # no +1: injury day to last recovery day

    In Realistic Mode the result is identical to the type-13 count because:
        last_recovery_date - injury_date == count(consecutive type-13 days)

    If no status=4 sortie is found the original range is kept unchanged.
    """
    if isinstance(pilot_ids, int):
        pilot_ids = [pilot_ids]

    refined = []
    for r in ranges:
        last_recovery = _parse_iso(r["end_date"])
        if last_recovery is None:
            refined.append(r)
            continue

        # Convert ISO end_date ("1941-11-30") to the dot-format used in the
        # sortie table ("1941.11.30 00:00:00") so SQLite string comparison
        # works correctly.  Sorties carry a time component; appending
        # " 00:00:00" means the last recovery day itself is excluded while
        # any same-day sortie with a real timestamp would still be caught
        # (injury sorties always precede the first recovery day).
        before_date_db = r["end_date"].replace("-", ".") + " 00:00:00"
        sortie_row = db.get_injured_sortie_before(pilot_ids, before_date_db)
        if sortie_row is None:
            logger.debug(
                "No status=4 sortie found before %s; keeping type-13 count (%d days)",
                before_date_db, r["duration_days"],
            )
            refined.append(r)
            continue

        injury_date = _parse_iso(sortie_row["date"])
        if injury_date is None or injury_date >= last_recovery:
            logger.debug(
                "Sortie date %s is not before recovery end %s; skipping refinement",
                sortie_row["date"], r["end_date"],
            )
            refined.append(r)
            continue

        duration = (last_recovery - injury_date).days
        logger.debug(
            "Refined recovery range: injury=%s last_recovery=%s duration=%d days "
            "(was %d from type-13 count)",
            _iso(injury_date), r["end_date"], duration, r["duration_days"],
        )
        refined.append({
            "start_date":    _iso(injury_date),
            "end_date":      r["end_date"],
            "duration_days": duration,
            "source_mission_id": int(sortie_row["missionId"]) if sortie_row["missionId"] is not None and int(sortie_row["missionId"]) > 0 else None,
        })
    return refined


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
        ranges = collapse_recovery_ranges(date_strings)
        ranges = _refine_ranges_with_sortie(ranges, db, player_id)
        for r in ranges:
            entries.append({
                "type":          "RECOVERY",
                "start_date":    r["start_date"],
                "end_date":      r["end_date"],
                "duration_days": r["duration_days"],
                "source_mission_id": r.get("source_mission_id"),
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
            config_id = _safe_int(row, "squadronId")
            squadron = None
            if config_id:
                display = resolve_squadron_fn(career_id, config_id)
                squadron = display if display else f"Squadron {config_id}"
            _mid = _safe_int(row, "missionId")
            entries.append({
                "type":      "COMMAND",
                "date":      iso,
                "squadron":  squadron,
                "source_mission_id": _mid if _mid > 0 else None,
                "sort_key":  iso,
            })
    except Exception as exc:
        logger.warning(
            "Failed to load command events for careerId=%d pilotId=%d: %s",
            career_id, player_id, exc,
        )

    # ------------------------------------------------------------------ #
    # Squadron change events (event.type = 10)
    # new squadron = event.squadronId of the type-10 event
    # old squadron = squadronId of the most recent prior event that carries one
    # ------------------------------------------------------------------ #
    try:
        squadron_change_rows = db.get_incidence_events_for_career(
            career_id, player_id, [_TYPE_SQUADRON_CHANGE]
        )
        # All events with a non-null squadronId, ordered by date — used to
        # determine which squadron the pilot was in just before each change.
        squadron_history = db.get_events_with_squadron_for_career(career_id, player_id)

        for row in squadron_change_rows:
            d = _parse_iso(row["date"])
            if d is None:
                logger.debug("SQUADRON_CHANGE event has unparseable date; skipping")
                continue

            # New squadron: from the type-10 event itself
            new_config_id = _safe_int(row, "squadronId")
            if new_config_id:
                new_display = resolve_squadron_fn(career_id, new_config_id)
                new_squadron = new_display if new_display else f"Squadron {new_config_id}"
            else:
                new_squadron = "?"

            # Old squadron: most recent event with a non-null squadronId
            # that occurred strictly before this event's date
            old_config_id = 0
            for h in reversed(squadron_history):
                h_date = _parse_iso(h["date"])
                if h_date is not None and h_date < d:
                    cid = _safe_int(h, "squadronId")
                    if cid:
                        old_config_id = cid
                        break

            if old_config_id:
                old_display = resolve_squadron_fn(career_id, old_config_id)
                old_squadron = old_display if old_display else f"Squadron {old_config_id}"
            else:
                old_squadron = "?"

            iso = _iso(d)
            _mid = _safe_int(row, "missionId")
            entries.append({
                "type":         "SQUADRON_CHANGE",
                "date":         iso,
                "old_squadron": old_squadron,
                "new_squadron": new_squadron,
                "source_mission_id": _mid if _mid > 0 else None,
                "sort_key":     iso,
            })
    except Exception as exc:
        logger.warning(
            "Failed to load squadron change events for careerId=%d pilotId=%d: %s",
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
