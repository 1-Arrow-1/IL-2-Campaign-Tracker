from collections import defaultdict

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
        "Residential<br>Buildings": "killResidentalBuilding",
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


def generate_mission_combat_results_html(mission_id: str, decoded_data: dict, game_directory: str = None) -> str:
    """
    Creates Combat-Results table for a specific mission (for PDF debrief).
    Matches the in-game layout with icons and shows ALL categories (even 0 kills).
    """
    stats = decoded_data.get("characterStatisticsByFileName", {}).get(mission_id, {})
    if not stats:
        return "<p>Combat data not available for this mission.</p>"

    # Calculate totals per category
    category_totals = {}
    for category, subcats in KILL_MAPPING.items():
        total = sum(stats.get(key, 0) for key in subcats.values())
        category_totals[category] = total

    # Build HTML matching screenshot layout
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

        total = category_totals[category]
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
            count = stats.get(key, 0)
            html.append(f'<div class="subcat-row">')
            html.append(f'  <span class="subcat-name">{subcat}</span>')
            html.append(f'  <span class="subcat-value">{count}</span>')
            html.append(f'</div>')
        html.append('</div>')

    html.append('</div>')
    html.append('</div>')

    return "\n".join(html)


def generate_campaign_summary_combat_results_html(decoded_campaign_data: dict, game_directory: str = None) -> str:
    """
    Generate cumulative combat results for entire campaign.
    decoded_campaign_data should be the campaign data from campaigns_decoded.json[campaign_name]
    """
    stats_by_mission = decoded_campaign_data.get("characterStatisticsByFileName", {})

    if not stats_by_mission:
        return "<p>No combat data available.</p>"

    # Aggregate ALL missions
    totals = defaultdict(lambda: defaultdict(int))
    for mission_id, mission_stats in stats_by_mission.items():
        for category, subcats in KILL_MAPPING.items():
            for subcat, key in subcats.items():
                totals[category][subcat] += mission_stats.get(key, 0)

    # Calculate category totals
    category_totals = {}
    for category, subcats in KILL_MAPPING.items():
        total = sum(totals[category].get(subcat, 0) for subcat in subcats.keys())
        category_totals[category] = total

    # Build HTML (same layout as mission combat results)
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
            count = totals[category].get(subcat, 0)
            html.append(f'<div class="subcat-row">')
            html.append(f'  <span class="subcat-name">{subcat}</span>')
            html.append(f'  <span class="subcat-value">{count}</span>')
            html.append(f'</div>')
        html.append('</div>')

    html.append('</div>')
    html.append('</div>')

    return "\n".join(html)
