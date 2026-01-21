from __future__ import annotations

from pathlib import Path
import sys


def get_base_path(source_file: str | Path | None = None) -> Path:
    """Return base directory for script or bundled EXE execution."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    if source_file is not None:
        return Path(source_file).resolve().parent
    return Path.cwd().resolve()
