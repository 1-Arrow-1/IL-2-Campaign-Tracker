# ==============================================================
# IL-2 Campaign Tracker – Popup Cleanup Utility (Enhanced)
# --------------------------------------------------------------
# Removes ALL traces when a campaign has been reset:
# - Popup entries in campaign_popups_seen.json
# - PDF reports
# - Events/Debriefings from info.locale=eng.txt
# Works both in script and EXE environment.
# ==============================================================

import json
import os
import re
from pathlib import Path

from utils.info_locale import decode_and_clean_info_locale
from utils.formatting import safe_campaign_filename
from utils.il2_paths import resolve_il2_paths
from utils.pathing import get_base_path
from utils.popup_state import load_popup_seen, save_popup_seen

def cleanup_popups_for_reset_campaigns() -> bool:
    """
    Main cleanup routine for reset or never-started campaigns.
    
    Detects campaigns with empty completedMissionsByFileName and removes:
    1. Popup entries in campaign_popups_seen.json
    2. PDF reports in reports/ directory
    3. Events/Debriefings from info.locale=eng.txt
    
    Returns:
        True if changes were made, False otherwise
    """
    base_path = get_base_path(__file__)

    decoded_path = os.path.join(base_path, "campaigns_decoded.json")
    popups_path = os.path.join(base_path, "campaign_popups_seen.json")
    popups_path_obj = Path(popups_path)
    
    # ================================================================
    # Validate files exist
    # ================================================================
    if not os.path.exists(decoded_path):
        print("[WARN] campaigns_decoded.json not found at", decoded_path)
        return False

    try:
        with open(decoded_path, "r", encoding="utf-8") as f:
            campaigns_data = json.load(f)
    except json.JSONDecodeError:
        print("[WARN] campaigns_decoded.json invalid JSON")
        return False

    if not os.path.exists(popups_path):
        print("[INFO] campaign_popups_seen.json not found – skipping cleanup")
        return False

    popups_data = load_popup_seen(popups_path_obj)

    # ================================================================
    # Detect reset campaigns (empty completedMissionsByFileName)
    # ================================================================
    reset_campaigns = [
        name for name, info in campaigns_data.items()
        if isinstance(info, dict) and not info.get("completedMissionsByFileName")
    ]

    if not reset_campaigns: 
        print("[INFO] No reset campaigns detected.")
        return False

    print(f"[INFO] Found {len(reset_campaigns)} reset campaign(s): {', '.join(reset_campaigns)}")
    modified = False

    # ================================================================
    # Step 0: Clear campaign_events.json entries
    # ================================================================
    events_path = os.path.join(base_path, "campaign_events.json")
    if os.path.exists(events_path):
        try:
            with open(events_path, "r", encoding="utf-8") as f:
                events_data = json.load(f)
        except json.JSONDecodeError:
            print("[WARN] campaign_events.json invalid JSON – skipping cleanup")
            events_data = None

        if isinstance(events_data, dict):
            events_modified = False
            for campaign_name in reset_campaigns:
                if events_data.get(campaign_name) != []:
                    events_data[campaign_name] = []
                    print(f"  🧹 Cleared events: '{campaign_name}'")
                    events_modified = True

            if events_modified:
                tmp_path = events_path + ".tmp"
                with open(tmp_path, "w", encoding="utf-8") as f:
                    json.dump(events_data, f, indent=4)
                os.replace(tmp_path, events_path)
                print("[INFO] campaign_events.json updated")
                modified = True
    else:
        print("[INFO] campaign_events.json not found – skipping cleanup")
        
    # ================================================================
    # Step 1: Remove popup entries
    # ================================================================
    for campaign_name in reset_campaigns:
        if campaign_name in popups_data:
            del popups_data[campaign_name]
            print(f"  🧹 Removed popups: '{campaign_name}'")
            modified = True

    if modified:
        save_popup_seen(popups_path_obj, popups_data)
        print("[INFO] campaign_popups_seen.json updated")
    
    # ================================================================
    # Step 2: Delete PDF reports
    # ================================================================
    reports_dir = os.path.join(base_path, "reports")
    if os.path.exists(reports_dir):
        for campaign_name in reset_campaigns:
            # Clean campaign name for filename (same logic as in step3)
            safe_name = safe_campaign_filename(campaign_name)
            pdf_path = os.path.join(reports_dir, f"{safe_name}_Report.pdf")
            
            if os.path.exists(pdf_path):
                try:
                    os.remove(pdf_path)
                    print(f"  🗑️  Deleted PDF: {safe_name}_Report.pdf")
                    modified = True
                except Exception as e:
                    print(f"[WARN] Could not delete PDF for '{campaign_name}': {e}")
    
    # ================================================================
    # Step 3: Clear info.locale=eng.txt
    # ================================================================
    # Load mission dates to get game directory
    paths = resolve_il2_paths(base_path)
    if paths.game_directory and paths.game_directory.exists():
        if not paths.campaigns_dir:
            print(f"[WARN] Campaigns directory not resolved under {paths.game_directory}")
        else:
            for campaign_name in reset_campaigns:
                info_file = paths.campaigns_dir / campaign_name / "info.locale=eng.txt"

                if info_file.exists():
                    try:
                        # Read file with encoding detection and tracker cleanup
                        raw = info_file.read_bytes()

                        cleaned, encoding, original = decode_and_clean_info_locale(raw)
                        # Write back only if content changed
                        if cleaned != original:
                            info_file.write_text(cleaned, encoding=encoding, newline="")
                            print(f"  ✂️  Cleared info file: {campaign_name}")
                            modified = True

                    except Exception as e:
                        print(f"[WARN] Could not clear info file for '{campaign_name}': {e}")
    else:
        mission_dates_path = os.path.join(base_path, "campaign_mission_dates.json")
        print(f"[WARN] Game directory not found via {mission_dates_path}")

    # ================================================================
    # Summary
    # ================================================================
    if modified:
        print("[INFO] ✅ Reset campaign cleanup complete")
        return True
    else:
        print("[INFO] No cleanup actions needed")
        return False
