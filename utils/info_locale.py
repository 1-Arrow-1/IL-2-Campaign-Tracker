import logging
import regex

from pathlib import Path
from typing import List, Optional, Tuple

from utils.supported_locales import APP_TO_IL2_LOCALE

logger = logging.getLogger(__name__)

TRACKER_SECTION_HEADER_PATTERN = (
    r'(?:Mission Debriefings<br>|<[ub]>Mission Debriefings</[ub]>|<[ub]>Events</[ub]>)'
)
TRACKER_SECTION_PATTERN = f"{TRACKER_SECTION_HEADER_PATTERN}[\\s\\S]*$"


def _build_tracker_section_pattern(extra_headers: Optional[List[str]] = None) -> str:
    if not extra_headers:
        return TRACKER_SECTION_PATTERN

    localized_patterns: list[str] = []
    for header in extra_headers:
        if not header:
            continue
        escaped = regex.escape(header)
        localized_patterns.append(f"{escaped}<br>")
        localized_patterns.append(f"<[ub]>{escaped}</[ub]>")

    if not localized_patterns:
        return TRACKER_SECTION_PATTERN

    extra_pattern = "|".join(localized_patterns)
    header_pattern = f"(?:{TRACKER_SECTION_HEADER_PATTERN}|{extra_pattern})"
    return f"{header_pattern}[\\s\\S]*$"

def find_all_info_locale_files(campaign_path: Path) -> List[Path]:
    """
    Find all info.locale=*.txt files in a campaign folder.
    
    IL-2 loads the locale file matching the user's language setting.
    To ensure tracker content is visible regardless of language,
    we need to write to all existing locale files.
   
    Args:
        campaign_path: Path to the campaign folder
        
    Returns:
        List of paths to info.locale=*.txt files (e.g., eng, ger, rus, fra, spa, chs)
    """
    return list(campaign_path.glob("info.locale=*.txt"))


def ensure_info_locale_files(
    campaign_path: Path,
    supported_locales: List[str],
) -> Tuple[List[Path], List[Path], Optional[Path]]:
    """
    Ensure all info.locale files exist for the supported locales.

    Returns:
        Tuple of (all_locale_files, created_files, source_file_used)
    """
    existing_files = {path.name: path for path in find_all_info_locale_files(campaign_path)}
    if not existing_files:
        logger.warning("No info.locale files found in %s", campaign_path)
        return [], [], None

    preferred_source = campaign_path / "info.locale=eng.txt"
    source_file = preferred_source if preferred_source.exists() else next(iter(existing_files.values()))

    created_files: list[Path] = []
    source_bytes = source_file.read_bytes()

    for locale in supported_locales:
        il2_locale = APP_TO_IL2_LOCALE.get(locale)
        if not il2_locale:
            logger.warning("No IL-2 locale mapping for '%s'", locale)
            continue

        target_name = f"info.locale={il2_locale}.txt"
        if target_name in existing_files:
            continue

        target_file = campaign_path / target_name
        target_file.write_bytes(source_bytes)
        created_files.append(target_file)
        existing_files[target_name] = target_file
        logger.info("Created missing locale file %s from %s", target_file.name, source_file.name)

    return list(existing_files.values()), created_files, source_file

def detect_info_locale_encoding(raw: bytes) -> str:
    if raw.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return "utf-16"
    return "utf-8"


def decode_and_clean_info_locale(
    raw: bytes,
    extra_headers: Optional[List[str]] = None,
) -> tuple[str, str, str]:
    encoding = detect_info_locale_encoding(raw)
    content = raw.decode(encoding)
    section_pattern = _build_tracker_section_pattern(extra_headers)

    cleaned = regex.sub(
        section_pattern,
        '',
        content,
        flags=regex.IGNORECASE,
    )

    cleaned = cleaned.rstrip()
    while cleaned.endswith('<br>'):
        cleaned = cleaned[:-4].rstrip()

    return cleaned, encoding, content


def apply_tracker_content(
    raw: bytes,
    content_html: str,
    extra_headers: Optional[List[str]] = None,
) -> tuple[str, str, str, str]:
    """
    Remove old tracker content and append new content.

    Returns:
        Tuple of (updated_content, encoding, original_content, cleaned_content)
    """
    cleaned, encoding, original = decode_and_clean_info_locale(raw, extra_headers=extra_headers)
    updated = cleaned
    if content_html:
        updated = f"{cleaned}<br><br>{content_html}"
    return updated, encoding, original, cleaned
