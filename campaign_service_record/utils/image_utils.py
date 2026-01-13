"""
Image utilities for Campaign Service Record.

Provides DDS -> PNG conversion helpers for frontend rendering.
"""

from __future__ import annotations

import base64
import logging
from io import BytesIO
from pathlib import Path
from typing import Optional

try:
    from PIL import Image
except ImportError:  # pragma: no cover - handled at runtime
    Image = None

logger = logging.getLogger(__name__)


def resolve_game_asset_path(game_directory: str, relative_path: str) -> Optional[Path]:
    """Resolve a relative asset path under the IL-2 data/swf directory."""
    if not game_directory or not relative_path:
        return None
    swf_dir = Path(game_directory) / "data" / "swf"
    return (swf_dir / relative_path).resolve()


def find_existing_image_path(asset_path: Path) -> Optional[Path]:
    """Return a valid image path, trying DDS when PNG is missing."""
    if asset_path.exists():
        return asset_path
    if asset_path.suffix.lower() == ".png":
        dds_path = asset_path.with_suffix(".dds")
        if dds_path.exists():
            return dds_path
    return None


def convert_dds_to_png_bytes(dds_path: Path) -> Optional[bytes]:
    """Convert a DDS image to PNG bytes."""
    if Image is None:
        logger.warning("PIL not available; cannot convert DDS: %s", dds_path)
        return None
    try:
        with Image.open(dds_path) as img:
            png_buffer = BytesIO()
            img.save(png_buffer, format="PNG")
            return png_buffer.getvalue()
    except Exception as exc:  # pragma: no cover - external lib behavior
        logger.warning("Failed to convert DDS %s: %s", dds_path, exc)
        return None


def build_dds_data_uri(game_directory: str, relative_path: str) -> Optional[str]:
    """Return a PNG data URI for a DDS asset, if conversion succeeds."""
    asset_path = resolve_game_asset_path(game_directory, relative_path)
    if not asset_path:
        return None
    asset_path = find_existing_image_path(asset_path)
    if not asset_path or asset_path.suffix.lower() != ".dds":
        return None
    png_bytes = convert_dds_to_png_bytes(asset_path)
    if not png_bytes:
        return None
    encoded = base64.b64encode(png_bytes).decode("ascii")
    return f"data:image/png;base64,{encoded}"
