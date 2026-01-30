#!/usr/bin/env python3
"""Validate locale JSON files are readable UTF-8 and list missing keys vs legacy."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
PRIMARY_DIR = ROOT / "locales"
LEGACY_DIR = ROOT / "campaign_service_record" / "static" / "locales"


def _load(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _iter_keys(data: Dict[str, Any], prefix: str = "") -> Iterable[str]:
    for key, value in data.items():
        full_key = f"{prefix}{key}"
        if isinstance(value, dict):
            yield from _iter_keys(value, f"{full_key}.")
        else:
            yield full_key


def _find_missing(primary: Dict[str, Any], legacy: Dict[str, Any]) -> List[str]:
    primary_keys = set(_iter_keys(primary))
    legacy_keys = set(_iter_keys(legacy))
    return sorted(legacy_keys - primary_keys)


def main() -> int:
    if not PRIMARY_DIR.exists():
        print(f"Primary locales directory not found: {PRIMARY_DIR}")
        return 1

    failures: List[Tuple[str, str]] = []
    missing_reports: List[Tuple[str, List[str]]] = []

    for locale_path in sorted(PRIMARY_DIR.glob("*.json")):
        locale = locale_path.stem
        try:
            primary = _load(locale_path)
        except (OSError, json.JSONDecodeError) as exc:
            failures.append((locale, str(exc)))
            continue

        if LEGACY_DIR.exists():
            legacy_path = LEGACY_DIR / f"{locale}.json"
            if legacy_path.exists():
                legacy = _load(legacy_path)
                missing = _find_missing(primary, legacy)
                missing_reports.append((locale, missing))

    if failures:
        print("❌ Locale validation failures:")
        for locale, message in failures:
            print(f"- {locale}: {message}")
        return 1

    print("✓ All locale JSON files loaded successfully.")

    if missing_reports:
        print("\nMissing legacy keys after merge (should be zero):")
        for locale, missing in missing_reports:
            if missing:
                print(f"- {locale}: {len(missing)} missing keys")
                for key in missing:
                    print(f"  - {key}")
            else:
                print(f"- {locale}: 0 missing keys")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
