"""
Utility modules copied from Campaign Tracker.

These provide core functionality for:
- Combat results calculation (kill mapping, scoring)
- HTML generation for combat results grids
- String formatting (safe filenames, etc.)
- Mission sorting (chronological order)
"""

from .combat_results import (
    calculate_kills_from_stats,
    calculate_total_air_kills_weighted,
    KILL_MAPPING
)
from .combat_results_html import generate_campaign_summary_combat_results_html
from .formatting import safe_campaign_filename
from .sorting import smart_mission_sort_key

__all__ = [
    'calculate_kills_from_stats',
    'calculate_total_air_kills_weighted',
    'KILL_MAPPING',
    'generate_campaign_summary_combat_results_html',
    'safe_campaign_filename',
    'smart_mission_sort_key'
]
