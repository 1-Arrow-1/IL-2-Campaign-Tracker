#!/usr/bin/env python3
"""
IL-2 Campaign Progress Tracker - Unified Launcher
Version:  1.7 (Added Backup Restore GUI)
"""

import sys
import os
import argparse
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

os.environ. setdefault("FORCE_REGENERATE", "0")


def print_header(title: str):
    """Print a formatted section header."""
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)
    print()


def check_config() -> bool:
    """
    Check for required config file. 
    
    Returns:
        True if config exists, False otherwise
    """
    config_file = SCRIPT_DIR / "campaign_progress_config.yaml"
    if not config_file. exists():
        print("ERROR: campaign_progress_config.yaml not found!")
        print(f"Expected location: {config_file}")
        print()
        print("Please place campaign_progress_config.yaml in the same folder")
        print("as this executable.")
        return False
    return True


def run_first_time_setup() -> bool:
    """
    Run first-time setup if needed.
    
    Returns:
        True if setup completed successfully (or not needed), False on error
    """
    mission_dates_file = SCRIPT_DIR / "campaign_mission_dates.json"
    
    if mission_dates_file. exists():
        return True  # No setup needed
    
    print("FIRST RUN SETUP")
    print("=" * 70)
    print()
    
    # Import and run step 1
    import step1_extract_mission_dates
    step1_extract_mission_dates.main()
    
    if not mission_dates_file.exists():
        print()
        print("ERROR: Setup incomplete.  Mission dates not created.")
        return False
    
    # Show country validation GUI
    print_header("COUNTRY VALIDATION")
    print("Please verify the automatically detected countries...")
    print()
    
    try:
        from country_validator_gui import validate_countries
        result = validate_countries(str(mission_dates_file))
        
        if not result:
            print()
            print("Country validation was cancelled.")
            print("You can manually edit campaign_mission_dates. json")
            print("or restart the tracker to validate again.")
            print()
            input("Press Enter to continue anyway...")
    except Exception as e: 
        print(f"Warning: Could not show country validation GUI: {e}")
        print("You can manually edit campaign_mission_dates.json")
        print()
        input("Press Enter to continue...")
    
    return True


def find_il2_states_path() -> Path | None:
    """
    Find IL-2 campaign save file.
    
    Returns:
        Path to campaignsstates.txt, or None if not found
    """
    mission_dates_file = SCRIPT_DIR / "campaign_mission_dates.json"
    
    try:
        with open(mission_dates_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            game_dir = Path(data.get('game_directory', '')).expanduser().resolve()

        usersave_dir = game_dir / 'data' / 'swf' / 'il2' / 'usersave'
        if usersave_dir.exists():
            for user_dir in usersave_dir.iterdir():
                potential = user_dir / 'campaign' / 'campaignsstates.txt'
                if potential.exists():
                    print(f"✓ Found campaign save:  {potential}")
                    return potential
            
            print(f"⚠️ No campaignsstates.txt found under {usersave_dir}")
        else:
            print(f"⚠️ usersave directory not found:  {usersave_dir}")
            
    except Exception as e:
        print(f"❌ Could not locate campaign save:  {e}")
        import traceback
        traceback.print_exc()
    
    return None


def decode_campaign_save(il2_states_path: Path) -> bool:
    """
    Decode campaign save file. 
    
    Args:
        il2_states_path:  Path to campaignsstates.txt
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Delete old decoded file if it exists
        old_decoded = SCRIPT_DIR / "campaigns_decoded.json"
        if old_decoded.exists():
            print("Removing old decoded file...")
            old_decoded. unlink()
        
        import decode_campaign_usersave1
        print(f"Decoding:  {il2_states_path}")
        
        # Pass the IL-2 path to decoder
        result = decode_campaign_usersave1.main(states_path=str(il2_states_path))
        return result if result is not None else True
        
    except Exception as e: 
        print(f"Warning:  Decoder error: {e}")
        import traceback
        traceback.print_exc()
        return False


def restore_popup_backup(il2_states_path:  Path) -> bool:
    """
    Check and restore popup backup if hash matches.
    
    Args:
        il2_states_path: Path to campaignsstates.txt
        
    Returns:
        True if backup was restored, False otherwise
    """
    try:
        from cleanup_failed_missions import MissionCleanup
        
        cleanup_manager = MissionCleanup(campaignstates_path=il2_states_path)
        if cleanup_manager.restore_matching_popups():
            os. environ["FORCE_REGENERATE"] = "1"
            print("⚡ Backup restore detected — forcing event regeneration...")
            return True
        else:
            print("ℹ️ No backup restore needed")
            return False
            
    except Exception as e: 
        print(f"⚠️ Popup restore check failed: {e}")
        return False


def generate_initial_events() -> bool:
    """
    Generate events on first run or after backup restore.
    
    Returns:
        True if events were generated, False if skipped or error
    """
    popup_path = SCRIPT_DIR / "campaign_popups_seen.json"
    force_regenerate = os.environ.get("FORCE_REGENERATE", "0") == "1"
    
    # Check if this is first run (popup file doesn't exist or is empty)
    is_first_run = (not popup_path. exists()) or (popup_path.stat().st_size == 0)
    
    if not is_first_run and not force_regenerate: 
        print("✅ Popup state exists - skipping initial event generation")
        print(f"   (File size: {popup_path.stat().st_size} bytes)")
        return False
    
    if force_regenerate: 
        print("⚡ Regenerating events after backup restore...")
    else:
        print("🎯 First run detected - generating initial events...")
        print("   (This fills campaign_popups_seen.json with baseline)")
        print()
    
    try:
        import step3_generate_events
        # Direkte Parameterübergabe statt sys.argv Manipulation
        step3_generate_events.main(show_popups=False)
        
        if popup_path.exists() and popup_path. stat().st_size > 0:
            print(f"✅ Events generated, popup state initialized ({popup_path.stat().st_size} bytes)")
            return True
        else: 
            print("⚠️ Warning: Event generation completed but popup state empty")
            # Create empty state as fallback
            with open(popup_path, 'w', encoding='utf-8') as f:
                json.dump({}, f, indent=2)
            print("✅ Created empty popup state as fallback")
            return True
            
    except Exception as e: 
        print(f"❌ Error during event generation: {e}")
        import traceback
        traceback.print_exc()
        
        # Create empty state as fallback
        if not popup_path.exists():
            with open(popup_path, 'w', encoding='utf-8') as f:
                json.dump({}, f, indent=2)
            print("✅ Created empty popup state after error")
        return False


def run_cleanup_check(il2_states_path: Path) -> bool:
    """
    Check for unsuccessful missions and show cleanup GUI.
    
    Args:
        il2_states_path: Path to campaignsstates.txt
        
    Returns: 
        True if cleanup was performed, False otherwise
    """
    try: 
        from cleanup_failed_missions import startup_cleanup_check
        return startup_cleanup_check(states_path=il2_states_path)
        
    except ImportError:
        print("Note: cleanup_failed_missions. py not found")
        print("      Mission cleanup feature not available")
        return False
    except Exception as e:
        print(f"Warning:  Cleanup check failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_popup_reset_cleanup() -> bool:
    """
    Clean up popups for reset campaigns.
    
    Returns:
        True if changes were made, False otherwise
    """
    try:
        from campaign_reset_checker import cleanup_popups_for_reset_campaigns
        return cleanup_popups_for_reset_campaigns()
    except Exception as e: 
        print(f"⚠️ Popup cleanup check failed: {e}")
        return False


def show_campaign_not_found_message(game_dir: Path = None):
    """Display helpful message when campaign file is not found."""
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
    if game_dir: 
        print(f"     → Current path: {game_dir}")
    print("     → Re-run setup (delete campaign_mission_dates. json and restart)")
    print()
    print("  3. Permission issues accessing IL-2 directory")
    print("     → Try running tracker as Administrator")
    print()


def start_monitoring(il2_states_path: Path = None) -> int:
    """
    Start the campaign monitor. 
    
    Args:
        il2_states_path:  Path to campaignsstates.txt (optional)
        
    Returns:
        Exit code:  0 = normal exit, 1 = error
    """
    print_header("MONITORING ACTIVE")
    print("Checking for changes every second...")
    print()
    print("This window will stay open - you can minimize it.")
    print("The tracker will automatically update your campaigns.")
    print()
    print("Press Ctrl+C to stop.")
    print()
    
    try:
        import monitor_campaigns
        monitor = monitor_campaigns.CampaignMonitor(
            check_interval=1,
            use_file_watcher=True,
            il2_states_path=il2_states_path
        )
        monitor.run()
        return 0
        
    except Exception as e:
        print(f"❌ Monitor error:  {e}")
        import traceback
        traceback.print_exc()
        return 1


def run_tracker() -> int:
    """
    Main tracker execution. 
    """
    # ================================================================
    # DEBUG: Show command line arguments
    # ================================================================
    print()
    print(f"[DEBUG] sys.argv = {sys.argv}")
    print(f"[DEBUG] Working directory = {os. getcwd()}")
    print()
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--skip-backup-gui', action='store_true',
                       help='Skip backup GUI (used only for automatic restart after restore)')
    args, unknown = parser.parse_known_args()
    
    print(f"[DEBUG] --skip-backup-gui = {args.skip_backup_gui}")
    print(f"[DEBUG] Unknown args = {unknown}")
    print()
    print("=" * 70)
    print("IL-2 CAMPAIGN PROGRESS TRACKER v1.7")
    print("=" * 70)
    print()
    
    # Change to script directory
    os.chdir(SCRIPT_DIR)
    
    # Step 0: Check config
    if not check_config():
        input("Press Enter to exit...")
        return 1
    
    # Step 1: First-time setup
    if not run_first_time_setup():
        input("Press Enter to exit...")
        return 1
    
    # Step 2: Find IL-2 states path
    print_header("LOCATING IL-2 CAMPAIGN SAVE FILE")
    il2_states_path = find_il2_states_path()
    
    if il2_states_path and il2_states_path.exists():
        
        # ================================================================
        # Step 2. 5: Show backup restore GUI
        # Only skip if this is an automatic restart after restore
        # On manual starts, the GUI will always appear (if backups exist)
        # ================================================================
        if args.skip_backup_gui:
            print()
            print("ℹ️ Backup GUI skipped (automatic restart after restore)")
        else:
            try:
                from backup_restore_gui import check_and_show_backup_gui, restart_tracker
                
                print_header("CHECKING FOR AVAILABLE BACKUPS")
                backup_result = check_and_show_backup_gui(il2_states_path)
                
                if backup_result == 'restored':
                    # Don't print anything here - restart_tracker handles output
                    restart_tracker()  # This calls sys. exit(0)
                    # Code below will never be reached
                    
                elif backup_result == 'cancelled': 
                    print()
                    print("❌ Cancelled by user")
                    input("Press Enter to exit...")
                    return 2
                    
                elif backup_result == 'skipped':
                    print("ℹ️ Backup restore skipped - continuing normally...")
                    
                elif backup_result == 'no_backups':
                    print("ℹ️ No backups available yet")
                    
            except ImportError as e:
                print(f"ℹ️ Backup restore GUI not available: {e}")
            except Exception as e: 
                print(f"⚠️ Backup GUI error: {e}")
                import traceback
                traceback.print_exc()
                print()
                print("Continuing without backup restore option...")
                input("Press Enter to continue...")
        
        # Step 3: Decode campaign save
        print_header("DECODING CAMPAIGN SAVE")
        decode_campaign_save(il2_states_path)
        
        # Step 4: Popup restore check (automatic hash-based restore)
        print_header("CHECKING FOR MATCHING POPUP BACKUP (STATE RESTORE)")
        restore_popup_backup(il2_states_path)
        
        # Step 5: Event generation
        print_header("EVENT GENERATION CHECK")
        generate_initial_events()
        
        # Step 6: Cleanup check
        print_header("CHECKING FOR UNSUCCESSFUL MISSIONS")
        run_cleanup_check(il2_states_path)
        
        # Step 7: Popup reset cleanup
        print_header("CHECKING FOR RESET CAMPAIGNS (POPUP CLEANUP)")
        run_popup_reset_cleanup()
        
    else:
        show_campaign_not_found_message()
    
    # Step 8: Start monitoring
    return start_monitoring(il2_states_path)


def main() -> int:
    """
    Entry point with exception handling.
    
    Returns:
        Exit code for sys.exit()
    """
    try: 
        return run_tracker()
        
    except KeyboardInterrupt:
        print()
        print("=" * 70)
        print("TRACKER STOPPED BY USER")
        print("=" * 70)
        return 0
        
    except Exception as e:
        print()
        print("=" * 70)
        print(f"ERROR: {e}")
        print("=" * 70)
        import traceback
        traceback.print_exc()
        print()
        input("Press Enter to exit...")
        return 1


if __name__ == "__main__":
    exit_code = main()
    
    # ================================================================
    # DEBUG:  Always wait before closing (remove this later!)
    # ================================================================
    if exit_code != 0:
        print()
        print(f"[DEBUG] Exiting with code {exit_code}.  Press Enter to close...")
        input()
    
    sys.exit(exit_code)