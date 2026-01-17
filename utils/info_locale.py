import regex

from pathlib import Path
from typing import List

INFO_LOCALE_TO_I18N = {
    "eng": "en",
    "ger": "de",
    "fra": "fr",
    "spa": "es",
    "pol": "pl",
    "rus": "ru",
    "chs": "zh_hans",
    "cht": "zh_hant",
}

I18N_TO_INFO_LOCALE = {value: key for key, value in INFO_LOCALE_TO_I18N.items()}

TRACKER_SECTION_HEADER_PATTERN = (
    r'(?:Mission Debriefings<br>|<[ub]>Mission Debriefings</[ub]>|<[ub]>Events</[ub]>)'
)
TRACKER_SECTION_PATTERN = f"{TRACKER_SECTION_HEADER_PATTERN}[\\s\\S]*$"

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


def normalize_locale_code(locale: str) -> str:
    return locale.strip().lower().replace("-", "_")


def map_info_locale_to_i18n(locale_code: str) -> str:
    normalized = normalize_locale_code(locale_code)
    return INFO_LOCALE_TO_I18N.get(normalized, normalized)


def map_i18n_to_info_locale(locale_code: str) -> str:
    normalized = normalize_locale_code(locale_code)
    return I18N_TO_INFO_LOCALE.get(normalized, normalized)


def get_info_locale_code(info_file: Path) -> str:
    match = regex.search(r"info\.locale=([^\.]+)\.txt$", info_file.name, flags=regex.IGNORECASE)
    if not match:
        return ""
    return match.group(1)


def get_supported_locales(locales_dir: Path) -> List[str]:
    locales = []
    if not locales_dir.exists():
        return locales
    for path in locales_dir.glob("*.json"):
        locales.append(path.stem)
    return sorted(set(locales))

def detect_info_locale_encoding(raw: bytes) -> str:
    if raw.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return "utf-16"
    return "utf-8"


def decode_and_clean_info_locale(raw: bytes) -> tuple[str, str, str]:
    encoding = detect_info_locale_encoding(raw)
    content = raw.decode(encoding)

    cleaned = regex.sub(
        TRACKER_SECTION_PATTERN,
        '',
        content,
        flags=regex.IGNORECASE,
    )

    cleaned = cleaned.rstrip()
    while cleaned.endswith('<br>'):
        cleaned = cleaned[:-4].rstrip()

    return cleaned, encoding, content


def verify_info_locale_files(campaign_path: Path) -> dict[str, bool]:
    """
    Verify that each info.locale file contains locale-specific tracker text.

    Returns a map of filename -> contains localized tracker heading.
    """
    from utils.i18n import get_locale, load_locale, t

    results: dict[str, bool] = {}
    locale_files = find_all_info_locale_files(campaign_path)
    previous_locale = get_locale()

    try:
        for info_file in locale_files:
            locale_code = map_info_locale_to_i18n(get_info_locale_code(info_file))
            load_locale(locale=locale_code)
            markers = [
                t("tracker.debriefings.heading"),
                t("tracker.events.heading"),
                t("tracker.debriefings.flight_log"),
            ]
            raw = info_file.read_bytes()
            encoding = detect_info_locale_encoding(raw)
            content = raw.decode(encoding, errors="ignore")
            results[info_file.name] = any(marker and marker in content for marker in markers)
    finally:
        load_locale(locale=previous_locale)

    return results
