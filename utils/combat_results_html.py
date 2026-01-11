"""
IL-2 Campaign Tracker - Combat Results HTML Generator

Provides:
1. generate_mission_combat_results_html() - HTML for single mission
2. generate_campaign_summary_combat_results_html() - HTML for campaign summary
"""

from collections import defaultdict

from utils.combat_results import KILL_MAPPING


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
        return "<p>Combat data not available for this mission.</p>"

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
        return "<p>No combat data available.</p>"

    # Aggregate ALL missions
    totals = defaultdict(lambda: defaultdict(int))
    for mission_id, mission_stats in stats_by_mission.items():
        if not isinstance(mission_stats, dict):
            continue
        for category, subcats in KILL_MAPPING.items():
            for subcat, key in subcats.items():
                totals[category][subcat] += int(mission_stats.get(key, 0))

    # Calculate category totals
    category_totals = {}
    for category, subcats in KILL_MAPPING.items():
        total = sum(totals[category].get(subcat, 0) for subcat in subcats.keys())
        category_totals[category] = total

    # Build aggregated stats dict for HTML builder
    aggregated_stats = {}
    for category, subcats in KILL_MAPPING.items():
        for subcat, key in subcats.items():
            aggregated_stats[key] = totals[category].get(subcat, 0)

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
        html.append(f'  <div class="category-name">{category}</div>')
        html.append(f'</div>')
    html.append('</div>')

    # Subcategories - BUILD COLUMNS, NOT ROWS!
    html.append('<div class="subcategory-columns">')

    for category, subcats in KILL_MAPPING.items():
        html.append('<div class="subcat-column">')
        for subcat, key in subcats.items():
            count = int(stats.get(key, 0))
            html.append(f'<div class="subcat-row">')
            html.append(f'  <span class="subcat-name">{subcat}</span>')
            html.append(f'  <span class="subcat-value">{count}</span>')
            html.append(f'</div>')
        html.append('</div>')

    html.append('</div>')
    html.append('</div>')

    return "\n".join(html)
