"""
StatisticsMapper: maps cp.db pilot table kill counters to the combat_results
shape expected by the existing frontend (detail.js).

Key design decisions:
- Statistics are read directly from the pilot table (accumulated totals).
  No recomputation across sorties.
- Only atomic kill-counter columns are summed. Higher-level rollup columns
  (e.g. killShips, killArmouredVehicle) are intentionally excluded to
  prevent double-counting.
- Missing columns (older cp.db versions) degrade gracefully to 0.
- total_score is set to 0: cp.db has no score column equivalent to the
  Campaign Tracker's per-mission score; this field can be populated later
  if a score source is identified.
"""

import logging
import sqlite3
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Kill bucket definitions
# ---------------------------------------------------------------------------
# Each entry: (result_key, [db_column, ...])
# All listed columns are summed into result_key.
# The result_key names match those produced by CampaignAggregator._calculate_summary()
# so that the frontend renders them without change.

_KILL_BUCKETS: List[Tuple[str, List[str]]] = [
    # Aircraft
    ("air_kills",         ["killLightPlane", "killMediumPlane", "killHeavyPlane"]),
    ("static_air_kills",  ["killStaticPlane"]),
    # Vehicles
    ("ground_kills",      ["killVehicle", "killLightTank", "killMediumTank", "killHeavyTank"]),
    # Railroad
    ("rail_kills",        ["killTrainLocomotive", "killTrainVagon", "killRailwayStationFacility"]),
    # Armaments
    ("mg_kills",          ["killMachineGun"]),
    ("artillery_kills",   ["killFieldGun", "killHowitzer", "killNavalGun"]),
    ("aa_kills",          ["killAirDefence"]),
    ("rocket_kills",      ["killRocketLauncher"]),
    ("searchlight_kills", ["killSearchlight"]),
    # Buildings
    ("building_kills",    ["killTownBuilding", "killRuralYard"]),
    ("facility_kills",    ["killFactoryBuilding", "killAirfieldFacility"]),
    ("bridge_kills",      ["killBridge"]),
    # Marine
    ("light_ship_kills",  ["killLightShip"]),
    ("cargo_ship_kills",  ["killLargeCargoShip"]),
    ("submarine_kills",   ["killSubmarine"]),
    ("destroyer_kills",   ["killDestroyerShip"]),
]

# ---------------------------------------------------------------------------
# Nested by_category structure expected by the frontend renderCombatResults()
# ---------------------------------------------------------------------------
# Each entry: (category_key, [(subcategory_label, [db_columns, ...]), ...])
# category_key matches the frontend's categories[].key strings.
# subcategory_label matches subcategoryMap[][].label strings.

_BY_CATEGORY_MAP: List[Tuple[str, List[Tuple[str, List[str]]]]] = [
    ("Aircraft", [
        ("Light",   ["killLightPlane"]),
        ("Medium",  ["killMediumPlane"]),
        ("Heavy",   ["killHeavyPlane"]),
        ("Parked",  ["killStaticPlane"]),
        ("Balloons", []),
    ]),
    ("Vehicles", [
        ("Transport",        ["killVehicle"]),
        ("Armored (Light)",  ["killLightTank"]),
        ("Armored (Medium)", ["killMediumTank"]),
        ("Armored (Heavy)",  ["killHeavyTank"]),
    ]),
    ("Railroad", [
        ("Locomotives",        ["killTrainLocomotive"]),
        ("Railroad Cars",      ["killTrainVagon"]),
        ("Station Facilities", ["killRailwayStationFacility"]),
    ]),
    ("Armaments", [
        ("Machine Guns",     ["killMachineGun"]),
        ("Cannons",          ["killFieldGun", "killHowitzer", "killNavalGun"]),
        ("AAA Guns",         ["killAirDefence"]),
        ("Rocket Launchers", ["killRocketLauncher"]),
        ("Searchlights",     ["killSearchlight"]),
        ("Radars",           []),
    ]),
    ("Buildings", [
        ("Residential Buildings", ["killTownBuilding", "killRuralYard"]),
        ("Facilities",            ["killFactoryBuilding", "killAirfieldFacility"]),
        ("Bridges",               ["killBridge"]),
    ]),
    ("Marine", [
        ("Light",      ["killLightShip"]),
        ("Cargo",      ["killLargeCargoShip"]),
        ("Submarines", ["killSubmarine"]),
        ("Destroyers", ["killDestroyerShip"]),
    ]),
]


class StatisticsMapper:
    """
    Maps pilot table kill counter columns to the combat_results dict shape.

    Usage:
        mapper = StatisticsMapper()
        pilot_row = db.get_pilot_by_id(pilot_id)
        combat_results = mapper.build_combat_results(pilot_row)
    """

    def build_combat_results(self, pilot_row: Optional[sqlite3.Row]) -> Dict:
        """
        Build the combat_results dict from a pilot table row.

        Args:
            pilot_row: sqlite3.Row from the pilot table, or None.

        Returns:
            Dict matching the combat_results shape produced by CampaignAggregator.
            Returns an empty dict if pilot_row is None.
        """
        if pilot_row is None:
            return {}

        result: Dict = {}
        total_kills = 0

        for result_key, columns in _KILL_BUCKETS:
            bucket_total = 0
            for col in columns:
                bucket_total += self._safe_int(pilot_row, col)
            result[result_key] = bucket_total
            total_kills += bucket_total

        result["total_kills"] = total_kills
        # cp.db has no direct score equivalent; placeholder for future mapping
        result["total_score"] = 0

        # Build nested by_category dict for the frontend's category/subcategory display
        by_category: Dict = {}
        for cat_key, subcats in _BY_CATEGORY_MAP:
            subcategory_dict: Dict = {}
            for subcat_label, columns in subcats:
                subcategory_dict[subcat_label] = sum(
                    self._safe_int(pilot_row, col) for col in columns
                )
            by_category[cat_key] = subcategory_dict
        result["by_category"] = by_category

        return result

    @staticmethod
    def _safe_int(row: sqlite3.Row, column: str) -> int:
        """Read an integer from a Row column, returning 0 on any error."""
        try:
            val = row[column]
            return int(val) if val is not None else 0
        except (IndexError, TypeError, ValueError):
            logger.debug("Kill counter column '%s' not found or invalid; defaulting to 0", column)
            return 0
