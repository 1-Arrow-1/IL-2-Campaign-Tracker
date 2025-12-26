#!/usr/bin/env python3
"""
IL-2 Campaign Progress Tracker - Automatic Monitor

Monitors IL-2 game and automatically updates campaign events when missions complete.

Features:
- Detects when IL-2.exe is running
- Monitors campaignsstates.txt for changes
- Automatically runs decoder + event generator
- Prevents duplicate processing
- Logs all activity

Usage:
    python monitor_campaigns.py
    
    (runs in background, press Ctrl+C to stop)
"""

import time
import subprocess
import os
import json
import hashlib
from pathlib import Path
from datetime import datetime
import psutil
import sys
import io
import contextlib


class CampaignMonitor:
    def __init__(self, check_interval: int = 10):
        """
        Initialize campaign monitor
        
        Args:
            check_interval: Seconds between checks (default: 10)
        """
        self.check_interval = check_interval
        self.last_hash = None
        self.last_campaigns_hash = None  # Track campaigns folder changes
        self.processing = False
        self.game_running = False
        self.il2_was_running = False  # Track if IL-2 was running previously
        
        # Log file - MUST be set before calling any methods that use log()
        self.log_file = Path("campaign_monitor.log")
        
        # Load configuration
        try:
            with open('campaign_mission_dates.json', 'r') as f:
                config = json.load(f)
                self.game_directory = config.get('game_directory')
        except:
            self.game_directory = None
        
        # Build path to save file
        if self.game_directory:
            self.save_file_base = Path(self.game_directory) / "data" / "swf" / "il2" / "usersave"
        else:
            self.save_file_base = None
        
        # Find campaignsstates.txt
        self.save_file = self.find_save_file()
        
        self.log("="*70)
        self.log("IL-2 CAMPAIGN MONITOR STARTED")
        self.log("="*70)
        self.log(f"Check interval: {check_interval} seconds")
        self.log(f"Game directory: {self.game_directory}")
        self.log(f"Save file: {self.save_file}")
        self.log("")
        
        # Auto-refresh mission dates on startup
        new_campaigns = self.refresh_mission_dates()
        
        # Show country validation GUI if new campaigns detected
        if new_campaigns:
            self.show_country_validation_gui(new_campaigns)
    
    def refresh_mission_dates(self):
        """
        Refresh mission dates by running step1 (if game directory known)
        
        Returns:
            List of new campaign names (for country validation), or empty list
        """
        if not self.game_directory:
            self.log("Skipping mission date refresh - no game directory configured")
            return []
        
        self.log("Checking for new campaigns and missions...")
        
        # Check for new campaigns or missions
        try:
            campaigns_path = Path(self.game_directory) / 'data' / 'Campaigns'
            if not campaigns_path.exists():
                self.log("Warning: Campaigns folder not found")
                return
            
            # Get actual campaign folders (exclude WW1 by default)
            campaign_folders = [
                f for f in campaigns_path.iterdir() 
                if f.is_dir() and 'flyingcircus' not in f.name.lower()
            ]
            
            # Load known campaigns from JSON
            try:
                with open('campaign_mission_dates.json', 'r') as f:
                    config = json.load(f)
                    known_campaigns = {k: v for k, v in config.items() if k != 'game_directory'}
            except:
                known_campaigns = {}
            
            # Detect removed campaigns and missions
            # 🔍 Detect removed campaigns and missions
            try:
                if known_campaigns:
                    # Detect if this is a new or empty config (first run)
                    if not known_campaigns or all(not c.get("missions") for c in known_campaigns.values()):
                        self.log("First run detected — skipping deletion check.")
                    else:
                        live_campaigns = {folder.name for folder in campaign_folders}

                        # --- Detect removed campaigns ---
                        removed_campaigns = [
                            name for name in known_campaigns.keys()
                            if name not in live_campaigns
                        ]

                        # --- Detect removed missions within existing campaigns ---
                        removed_missions = []
                        for name, campaign_data in known_campaigns.items():
                            if name not in live_campaigns:
                                continue

                            campaign_path = Path(self.game_directory) / "data" / "Campaigns" / name
                            if not campaign_path.exists():
                                continue

                            existing_missions = campaign_data.get("missions", {})
                            if not existing_missions:
                                continue  # skip pre-scan or first run

                            # Detect current mission files (.cmpbin / .msnbin)
                            valid_mission_exts = {".cmpbin", ".msnbin"}
                            actual_mission_names = {
                                f.stem for f in campaign_path.iterdir()
                                if f.suffix.lower() in valid_mission_exts
                            }

                            # Compare JSON vs actual mission files — remove only missing ones
                            removed = [
                                m for m in existing_missions
                                if Path(existing_missions[m].get("mission_file", "")).stem not in actual_mission_names
                            ]

                            if removed:
                                removed_missions.append({"campaign": name, "missions": removed})

                        # --- Apply deletions if found ---
                        if removed_campaigns or removed_missions:
                            self.log("=" * 70)
                            self.log(f"Detected {len(removed_campaigns)} removed campaign(s) "
                                     f"and {len(removed_missions)} campaign(s) with removed missions.")

                            # Remove deleted campaigns
                            for name in removed_campaigns:
                                self.log(f"  - Removing deleted campaign: {name}")
                                known_campaigns.pop(name, None)

                            # Remove deleted missions and update mission counts
                            for entry in removed_missions:
                                camp = entry["campaign"]
                                for mission in entry["missions"]:
                                    self.log(f"  - Removing mission '{mission}' from campaign '{camp}'")
                                    if "missions" in known_campaigns.get(camp, {}):
                                        known_campaigns[camp]["missions"].pop(mission, None)

                                # 🧩 Recalculate mission_count for this campaign
                                remaining_missions = known_campaigns.get(camp, {}).get("missions", {})
                                new_count = len(remaining_missions)
                                known_campaigns[camp]["mission_count"] = new_count
                                self.log(f"  - Updated mission count for '{camp}': {new_count}")

                            # ✅ Update config JSON safely
                            game_dir = config.get("game_directory")
                            config = known_campaigns
                            if game_dir:
                                config["game_directory"] = game_dir

                            with open('campaign_mission_dates.json', 'w', encoding='utf-8') as f:
                                json.dump(config, f, indent=2, ensure_ascii=False)

                            self.log("✓ Updated campaign_mission_dates.json after deletions")
                            self.log("=" * 70)

            except Exception as e:
                self.log(f"⚠️ Error during deletion detection: {e}")

            # 🔍 Detect new campaigns or added missions
            new_campaigns = []
            campaigns_with_new_missions = []

            # Create lowercase mapping for case-insensitive comparison
            known_campaigns_lower = {k.lower(): (k, v) for k, v in known_campaigns.items()}

            for folder in campaign_folders:
                campaign_name = folder.name.lower()

                # --- Detect completely new campaigns ---
                if campaign_name not in known_campaigns_lower:
                    new_campaigns.append(folder.name)
                    continue

                # --- Detect added missions in existing campaign ---
                valid_mission_exts = {".cmpbin", ".msnbin"}
                mission_files = [
                    f for f in folder.iterdir()
                    if f.suffix.lower() in valid_mission_exts
                ]
                actual_mission_count = len(mission_files)

                original_name, campaign_data = known_campaigns_lower[campaign_name]
                known_mission_count = campaign_data.get('mission_count', 0)

                # Only refresh if actual count increased
                if actual_mission_count > known_mission_count:
                    campaigns_with_new_missions.append({
                        'name': folder.name,
                        'old': known_mission_count,
                        'new': actual_mission_count
                    })

            # --- Log and trigger refresh if needed ---
            needs_refresh = len(new_campaigns) > 0 or len(campaigns_with_new_missions) > 0

            if needs_refresh:
                if new_campaigns:
                    self.log(f"  New campaigns: {len(new_campaigns)}")
                    for camp in new_campaigns[:3]:
                        self.log(f"    - {camp}")
                    if len(new_campaigns) > 3:
                        self.log(f"    ... and {len(new_campaigns) - 3} more")

                if campaigns_with_new_missions:
                    self.log(f"  Campaigns with new missions: {len(campaigns_with_new_missions)}")
                    for camp in campaigns_with_new_missions[:3]:
                        self.log(f"    - {camp['name']}: {camp['old']} → {camp['new']} missions")
                    if len(campaigns_with_new_missions) > 3:
                        self.log(f"    ... and {len(campaigns_with_new_missions) - 3} more")

                self.log("Refreshing mission dates...")

                try:
                    import step1_extract_mission_dates
                    import io, sys
                    old_stdout, old_argv = sys.stdout, sys.argv
                    sys.stdout = io.StringIO()
                    sys.argv = ['step1_extract_mission_dates.py', '--auto', self.game_directory]
                    try:
                        step1_extract_mission_dates.main()
                        success, error_msg = True, None
                    except Exception as e:
                        success, error_msg = False, str(e)
                    finally:
                        sys.stdout, sys.argv = old_stdout, old_argv

                    if success:
                        self.log("✓ Mission dates refreshed successfully")
                        return new_campaigns  # Return list of new campaigns for validation
                    else:
                        self.log(f"Warning: Mission date refresh failed: {error_msg}")
                        return []

                except ImportError as e:
                    self.log(f"ERROR: Cannot import step1_extract_mission_dates: {e}")
                    self.log("Please ensure step1_extract_mission_dates.py is in the same folder.")
                    return []

            else:
                total_campaigns = len(campaign_folders)
                self.log(f"✓ No new campaigns or missions detected ({total_campaigns} campaigns)")
                return []  # No new campaigns
                
        except Exception as e:
            self.log(f"⚠️ Error while refreshing mission dates: {e}")
            return []
    
    def show_country_validation_gui(self, new_campaigns: list):
        """Show country validation GUI for new campaigns"""
        if not new_campaigns:
            return
        
        self.log("")
        self.log("=" * 70)
        self.log(f"NEW CAMPAIGNS DETECTED: {len(new_campaigns)}")
        self.log("=" * 70)
        self.log("Please verify the automatically detected countries...")
        self.log("")
        
        try:
            from country_validator_gui import validate_new_campaigns
            mission_dates_file = Path("campaign_mission_dates.json")
            
            if mission_dates_file.exists():
                validate_new_campaigns(str(mission_dates_file), new_campaigns)
                self.log("✓ Country validation complete")
            else:
                self.log("Warning: campaign_mission_dates.json not found")
                
        except Exception as e:
            self.log(f"Warning: Could not show country validation GUI: {e}")
            self.log("You can manually edit campaign_mission_dates.json")
        
        self.log("=" * 70)
        self.log("")
    
    def get_campaigns_folder_hash(self) -> str:
        """
        Generate hash of campaigns folder structure
        (campaign names and mission counts only, not file contents)
        """
        try:
            if not self.game_directory:
                return None
            
            campaigns_folder = Path(self.game_directory) / "data" / "Campaigns"
            if not campaigns_folder.exists():
                return None
            
            # List all campaign folders and their .msnbin/.cmpbin counts
            campaign_data = []
            for campaign_folder in sorted(campaigns_folder.iterdir()):
                if campaign_folder.is_dir():
                    mission_count = len(list(campaign_folder.glob("*.msnbin"))) + len(list(campaign_folder.glob("*.cmpbin")))
                    campaign_data.append(f"{campaign_folder.name}:{mission_count}")
            
            # Create hash
            data_str = "|".join(campaign_data)
            return hashlib.md5(data_str.encode()).hexdigest()
            
        except Exception as e:
            self.log(f"Error checking campaigns folder: {e}")
            return None
    
    def find_save_file(self) -> Path:
        """Find the campaignsstates.txt file (prefer live IL-2 save, fallback to local copy)."""

        # 1) Prefer the live IL-2 save location
        if self.save_file_base and self.save_file_base.exists():
            # Find UUID folder (there should typically be only one)
            uuid_folders = [f for f in self.save_file_base.iterdir() if f.is_dir()]

            if uuid_folders:
                uuid_folder = uuid_folders[0]
                live_save_file = uuid_folder / "campaign" / "campaignsstates.txt"

                if live_save_file.exists():
                    self.log(f"Found live save file: {live_save_file}")
                    return live_save_file
                else:
                    self.log(f"Warning: Live save file not found at {live_save_file}")
            else:
                self.log("Warning: No UUID folders found in usersave directory")
        else:
            self.log("Warning: Cannot find IL-2 save directory")

        # 2) Fallback: use local copy if present
        # NOTE: We only use local copy as absolute fallback (offline mode)
        local_copy = Path("campaignsstates.txt")
        if local_copy.exists():
            self.log(f"Using local save file (offline mode - no IL-2 save found): {local_copy}")
            return local_copy

        return None
    
    def log(self, message: str):
        """Write to log file and console"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] {message}"
        
        # Console
        print(log_message)
        
        # File
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_message + '\n')
    
    def is_il2_running(self) -> bool:
        """Check if IL-2.exe is running"""
        for proc in psutil.process_iter(['name']):
            try:
                if proc.info['name'].lower() in ['il-2.exe', 'il2.exe']:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return False
    
    def should_exit(self) -> bool:
        """
        Check if monitor should exit (IL-2 closed after running)
        
        Returns:
            True if IL-2 was running but now closed
        """
        il2_running = self.is_il2_running()
        
        # If IL-2 was running but now isn't, exit
        if self.il2_was_running and not il2_running:
            return True
        
        # Update state
        self.il2_was_running = il2_running or self.il2_was_running
        
        return False
    
    def get_file_hash(self, filepath: Path) -> str:
        """Get MD5 hash of file using chunked reading for efficiency"""
        if not filepath or not filepath.exists():
            return None
        
        try:
            md5 = hashlib.md5()
            with open(filepath, 'rb') as f:
                # Read in 4MB chunks
                for chunk in iter(lambda: f.read(4194304), b""):
                    md5.update(chunk)
            return md5.hexdigest()
        except:
            return None
    
    def wait_for_file_stable(self, filepath: Path, timeout: int = 5) -> bool:
        """
        Wait for file to stop being written to
        
        Args:
            filepath: File to monitor
            timeout: Max seconds to wait
            
        Returns:
            True if file is stable, False if timeout
        """
        start_time = time.time()
        last_hash = self.get_file_hash(filepath)
        
        while time.time() - start_time < timeout:
            time.sleep(0.5)
            current_hash = self.get_file_hash(filepath)
            
            if current_hash == last_hash:
                return True  # File is stable
            
            last_hash = current_hash
        
        return False  # Timeout
    
    def copy_save_file(self) -> bool:
        """Copy save file to working directory"""
        if not self.save_file or not self.save_file.exists():
            return False
        
        try:
            import shutil
            local_copy = Path("campaignsstates.txt")
            shutil.copy(self.save_file, local_copy)
            self.log(f"Copied save file to: {local_copy}")
            return True
        except Exception as e:
            self.log(f"Error copying save file: {e}")
            return False
    
    def run_decoder(self) -> bool:
        """Run the decoder (works both as .py and as PyInstaller EXE)."""
        try:
            self.log("Running decoder...")

            # If running as EXE, call the module directly (no external python process).
            if getattr(sys, "frozen", False):
                try:
                    import decode_campaing_usersave1
                except Exception as e:
                    self.log(f"✗ Decoder import failed inside EXE: {e}")
                    return False

                buf = io.StringIO()
                try:
                    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                        if hasattr(decode_campaing_usersave1, "main"):
                            decode_campaing_usersave1.main()
                        else:
                            raise RuntimeError("decode_campaing_usersave1.main() not found")
                except Exception as e:
                    self.log(f"✗ Decoder failed inside EXE: {e}")
                    out = buf.getvalue().strip()
                    if out:
                        self.log(out)
                    return False

                out = buf.getvalue().strip()
                if out:
                    for line in out.splitlines():
                        self.log(line)
                self.log("✓ Decoder completed successfully")
                return True

            # Running as script: use the current interpreter, not "python"
            result = subprocess.run(
                [sys.executable, "decode_campaing_usersave1.py"],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.stdout:
                for line in result.stdout.splitlines():
                    self.log(line)
            if result.stderr:
                for line in result.stderr.splitlines():
                    self.log(line)

            if result.returncode == 0:
                self.log("✓ Decoder completed successfully")
                return True

            self.log(f"✗ Decoder failed (exit code {result.returncode})")
            return False

        except subprocess.TimeoutExpired:
            self.log("✗ Decoder timeout")
            return False
        except Exception as e:
            self.log(f"✗ Decoder error: {e}")
            return False
    
    def run_event_generator(self) -> bool:
        """Run the event generator (works both as .py and as PyInstaller EXE)."""
        try:
            self.log("Running event generator...")

            # If running as EXE, call the module directly (no external python process).
            if getattr(sys, "frozen", False):
                try:
                    import step3_generate_events
                except Exception as e:
                    self.log(f"✗ Event generator import failed inside EXE: {e}")
                    return False

                buf = io.StringIO()
                try:
                    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                        if hasattr(step3_generate_events, "main"):
                            step3_generate_events.main()
                        else:
                            raise RuntimeError("step3_generate_events.main() not found")
                except Exception as e:
                    self.log(f"✗ Event generator failed inside EXE: {e}")
                    out = buf.getvalue().strip()
                    if out:
                        self.log(out)
                    return False

                out = buf.getvalue().strip()
                if out:
                    # Keep your summary lines plus full output for debugging
                    for line in out.splitlines():
                        if ("Generated events for" in line) or ("Updated" in line):
                            self.log(f"  {line.strip()}")
                        else:
                            self.log(line)

                self.log("✓ Event generator completed")
                return True

            # Running as script: use the current interpreter, not "python"
            result = subprocess.run(
                [sys.executable, "step3_generate_events.py"],
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.stdout:
                for line in result.stdout.splitlines():
                    if ("Generated events for" in line) or ("Updated" in line):
                        self.log(f"  {line.strip()}")
                    else:
                        self.log(line)
            if result.stderr:
                for line in result.stderr.splitlines():
                    self.log(line)

            if result.returncode == 0:
                self.log("✓ Event generator completed")
                return True

            self.log(f"✗ Event generator failed (exit code {result.returncode})")
            return False

        except subprocess.TimeoutExpired:
            self.log("✗ Event generator timeout")
            return False
        except Exception as e:
            self.log(f"✗ Event generator error: {e}")
            return False
    
    def process_changes(self):
        """Process detected changes"""
        if self.processing:
            self.log("Already processing, skipping...")
            return
        
        self.processing = True
        
        try:
            self.log("")
            self.log("="*70)
            self.log("CHANGES DETECTED - Processing...")
            self.log("="*70)
            
            # Step 1: ALWAYS copy save file to ensure we have latest data
            # This is critical: even if local copy exists, we want fresh data from IL-2
            if self.save_file and self.save_file.exists():
                if self.save_file != Path("campaignsstates.txt"):
                    # Copying from IL-2 save directory
                    if not self.copy_save_file():
                        self.log("✗ Failed to copy save file")
                        return
                    self.log(f"✓ Copied latest save from: {self.save_file}")
                else:
                    # Using local copy (offline mode)
                    self.log("Processing local campaignsstates.txt (offline mode)")
            else:
                self.log("✗ No save file found")
                return
            
            # Step 2: Run decoder
            if not self.run_decoder():
                self.log("✗ Processing failed at decoder stage")
                return
            
            # Step 3: Run event generator
            if not self.run_event_generator():
                self.log("✗ Processing failed at event generator stage")
                return
            
            self.log("="*70)
            self.log("✓ PROCESSING COMPLETE")
            self.log("="*70)
            self.log("")
            
        finally:
            self.processing = False
    
    def check_for_changes(self) -> bool:
        """Check if save file has changed"""
        if not self.save_file:
            return False
        
        # Wait for file to be stable
        if not self.wait_for_file_stable(self.save_file):
            self.log("Warning: Save file still being written, skipping...")
            return False
        
        current_hash = self.get_file_hash(self.save_file)
        
        if current_hash is None:
            return False
        
        if self.last_hash is None:
            # First check, just record hash
            self.last_hash = current_hash
            return False
        
        if current_hash != self.last_hash:
            # File changed!
            self.last_hash = current_hash
            return True
        
        return False
    
    def run(self):
        """Main monitoring loop"""
        
        if not self.save_file:
            self.log("ERROR: Cannot find save file. Please:")
            self.log("  1. Run step1_extract_mission_dates.py first")
            self.log("  2. Or copy campaignsstates.txt to this directory")
            return
        
        # CRITICAL: Copy save file at startup to ensure we have latest data
        self.log("Initializing...")
        if self.save_file != Path("campaignsstates.txt"):
            self.log(f"Copying latest save file from: {self.save_file}")
            if self.copy_save_file():
                self.log("✓ Initial save file copied successfully")
            else:
                self.log("⚠️ Warning: Failed to copy save file, will use existing local copy")
        
        self.log("Monitoring started. Press Ctrl+C to stop.")
        self.log("")
        
        try:
            while True:
                # Check if should exit (IL-2 closed)
                if self.should_exit():
                    self.log("")
                    self.log("="*70)
                    self.log("IL-2 CLOSED - Exiting in 5 seconds...")
                    self.log("="*70)
                    time.sleep(5)
                    break
                
                # Check if IL-2 is running
                il2_running = self.is_il2_running()
                
                if il2_running != self.game_running:
                    self.game_running = il2_running
                    if il2_running:
                        self.log("IL-2 detected running")
                    else:
                        self.log("IL-2 not running")
                
                # Check for changes (even if IL-2 not running - useful for testing)
                
                # Check 1: campaignsstates.txt changes (mission progress)
                if self.check_for_changes():
                    self.process_changes()
                
                # Check 2: Campaigns folder changes (new/removed campaigns or missions)
                current_campaigns_hash = self.get_campaigns_folder_hash()
                if current_campaigns_hash and current_campaigns_hash != self.last_campaigns_hash:
                    if self.last_campaigns_hash is not None:  # Skip on first check
                        # Folder changed - refresh and validate
                        new_campaigns = self.refresh_mission_dates()
                        if new_campaigns:
                            self.show_country_validation_gui(new_campaigns)
                    self.last_campaigns_hash = current_campaigns_hash
                
                # Wait before next check
                time.sleep(self.check_interval)
                
        except KeyboardInterrupt:
            self.log("")
            self.log("="*70)
            self.log("MONITOR STOPPED BY USER")
            self.log("="*70)


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='IL-2 Campaign Monitor - Automatic event generation'
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=10,
        help='Check interval in seconds (default: 10)'
    )
    
    args = parser.parse_args()
    
    monitor = CampaignMonitor(check_interval=args.interval)
    monitor.run()


if __name__ == "__main__":
    main()
