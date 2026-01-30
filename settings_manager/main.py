#!/usr/bin/env python3
"""
IL-2 Campaign Tracker - Settings Manager

A standalone GUI application for editing tracker configuration files.
This is an add-on that does not modify any tracker functionality.

Features:
- Edit language settings (campaign_tracker_settings.json)
- Edit rank scaling factors (campaign_progress_config.yaml)
- Edit rank score thresholds (campaign_progress_config.yaml)
- Edit campaign starting rank offsets (campaign_mission_dates.json)
"""

import sys
import tkinter as tk
from tkinter import messagebox
from pathlib import Path

# Add parent directory to path for imports
if getattr(sys, 'frozen', False):
    # Running as compiled EXE
    BASE_DIR = Path(sys.executable).parent
else:
    # Running as script
    BASE_DIR = Path(__file__).parent.parent
    sys.path.insert(0, str(BASE_DIR))

from settings_manager.app import SettingsManagerApp
from settings_manager.config.paths import (
    CONFIG_YAML_PATH,
    SETTINGS_JSON_PATH,
    MISSION_DATES_PATH,
)
from utils.il2_paths import read_game_directory
from utils.i18n import t, init_i18n
from utils.locale_config import resolve_locale

# Initialize i18n early so we can show localized error messages
try:
    user_locale = resolve_locale()
    init_i18n(user_locale)
except Exception:
    init_i18n('en')


def check_first_run_required() -> str | None:
    """
    Check if first-time setup is required.

    Returns:
        Error message if first-run required, None if setup is complete
    """
    # Check if campaign_mission_dates.json exists
    if not MISSION_DATES_PATH.exists():
        return t('ui.launcher.first_run_required')

    # Check if game_directory is valid
    game_dir = read_game_directory(BASE_DIR)
    if not game_dir or not game_dir.exists():
        return t('ui.launcher.first_run_required')

    return None


def check_prerequisites() -> tuple[bool, list[str]]:
    """
    Check if required files exist.

    Returns:
        (can_start, errors)
    """
    errors = []

    # First-run check - BLOCKING
    first_run_msg = check_first_run_required()
    if first_run_msg:
        errors.append(first_run_msg)
        return (False, errors)

    # campaign_progress_config.yaml - required
    if not CONFIG_YAML_PATH.exists():
        errors.append(f"Required file missing:\n{CONFIG_YAML_PATH.name}\n\nPlease run the Campaign Tracker at least once.")

    # campaign_tracker_settings.json - create if missing
    if not SETTINGS_JSON_PATH.exists():
        # Will be created with defaults
        pass

    if errors:
        return (False, errors)

    return (True, [])


def main():
    """Main entry point."""
    # Check prerequisites
    can_start, errors = check_prerequisites()

    if not can_start:
        # Show error and exit - Settings Manager cannot be used until first-time setup is complete
        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo("IL-2 Settings Manager", "\n".join(errors))
        root.destroy()
        return 0  # Clean exit - not an error, just need setup first

    # Create and run application
    app = SettingsManagerApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
