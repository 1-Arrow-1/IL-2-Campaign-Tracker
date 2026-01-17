"""
IL-2 Campaign Tracker - Combat Results HTML Generator

Provides:
1. generate_mission_combat_results_html() - HTML for single mission
2. generate_campaign_summary_combat_results_html() - HTML for campaign summary
"""

from utils.combat_results import KILL_MAPPING, aggregate_kills_from_missions
from utils.i18n import t

CATEGORY_I18N_KEYS = {
    "Aircraft": "tracker.combat.category.aircraft",
    "Vehicles": "tracker.combat.category.vehicles",
    "Railroad": "tracker.combat.category.railroad",
    "Armaments": "tracker.combat.category.armaments",
    "Buildings": "tracker.combat.category.buildings",
    "Marine": "tracker.combat.category.marine",
}

SUBCATEGORY_I18N_KEYS = {
    "Aircraft": {
        "Light": "tracker.combat.subcategory.aircraft.light",
        "Medium": "tracker.combat.subcategory.aircraft.medium",
        "Heavy": "tracker.combat.subcategory.aircraft.heavy",
        "Parked": "tracker.combat.subcategory.aircraft.parked",
        "Balloons": "tracker.combat.subcategory.aircraft.balloons",
    },
    "Vehicles": {
        "Transport": "tracker.combat.subcategory.vehicles.transport",
        "Armored (Light)": "tracker.combat.subcategory.vehicles.armored_light",
        "Armored (Medium)": "tracker.combat.subcategory.vehicles.armored_medium",
        "Armored (Heavy)": "tracker.combat.subcategory.vehicles.armored_heavy",
    },
    "Railroad": {
        "Locomotives": "tracker.combat.subcategory.railroad.locomotives",
        "Railroad Cars": "tracker.combat.subcategory.railroad.cars",
        "Station Facilities": "tracker.combat.subcategory.railroad.facilities",
    },
    "Armaments": {
        "Machine Guns": "tracker.combat.subcategory.armaments.machine_guns",
        "Cannons": "tracker.combat.subcategory.armaments.cannons",
        "AAA Guns": "tracker.combat.subcategory.armaments.aaa_guns",
        "Rocket Launchers": "tracker.combat.subcategory.armaments.rocket_launchers",
        "Searchlights": "tracker.combat.subcategory.armaments.searchlights",
        "Radars": "tracker.combat.subcategory.armaments.radars",
    },
    "Buildings": {
        "Residential Buildings": "tracker.combat.subcategory.buildings.residential",
        "Facilities": "tracker.combat.subcategory.buildings.facilities",
        "Bridges": "tracker.combat.subcategory.buildings.bridges",
    },
    "Marine": {
        "Light": "tracker.combat.subcategory.marine.light",
        "Cargo": "tracker.combat.subcategory.marine.cargo",
        "Submarines": "tracker.combat.subcategory.marine.submarines",
        "Destroyers": "tracker.combat.subcategory.marine.destroyers",
    },
}


def _category_label(category: str) -> str:
    key = CATEGORY_I18N_KEYS.get(category)
    return t(key) if key else category


def _subcategory_label(category: str, subcategory: str) -> str:
    key = SUBCATEGORY_I18N_KEYS.get(category, {}).get(subcategory)
    return t(key) if key else subcategory


# =============================================================================
# HTML GENERATORS
# =============================================================================

def generate_mission_combat_results_html(mission_id: str, decoded_data: dict, game_directory: str = None) -> str:
    """
    Creates Combat-Results table for a specific mission (for PDF debrief).
    Matches the in-game layout with icons and shows ALL categories (even 0 kills).
    
    Args:
        mission_id: Mission identifier
        decoded_data: Campaign data from campaigns_decoded.json
        game_directory: Path to IL-2 game directory (for icon paths)
        
    Returns:
        HTML string for combat results grid
    """
    stats = decoded_data.get("characterStatisticsByFileName", {}).get(mission_id, {})
    if not stats:
        return f"<p>{t('tracker.combat.mission_unavailable')}</p>"

    # Calculate totals per category using central mapping
    category_totals = {}
    for category, subcats in KILL_MAPPING.items():
        total = sum(int(stats.get(key, 0)) for key in subcats.values())
        category_totals[category] = total

    return _build_combat_results_html(stats, category_totals, game_directory)


def generate_campaign_summary_combat_results_html(decoded_campaign_data: dict, game_directory: str = None) -> str:
    """
    Generate cumulative combat results for entire campaign.
    
    Args:
        decoded_campaign_data: Campaign data from campaigns_decoded.json[campaign_name]
        game_directory: Path to IL-2 game directory (for icon paths)
        
    Returns:
        HTML string for combat results grid
    """
    stats_by_mission = decoded_campaign_data.get("characterStatisticsByFileName", {})

    if not stats_by_mission:
        return f"<p>{t('tracker.combat.campaign_unavailable')}</p>"

    aggregated_kills = aggregate_kills_from_missions(stats_by_mission)
    by_category = aggregated_kills.get("by_category", {})

    # Calculate category totals
    category_totals = {}
    for category, subcats in KILL_MAPPING.items():
        total = sum(by_category.get(category, {}).get(subcat, 0) for subcat in subcats.keys())
        category_totals[category] = total

    # Build aggregated stats dict for HTML builder
    aggregated_stats = {}
    for category, subcats in KILL_MAPPING.items():
        for subcat, key in subcats.items():
            aggregated_stats[key] = by_category.get(category, {}).get(subcat, 0)

    return _build_combat_results_html(aggregated_stats, category_totals, game_directory)


def _build_combat_results_html(stats: dict, category_totals: dict, game_directory: str = None) -> str:
    """
    Build combat results HTML grid (shared by mission and campaign summary).
    
    Args:
        stats: Statistics dict (mission or aggregated)
        category_totals: Pre-calculated category totals
        game_directory: Path to IL-2 game directory
        
    Returns:
        HTML string
    """
    html = []
    html.append('<div class="combat-results-grid">')

    # Category headers with icons and totals
    html.append('<div class="category-headers">')
    for category in KILL_MAPPING.keys():
        icon_file = f"icon_{category.lower()}.png"
        if game_directory:
            icon_path = "file:///" + game_directory.replace("\\", "/") + "/data/swf/CampaignRanksAwards/Misc/" + icon_file
        else:
            icon_path = f"data/swf/CampaignRanksAwards/Misc/{icon_file}"

        total = category_totals.get(category, 0)
        category_label = _category_label(category)
        html.append(f'<div class="category-col">')
        html.append(f'  <div class="category-icon"><img src="{icon_path}" width="48" height="48"/></div>')
        html.append(f'  <div class="category-total">{total}</div>')
        html.append(f'  <div class="category-name">{category_label}</div>')
        html.append(f'</div>')
    html.append('</div>')

    # Subcategories - BUILD COLUMNS, NOT ROWS!
    html.append('<div class="subcategory-columns">')

    for category, subcats in KILL_MAPPING.items():
        html.append('<div class="subcat-column">')
        for subcat, key in subcats.items():
            count = int(stats.get(key, 0))
            subcat_label = _subcategory_label(category, subcat)
            html.append(f'<div class="subcat-row">')
            html.append(f'  <span class="subcat-name">{subcat_label}</span>')
            html.append(f'  <span class="subcat-value">{count}</span>')
            html.append(f'</div>')
        html.append('</div>')

    html.append('</div>')
    html.append('</div>')

    return "\n".join(html)
