#!/usr/bin/env python3
"""
IL-2 Campaign Progress Tracker - Unified Launcher
Version: 1.5 (Refactored - No Copy)
"""

import sys
import os
import time
from pathlib import Path
import json
import shutil

# Determine script directory (works for both script and EXE)
if getattr(sys, 'frozen', False):
    # Running as EXE
    SCRIPT_DIR = Path(sys.executable).parent
else:
    # Running as script
    SCRIPT_DIR = Path(__file__).parent

# Add to path for imports
sys.path.insert(0, str(SCRIPT_DIR))

os.environ.setdefault("FORCE_REGENERATE", "0")

print("="*70)
print("IL-2 CAMPAIGN PROGRESS TRACKER v1.5")
print("="*70)
print()

# Check for required config file
CONFIG_FILE = SCRIPT_DIR / "campaign_progress_config.yaml"
if not CONFIG_FILE.exists():
    print("ERROR: campaign_progress_config.yaml not found!")
    print(f"Expected location: {CONFIG_FILE}")
    print()
    print("Please place campaign_progress_config.yaml in the same folder")
    print("as this executable.")
    print()
    input("Press Enter to exit...")
    sys.exit(1)

# Import modules
try:
    # Change to script directory
    os.chdir(SCRIPT_DIR)
    
    # Run step 1 if first time
    MISSION_DATES_FILE = SCRIPT_DIR / "campaign_mission_dates.json"
    
    if not MISSION_DATES_FILE.exists():
        print("FIRST RUN SETUP")
        print("="*70)
        print()
        
        # Import and run step 1
        import step1_extract_mission_dates
        step1_extract_mission_dates.main()
        
        if not MISSION_DATES_FILE.exists():
            print()
            print("ERROR: Setup incomplete. Mission dates not created.")
            input("Press Enter to exit...")
            sys.exit(1)
        
        # Show country validation GUI
        print()
        print("="*70)
        print("COUNTRY VALIDATION")
        print("="*70)
        print()
        print("Please verify the automatically detected countries...")
        print()
        
        try:
            from country_validator_gui import validate_countries
            result = validate_countries(str(MISSION_DATES_FILE))
            
            if not result:
                print()
                print("Country validation was cancelled.")
                print("You can manually edit campaign_mission_dates.json")
                print("or restart the tracker to validate again.")
                print()
                input("Press Enter to continue anyway...")
        except Exception as e:
            print(f"Warning: Could not show country validation GUI: {e}")
            print("You can manually edit campaign_mission_dates.json")
            print()
            input("Press Enter to continue...")
    
    # ========================================================================
    # STEP 1: FIND IL-2 CAMPAIGN SAVE FILE
    # ========================================================================
    print()
    print("=" * 70)
    print("LOCATING IL-2 CAMPAIGN SAVE FILE")
    print("=" * 70)
    print()

    IL2_STATES_PATH = None
    
    try:
        with open(MISSION_DATES_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            game_dir = Path(data.get('game_directory', '')).expanduser().resolve()

        usersave_dir = game_dir / 'data' / 'swf' / 'il2' / 'usersave'
        if usersave_dir.exists():
            for user_dir in usersave_dir.iterdir():
                potential = user_dir / 'campaign' / 'campaignsstates.txt'
                if potential.exists():
                    IL2_STATES_PATH = potential
                    print(f"✓ Found campaign save: {IL2_STATES_PATH}")
                    break
            
            if not IL2_STATES_PATH:
                print(f"⚠️ No campaignsstates.txt found under {usersave_dir}")
        else:
            print(f"⚠️ usersave directory not found: {usersave_dir}")
    except Exception as e:
        print(f"❌ Could not locate campaign save: {e}")
        import traceback
        traceback.print_exc()
    
    # ========================================================================
    # CHECK IF WE FOUND THE FILE
    # ========================================================================
    
    if IL2_STATES_PATH and IL2_STATES_PATH.exists():
        
        # ====================================================================
        # STEP 2: DECODE CAMPAIGN SAVE
        # ====================================================================
        print()
        print("=" * 70)
        print("DECODING CAMPAIGN SAVE")
        print("=" * 70)
        print()
        
        try:
            # Delete old decoded file if it exists
            old_decoded = SCRIPT_DIR / "campaigns_decoded.json"
            if old_decoded.exists():
                print(f"Removing old decoded file...")
                old_decoded.unlink()
            
            import decode_campaign_usersave1
            print(f"Decoding: {IL2_STATES_PATH}")
            
            # Pass the IL-2 path to decoder
            decode_campaign_usersave1.main(states_path=str(IL2_STATES_PATH))
        except Exception as e:
            print(f"Warning: Decoder error: {e}")
            import traceback
            traceback.print_exc()
        
        # ====================================================================
        # STEP 3: POPUP-RESTORE (if backup hash matches)
        # ====================================================================
        try:
            from cleanup_failed_missions import MissionCleanup
            print()
            print("="*70)
            print("CHECKING FOR MATCHING POPUP BACKUP (STATE RESTORE)")
            print("="*70)
            
            # Pass IL-2 path to cleanup manager
            cleanup_manager = MissionCleanup(campaignstates_path=IL2_STATES_PATH)
            if cleanup_manager.restore_matching_popups():  # Rückgabe bool
                os.environ["FORCE_REGENERATE"] = "1"
                print("⚡ Backup restore detected — forcing event regeneration...")
        except Exception as e:
            print(f"⚠️ Popup restore check failed: {e}")
        
        # ====================================================================
        # STEP 4: EVENT-GENERATION (only on first start)
        # ====================================================================
        print()
        print("="*70)
        print("EVENT GENERATION CHECK")
        print("="*70)
        print()
        
        popup_path = SCRIPT_DIR / "campaign_popups_seen.json"
        force_regenerate = os.environ.get("FORCE_REGENERATE", "0") == "1"
        # Check if this is first run (popup file doesn't exist or is empty)
        is_first_run = (not popup_path.exists()) or (popup_path.stat().st_size == 0)
        
        if is_first_run or force_regenerate:
            if force_regenerate:
                print("⚡ Regenerating events after backup restore...")
            else:    
                print("🎯 First run detected - generating initial events...")
                print("   (This fills campaign_popups_seen.json with baseline)")
                print()
            
            try:
                import step3_generate_events
                step3_generate_events.main()
                
                if popup_path.exists() and popup_path.stat().st_size > 0:
                    print(f"✅ Events generated, popup state initialized ({popup_path.stat().st_size} bytes)")
                else:
                    print("⚠️ Warning: Event generation completed but popup state empty")
                    # Create empty state as fallback
                    with open(popup_path, 'w', encoding='utf-8') as f:
                        json.dump({}, f, indent=2)
                    print("✅ Created empty popup state as fallback")
            except Exception as e:
                print(f"❌ Error during event generation: {e}")
                import traceback
                traceback.print_exc()
                # Create empty state as fallback
                if not popup_path.exists():
                    with open(popup_path, 'w', encoding='utf-8') as f:
                        json.dump({}, f, indent=2)
                    print("✅ Created empty popup state after error")
        else:
            print("✅ Popup state exists - skipping initial event generation")
            print(f"   (File size: {popup_path.stat().st_size} bytes)")
        
        # ====================================================================
        # STEP 5: CLEANUP-SCAN (with user confirmation)
        # ====================================================================
        print()
        print("="*70)
        print("CHECKING FOR UNSUCCESSFUL MISSIONS")
        print("="*70)
        print()
        
        try:
            from cleanup_failed_missions import startup_cleanup_check
            
            # Pass IL-2 path to cleanup
            startup_cleanup_check(states_path=IL2_STATES_PATH)
            
        except ImportError:
            print("Note: cleanup_failed_missions.py not found")
            print("      Mission cleanup feature not available")
        except Exception as e:
            print(f"Warning: Cleanup check failed: {e}")
            import traceback
            traceback.print_exc()
        
        # ====================================================================
        # STEP 6: POPUP-RESET-CLEANUP (reset campaigns)
        # ====================================================================
        try:
            from campaign_reset_checker import cleanup_popups_for_reset_campaigns
            print()
            print("="*70)
            print("CHECKING FOR RESET CAMPAIGNS (POPUP CLEANUP)")
            print("="*70)
            cleanup_popups_for_reset_campaigns()
        except Exception as e:
            print(f"⚠️ Popup cleanup check failed: {e}")

    else:
        print()
        print("=" * 70)
        print("CAMPAIGN FILE NOT FOUND")
        print("=" * 70)
        print()
        print("⚠️  Could not locate campaignsstates.txt in IL-2 installation.")
        print()
        print("Possible reasons:")
        print("  1. No campaign started in IL-2 yet")
        print("     → Start a career campaign in IL-2, fly at least one mission")
        print()
        print("  2. IL-2 installation path incorrect in campaign_mission_dates.json")
        if 'game_dir' in locals():
            print(f"     → Current path: {game_dir}")
        print("     → Re-run setup (delete campaign_mission_dates.json and restart)")
        print()
        print("  3. Permission issues accessing IL-2 directory")
        print("     → Try running tracker as Administrator")
        print()

    # ========================================================================
    # STEP 7: START MONITORING
    # ========================================================================
    print()
    print("="*70)
    print("MONITORING ACTIVE")
    print("="*70)
    print("Checking for changes every second...")
    print()
    print("This window will stay open - you can minimize it.")
    print("The tracker will automatically update your campaigns.")
    print()
    print("Press Ctrl+C to stop.")
    print()
    
    import monitor_campaigns
    monitor = monitor_campaigns.CampaignMonitor(
        check_interval=1,
        use_file_watcher=True,
        il2_states_path=IL2_STATES_PATH  # Pass IL-2 path to monitor!
    )
    monitor.run()
    
except KeyboardInterrupt:
    print()
    print("="*70)
    print("TRACKER STOPPED BY USER")
    print("="*70)
    sys.exit(0)
    
except Exception as e:
    print()
    print("="*70)
    print(f"ERROR: {e}")
    print("="*70)
    import traceback
    traceback.print_exc()
    print()
    input("Press Enter to exit...")
    sys.exit(1)
