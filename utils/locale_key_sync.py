#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _plural_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value.keys())
    return set()


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare locale keys between JSON files.")
    parser.add_argument("--base", default="locales/en.json", help="Base locale JSON file.")
    parser.add_argument("--target", default="locales/de.json", help="Target locale JSON file.")
    args = parser.parse_args()

    base_path = Path(args.base)
    target_path = Path(args.target)

    base = _load_json(base_path)
    target = _load_json(target_path)

    base_keys = set(base.keys())
    target_keys = set(target.keys())

    missing = sorted(base_keys - target_keys)
    extra = sorted(target_keys - base_keys)

    plural_mismatches: list[str] = []
    for key in sorted(base_keys & target_keys):
        base_value = base[key]
        target_value = target[key]
        if isinstance(base_value, dict):
            if not isinstance(target_value, dict):
                plural_mismatches.append(f"{key}: base is plural map, target is {type(target_value).__name__}")
                continue
            base_plural = _plural_keys(base_value)
            target_plural = _plural_keys(target_value)
            if base_plural != target_plural:
                plural_mismatches.append(
                    f"{key}: plural keys differ (base={sorted(base_plural)}, target={sorted(target_plural)})"
                )
        elif isinstance(target_value, dict):
            plural_mismatches.append(f"{key}: target is plural map, base is {type(base_value).__name__}")

    if missing:
        print("Missing keys in target locale:")
        for key in missing:
            print(f"  - {key}")

    if extra:
        print("Extra keys in target locale:")
        for key in extra:
            print(f"  + {key}")

    if plural_mismatches:
        print("Pluralization mismatches:")
        for item in plural_mismatches:
            print(f"  ! {item}")

    if missing or extra or plural_mismatches:
        return 1

    print("Locale keys match.")
    return 0


if __name__ == "__main__":
    sys.exit(main())