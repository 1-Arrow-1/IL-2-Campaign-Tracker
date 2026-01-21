"""
IL-2 Campaign Tracker - Locale Configuration Management

Manages user locale preferences:
- Load/save user's preferred language
- Integrate with installer language selection
- Provide fallback defaults

Storage:
- JSON file: campaign_tracker_settings.json
- Location: Same directory as executable/script
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional

from utils.pathing import get_base_path

logger = logging.getLogger(__name__)

SETTINGS_FILE = "campaign_tracker_settings.json"
LOCALE_OVERRIDE_FILE = "locale_setting.txt"  # From installer
LOCALE_ENV_VAR = "CAMPAIGN_TRACKER_LOCALE"


def get_settings_path() -> Path:
    """Get path to settings file."""
    base_dir = get_base_path(__file__)
    return base_dir / SETTINGS_FILE


def get_locale_override_path() -> Path:
    """Get path to installer locale override file."""
    base_dir = get_base_path(__file__)
    return base_dir / LOCALE_OVERRIDE_FILE


def load_settings() -> dict:
    """
    Load settings from JSON file.
    
    Returns:
        Settings dictionary (empty if file doesn't exist)
    """
    settings_path = get_settings_path()
    
    if not settings_path.exists():
        logger.debug(f"Settings file not found: {settings_path}")
        return {}
    
    try:
        with open(settings_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            logger.debug(f"Loaded settings from {settings_path}")
            return data
    except (OSError, json.JSONDecodeError) as e:
        logger.error(f"Error loading settings: {e}")
        return {}


def save_settings(settings: dict) -> bool:
    """
    Save settings to JSON file.
    
    Args:
        settings: Settings dictionary to save
        
    Returns:
        True if successful, False otherwise
    """
    settings_path = get_settings_path()
    
    try:
        # Write to temporary file first
        tmp_path = settings_path.with_suffix('.tmp')
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
        
        # Atomic replace
        tmp_path.replace(settings_path)
        logger.debug(f"Saved settings to {settings_path}")
        return True
    except OSError as e:
        logger.error(f"Error saving settings: {e}")
        return False


def get_user_locale() -> str:
    """
    Get user's preferred locale.
    
    Priority:
    1. Installer override file (locale_setting.txt)
    2. Settings file (locale key)
    3. Default fallback ('en')
    
    Returns:
        Locale code (e.g., 'en', 'de')
    """
    # 1. Check installer override
    override_path = get_locale_override_path()
    if override_path.exists():
        try:
            locale = override_path.read_text(encoding='utf-8').strip()
            if locale:
                logger.info(f"Using installer locale: {locale}")
                
                # Migrate to settings file and remove override
                settings = load_settings()
                settings['locale'] = locale
                save_settings(settings)
                
                try:
                    override_path.unlink()
                    logger.debug("Removed installer locale override file")
                except OSError:
                    pass
                
                return locale
        except OSError as e:
            logger.warning(f"Error reading locale override: {e}")
    
    # 2. Check settings file
    settings = load_settings()
    locale = settings.get('locale')
    if locale:
        logger.debug(f"Using settings locale: {locale}")
        return locale
    
    # 3. Default fallback
    logger.debug("Using default locale: en")
    return 'en'


def resolve_locale(explicit_locale: Optional[str] = None) -> str:
    """
    Resolve locale based on runtime precedence.

    Priority:
    1. Explicit locale (runtime override)
    2. CAMPAIGN_TRACKER_LOCALE environment variable
    3. User locale (installer override / settings.json)
    4. Fallback ('en')
    """
    if explicit_locale:
        return explicit_locale.strip().lower()

    env_locale = os.environ.get(LOCALE_ENV_VAR, "").strip().lower()
    if env_locale:
        logger.info(f"Using locale from {LOCALE_ENV_VAR}: {env_locale}")
        return env_locale

    return get_user_locale()


def set_user_locale(locale: str) -> bool:
    """
    Set user's preferred locale.
    
    Args:
        locale: Locale code to set (e.g., 'en', 'de')
        
    Returns:
        True if successful, False otherwise
    """
    settings = load_settings()
    settings['locale'] = locale
    
    if save_settings(settings):
        logger.info(f"User locale set to: {locale}")
        return True
    else:
        logger.error(f"Failed to set user locale: {locale}")
        return False


def get_system_locale() -> Optional[str]:
    """
    Try to detect system locale.
    
    Returns:
        Best-guess locale code or None
    """
    import locale as locale_module
    
    try:
        # Get system locale
        system_locale = locale_module.getdefaultlocale()[0]
        if not system_locale:
            return None
        
        # Extract language code (e.g., 'de_DE' → 'de')
        lang_code = system_locale.split('_')[0].lower()
        
        # Map common language codes
        supported = {
            'en': 'en',
            'de': 'de',
            'fr': 'fr',
            'es': 'es',
            'ru': 'ru',
            'pl': 'pl',
            'zh': 'zh',
        }
        
        return supported.get(lang_code)
    except Exception as e:
        logger.debug(f"Could not detect system locale: {e}")
        return None


def auto_detect_locale() -> str:
    """
    Auto-detect best locale to use.
    
    Priority:
    1. User preference (if set)
    2. System locale (if supported)
    3. Default fallback ('en')
    
    Returns:
        Locale code
    """
    # Check user preference first
    settings = load_settings()
    user_locale = settings.get('locale')
    if user_locale:
        return user_locale
    
    # Try system locale
    system_locale = get_system_locale()
    if system_locale:
        logger.info(f"Auto-detected system locale: {system_locale}")
        return system_locale
    
    # Fallback
    return 'en'
