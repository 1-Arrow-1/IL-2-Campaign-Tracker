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

from utils.info_locale import decode_and_clean_info_locale
from utils.formatting import safe_campaign_filename
from utils.pathing import get_base_path

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

    try:
        with open(popups_path, "r", encoding="utf-8") as f:
            popups_data = json.load(f)
    except json.JSONDecodeError:
        print("[WARN] campaign_popups_seen.json invalid JSON – resetting")
        popups_data = {}

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
        tmp_path = popups_path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(popups_data, f, indent=4)
        os.replace(tmp_path, popups_path)
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
    mission_dates_path = os.path.join(base_path, "campaign_mission_dates.json")
    if os.path.exists(mission_dates_path):
        try:
            with open(mission_dates_path, "r", encoding="utf-8") as f:
                mission_dates = json.load(f)
                game_dir = mission_dates.get("game_directory", "")
                
            if game_dir and os.path.exists(game_dir):
                for campaign_name in reset_campaigns:
                    info_file = os.path.join(game_dir, "data", "Campaigns", campaign_name, "info.locale=eng.txt")
                    
                    if os.path.exists(info_file):
                        try:
                            # Read file with encoding detection and tracker cleanup
                            with open(info_file, 'rb') as f:
                                raw = f.read()
                            
                            cleaned, encoding, _ = decode_and_clean_info_locale(raw)
                            # Write back only if content changed
                            if cleaned != content:
                                with open(info_file, "w", encoding=encoding, newline="") as f:
                                    f.write(cleaned)
                                print(f"  ✂️  Cleared info file: {campaign_name}")
                                modified = True
                                
                        except Exception as e:
                            print(f"[WARN] Could not clear info file for '{campaign_name}': {e}")
            else:
                print(f"[WARN] Game directory not found: {game_dir}")
        
        except Exception as e:
            print(f"[WARN] Could not load mission dates: {e}")
    else:
        print(f"[WARN] mission_dates file not found: {mission_dates_path}")

    # ================================================================
    # Summary
    # ================================================================
    if modified:
        print("[INFO] ✅ Reset campaign cleanup complete")
        return True
    else:
        print("[INFO] No cleanup actions needed")
        return False
