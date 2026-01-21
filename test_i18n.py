#!/usr/bin/env python3
"""
IL-2 Campaign Tracker - i18n Validation Test

Checks translation completeness and parameter consistency.
"""

import sys
import json
from pathlib import Path
from typing import Dict, Set, List, Tuple

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from campaign_service_record.utils.i18n import get_available_locales, _get_all_keys, load_locale


def load_all_translations() -> Dict[str, Dict]:
    """Load all translation files."""
    translations = {}
    for locale in get_available_locales():
        translations[locale] = load_locale(locale)
    return translations


def extract_parameters(text: str) -> Set[str]:
    """Extract parameter names from translation string."""
    import re
    params = set(re.findall(r'\{(\w+)\}', text))
    return params


def get_value_at_key(data: Dict, key: str):
    """Get value at nested key."""
    parts = key.split('.')
    current = data
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


def test_translation_completeness() -> bool:
    """Test that all locales have the same keys as English."""
    print("=" * 70)
    print("TEST: Translation Completeness")
    print("=" * 70)
    
    translations = load_all_translations()
    
    if 'en' not in translations:
        print("❌ FATAL: English (en) translation file not found!")
        return False
    
    en_keys = _get_all_keys(translations['en'])
    print(f"\n✓ English has {len(en_keys)} keys")
    
    all_passed = True
    
    for locale in sorted(translations.keys()):
        if locale == 'en':
            continue
        
        locale_keys = _get_all_keys(translations[locale])
        missing = en_keys - locale_keys
        extra = locale_keys - en_keys
        
        print(f"\nLocale: {locale}")
        print(f"  Total keys: {len(locale_keys)}")
        
        if missing:
            print(f"  ❌ Missing {len(missing)} keys:")
            for key in sorted(missing)[:10]:  # Show first 10
                print(f"     - {key}")
            if len(missing) > 10:
                print(f"     ... and {len(missing) - 10} more")
            all_passed = False
        else:
            print(f"  ✓ No missing keys")
        
        if extra:
            print(f"  ⚠️  Extra {len(extra)} keys (not in English):")
            for key in sorted(extra)[:10]:
                print(f"     - {key}")
            if len(extra) > 10:
                print(f"     ... and {len(extra) - 10} more")
    
    return all_passed


def test_parameter_consistency() -> bool:
    """Test that parameter placeholders match across locales."""
    print("\n" + "=" * 70)
    print("TEST: Parameter Consistency")
    print("=" * 70)
    
    translations = load_all_translations()
    
    if 'en' not in translations:
        print("❌ FATAL: English (en) translation file not found!")
        return False
    
    en_keys = _get_all_keys(translations['en'])
    inconsistencies = []
    
    for key in sorted(en_keys):
        en_value = get_value_at_key(translations['en'], key)
        if not isinstance(en_value, str):
            continue
        
        en_params = extract_parameters(en_value)
        if not en_params:
            continue  # No parameters to check
        
        for locale in translations:
            if locale == 'en':
                continue
            
            locale_value = get_value_at_key(translations[locale], key)
            if locale_value is None:
                continue  # Missing key (caught by completeness test)
            
            locale_params = extract_parameters(locale_value)
            
            if en_params != locale_params:
                inconsistencies.append((key, locale, en_params, locale_params))
    
    if inconsistencies:
        print(f"\n❌ Found {len(inconsistencies)} parameter inconsistencies:\n")
        for key, locale, en_params, locale_params in inconsistencies[:10]:
            print(f"  Key: {key}")
            print(f"  Locale: {locale}")
            print(f"  English params: {sorted(en_params)}")
            print(f"  {locale} params: {sorted(locale_params)}")
            print()
        
        if len(inconsistencies) > 10:
            print(f"  ... and {len(inconsistencies) - 10} more")
        
        return False
    else:
        print("\n✓ All parameters consistent across locales")
        return True


def test_no_empty_values() -> bool:
    """Test that no translations have empty values."""
    print("\n" + "=" * 70)
    print("TEST: No Empty Values")
    print("=" * 70)
    
    translations = load_all_translations()
    empty_found = []
    
    for locale, data in translations.items():
        for key in _get_all_keys(data):
            value = get_value_at_key(data, key)
            if isinstance(value, str) and not value.strip():
                empty_found.append((locale, key))
    
    if empty_found:
        print(f"\n❌ Found {len(empty_found)} empty values:\n")
        for locale, key in empty_found[:10]:
            print(f"  [{locale}] {key}")
        if len(empty_found) > 10:
            print(f"  ... and {len(empty_found) - 10} more")
        return False
    else:
        print("\n✓ No empty values found")
        return True


def test_encoding() -> bool:
    """Test that all files are valid UTF-8."""
    print("\n" + "=" * 70)
    print("TEST: UTF-8 Encoding")
    print("=" * 70)
    
    locales_dir = PROJECT_ROOT / 'locales'
    all_passed = True
    
    for json_file in locales_dir.glob('*.json'):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                json.load(f)
            print(f"  ✓ {json_file.name} - Valid UTF-8")
        except UnicodeDecodeError as e:
            print(f"  ❌ {json_file.name} - Encoding error: {e}")
            all_passed = False
        except json.JSONDecodeError as e:
            print(f"  ❌ {json_file.name} - JSON parse error: {e}")
            all_passed = False
    
    return all_passed


def generate_key_usage_report():
    """Generate report of where each key should be used."""
    print("\n" + "=" * 70)
    print("KEY USAGE GUIDE")
    print("=" * 70)
    
    translations = load_all_translations()
    if 'en' not in translations:
        return
    
    en_keys = sorted(_get_all_keys(translations['en']))
    
    categories = {
        'ui': 'UI Components (Tkinter, Popups)',
        'event': 'In-Game Events (info.locale files)',
        'pdf': 'PDF Generation',
        'web': 'Web Frontend (Campaign Service Record)',
        'cli': 'Command-Line Interface',
        'installer': 'Inno Setup Installer',
        'validation': 'Validation & Status',
        'common': 'Common/Shared Strings'
    }
    
    for category, description in categories.items():
        matching_keys = [k for k in en_keys if k.startswith(f'{category}.')]
        
        if matching_keys:
            print(f"\n{category.upper()} ({description})")
            print(f"  {len(matching_keys)} keys")
            print(f"  Example: {matching_keys[0]}")


def main():
    """Run all tests."""
    print("IL-2 Campaign Tracker - i18n Validation")
    print("=" * 70)
    
    tests = [
        ("Encoding", test_encoding),
        ("Translation Completeness", test_translation_completeness),
        ("Parameter Consistency", test_parameter_consistency),
        ("No Empty Values", test_no_empty_values),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"\n❌ {name} test crashed: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    for name, passed in results:
        status = "✓ PASS" if passed else "❌ FAIL"
        print(f"{status:10} {name}")
    
    all_passed = all(passed for _, passed in results)
    
    if all_passed:
        print("\n✅ All tests passed!")
    else:
        print("\n❌ Some tests failed. Please fix the issues above.")
    
    # Generate usage guide
    generate_key_usage_report()
    
    return 0 if all_passed else 1


if __name__ == '__main__':
    sys.exit(main())
