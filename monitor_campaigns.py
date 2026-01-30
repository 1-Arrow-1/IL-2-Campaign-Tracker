#!/usr/bin/env python3
"""
IL-2 Campaign Progress Tracker - Automatic Monitor

Monitors IL-2 game and automatically updates campaign events when missions complete.

Version 2.1: IMPROVED RELIABILITY
✅ FIX: Increased debounce time to 1.5s (prevents race conditions)
✅ FIX: Log rotation (max 5MB per file, keeps 3 backups)
✅ FIX: Better file-change detection with retry logic

Features:
- Detects when IL-2.exe is running
- TWO MODES:
  * FAST MODE (file watcher): Reacts within 2-3 seconds! ⚡
  * LEGACY MODE (polling): Checks every N seconds
- Automatically runs decoder + event generator
- Prevents duplicate processing
- Logs all activity with rotation

Usage:
    # Fast mode (recommended):
    monitor = CampaignMonitor(check_interval=1, use_file_watcher=True)
    
    # Legacy mode:
    monitor = CampaignMonitor(check_interval=5, use_file_watcher=False)
"""

import time
import subprocess
import os
import json
import hashlib
from pathlib import Path
from datetime import datetime
import sys
import io
import contextlib

from utils.il2_paths import resolve_il2_paths
from utils.logging import get_logger, log_message
from utils.pathing import get_base_path
# ================================================================
# DEBUG: psutil import test
# ================================================================
logger = get_logger(__name__)
logger.debug("sys.executable: %s", sys.executable)
logger.debug("sys.frozen: %s", getattr(sys, 'frozen', False))

try:
    import psutil
    logger.debug("psutil imported successfully: %s", psutil.__file__)
    PSUTIL_AVAILABLE = True
except ImportError as e: 
    logger.debug("psutil import FAILED: %s", e)
    PSUTIL_AVAILABLE = False
except Exception as e: 
    logger.debug("psutil unexpected error: %s: %s", type(e).__name__, e)
    PSUTIL_AVAILABLE = False
# ================================================================

class CampaignMonitor:
    def __init__(self, check_interval: int = 1, use_file_watcher: bool = True,
                 il2_states_path=None, debug: bool | None = None,
                 log_path: str | None = None, exit_with_il2: bool = False):
        """
        Initialize campaign monitor
        
        Args:
            check_interval: Seconds between checks
                           Fast mode: 1 second recommended
                           Legacy mode: 5-10 seconds
            use_file_watcher: Enable fast file watching mode (recommended!)
                             True = Fast mode (reacts in 2-3 seconds) and
                             runs the campaign watcher for new/changed campaigns
                             False = Legacy polling mode (no campaign watcher)
            il2_states_path: Path to campaignsstates.txt in IL-2 directory
                            (default: auto-detect)
            debug: Enable debug logging output (default: from IL2_TRACKER_DEBUG env)
            log_path: Optional log file path (default: campaign_monitor.log in script dir)
            exit_with_il2: If True, exit the tracker when IL-2 is closed (default: False)             
        """
        self.check_interval = check_interval
        self.use_file_watcher = use_file_watcher
        self.exit_with_il2 = exit_with_il2
        if debug is None:
            env_value = os.environ.get("IL2_TRACKER_DEBUG", "")
            debug = env_value.strip().lower() in {"1", "true", "yes", "on"}
        self.debug = debug
        self.last_hash = None
        self.last_campaigns_hash = None
        self.processing = False
        self.game_running = False
        self.il2_was_running = False
        
        # ✅ FIX #1: Increased debounce from 0.5s to 1.5s
        # This prevents race conditions when IL-2 writes the file in chunks
        self.debounce_seconds = 1.5 if use_file_watcher else 0
        self.pending_change = False
        self.debounce_timer = 0
        
        # Determine paths (works for both script and EXE)
        self.script_dir = get_base_path(__file__)
        self.mission_dates_path = self.script_dir / "campaign_mission_dates.json"
        self.mission_dates_mtime = None
        self.ww1_excluded = set()
        self.mission_dates = {}    
                  
        # ✅ FIX #2: Log rotation - max 5 MB per file, keep 3 backups
        self.log_file = Path(log_path).resolve() if log_path else self.script_dir / "campaign_monitor.log"
        self._setup_logging()
        
        # Use provided IL-2 path or auto-detect
        if il2_states_path:
            self.campaign_file = Path(il2_states_path)
            self.campaigns_folder = self.campaign_file.parent
            log_message(self.logger, f"[monitor] Using provided path: {self.campaign_file}")
        else:
            # Auto-detect (backward compatibility)
            paths = resolve_il2_paths(self.script_dir)
            self.game_dir = paths.game_directory
            self.campaign_file = paths.campaignsstates_path
            self.campaigns_folder = (
                self.campaign_file.parent if self.campaign_file else None
            )
        if self.use_file_watcher:
            # Starte verzögert den Watcher (nach 5 Sekunden)
            import threading, time

            if not hasattr(self, "_watcher_lock"):
                self._watcher_lock = threading.Lock()
            if not hasattr(self, "campaign_watcher_running"):
                self.campaign_watcher_running = False

            def delayed_start():
                with self._watcher_lock:
                    if self.campaign_watcher_running:
                        self.logger.debug("Campaign watcher already active, skipping duplicate launch.")
                        return
                    self.campaign_watcher_running = True
                self.logger.debug("delayed_start() thread launched")
                time.sleep(5)
                self.logger.debug("launching watcher...")
                self._start_campaign_watcher()

            threading.Thread(target=delayed_start, daemon=True).start()
                                    

        # Print mode
        mode = (
            "⚡ FAST MODE (File Watcher + Campaign Watcher)"
            if use_file_watcher
            else "🌍 LEGACY MODE (Polling, no Campaign Watcher)"
        )
        log_message(self.logger, f"\n{'='*70}")
        log_message(self.logger, f"CAMPAIGN MONITOR - {mode}")
        log_message(self.logger, f"{'='*70}")
        log_message(self.logger, f"Check interval: {check_interval} second(s)")
        if use_file_watcher:
            log_message(self.logger, f"Debounce: {self.debounce_seconds}s (prevents race conditions)")
            log_message(self.logger, f"⚡ Fast mode enabled - popups appear within 2-3 seconds!")
        log_message(self.logger, "Log rotation: 5 MB max, 3 backups")
        log_message(self.logger, f"{'='*70}\n")
        
        
        # 🟡 WW1 Filter - Skip user-marked campaigns
        self._load_mission_dates()
                
    def _restart_file_monitor(self):
        """Restart the main campaignsstates.txt file watcher."""
        try:
            log_message(self.logger, "[Monitor] 🔁 Restarting main file watcher after campaign rescan...")
            self.last_hash = None
            self.last_campaigns_hash = None
            self.processing = False
            self.pending_change = False
            self.debounce_timer = 0
            self.il2_was_running = False

            # Optional: kleine Pause für Stabilität
            time.sleep(2)
            log_message(self.logger, "[Monitor] ✅ File watcher re-initialized, monitoring resumed.")
        except Exception as e:
            self.log(f"⚠️ Could not restart file watcher: {e}")
            
    def _start_campaign_watcher(self):
        """Background watcher for detecting new/changed campaigns"""
        import time, json, subprocess, sys
        import step1_extract_mission_dates

        self.logger.debug("_start_campaign_watcher() entered")

        # 🔹 Load game_directory directly from campaign_mission_dates.json
        mission_dates_path = self.script_dir / "campaign_mission_dates.json"
        if mission_dates_path.exists():
            try:
                with open(mission_dates_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    game_dir_str = data.get("game_directory", "")
                    if game_dir_str:
                        self.game_dir = Path(game_dir_str).expanduser().resolve()
                        log_message(self.logger, f"[Monitor] ✅ Loaded game_directory from JSON: {self.game_dir}")
                    else:
                        log_message(self.logger, "[Monitor] ⚠️ game_directory key not found in JSON")
            except Exception as e:
                log_message(self.logger, f"[Monitor] ⚠️ Failed to read campaign_mission_dates.json: {e}")

        # 🟡 Build correct campaigns path <game_dir>\data\Campaigns
        if getattr(self, "game_dir", None):
            campaign_root = self.game_dir / "data" / "Campaigns"
            if campaign_root.exists():
                self.campaigns_folder = campaign_root
            else:
                log_message(self.logger, f"[Monitor] ⚠️ Campaigns folder not found: {campaign_root}")
                return
        else:
            log_message(self.logger, "[Monitor] ⚠️ No game_dir set - watcher aborted.")
            return

        log_message(self.logger, f"[Monitor] 🟢 Watching {self.campaigns_folder} for new campaigns...")
        self.logger.debug("entering monitoring loop...")

        # 🟢 Local helper to snapshot campaign structure
        def snapshot():
            snapshot_data = {}
            for folder in self.campaigns_folder.iterdir():
                if not folder.is_dir():
                    continue
                missions = []
                for pattern in ("*.Mission*", "*.mission*", "*.msnbin", "*.MSNBIN"):
                    for p in folder.glob(pattern):
                        try:
                            stat = p.stat()
                            missions.append((p.name, stat.st_mtime, stat.st_size))
                        except FileNotFoundError:
                            continue
                snapshot_data[folder.name] = tuple(sorted(missions))
            return snapshot_data

        prev_snapshot = snapshot()

        # 🔁 Continuous watcher loop
        while True:
            time.sleep(10)
            current_snapshot = snapshot()
            added = set(current_snapshot.keys()) - set(prev_snapshot.keys())
            removed = set(prev_snapshot.keys()) - set(current_snapshot.keys())
            changed = {
                name for name in current_snapshot.keys() & prev_snapshot.keys()
                if current_snapshot[name] != prev_snapshot[name]
            }

            if added or removed or changed:
                log_message(
                    self.logger,
                    f"[Monitor] 🔄 Added: {added} | Removed: {removed} | Changed: {changed} - rescanning...",
                )
                self.log(f"[Monitor] 🔄 Added: {added} | Removed: {removed} | Changed: {changed} - rescanning...")
                prev_snapshot = current_snapshot

                try:
                    import sys, subprocess, os

                    # 🔹 Pfad zur Script-Datei
                    step1_path = self.script_dir / "step1_extract_mission_dates.py"

                    # 🔹 Wenn die Datei existiert (z. B. im Dev-Modus) → starte sie als externen Prozess
                    if step1_path.exists():
                        if getattr(sys, "frozen", False):
                            python_exe = "python"
                        else:
                            python_exe = sys.executable

                        self.logger.debug("Launching external step1_extract_mission_dates.py")
                        self.logger.debug("Using interpreter: %s", python_exe)
                        subprocess.run(
                            [python_exe, str(step1_path), "--auto"],
                            cwd=self.script_dir,
                            check=True
                        )

                    # 🔹 Wenn die Datei nicht existiert (EXE-Modus) → direkt importieren und aufrufen
                    else:
                        self.logger.debug(
                            "step1_extract_mission_dates.py not found on disk – running internal import"
                        )
                        import step1_extract_mission_dates
                        step1_extract_mission_dates.main(args=["--auto"])

                    log_message(self.logger, "[Monitor] ✅ Extraction completed, resuming monitoring.")

                    try:
                        import yaml
                        from country_validator_gui import validate_countries

                        # Pfade
                        mission_json = self.script_dir / "campaign_mission_dates.json"
                        stock_yaml = self.script_dir / "stock_campaigns.yaml"

                        # Lade aktuelle Kampagnendaten
                        with open(mission_json, "r", encoding="utf-8") as f:
                            campaign_data = json.load(f)

                        # Lade Stock-Kampagnen (wenn vorhanden)
                        stock_campaigns = set()
                        if stock_yaml.exists():
                            with open(stock_yaml, "r", encoding="utf-8") as f:
                                try:
                                    data = yaml.safe_load(f)
                                    if isinstance(data, dict):
                                        stock_campaigns = set(data.keys())
                                    elif isinstance(data, list):
                                        stock_campaigns = set(data)
                                except Exception as e:
                                    self.log(f"⚠️ Could not read stock_campaigns.yaml: {e}")

                        # Prüfe, ob Added-Kampagnen nicht stock sind
                        custom_to_validate = [c for c in added if c not in stock_campaigns]

                        if custom_to_validate:
                            log_message(self.logger, f"[Monitor] 🟡 New custom campaigns detected: {custom_to_validate}")
                            #self.log(f"[Monitor] 🟡 New custom campaigns detected: {custom_to_validate}")
                            log_message(self.logger, "[Monitor] 🪶 Launching country validator GUI for user verification...")

                            validate_countries(str(mission_json))
                            log_message(self.logger, "[Monitor] ✅ Validation complete.")

                        else:
                            log_message(self.logger, "[Monitor] 💤 No custom campaigns needing validation found.")

                    except Exception as e:
                        log_message(self.logger, f"⚠️ Could not perform validation check: {e}")

                    # 🟢 Restart main file watcher (campaignsstates.txt watcher)
                    self._restart_file_monitor()
                except subprocess.CalledProcessError as e:
                    log_message(self.logger, f"⚠️ step1_extract_mission_dates exited with error: {e}")
                except Exception as e:
                    log_message(self.logger, f"⚠️ Could not rescan campaigns: {e}")
     
                
    def _setup_logging(self):
        """
        ✅ FIX #2: Setup rotating log handler
        Max 5 MB per file, keeps 3 backup files
        """
        self.logger = get_logger('CampaignMonitor', log_path=self.log_file, debug=self.debug)
    
    def _load_game_directory(self):
        """Load game directory from mission dates file"""
        paths = resolve_il2_paths(self.script_dir)
        if paths.game_directory:
            return paths.game_directory
        return None
     
    def _load_mission_dates(self) -> bool:
        """Load mission dates and refresh WW1 exclusion list if changed."""
        if not self.mission_dates_path.exists():
            return False

        try:
            current_mtime = self.mission_dates_path.stat().st_mtime
        except Exception as e:
            self.log(f"⚠️  Could not stat mission dates file: {e}")
            return False

        if self.mission_dates_mtime == current_mtime:
            return False

        try:
            with open(self.mission_dates_path, "r", encoding="utf-8") as f:
                mission_dates = json.load(f)
        except Exception as e:
            self.log(f"⚠️  Could not read mission dates: {e}")
            return False

        if not isinstance(mission_dates, dict):
            self.log("⚠️  Mission dates JSON is not a dictionary, skipping reload.")
            return False

        new_exclusions = {
            cname.lower()
            for cname, cdata in mission_dates.items()
            if isinstance(cdata, dict) and cdata.get("is_ww1", False)
        }

        if new_exclusions != self.ww1_excluded:
            added = sorted(new_exclusions - self.ww1_excluded)
            removed = sorted(self.ww1_excluded - new_exclusions)
            self.log(
                "[Monitor] 🟡 WW1 exclusions updated "
                f"(added={len(added)}, removed={len(removed)})"
            )

        self.ww1_excluded = new_exclusions
        self.mission_dates = mission_dates
        self.mission_dates_mtime = current_mtime

        game_dir_str = mission_dates.get("game_directory", "")
        if game_dir_str:
            self.game_dir = Path(game_dir_str).expanduser().resolve()

        return True
     
    def log(self, message: str):
        """Write message using rotating logger"""
        self.logger.info(message)
    
    def _get_file_hash(self, filepath: Path) -> str:
        """
        Calculate MD5 hash of file
        ✅ Added: File size check to prevent memory issues
        """
        try:
            # ✅ FIX #3: Check file size first
            file_size = filepath.stat().st_size
            max_size = 50 * 1024 * 1024  # 50 MB limit
            
            if file_size > max_size:
                self.log(f"⚠️  Warning: File too large ({file_size} bytes), using size+mtime hash")
                # Use file size + modification time as hash for very large files
                mtime = filepath.stat().st_mtime
                return hashlib.md5(f"{file_size}_{mtime}".encode()).hexdigest()
            
            with open(filepath, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception as e:
            self.log(f"⚠️  Hash calculation error: {e}")
            return ""
    
    def _check_il2_running(self) -> bool:
        """Check if IL-2 Sturmovik is running"""
        # Fallback wenn psutil nicht verfügbar
        if not PSUTIL_AVAILABLE:
            return True  # Annehmen, dass IL-2 läuft
        try:
            for proc in psutil.process_iter(['name']):
                if proc.info['name'] and 'il-2' in proc.info['name'].lower():
                    return True
        except Exception:
            pass
        return False
    
    def _sync_campaign_file(self):
        """Copy campaignsstates.txt from IL-2 to script directory"""
        if not self.campaign_file:
            return False
        
        local_file = self.script_dir / 'campaignsstates.txt'
        
        try:
            # Check if source file is newer
            if self.campaign_file.exists():
                import shutil
                shutil.copy2(self.campaign_file, local_file)
                return True
        except Exception as e:
            self.log(f"Warning: Could not sync campaign file: {e}")
        
        return False
    
    def _has_file_changed(self) -> bool:
        """
        Check if campaignsstates.txt has changed
        ✅ Added: Retry logic to handle file locks
        """
        # Watch the LIVE file in IL-2 directory!
        if not self.campaign_file or not self.campaign_file.exists():
            return False
        
        # ✅ FIX #4: Retry logic if file is locked
        max_retries = 3
        retry_delay = 0.1
        
        for attempt in range(max_retries):
            try:
                current_hash = self._get_file_hash(self.campaign_file)
                
                if not current_hash:
                    return False
                
                if self.last_hash is None:
                    self.last_hash = current_hash
                    return False
                
                if current_hash != self.last_hash:
                    self.last_hash = current_hash
                    return True
                
                return False
                
            except PermissionError:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                else:
                    self.log(f"⚠️  File locked after {max_retries} retries, skipping")
                    return False
            except Exception as e:
                self.log(f"⚠️  Error checking file: {e}")
                return False
        
        return False
    
    def _process_campaigns(self):
        """Run decoder and event generator"""
        if self.processing:
            return
        
        self.processing = True
        
        try:
            self._load_mission_dates()
            self.log("📋 Processing campaigns...")
            
            # NO SYNC NEEDED - we read directly from IL-2!
            
            # Run decoder with IL-2 path
            try:
                import decode_campaign_usersave1
                import io
                import contextlib
                
                # Capture stdout to log
                output_buffer = io.StringIO()
                with contextlib.redirect_stdout(output_buffer):
                    if self.campaign_file:
                        decode_campaign_usersave1.main(states_path=str(self.campaign_file))
                    else:
                        decode_campaign_usersave1.main()
                
                # Log captured output (only important lines)
                captured = output_buffer.getvalue()
                for line in captured.strip().split('\n'):
                    if line and any(x in line for x in ['✅', '❌', '⚠️', 'Decoded', 'campaigns']):
                        self.log(f"  [decode] {line.strip()}")
                        
            except Exception as e:
                self.log(f"Decoder error: {e}")
            
            # Run event generator
            try:
                import step3_generate_events
                import io
                import contextlib
                
                # Capture stdout to log
                output_buffer = io.StringIO()
                with contextlib.redirect_stdout(output_buffer):
                    step3_generate_events.main(args=["--auto"], show_popups=True)
                
                # Log captured output (all popup-related lines)
                captured = output_buffer.getvalue()
                for line in captured.strip().split('\n'):
                    if line and any(x in line for x in ['[popups]', '[DEBUG]', 'new event', 'initial sync', 'SHOWING NOW', 'deferred']):
                        self.log(f"  [events] {line.strip()}")
                    
            except Exception as e:
                self.log(f"Event generator error: {e}")
            
            # Check for reset campaigns and cleanup popups
            # IMPORTANT: This must run AFTER event generation because
            # it modifies campaign_popups_seen.json on disk, and we need
            # the next event generation cycle to reload the file
            try:
                from campaign_reset_checker import cleanup_popups_for_reset_campaigns
                cleanup_popups_for_reset_campaigns()
                self.log("✅ Reset cleanup complete")
            except Exception as e:
                self.log(f"⚠️  Reset cleanup error: {e}")
        
        finally:
            self.processing = False
    
    def run(self):
        """Start monitoring"""
        self.log("🚀 Monitor started!")
        
        # Show which file we're watching
        if self.campaign_file:
            self.log(f"Watching: {self.campaign_file}")
        else:
            self.log(f"⚠️  Campaign file not found yet - waiting...")
        
        if self.use_file_watcher:
            self.log(f"⚡ Fast mode: File watcher active (debounce: {self.debounce_seconds}s)")
        else:
            self.log(f"🌍 Legacy mode: Polling every {self.check_interval}s")
        
        # Initial hash from LIVE file
        if self.campaign_file and self.campaign_file.exists():
            self.last_hash = self._get_file_hash(self.campaign_file)
        
        try:
            while True:
                self._load_mission_dates()
                # Check if IL-2 is running
                self.game_running = self._check_il2_running()
                
                # Log IL-2 status changes
                if self.game_running:
                    if not self.il2_was_running:
                        self.log("🎮 IL-2 Sturmovik detected!")
                        self.il2_was_running = True
                else:
                    if self.il2_was_running:
                        self.log("👋 IL-2 Sturmovik closed")
                        self.il2_was_running = False

                        # CRITICAL FIX: Process any pending/final changes BEFORE exiting
                        # IL-2 may have saved campaign state right before closing
                        if self.exit_with_il2:
                            # Process any pending debounced changes
                            if self.pending_change:
                                self.log("📋 Processing pending changes before exit...")
                                self._process_campaigns()
                                self.pending_change = False

                            # Check for final file change (IL-2 may have saved on exit)
                            if self._has_file_changed():
                                self.log("📝 Final file change detected, processing before exit...")
                                self._process_campaigns()

                            self.log("🛑 Tracker exiting (exit_with_il2 enabled)")
                            break
                
                # Check for file changes
                if self._has_file_changed():
                    self.log(f"📝 File changed! (hash: {self.last_hash[:8]}...)")
                    
                    if self.use_file_watcher:
                        # File watcher mode - use debounce
                        self.pending_change = True
                        self.debounce_timer = time.time()
                    else:
                        # Legacy mode - process immediately
                        self._process_campaigns()
                
                # Process after debounce (file watcher mode only)
                if self.pending_change and (time.time() - self.debounce_timer) >= self.debounce_seconds:
                    self._process_campaigns()
                    self.pending_change = False
                
                # Sleep
                time.sleep(self.check_interval)
        
        except KeyboardInterrupt:
            self.log("\n👋 Monitor stopped by user")
        except Exception as e:
            self.log(f"\n❌ Monitor error: {e}")
            import traceback
            traceback.print_exc()
            raise


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='IL-2 Campaign Monitor')
    parser.add_argument('--interval', type=int, default=1,
                       help='Check interval in seconds (default: 1)')
    parser.add_argument('--legacy', action='store_true',
                       help='Use legacy polling mode instead of fast file watcher')
    parser.add_argument('--exit-with-il2', action='store_true',
                       help='Exit tracker when IL-2 is closed')
    
    args = parser.parse_args()
    
    monitor = CampaignMonitor(
        check_interval=args.interval,
        use_file_watcher=not args.legacy,
        exit_with_il2=args.exit_with_il2
    )
    
    monitor.run()


if __name__ == "__main__":
    main()
