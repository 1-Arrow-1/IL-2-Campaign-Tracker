"""
IL-2 Settings Manager - Path Configuration

Defines paths to all configuration files.
Reuses existing path utilities from the main tracker.
"""

import sys
from pathlib import Path

# Determine base directory
if getattr(sys, 'frozen', False):
    # Running as compiled EXE
    BASE_DIR = Path(sys.executable).parent
else:
    # Running as script - go up one level from settings_manager/
    BASE_DIR = Path(__file__).parent.parent.parent

# Configuration files
SETTINGS_JSON_PATH = BASE_DIR / "campaign_tracker_settings.json"
CONFIG_YAML_PATH = BASE_DIR / "campaign_progress_config.yaml"
MISSION_DATES_PATH = BASE_DIR / "campaign_mission_dates.json"
STOCK_CAMPAIGNS_PATH = BASE_DIR / "stock_campaigns.yaml"

# Locales directory
LOCALES_DIR = BASE_DIR / "locales"


def get_base_dir() -> Path:
    """Return the base directory for all files."""
    return BASE_DIR
