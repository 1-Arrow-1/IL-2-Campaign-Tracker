"""
IL-2 Campaign Tracker - Internationalization (i18n) Helper

Provides translation functionality for all Python components:
- GUI (Tkinter)
- CLI messages
- Event generation
- PDF generation
- In-game text (info.locale files)

Usage:
    from campaign_service_record.utils.i18n import t, set_locale, get_locale
    
    # Set locale (once at startup)
    set_locale('de')  # or 'en', etc.
    
    # Translate strings
    t('ui.button.ok')  # → "OK" (en) or "OK" (de)
    t('ui.popup.promotion_message', rank='Hauptmann')  
    # → "Sie wurden zum Hauptmann befördert"
    
    # Get current locale
    current = get_locale()  # → 'de'
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from utils.supported_locales import (
    APP_TO_IL2_LOCALE,
    DEFAULT_LOCALE,
    IL2_TO_APP_LOCALE,
    get_locales_dir,
    get_supported_locales,
    normalize_locale,
)

logger = logging.getLogger(__name__)

# Global state
_current_locale: str = DEFAULT_LOCALE
_translations: Dict[str, Dict[str, Any]] = {}
_locales_dir: Optional[Path] = None
_initialized: bool = False


def _get_locales_dir() -> Path:
    """
    Get the locales directory path.
    
    Works for both script and PyInstaller EXE mode:
    - Script: PROJECT_ROOT/locales
    - EXE: Same directory as EXE (locales/ next to .exe)
    """
    global _locales_dir
    if _locales_dir is None:
        _locales_dir = get_locales_dir()
    return _locales_dir


def load_locale(locale: str) -> Dict[str, Any]:
    """
    Load translation file for given locale.
    
    Args:
        locale: Locale code ('en', 'de', etc.)
        
    Returns:
        Translation dictionary (empty dict if file not found)
    """
    locales_dir = _get_locales_dir()
    file_path = locales_dir / f'{locale}.json'
    
    if not file_path.exists():
        logger.warning(f"Translation file not found: {file_path}")
        return {}
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            logger.debug(f"Loaded locale '{locale}' from {file_path}")
            return data
    except (OSError, json.JSONDecodeError) as e:
        logger.error(f"Error loading locale '{locale}': {e}")
        return {}


def init_i18n(locale: str = DEFAULT_LOCALE, force_reload: bool = False):
    """
    Initialize i18n system with given locale.
    
    This loads the fallback (en) and requested locale into memory.
    Should be called once at application startup.
    
    Args:
        locale: Locale code to set
        force_reload: Force reload even if already initialized
    """
    global _initialized, _current_locale, _translations

    locale = normalize_locale(locale)
    
    if _initialized and not force_reload:
        if locale and locale != _current_locale:
            set_locale(locale)
        logger.debug(f"i18n already initialized (locale={_current_locale})")
        return
    
    # Load fallback (English) first
    _translations[DEFAULT_LOCALE] = load_locale(DEFAULT_LOCALE)
    
    if not _translations[DEFAULT_LOCALE]:
        logger.error("CRITICAL: English fallback translations not loaded!")
    
    # Load requested locale (if different from fallback)
    if locale != DEFAULT_LOCALE:
        _translations[locale] = load_locale(locale)
        if not _translations[locale]:
            logger.warning(f"Requested locale '{locale}' not available, using 'en' fallback")
            locale = DEFAULT_LOCALE
    
    _current_locale = locale
    _initialized = True
    logger.info(f"i18n initialized with locale='{locale}'")


def set_locale(locale: str):
    """
    Set current locale.
    
    If the locale hasn't been loaded yet, this will load it.
    
    Args:
        locale: Locale code ('en', 'de', etc.)
    """
    global _current_locale, _translations
    
    if not locale:
        return

    locale = normalize_locale(locale)

    # Ensure fallback is always loaded
    if DEFAULT_LOCALE not in _translations:
        _translations[DEFAULT_LOCALE] = load_locale(DEFAULT_LOCALE)
    
    # Load requested locale if not already loaded
    if locale not in _translations:
        _translations[locale] = load_locale(locale)
        if not _translations[locale]:
            logger.warning(f"Locale '{locale}' not available, staying with '{_current_locale}'")
            return
    
    _current_locale = locale
    logger.debug(f"Locale set to '{locale}'")


def get_locale() -> str:
    """
    Get current locale code.
    
    Returns:
        Current locale code (e.g., 'en', 'de')
    """
    return _current_locale


def get_loaded_locales() -> list[str]:
    """
    Get list of locales currently loaded in memory.

    Returns:
        List of locale codes.
    """
    return sorted(_translations.keys())


def get_il2_locale_code() -> str:
    """
    Get IL-2 locale code for current app locale.
    
    Returns:
        IL-2 locale code (e.g., 'eng', 'ger')
    """
    return APP_TO_IL2_LOCALE.get(_current_locale, 'eng')


def _get_nested_value(data: Dict[str, Any], key_parts: list) -> Any:
    """
    Navigate nested dictionary using key parts.
    
    Args:
        data: Dictionary to navigate
        key_parts: List of key parts (e.g., ['ui', 'button', 'ok'])
        
    Returns:
        Value at nested location, or None if not found
    """
    current = data
    for part in key_parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


def t(key: str, **params) -> str:
    """
    Translate key with optional parameters.
    
    Fallback chain: current_locale → 'en' → '[key]'
    
    Args:
        key: Translation key (dot-separated, e.g., 'ui.button.ok')
        **params: Named parameters for string formatting
        
    Returns:
        Translated string with parameters substituted
        
    Examples:
        >>> t('ui.button.ok')
        'OK'
        
        >>> set_locale('de')
        >>> t('ui.popup.promotion_message', rank='Hauptmann')
        'Sie wurden zum Hauptmann befördert'
        
        >>> t('nonexistent.key')
        '[nonexistent.key]'
    """
    # Ensure initialized
    if not _translations:
        init_i18n()
    
    # Split nested key
    key_parts = key.split('.')
    
    # Try current locale
    trans = _get_nested_value(_translations.get(_current_locale, {}), key_parts)
    
    # If not found, try fallback (en)
    if not isinstance(trans, str):
        trans = _get_nested_value(_translations.get(DEFAULT_LOCALE, {}), key_parts)
    
    # If still not found, return placeholder
    if not isinstance(trans, str):
        logger.debug(f"Translation key not found: {key}")
        return f'[{key}]'
    
    # Parameter substitution
    if params:
        try:
            return trans.format(**params)
        except KeyError as e:
            # Missing parameter - return with error indicator
            logger.warning(f"Missing parameter for key '{key}': {e}")
            return f'{trans} [MISSING: {e}]'
        except Exception as e:
            logger.error(f"Error formatting key '{key}': {e}")
            return trans
    
    return trans


def get_available_locales() -> list[str]:
    """
    Get list of available locale codes.
    
    Returns:
        List of locale codes (e.g., ['en', 'de'])
    """
    return get_supported_locales()


def validate_translations() -> Dict[str, list]:
    """
    Validate that all locales have the same keys as English.
    
    Returns:
        Dictionary mapping locale codes to lists of missing keys
    """
    en_keys = _get_all_keys(_translations.get(DEFAULT_LOCALE, {}))
    missing_by_locale = {}
    
    for locale in get_available_locales():
        if locale == DEFAULT_LOCALE:
            continue
        
        if locale not in _translations:
            _translations[locale] = load_locale(locale)
        
        locale_keys = _get_all_keys(_translations.get(locale, {}))
        missing = en_keys - locale_keys
        
        if missing:
            missing_by_locale[locale] = sorted(missing)
    
    return missing_by_locale


def _get_all_keys(data: Dict[str, Any], prefix: str = '') -> set:
    """
    Recursively extract all keys from nested dictionary.
    
    Args:
        data: Dictionary to extract keys from
        prefix: Current key prefix (for recursion)
        
    Returns:
        Set of all dot-separated keys
    """
    keys = set()
    
    for key, value in data.items():
        full_key = f'{prefix}.{key}' if prefix else key
        
        if isinstance(value, dict):
            keys.update(_get_all_keys(value, full_key))
        else:
            keys.add(full_key)
    
    return keys


# Auto-initialize with English on import
init_i18n(DEFAULT_LOCALE)
