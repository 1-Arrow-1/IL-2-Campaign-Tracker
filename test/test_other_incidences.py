"""
Tests for Other Incidences (career service record).

Coverage:
    Unit  — collapse_recovery_ranges() edge-cases and spec example
    Integration-style — load_other_incidences() with in-memory SQLite
                        verifying strict careerId + pilotId filtering
"""

import sqlite3
import unittest
from typing import Dict, List, Optional

from campaign_service_record.career.other_incidences import (
    collapse_recovery_ranges,
    load_other_incidences,
)


# ---------------------------------------------------------------------------
# Helpers – in-memory SQLite stub
# ---------------------------------------------------------------------------

_CREATE_EVENT = """
CREATE TABLE event (
    id         INTEGER PRIMARY KEY,
    careerId   INTEGER NOT NULL,
    pilotId    INTEGER NOT NULL,
    type       INTEGER NOT NULL,
    date       TEXT,
    squadronId INTEGER,
    isDeleted  INTEGER NOT NULL DEFAULT 0
)
"""

_CREATE_SQUADRON = """
CREATE TABLE squadron (
    id       INTEGER PRIMARY KEY,
    careerId INTEGER NOT NULL,
    configId INTEGER NOT NULL
)
"""


def _make_db(rows: List[Dict]):
    """
    Build an in-memory CareerDatabase stub containing the given event rows.

    Each dict should have keys matching the event table columns.
    Returns a stub object whose get_incidence_events_for_career() reads from
    the in-memory SQLite without needing a real cp.db file.
    """

    class _StubDB:
        def __init__(self, conn: sqlite3.Connection):
            self._conn = conn
            self._conn.row_factory = sqlite3.Row

        def get_incidence_events_for_career(
            self, career_id: int, player_id: int, types: List[int]
        ) -> List[sqlite3.Row]:
            placeholders = ",".join("?" * len(types))
            cursor = self._conn.execute(
                f"SELECT * FROM event "
                f"WHERE careerId = ? AND pilotId = ? AND type IN ({placeholders}) "
                f"AND isDeleted = 0 ORDER BY date ASC",
                [career_id, player_id, *types],
            )
            return cursor.fetchall()

    conn = sqlite3.connect(":memory:")
    conn.execute(_CREATE_EVENT)
    conn.execute(_CREATE_SQUADRON)
    for row in rows:
        conn.execute(
            "INSERT INTO event (id, careerId, pilotId, type, date, squadronId, isDeleted) "
            "VALUES (:id, :careerId, :pilotId, :type, :date, :squadronId, :isDeleted)",
            {
                "id":         row.get("id", 1),
                "careerId":   row["careerId"],
                "pilotId":    row["pilotId"],
                "type":       row["type"],
                "date":       row.get("date"),
                "squadronId": row.get("squadronId"),
                "isDeleted":  row.get("isDeleted", 0),
            },
        )
    conn.commit()
    return _StubDB(conn)


def _no_resolve(_cid: int, _cfgid: int) -> Optional[str]:
    """Squadron resolver that always returns None (triggers fallback)."""
    return None


# ---------------------------------------------------------------------------
# Unit tests: collapse_recovery_ranges
# ---------------------------------------------------------------------------

class TestCollapseRecoveryRanges(unittest.TestCase):

    def test_spec_example(self):
        """Spec example: [01, 02, 04] → two ranges."""
        result = collapse_recovery_ranges(
            ["1942-08-01", "1942-08-02", "1942-08-04"]
        )
        self.assertEqual(len(result), 2)

        first = result[0]
        self.assertEqual(first["start_date"], "1942-08-01")
        self.assertEqual(first["end_date"],   "1942-08-02")
        self.assertEqual(first["duration_days"], 2)

        second = result[1]
        self.assertEqual(second["start_date"], "1942-08-04")
        self.assertEqual(second["end_date"],   "1942-08-04")
        self.assertEqual(second["duration_days"], 1)

    def test_empty_input(self):
        self.assertEqual(collapse_recovery_ranges([]), [])

    def test_single_day(self):
        result = collapse_recovery_ranges(["1943-01-15"])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["start_date"], "1943-01-15")
        self.assertEqual(result[0]["end_date"],   "1943-01-15")
        self.assertEqual(result[0]["duration_days"], 1)

    def test_all_consecutive(self):
        result = collapse_recovery_ranges(
            ["1942-09-01", "1942-09-02", "1942-09-03"]
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["duration_days"], 3)

    def test_no_consecutive(self):
        """Every date is isolated → each is its own 1-day range."""
        result = collapse_recovery_ranges(
            ["1942-01-01", "1942-01-03", "1942-01-05"]
        )
        self.assertEqual(len(result), 3)
        self.assertTrue(all(r["duration_days"] == 1 for r in result))

    def test_input_unsorted(self):
        """Dates need not be supplied in order."""
        result = collapse_recovery_ranges(
            ["1942-08-04", "1942-08-01", "1942-08-02"]
        )
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["start_date"], "1942-08-01")
        self.assertEqual(result[1]["start_date"], "1942-08-04")

    def test_month_boundary(self):
        """Range spanning month boundary collapses correctly."""
        result = collapse_recovery_ranges(
            ["1942-01-30", "1942-01-31", "1942-02-01"]
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["start_date"], "1942-01-30")
        self.assertEqual(result[0]["end_date"],   "1942-02-01")
        self.assertEqual(result[0]["duration_days"], 3)


# ---------------------------------------------------------------------------
# Integration-style tests: careerId + pilotId filtering
# ---------------------------------------------------------------------------

class TestCareerIdFiltering(unittest.TestCase):
    """
    Verify that load_other_incidences() returns only events matching BOTH
    careerId AND pilotId, even when the same pilotId appears in other careers.
    """

    def setUp(self):
        # PILOT 10 appears in career 1 (ours) and career 99 (another pilot's career).
        # PILOT 99 appears in career 1 (not our player).
        # We query career_id=1, player_id=10 → must get only the first two rows.
        self._db = _make_db([
            # Our player in our career → include
            {"id": 1, "careerId": 1, "pilotId": 10, "type": 13, "date": "1942-08-01"},
            {"id": 2, "careerId": 1, "pilotId": 10, "type": 13, "date": "1942-08-02"},
            # Same pilotId but different careerId → must be excluded
            {"id": 3, "careerId": 99, "pilotId": 10, "type": 13, "date": "1942-09-01"},
            # Different pilotId in our careerId → must be excluded
            {"id": 4, "careerId": 1,  "pilotId": 99, "type": 13, "date": "1942-10-01"},
        ])

    def test_only_correct_career_and_pilot_returned(self):
        results = load_other_incidences(self._db, career_id=1, player_id=10, resolve_squadron_fn=_no_resolve)
        self.assertEqual(len(results), 1, "Expected exactly one collapsed RECOVERY range")
        rec = results[0]
        self.assertEqual(rec["type"], "RECOVERY")
        self.assertEqual(rec["start_date"], "1942-08-01")
        self.assertEqual(rec["end_date"],   "1942-08-02")
        self.assertEqual(rec["duration_days"], 2)

    def test_isdeleted_rows_excluded(self):
        """Soft-deleted events must not appear."""
        db = _make_db([
            {"id": 1, "careerId": 1, "pilotId": 10, "type": 7, "date": "1942-11-01", "isDeleted": 1},
        ])
        results = load_other_incidences(db, career_id=1, player_id=10, resolve_squadron_fn=_no_resolve)
        self.assertEqual(results, [])


class TestCommandAndTransferEntries(unittest.TestCase):
    """Basic smoke-tests for COMMAND and TRANSFER type entries."""

    def test_command_entry(self):
        db = _make_db([
            {"id": 1, "careerId": 5, "pilotId": 20, "type": 7, "date": "1943-03-10"},
        ])
        results = load_other_incidences(db, career_id=5, player_id=20, resolve_squadron_fn=_no_resolve)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["type"], "COMMAND")
        self.assertEqual(results[0]["date"], "1943-03-10")

    def test_transfer_fallback_name(self):
        """When resolve_squadron_fn returns None, fallback squadron name is used."""
        db = _make_db([
            {"id": 1, "careerId": 5, "pilotId": 20, "type": 9, "date": "1943-04-01", "squadronId": 42},
        ])
        results = load_other_incidences(db, career_id=5, player_id=20, resolve_squadron_fn=_no_resolve)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["type"], "TRANSFER")
        self.assertIn("42", results[0]["squadron_name"])  # fallback contains configId

    def test_transfer_resolved_name(self):
        """When resolve_squadron_fn returns a name, it is used."""
        def _resolve(cid: int, cfgid: int) -> Optional[str]:
            if cid == 5 and cfgid == 42:
                return "I./JG 52"
            return None

        db = _make_db([
            {"id": 1, "careerId": 5, "pilotId": 20, "type": 9, "date": "1943-04-01", "squadronId": 42},
        ])
        results = load_other_incidences(db, career_id=5, player_id=20, resolve_squadron_fn=_resolve)
        self.assertEqual(results[0]["squadron_name"], "I./JG 52")

    def test_sort_order_across_types(self):
        """Entries from different types are sorted by date ascending."""
        db = _make_db([
            {"id": 1, "careerId": 5, "pilotId": 20, "type": 9, "date": "1943-06-01", "squadronId": 1},
            {"id": 2, "careerId": 5, "pilotId": 20, "type": 7, "date": "1943-04-01"},
            {"id": 3, "careerId": 5, "pilotId": 20, "type": 13, "date": "1943-02-01"},
        ])
        results = load_other_incidences(db, career_id=5, player_id=20, resolve_squadron_fn=_no_resolve)
        dates = [r.get("date") or r.get("start_date") for r in results]
        self.assertEqual(dates, sorted(dates))


if __name__ == "__main__":
    unittest.main()
