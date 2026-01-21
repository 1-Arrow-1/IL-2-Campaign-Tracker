"""
IL-2 Campaign Tracker - Combat Results HTML Generator

Provides:
1. generate_mission_combat_results_html() - HTML for single mission
2. generate_campaign_summary_combat_results_html() - HTML for campaign summary
"""

from utils.combat_results import KILL_MAPPING, aggregate_kills_from_missions
from utils.i18n import t

CATEGORY_I18N_KEYS = {
    "Aircraft": "combat.category.aircraft",
    "Vehicles": "combat.category.vehicles",
    "Railroad": "combat.category.railroad",
    "Armaments": "combat.category.armaments",
    "Buildings": "combat.category.buildings",
    "Marine": "combat.category.marine",
}

SUBCATEGORY_I18N_KEYS = {
    "Light": "combat.subcategory.light",
    "Medium": "combat.subcategory.medium",
    "Heavy": "combat.subcategory.heavy",
    "Parked": "combat.subcategory.parked",
    "Balloons": "combat.subcategory.balloons",
    "Transport": "combat.subcategory.transport",
    "Armored (Light)": "combat.subcategory.armored_light",
    "Armored (Medium)": "combat.subcategory.armored_medium",
    "Armored (Heavy)": "combat.subcategory.armored_heavy",
    "Locomotives": "combat.subcategory.locomotives",
    "Railroad Cars": "combat.subcategory.railroad_cars",
    "Station Facilities": "combat.subcategory.facilities",
    "Machine Guns": "combat.subcategory.machine_guns",
    "Cannons": "combat.subcategory.cannons",
    "AAA Guns": "combat.subcategory.aaa_guns",
    "Rocket Launchers": "combat.subcategory.rocket_launchers",
    "Searchlights": "combat.subcategory.searchlights",
    "Radars": "combat.subcategory.radars",
    "Residential Buildings": "combat.subcategory.residential",
    "Facilities": "combat.subcategory.facilities",
    "Bridges": "combat.subcategory.bridges",
    "Cargo": "combat.subcategory.cargo",
    "Submarines": "combat.subcategory.submarines",
    "Destroyers": "combat.subcategory.destroyers",
}


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
        return f"<p>{t('pdf.message.combat_data_not_available_mission', mission=mission_id)}</p>"

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
        return f"<p>{t('pdf.message.combat_data_not_available')}</p>"

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
        html.append(f'<div class="category-col">')
        html.append(f'  <div class="category-icon"><img src="{icon_path}" width="48" height="48"/></div>')
        html.append(f'  <div class="category-total">{total}</div>')
        category_key = CATEGORY_I18N_KEYS.get(category)
        category_label = t(category_key) if category_key else category
        html.append(f'  <div class="category-name">{category_label}</div>')
        html.append(f'</div>')
    html.append('</div>')

    # Subcategories - BUILD COLUMNS, NOT ROWS!
    html.append('<div class="subcategory-columns">')

    for category, subcats in KILL_MAPPING.items():
        html.append('<div class="subcat-column">')
        for subcat, key in subcats.items():
            count = int(stats.get(key, 0))
            html.append(f'<div class="subcat-row">')
            subcat_key = SUBCATEGORY_I18N_KEYS.get(subcat)
            subcat_label = t(subcat_key) if subcat_key else subcat
            html.append(f'  <span class="subcat-name">{subcat_label}</span>')
            html.append(f'  <span class="subcat-value">{count}</span>')
            html.append(f'</div>')
        html.append('</div>')

    html.append('</div>')
    html.append('</div>')

    return "\n".join(html)
