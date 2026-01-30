#!/usr/bin/env python3
"""
Merge legacy locale JSON files into the root locales directory.

Adds only missing keys (deep merge) without overwriting existing values.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
PRIMARY_DIR = ROOT / "locales"
LEGACY_DIR = ROOT / "campaign_service_record" / "static" / "locales"
LANGUAGES = ["en", "de", "fr", "es", "pl", "ru", "zh"]


def _deep_add_missing(target: Dict[str, Any], source: Dict[str, Any], prefix: str = "") -> List[str]:
    added: List[str] = []
    for key, value in source.items():
        if key not in target:
            target[key] = value
            added.append(f"{prefix}{key}")
        else:
            target_value = target[key]
            if isinstance(target_value, dict) and isinstance(value, dict):
                added.extend(_deep_add_missing(target_value, value, f"{prefix}{key}."))
    return added


def _load_locale(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_locale(path: Path, data: Dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False, sort_keys=True)
        handle.write("\n")


def merge_locales() -> List[Tuple[str, List[str]]]:
    report: List[Tuple[str, List[str]]] = []
    for locale in LANGUAGES:
        primary_path = PRIMARY_DIR / f"{locale}.json"
        legacy_path = LEGACY_DIR / f"{locale}.json"

        if not primary_path.exists():
            raise FileNotFoundError(f"Missing primary locale file: {primary_path}")
        if not legacy_path.exists():
            print(f"[merge_locales] Skipping missing legacy file: {legacy_path}")
            report.append((locale, []))
            continue

        primary_data = _load_locale(primary_path)
        legacy_data = _load_locale(legacy_path)
        added_keys = _deep_add_missing(primary_data, legacy_data)

        _write_locale(primary_path, primary_data)
        report.append((locale, added_keys))
    return report


def main() -> int:
    if not PRIMARY_DIR.exists():
        print(f"Primary locales directory not found: {PRIMARY_DIR}")
        return 1
    if not LEGACY_DIR.exists():
        print(f"Legacy locales directory not found: {LEGACY_DIR}")
        return 1

    report = merge_locales()

    print("\nMerge report (added missing keys only):")
    for locale, keys in report:
        if keys:
            print(f"- {locale}: {len(keys)} keys added")
            for key in sorted(keys):
                print(f"  - {key}")
        else:
            print(f"- {locale}: 0 keys added")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
