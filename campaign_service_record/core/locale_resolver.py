"""
Locale resolver for Campaign Service Record detail page.

This module provides locale resolution specifically for the detail page,
supporting per-campaign language overrides while respecting global settings.

The per-campaign override affects ONLY the detail page rendering.
PDFs, in-game debriefings, and other outputs use the global locale.
"""

import logging
from typing import Optional

from utils.locale_config import resolve_locale
from utils.supported_locales import normalize_locale

logger = logging.getLogger(__name__)

# Valid per-campaign locale overrides (detail page only)
VALID_DETAIL_PAGE_LOCALES = ('en', 'de', 'ru')


def resolve_detail_page_locale(
    campaign_name: str,
    campaign_data: Optional[dict] = None,
    data_loader=None
) -> str:
    """
    Resolve locale for Campaign Service Record detail page ONLY.

    Resolution order:
    1. If per-campaign override is 'en', 'de', or 'ru' -> use it (locked)
    2. Otherwise (Default/unset) -> use current global language (dynamic)

    This function must ONLY be called for detail page rendering.
    PDFs and debriefings must use resolve_locale() directly.

    Args:
        campaign_name: Campaign folder name
        campaign_data: Optional pre-loaded campaign mission dates dict.
                       If not provided, will load via data_loader.
        data_loader: Optional DataLoader instance for loading campaign data.

    Returns:
        Two-letter locale code (e.g., 'de', 'en', 'ru')
    """
    # Get campaign-specific data
    if campaign_data is None and data_loader is not None:
        campaign_data = data_loader.get_mission_dates_for_campaign(campaign_name)

    if campaign_data is None:
        campaign_data = {}

    # Check for per-campaign override
    override = campaign_data.get('detail_page_locale')

    if override:
        normalized = normalize_locale(override)
        if normalized in VALID_DETAIL_PAGE_LOCALES:
            logger.debug(
                "Campaign '%s' using locked locale: %s",
                campaign_name, normalized
            )
            return normalized
        else:
            logger.warning(
                "Campaign '%s' has invalid detail_page_locale '%s', using global",
                campaign_name, override
            )

    # Default: follow current global language (all 7 supported locales)
    # Debriefings HTML selection (en/de/ru only) is handled separately in routes.py
    global_locale = resolve_locale()

    logger.debug(
        "Campaign '%s' using global locale (Default): %s",
        campaign_name, global_locale
    )
    return global_locale
