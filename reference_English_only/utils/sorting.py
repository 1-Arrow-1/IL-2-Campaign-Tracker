import re
from typing import Tuple


def smart_mission_sort_key(mission_id: str) -> Tuple[int, str]:
    """
    Smart sorting for mission IDs
    - Numeric IDs (01, 02, 10): Sort numerically
    - Date-based IDs (1943-07-04a): Sort alphabetically (ISO format sorts correctly)
    - Mixed (01a, 02b): Sort by number then suffix
    """
    # If it's purely numeric, convert to int
    if mission_id.isdigit():
        return (int(mission_id), "")

    # Try to extract leading digits (handles "01a", "02b", "1943-07-04a", etc.)
    match = re.match(r'^(\d+)(.*)$', mission_id)
    if match:
        return (int(match.group(1)), match.group(2))

    # No leading digits - sort alphabetically (works for ISO dates like "1943-07-04a")
    # Use large number to put these after pure numeric missions
    return (999999, mission_id)
