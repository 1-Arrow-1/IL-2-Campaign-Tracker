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
import psutil
import sys
import io
import contextlib
import logging
from logging.handlers import RotatingFileHandler


class CampaignMonitor:
    def __init__(self, check_interval: int = 1, use_file_watcher: bool = True, il2_states_path=None):
        """
        Initialize campaign monitor
        
        Args:
            check_interval: Seconds between checks
                           Fast mode: 1 second recommended
                           Legacy mode: 5-10 seconds
            use_file_watcher: Enable fast file watching mode (recommended!)
                             True = Fast mode (reacts in 2-3 seconds)
                             False = Legacy polling mode
            il2_states_path: Path to campaignsstates.txt in IL-2 directory
                            (default: auto-detect)
        """
        self.check_interval = check_interval
        self.use_file_watcher = use_file_watcher
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
        
        # ✅ FIX #2: Log rotation - max 5 MB per file, keep 3 backups
        self.log_file = Path("campaign_monitor.log")
        self._setup_logging()
        
        # Determine paths (works for both script and EXE)
        if getattr(sys, 'frozen', False):
            # Running as EXE - use executable directory
            self.script_dir = Path(sys.executable).parent.resolve()
        else:
            # Running as script - use script directory
            self.script_dir = Path(__file__).parent.resolve()
        
        # Use provided IL-2 path or auto-detect
        if il2_states_path:
            self.campaign_file = Path(il2_states_path)
            self.campaigns_folder = self.campaign_file.parent
            print(f"[monitor] Using provided path: {self.campaign_file}")
        else:
            # Auto-detect (backward compatibility)
            # Load game directory from mission dates
            self.game_dir = self._load_game_directory()
            self.campaign_file = None
            self.campaigns_folder = None
            
            if self.game_dir:
                # Try to find campaignsstates.txt
                usersave_dir = self.game_dir / 'data' / 'swf' / 'il2' / 'usersave'
                
                if usersave_dir.exists():
                    for user_dir in usersave_dir.iterdir():
                        if user_dir.is_dir():
                            potential = user_dir / 'campaign' / 'campaignsstates.txt'
                            if potential.exists():
                                self.campaign_file = potential
                                self.campaigns_folder = user_dir / 'campaign'
                                break
        
        # Print mode
        mode = "⚡ FAST MODE (File Watcher)" if use_file_watcher else "🌍 LEGACY MODE (Polling)"
        print(f"\n{'='*70}")
        print(f"CAMPAIGN MONITOR - {mode}")
        print(f"{'='*70}")
        print(f"Check interval: {check_interval} second(s)")
        if use_file_watcher:
            print(f"Debounce: {self.debounce_seconds}s (prevents race conditions)")
            print(f"⚡ Fast mode enabled - popups appear within 2-3 seconds!")
        print(f"Log rotation: 5 MB max, 3 backups")
        print(f"{'='*70}\n")
    
    def _setup_logging(self):
        """
        ✅ FIX #2: Setup rotating log handler
        Max 5 MB per file, keeps 3 backup files
        """
        # Create logger
        self.logger = logging.getLogger('CampaignMonitor')
        self.logger.setLevel(logging.INFO)
        
        # Remove existing handlers
        self.logger.handlers.clear()
        
        # Rotating file handler (5 MB max, 3 backups)
        file_handler = RotatingFileHandler(
            self.log_file,
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=3,
            encoding='utf-8'
        )
        
        # Format with timestamp
        formatter = logging.Formatter('[%(asctime)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        file_handler.setFormatter(formatter)
        
        # Console handler (also print to console)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        
        # Add both handlers
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
    
    def _load_game_directory(self):
        """Load game directory from mission dates file"""
        mission_dates = self.script_dir / "campaign_mission_dates.json"
        if mission_dates.exists():
            try:
                with open(mission_dates, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    game_dir_str = data.get('game_directory', '')
                    if game_dir_str:
                        return Path(game_dir_str).expanduser().resolve()
            except Exception as e:
                self.log(f"Warning: Could not load game directory: {e}")
        return None
    
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
            self.log("📋 Processing campaigns...")
            
            # NO SYNC NEEDED - we read directly from IL-2!
            
            # Run decoder with IL-2 path
            try:
                import decode_campaign_usersave1
                if self.campaign_file:
                    decode_campaign_usersave1.main(states_path=str(self.campaign_file))
                else:
                    decode_campaign_usersave1.main()  # Fallback for backward compat
            except Exception as e:
                self.log(f"Decoder error: {e}")
            
            # Run event generator
            try:
                import step3_generate_events
                
                step3_generate_events.main(show_popups=True)
                    
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
    
    args = parser.parse_args()
    
    monitor = CampaignMonitor(
        check_interval=args.interval,
        use_file_watcher=not args.legacy
    )
    
    monitor.run()


if __name__ == "__main__":
    main()
