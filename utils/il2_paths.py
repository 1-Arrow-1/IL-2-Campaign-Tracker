from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Optional

from utils.pathing import get_base_path


@dataclass(frozen=True)
class IL2Paths:
    game_directory: Optional[Path]
    campaignsstates_path: Optional[Path]
    campaigns_dir: Optional[Path]


def read_game_directory(base_path: Path | None = None) -> Optional[Path]:
    base_path = Path(base_path) if base_path else get_base_path(__file__)
    mission_dates_file = base_path / "campaign_mission_dates.json"
    if not mission_dates_file.exists():
        return None

    try:
        with open(mission_dates_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        game_dir_str = str(data.get("game_directory", "")).strip()
    except Exception:
        return None

    if not game_dir_str:
        return None

    return Path(game_dir_str).expanduser().resolve()


def find_campaignsstates_path(game_directory: Path | None) -> Optional[Path]:
    if not game_directory:
        return None

    usersave_dir = game_directory / "data" / "swf" / "il2" / "usersave"
    if usersave_dir.exists():
        for user_dir in usersave_dir.iterdir():
            if user_dir.is_dir():
                candidate = user_dir / "campaign" / "campaignsstates.txt"
                if candidate.exists():
                    return candidate

    legacy_path = game_directory / "data" / "campaignsstates.txt"
    if legacy_path.exists():
        return legacy_path

    return None


def resolve_campaigns_dir(game_directory: Path | None) -> Optional[Path]:
    if not game_directory:
        return None

    candidates = [
        game_directory / "data" / "Campaigns",
        game_directory / "data" / "campaigns",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate

    return candidates[0]


def resolve_il2_paths(
    base_path: Path | None = None,
    game_directory: Path | None = None,
) -> IL2Paths:
    if game_directory is None:
        game_directory = read_game_directory(base_path)

    return IL2Paths(
        game_directory=game_directory,
        campaignsstates_path=find_campaignsstates_path(game_directory),
        campaigns_dir=resolve_campaigns_dir(game_directory),
    )
