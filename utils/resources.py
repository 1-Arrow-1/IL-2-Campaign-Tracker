from __future__ import annotations

from pathlib import Path
import sys


def resolve_locales_dir() -> Path:
    candidates: list[Path] = []

    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        candidates.append(Path(sys._MEIPASS) / "locales")

    candidates.append(Path(sys.executable).resolve().parent / "locales")
    candidates.append(Path(__file__).resolve().parents[1] / "locales")

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return candidates[-1]