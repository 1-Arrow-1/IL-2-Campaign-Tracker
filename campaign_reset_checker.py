# ==============================================================
# IL-2 Campaign Tracker – Popup Cleanup Utility (flat structure)
# --------------------------------------------------------------
# Removes popup entries in campaign_popups_seen. json when
# a campaign has been reset (empty completedMissionsByFileName).
# Works both in script and EXE environment. 
# ==============================================================

import json
import os
import sys


def _get_base_path():
    """Detects correct working directory (EXE or script)."""
    if getattr(sys, 'frozen', False):  # EXE mode
        return os. path.dirname(sys.executable)
    else:  # Python script mode
        return os.path.dirname(os.path. abspath(__file__))


def cleanup_popups_for_reset_campaigns() -> bool:
    """
    Main cleanup routine for reset or never-started campaigns.
    
    Returns:
        True if changes were made, False otherwise
    """
    base_path = _get_base_path()

    decoded_path = os.path. join(base_path, "campaigns_decoded.json")
    popups_path = os.path.join(base_path, "campaign_popups_seen.json")

    if not os.path.exists(decoded_path):
        print("[WARN] campaigns_decoded. json not found at", decoded_path)
        return False  # ✅ Expliziter Rückgabewert

    try:
        with open(decoded_path, "r", encoding="utf-8") as f:
            campaigns_data = json.load(f)
    except json.JSONDecodeError:
        print("[WARN] campaigns_decoded.json invalid JSON")
        return False  # ✅ Expliziter Rückgabewert

    if not os.path. exists(popups_path):
        print("[INFO] campaign_popups_seen. json not found — skipping cleanup")
        return False  # ✅ Expliziter Rückgabewert

    try:
        with open(popups_path, "r", encoding="utf-8") as f:
            popups_data = json.load(f)
    except json.JSONDecodeError:
        print("[WARN] campaign_popups_seen.json invalid JSON — resetting")
        popups_data = {}

    # Detect campaigns with empty completedMissionsByFileName
    reset_campaigns = [
        name for name, info in campaigns_data. items()
        if isinstance(info, dict) and not info.get("completedMissionsByFileName")
    ]

    if not reset_campaigns: 
        print("[INFO] No reset campaigns detected.")
        return False  # ✅ Expliziter Rückgabewert (keine Änderungen)

    modified = False
    for campaign_name in reset_campaigns:
        if campaign_name in popups_data:
            del popups_data[campaign_name]
            print(f"🧹 Removed popups for reset/unplayed campaign: '{campaign_name}'")
            modified = True

    if modified:
        tmp_path = popups_path + ". tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(popups_data, f, indent=4)
        os.replace(tmp_path, popups_path)
        print("[INFO] campaign_popups_seen.json updated successfully.")
        return True  # ✅ Änderungen wurden gemacht
    else:
        print("[INFO] No popup entries to remove.")
        return False  # ✅ Keine Änderungen nötig
