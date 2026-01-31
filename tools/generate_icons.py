#!/usr/bin/env python3
"""
Generate icon assets for IL-2 Campaign Tracker Control GUI.

Creates:
- stop.png (64x64) - Stop sign icon for "Close Tracker"
- uninstall.png (64x64) - Red X icon for "Uninstall"
- tracker.png (64x64) - Converted from il2_tracker_icon.ico
- service_record.png (64x64) - Converted from Campaign_Service_Record.ico
- settings.png (64x64) - Converted from settings.ico

Run this script once to generate the icons, which are then bundled with the EXE.

Requirements:
    pip install Pillow
"""

import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError:
    print("ERROR: Pillow not installed. Run: pip install Pillow")
    sys.exit(1)


ICON_SIZE = 64
SCRIPT_DIR = Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR / "icons"
ROOT_DIR = SCRIPT_DIR.parent


def create_stop_icon(size: int = ICON_SIZE) -> Image.Image:
    """
    Create a stop sign (octagon) icon.

    Returns:
        PIL Image with transparent background
    """
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Calculate octagon points
    margin = size // 10
    s = size - 2 * margin
    cx, cy = size // 2, size // 2
    d = s // 3  # Distance from center for flat edges

    # Octagon vertices (starting from top-left flat edge going clockwise)
    points = [
        (cx - d, margin),           # Top-left
        (cx + d, margin),           # Top-right
        (size - margin, cy - d),    # Right-top
        (size - margin, cy + d),    # Right-bottom
        (cx + d, size - margin),    # Bottom-right
        (cx - d, size - margin),    # Bottom-left
        (margin, cy + d),           # Left-bottom
        (margin, cy - d),           # Left-top
    ]

    # Draw octagon with gradient-like effect
    # Outer shadow
    shadow_points = [(p[0] + 2, p[1] + 2) for p in points]
    draw.polygon(shadow_points, fill=(60, 20, 20, 100))

    # Main octagon
    draw.polygon(points, fill=(220, 53, 69), outline=(180, 30, 50))

    # Inner white square/bar (like a stop hand)
    bar_h = size // 6
    bar_w = size // 3
    bar_left = cx - bar_w // 2
    bar_top = cy - bar_h // 2
    draw.rectangle(
        [bar_left, bar_top, bar_left + bar_w, bar_top + bar_h],
        fill=(255, 255, 255)
    )

    return img


def create_uninstall_icon(size: int = ICON_SIZE) -> Image.Image:
    """
    Create an uninstall (X in circle) icon.

    Returns:
        PIL Image with transparent background
    """
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    margin = size // 10

    # Draw shadow
    draw.ellipse(
        [margin + 2, margin + 2, size - margin + 2, size - margin + 2],
        fill=(60, 20, 20, 100)
    )

    # Draw circle background
    draw.ellipse(
        [margin, margin, size - margin, size - margin],
        fill=(220, 53, 69),
        outline=(180, 30, 50),
        width=2
    )

    # Draw X with proper thickness
    inner_margin = size // 4
    line_width = max(size // 10, 4)

    # Draw X lines with rounded ends
    for offset in range(-line_width // 2, line_width // 2 + 1):
        # Diagonal 1 (top-left to bottom-right)
        draw.line(
            [
                (inner_margin + offset, inner_margin),
                (size - inner_margin + offset, size - inner_margin)
            ],
            fill=(255, 255, 255),
            width=2
        )
        draw.line(
            [
                (inner_margin, inner_margin + offset),
                (size - inner_margin, size - inner_margin + offset)
            ],
            fill=(255, 255, 255),
            width=2
        )

        # Diagonal 2 (top-right to bottom-left)
        draw.line(
            [
                (size - inner_margin - offset, inner_margin),
                (inner_margin - offset, size - inner_margin)
            ],
            fill=(255, 255, 255),
            width=2
        )
        draw.line(
            [
                (size - inner_margin, inner_margin + offset),
                (inner_margin, size - inner_margin + offset)
            ],
            fill=(255, 255, 255),
            width=2
        )

    return img


def convert_ico_to_png(ico_path: Path, output_path: Path, size: int = ICON_SIZE) -> bool:
    """
    Convert an ICO file to PNG at the specified size.

    Args:
        ico_path: Path to the ICO file
        output_path: Path for the output PNG file
        size: Target size (width and height)

    Returns:
        True if successful, False otherwise
    """
    if not ico_path.exists():
        print(f"  WARNING: ICO file not found: {ico_path}")
        return False

    try:
        img = Image.open(ico_path)
        # ICO files may have multiple sizes; get the largest or specified size
        if hasattr(img, 'n_frames') and img.n_frames > 1:
            # Multi-frame ICO - find best size
            best_size = 0
            best_frame = 0
            for i in range(img.n_frames):
                img.seek(i)
                if img.size[0] > best_size:
                    best_size = img.size[0]
                    best_frame = i
            img.seek(best_frame)

        # Convert to RGBA and resize
        img = img.convert('RGBA')
        img = img.resize((size, size), Image.Resampling.LANCZOS)
        img.save(output_path, "PNG")
        return True
    except Exception as e:
        print(f"  ERROR converting {ico_path}: {e}")
        return False


def main():
    """Generate all icons."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Generate stop icon
    print(f"Generating stop.png ({ICON_SIZE}x{ICON_SIZE})...")
    stop_icon = create_stop_icon(ICON_SIZE)
    stop_path = OUTPUT_DIR / "stop.png"
    stop_icon.save(stop_path, "PNG")
    print(f"  Saved: {stop_path}")

    # Generate uninstall icon
    print(f"Generating uninstall.png ({ICON_SIZE}x{ICON_SIZE})...")
    uninstall_icon = create_uninstall_icon(ICON_SIZE)
    uninstall_path = OUTPUT_DIR / "uninstall.png"
    uninstall_icon.save(uninstall_path, "PNG")
    print(f"  Saved: {uninstall_path}")

    # Convert ICO files to PNG
    ico_conversions = [
        (ROOT_DIR / "il2_tracker_icon.ico", OUTPUT_DIR / "tracker.png"),
        (ROOT_DIR / "campaign_service_record" / "Campaign_Service_Record.ico", OUTPUT_DIR / "service_record.png"),
        (ROOT_DIR / "settings.ico", OUTPUT_DIR / "settings.png"),
    ]

    print(f"\nConverting ICO files to PNG ({ICON_SIZE}x{ICON_SIZE})...")
    for ico_path, png_path in ico_conversions:
        print(f"  Converting {ico_path.name}...")
        if convert_ico_to_png(ico_path, png_path, ICON_SIZE):
            print(f"    Saved: {png_path}")

    print("\nDone! Icons generated successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
