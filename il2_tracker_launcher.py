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

from utils.il2_paths import resolve_il2_paths, read_game_directory
from utils.logging import get_logger, log_message
from utils.pathing import get_base_path
from utils.i18n import t

# Determine script directory (works for both script and EXE)
SCRIPT_DIR = get_base_path(__file__)

# Add to path for imports
sys.path.insert(0, str(SCRIPT_DIR))

os.environ.setdefault("FORCE_REGENERATE", "0")

DEBUG_ENABLED = False
logger = get_logger(__name__)


def is_debug_enabled(args_debug: bool = False) -> bool:
    """Determine whether debug logging is enabled."""
    env_value = os.environ.get("IL2_TRACKER_DEBUG", "")
    env_enabled = env_value.strip().lower() in {"1", "true", "yes", "on"}
    return args_debug or env_enabled


def safe_input(prompt: str = "") -> str | None:
    """
    Safe input that handles EOFError and OSError in packaged EXE.

    Returns:
        User input string, or None if stdin is not available
    """
    # Check if stdin is available
    if not sys.stdin or not hasattr(sys.stdin, 'isatty'):
        return None

    try:
        # Check if we're in an interactive terminal
        if not sys.stdin.isatty():
            return None
        return input(prompt)
    except (EOFError, OSError):
        # stdin closed or not available (common in packaged EXE)
        return None


def check_first_run_setup(non_interactive: bool = False) -> tuple[bool, str | None]:
    """
    Preflight check for first-run conditions in non-interactive mode.

    In non-interactive mode (e.g., --auto flag, Settings Manager context, or packaged EXE
    without console), we cannot prompt the user for IL-2 installation path. If this is
    a first run (no campaign_mission_dates.json or no valid game_directory), we must
    abort early with a clear message.

    Args:
        non_interactive: True if running without user interaction capability

    Returns:
        (can_continue, error_message)
        - can_continue: True if setup can proceed, False if must abort
        - error_message: Human-readable message if aborting, None otherwise
    """
    mission_dates_file = SCRIPT_DIR / "campaign_mission_dates.json"

    # If mission dates file exists, check if it has a valid game_directory
    if mission_dates_file.exists():
        game_dir = read_game_directory(SCRIPT_DIR)
        if game_dir and game_dir.exists():
            # Valid setup exists, can continue
            return (True, None)
        elif not non_interactive:
            # File exists but invalid path - interactive mode can fix this
            return (True, None)
        else:
            # File exists but invalid path in non-interactive mode
            error_msg = t('ui.launcher.first_run_required')
            return (False, error_msg)

    # Mission dates file doesn't exist - this is first run
    if not non_interactive:
        # Interactive mode can prompt user for IL-2 path
        return (True, None)

    # Non-interactive mode cannot prompt for IL-2 path
    error_msg = t('ui.launcher.first_run_required')
    return (False, error_msg)


def print_header(title: str):
    """Print a formatted section header."""
    log_message(logger)
    log_message(logger, "=" * 70)
    log_message(logger, title)
    log_message(logger, "=" * 70)
    log_message(logger)


def check_config() -> bool:
    """
    Check for required config file. 
    
    Returns:
        True if config exists, False otherwise
    """
    config_file = SCRIPT_DIR / "campaign_progress_config.yaml"
    if not config_file.exists():
        log_message(logger, "ERROR: campaign_progress_config.yaml not found!")
        log_message(logger, f"Expected location: {config_file}")
        log_message(logger)
        log_message(logger, "Please place campaign_progress_config.yaml in the same folder")
        log_message(logger, "as this executable.")
        return False
    return True


def run_first_time_setup() -> bool:
    """
    Run first-time setup if needed.
    
    Returns:
        True if setup completed successfully (or not needed), False on error
    """
    mission_dates_file = SCRIPT_DIR / "campaign_mission_dates.json"
    
    if mission_dates_file.exists():
        return True  # No setup needed
    
    log_message(logger, "FIRST RUN SETUP")
    log_message(logger, "=" * 70)
    log_message(logger)
    
    # Import and run step 1
    import step1_extract_mission_dates
    step1_extract_mission_dates.main(args=["--auto"])
    
    if not mission_dates_file.exists():
        log_message(logger)
        log_message(logger, "ERROR: Setup incomplete.  Mission dates not created.")
        return False
    
    # Show country validation GUI
    print_header("COUNTRY VALIDATION")
    log_message(logger, "Please verify the automatically detected countries...")
    log_message(logger)
    
    try:
        from country_validator_gui import validate_countries
        result = validate_countries(str(mission_dates_file))
        
        if not result:
            log_message(logger)
            log_message(logger, "Country validation was cancelled.")
            log_message(logger, "You can manually edit campaign_mission_dates. json")
            log_message(logger, "or restart the tracker to validate again.")
            log_message(logger)
            safe_input("Press Enter to continue anyway...")
    except Exception as e:
        log_message(logger, f"Warning: Could not show country validation GUI: {e}")
        log_message(logger, "You can manually edit campaign_mission_dates.json")
        log_message(logger)
        safe_input("Press Enter to continue...")
    
    return True


def sync_campaign_structure() -> bool:
    """
    Sync campaign structure (new/deleted campaigns/missions) at every startup.
    
    This ensures that campaigns added or missions added while the tracker
    was not running are properly registered in campaign_mission_dates.json.
    
    If new campaigns are detected, the country validator GUI is shown.
    If campaigns were deleted, orphaned data is cleaned up.
    
    Returns:
        True if sync completed successfully, False on error
    """
    mission_dates_file = SCRIPT_DIR / "campaign_mission_dates.json"
    
    if not mission_dates_file.exists():
        # First run - will be handled by run_first_time_setup
        return True
    
    log_message(logger, "Checking for new/changed campaigns...")
    
    # Load existing campaigns before sync
    try:
        with open(mission_dates_file, 'r', encoding='utf-8') as f:
            old_data = json.load(f)
        old_campaigns = set(k for k in old_data.keys() if k != 'game_directory')
    except Exception:
        old_campaigns = set()
    
    try:
        import step1_extract_mission_dates
        step1_extract_mission_dates.main(args=["--auto"])
        
        # Load campaigns after sync
        try:
            with open(mission_dates_file, 'r', encoding='utf-8') as f:
                new_data = json.load(f)
            new_campaigns = set(k for k in new_data.keys() if k != 'game_directory')
        except Exception:
            new_campaigns = set()
        
        # Check for newly added campaigns
        added_campaigns = new_campaigns - old_campaigns
        
        if added_campaigns:
            log_message(logger, f"✅ Found {len(added_campaigns)} new campaign(s):")
            for name in sorted(added_campaigns):
                log_message(logger, f"   - {name}")
            log_message(logger)
            
            # Show country validator GUI for new campaigns
            log_message(logger, "Please verify the country for new campaigns...")
            try:
                from country_validator_gui import validate_countries
                result = validate_countries(str(mission_dates_file))
                
                if not result:
                    log_message(logger, "Country validation was cancelled.")
                    log_message(logger, "You can manually edit campaign_mission_dates.json later.")
            except Exception as e:
                log_message(logger, f"⚠️ Could not show country validation GUI: {e}")
                log_message(logger, "You can manually edit campaign_mission_dates.json later.")
        else:
            log_message(logger, "✅ Campaign structure synced (no new campaigns)")
        
        # Check for deleted campaigns and clean up orphaned data
        deleted_campaigns = old_campaigns - new_campaigns
        if deleted_campaigns:
            log_message(logger, f"🗑️ Detected {len(deleted_campaigns)} deleted campaign(s):")
            for name in sorted(deleted_campaigns):
                log_message(logger, f"   - {name}")
            
            # Clean up orphaned data files
            try:
                from sync_campaign_mission_states import cleanup_orphaned_campaigns
                existing_lower = {name.lower() for name in new_campaigns}
                cleanup_orphaned_campaigns(existing_lower, SCRIPT_DIR)
            except Exception as e:
                log_message(logger, f"⚠️ Could not clean up orphaned campaign data: {e}")
        
        return True
        
    except Exception as e:
        log_message(logger, f"⚠️ Warning: Campaign sync failed: {e}")
        return False


def find_il2_states_path() -> Path | None:
    """
    Find IL-2 campaign save file.
    
    Returns:
        Path to campaignsstates.txt, or None if not found
    """
    try:
        paths = resolve_il2_paths(SCRIPT_DIR)
        if paths.campaignsstates_path:
            log_message(logger, f"✓ Found campaign save:  {paths.campaignsstates_path}")
            return paths.campaignsstates_path
        if paths.game_directory:
            usersave_dir = paths.game_directory / "data" / "swf" / "il2" / "usersave"
            if usersave_dir.exists():
                log_message(logger, f"⚠️ No campaignsstates.txt found under {usersave_dir}")
            else:
                log_message(logger, f"⚠️ usersave directory not found:  {usersave_dir}")
        else:
            log_message(logger, "⚠️ Game directory not found in campaign_mission_dates.json")
            
    except Exception as e:
        log_message(logger, f"❌ Could not locate campaign save:  {e}")
        import traceback
        traceback.print_exc()
    
    return None


def cleanup_after_restore():
    """
    Clean up derived state files after backup restore to ensure consistency.
    
    Removes:
    - campaign_completion_state.json (will be regenerated)
    - All mission_aircraft_map.json files (will be regenerated from MLG)
    
    These files may contain stale data that doesn't match the restored backup.
    """
    log_message(logger, "🧹 Cleaning up derived state files after restore...")
    
    # 1. Remove campaign_completion_state.json
    completion_state = SCRIPT_DIR / "campaign_completion_state.json"
    if completion_state.exists():
        try:
            completion_state.unlink()
            log_message(logger, "  ✓ Removed campaign_completion_state.json")
        except Exception as e:
            log_message(logger, f"  ⚠️ Could not remove campaign_completion_state.json: {e}")
    
    # 2. Remove all mission_aircraft_map.json files
    reports_dir = SCRIPT_DIR / "reports"
    if reports_dir.exists():
        removed_count = 0
        for campaign_dir in reports_dir.iterdir():
            if campaign_dir.is_dir():
                aircraft_cache = campaign_dir / "mission_aircraft_map.json"
                if aircraft_cache.exists():
                    try:
                        aircraft_cache.unlink()
                        removed_count += 1
                    except Exception as e:
                        log_message(logger, f"  ⚠️ Could not remove {aircraft_cache}: {e}")
        
        if removed_count > 0:
            log_message(logger, f"  ✓ Removed {removed_count} aircraft cache file(s)")
    
    log_message(logger, "  ✅ Cleanup complete - files will be regenerated")



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
            log_message(logger, "Removing old decoded file...")
            old_decoded.unlink()
        
        import decode_campaign_usersave1
        log_message(logger, f"Decoding:  {il2_states_path}")
        
        # Pass the IL-2 path to decoder
        result = decode_campaign_usersave1.main(states_path=str(il2_states_path))
        return result if result is not None else True
        
    except Exception as e: 
        log_message(logger, f"Warning:  Decoder error: {e}")
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
            os.environ["FORCE_REGENERATE"] = "1"
            log_message(logger, "⚡ Backup restore detected — forcing event regeneration...")
            return True
        else:
            log_message(logger, "ℹ️ No backup restore needed")
            return False
            
    except Exception as e: 
        log_message(logger, f"⚠️ Popup restore check failed: {e}")
        return False


def generate_initial_events(locale_override: str | None = None) -> bool:
    """
    Generate events on first run or after backup restore.

    Args:
        locale_override: Optional locale to use for translations (e.g., 'de', 'en')

    Returns:
        True if events were generated, False if skipped or error
    """
    popup_path = SCRIPT_DIR / "campaign_popups_seen.json"
    force_regenerate = os.environ.get("FORCE_REGENERATE", "0") == "1"
    
    # Check if this is first run (popup file doesn't exist or is empty)
    is_first_run = (not popup_path.exists()) or (popup_path.stat().st_size == 0)
    
    if not is_first_run and not force_regenerate: 
        log_message(logger, "✅ Popup state exists - skipping initial event generation")
        log_message(logger, f"   (File size: {popup_path.stat().st_size} bytes)")
        return False
    
    if force_regenerate: 
        log_message(logger, "⚡ Regenerating events after backup restore...")
        log_message(logger, "🔄 Refreshing campaign mission dates...")
        try:
            import step1_extract_mission_dates
            step1_extract_mission_dates.main(args=["--auto"])
        except Exception as e:
            log_message(logger, f"⚠️ Failed to refresh campaign mission dates: {e}")
    else:
        log_message(logger, "🎯 First run detected - generating initial events...")
        log_message(logger, "   (This fills campaign_popups_seen.json with baseline)")
        log_message(logger)
    
    try:
        import step3_generate_events
        # Build args list with optional locale
        step3_args = ["--auto"]
        if locale_override:
            step3_args.extend(["--locale", locale_override])
        step3_generate_events.main(args=step3_args, show_popups=False)
        
        if popup_path.exists() and popup_path.stat().st_size > 0:
            log_message(logger, f"✅ Events generated, popup state initialized ({popup_path.stat().st_size} bytes)")
            return True
        else: 
            log_message(logger, "⚠️ Warning: Event generation completed but popup state empty")
            # Create empty state as fallback
            with open(popup_path, 'w', encoding='utf-8') as f:
                json.dump({}, f, indent=2)
            log_message(logger, "✅ Created empty popup state as fallback")
            return True
            
    except Exception as e: 
        log_message(logger, f"❌ Error during event generation: {e}")
        import traceback
        traceback.print_exc()
        
        # Create empty state as fallback
        if not popup_path.exists():
            with open(popup_path, 'w', encoding='utf-8') as f:
                json.dump({}, f, indent=2)
            log_message(logger, "✅ Created empty popup state after error")
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
        log_message(logger, "Note: cleanup_failed_missions. py not found")
        log_message(logger, "      Mission cleanup feature not available")
        return False
    except Exception as e:
        log_message(logger, f"Warning:  Cleanup check failed: {e}")
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
        log_message(logger, f"⚠️ Popup cleanup check failed: {e}")
        return False


def show_campaign_not_found_message(game_dir: Path = None):
    """Display helpful message when campaign file is not found."""
    log_message(logger)
    log_message(logger, "=" * 70)
    log_message(logger, "CAMPAIGN FILE NOT FOUND")
    log_message(logger, "=" * 70)
    log_message(logger)
    log_message(logger, "⚠️  Could not locate campaignsstates.txt in IL-2 installation.")
    log_message(logger)
    log_message(logger, "Possible reasons:")
    log_message(logger, "  1. No campaign started in IL-2 yet")
    log_message(logger, "     → Start a career campaign in IL-2, fly at least one mission")
    log_message(logger)
    log_message(logger, "  2. IL-2 installation path incorrect in campaign_mission_dates.json")
    if game_dir: 
        log_message(logger, f"     → Current path: {game_dir}")
    log_message(logger, "     → Re-run setup (delete campaign_mission_dates. json and restart)")
    log_message(logger)
    log_message(logger, "  3. Permission issues accessing IL-2 directory")
    log_message(logger, "     → Try running tracker as Administrator")
    log_message(logger)


def start_monitoring(il2_states_path: Path = None, exit_with_il2: bool = True) -> int:
    """
    Start the campaign monitor. 
    
    Args:
        il2_states_path:  Path to campaignsstates.txt (optional)
        exit_with_il2: If True, exit tracker when IL-2 closes (default: True)
        
    Returns:
        Exit code:  0 = normal exit, 1 = error
    """
    print_header("MONITORING ACTIVE")
    log_message(logger, "Checking for changes every second...")
    log_message(logger)
    log_message(logger, "This window will stay open - you can minimize it.")
    log_message(logger, "The tracker will automatically update your campaigns.")
    log_message(logger)
    if exit_with_il2:
        log_message(logger, "Tracker will exit when IL-2 closes.")
        log_message(logger, "(Use --no-exit-with-il2 to keep running)")
    else:
        log_message(logger, "Tracker will keep running after IL-2 closes.")
    log_message(logger)
    log_message(logger, "Press Ctrl+C to stop.")
    log_message(logger)
    
    try:
        import monitor_campaigns
        monitor = monitor_campaigns.CampaignMonitor(
            check_interval=1,
            use_file_watcher=True,
            il2_states_path=il2_states_path,
            debug=DEBUG_ENABLED,
            exit_with_il2=exit_with_il2
        )
        monitor.run()
        return 0
        
    except Exception as e:
        log_message(logger, f"❌ Monitor error:  {e}")
        import traceback
        traceback.print_exc()
        return 1


def run_tracker() -> int:
    """
    Main tracker execution. 
    """   
    # Parse command line arguments
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--skip-backup-gui', action='store_true',
                       help='Skip backup GUI (used only for automatic restart after restore)')
    parser.add_argument('--debug', action='store_true',
                        help='Enable debug logging output')
    parser.add_argument('--non-interactive', action='store_true',
                        help='Run without interactive prompts or backup restore GUI')
    parser.add_argument('--no-exit-with-il2', action='store_true',
                       help='Keep tracker running after IL-2 closes (default: exit with IL-2)')
    parser.add_argument('--skip-monitor', action='store_true',
                       help='Skip monitoring loop (for Settings Manager regeneration)')
    parser.add_argument('--locale', type=str,
                       help='Override locale for translations (e.g., de, en)')
    args, unknown = parser.parse_known_args()
    
    global DEBUG_ENABLED
    DEBUG_ENABLED = is_debug_enabled(args.debug)
    global logger
    logger = get_logger(__name__, debug=DEBUG_ENABLED)

    # ================================================================
    # DEBUG: Show command line arguments
    # ================================================================
    logger.debug("sys.argv = %s", sys.argv)
    logger.debug("Working directory = %s", os.getcwd())
    logger.debug("--skip-backup-gui = %s", args.skip_backup_gui)
    logger.debug("--non-interactive = %s", args.non_interactive)
    logger.debug("--skip-monitor = %s", args.skip_monitor)
    logger.debug("--locale = %s", args.locale)
    logger.debug("Unknown args = %s", unknown)
    if unknown:
        logger.warning("Unrecognized command-line arguments ignored: %s", unknown)
    log_message(logger, "=" * 70)
    log_message(logger, "IL-2 CAMPAIGN PROGRESS TRACKER v1.7")
    log_message(logger, "=" * 70)
    log_message(logger)
    
    # Change to script directory
    os.chdir(SCRIPT_DIR)
    
    # Step 0: Check config
    def wait_for_exit(message: str, exit_code: int) -> int:
        log_message(logger, message)
        if args.non_interactive:
            return exit_code
        safe_input("Press Enter to exit...")
        return exit_code

    if not check_config():
        return wait_for_exit("Configuration check failed.", 1)

    # Step 0.5: Preflight check for non-interactive first-run
    # In non-interactive mode, we cannot prompt for IL-2 path on first run
    can_continue, error_msg = check_first_run_setup(non_interactive=args.non_interactive)
    if not can_continue:
        log_message(logger)
        log_message(logger, "=" * 70)
        log_message(logger, "FIRST-TIME SETUP REQUIRED")
        log_message(logger, "=" * 70)
        log_message(logger)
        log_message(logger, error_msg)
        log_message(logger)
        return 0  # Clean exit - not an error, just need manual setup first
    
    # Step 1: First-time setup
    if not run_first_time_setup():
        return wait_for_exit("First-time setup failed.", 1)
    
    # Step 1.5: Sync campaign structure (detect new/deleted campaigns/missions)
    print_header("SYNCING CAMPAIGN STRUCTURE")
    sync_campaign_structure()
    
    # Step 2: Find IL-2 states path
    print_header("LOCATING IL-2 CAMPAIGN SAVE FILE")
    il2_states_path = find_il2_states_path()
    
    if il2_states_path and il2_states_path.exists():
        
        # ================================================================
        # Step 2. 5: Show backup restore GUI
        # Only skip if this is an automatic restart after restore
        # On manual starts, the GUI will always appear (if backups exist)
        # ================================================================
        if args.skip_backup_gui or args.non_interactive:
            log_message(logger)
            if args.non_interactive:
                log_message(logger, "ℹ️ Backup GUI skipped (non-interactive mode)")
            else:
                log_message(logger, "ℹ️ Backup GUI skipped (automatic restart after restore)")
        else:
            try:
                from backup_restore_gui import check_and_show_backup_gui, restart_tracker
                
                print_header("CHECKING FOR AVAILABLE BACKUPS")
                backup_result = check_and_show_backup_gui(il2_states_path)
                
                if backup_result == 'restored':
                    # ✅ NO RESTART! Just continue processing
                    # The backup has been restored, now we just need to:
                    # 1. Re-decode the campaigns
                    # 2. Regenerate events
                    # 3. Continue monitoring
                    log_message(logger)
                    log_message(logger, "=" * 70)
                    log_message(logger, "ℹ️  CONTINUING WITH RESTORED BACKUP")
                    log_message(logger, "=" * 70)
                    log_message(logger)
                    log_message(logger, "  The tracker will now re-process the restored state...")
                    log_message(logger, "  (This is faster than restarting!)")
                    log_message(logger)
                    
                    # ✅ CRITICAL: Clean up derived state files that may be inconsistent
                    cleanup_after_restore()
                    
                    # ✅ CRITICAL: Set flag to force event regeneration
                    # This ensures that PDFs, events, and all derived files
                    # are regenerated from the restored campaignsstates.txt
                    os.environ["FORCE_REGENERATE"] = "1"
                    log_message(logger, "  ⚡ Force regeneration enabled")
                    log_message(logger)
                    
                    # DON'T call restart_tracker()! Just continue to next step!
                    
                elif backup_result == 'cancelled': 
                    log_message(logger)
                    log_message(logger, "❌ Cancelled by user")
                    return wait_for_exit("User cancelled restore.", 2)
                    
                elif backup_result == 'skipped':
                    log_message(logger, "ℹ️ Backup restore skipped - continuing normally...")
                    
                elif backup_result == 'no_backups':
                    log_message(logger, "ℹ️ No backups available yet")
                    
            except ImportError as e:
                log_message(logger, f"ℹ️ Backup restore GUI not available: {e}")
            except Exception as e: 
                log_message(logger, f"⚠️ Backup GUI error: {e}")
                import traceback
                traceback.print_exc()
                log_message(logger)
                log_message(logger, "Continuing without backup restore option...")
                if not args.non_interactive:
                    safe_input("Press Enter to continue...")
        
        # Step 3: Decode campaign save
        print_header("DECODING CAMPAIGN SAVE")
        decode_campaign_save(il2_states_path)
        
        # Step 4: Popup restore check (automatic hash-based restore)
        print_header("CHECKING FOR MATCHING POPUP BACKUP (STATE RESTORE)")
        restore_popup_backup(il2_states_path)
        
        # Step 5: Event generation
        print_header("EVENT GENERATION CHECK")
        generate_initial_events(locale_override=args.locale)
        
        # Step 6: Cleanup check
        print_header("CHECKING FOR UNSUCCESSFUL MISSIONS")
        run_cleanup_check(il2_states_path)
        
        # Step 7: Popup reset cleanup
        print_header("CHECKING FOR RESET CAMPAIGNS (POPUP CLEANUP)")
        run_popup_reset_cleanup()
        
    else:
        show_campaign_not_found_message()

    # Step 8: Start monitoring (or exit if --skip-monitor)
    if args.skip_monitor:
        log_message(logger)
        log_message(logger, "=" * 70)
        log_message(logger, "REGENERATION COMPLETE")
        log_message(logger, "=" * 70)
        log_message(logger, "COMPLETE!")  # Marker for Settings Manager
        return 0

    return start_monitoring(il2_states_path, exit_with_il2=not args.no_exit_with_il2)


def main() -> int:
    """
    Entry point with exception handling.
    
    Returns:
        Exit code for sys.exit()
    """
    try: 
        return run_tracker()
        
    except KeyboardInterrupt:
        log_message(logger)
        log_message(logger, "=" * 70)
        log_message(logger, "TRACKER STOPPED BY USER")
        log_message(logger, "=" * 70)
        return 0
        
    except Exception as e:
        log_message(logger)
        log_message(logger, "=" * 70)
        log_message(logger, f"ERROR: {e}")
        log_message(logger, "=" * 70)
        import traceback
        traceback.print_exc()
        log_message(logger)
        safe_input("Press Enter to exit...")
        return 1


if __name__ == "__main__":
    exit_code = main()

    # ================================================================
    # DEBUG:  Always wait before closing (remove this later!)
    # ================================================================
    if exit_code != 0:
        log_message(logger)
        log_message(logger, f"[DEBUG] Exiting with code {exit_code}.  Press Enter to close...")
        safe_input()

    sys.exit(exit_code)
