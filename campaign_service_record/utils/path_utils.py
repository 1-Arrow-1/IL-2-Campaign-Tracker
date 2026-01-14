"""
Path helpers for Campaign Service Record.

Provides shared logic for:
- Game directory resolution
- Rank/award image path construction
- USSR early/late folder selection
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Optional

USSR_TRANSITION_DATE = date(1943, 1, 6)

COUNTRY_FOLDER_MAP = {
    'germany': 'Germany',
    'britain': 'Britain',
    'usa': 'US',
    'united states': 'US',
    'united states of america': 'US',
}


def get_game_directory(mission_dates: dict) -> str:
    """Extract game directory from campaign_mission_dates.json data."""
    if not isinstance(mission_dates, dict):
        return ''
    game_dir = mission_dates.get('game_directory')
    return str(game_dir).strip() if game_dir else ''


def _parse_event_date(raw_date: Optional[str]) -> Optional[date]:
    """Parse event dates in multiple known formats."""
    if not raw_date:
        return None
    for fmt in ('%Y-%m-%d', '%d.%m.%Y'):
        try:
            return datetime.strptime(raw_date, fmt).date()
        except ValueError:
            continue
    return None


def resolve_country_folder(country: str, event_date: Optional[str]) -> str:
    """Resolve CampaignRanksAwards country folder, including USSR early/late."""
    if not country:
        return ''
    normalized = country.strip()
    normalized_lower = normalized.lower()
    if normalized_lower in {'ussr', 'soviet union'}:
        parsed_date = _parse_event_date(event_date)
        if parsed_date and parsed_date >= USSR_TRANSITION_DATE:
            return 'USSR/late'
        return 'USSR/early'
    return COUNTRY_FOLDER_MAP.get(normalized_lower, normalized)


def build_award_image_relative_path(country: str, image_name: Optional[str], event_date: Optional[str]) -> str:
    """Build relative path for rank/award images under CampaignRanksAwards."""
    if not image_name:
        return ''
    country_folder = resolve_country_folder(country, event_date)
    return f"CampaignRanksAwards/{country_folder}/{image_name}"


def build_award_large_image_relative_path(
    country: str,
    image_name: Optional[str],
    event_date: Optional[str]
) -> str:
    """Build relative path for large award images under CampaignRanksAwards."""
    if not image_name:
        return ''
    image_path = Path(image_name)
    suffix = image_path.suffix
    stem = image_path.stem if image_path.stem else image_name
    if stem.endswith('_big'):
        large_name = f"{stem}{suffix}"
    else:
        large_name = f"{stem}_big{suffix}"
    country_folder = resolve_country_folder(country, event_date)
    return f"CampaignRanksAwards/{country_folder}/{large_name}"


def build_misc_icon_relative_path(icon_filename: str) -> str:
    """Build relative path for Misc icons."""
    return f"CampaignRanksAwards/Misc/{icon_filename}"


def build_game_asset_url(relative_path: str) -> str:
    """Create API URL for game assets from a relative path."""
    if not relative_path:
        return ''
    normalized = relative_path.replace('\\', '/').lstrip('/')
    return f"/api/game_assets/{normalized}"
