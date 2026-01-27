"""
IL-2 Campaign Tracker - Name Normalization Utilities

Provides helper functions for converting display names to i18n keys
and resolving country codes for rank translations.

These utilities are used across:
- Event generation (step3_generate_events.py)
- Popup displays (popups_min.py)
- Settings manager (settings_manager/i18n.py)
- String validation (campaign_service_record/utils/check_rendered_strings.py)
"""

import re
from typing import Optional


def name_to_i18n_key(name: str) -> str:
    """
    Convert display name to i18n key format.

    Transforms human-readable names into standardized lowercase underscore
    format suitable for use as translation keys in locale JSON files.

    Examples:
        >>> name_to_i18n_key("Light & Medium Bombers")
        'light_and_medium_bombers'
        >>> name_to_i18n_key("Officer's Mess (Day)")
        'officers_mess_day'
        >>> name_to_i18n_key("Iron Cross, 2nd Class")
        'iron_cross_2nd_class'

    Args:
        name: Human-readable display name (award name, rank name, etc.)

    Returns:
        Normalized key string (lowercase, underscores, no special chars)
    """
    value = name.lower()

    # Normalize various quote styles
    value = value.replace("'", "'").replace("'", "'")
    value = value.replace("'", "")

    # Replace operators with "and"
    value = value.replace("&", "and")
    value = value.replace("+", "and")

    # Remove punctuation
    value = re.sub(r"[,\.\"]", "", value)

    # Convert parentheses to underscores (for descriptions)
    value = re.sub(r"\s*\(\s*", "_", value)
    value = re.sub(r"\s*\)\s*", "", value)

    # Remove ellipsis
    value = value.replace("…", "")

    # Replace whitespace with underscores
    value = re.sub(r"\s+", "_", value)

    # Collapse multiple underscores
    value = re.sub(r"_+", "_", value)

    # Remove leading/trailing underscores
    return value.strip("_")


def country_code_for_rank(country: Optional[str]) -> str:
    """
    Get country code prefix for rank i18n keys.

    Maps full country names to their IL-2 country code abbreviations
    used in translation keys for ranks and awards.

    Examples:
        >>> country_code_for_rank("Germany")
        'ger'
        >>> country_code_for_rank("Soviet Union")
        'vvs'
        >>> country_code_for_rank("Britain")
        'raf'

    Args:
        country: Full country name (case-insensitive)

    Returns:
        Country code prefix:
        - "ger" for Germany
        - "raf" for Britain/UK/Great Britain
        - "usaaf" for USA/United States
        - "vvs" for Soviet Union/USSR/Russia
        - "" (empty string) for unknown countries
    """
    normalized = (country or "").lower().strip()

    if normalized == "germany":
        return "ger"
    if normalized in {"britain", "uk", "great britain"}:
        return "raf"
    if normalized in {"usa", "united states", "united states of america", "us"}:
        return "usaaf"
    if normalized in {"soviet union", "ussr", "russia"}:
        return "vvs"

    return ""
