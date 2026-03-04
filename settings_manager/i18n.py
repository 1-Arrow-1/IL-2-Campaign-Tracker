"""
IL-2 Settings Manager - Internationalization

Provides translation support for the Settings Manager GUI.
Uses the unified i18n system from utils.i18n with settings-specific extensions.
"""

import json
from pathlib import Path
from typing import Dict, Optional

from utils.i18n import t as i18n_t, init_i18n, set_locale as i18n_set_locale, get_locale as i18n_get_locale
from utils.name_normalization import name_to_i18n_key, country_code_for_rank
from settings_manager.config.paths import LOCALES_DIR


# Language display names
LANGUAGE_NAMES = {
    'en': 'English',
    'de': 'Deutsch',
    'es': 'Español',
    'fr': 'Français',
    'pl': 'Polski',
    'ru': 'Русский',
    'zh': '简体中文',
}


class Translator:
    """
    Translator wrapper for Settings Manager.

    Delegates to the unified i18n system (utils.i18n) while providing
    settings-specific functionality like rank name translation.
    """

    SUPPORTED_LOCALES = list(LANGUAGE_NAMES.keys())

    def __init__(self):
        self.locale_data: Dict[str, dict] = {}
        # i18n is already initialized by main.py with the user's locale before Translator is created
        self.current_locale = i18n_get_locale()

    def _load_locale_data(self, locale: str) -> dict:
        """Load full locale JSON for rank translations."""
        if locale in self.locale_data:
            return self.locale_data[locale]
        data: dict = {}
        filepath = LOCALES_DIR / f"{locale}.json"
        if filepath.exists():
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError):
                data = {}
        self.locale_data[locale] = data
        return data

    def _lookup_rank_translation(self, locale: str, key: str) -> Optional[str]:
        data = self._load_locale_data(locale)
        return data.get("progression", {}).get("ranks", {}).get(key)

    def translate_rank_name(self, name: str, country: Optional[str]) -> str:
        """Translate rank name using locale files with fallback to English."""
        if not name:
            return name

        base_key = name_to_i18n_key(name)
        country_code = country_code_for_rank(country)
        keys = []
        if country_code:
            keys.append(f"{country_code}_{base_key}")
        keys.append(base_key)

        for locale in (self.current_locale, 'en'):
            for key in keys:
                translated = self._lookup_rank_translation(locale, key)
                if translated:
                    return translated

        return name

    def set_locale(self, locale: str) -> None:
        """Set current locale."""
        if locale in self.SUPPORTED_LOCALES:
            self.current_locale = locale
            i18n_set_locale(locale)

    def t(self, key: str, **kwargs) -> str:
        """
        Translate key to current locale with optional formatting.

        Converts old settings_manager keys to new dot-notation format:
        - "app_title" → "settings_manager.app_title"
        - "btn_ok" → "settings_manager.button.ok"
        - "msg_save_success" → "settings_manager.message.save_success"

        Args:
            key: Translation key (with or without settings_manager prefix)
            **kwargs: Format arguments for string interpolation

        Returns:
            Translated string with fallback to English, then to key itself
        """
        # Convert legacy flat keys to nested dot-notation
        if '.' not in key:
            # Map old keys to new structure
            if key.startswith('tab_'):
                new_key = f"settings_manager.tab.{key[4:]}"
            elif key.startswith('lbl_'):
                new_key = f"settings_manager.label.{key[4:]}"
            elif key.startswith('btn_'):
                new_key = f"settings_manager.button.{key[4:]}"
            elif key.startswith('msg_'):
                new_key = f"settings_manager.message.{key[4:]}"
            elif key.startswith('err_'):
                new_key = f"settings_manager.error.{key[4:]}"
            elif key.startswith('dlg_'):
                new_key = f"settings_manager.dialog.{key[4:]}"
            elif key.startswith('tooltip_'):
                new_key = f"settings_manager.tooltip.{key[8:]}"
            else:
                new_key = f"settings_manager.{key}"
        else:
            # Already in dot-notation, check if it needs settings_manager prefix
            if not key.startswith('settings_manager.'):
                new_key = f"settings_manager.{key}"
            else:
                new_key = key

        # Use unified i18n system
        return i18n_t(new_key, **kwargs)

    def get_language_options(self) -> Dict[str, str]:
        """Return dict of locale_code -> display_name."""
        return LANGUAGE_NAMES.copy()
