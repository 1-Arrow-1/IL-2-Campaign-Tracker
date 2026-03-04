"""
CareerDatabase: read-only SQLite access layer for cp.db.

Design decisions:
- Read-only connection via URI mode:  file:<path>?mode=ro
  Prevents any accidental writes to the live game database.
- Lazy connection: sqlite3 handle created on first query call, cached thereafter.
- sqlite3.Row factory: all rows returned with named column access (row["column"]).
- No ORM. All queries use plain parameterized statements (:name style) to
  prevent SQL injection.
- close() releases the connection; callers should call it on shutdown.

PilotDescriptionParser:
- Extracts structured fields from pilot.description (a delimited long string).
- Uses narrow regex anchors to avoid assumptions about surrounding content.
"""

import logging
import re
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pilot description parser
# ---------------------------------------------------------------------------

class PilotDescriptionParser:
    """
    Parses the pilot.description long string to extract structured fields.

    Confirmed format substrings:
        birthCountryInfo=<int>   (country code)
        &birthDate=YYYY.MM.DD%   (birth date)

    Country codes:
        101 = USSR
        102 = Britain
        103 = USA
        201 = Germany
    """

    COUNTRY_MAP: Dict[int, str] = {
        101: "ussr",
        102: "britain",
        103: "usa",
        201: "germany",
    }

    _COUNTRY_RE = re.compile(r'birthCountryInfo=(\d+)')
    _BIRTHDATE_RE = re.compile(r'&birthDate=(\d{4}\.\d{2}\.\d{2})%')

    @classmethod
    def parse_country(cls, description: str) -> Optional[str]:
        """
        Extract country string from pilot.description.

        Returns:
            Country key ("ussr", "britain", "usa", "germany") or None.
        """
        if not description:
            return None
        match = cls._COUNTRY_RE.search(description)
        if not match:
            return None
        country_code = int(match.group(1))
        country = cls.COUNTRY_MAP.get(country_code)
        if country is None:
            logger.warning("Unknown birthCountryInfo code: %d", country_code)
        return country

    @classmethod
    def parse_birth_date(cls, description: str) -> Optional[str]:
        """
        Extract birth date from pilot.description.

        Returns:
            ISO date string "YYYY-MM-DD" or None.
        """
        if not description:
            return None
        match = cls._BIRTHDATE_RE.search(description)
        if not match:
            return None
        # Convert "YYYY.MM.DD" → "YYYY-MM-DD"
        return match.group(1).replace('.', '-')


# ---------------------------------------------------------------------------
# Database access layer
# ---------------------------------------------------------------------------

class CareerDatabase:
    """
    Read-only SQLite wrapper for cp.db.

    All public methods return sqlite3.Row instances (dict-like, named access).
    The connection is opened lazily on first query and cached for subsequent calls.
    """

    def __init__(self, db_path: Path):
        self._db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        # cp.db lives at <game_dir>/data/Career/cp.db — derive game_dir for asset lookups
        self.game_dir: Optional[Path] = db_path.parent.parent.parent if db_path else None

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        if self._conn is None:
            uri = f"file:{self._db_path}?mode=ro"
            try:
                self._conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
                self._conn.row_factory = sqlite3.Row
                logger.info("CareerDatabase connected (read-only): %s", self._db_path)
            except sqlite3.OperationalError as exc:
                logger.error("Cannot open cp.db at %s: %s", self._db_path, exc)
                raise
        return self._conn

    def close(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None
            logger.info("CareerDatabase closed")

    # ------------------------------------------------------------------
    # career table
    # ------------------------------------------------------------------

    def get_all_root_careers(self) -> List[sqlite3.Row]:
        """Return all career rows where extends = -1 (chain roots)."""
        conn = self._connect()
        cursor = conn.execute("SELECT * FROM career WHERE extends = -1")
        return cursor.fetchall()

    def get_career_by_id(self, career_id: int) -> Optional[sqlite3.Row]:
        """Return a single career row by id."""
        conn = self._connect()
        cursor = conn.execute(
            "SELECT * FROM career WHERE id = :id",
            {"id": career_id}
        )
        return cursor.fetchone()

    def get_careers_extending(self, career_id: int) -> List[sqlite3.Row]:
        """Return career rows whose extends column equals career_id."""
        conn = self._connect()
        cursor = conn.execute(
            "SELECT * FROM career WHERE extends = :career_id",
            {"career_id": career_id}
        )
        return cursor.fetchall()

    # ------------------------------------------------------------------
    # pilot table
    # ------------------------------------------------------------------

    def get_pilot_by_id(self, pilot_id: int) -> Optional[sqlite3.Row]:
        """
        Return the pilot row for the given id.

        The pilot row contains:
            - name, lastName          (display name)
            - description             (long string, parsed by PilotDescriptionParser)
            - kill counter columns    (accumulated totals, used by StatisticsMapper)
        """
        conn = self._connect()
        cursor = conn.execute(
            "SELECT * FROM pilot WHERE id = :id",
            {"id": pilot_id}
        )
        return cursor.fetchone()

    def get_squadron_by_id(self, squadron_id: int) -> Optional[sqlite3.Row]:
        """
        Return the squadron row for the given id.

        The squadron row contains:
            - id                (primary key)
            - configId          (folder name in CampaignRanksAwards/squadrons/)
        """
        conn = self._connect()
        cursor = conn.execute(
            "SELECT * FROM squadron WHERE id = :id",
            {"id": squadron_id}
        )
        return cursor.fetchone()

    # ------------------------------------------------------------------
    # event table
    # ------------------------------------------------------------------

    def get_events_for_pilot(
        self,
        pilot_id: int,
        types: Optional[List[int]] = None
    ) -> List[sqlite3.Row]:
        """
        Return events for a pilot ordered by event.date ascending.

        Args:
            pilot_id: pilot.id value (= career.playerId).
            types:    If provided, filter to only these event type integers.
                      Confirmed types: 6=promotion, 8=award, 10=transfer.

        Returns:
            List of sqlite3.Row ordered by event.date ASC.
        """
        conn = self._connect()
        if types:
            placeholders = ",".join("?" * len(types))
            cursor = conn.execute(
                f"SELECT * FROM event WHERE pilotId = ? AND type IN ({placeholders}) "
                f"ORDER BY date ASC",
                [pilot_id, *types]
            )
        else:
            cursor = conn.execute(
                "SELECT * FROM event WHERE pilotId = ? ORDER BY date ASC",
                [pilot_id]
            )
        return cursor.fetchall()

    # ------------------------------------------------------------------
    # sortie + mission tables
    # ------------------------------------------------------------------

    def get_sorties_for_pilot(self, pilot_id: int) -> List[sqlite3.Row]:
        """
        Return all sortie rows for a pilot.

        Note: sortie has only a pilotId column (no careerId FK).
        All sorties across all theatre segments are returned via pilotId.
        """
        conn = self._connect()
        cursor = conn.execute(
            "SELECT * FROM sortie WHERE pilotId = :pilot_id",
            {"pilot_id": pilot_id}
        )
        return cursor.fetchall()

    def get_mission_by_id(self, mission_id: int) -> Optional[sqlite3.Row]:
        """Return a single mission row by id."""
        conn = self._connect()
        cursor = conn.execute(
            "SELECT * FROM mission WHERE id = :id",
            {"id": mission_id}
        )
        return cursor.fetchone()

    def get_incidence_events_for_career(
        self,
        career_id: int,
        player_id: int,
        types: List[int],
    ) -> List[sqlite3.Row]:
        """
        Return events filtered by careerId AND pilotId AND type, with isDeleted=0.

        Unlike get_events_for_pilot(), this enforces the careerId constraint so that
        events from other career chains sharing the same pilot id are excluded.

        Args:
            career_id:  career.id for the specific theatre segment.
            player_id:  career.playerId for that segment.
            types:      List of event.type integers to include.

        Returns:
            List of sqlite3.Row ordered by event.date ASC.
        """
        conn = self._connect()
        placeholders = ",".join("?" * len(types))
        cursor = conn.execute(
            f"SELECT * FROM event "
            f"WHERE careerId = ? AND pilotId = ? AND type IN ({placeholders}) "
            f"AND isDeleted = 0 ORDER BY date ASC",
            [career_id, player_id, *types],
        )
        return cursor.fetchall()

    def get_events_with_squadron_for_career(
        self,
        career_id: int,
        player_id: int,
    ) -> List[sqlite3.Row]:
        """
        Return all non-deleted events for this career that carry a non-null
        squadronId, ordered by date ASC.

        Used by the squadron-change (event.type = 10) handler to determine the
        pilot's previous squadron just before each change event.
        """
        conn = self._connect()
        cursor = conn.execute(
            "SELECT * FROM event "
            "WHERE careerId = ? AND pilotId = ? AND isDeleted = 0 "
            "AND squadronId IS NOT NULL "
            "ORDER BY date ASC",
            [career_id, player_id],
        )
        return cursor.fetchall()

    def get_squadron_by_career_and_config(
        self,
        career_id: int,
        config_id: int,
    ) -> Optional[sqlite3.Row]:
        """
        Return the squadron row matching a careerId + configId pair.

        Used to resolve squadron transfer events (event.type = 9), where
        event.squadronId carries the squadron configId (not the primary key).

        Args:
            career_id:  career.id of the theatre segment that owns the squadron.
            config_id:  squadron.configId value stored in event.squadronId.

        Returns:
            sqlite3.Row or None if not found.
        """
        conn = self._connect()
        cursor = conn.execute(
            "SELECT * FROM squadron WHERE careerId = ? AND configId = ?",
            [career_id, config_id],
        )
        return cursor.fetchone()

    def get_missions_for_career(
        self, career_id: int, player_id: int
    ) -> List[sqlite3.Row]:
        """
        Return mission rows for a career segment where the player flew.

        First tries to filter by pilot slot columns (pilot0..pilot8).
        Falls back to careerId-only if the schema lacks those columns.

        Returns rows ordered by startTime ASC.
        """
        conn = self._connect()
        try:
            cursor = conn.execute(
                """SELECT * FROM mission
                   WHERE careerId = :career_id
                     AND (   pilot0 = :pid OR pilot1 = :pid OR pilot2 = :pid
                          OR pilot3 = :pid OR pilot4 = :pid OR pilot5 = :pid
                          OR pilot6 = :pid OR pilot7 = :pid OR pilot8 = :pid)
                   ORDER BY startTime ASC""",
                {"career_id": career_id, "pid": player_id},
            )
            return cursor.fetchall()
        except sqlite3.OperationalError as exc:
            logger.warning(
                "Pilot-slot filter failed (%s); falling back to careerId-only", exc
            )
            cursor = conn.execute(
                "SELECT * FROM mission WHERE careerId = :career_id ORDER BY startTime ASC",
                {"career_id": career_id},
            )
            return cursor.fetchall()

    def get_mission_count_for_career(
        self, career_id: int, player_id: int
    ) -> int:
        """
        Return the count of missions for a career segment where the player flew.

        Mirrors the filter logic of get_missions_for_career() but uses COUNT(*)
        to avoid fetching full rows — used to pre-calculate progress totals.

        Falls back to zero on OperationalError (older schema without pilot slots).
        """
        conn = self._connect()
        try:
            cursor = conn.execute(
                """SELECT COUNT(*) FROM mission
                   WHERE careerId = :career_id
                     AND (   pilot0 = :pid OR pilot1 = :pid OR pilot2 = :pid
                          OR pilot3 = :pid OR pilot4 = :pid OR pilot5 = :pid
                          OR pilot6 = :pid OR pilot7 = :pid OR pilot8 = :pid)""",
                {"career_id": career_id, "pid": player_id},
            )
            row = cursor.fetchone()
            return int(row[0]) if row else 0
        except sqlite3.OperationalError as exc:
            logger.warning(
                "Mission count failed (%s); returning 0", exc
            )
            return 0
