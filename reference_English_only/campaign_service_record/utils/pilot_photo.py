"""
Pilot photo helpers.

Mirrors IL-2 Pilot Service Record naming and hashing strategy.
"""

from __future__ import annotations

import hashlib
from pathlib import Path


def pilot_photo_filename(description: str) -> str:
    """Return hashed pilot photo filename for a given description."""
    pilot_hash = hashlib.sha256(description.encode('utf-8')).hexdigest()[:20]
    return f"{pilot_hash}.png"


def pilot_photo_path(photo_dir: Path, description: str) -> Path:
    """Return full path for a pilot photo."""
    return Path(photo_dir) / pilot_photo_filename(description)


def pilot_name_filename(description: str) -> str:
    """Return hashed pilot name filename for a given description."""
    pilot_hash = hashlib.sha256(description.encode('utf-8')).hexdigest()[:20]
    return f"{pilot_hash}.txt"


def pilot_name_path(photo_dir: Path, description: str) -> Path:
    """Return full path for a pilot name."""
    return Path(photo_dir) / pilot_name_filename(description)