"""
IL-2 Campaign Tracker - Supported Locale Registry

Single source of truth for supported locales and IL-2 locale mappings.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable, Optional

from utils.pathing import get_base_path

logger = logging.getLogger(__name__)

DEFAULT_LOCALE = "en"

# IL-2 locale code mapping to app locale codes
IL2_TO_APP_LOCALE = {
    "eng": "en",
    "ger": "de",
    "fra": "fr",
    "spa": "es",
    "rus": "ru",
    "pol": "pl",
    "chs": "zh",
}

# Reverse mapping (app → IL-2)
APP_TO_IL2_LOCALE = {v: k for k, v in IL2_TO_APP_LOCALE.items()}

_locales_dir: Optional[Path] = None
_supported_locales_cache: Optional[list[str]] = None


def get_locales_dir() -> Path:
    """
    Resolve the locales directory path.

    Works for both script and PyInstaller EXE mode:
    - Script: PROJECT_ROOT/locales
    - EXE: Same directory as EXE (locales/ next to .exe)
    """
    global _locales_dir
    if _locales_dir is not None:
        return _locales_dir

    import sys

    if getattr(sys, "frozen", False):
        _locales_dir = Path(sys.executable).parent / "locales"
        return _locales_dir

    current = Path(__file__).resolve()
    for parent in current.parents:
        candidate = parent / "locales"
        if candidate.exists():
            _locales_dir = candidate
            return _locales_dir

    _locales_dir = get_base_path(__file__) / "locales"
    return _locales_dir


def _scan_supported_locales(locales_dir: Path) -> list[str]:
    if not locales_dir.exists():
        return [DEFAULT_LOCALE]

    locales: list[str] = []
    for file_path in locales_dir.glob("*.json"):
        locale = file_path.stem.strip().lower()
        if locale:
            locales.append(locale)

    if DEFAULT_LOCALE not in locales:
        locales.append(DEFAULT_LOCALE)

    return sorted(set(locales))


def get_supported_locales(force_refresh: bool = False) -> list[str]:
    """
    Return the list of supported locale codes.
    """
    global _supported_locales_cache
    if _supported_locales_cache is None or force_refresh:
        _supported_locales_cache = _scan_supported_locales(get_locales_dir())
    return list(_supported_locales_cache)


def normalize_locale(locale: Optional[str], fallback: str = DEFAULT_LOCALE) -> str:
    """
    Normalize locale code and enforce supported locales.
    """
    if not locale:
        return fallback

    candidate = locale.strip().lower()
    if candidate.startswith("zh"):
        candidate = candidate.replace("_", "-")
        if candidate == "zh" or candidate.startswith("zh-"):
            candidate = "zh"
    supported = get_supported_locales()
    if candidate in supported:
        return candidate

    logger.warning("Unsupported locale '%s', falling back to '%s'", candidate, fallback)
    return fallback


def filter_supported_locales(locales: Iterable[str]) -> list[str]:
    supported = set(get_supported_locales())
    return [locale for locale in locales if locale in supported]
