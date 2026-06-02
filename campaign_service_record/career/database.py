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
    _BIOID_RE = re.compile(r'bioInfo=id%3D(\d+)')

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

    @classmethod
    def parse_bio_id(cls, description: str) -> Optional[int]:
        """
        Extract character bio ID from pilot.description.

        The game stores the chosen bio as bioInfo=id%3D<id>% in the description
        string.  Returns the integer bio ID, or None if absent.
        """
        if not description:
            return None
        match = cls._BIOID_RE.search(description)
        if not match:
            return None
        try:
            return int(match.group(1))
        except ValueError:
            return None


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

    def get_award_events_for_pilots(self, pilot_ids: List[int]) -> List[sqlite3.Row]:
        """
        Return all type-8 (award) events for the given pilot IDs.

        No isDeleted filter — get_events_for_pilots (the timeline query) also
        omits it, and award events may carry isDeleted != 0 in some db versions.

        Returns pilotId, date, and tpar2 (award code) columns.
        """
        if not pilot_ids:
            return []
        conn = self._connect()
        id_ph = ",".join("?" * len(pilot_ids))
        cursor = conn.execute(
            f"SELECT pilotId, date, tpar2 FROM event"
            f" WHERE pilotId IN ({id_ph}) AND type = 8",
            pilot_ids,
        )
        return cursor.fetchall()

    def get_all_pilot_ids_for_squadron(self, pilot_squadron_id: int) -> List[int]:
        """
        Return ALL pilot.id values ever associated with a given squadronId.

        A pilot who transferred theatres has one pilot row per theatre, all
        sharing the same squadronId.  Awards may be recorded under any of those
        rows, so we collect them all for a complete award lookup.
        """
        conn = self._connect()
        cursor = conn.execute(
            "SELECT id FROM pilot WHERE squadronId = ?",
            [pilot_squadron_id],
        )
        return [row[0] for row in cursor.fetchall()]

    def get_pilot_ids_by_name(self, name: str, last_name: str) -> List[int]:
        """
        Return all pilot.id values that share the same (name, lastName).

        Used to collect a pilot's historical IDs across theatres: each time a
        pilot enters a new theatre a fresh pilot row is created with a new id
        but the same name.  Awards are recorded under the old row's id, so we
        need every id in the name group for a complete award lookup.
        """
        conn = self._connect()
        cursor = conn.execute(
            "SELECT id FROM pilot WHERE name = ? AND lastName = ?",
            [name, last_name],
        )
        return [row[0] for row in cursor.fetchall()]

    def get_pilot_ids_by_name_before_ins_date(
        self,
        name: str,
        last_name: str,
        max_ins_date: str,
    ) -> List[int]:
        """
        Return pilot.id values for the same pilot name up to a snapshot row date.

        IL-2 creates a fresh pilot row when a pilot enters a new theatre. For
        historical squadron snapshots we must exclude future-theatre rows, or a
        pilot may incorrectly inherit awards earned later in the career.

        Args:
            name:         pilot.name
            last_name:    pilot.lastName
            max_ins_date: pilot.insDate from the selected historical snapshot row

        Returns:
            Matching pilot.id values whose insDate is NULL or <= max_ins_date.
        """
        if not max_ins_date:
            return self.get_pilot_ids_by_name(name, last_name)
        conn = self._connect()
        cursor = conn.execute(
            "SELECT id FROM pilot "
            "WHERE name = ? AND lastName = ? AND isDeleted = 0 "
            "AND (insDate IS NULL OR insDate <= ?) "
            "ORDER BY insDate ASC, id ASC",
            [name, last_name, max_ins_date],
        )
        return [row[0] for row in cursor.fetchall()]

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

    def get_events_for_pilots(
        self,
        pilot_ids: List[int],
        types: Optional[List[int]] = None,
    ) -> List[sqlite3.Row]:
        """
        Return events for multiple pilot IDs ordered by event.date ascending.

        Used when a career spans multiple theatre segments that each have their
        own pilot row (playerId differs per theatre).

        Args:
            pilot_ids: List of pilot.id values to include.
            types:     If provided, filter to only these event type integers.
        """
        if not pilot_ids:
            return []
        conn = self._connect()
        id_ph = ",".join("?" * len(pilot_ids))
        if types:
            type_ph = ",".join("?" * len(types))
            cursor = conn.execute(
                f"SELECT * FROM event WHERE pilotId IN ({id_ph}) "
                f"AND type IN ({type_ph}) ORDER BY date ASC",
                [*pilot_ids, *types],
            )
        else:
            cursor = conn.execute(
                f"SELECT * FROM event WHERE pilotId IN ({id_ph}) ORDER BY date ASC",
                pilot_ids,
            )
        return cursor.fetchall()

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

    def get_sorties_for_pilot(self, pilot_ids) -> List[sqlite3.Row]:
        """
        Return all sortie rows for one or more pilots.

        Accepts a single int or a list of ints so multi-theatre careers
        (where each theatre segment has its own pilotId) are covered in
        one call.  sortie has no careerId FK, so pilotId is the only key.
        """
        if isinstance(pilot_ids, int):
            pilot_ids = [pilot_ids]
        if not pilot_ids:
            return []
        conn = self._connect()
        id_ph = ",".join("?" * len(pilot_ids))
        cursor = conn.execute(
            f"SELECT * FROM sortie WHERE pilotId IN ({id_ph})",
            pilot_ids,
        )
        return cursor.fetchall()

    def get_sortie_for_mission(self, mission_id: int, pilot_id: int) -> Optional[sqlite3.Row]:
        """Return the human player's sortie row for a specific mission."""
        conn = self._connect()
        cursor = conn.execute(
            "SELECT * FROM sortie"
            " WHERE missionId = :mission_id AND pilotId = :pilot_id"
            " AND pilotAi = 0 AND isDeleted = 0",
            {"mission_id": mission_id, "pilot_id": pilot_id},
        )
        return cursor.fetchone()

    def get_sorties_for_mission_pilots(self, mission_id: int, pilot_ids: List[int]) -> List[sqlite3.Row]:
        """
        Return sortie rows for one mission filtered to a list of pilot IDs.

        This is used for squadron-context extraction (WIA/MIA/KIA) on the
        mission date. Returns an empty list when no pilot IDs are supplied.
        """
        if not pilot_ids:
            return []
        conn = self._connect()
        id_ph = ",".join("?" * len(pilot_ids))
        cursor = conn.execute(
            f"SELECT * FROM sortie WHERE missionId = ? AND pilotId IN ({id_ph}) AND isDeleted = 0",
            [mission_id, *pilot_ids],
        )
        return cursor.fetchall()

    def get_injured_sortie_before(
        self,
        pilot_ids,
        before_date_str: str,
    ) -> Optional[sqlite3.Row]:
        """
        Return the most recent status=4 (injured) sortie for any of the given
        pilot IDs whose date is strictly before before_date_str.

        Used by the recovery-range refinement to find the actual injury start
        date when Rapid Mode has skipped calendar days and only the final
        recovery day was recorded as a type-13 event.
        """
        if isinstance(pilot_ids, int):
            pilot_ids = [pilot_ids]
        if not pilot_ids:
            return None
        conn = self._connect()
        id_ph = ",".join("?" * len(pilot_ids))
        cursor = conn.execute(
            f"SELECT missionId, pilotId, date FROM sortie"
            f" WHERE pilotId IN ({id_ph})"
            f"   AND status = 4"
            f"   AND isDeleted = 0"
            f"   AND date < ?"
            f" ORDER BY date DESC"
            f" LIMIT 1",
            (*pilot_ids, before_date_str),
        )
        return cursor.fetchone()

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

    def get_squadron_members(self, pilot_squadron_id: int) -> List[sqlite3.Row]:
        """
        Return pilot rows for all members of a squadron.

        Uses pilot.squadronId directly — the simplest and most reliable key.
        All pilots (player and AI) in the same squadron share the same
        pilot.squadronId value; no career-chain traversal is needed.

        Returns rows ordered by pilot.rankId DESC, then air kills DESC.
        """
        conn = self._connect()
        cursor = conn.execute(
            """
            SELECT *
            FROM pilot
            WHERE squadronId = ?
              AND isDeleted = 0
            ORDER BY rankId DESC,
                     (COALESCE(killLightPlane, 0) + COALESCE(killMediumPlane, 0)
                      + COALESCE(killHeavyPlane, 0) + COALESCE(killStaticPlane, 0)) DESC
            """,
            [pilot_squadron_id],
        )
        return cursor.fetchall()

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

    def get_all_missions_for_career(self, career_id: int) -> List[sqlite3.Row]:
        """Return ALL mission rows for a career segment, regardless of pilot slot.

        Unlike get_missions_for_career, this includes AI-only missions where the
        player is not listed in any pilot slot.  Used by the story context builder
        so every game mission gets its own chapter.

        Returns rows ordered by startTime ASC.
        """
        conn = self._connect()
        cursor = conn.execute(
            "SELECT * FROM mission WHERE careerId = :career_id ORDER BY startTime ASC",
            {"career_id": career_id},
        )
        return cursor.fetchall()

    def get_unflown_squadron_sorties(
        self,
        player_pilot_id: int,
        squadron_pilot_ids: List[int],
    ) -> List[sqlite3.Row]:
        """
        Return sortie rows for squadron members from missions the player did not fly.

        A mission is considered "flown" by the player when a non-AI sortie row
        (pilotAi=0, isDeleted=0) exists for player_pilot_id.  All non-deleted
        sortie rows for squadron_pilot_ids that belong to other missions are
        returned, ordered by date ASC.

        Used for inter-mission activity extraction: what the squadron did on days
        (or sorties within a day) the player sat out.
        """
        if not squadron_pilot_ids:
            return []
        conn = self._connect()
        id_ph = ",".join("?" * len(squadron_pilot_ids))
        cursor = conn.execute(
            f"SELECT * FROM sortie"
            f" WHERE pilotId IN ({id_ph})"
            f"   AND isDeleted = 0"
            f"   AND missionId NOT IN ("
            f"       SELECT missionId FROM sortie"
            f"       WHERE pilotId = ? AND pilotAi = 0 AND isDeleted = 0"
            f"   )"
            f" ORDER BY date ASC",
            [*squadron_pilot_ids, player_pilot_id],
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
