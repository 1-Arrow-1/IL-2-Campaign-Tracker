"""
German award style switcher.

Handles detection of the currently active German award style and the safe
swap of award image files between the '1957 Bundeswehr-era' and 'WW2' styles.

Folder convention (under <IL-2>/data/swf/CampaignRanksAwards/):

  Germany/           – always the ACTIVE folder read by the game
  Germany - WW2/     – alternate WW2-era images
  Germany - 1957/    – alternate 1957 Bundeswehr images (created on first swap)

Detection rule:
  Whichever alternate folder is NON-EMPTY is the backup → the other style is
  currently active in Germany/.

  Germany - WW2  non-empty, Germany - 1957  empty/absent  → 1957 is active
  Germany - 1957 non-empty, Germany - WW2   empty/absent  → ww2  is active
  Both non-empty or both empty/absent                      → ambiguous

Swap algorithm (uses rename for same-volume atomicity + rollback):
  1. Germany/            → Germany - _swap_temp/  (rename, atomic)
  2. source_folder/      → Germany/               (rename, atomic)
  3. _swap_temp/         → backup_dest/           (rename; removes empty
                                                   backup_dest first if needed)
"""

import os
import shutil
from pathlib import Path
from typing import Optional


# --- helpers -------------------------------------------------------------------

def _count_files(folder: Path) -> int:
    """Return the number of files in *folder* (recursive). Returns 0 if absent."""
    if not folder.exists():
        return 0
    return sum(1 for p in folder.rglob("*") if p.is_file())


def get_awards_dir(game_dir: Path) -> Optional[Path]:
    """
    Return the CampaignRanksAwards directory for *game_dir*, or None if it
    does not exist.
    """
    awards = game_dir / "data" / "swf" / "CampaignRanksAwards"
    return awards if awards.is_dir() else None


# --- detection -----------------------------------------------------------------

STYLE_1957 = "1957"
STYLE_WW2  = "ww2"


def detect_current_style(awards_dir: Path) -> Optional[str]:
    """
    Determine which German award style is currently active.

    Returns STYLE_1957, STYLE_WW2, or None when the state is ambiguous /
    cannot be determined.
    """
    ww2_count  = _count_files(awards_dir / "Germany - WW2")
    y57_count  = _count_files(awards_dir / "Germany - 1957")

    if ww2_count > 0 and y57_count == 0:
        return STYLE_1957   # WW2 folder is the backup → 1957 is active

    if y57_count > 0 and ww2_count == 0:
        return STYLE_WW2    # 1957 folder is the backup → WW2 is active

    # Both non-empty or both empty / absent – cannot decide safely
    return None


def has_alternate_folders(awards_dir: Path) -> bool:
    """
    Return True when at least one alternate folder exists (Germany - WW2
    or Germany - 1957), meaning style switching is possible.
    """
    return (
        (awards_dir / "Germany - WW2").exists()
        or (awards_dir / "Germany - 1957").exists()
    )


# --- swap ----------------------------------------------------------------------

_TEMP_NAME = "Germany - _swap_temp"


def perform_swap(awards_dir: Path, target_style: str) -> None:
    """
    Move award image files to activate *target_style* (STYLE_1957 or STYLE_WW2).

    Raises:
        ValueError  – target is already active or style is invalid
        FileNotFoundError – required folders are missing or empty
        OSError     – a file-system operation failed (partial state possible;
                      rollback attempted automatically)
    """
    if target_style not in (STYLE_1957, STYLE_WW2):
        raise ValueError(f"Unknown target style: {target_style!r}")

    germany     = awards_dir / "Germany"
    ww2_folder  = awards_dir / "Germany - WW2"
    y57_folder  = awards_dir / "Germany - 1957"
    tmp_folder  = awards_dir / _TEMP_NAME

    # --- validate current state ------------------------------------------------
    current = detect_current_style(awards_dir)
    if current == target_style:
        raise ValueError(f"Style '{target_style}' is already active.")

    if not germany.exists():
        raise FileNotFoundError(f"Active awards folder not found: {germany}")

    # Resolve which folder is the source (to move INTO Germany) and which will
    # become the new backup (to receive the current Germany contents).
    if target_style == STYLE_WW2:
        source_folder = ww2_folder
        backup_dest   = y57_folder
    else:
        source_folder = y57_folder
        backup_dest   = ww2_folder

    if not source_folder.exists() or _count_files(source_folder) == 0:
        raise FileNotFoundError(
            f"Source folder is missing or empty: {source_folder}\n"
            "Cannot switch styles without the alternate award files."
        )

    # --- guard against leftover temp folder ------------------------------------
    if tmp_folder.exists():
        shutil.rmtree(str(tmp_folder))

    # --- step 1: Germany → temp  (atomic rename) --------------------------------
    germany.rename(tmp_folder)

    try:
        # --- step 2: source → Germany  (atomic rename) -------------------------
        source_folder.rename(germany)

        # --- step 3: temp → backup_dest  (atomic rename where possible) --------
        backup_dest.mkdir(parents=True, exist_ok=True)

        if _count_files(backup_dest) == 0:
            # Empty destination – remove it so rename can succeed atomically
            shutil.rmtree(str(backup_dest))
            tmp_folder.rename(backup_dest)
        else:
            # Destination unexpectedly has files – fall back to content-level move
            for item in list(tmp_folder.iterdir()):
                dest_item = backup_dest / item.name
                if dest_item.exists():
                    if dest_item.is_dir():
                        shutil.rmtree(str(dest_item))
                    else:
                        dest_item.unlink()
                shutil.move(str(item), str(dest_item))
            shutil.rmtree(str(tmp_folder), ignore_errors=True)

    except Exception:
        # --- rollback: restore Germany from temp --------------------------------
        try:
            if tmp_folder.exists() and not germany.exists():
                tmp_folder.rename(germany)
        except Exception:
            pass  # Best-effort rollback
        raise
