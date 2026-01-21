import regex

from pathlib import Path
from typing import List, Optional

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
