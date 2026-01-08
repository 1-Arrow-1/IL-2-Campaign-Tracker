#!/usr/bin/env python3
"""
IL-2 Campaign Mission Cleanup Tool

Detects and allows deletion of unsuccessful last missions (takeOffStatus = 1)
from campaignsstates.txt, enabling replay for better results.
"""

import json
import re
import shutil
import urllib.parse
import hashlib
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Set
import tkinter as tk
from tkinter import ttk, messagebox

from utils.il2_paths import find_campaignsstates_path, read_game_directory
from utils.logging import get_logger, log_message
from utils.pathing import get_base_path

BASE_DIR = get_base_path(__file__)
CAMPAIGN_COMPLETION_STATE_FILE = BASE_DIR / "campaign_completion_state.json"


def _is_debug_enabled() -> bool:
    env_value = os.environ.get("IL2_TRACKER_DEBUG", "")
    return env_value.strip().lower() in {"1", "true", "yes", "on"}

logger = get_logger(__name__, debug=_is_debug_enabled())


# File to store "don't ask again" preferences
IGNORE_FILE = Path("cleanup_ignored_missions.json")


def load_ignored_missions() -> Set[str]:
    """
    Load list of missions that user chose to ignore
    
    Returns:
        Set of mission keys in format "campaign_name::mission_id"
    """
    if not IGNORE_FILE.exists():
        return set()
    
    try:
        with open(IGNORE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return set(data.get('ignored', []))
    except Exception as e:
        log_message(logger, f"Warning: Could not load ignored missions: {e}")
        return set()


def save_ignored_missions(ignored: Set[str]):
    """
    Save list of ignored missions
    
    Args:
        ignored: Set of mission keys in format "campaign_name::mission_id"
    """
    try:
        data = {
            'ignored': sorted(list(ignored)),
            'last_updated': datetime.now().isoformat()
        }
        with open(IGNORE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        log_message(logger, f"Warning: Could not save ignored missions: {e}")


def add_to_ignored(campaign_name: str, mission_id: str):
    """
    Add a mission to the ignore list
    
    Args:
        campaign_name: Campaign name
        mission_id: Mission identifier
    """
    ignored = load_ignored_missions()
    key = f"{campaign_name}::{mission_id}"
    ignored.add(key)
    save_ignored_missions(ignored)
    log_message(logger, f"✓ Added to ignore list: {campaign_name} - Mission {mission_id}")


def is_ignored(campaign_name: str, mission_id: str) -> bool:
    """
    Check if a mission is in the ignore list
    
    Args:
        campaign_name: Campaign name
        mission_id: Mission identifier
        
    Returns:
        True if mission should be ignored
    """
    ignored = load_ignored_missions()
    key = f"{campaign_name}::{mission_id}"
    return key in ignored
    
def _md5_file(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def _load_hash_index(index_path: Path) -> dict:
    if not index_path.exists():
        return {}
    try:
        with open(index_path, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _load_json_file(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
        log_message(logger, f"⚠️  Expected JSON object in {path}, got {type(data).__name__}")
        return {}
    except Exception as e:
        log_message(logger, f"⚠️  Could not read {path}: {e}")
        return {}

def _load_completion_state(path: Path = CAMPAIGN_COMPLETION_STATE_FILE) -> dict:
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception as e:
        log_message(logger, f"⚠️  Could not read completion state file {path}: {e}")
        return {}


def _save_completion_state(state: dict, path: Path = CAMPAIGN_COMPLETION_STATE_FILE) -> bool:
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
        return True
    except Exception as e:
        log_message(logger, f"⚠️  Could not save completion state file {path}: {e}")
        return False


def update_completion_state_for_campaign(
    campaign_name: str,
    campaign_data: Optional[dict] = None,
    decoded_path: Path = Path("campaigns_decoded.json"),
    state_path: Path = CAMPAIGN_COMPLETION_STATE_FILE,
) -> bool:
    if not campaign_data:
        decoded_data = _load_json_file(decoded_path)
        campaign_data = decoded_data.get(campaign_name)

    if not campaign_data:
        log_message(logger, f"    ⚠️  Could not update completion state; campaign '{campaign_name}' not found")
        return False

    state = _load_completion_state(state_path)
    completed = sorted(
        list(campaign_data.get("completedMissionsByFileName", {}).keys())
    )
    state[campaign_name] = completed

    if _save_completion_state(state, state_path):
        log_message(logger, f"    ✓ Updated completion state for campaign {campaign_name} after cleanup")
        return True
    return False



def resync_campaign_events_for_campaign(
    campaign_name: str,
    generator,
    decoded_path: Path = Path("campaigns_decoded.json"),
    events_path: Path = Path("campaign_events.json"),
) -> dict:
    decoded_data = _load_json_file(decoded_path)
    campaign_data = decoded_data.get(campaign_name)
    if not campaign_data:
        log_message(logger, f"    ⚠️  Campaign '{campaign_name}' not found in {decoded_path}")
        return {
            "events": [],
            "campaign_data": {},
            "completed_missions": [],
            "country": None,
            "combined_html": "",
        }

    completed_missions = list(
        campaign_data.get("completedMissionsByFileName", {}).keys()
    )

    events = generator.generate_events_for_campaign(campaign_name)
    events_data = _load_json_file(events_path)

    country = generator.mission_dates.get(campaign_name, {}).get("country")
    combined_html = ""

    if events:
        events_html = generator.generate_events_html(events, country)
        debriefings_html = ""
        if generator.log_processor and completed_missions:
            debriefings_html, _ = generator.generate_debriefings_html(
                campaign_name, completed_missions
            )
        combined_html = (
            f"{debriefings_html}\n{events_html}" if debriefings_html else events_html
        )
        events_data[campaign_name] = {
            "country": country,
            "events": events,
            "debriefings_html": debriefings_html,
            "events_html": events_html,
            "html": combined_html,
        }
        log_message(logger, f"    ✓ Resynced campaign_events.json")
    else:
        if completed_missions:
            log_message(logger, 
                f"    ⚠️  No events generated for '{campaign_name}' despite completed missions; "
                "clearing stale campaign_events.json entry"
            )
        else:
            log_message(logger, 
                f"    ℹ️  No completed missions for '{campaign_name}'; clearing campaign_events.json entry"
            )
        events_data[campaign_name] = []

    try:
        with open(events_path, "w", encoding="utf-8") as f:
            json.dump(events_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        log_message(logger, f"    ⚠️  Could not update {events_path}: {e}")

    return {
        "events": events,
        "campaign_data": campaign_data,
        "completed_missions": completed_missions,
        "country": country,
        "combined_html": combined_html,
    }


class MissionCleanup:
    """Handle cleanup of failed campaign missions"""
    
    def __init__(self, decoded_json_path: str = 'campaigns_decoded.json',
                 mission_dates_path: str = 'campaign_mission_dates.json',
                 campaignstates_path: str = None):
        """
        Initialize cleanup tool
        
        Args:
            decoded_json_path: Path to decoded campaign states
            mission_dates_path: Path to campaign mission dates
            campaignstates_path: Path to raw campaign states file (if None, auto-detect from game directory)
        """
        self.decoded_path = Path(decoded_json_path)
        self.dates_path = Path(mission_dates_path)
        
        # Auto-detect campaignsstates.txt location from game directory
        if campaignstates_path is None:
            self.states_path = self._find_campaignstates_file()
        else:
            self.states_path = Path(campaignstates_path)
        
        self.max_backups = 50
        
        log_message(logger, f"Using campaignsstates.txt: {self.states_path}")
        
    def _get_tracker_popups_path(self) -> Path:
        """
        Get path to campaign_popups_seen. json in TRACKER directory. 
        
        Note: The active popup file is in the tracker directory,
        while BACKUPS are stored in the IL-2 campaign directory.
        
        Returns:
            Path to campaign_popups_seen.json in tracker directory
        """
        import sys
        
        if getattr(sys, 'frozen', False):
            # EXE-Modus:  Verzeichnis der . exe
            tracker_dir = get_base_path(__file__)
        else:
            # Skript-Modus: Verzeichnis des Skripts
            script_dir = get_base_path(__file__)
            # Check if we're in a subdirectory (e.g., running from src/)
            if (script_dir / "step3_generate_events.py").exists():
                tracker_dir = script_dir
            elif (script_dir.parent / "step3_generate_events.py").exists():
                tracker_dir = script_dir.parent
            else: 
                tracker_dir = script_dir
        
        return tracker_dir / "campaign_popups_seen.json"    
    
    def _find_campaignstates_file(self) -> Path:
        """
        Find campaignsstates.txt in IL-2 game directory (new structure supported)
        """
        game_path = read_game_directory(self.dates_path.parent)
        if game_path:
            states_path = find_campaignsstates_path(game_path)
            if states_path:
                log_message(logger, f"✓ Found campaignsstates.txt in {states_path}")
                return states_path
            log_message(logger, "⚠️  campaignsstates.txt not found in expected IL-2 directories")
        else:
            log_message(logger, "⚠️  Could not read game directory from mission dates")

        # Fallback to current working directory
        fallback = Path('campaignsstates.txt')
        if fallback.exists():
            log_message(logger, f"⚠️  Using campaignsstates.txt from current directory (fallback)")
            return fallback

        log_message(logger, "❌ campaignsstates.txt not found! Please verify your IL-2 user save path.")
        raise FileNotFoundError("campaignsstates.txt not found in expected IL-2 user directory structure")

    
    def find_cleanup_opportunities(self) -> Dict:
        """
        Find ALL missions with takeOffStatus = 1 (unsuccessful)
        
        Returns:
            Dict of campaigns needing cleanup with their details
            Format: {campaign_name: {mission_id: details, ...}}
            (excludes missions marked as "don't ask again")
        """
        if not self.decoded_path.exists():
            log_message(logger, f"⚠️  {self.decoded_path} not found - cannot scan")
            return {}
        
        # Load decoded campaign states
        with open(self.decoded_path, 'r', encoding='utf-8') as f:
            decoded = json.load(f)
        
        # Load mission order (if available)
        mission_dates = {}
        if self.dates_path.exists():
            with open(self.dates_path, 'r', encoding='utf-8') as f:
                mission_dates = json.load(f)
        
        # Load ignored missions
        ignored = load_ignored_missions()
        
        opportunities = {}
        
        for campaign_name, campaign_data in decoded.items():
            # Skip non-campaign entries
            if campaign_name == 'game_directory':
                continue
            
            # Get mission stats
            stats = campaign_data.get('characterStatisticsByFileName', {})
            if not stats:
                continue
            
            # Determine mission order
            dates_data = mission_dates.get(campaign_name, {})
            all_missions = dates_data.get('missions', {})
            
            if all_missions:
                # Use chronological order from campaign_mission_dates
                mission_order = sorted(all_missions.keys(),
                                     key=lambda x: int(x) if x.isdigit() else 0)
            else:
                # Fallback: numeric sort
                mission_order = sorted(stats.keys(),
                                     key=lambda x: int(x) if x.isdigit() else 0)
            
            # *** NEW: Check ALL flown missions, not just last ***
            campaign_opportunities = {}
            
            for mission_id in mission_order:
                # Skip missions not in stats
                if mission_id not in stats:
                    continue
                
                # Check if ignored
                if is_ignored(campaign_name, mission_id):
                    continue
                
                mission_stats = stats[mission_id]
                
                # Check takeOffStatus
                takeoff_status = mission_stats.get('takeOffStatus', 2)
                
                # Mission is considered "locked" only if it both failed (takeOffStatus=1)
                # AND still exists in completedMissionsByFileName
                completed_missions = campaign_data.get('completedMissionsByFileName', {})
                if takeoff_status == 1 and mission_id in completed_missions:
                    # This mission needs cleanup!
                    
                    # Calculate kills
                    air_kills = (mission_stats.get('killLightPlane', 0) + 
                               mission_stats.get('killMediumPlane', 0) +
                               mission_stats.get('killHeavyPlane', 0))
                    
                    ground_kills = (mission_stats.get('killLightArmoredVehicle', 0) +
                                  mission_stats.get('killMediumArmoredVehicle', 0) +
                                  mission_stats.get('killHeavyArmoredVehicle', 0) +
                                  mission_stats.get('killCannon', 0) +
                                  mission_stats.get('killAAAGun', 0) +
                                  mission_stats.get('killMachinegun', 0))
                    
                    naval_kills = (mission_stats.get('killLightShip', 0) +
                                 mission_stats.get('killDestroyerShip', 0) +
                                 mission_stats.get('killLargeCargoShip', 0))
                    
                    # Format flight time
                    flight_time_seconds = mission_stats.get('totalFlightTime', 0)
                    minutes = int(flight_time_seconds / 60)
                    seconds = int(flight_time_seconds % 60)
                    flight_time_str = f"{minutes:02d}:{seconds:02d}"
                    
                    # Get mission position in campaign
                    flown_missions = [m for m in mission_order if m in stats]
                    mission_position = flown_missions.index(mission_id) + 1 if mission_id in flown_missions else 0
                    
                    campaign_opportunities[mission_id] = {
                        'mission_id': mission_id,
                        'mission_number': f"{mission_position} of {len(mission_order)}",
                        'air_kills': air_kills,
                        'ground_kills': ground_kills,
                        'naval_kills': naval_kills,
                        'flight_time': flight_time_str,
                        'raw_stats': mission_stats
                    }
            
            # Only add campaign if it has opportunities
            if campaign_opportunities:
                opportunities[campaign_name] = campaign_opportunities
        
        return opportunities
    
    def create_backup(self) -> Optional[Path]:
        """
        Create timestamped backup of campaignsstates.txt and the corresponding
        campaign_popups_seen.json, both linked by hash. 

        Prevents redundant backups within 60 seconds of the previous one. 
        Returns:
            Path to campaignsstates backup, or None if skipped/failed. 
        """
        if not self.states_path.exists():
            log_message(logger, f"⚠️  {self.states_path} not found - cannot backup")
            return None

        # --- Check for recent backup (last 60 seconds)
        index_path = self.states_path.parent / "campaignsstates_hash_index.json"
        import time
        if index_path.exists():
            try:
                with open(index_path, "r", encoding="utf-8") as f:
                    data = json.load(f) or {}
                if data: 
                    last_entry = list(data.values())[-1]
                    last_ts = time.strptime(last_entry["timestamp"], "%Y%m%d_%H%M%S")
                    now = time.localtime()
                    delta = time.mktime(now) - time.mktime(last_ts)
                    if delta < 60:
                        log_message(logger, f"🟡 Skipping backup — last backup only {int(delta)}s ago ({last_entry['timestamp']})")
                        return None
            except Exception as e:
                log_message(logger, f"⚠️  Could not check last backup time: {e}")

        # --- Normal backup process below ---
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f'campaignsstates_{timestamp}.backup'
        backup_path = self.states_path.parent / backup_filename

        # ✅ FIX: Verwende zentrale Helper-Methode für Tracker-Pfad
        tracker_popups_path = self._get_tracker_popups_path()
        logger.debug("Looking for popups at: %s", tracker_popups_path)
        if tracker_popups_path.exists():
            logger.debug(
                "File size: %s bytes",
                tracker_popups_path.stat().st_size,
            )

        try:
            # 1️⃣ Backup campaignsstates.txt
            shutil.copy2(self.states_path, backup_path)
            log_message(logger, f"✓ Backup created:  {backup_path.name}")

            # 2️⃣ Backup popups file if available
            backup_popups_path = None
            if tracker_popups_path.exists():
                backup_popups_filename = f'campaign_popups_seen_{timestamp}.backup'
                backup_popups_path = self.states_path.parent / backup_popups_filename
                shutil.copy2(tracker_popups_path, backup_popups_path)
                log_message(logger, f"✓ Popup backup created: {backup_popups_path.name}")
            else:
                log_message(logger, f"⚠️  No campaign_popups_seen.json found at {tracker_popups_path}")

            # 3️⃣ Compute hash and update index
            backup_hash = _md5_file(self.states_path)
            index = _load_hash_index(index_path)
            index[backup_hash] = {
                "timestamp": timestamp,
                "campaignsstates_backup": backup_path.name,
                "popups_backup": backup_popups_path.name if backup_popups_path else None
            }
            with open(index_path, "w", encoding="utf-8") as f:
                json.dump(index, f, indent=2, sort_keys=True)

            # 4️⃣ Cleanup old backups
            self.cleanup_old_backups()

            log_message(logger, f"✅ Backup set completed with hash {backup_hash}")
            return backup_path

        except Exception as e:
            log_message(logger, f"❌ Failed to create backup: {e}")
            import traceback
            traceback.print_exc()
            return None

    def restore_matching_popups(self) -> bool:
        """
        Restore the campaign_popups_seen.json backup that matches
        the current campaignsstates.txt hash, if available.
        
        Note: Since campaign_popups_seen.json is now created at startup,
        every backup should have a valid popups_backup entry.
        
        Returns:
            True if popups were restored, False otherwise
        """
        index_path = self.states_path.parent / "campaignsstates_hash_index.json"
        
        # ✅ FIX: Popup-Datei liegt im TRACKER-Verzeichnis! 
        popups_path = self._get_tracker_popups_path()
        
        logger.debug("Tracker popups path: %s", popups_path)
        logger.debug("IL-2 states path: %s", self.states_path)
        
        if not self.states_path.exists():
            log_message(logger, "⚠️ Cannot restore popups — states file missing.")
            return False
        
        if not index_path.exists():
            log_message(logger, "⚠️ Cannot restore popups — hash index missing.")
            return False
        
        # Calculate hash of current states file
        backup_hash = _md5_file(self.states_path)
        index = _load_hash_index(index_path)
        entry = index.get(backup_hash)
        
        if not entry:
            log_message(logger, "ℹ️ No matching hash entry found in index.")
            return False
        
        popups_backup_name = entry.get("popups_backup")
        
        # Handle legacy backups that were created before popup initialization
        if not popups_backup_name:
            log_message(logger, "ℹ️ Restored state has no popup backup (legacy backup)")
            log_message(logger, "   Popup state will be regenerated on next event generation")
            return False
        
        # Backup file is in IL-2 directory (next to campaignsstates.txt)
        src = self.states_path.parent / popups_backup_name
        
        if not src.exists():
            log_message(logger, f"⚠️ Popup backup missing: {src}")
            return False
        
        try: 
            shutil.copy2(src, popups_path)
            log_message(logger, f"✅ Restored popups from backup: {popups_backup_name}")
            log_message(logger, f"   Source: {src}")
            log_message(logger, f"   Target: {popups_path}")
            return True  # ✅ Erfolg! 
        except Exception as e:
            log_message(logger, f"❌ Failed to restore popup backup: {e}")
            return False


    def _cleanup_mission_popups(self, campaign_name: str, mission_id: str):
        """
        Remove popup events associated with deleted mission from campaign_popups_seen.json
        
        This ensures that when a mission is replayed after cleanup, the player will see
        popups for events (promotions, awards) again. 
        
        Args:
            campaign_name: Campaign folder name
            mission_id: Mission identifier (e.g., "04")
        """
        # ✅ FIX: Popup-Datei liegt im TRACKER-Verzeichnis, nicht im IL-2-Verzeichnis! 
        popups_path = self._get_tracker_popups_path()
        
        logger.debug("Looking for popups at: %s", popups_path)
        
        if not popups_path.exists():
            log_message(logger, "  ℹ️ No popup file found - nothing to clean")
            return
        
        try:
            with open(popups_path, 'r', encoding='utf-8') as f:
                popups_data = json.load(f)
        except json.JSONDecodeError:
            log_message(logger, "  ⚠️ Warning: Could not read popup file (invalid JSON)")
            return
        except Exception as e: 
            log_message(logger, f"  ⚠️ Warning: Could not read popup file: {e}")
            return
        
        if campaign_name not in popups_data: 
            log_message(logger, f"  ℹ️ No popup history for campaign '{campaign_name}'")
            return
        
        # Event keys look like: "promotion|Hauptmann|05|1943-07-15" or "award|Iron Cross|05|1943-07-15"
        # We need to remove all keys that reference this mission
        original_count = len(popups_data[campaign_name])
        
        # Filter out events that contain this mission ID
        # The mission ID appears between the second and third pipe separator
        popups_data[campaign_name] = [
            key for key in popups_data[campaign_name]
            if f"|{mission_id}|" not in key
        ]
        
        removed = original_count - len(popups_data[campaign_name])
        
        if removed > 0:
            try:
                with open(popups_path, 'w', encoding='utf-8') as f:
                    json.dump(popups_data, f, indent=2, sort_keys=True)
                log_message(logger, f"  ✓ Removed {removed} popup event(s) for Mission {mission_id}")
                log_message(logger, f"    (Events will be shown again when mission is replayed)")
            except Exception as e:
                log_message(logger, f"  ⚠️ Warning: Could not save popup file: {e}")
        else:
            log_message(logger, f"  ℹ️ No popup events found for Mission {mission_id}")
   
    def cleanup_old_backups(self):
        """Keep only the last N backups in game directory"""
        backup_pattern = 'campaignsstates_*.backup'
        backup_dir = self.states_path.parent
        backups = sorted(backup_dir.glob(backup_pattern))
        
        if len(backups) > self.max_backups:
            # Remove oldest backups
            to_remove = backups[:-self.max_backups]
            for backup in to_remove:
                try:
                    backup.unlink()
                    log_message(logger, f"  Removed old backup: {backup.name}")
                except Exception as e:
                    log_message(logger, f"  ⚠️  Could not remove {backup.name}: {e}")
    
    def delete_mission_entry(self, campaign_name: str, mission_id: str) -> bool:
        """
        Delete mission from completedMissionsByFileName in campaignsstates.txt
        
        ✅ FIXED: Correctly handles last mission deletion
        ✅ FIXED: Preserves completedMissionsByFileName structure
        
        Args:
            campaign_name: Campaign folder name
            mission_id: Mission identifier (e.g., "04")
            
        Returns:
            True if successful, False otherwise
        """
        if not self.states_path.exists():
            log_message(logger, f"❌ {self.states_path} not found")
            return False
        
        log_message(logger, f"\n{'='*70}")
        log_message(logger, f"DELETING: {campaign_name} - Mission {mission_id}")
        log_message(logger, f"{'='*70}")
        log_message(logger, f"Target: completedMissionsByFileName entry only")
        
        # Create backup FIRST
        backup_path = self.create_backup()
        if not backup_path:
            log_message(logger, "❌ Cannot proceed without backup!")
            return False
        
        try:
            # Read file
            with open(self.states_path, 'rb') as f:
                content = f.read().decode('utf-8', errors='ignore')
            
            log_message(logger, f"✓ Loaded {self.states_path.name} ({len(content)} chars)")
            
            # Find campaign section (between =kampagne= tags)
            campaign_start_tag = f'{campaign_name}='
            campaign_start = content.find(campaign_start_tag)
            
            if campaign_start == -1:
                log_message(logger, f"❌ Campaign '{campaign_name}' not found in file")
                return False
            
            # Find end of campaign (next =kampagne= or end of file)
            next_campaign_start = content.find('=', campaign_start + len(campaign_start_tag))
            if next_campaign_start == -1:
                campaign_end = len(content)
            else:
                # Search for next campaign start tag
                temp_pos = campaign_start + len(campaign_start_tag)
                while temp_pos < len(content):
                    next_eq = content.find('=', temp_pos)
                    if next_eq == -1:
                        campaign_end = len(content)
                        break
                    # Check if this is a campaign tag (has another = after it)
                    if next_eq + 1 < len(content) and content[next_eq + 1] != '=':
                        # Check if this looks like start of campaign name
                        potential_end = content.find('=', next_eq + 1)
                        if potential_end != -1 and potential_end - next_eq < 50:
                            campaign_end = next_eq
                            break
                    temp_pos = next_eq + 1
                else:
                    campaign_end = len(content)
            
            # Extract campaign section
            campaign_section = content[campaign_start:campaign_end]
            before_campaign = content[:campaign_start]
            after_campaign = content[campaign_end:]
            
            log_message(logger, f"✓ Found campaign section ({len(campaign_section)} chars)")
            
            # ✅ FIX: Find completedMissionsByFileName parameter
            completed_marker = "completedMissionsByFileName"
            completed_start = campaign_section.find(completed_marker)
            
            if completed_start == -1:
                log_message(logger, f"⚠️  completedMissionsByFileName not found in campaign section")
                return False
            
            # Find the value part (after the =)
            value_start = campaign_section.find('%3D', completed_start)
            if value_start == -1:
                log_message(logger, f"⚠️  No missions in completedMissionsByFileName")
                return False
            
            # Find end of this parameter (next & or end of section)
            value_end = campaign_section.find('&', value_start)
            if value_end == -1:
                value_end = len(campaign_section)
            
            completed_value = campaign_section[value_start:value_end]
            
            # Count missions in completedMissionsByFileName
            # Missions are separated by %2526
            mission_count = completed_value.count('%253D1')
            
            log_message(logger, f"  Current missions in completedMissionsByFileName: {mission_count}")
            
            # IMPORTANT: Mission IDs with spaces need to be TRIPLE-encoded!
            import urllib.parse
            encoded_mission_id = urllib.parse.quote(mission_id, safe='')  # space → %20
            double_encoded = encoded_mission_id.replace('%', '%25')  # %20 → %2520
            triple_encoded = double_encoded.replace('%', '%25')  # %2520 → %252520
            
            # Try to find and remove the mission
            patterns_to_try = [
                (f'%3D{triple_encoded}%253D1', 'first mission'),
                (f'%2526{triple_encoded}%253D1', 'following mission'),
            ]
            
            deleted = False
            for pattern, description in patterns_to_try:
                if pattern in completed_value:
                    # ✅ FIX: Check if this is the LAST mission
                    if mission_count == 1:
                        # Last mission - replace value with %3D (encoded "=")
                        # This creates: completedMissionsByFileName%3D& → decodes to: completedMissionsByFileName=&
                        log_message(logger, f"  This is the LAST mission in completedMissionsByFileName")
                        new_completed_value = "%3D"
                    else:
                        # Not the last mission - just remove this one
                        new_completed_value = completed_value.replace(pattern, '', 1)
                        
                        # ✅ FIX: If we removed the first mission and there are more,
                        # we need to fix the separator of the new first mission
                        if description == 'first mission' and mission_count > 1:
                            # Change %2526 to %3D for the new first mission
                            new_completed_value = new_completed_value.replace('%2526', '%3D', 1)
                    
                    # Build new campaign section
                    new_campaign_section = (
                        campaign_section[:value_start] + 
                        new_completed_value + 
                        campaign_section[value_end:]
                    )
                    
                    old_length = len(campaign_section)
                    new_length = len(new_campaign_section)
                    
                    log_message(logger, f"✓ Deleted mission {mission_id} from completedMissionsByFileName")
                    log_message(logger, f"  Pattern: {pattern} ({description})")
                    log_message(logger, f"  Removed: {old_length - new_length} chars")
                    
                    if mission_count == 1:
                        log_message(logger, f"  ✅ completedMissionsByFileName is now EMPTY (correct!)")
                    else:
                        log_message(logger, f"  Remaining missions: {mission_count - 1}")
                    
                    campaign_section = new_campaign_section
                    deleted = True
                    break
            
            if not deleted:
                log_message(logger, f"⚠️  Mission {mission_id} not found in completedMissionsByFileName")
                log_message(logger, f"   Searched for patterns:")
                for p, desc in patterns_to_try:
                    log_message(logger, f"     - {p} ({desc})")
                log_message(logger, f"\n   This might mean:")
                log_message(logger, f"   - Mission was never completed (not in completedMissionsByFileName)")
                log_message(logger, f"   - Mission has different ID encoding")
                return False
            
            # Reconstruct file
            new_content = before_campaign + campaign_section + after_campaign
            
            log_message(logger, f"\n{'='*70}")
            log_message(logger, f"WRITING CHANGES")
            log_message(logger, f"{'='*70}")
            log_message(logger, f"Original file size: {len(content)} chars")
            log_message(logger, f"New file size: {len(new_content)} chars")
            log_message(logger, f"Difference: {len(content) - len(new_content)} chars")
            
            # Write back
            with open(self.states_path, 'wb') as f:
                f.write(new_content.encode('utf-8'))
            
            log_message(logger, f"✓ Saved {self.states_path.name}")
            
            # Verify by reading back
            with open(self.states_path, 'rb') as f:
                verify_content = f.read().decode('utf-8', errors='ignore')
            
            log_message(logger, f"\n{'='*70}")
            log_message(logger, f"VERIFICATION")
            log_message(logger, f"{'='*70}")
            
            # Check if completedMissionsByFileName structure is preserved
            verify_section = verify_content[verify_content.find(campaign_start_tag):
                                           verify_content.find(campaign_start_tag) + len(campaign_section)]
            
            if "completedMissionsByFileName" in verify_section:
                log_message(logger, f"✓ Verification passed - completedMissionsByFileName structure preserved")
                
                # ✅ Additional check: make sure it's not left as a string
                completed_pos = verify_section.find("completedMissionsByFileName")
                if completed_pos != -1:
                    # Look for the value after it
                    next_char_pos = verify_section.find('=', completed_pos + len("completedMissionsByFileName"))
                    if next_char_pos != -1:
                        next_char = verify_section[next_char_pos + 1] if next_char_pos + 1 < len(verify_section) else ''
                        # Should be either & (empty) or % (has missions)
                        if next_char in ['&', '%', '']:
                            log_message(logger, f"✓ completedMissionsByFileName format correct")
                        else:
                            log_message(logger, f"⚠️  Unexpected character after completedMissionsByFileName: '{next_char}'")
            else:
                log_message(logger, f"⚠️  Warning: completedMissionsByFileName not found in verification")
            
            # Cleanup popup events for this mission
            log_message(logger, f"\n{'='*70}")
            log_message(logger, f"POPUP CLEANUP")
            log_message(logger, f"{'='*70}")
            self._cleanup_mission_popups(campaign_name, mission_id)
            
            log_message(logger, f"\n{'='*70}")
            log_message(logger, f"SUCCESS!")
            log_message(logger, f"{'='*70}")
            log_message(logger, f"Mission {mission_id} removed from completedMissionsByFileName")
            log_message(logger, f"characterStatisticsByFileName remains intact")
            log_message(logger, f"")
            log_message(logger, f"When you replay the mission:")
            log_message(logger, f"  - IL-2 will let you fly it again")
            log_message(logger, f"  - New stats will overwrite old stats")
            log_message(logger, f"  - Mission will be re-added to completedMissionsByFileName on success")
            log_message(logger, f"  - Popups for events will be shown again")
            
            return True
            
        except Exception as e:
            log_message(logger, f"❌ Error during deletion: {e}")
            import traceback
            traceback.print_exc()
            return False
            
    def verify_deletion(self, campaign_name: str, mission_id: str) -> bool:
        """
        Verify mission was actually deleted
        
        Args:
            campaign_name: Campaign folder name
            mission_id: Mission number
            
        Returns:
            True if mission is gone, False if still exists
        """
        try:
            # Simple verification: read file and check if mission ID still exists
            with open(self.states_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Find campaign section
            campaign_pattern = f'campaigns/{campaign_name}='
            if campaign_pattern not in content:
                log_message(logger, f"⚠️  Campaign {campaign_name} not found in file")
                return False
            
            # Extract campaign section
            start = content.index(campaign_pattern)
            # Find next campaign or end of file
            next_campaign = content.find('&campaigns/', start + 1)
            if next_campaign == -1:
                campaign_section = content[start:]
            else:
                campaign_section = content[start:next_campaign]
            
            # Decode and check if mission exists
            decoded = urllib.parse.unquote(campaign_section)
            
            # Mission should NOT exist in the characterStatisticsByFileName section
            # Pattern: &{mission_id}= or ={mission_id}=
            mission_patterns = [
                f'&{mission_id}=',
                f'={mission_id}=',
            ]
            
            for pattern in mission_patterns:
                if pattern in decoded:
                    log_message(logger, f"⚠️  Mission {mission_id} still found with pattern: {pattern}")
                    return False
            
            # Double check with URL-encoded version
            encoded_patterns = [
                urllib.parse.quote(f'&{mission_id}='),
                urllib.parse.quote(f'={mission_id}='),
            ]
            
            for pattern in encoded_patterns:
                if pattern in campaign_section:
                    log_message(logger, f"⚠️  Mission {mission_id} still found (encoded)")
                    return False
            
            return True
            
        except Exception as e:
            log_message(logger, f"⚠️  Could not verify deletion: {e}")
            import traceback
            traceback.print_exc()
            return False


class CleanupGUI:
    """Tkinter GUI for mission cleanup"""
    
    def __init__(self, opportunities: Dict):
        """
        Initialize GUI
        
        Args:
            opportunities: Dict of campaigns with missions needing cleanup
                          Format: {campaign_name: {mission_id: details, ...}}
        """
        self.opportunities = opportunities
        self.selected = {}  # "campaign_name::mission_id" -> selected (bool)
        self.ignore_flags = {}  # "campaign_name::mission_id" -> ignore flag (bool)
        self.cleanup_tool = MissionCleanup()
        
        self.root = tk.Tk()
        self.root.title("IL-2 Campaign Mission Cleanup")
        self.root.geometry("800x600")
        
        self.create_widgets()
    
    def create_widgets(self):
        """Create GUI widgets"""
        
        # Title
        title_frame = ttk.Frame(self.root, padding="10")
        title_frame.pack(fill=tk.X)
        
        ttk.Label(title_frame, text="Campaign Mission Cleanup",
                 font=('Arial', 14, 'bold')).pack()
        
        ttk.Label(title_frame, 
                 text="Found unsuccessful missions that can be replayed:",
                 font=('Arial', 10)).pack()
        
        # Scrollable frame for campaigns
        canvas_frame = ttk.Frame(self.root)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        canvas = tk.Canvas(canvas_frame)
        scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor=tk.NW)
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Create campaign cards - now handling multiple missions per campaign
        for campaign_name, missions in self.opportunities.items():
            # If missions is a dict (new format), iterate over it
            if isinstance(missions, dict):
                for mission_id, data in missions.items():
                    self.create_mission_card(scrollable_frame, campaign_name, mission_id, data)
            else:
                # Old format compatibility (single mission)
                self.create_mission_card(scrollable_frame, campaign_name, missions['mission_id'], missions)
        
        # Buttons
        button_frame = ttk.Frame(self.root, padding="10")
        button_frame.pack(fill=tk.X)
        
        ttk.Button(button_frame, text="Apply Changes", 
                  command=self.on_apply, width=20).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", 
                  command=self.on_cancel, width=20).pack(side=tk.LEFT, padx=5)
        
        # Note
        note_frame = ttk.Frame(self.root, padding="10")
        note_frame.pack(fill=tk.X)
        
        ttk.Label(note_frame, 
                 text="Note: Backup will be created automatically before deletion. "
                      "Ignored missions can be managed in cleanup_ignored_missions.json",
                 font=('Arial', 9, 'italic'),
                 foreground='gray').pack()
    
    
    def create_mission_card(self, parent, campaign_name: str, mission_id: str, data: Dict):
        """Create a card for one mission"""
        
        card = ttk.LabelFrame(parent, text=f"{campaign_name.upper()} - Mission {mission_id}", padding="10")
        card.pack(fill=tk.X, padx=5, pady=5)
        
        # Mission info
        info_text = f"Mission Position: {data['mission_number']}"
        ttk.Label(card, text=info_text, font=('Arial', 10, 'bold')).pack(anchor=tk.W)
        
        ttk.Label(card, text="Status: ⚠️  Unsuccessful (takeOffStatus = 1)",
                 foreground='orange').pack(anchor=tk.W)
        
        # Stats
        stats_text = f"Result: {data['air_kills']} air, {data['ground_kills']} ground"
        if data['naval_kills'] > 0:
            stats_text += f", {data['naval_kills']} naval"
        stats_text += f" | Flight Time: {data['flight_time']}"
        
        ttk.Label(card, text=stats_text).pack(anchor=tk.W)
        
        # Warning
        ttk.Label(card, 
                 text="⚠️  This mission entry is locked. Delete it to replay for a better result.",
                 foreground='red',
                 font=('Arial', 9)).pack(anchor=tk.W, pady=(5, 0))
        
        # Separator
        ttk.Separator(card, orient='horizontal').pack(fill=tk.X, pady=8)
        
        # Action frame for checkboxes
        action_frame = ttk.Frame(card)
        action_frame.pack(fill=tk.X, anchor=tk.W)
        
        # Unique key for this mission
        mission_key = f"{campaign_name}::{mission_id}"
        
        # Delete checkbox
        delete_var = tk.BooleanVar(value=False)
        self.selected[mission_key] = delete_var
        
        ttk.Checkbutton(action_frame, 
                       text=f"Delete Mission {mission_id} entry",
                       variable=delete_var).pack(anchor=tk.W)
        
        # Ignore checkbox (with distinctive styling)
        ignore_var = tk.BooleanVar(value=False)
        self.ignore_flags[mission_key] = ignore_var
        
        ignore_frame = ttk.Frame(action_frame)
        ignore_frame.pack(anchor=tk.W, pady=(5, 0))
        
        ignore_cb = ttk.Checkbutton(ignore_frame, 
                                   text="Don't ask me about this mission again",
                                   variable=ignore_var)
        ignore_cb.pack(side=tk.LEFT)
        
        # Info icon/text
        ttk.Label(ignore_frame, 
                 text="ℹ️",
                 foreground='blue',
                 cursor='hand2').pack(side=tk.LEFT, padx=(5, 0))
        
        # Tooltip would be nice here but keeping it simple
        ttk.Label(ignore_frame,
                 text="(Hide this mission from future checks)",
                 font=('Arial', 8, 'italic'),
                 foreground='gray').pack(side=tk.LEFT, padx=(2, 0))
    
    def on_apply(self):
        """Handle Apply button"""
        
        # Get selected missions for deletion and ignoring
        to_delete = []
        to_ignore = []
        
        for mission_key, delete_var in self.selected.items():
            if delete_var.get():
                # Parse "campaign_name::mission_id"
                campaign_name, mission_id = mission_key.split('::', 1)
                # Find mission data
                if campaign_name in self.opportunities:
                    missions = self.opportunities[campaign_name]
                    if isinstance(missions, dict) and mission_id in missions:
                        to_delete.append((campaign_name, mission_id, missions[mission_id]))
                    elif not isinstance(missions, dict):
                        # Old format compatibility
                        to_delete.append((campaign_name, mission_id, missions))
        
        for mission_key, ignore_var in self.ignore_flags.items():
            if ignore_var.get():
                campaign_name, mission_id = mission_key.split('::', 1)
                if campaign_name in self.opportunities:
                    missions = self.opportunities[campaign_name]
                    if isinstance(missions, dict) and mission_id in missions:
                        to_ignore.append((campaign_name, mission_id, missions[mission_id]))
                    elif not isinstance(missions, dict):
                        to_ignore.append((campaign_name, mission_id, missions))
        
        if not to_delete and not to_ignore:
            messagebox.showinfo("No Changes", "No missions selected for cleanup or ignore")
            return
        
        # Build confirmation message
        msg_parts = []
        
        if to_delete:
            msg_parts.append(f"Delete {len(to_delete)} mission entr{'y' if len(to_delete) == 1 else 'ies'}:")
            for campaign_name, mission_id, data in to_delete:
                msg_parts.append(f"  • {campaign_name} - Mission {mission_id}")
        
        if to_ignore:
            msg_parts.append("")
            msg_parts.append(f"Hide {len(to_ignore)} mission{'s' if len(to_ignore) > 1 else ''} from future checks:")
            for campaign_name, mission_id, data in to_ignore:
                msg_parts.append(f"  • {campaign_name} - Mission {mission_id}")
        
        if to_delete:
            msg_parts.append("")
            msg_parts.append("Backup will be created automatically.")
        
        msg = "\n".join(msg_parts)
        
        if not messagebox.askyesno("Confirm Changes", msg):
            return
        
        # Process ignore flags FIRST (before any deletion)
        for campaign_name, mission_id, data in to_ignore:
            add_to_ignored(campaign_name, mission_id)
        
        # Perform deletions
        success_count = 0
        if to_delete:
            for campaign_name, mission_id, data in to_delete:
                if self.cleanup_tool.delete_mission_entry(campaign_name, mission_id):
                    success_count += 1
        
        # Build result message
        result_parts = []
        
        if to_delete:
            if success_count == len(to_delete):
                result_parts.append(f"✓ Successfully deleted {success_count} mission entr{'y' if success_count == 1 else 'ies'}!")
                result_parts.append("You can now replay these missions for better results.")
            else:
                result_parts.append(f"⚠️  Deleted {success_count} of {len(to_delete)} missions.")
                result_parts.append("Check console for details.")
        
        if to_ignore:
            result_parts.append("")
            result_parts.append(f"✓ Added {len(to_ignore)} mission{'s' if len(to_ignore) > 1 else ''} to ignore list.")
            result_parts.append("You won't be asked about them again.")
        
        result_msg = "\n".join(result_parts)
        
        if success_count == len(to_delete) or not to_delete:
            messagebox.showinfo("Success", result_msg)
        else:
            messagebox.showwarning("Partial Success", result_msg)
        
        # ✅ Automatically re-decode campaignsstates.txt after all deletions
        if success_count > 0:
            log_message(logger, "\nRe-decoding campaignsstates.txt to update campaigns_decoded.json...")
            try:
                # Copy the in-game campaignsstates.txt to local working directory
                source_file = self.cleanup_tool.states_path
                local_copy = Path.cwd() / "campaignsstates.txt"

                if source_file.exists():
                    shutil.copy2(source_file, local_copy)
                    log_message(logger, f"✓ Copied {source_file} → {local_copy}")
                else:
                    log_message(logger, f"⚠️ Source file not found at {source_file}, skipping copy")
                    
                # Decode using local file    
                from decode_campaign_usersave1 import main as decode_campaignsstates
                success = decode_campaignsstates()
                if success:
                    log_message(logger, "✓ campaigns_decoded.json successfully regenerated.")
                else:
                    log_message(logger, "⚠️ Decoder reported failure; campaigns_decoded.json may be outdated.")
            except Exception as e:
                log_message(logger, f"⚠️ Could not re-decode campaigns_decoded.json: {e}")
            
            # ✅ NEW: Regenerate PDFs for affected campaigns after cleanup
            log_message(logger, "\n" + "="*70)
            log_message(logger, "REGENERATING PDF REPORTS")
            log_message(logger, "="*70)
            
            # Collect affected campaigns
            affected_campaigns = set()
            for campaign_name, mission_id, data in to_delete:
                affected_campaigns.add(campaign_name)
            
            log_message(logger, f"Regenerating PDFs for {len(affected_campaigns)} campaign(s)...")
            
            try:
                import step3_generate_events
                
                # Create generator instance (without popups, since we're in cleanup mode)
                generator = step3_generate_events.EventGenerator(
                    dry_run=False,
                    show_popups=False
                )
                
                # Regenerate events and PDFs for each affected campaign
                for campaign_name in affected_campaigns:
                    log_message(logger, f"\n  Processing: {campaign_name}")
                    
                    try:
                        resync_result = resync_campaign_events_for_campaign(
                            campaign_name, generator
                        )
                        events = resync_result["events"]
                        campaign_data = resync_result["campaign_data"]
                        completed_missions = resync_result["completed_missions"]
                        country = resync_result["country"]
                        update_completion_state_for_campaign(
                            campaign_name, campaign_data=campaign_data
                        )
                        
                        if events:
                            if country:
                                # Update campaign info file
                                generator.update_campaign_info_file(
                                    campaign_name, resync_result["combined_html"]
                                )

                                # *** REGENERATE PDF ***
                                if completed_missions and len(completed_missions) > 0:
                                    log_message(logger, f"    Regenerating PDF...")

                                    # Switch to PDF mode
                                    generator.set_mode("pdf")

                                    # Regenerate debriefings in PDF mode
                                    debriefings_html_pdf, debriefings_pdf = generator.generate_debriefings_html(
                                        campaign_name, 
                                        completed_missions
                                    )

                                    # Generate PDF-specific HTML with base64 images
                                    events_html_pdf = generator.generate_events_html(events, country, for_pdf=True)

                                    # Combine for PDF
                                    if debriefings_html_pdf:
                                        combined_html_pdf = debriefings_html_pdf + "\n" + events_html_pdf
                                    else:
                                        combined_html_pdf = events_html_pdf

                                    # Generate campaign summary
                                    cumulative_stats = None
                                    try:
                                        stats = campaign_data.get('characterStatisticsByFileName', {})
                                        if stats:
                                            latest_mission = max(
                                                stats.keys(), key=lambda x: int(x) if x.isdigit() else 0
                                            )
                                            cumulative_stats = stats.get(latest_mission, {})
                                    except Exception:
                                        pass

                                    summary_html = generator.generate_campaign_summary_html(
                                        campaign_name,
                                        events,
                                        debriefings_pdf,
                                        country,
                                        cumulative_stats,
                                        campaign_data
                                    )

                                    if summary_html:
                                        combined_html_pdf += "\n" + summary_html

                                    # Export to PDF
                                    generator.export_campaign_to_pdf(campaign_name, combined_html_pdf)

                                    # Switch back to ingame mode
                                    generator.set_mode("ingame")

                                    log_message(logger, f"    ✓ PDF regenerated")
                                else:
                                    log_message(logger, f"    ℹ️  No completed missions - skipping PDF")

                                    # ✅ Delete existing PDF if it exists
                                    import os
                                    pdf_path = Path('reports') / f"{campaign_name}_Report.pdf"
                                    if pdf_path.exists():
                                        try:
                                            os.remove(pdf_path)
                                            log_message(logger, f"    ✓ Removed outdated PDF: {pdf_path.name}")
                                        except Exception as e:
                                            log_message(logger, f"    ⚠️  Could not remove PDF: {e}")
                            else:
                                log_message(logger, f"    ⚠️  No country metadata found")
                        else:
                            log_message(logger, f"    ℹ️  No events generated")

                            # ✅ CRITICAL: Even with no events, cleanup PDF and info file if no missions left
                            try:
                               # If no missions left, cleanup everything
                                if not completed_missions or len(completed_missions) == 0:
                                    log_message(logger, f"    ℹ️  No missions left - cleaning up")
                                    
                                    # Delete PDF if exists
                                    import os
                                    pdf_path = Path('reports') / f"{campaign_name}_Report.pdf"
                                    if pdf_path.exists():
                                        try:
                                            os.remove(pdf_path)
                                            log_message(logger, f"    ✓ Removed PDF: {pdf_path.name}")
                                        except Exception as e:
                                            log_message(logger, f"    ⚠️  Could not remove PDF: {e}")

                                    # Update info file with empty content
                                    try:
                                        if country:
                                            empty_html = ""
                                            generator.update_campaign_info_file(campaign_name, empty_html)
                                            log_message(logger, f"    ✓ Cleared campaign info file")
                                    except Exception as e:
                                        log_message(logger, f"    ⚠️  Could not update info file: {e}")
                                                                       
                            except Exception as e:
                                log_message(logger, f"    ⚠️  Error during cleanup: {e}")
                            
                    except Exception as e:
                        log_message(logger, f"    ⚠️  Error regenerating for {campaign_name}: {e}")
                        import traceback
                        traceback.print_exc()
                
                log_message(logger, f"\n✅ PDF regeneration complete")
                
            except Exception as e:
                log_message(logger, f"⚠️  PDF regeneration failed: {e}")
                log_message(logger, f"   PDFs may be outdated - run tracker again to update")
                import traceback
                traceback.print_exc()
        
        self.root.destroy()
    
    def on_cancel(self):
        """Handle Cancel button"""
        self.root.destroy()
    
    def run(self):
        """Run the GUI"""
        self.root.mainloop()


def startup_cleanup_check(states_path=None):
    """
    Run at tracker startup to check for cleanup opportunities
    
    Args:
        states_path: Path to campaignsstates.txt in IL-2 directory (default: auto-detect)
    
    Returns:
        True if cleanup was performed, False otherwise
    """
    log_message(logger, "\n" + "="*70)
    log_message(logger, "SCANNING FOR UNSUCCESSFUL MISSIONS...")
    log_message(logger, "="*70)
    
    cleanup = MissionCleanup(campaignstates_path=states_path)
    opportunities = cleanup.find_cleanup_opportunities()
    
    # Show info about ignored missions (if any exist)
    ignored = load_ignored_missions()
    if ignored:
        log_message(logger, f"ℹ️  {len(ignored)} mission(s) currently in ignore list")
        log_message(logger, f"   (To manage: edit cleanup_ignored_missions.json)")
        log_message(logger)
    
    if not opportunities:
        log_message(logger, "✓ All campaigns clean - no unsuccessful missions found")
        return False
    
    # Count total missions across all campaigns
    total_missions = sum(len(missions) if isinstance(missions, dict) else 1 
                        for missions in opportunities.values())
    
    log_message(logger, f"\n⚠️  Found {total_missions} unsuccessful mission(s) across {len(opportunities)} campaign(s):")
    for campaign_name, missions in opportunities.items():
        if isinstance(missions, dict):
            for mission_id in missions.keys():
                log_message(logger, f"  • {campaign_name} - Mission {mission_id}")
        else:
            # Old format compatibility
            log_message(logger, f"  • {campaign_name} - Mission {missions['mission_id']}")
    
    # Show GUI
    gui = CleanupGUI(opportunities)
    gui.run()
    
    return True


if __name__ == '__main__':
    startup_cleanup_check()
