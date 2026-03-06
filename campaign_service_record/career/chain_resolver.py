"""
CareerChainResolver: resolves career.extends chains into VirtualPilotCareer objects.

A VirtualPilotCareer aggregates all theatre segments for one virtual pilot
into a single logical career. It is identified by root_career_id — the id
of the career row where extends = -1.

Chain resolution algorithm:
    1. Start from a root row (extends = -1).
    2. Query for rows extending the current row's id.
    3. If exactly one: append to chain, continue.
       If multiple: log warning, use first (ambiguous state in db — shouldn't occur).
       If none: chain is complete.
    4. Fetch pilot row using root.playerId to obtain name, country, birth date.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from campaign_service_record.career.database import CareerDatabase, PilotDescriptionParser

logger = logging.getLogger(__name__)


# career.infoId → theatre display label mapping.
# Add entries here when new theatres are confirmed.
THEATRE_LABELS: Dict[str, str] = {
    "BoL41": "Battle of Leningrad 1941",
    "BoO41": "Defence of Odessa",
    "BOM":   "Battle of Moscow",
    "BOS":   "Battle of Stalingrad",
    "BOK":   "Battle of Kuban",
    "BoO44": "Liberation of Odessa",
    "BON":   "Battle of Normandy",
    "BOBP":  "Battle of Rheinland",
}


@dataclass
class VirtualPilotCareer:
    """
    A complete virtual pilot career spanning one or more theatre segments.

    Attributes:
        pilot_id           -- career.playerId from the root career = pilot.id
        pilot_first_name   -- pilot.name (given name)
        pilot_last_name    -- pilot.lastName (family name)
        pilot_name         -- "{pilot.name} {pilot.lastName}" (combined display name)
        country            -- country key derived from pilot.description
        birth_date         -- "YYYY-MM-DD" derived from pilot.description, or None
        root_career_id     -- id of the chain root (extends = -1); used as URL key
        last_pilot_id      -- career.playerId of the most current (last) career in chain
        chain              -- ordered list of career sqlite3.Row objects, root → latest
        theatre_labels     -- display label for each career row in chain
        faction            -- same value as country (kept for display clarity)
    """
    pilot_id: int
    pilot_first_name: str
    pilot_last_name: str
    pilot_name: str
    country: Optional[str]
    birth_date: Optional[str]
    root_career_id: int
    last_pilot_id: int = 0
    chain: list = field(default_factory=list)
    theatre_labels: List[str] = field(default_factory=list)
    faction: Optional[str] = None


class CareerChainResolver:
    """Resolves career.extends chains and builds VirtualPilotCareer objects."""

    def __init__(self, db: CareerDatabase):
        self._db = db

    def resolve_all_careers(self) -> List[VirtualPilotCareer]:
        """
        Resolve all root careers into VirtualPilotCareer objects.

        Returns:
            One VirtualPilotCareer per unique root career (i.e. per virtual pilot).
        """
        roots = self._db.get_all_root_careers()
        careers = []
        for root in roots:
            try:
                career = self._resolve_chain(root)
                if career is not None:
                    careers.append(career)
            except Exception as exc:
                logger.error(
                    "Failed to resolve career chain for root id=%s: %s",
                    root["id"], exc, exc_info=True
                )
        return careers

    def get_career(self, root_career_id: int) -> Optional[VirtualPilotCareer]:
        """
        Resolve a single career chain by root career id.

        Args:
            root_career_id: The id of the career row where extends = -1.

        Returns:
            VirtualPilotCareer or None if root is not found or is not a root.
        """
        root = self._db.get_career_by_id(root_career_id)
        if root is None:
            logger.warning("Career root not found: id=%d", root_career_id)
            return None
        if root["extends"] != -1:
            logger.warning(
                "Career id=%d is not a root (extends=%d)",
                root_career_id, root["extends"]
            )
            return None
        return self._resolve_chain(root)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _resolve_chain(self, root) -> Optional[VirtualPilotCareer]:
        """Build a VirtualPilotCareer by following the extends chain from root."""
        chain = [root]
        current = root

        while True:
            next_rows = self._db.get_careers_extending(current["id"])
            if not next_rows:
                break
            if len(next_rows) > 1:
                logger.warning(
                    "Career id=%d has %d extending careers; using first",
                    current["id"], len(next_rows)
                )
            current = next_rows[0]
            chain.append(current)

        pilot_id = root["playerId"]
        pilot_row = self._db.get_pilot_by_id(pilot_id)
        if pilot_row is None:
            logger.warning(
                "Pilot not found for career root id=%d, playerId=%d",
                root["id"], pilot_id
            )
            return None

        description = pilot_row["description"] or ""
        country = PilotDescriptionParser.parse_country(description)
        birth_date = PilotDescriptionParser.parse_birth_date(description)

        first_name = (pilot_row["name"] or "").strip()
        last_name = (pilot_row["lastName"] or "").strip()
        pilot_name = f"{first_name} {last_name}".strip() or f"Pilot #{pilot_id}"

        # Most current career is the last in the chain; its playerId is the
        # up-to-date pilot reference (pcp, squadronId, etc.)
        last_pilot_id = int(chain[-1]["playerId"]) if chain else pilot_id

        theatre_labels = [
            THEATRE_LABELS.get(row["infoId"] or "", f"Theatre ({row['infoId']})")
            for row in chain
        ]

        return VirtualPilotCareer(
            pilot_id=pilot_id,
            pilot_first_name=first_name,
            pilot_last_name=last_name,
            pilot_name=pilot_name,
            country=country,
            birth_date=birth_date,
            root_career_id=int(root["id"]),
            last_pilot_id=last_pilot_id,
            chain=chain,
            theatre_labels=theatre_labels,
            faction=country,
        )
