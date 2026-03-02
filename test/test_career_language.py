"""
Unit tests for per-career language override helpers in utils.locale_config.

Tests cover:
  - get_career_effective_locale: no override, explicit override, "default" override,
    invalid override (not in VALID_CAREER_OVERRIDE_LOCALES)
  - set_career_language_override + get_career_language_overrides round-trip
  - Clearing an override with None
"""

import unittest
from unittest.mock import patch, call


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _settings(overrides=None, locale='en'):
    """Build a minimal settings dict for mocking."""
    s = {'locale': locale}
    if overrides is not None:
        s['careerLanguageOverrides'] = overrides
    return s


# ---------------------------------------------------------------------------
# Tests: get_career_effective_locale
# ---------------------------------------------------------------------------

class TestGetCareerEffectiveLocale(unittest.TestCase):

    def test_no_override_returns_global_locale(self):
        """When no override is set, return the global locale."""
        settings = _settings(locale='en')
        with patch('utils.locale_config.load_settings', return_value=settings), \
             patch('utils.locale_config.resolve_locale', return_value='en'):
            from utils.locale_config import get_career_effective_locale
            result = get_career_effective_locale('12345')
        self.assertEqual(result, 'en')

    def test_no_override_returns_global_locale_de(self):
        """Global locale 'de' is returned when no per-career override exists."""
        settings = _settings(locale='de')
        with patch('utils.locale_config.load_settings', return_value=settings), \
             patch('utils.locale_config.resolve_locale', return_value='de'):
            from utils.locale_config import get_career_effective_locale
            result = get_career_effective_locale('99')
        self.assertEqual(result, 'de')

    def test_explicit_override_de(self):
        """When override is 'de', return 'de' regardless of global locale."""
        settings = _settings(overrides={'42': 'de'}, locale='en')
        with patch('utils.locale_config.load_settings', return_value=settings), \
             patch('utils.locale_config.resolve_locale', return_value='en'):
            from utils.locale_config import get_career_effective_locale
            result = get_career_effective_locale('42')
        self.assertEqual(result, 'de')

    def test_explicit_override_ru(self):
        """When override is 'ru', return 'ru'."""
        settings = _settings(overrides={'7': 'ru'}, locale='en')
        with patch('utils.locale_config.load_settings', return_value=settings), \
             patch('utils.locale_config.resolve_locale', return_value='en'):
            from utils.locale_config import get_career_effective_locale
            result = get_career_effective_locale('7')
        self.assertEqual(result, 'ru')

    def test_default_override_falls_through_to_global(self):
        """When override is 'default', use the global locale."""
        settings = _settings(overrides={'5': 'default'}, locale='ru')
        with patch('utils.locale_config.load_settings', return_value=settings), \
             patch('utils.locale_config.resolve_locale', return_value='ru'):
            from utils.locale_config import get_career_effective_locale
            result = get_career_effective_locale('5')
        self.assertEqual(result, 'ru')

    def test_invalid_override_fr_falls_through_to_global(self):
        """Override 'fr' is not in VALID_CAREER_OVERRIDE_LOCALES, so fall back to global."""
        settings = _settings(overrides={'3': 'fr'}, locale='en')
        with patch('utils.locale_config.load_settings', return_value=settings), \
             patch('utils.locale_config.resolve_locale', return_value='en'):
            from utils.locale_config import get_career_effective_locale
            result = get_career_effective_locale('3')
        self.assertEqual(result, 'en')

    def test_career_id_as_int_string_normalized(self):
        """Career IDs are always compared as strings."""
        settings = _settings(overrides={'100': 'de'}, locale='en')
        with patch('utils.locale_config.load_settings', return_value=settings), \
             patch('utils.locale_config.resolve_locale', return_value='en'):
            from utils.locale_config import get_career_effective_locale
            # Pass as string (normal usage from aggregator str(root_career_id))
            result = get_career_effective_locale('100')
        self.assertEqual(result, 'de')


# ---------------------------------------------------------------------------
# Tests: set_career_language_override + get_career_language_overrides
# ---------------------------------------------------------------------------

class TestSetAndGetCareerLanguageOverride(unittest.TestCase):

    def test_round_trip_store_and_retrieve(self):
        """set_career_language_override stores value; get_career_language_overrides retrieves it."""
        saved = {}

        def fake_load():
            return dict(saved)

        def fake_save(s):
            saved.clear()
            saved.update(s)
            return True

        with patch('utils.locale_config.load_settings', side_effect=fake_load), \
             patch('utils.locale_config.save_settings', side_effect=fake_save):
            from utils.locale_config import (
                set_career_language_override,
                get_career_language_overrides,
            )
            result = set_career_language_override('55', 'de')
            self.assertTrue(result)
            overrides = get_career_language_overrides()

        self.assertEqual(overrides.get('55'), 'de')

    def test_clear_override_with_none(self):
        """set_career_language_override(id, None) removes the entry."""
        initial = {'careerLanguageOverrides': {'10': 'ru'}}
        saved = dict(initial)

        def fake_load():
            return dict(saved)

        def fake_save(s):
            saved.clear()
            saved.update(s)
            return True

        with patch('utils.locale_config.load_settings', side_effect=fake_load), \
             patch('utils.locale_config.save_settings', side_effect=fake_save):
            from utils.locale_config import (
                set_career_language_override,
                get_career_language_overrides,
            )
            set_career_language_override('10', None)
            overrides = get_career_language_overrides()

        self.assertNotIn('10', overrides)

    def test_clear_override_with_default_string(self):
        """set_career_language_override(id, 'default') removes the entry."""
        initial = {'careerLanguageOverrides': {'20': 'en'}}
        saved = dict(initial)

        def fake_load():
            return dict(saved)

        def fake_save(s):
            saved.clear()
            saved.update(s)
            return True

        with patch('utils.locale_config.load_settings', side_effect=fake_load), \
             patch('utils.locale_config.save_settings', side_effect=fake_save):
            from utils.locale_config import (
                set_career_language_override,
                get_career_language_overrides,
            )
            set_career_language_override('20', 'default')
            overrides = get_career_language_overrides()

        self.assertNotIn('20', overrides)

    def test_get_overrides_returns_empty_when_key_absent(self):
        """get_career_language_overrides returns {} when key not in settings."""
        settings = {'locale': 'en'}  # No careerLanguageOverrides key
        with patch('utils.locale_config.load_settings', return_value=settings):
            from utils.locale_config import get_career_language_overrides
            result = get_career_language_overrides()
        self.assertEqual(result, {})

    def test_get_overrides_handles_corrupted_value(self):
        """get_career_language_overrides returns {} when value is not a dict."""
        settings = {'locale': 'en', 'careerLanguageOverrides': 'bad_value'}
        with patch('utils.locale_config.load_settings', return_value=settings):
            from utils.locale_config import get_career_language_overrides
            result = get_career_language_overrides()
        self.assertEqual(result, {})


if __name__ == '__main__':
    unittest.main()
