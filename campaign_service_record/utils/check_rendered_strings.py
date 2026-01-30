#!/usr/bin/env python3
"""
Scan rendered-like strings for key-shaped patterns.

This script uses sample campaign events plus locale catalogs to ensure
no UI-facing string would render as a raw i18n key.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from utils.name_normalization import name_to_i18n_key

ROOT = Path(__file__).resolve().parents[2]
LOCALES_DIR = ROOT / "locales"
SAMPLE_EVENTS = ROOT / "json" / "campaign_events.json"

KEY_PATTERN = re.compile(r"^[a-z0-9_]+(\.[a-z0-9_]+)+$", re.IGNORECASE)


def load_locale(locale: str) -> Dict:
    with open(LOCALES_DIR / f"{locale}.json", "r", encoding="utf-8") as handle:
        return json.load(handle)


def get_nested_value(data: Dict, key: str) -> Optional[str]:
    current = data
    for part in key.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current if isinstance(current, str) else None


def resolve_key(
    key: str,
    locale_data: Dict,
    fallback_data: Dict,
) -> Optional[str]:
    return get_nested_value(locale_data, key) or get_nested_value(fallback_data, key)


def translate_award(
    name: str,
    locale_data: Dict,
    fallback_data: Dict,
) -> str:
    if KEY_PATTERN.match(name):
        return resolve_key(name, locale_data, fallback_data) or "[missing translation]"
    key = f"progression.awards.{name_to_i18n_key(name)}"
    return resolve_key(key, locale_data, fallback_data) or name


def iter_award_names(sample_data: Dict) -> Iterable[str]:
    for campaign in sample_data.values():
        if isinstance(campaign, dict):
            for event in campaign.get("events", []):
                if isinstance(event, dict) and event.get("type") == "award":
                    name = event.get("name")
                    if isinstance(name, str) and name.strip():
                        yield name.strip()


def main() -> int:
    if not SAMPLE_EVENTS.exists():
        print(f"Sample events file not found: {SAMPLE_EVENTS}")
        return 1

    locale_en = load_locale("en")
    locale_de = load_locale("de")

    with open(SAMPLE_EVENTS, "r", encoding="utf-8") as handle:
        sample_data = json.load(handle)

    failures: List[str] = []

    for name in iter_award_names(sample_data):
        for locale_label, locale_data in [("en", locale_en), ("de", locale_de)]:
            translated = translate_award(name, locale_data, locale_en)
            if KEY_PATTERN.match(translated):
                failures.append(f"[{locale_label}] {name} -> {translated}")

    if failures:
        print("❌ Found key-like rendered strings:")
        for entry in failures:
            print(f"  - {entry}")
        return 1

    print("✓ No key-like rendered strings detected in sample awards.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
