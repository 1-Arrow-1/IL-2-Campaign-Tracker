"""
IL-2 Campaign Tracker - Combat Results Utilities

Provides:
1. KILL_MAPPING - Central mapping of kill categories to stat keys
2. calculate_kills_from_stats() - Calculate kill totals from mission stats
3. calculate_air_combat_score() - Calculate weighted air combat score for awards
4. calculate_total_air_kills_weighted() - Weighted air kill totals for displays
5. aggregate_kills_from_missions() - Aggregate kills across missions
"""

from collections import defaultdict
from typing import Any, Dict

# =============================================================================
# CENTRAL KILL MAPPING
# =============================================================================
# Maps display categories to IL-2 stat keys
# Used by all kill calculation functions for consistency

KILL_MAPPING = {
    "Aircraft": {
        "Light": "killLightPlane",
        "Medium": "killMediumPlane",
        "Heavy": "killHeavyPlane",
        "Parked": "killStaticPlane",
        "Balloons": "killMediumAerostat",
    },
    "Vehicles": {
        "Transport": "killTransportVehicle",
        "Armored (Light)": "killLightArmoredVehicle",
        "Armored (Medium)": "killMediumArmoredVehicle",
        "Armored (Heavy)": "killHeavyArmoredVehicle",
    },
    "Railroad": {
        "Locomotives": "killLocomotive",
        "Railroad Cars": "killRailroadCarriage",
        "Station Facilities": "killRailroadStation",
    },
    "Armaments": {
        "Machine Guns": "killMachinegun",
        "Cannons": "killCannon",
        "AAA Guns": "killAAAGun",
        "Rocket Launchers": "killRocketLauncher",
        "Searchlights": "killSearchlight",
        "Radars": "killRadar",
    },
    "Buildings": {
        "Residential Buildings": "killResidentalBuilding",  # IL-2 uses this spelling
        "Facilities": "killFacility",
        "Bridges": "killBridge",
    },
    "Marine": {
        "Light": "killLightShip",
        "Cargo": "killLargeCargoShip",
        "Submarines": "killSubmarine",
        "Destroyers": "killDestroyerShip",
    },
}


# =============================================================================
# KILL CALCULATION HELPERS
# =============================================================================

def calculate_kills_from_stats(stats: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate kill totals from mission stats dictionary.

    This is the SINGLE SOURCE OF TRUTH for kill calculations.
    All air kills count as 1 (including parked/static planes).

    Args:
        stats: Mission statistics dict from characterStatisticsByFileName

    Returns:
        Dictionary containing:
        - air_kills: int (light + medium + heavy + static + balloons)
        - fighter_kills: int (light + medium)
        - bomber_kills: int (heavy)
        - static_kills: int (parked planes)
        - ground_kills: int (vehicles + railroad + armaments + buildings)
        - tank_kills: int (armored vehicles only)
        - naval_kills: int (all ships)
        - total_kills: int (air + ground + naval)
        - by_category: dict (detailed breakdown by category)
    """
    if not isinstance(stats, dict):
        return _empty_kills_result()

    # Calculate detailed breakdown by category
    by_category = {}
    for category, subcats in KILL_MAPPING.items():
        by_category[category] = {}
        for subcat, key in subcats.items():
            by_category[category][subcat] = int(stats.get(key, 0))

    # Aircraft kills
    aircraft = by_category.get('Aircraft', {})
    light = aircraft.get('Light', 0)
    medium = aircraft.get('Medium', 0)
    heavy = aircraft.get('Heavy', 0)
    static = aircraft.get('Parked', 0)
    balloons = aircraft.get('Balloons', 0)

    fighter_kills = light + medium
    bomber_kills = heavy
    static_kills = static
    air_kills = light + medium + heavy + static + balloons

    # Ground kills (Vehicles + Railroad + Armaments + Buildings)
    vehicles = by_category.get('Vehicles', {})
    railroad = by_category.get('Railroad', {})
    armaments = by_category.get('Armaments', {})
    buildings = by_category.get('Buildings', {})

    ground_kills = (
        sum(vehicles.values()) +
        sum(railroad.values()) +
        sum(armaments.values()) +
        sum(buildings.values())
    )

    # Tank kills (armored vehicles only)
    tank_kills = (
        vehicles.get('Armored (Light)', 0) +
        vehicles.get('Armored (Medium)', 0) +
        vehicles.get('Armored (Heavy)', 0)
    )

    # Naval kills
    marine = by_category.get('Marine', {})
    naval_kills = sum(marine.values())

    # Total kills
    total_kills = air_kills + ground_kills + naval_kills

    return {
        'air_kills': air_kills,
        'fighter_kills': fighter_kills,
        'bomber_kills': bomber_kills,
        'static_kills': static_kills,
        'ground_kills': ground_kills,
        'tank_kills': tank_kills,
        'naval_kills': naval_kills,
        'total_kills': total_kills,
        'by_category': by_category,
    }


def _empty_kills_result() -> Dict[str, Any]:
    """Return empty kills result structure."""
    return {
        'air_kills': 0,
        'fighter_kills': 0,
        'bomber_kills': 0,
        'static_kills': 0,
        'ground_kills': 0,
        'tank_kills': 0,
        'naval_kills': 0,
        'total_kills': 0,
        'by_category': {},
    }


def calculate_air_combat_score(stats: Dict[str, Any]) -> float:
    """
    Calculate weighted air combat score for award eligibility.

    Weighting:
    - Light/Medium planes (fighters): 1.0 each
    - Heavy planes (bombers): 2.0 each (harder to kill)
    - Static/Parked planes: 0.5 each (easier targets)
    - Balloons: 1.0 each

    Args:
        stats: Mission statistics dict from characterStatisticsByFileName

    Returns:
        Weighted air combat score (float)
    """
    if not isinstance(stats, dict):
        return 0.0

    light = int(stats.get('killLightPlane', 0))
    medium = int(stats.get('killMediumPlane', 0))
    heavy = int(stats.get('killHeavyPlane', 0))
    static = int(stats.get('killStaticPlane', 0))
    balloons = int(stats.get('killMediumAerostat', 0))

    return light + medium + (heavy * 2) + (static * 0.5) + balloons


def calculate_total_air_kills_weighted(stats: Dict[str, Any]) -> float:
    """
    Calculate total air kills with parked planes weighted at 0.5.

    Used for cumulative stats display where parked planes count less.

    Args:
        stats: Mission statistics dict

    Returns:
        Weighted air kills total (float)
    """
    if not isinstance(stats, dict):
        return 0.0

    light = int(stats.get('killLightPlane', 0))
    medium = int(stats.get('killMediumPlane', 0))
    heavy = int(stats.get('killHeavyPlane', 0))
    static = int(stats.get('killStaticPlane', 0))   mm
    balloons = int(stats.get('killMediumAerostat', 0))

    return light + medium + heavy + (static * 0.5) + balloons


def aggregate_kills_from_missions(stats_by_mission: Dict[str, Dict]) -> Dict[str, Any]:
    """
    Aggregate kill statistics across multiple missions.

    Args:
        stats_by_mission: Dict mapping mission_id -> mission_stats

    Returns:
        Aggregated kills result (same structure as calculate_kills_from_stats)
    """
    totals = _empty_kills_result()
    totals['by_category'] = defaultdict(lambda: defaultdict(int))

    for mission_id, mission_stats in stats_by_mission.items():
        if not isinstance(mission_stats, dict):
            continue

        kills = calculate_kills_from_stats(mission_stats)

        totals['air_kills'] += kills['air_kills']
        totals['fighter_kills'] += kills['fighter_kills']
        totals['bomber_kills'] += kills['bomber_kills']
        totals['static_kills'] += kills['static_kills']
        totals['ground_kills'] += kills['ground_kills']
        totals['tank_kills'] += kills['tank_kills']
        totals['naval_kills'] += kills['naval_kills']
        totals['total_kills'] += kills['total_kills']

        # Aggregate by_category
        for category, subcats in kills.get('by_category', {}).items():
            for subcat, count in subcats.items():
                totals['by_category'][category][subcat] += count

    # Convert defaultdicts to regular dicts
    totals['by_category'] = {k: dict(v) for k, v in totals['by_category'].items()}

    return totals