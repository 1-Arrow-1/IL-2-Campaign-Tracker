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


def check_prerequisites() -> tuple[bool, list[str]]:
    """
    Check if required files exist.
    
    Returns:
        (can_start, warnings)
    """
    errors = []
    warnings = []
    
    # campaign_progress_config.yaml - required
    if not CONFIG_YAML_PATH.exists():
        errors.append(f"Required file missing:\n{CONFIG_YAML_PATH.name}\n\nPlease run the Campaign Tracker at least once.")
    
    # campaign_tracker_settings.json - create if missing
    if not SETTINGS_JSON_PATH.exists():
        # Will be created with defaults
        pass
    
    # campaign_mission_dates.json - optional but affects functionality
    if not MISSION_DATES_PATH.exists():
        warnings.append("campaign_mission_dates.json not found.\nCampaign-specific settings will be disabled.\n\nPlease run the Campaign Tracker at least once to enable all features.")
    
    if errors:
        return (False, errors)
    
    return (True, warnings)


def main():
    """Main entry point."""
    # Check prerequisites
    can_start, messages = check_prerequisites()
    
    if not can_start:
        # Show error and exit
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("IL-2 Settings Manager - Error", "\n".join(messages))
        root.destroy()
        return 1
    
    # Create and run application
    app = SettingsManagerApp()
    
    # Show warnings if any
    if messages:
        app.after(100, lambda: messagebox.showwarning(
            app.tr.t("msg_warning_title"),
            "\n".join(messages)
        ))
    
    app.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
