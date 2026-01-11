#!/usr/bin/env python3
"""
IL-2 Campaign Progress Tracker - Step 3: Event Generator

Reads decoded campaign save files and generates Events section for campaign info files.
Calculates ranks, awards, and creates chronological event timeline.
Also processes mission logs (.mlg files) to generate debriefing sections.

Usage:
    python step3_generate_events.py
    
Files needed:
    - campaigns_decoded.json (from decode_campaign_usersave1.py)
    - campaign_mission_dates.json (from step1_extract_mission_dates.py)
    - campaign_progress_config.yaml (ranks & awards configuration)
    - mlg2txt.py (for mission log conversion)
    - il2_mission_debrief.py (for debriefing parsing)
    - object_categories.yaml (for object classification)
"""

import json, os
import yaml
import sys
import re
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import argparse

from utils.info_locale import (
    TRACKER_SECTION_HEADER_PATTERN,
    decode_and_clean_info_locale,
)
from utils.pathing import get_base_path
from utils.formatting import safe_campaign_filename
from utils.combat_results import (
    KILL_MAPPING,
    calculate_kills_from_stats,
    calculate_air_combat_score,
    calculate_total_air_kills_weighted,
)
from utils.combat_results_html import (
    generate_campaign_summary_combat_results_html,
    generate_mission_combat_results_html,
)
from utils.filesystem import is_file_locked
from utils.popup_state import load_popup_seen, save_popup_seen, make_event_key, get_seen_keys, set_seen_keys
from utils.rank_scaling import check_and_cleanup_rank_scaling
from utils.process import is_il2_running
from utils.sorting import smart_mission_sort_key
from utils.logging import get_logger, log_message

BASE_DIR = get_base_path(__file__)
POPUP_SEEN_FILE = BASE_DIR / "campaign_popups_seen.json"
CAMPAIGN_EVENTS_FILE = BASE_DIR / "campaign_events.json"
CAMPAIGN_MISSION_DATES_FILE = BASE_DIR / "campaign_mission_dates.json"
CAMPAIGNS_DECODED_FILE = BASE_DIR / "campaigns_decoded.json"
CAMPAIGN_COMPLETION_STATE_FILE = BASE_DIR / "campaign_completion_state.json"
DEFAULT_LOG_PATH = BASE_DIR / "campaign_events.log"
ENV_DEBUG = os.environ.get("IL2_TRACKER_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}
LOGGER = get_logger(__name__, log_path=DEFAULT_LOG_PATH, debug=ENV_DEBUG)

def _load_decoded_campaign(decoded_path: str) -> dict:
    if not os.path.exists(decoded_path):
        LOGGER.warning("campaigns_decoded.json not found at %s", decoded_path)
        return {}
    try:
        with open(decoded_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        LOGGER.error("Error reading decoded campaign file: %s", e)
        return {}




class EventGenerator:
    def __init__(
        self,
        config_file: str = "campaign_progress_config.yaml",
        dry_run: bool = False,
        show_popups: bool = False,
        log_path: str | Path | None = None,
        debug: bool | None = None,
    ):
        """Initialize event generator with configuration
        
        Args:
            config_file: Path to YAML configuration
            dry_run: If True, don't actually modify files (just show what would happen)
            log_path: Optional log file path for rotating file handler
            debug: Enable debug logging output (default: from IL2_TRACKER_DEBUG env)
        """
        
        if debug is None:
            env_value = os.environ.get("IL2_TRACKER_DEBUG", "")
            debug = env_value.strip().lower() in {"1", "true", "yes", "on"}
        self.log_path = Path(log_path) if log_path else DEFAULT_LOG_PATH
        self.logger = get_logger(f"{__name__}.EventGenerator", log_path=self.log_path, debug=debug)
        self.dry_run = dry_run
        self.show_popups = bool(show_popups)
        
        # --- NEW: default output mode (ingame or pdf)
        # Controls whether Combat Results or Flight Log is rendered
        self.mode = "ingame"  # Default: used when running in tracker/monitor mode
        
        # Load configuration
        # Try external file first (for user editing), then embedded
        self.config = self._load_config(config_file)
        self._init_popup_state()
        self.mission_dates = self._load_mission_dates()
        self.save_data = self._load_save_data()
        
        # Extract game directory from mission dates JSON
        self.game_directory = self.mission_dates.get('game_directory', '')
        
        # Initialize Mission Log Processor for debriefings
        self.log_processor = self._init_log_processor()
        
        self.logger.info("Loaded configuration:")
        self.logger.info("  - %s campaigns with dates", len(self.mission_dates) - 1)  # -1 for game_directory key
        self.logger.info("  - %s campaigns with save data", len(self.save_data))
        self.logger.info("  - Game directory: %s", self.game_directory)
        
        # Create case-insensitive lookup for mission_dates
        # (campaign names may have different capitalization between sources)
        self.mission_dates_lower = {
            k.lower(): (k, v) for k, v in self.mission_dates.items() if k != 'game_directory'
        }

    def _resolve_config_path(self, config_file: str) -> Path:        
        config_path = Path(config_file)
        if not config_path.is_absolute():
            if getattr(sys, 'frozen', False):
                config_path = get_base_path(__file__) / config_file
                if not config_path.exists():
                    config_path = Path(sys._MEIPASS) / config_file
        return config_path
        
    def _load_config(self, config_file: str) -> dict:
        config_path = self._resolve_config_path(config_file)
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
        except UnicodeDecodeError:
            with open(config_path, 'r', encoding='iso-8859-1') as f:
                config = yaml.safe_load(f)  

        if not isinstance(config, dict):
            return {}
        return config        
                
    def _init_popup_state(self) -> None:
        self.enable_popups = bool(self.config.get("enable_popups", True))
        self.logger.info("[popups] enabled = %s", self.enable_popups)
        if not self.enable_popups:
            self.show_popups = False
        self.logger.debug("[DEBUG] Popups aktiviert: %s", self.show_popups)
        self.popup_seen = load_popup_seen(POPUP_SEEN_FILE)
        self.logger.info("[popups] seen campaigns = %s", len(self.popup_seen))
        
    def _load_mission_dates(self) -> dict:
        try:
            with open(CAMPAIGN_MISSION_DATES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            self.logger.error("Required file '%s' not found!", CAMPAIGN_MISSION_DATES_FILE.name)
            self.logger.error("Please run step1_extract_mission_dates.py first.")
            raise
        except json.JSONDecodeError as e:
            self.logger.error("Invalid JSON in '%s'", CAMPAIGN_MISSION_DATES_FILE.name)
            self.logger.error("  Line %s, Column %s: %s", e.lineno, e.colno, e.msg)
            self.logger.error("  The file may be corrupted. Try regenerating it.")
            raise
        
    def _load_save_data(self) -> dict:
        try:
            with open(CAMPAIGNS_DECODED_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            self.logger.error("Required file '%s' not found!", CAMPAIGNS_DECODED_FILE.name)
            self.logger.error("Please run decode_campaign_usersave1.py first.")
            raise
        except json.JSONDecodeError as e:
            self.logger.error("Invalid JSON in '%s'", CAMPAIGNS_DECODED_FILE.name)
            self.logger.error("  Line %s, Column %s: %s", e.lineno, e.colno, e.msg)
            self.logger.error("  The file may be corrupted. Try re-decoding the save file.")
            raise
        
    def _init_log_processor(self):
        if not self.game_directory:
            return None

        try:
            from step4_process_mission_logs import MissionLogProcessor
            snapshot_dt = None    
            try:
                states_path, index_path = self._find_il2_states_path()

                if not states_path:
                    states_path = Path("campaignsstates.txt")
                    index_path = Path("campaignsstates_hash_index.json")

                if states_path and states_path.exists() and index_path and index_path.exists():
                    import hashlib
                    h = hashlib.md5(states_path.read_bytes()).hexdigest()
                    with open(index_path, "r", encoding="utf-8") as f:
                        idx = json.load(f) or {}

                    self.logger.info(
                        "[snapshot] hash=%s → %s in index",
                        h,
                        "FOUND" if h in idx else "NOT FOUND",
                    )

                    entry = idx.get(h)
                    if entry:
                        if isinstance(entry, dict):
                            ts = entry.get("timestamp")
                        else:
                            ts = entry

                        if ts:
                            snapshot_dt = datetime.strptime(ts, "%Y%m%d_%H%M%S")        
            except Exception as e:
                self.logger.warning("[snapshot] Error during snapshot lookup: %s", e)
                snapshot_dt = None

            if snapshot_dt:
                self.logger.info("[snapshot] Using snapshot timestamp: %s", snapshot_dt)
            else:
                self.logger.info("[snapshot] No snapshot match found – using newest mission logs")

            log_processor = MissionLogProcessor(self.game_directory, verbose=False, snapshot_dt=snapshot_dt)
            self.logger.info("  - Mission log processor initialized")
            return log_processor
        except Exception as e:
            self.logger.warning("  - Warning: Could not initialize mission log processor: %s", e)
            return None

    def reload_mission_dates(self) -> bool:
        """Reload mission dates to refresh WW1 exclusions and campaign metadata."""
        try:
            with open(CAMPAIGN_MISSION_DATES_FILE, 'r', encoding='utf-8') as f:
                mission_dates = json.load(f)
        except FileNotFoundError:
            self.logger.error("Required file '%s' not found!", CAMPAIGN_MISSION_DATES_FILE.name)
            return False
        except json.JSONDecodeError as e:
            self.logger.error("Invalid JSON in '%s'", CAMPAIGN_MISSION_DATES_FILE.name)
            self.logger.error("  Line %s, Column %s: %s", e.lineno, e.colno, e.msg)
            return False
        except Exception as e:
            self.logger.error("Could not read '%s': %s", CAMPAIGN_MISSION_DATES_FILE.name, e)
            return False

        if not isinstance(mission_dates, dict):
            self.logger.error("Mission dates JSON is not a dictionary.")
            return False

        self.mission_dates = mission_dates
        self.game_directory = self.mission_dates.get('game_directory', '')
        self.mission_dates_lower = {
            k.lower(): (k, v) for k, v in self.mission_dates.items() if k != 'game_directory'
        }
        self.logger.info("[missions] Reloaded mission dates (%s campaigns)", len(self.mission_dates_lower))
        return True
        
    def _find_il2_states_path(self):
        """
        Find campaignsstates.txt and hash index in IL-2 directory
        
        Returns:
            (states_path, index_path) tuple, or (None, None) if not found
        """
        if not self.game_directory:
            return None, None
        
        game_dir = Path(self.game_directory)
        usersave_dir = game_dir / 'data' / 'swf' / 'il2' / 'usersave'
        
        if not usersave_dir.exists():
            return None, None
        
        for user_dir in usersave_dir.iterdir():
            if not user_dir.is_dir():
                continue
            
            potential = user_dir / 'campaign' / 'campaignsstates.txt'
            if potential.exists():
                index_path = potential.parent / "campaignsstates_hash_index.json"
                return potential, index_path
        
        return None, None
    
    def set_mode(self, mode: str):
        """
        Set the output mode for HTML generation.
        mode can be:
          - "ingame":  for on-screen IL-2 tracker (Flight Log visible)
          - "pdf":     for PDF export (Combat Results visible)
        """
        if mode not in ["ingame", "pdf"]:
            raise ValueError(f"Invalid mode: {mode}")
        self.mode = mode
        self.logger.info("[EventGenerator] Mode set to: %s", self.mode)
    
    def _save_campaign_completion_state(self):
        """Save current completion state of all campaigns for next run comparison"""
        state = {}
        for campaign_name, data in self.save_data.items():
            completed = list(data.get('completedMissionsByFileName', {}).keys())
            state[campaign_name] = sorted(completed)
        
        try:
            with open(CAMPAIGN_COMPLETION_STATE_FILE, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2)
            self.logger.info("[state] Saved completion state for %s campaigns", len(state))
        except Exception as e:
            self.logger.warning("[state] Warning: Could not save completion state: %s", e)
    
    def _load_campaign_completion_state(self) -> dict:
        """Load previous completion state to detect which campaigns changed"""
        try:
            with open(CAMPAIGN_COMPLETION_STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            self.logger.info("[state] No previous state found - first run or state file missing")
            return {}
        except Exception as e:
            self.logger.warning("[state] Warning: Could not load completion state: %s", e)
            return {}
    
    def _get_campaigns_with_new_missions(self) -> set:
        """
        Return set of campaign names that have new completions since last run.
        This is used to filter popups - only show popups for campaigns that actually changed.
        """
        prev_state = self._load_campaign_completion_state()
        changed = set()
        
        for campaign_name, data in self.save_data.items():
            current_missions = set(data.get('completedMissionsByFileName', {}).keys())
            prev_missions = set(prev_state.get(campaign_name, []))
            
            # Campaign changed if mission list is different
            if current_missions != prev_missions:
                changed.add(campaign_name)
                new_count = len(current_missions - prev_missions)
                removed_count = len(prev_missions - current_missions)
                
                if new_count > 0:
                    self.logger.info("[state] %s: +%s new mission(s)", campaign_name, new_count)
                if removed_count > 0:
                    self.logger.info("[state] %s: -%s removed mission(s)", campaign_name, removed_count)
        
        if not changed:
            log_message(LOGGER, f"[state] No campaign changes detected")
        
        return changed    
    
    def extract_mission_datetime(self, campaign_name: str, mission_id: str) -> tuple[Optional[str], Optional[str]]:
        """
        Extract mission date and start time from .eng file
        
        Looks for:
        - Date: 4 November, 1943<br>
        - Time: 9:45<br>
        
        Args:
            campaign_name: Campaign folder name
            mission_id: Mission identifier (e.g., "01", "1941-07-02a")
            
        Returns:
            Tuple of (date_string, time_string) or (None, None) if not found
            Example: ("4 November, 1943", "09:45")
        """
        if not self.game_directory:
            return None, None
        
        campaign_path = Path(self.game_directory) / "data" / "Campaigns" / campaign_name
        
        # Try to find the mission file - check common patterns
        possible_files = [
            campaign_path / f"{mission_id}.eng",
            campaign_path / f"{mission_id.zfill(2)}.eng",
        ]
        
        # Also check for files with extended names
        for file in campaign_path.glob(f"{mission_id}*.eng"):
            possible_files.append(file)
        
        for mission_file in possible_files:
            if not mission_file.exists():
                continue
            
            try:
                # Try multiple encodings (IL-2 uses UTF-16 LE for .eng files)
                content = None
                for encoding in ['utf-16-le', 'utf-16', 'utf-8', 'utf-8-sig', 'iso-8859-1']:
                    try:
                        with open(mission_file, 'r', encoding=encoding, errors='ignore') as f:
                            content = f.read(2000)  # Read first 2000 chars (briefing is at top)
                        break  # Success!
                    except (UnicodeDecodeError, UnicodeError):
                        continue
                
                if not content:
                    continue
                
                # Look for: Date: 4 November, 1943<br>
                date_str = None
                date_match = re.search(r'Date:\s*([^<\r\n]+)', content, re.IGNORECASE)
                if date_match:
                    date_str = date_match.group(1).strip()
                
                # Look for: Time: 9:45<br> or Time: 09:45<br>
                time_str = None
                time_match = re.search(r'Time:\s*(\d{1,2}:\d{2})', content, re.IGNORECASE)
                if time_match:
                    time_raw = time_match.group(1)
                    # Ensure HH:MM format
                    parts = time_raw.split(':')
                    if len(parts) == 2:
                        hours = parts[0].zfill(2)
                        minutes = parts[1]
                        time_str = f"{hours}:{minutes}"
                
                if date_str or time_str:
                    return date_str, time_str
            
            except Exception:
                continue
        
        return None, None
    
    def extract_mission_start_time(self, campaign_name: str, mission_id: str) -> Optional[str]:
        """
        Extract mission start time from .eng file (backward compatibility)
        
        Returns:
            Time string (e.g., "09:45") or None if not found
        """
        _, time_str = self.extract_mission_datetime(campaign_name, mission_id)
        return time_str
    
    def calculate_cumulative_stats(self, campaign_stats: Dict) -> Dict:
        cumulative = {
            'missions_completed': 0,
            'total_air_kills': 0,
            'fighter_kills': 0,
            'bomber_kills': 0,
            'static_plane_kills': 0,
            'air_combat_score': 0,
            'ground_kills': 0,
            'tank_kills': 0,
            'ship_kills': 0,
            'total_kills': 0,
            'deaths': 0,
            'total_flight_time': 0,
            'flight_time_hours': 0,
            'total_score': 0
        }
        
        for mission_num, stats in campaign_stats.items():
            if not isinstance(stats, dict):
                log_message(LOGGER, f"    Warning: Stats for mission {mission_num} is not a dict")
                continue
            
            cumulative['missions_completed'] += 1
            
            # Use central kill calculation
            kills = calculate_kills_from_stats(stats)
            
            cumulative['fighter_kills'] += kills['fighter_kills']
            cumulative['bomber_kills'] += kills['bomber_kills']
            cumulative['static_plane_kills'] += kills['static_kills']
            cumulative['total_air_kills'] += calculate_total_air_kills_weighted(stats)
            cumulative['air_combat_score'] += calculate_air_combat_score(stats)
            cumulative['ground_kills'] += kills['ground_kills']
            cumulative['tank_kills'] += kills['tank_kills']
            cumulative['ship_kills'] += kills['naval_kills']
            cumulative['total_kills'] += kills['total_kills']
            
            # Non-kill stats
            cumulative['deaths'] += int(stats.get('deaths', 0))
            cumulative['total_flight_time'] += int(stats.get('totalFlightTime', 0))
            cumulative['total_score'] += int(stats.get('score', 0))
        
        cumulative['flight_time_hours'] = cumulative['total_flight_time'] / 3600
        return cumulative

    def _calculate_per_mission_kill_totals(self, campaign_stats: Dict) -> Dict[str, Dict[str, int]]:
        per_mission = {}
        for mission_id, stats in campaign_stats.items():
            if not isinstance(stats, dict):
                log_message(LOGGER, f"    Warning: Stats for mission {mission_id} is not a dict")
                continue
            
            kills = calculate_kills_from_stats(stats)
            per_mission[mission_id] = {
                "air_kills": kills['air_kills'],
                "ground_kills": kills['ground_kills'],
                "naval_kills": kills['naval_kills'],
                "total_kills": kills['total_kills'],
            }
        return per_mission

    def _load_mission_aircraft_map(self, campaign_name: str) -> Dict[str, Dict]:
        safe_name = safe_campaign_filename(campaign_name)
        cache_path = BASE_DIR / "reports" / safe_name / "mission_aircraft_map.json"

        if not cache_path.exists():
            return {}

        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            log_message(LOGGER, f"    Warning: Could not read aircraft cache: {exc}")
            return {}

        if isinstance(data, dict) and "missions" in data and isinstance(data["missions"], dict):
            return data["missions"]

        if isinstance(data, dict):
            return data

        return {}
    
    def get_mission_date(self, campaign_name: str, mission_num: str) -> Optional[str]:
        """Get the date for a specific mission (case-insensitive campaign lookup)"""
        # Case-insensitive lookup
        campaign_name_lower = campaign_name.lower()
        if campaign_name_lower not in self.mission_dates_lower:
            return None
        
        original_name, campaign_data = self.mission_dates_lower[campaign_name_lower]
        missions = campaign_data.get('missions', {})
        
        if mission_num in missions:
            mission_data = missions[mission_num]
            # Defensive: check if it's a dict
            if isinstance(mission_data, dict):
                return mission_data.get('normalized_date')
            else:
                log_message(LOGGER, f"    Warning: mission_data for {campaign_name}/{mission_num} is {type(mission_data)}: {mission_data}")
                return None
        
        return None
    
    def check_awards(self, country: str, cumulative_stats: Dict,
                    per_mission_stats: Dict, completed_missions: List[str],
                    campaign_name: str, debriefing_wounds: Dict = None) -> List[Dict]:
        """
        Check which awards have been earned - mission by mission
        
        Args:
            debriefing_wounds: Dict mapping mission_id -> wounded (True/False)
                               Based on actual damage taken in debriefings
        
        Returns:
            List of award events
        """
        if debriefing_wounds is None:
            debriefing_wounds = {}
        
        if country not in self.config['awards']:
            return []
        
        awards_config = self.config['awards'][country]
        earned_awards = []
        already_earned = []  # Track what's been earned so far
        earned_this_mission = []  # Track what was just earned this mission
        
        # Track running statistics
        running_stats = {
            'air_combat_score': 0,
            'total_air_kills': 0,
            'missions_completed': 0,
            'flight_time_hours': 0,
            'deaths': 0,
            'total_score': 0,
            'ground_kills': 0,
            'tank_kills': 0,
            'ship_kills': 0,
            'total_kills': 0  # air + ground + ship
        }
        
        # Add starting rank (before first mission)
        ranks = self.config['ranks'].get(country, [])
        if ranks:
            # Get starting rank offset from campaign_mission_dates.json
            starting_rank_offset = 0
            # New JSON structure: campaigns are at root level (no 'campaigns' wrapper)
            if campaign_name in self.mission_dates and campaign_name != 'game_directory':
                campaign_data = self.mission_dates[campaign_name]
                starting_rank_offset = campaign_data.get('starting_rank_offset', 0)
                # Clamp to valid range
                starting_rank_offset = max(0, min(starting_rank_offset, len(ranks) - 1))
            
            starting_rank = ranks[starting_rank_offset]  # Use configured offset
            # Get date of first mission or use placeholder
            first_mission = sorted(completed_missions, key=smart_mission_sort_key)[0]
            first_mission_date = self.get_mission_date(campaign_name, first_mission)
            
            earned_awards.append({
                'type': 'promotion',
                'rank': starting_rank['name'],
                'image': starting_rank['image'],
                'mission': 'Initial',
                'date': first_mission_date  # Same date as first mission
            })
        
        # Add Pilot's Badge/Emblem (before first mission)
        # For USSR: Choose between Badge (early) and Emblem (late) based on first mission date
        first_mission = sorted(completed_missions, key=smart_mission_sort_key)[0]
        first_mission_date = self.get_mission_date(campaign_name, first_mission)
        
        for award in awards_config:
            # Check if this is a pilot's badge/emblem
            is_pilots_award = (
                "Pilot's Badge" in award['name'] or 
                "Aviation Badge" in award['name'] or
                "Aviation Emblem" in award['name'] or
                "pilots_badge" in award.get('image', '') or
                "pilots_emblem" in award.get('image', '')
            )
            
            if is_pilots_award:
                # For Soviet Union, choose based on date
                if country == 'Soviet Union':
                    # Check if campaign starts before or after transition
                    if first_mission_date and first_mission_date >= "1943-01-06":
                        # Late period - use Aviation Emblem
                        if "Emblem" in award['name'] or "emblem" in award.get('image', ''):
                            earned_awards.append({
                                'type': 'award',
                                'name': award['name'],
                                'image': award['image'],
                                'mission': 'Initial',
                                'date': first_mission_date
                            })
                            already_earned.append(award['name'])
                            break
                    else:
                        # Early period - use Aviation Badge
                        if "Badge" in award['name'] or "badge" in award.get('image', ''):
                            earned_awards.append({
                                'type': 'award',
                                'name': award['name'],
                                'image': award['image'],
                                'mission': 'Initial',
                                'date': first_mission_date
                            })
                            already_earned.append(award['name'])
                            break
                else:
                    # For other countries, just use first match
                    earned_awards.append({
                        'type': 'award',
                        'name': award['name'],
                        'image': award['image'],
                        'mission': 'Initial',
                        'date': first_mission_date
                    })
                    already_earned.append(award['name'])
                    break  # Only one pilot's badge
        
        # Process missions in order
        for mission_num in sorted(completed_missions, key=smart_mission_sort_key):
            if mission_num not in per_mission_stats:
                continue
            
            mission_stats = per_mission_stats[mission_num]
            earned_this_mission = []  # Reset for new mission
            
            # Update running statistics using central helpers
            kills = calculate_kills_from_stats(mission_stats)

            running_stats['air_combat_score'] += calculate_air_combat_score(mission_stats)
            running_stats['total_air_kills'] += calculate_total_air_kills_weighted(mission_stats)
            running_stats['missions_completed'] += 1
            running_stats['flight_time_hours'] += int(mission_stats.get('totalFlightTime', 0)) / 3600
            running_stats['deaths'] += int(mission_stats.get('deaths', 0))
            running_stats['total_score'] += int(mission_stats.get('score', 0))
            running_stats['ground_kills'] += kills['ground_kills']
            running_stats['tank_kills'] += kills['tank_kills']
            running_stats['ship_kills'] += kills['naval_kills']
            running_stats['total_kills'] = (
                running_stats['total_air_kills'] +
                running_stats['ground_kills'] +
                running_stats['ship_kills']
            )
            
            # Check each award
            for award in awards_config:
                award_name = award['name']
                max_awards = award.get('max_awards', 1)
                
                # Handle unlimited awards (max_awards: null)
                if max_awards is not None:
                    # Check if max awards already reached for this award
                    award_count = already_earned.count(award_name)
                    if award_count >= max_awards:
                        continue  # Already earned maximum times
                
                # Check prerequisites - must have been earned BEFORE this mission
                # (not on this mission - prevents chaining)
                requires = award.get('requires')
                if requires:
                    if requires not in already_earned:
                        continue  # Don't have prerequisite at all
                    if requires in earned_this_mission:
                        continue  # Prerequisite earned THIS mission - wait for next mission
                
                # Check mutual exclusivity (e.g., USSR wound stripes)
                mutually_exclusive = award.get('mutually_exclusive_with')
                if mutually_exclusive:
                    if mutually_exclusive in earned_this_mission:
                        continue  # Mutually exclusive award already earned this mission
                
                # Check if per-sortie award
                if award.get('per_sortie'):
                    # Check THIS mission only (static planes count as 0.5)
                    mission_kills = calculate_total_air_kills_weighted(mission_stats)
                    wounded = int(mission_stats.get('deaths', 0)) > 0
                    
                    award_earned = False
                    conditions = award.get('conditions', [])
                    
                    for condition in conditions:
                        if 'air_kills_in_sortie' in condition:
                            if mission_kills >= condition['air_kills_in_sortie']:
                                award_earned = True
                                break
                        
                        if 'air_kills_wounded_sortie' in condition:
                            if mission_kills >= condition['air_kills_wounded_sortie'] and wounded:
                                award_earned = True
                                break
                        
                        if 'wounded_this_sortie' in condition:
                            # Check if wounded in THIS mission only
                            if wounded:
                                award_earned = True
                                break
                    
                    # Check random threshold (if specified)
                    if award_earned and ('random_threshold' in award or 'random_threshold_min' in award):
                        import random
                        # Seed with campaign + mission + award name for deterministic AND unique results
                        random.seed(f"{campaign_name}_{mission_num}_{award_name}")
                        random_roll = random.randint(0, 999)
                        
                        # Standard threshold: RND < X (e.g., RND<800 = 80% chance)
                        if 'random_threshold' in award:
                            if random_roll >= award['random_threshold']:
                                award_earned = False  # Failed random check
                        
                        # Minimum threshold: RND >= X (e.g., RND>=800 = 20% chance)
                        if 'random_threshold_min' in award:
                            if random_roll < award['random_threshold_min']:
                                award_earned = False  # Failed random check
                    
                    if award_earned:
                        # Store award with tier for later filtering
                        award_tier = award.get('award_tier', 999)  # Default = lowest priority
                        mission_date = self.get_mission_date(campaign_name, mission_num)
                        earned_this_mission.append({
                            'name': award_name,
                            'award': award,
                            'tier': award_tier,
                            'mission': mission_num,
                            'date': mission_date
                        })
                
                else:
                    # Check rank index requirements
                    # Get ranks for this country
                    current_rank_idx = 0
                    if country in self.config.get('ranks', {}):
                        ranks = self.config['ranks'][country]
                        # Find current rank based on score
                        for idx, rank in enumerate(ranks):
                            if running_stats.get('total_score', 0) >= rank['score']:
                                current_rank_idx = idx
                    
                    # Check minimum rank requirement
                    if 'requires_rank_index' in award or 'min_rank_index' in award:
                        required_min = award.get('requires_rank_index', award.get('min_rank_index', 0))
                        if current_rank_idx < required_min:
                            continue  # Don't have required minimum rank yet
                    
                    # Check maximum rank requirement (for NCO-only awards)
                    if 'max_rank_index' in award:
                        required_max = award['max_rank_index']
                        if current_rank_idx > required_max:
                            continue  # Rank too high for this award
                    
                    # Check cumulative stats OR graduated random
                    award_granted = False
                    
                    # First check graduated random kills (British DFM/DFC style)
                    if 'graduated_random_kills' in award:
                        import random
                        random.seed(f"{campaign_name}_{mission_num}_{award_name}")
                        random_roll = random.randint(0, 999)
                        
                        total_kills = running_stats.get('total_air_kills', 0)
                        graduated_thresholds = award['graduated_random_kills']
                        
                        # Check if any kill threshold passes the random check
                        for kill_count, rnd_threshold in sorted(graduated_thresholds.items(), reverse=True):
                            if total_kills >= kill_count and random_roll < rnd_threshold:
                                award_granted = True
                                break
                    
                    # OR check normal conditions (missions/flight time)
                    if not award_granted and self.check_award_conditions_with_stats(award, running_stats, debriefing_wounds):
                        award_granted = True
                    
                    # If no graduated_random_kills, just check normal conditions
                    if 'graduated_random_kills' not in award:
                        award_granted = self.check_award_conditions_with_stats(award, running_stats, debriefing_wounds)
                    
                    if award_granted:
                        # Check standard random thresholds
                        if 'random_threshold' in award or 'random_threshold_min' in award:
                            import random
                            random.seed(f"{campaign_name}_{mission_num}_{award_name}")
                            random_roll = random.randint(0, 999)
                            
                            # Standard threshold: RND < X
                            if 'random_threshold' in award:
                                if random_roll >= award['random_threshold']:
                                    award_granted = False
                            
                            # Minimum threshold: RND >= X
                            if 'random_threshold_min' in award:
                                if random_roll < award['random_threshold_min']:
                                    award_granted = False
                        
                        if award_granted:
                            mission_date = self.get_mission_date(campaign_name, mission_num)
                            # Store award with tier info for cumulative awards too
                            award_tier = award.get('award_tier', 999)
                            earned_this_mission.append({
                                'name': award_name,
                                'award': award,
                                'tier': award_tier,
                                'type': 'award',
                                'mission': mission_num,
                                'date': mission_date
                            })
            
            # TIER FILTERING: Process ALL tiered awards (both per-sortie and cumulative)
            # Keep only highest tier per mission to prevent multiple awards for same achievement
            tiered_awards_this_mission = [e for e in earned_this_mission if isinstance(e, dict) and 'tier' in e]
            regular_awards_this_mission = [e for e in earned_this_mission if isinstance(e, str)]
            
            if tiered_awards_this_mission:
                # Find highest tier (lowest number = highest priority)
                # Tier 1 = Hero/Medal of Honor, Tier 2 = Red Banner/DSC, etc.
                highest_tier = min(e['tier'] for e in tiered_awards_this_mission)
                
                # Keep only awards at highest tier
                kept_award_names = []
                for tiered_award in tiered_awards_this_mission:
                    if tiered_award['tier'] == highest_tier:
                        # Add to final list
                        earned_awards.append({
                            'type': 'award',
                            'name': tiered_award['name'],
                            'image': tiered_award['award']['image'],
                            'mission': tiered_award['mission'],
                            'date': tiered_award['date']
                        })
                        already_earned.append(tiered_award['name'])
                        kept_award_names.append(tiered_award['name'])
                
                # Update earned_this_mission for prerequisite checking next mission
                earned_this_mission = kept_award_names + regular_awards_this_mission
            else:
                # No tiered awards, process regular awards normally
                for regular_award in regular_awards_this_mission:
                    # These were already added to earned_awards in the loop above
                    pass
                    
        # === 🩸 WOUND BADGE SYSTEM (Cumulative, YAML-driven) ===
                    
        if country in self.config.get('awards', {}):
            # Dynamisch: finde alle Awards, die Verwundungen als Bedingung haben
            wound_awards = []
            for a in self.config['awards'][country]:
                for cond in a.get('conditions', []):
                    if 'deaths' in cond or 'wounded_in_sortie' in cond or 'wounded_this_sortie' in cond:
                        wound_awards.append(a)
                        break

            if wound_awards:
                cumulative_wounds = sum(1 for w in debriefing_wounds.values() if w)

                for award in wound_awards:
                    for condition in award.get('conditions', []):
                        if 'deaths' in condition or 'wounded_in_sortie' in condition:
                            required_wounds = condition.get('deaths') or condition.get('wounded_in_sortie')
                            if cumulative_wounds >= required_wounds and award['name'] not in already_earned:
                                mission_info = self.find_mission_for_award(
                                    campaign_name,
                                    award,
                                    completed_missions,
                                    per_mission_stats,
                                    debriefing_wounds
                                )
                                mission_num = mission_info['mission'] if mission_info else None
                                mission_date = mission_info['date'] if mission_info else None

                                earned_awards.append({
                                    'type': 'award',
                                    'name': award['name'],
                                    'image': award['image'],
                                    'mission': mission_num,
                                    'date': mission_date
                                })
                                already_earned.append(award['name'])
                                log_message(LOGGER, f"  ✓ Awarded {award['name']} after {cumulative_wounds} wounds")

        
        return earned_awards
    
    def check_award_conditions_with_stats(self, award: Dict, stats: Dict, debriefing_wounds: Dict = None) -> bool:
        """
        Check if award conditions are met (OR logic) with specific stats dict.
        Supports 'deaths' in YAML as an alias for cumulative wounds from debriefings.
        """
        conditions = award.get('conditions', [])
        if debriefing_wounds is None:
            debriefing_wounds = {}

        # Count total wounds from debriefings (most accurate)
        cumulative_wounds = sum(1 for w in debriefing_wounds.values() if w)

        for condition in conditions:
            for stat_name, threshold in condition.items():
                # Treat 'deaths' as wounds (for legacy YAML)
                if stat_name == 'deaths':
                    if cumulative_wounds >= threshold:
                        return True
                else:
                    stat_value = stats.get(stat_name, 0)
                    if stat_value >= threshold:
                        return True  # OR logic – any condition triggers

        return False
    
    def find_mission_for_award(self, campaign_name: str, award: Dict,
                               missions: List[str], per_mission_stats: Dict,
                               debriefing_wounds: Dict = None) -> Optional[Dict]:
        """Find which mission an award was earned on"""
        if not missions:
            return None

        if debriefing_wounds is None:
            debriefing_wounds = {}

        sorted_missions = sorted(missions, key=smart_mission_sort_key)
        running_stats = {
            'air_combat_score': 0,
            'total_air_kills': 0,
            'missions_completed': 0,
            'flight_time_hours': 0,
            'deaths': 0,
            'total_score': 0,
            'ground_kills': 0,
            'tank_kills': 0,
            'ship_kills': 0,
            'total_kills': 0  # air + ground + ship
        }
        wounds_to_date = {}
        previously_met = False

        for mission_num in sorted_missions:
            mission_stats = per_mission_stats.get(mission_num)
            if not isinstance(mission_stats, dict):
                continue

            running_stats['missions_completed'] += 1

            kills = calculate_kills_from_stats(mission_stats)
            running_stats['air_combat_score'] += calculate_air_combat_score(mission_stats)
            running_stats['total_air_kills'] += calculate_total_air_kills_weighted(mission_stats)
            running_stats['flight_time_hours'] += int(mission_stats.get('totalFlightTime', 0)) / 3600
            running_stats['deaths'] += int(mission_stats.get('deaths', 0))
            running_stats['total_score'] += int(mission_stats.get('score', 0))
            running_stats['ground_kills'] += kills['ground_kills']
            running_stats['tank_kills'] += kills['tank_kills']
            running_stats['ship_kills'] += kills['naval_kills']
            running_stats['total_kills'] = (
                running_stats['total_air_kills'] +
                running_stats['ground_kills'] +
                running_stats['ship_kills']
            )

            if mission_num in debriefing_wounds:
                wounds_to_date[mission_num] = debriefing_wounds.get(mission_num)

            currently_met = self.check_award_conditions_with_stats(
                award,
                running_stats,
                wounds_to_date if wounds_to_date else None
            )

            if currently_met and not previously_met:
                mission_date = self.get_mission_date(campaign_name, mission_num)
                return {
                    'mission': mission_num,
                    'date': mission_date
                }

            previously_met = currently_met

        last_mission = sorted_missions[-1]
        mission_date = self.get_mission_date(campaign_name, last_mission)
        
        return {
            'mission': last_mission,
            'date': mission_date
        }
    
    def generate_events_for_campaign(self, campaign_name: str) -> List[Dict]:
        """Generate all events (promotions + awards) for a campaign"""
        
        # Check if campaign has save data
        if campaign_name not in self.save_data:
            return []
        
        campaign_data = self.save_data[campaign_name]
        
        # Check if any missions completed
        completed = campaign_data.get('completedMissionsByFileName', {})
        if not completed:
            return []
        
        # Get country (case-insensitive lookup)
        campaign_name_lower = campaign_name.lower()
        if campaign_name_lower not in self.mission_dates_lower:
            log_message(LOGGER, f"  Warning: No mission dates found for {campaign_name}")
            return []
        
        # Get original campaign name and data from mission_dates
        original_name, mission_data = self.mission_dates_lower[campaign_name_lower]
        country = mission_data.get('country')
        if not country:
            log_message(LOGGER, f"  Warning: No country detected for {campaign_name}")
            return []
        
        log_message(LOGGER, f"\nProcessing: {campaign_name} ({country})")
        log_message(LOGGER, f"  Missions completed: {len(completed)}")
        
        # STEP 1: Load debriefing data FIRST (for accurate wound counting)
        debriefing_wounds = {}  # mission_id -> True/False
        if self.log_processor:
            try:
                completed_missions_list = list(completed.keys())
                debriefings = self.log_processor.get_all_debriefings(campaign_name, completed_missions_list)
                
                for mission_id, data in debriefings.items():
                    # Check if wounded (using threshold > 0.2)
                    wounded = data['summary'].get('wounded', False)
                    debriefing_wounds[mission_id] = wounded
                
                if debriefing_wounds:
                    wound_count = sum(1 for w in debriefing_wounds.values() if w)
                    log_message(LOGGER, f"  Debriefings loaded: {len(debriefings)} missions, {wound_count} wounded")
            except Exception as e:
                log_message(LOGGER, f"  Warning: Could not load debriefings: {e}")
        
        try:
            # Calculate statistics
            per_mission_stats = campaign_data.get('characterStatisticsByFileName', {})
            cumulative_stats = self.calculate_cumulative_stats(per_mission_stats)
            
            log_message(LOGGER, f"  Total score: {cumulative_stats['total_score']}")
            log_message(LOGGER, f"  Air kills: {cumulative_stats['total_air_kills']}")
            log_message(LOGGER, f"  Air combat score: {cumulative_stats['air_combat_score']}")
            
            # Show rank scaling info
            scale_factor = self.get_rank_scaling_factor(campaign_name)
            if scale_factor != 1.0:
                mission_count = len(completed)
                log_message(LOGGER, f"  Rank scaling: {scale_factor}x (campaign length: {mission_count} missions)")
            
            events = []
            
            # Check promotions
            completed_missions = list(completed.keys())
            promotions = self.check_rank_promotions_v2(
                campaign_name, country, per_mission_stats, completed_missions
            )
            events.extend(promotions)
            
            # Check awards (pass debriefing wounds for accurate wound counting)
            awards = self.check_awards(
                country, cumulative_stats, per_mission_stats, 
                completed_missions, campaign_name, debriefing_wounds
            )
            events.extend(awards)
            
            # Sort chronologically by mission DATE (not just number)
            def sort_key(event):
                # Initial events (starting rank, pilot's badge) come first
                if event['mission'] == 'Initial':
                    mission_sort = ("0000-00-00", "0", "")  # Before all missions - all strings!
                else:
                    # Try to get actual mission date for proper chronological order
                    mission_date = self.get_mission_date(campaign_name, event['mission'])
                    if mission_date:
                        # Parse date for sorting (YYYY-MM-DD format)
                        try:
                            # Handle both formats: "1941-06-22" and "22.6.1941"
                            if '-' in mission_date and len(mission_date) == 10 and mission_date[0].isdigit():
                                # ISO format YYYY-MM-DD
                                mission_sort = (mission_date, "0", "")  # String "0" for priority
                            else:
                                # DD.MM.YYYY format or D.M.YYYY - convert to YYYY-MM-DD
                                parts = mission_date.split('.')
                                if len(parts) == 3:
                                    # Pad day and month with zeros
                                    date_str = f"{parts[2].zfill(4)}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
                                    mission_sort = (date_str, "0", "")
                                else:
                                    # Fallback to mission number as string (padded)
                                    mission_num_str = event['mission'].zfill(10)
                                    mission_sort = ("9999-99-99", "1", mission_num_str)
                        except:
                            # Fallback to mission number as string
                            mission_num_str = event['mission'].zfill(10)
                            mission_sort = ("9999-99-99", "1", mission_num_str)
                    else:
                        # No date available - use mission number as string
                        mission_num_str = event['mission'].zfill(10)
                        mission_sort = ("9999-99-99", "1", mission_num_str)
                
                # Type order: promotion=0, award=1 (promotions first on same day)
                type_order = 0 if event['type'] == 'promotion' else 1
                score = event.get('score', 0)
                return (*mission_sort, type_order, score)
            
            events.sort(key=sort_key)
            
            log_message(LOGGER, f"  Generated {len(events)} events ({len(promotions)} promotions, {len(awards)} awards)")
            
            return events
            
        except Exception as e:
            log_message(LOGGER, f"  ERROR in {campaign_name}: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def get_rank_scaling_factor(self, campaign_name: str) -> float:
        """
        Get rank scaling factor based on campaign length
        
        Args:
            campaign_name: Campaign name
            
        Returns:
            Scaling factor (1.0 = no scaling, 2.0 = double requirements, etc.)
        """
        # Check if scaling is enabled
        rank_scaling = self.config.get('rank_scaling', {})
        if not rank_scaling.get('enabled', True):
            return 1.0  # Scaling disabled
        
        # Get total mission count for this campaign
        campaign_name_lower = campaign_name.lower()
        if campaign_name_lower not in self.mission_dates_lower:
            return 1.0  # Unknown campaign, use default
        
        _, mission_data = self.mission_dates_lower[campaign_name_lower]
        mission_count = mission_data.get('mission_count', 0)
        
        if mission_count == 0:
            return 1.0  # No missions, use default
        
        # Get factors from config
        factors = rank_scaling.get('factors', {})
        
        # Parse all brackets dynamically and find matching one
        matching_factor = 1.0  # Default if no bracket matches
        
        for bracket_str, factor in factors.items():
            # Parse bracket string (e.g., "11-20", "71+", "5")
            bracket_str = str(bracket_str).strip()
            
            try:
                if '+' in bracket_str:
                    # Format: "71+" means 71 and above
                    min_val = int(bracket_str.replace('+', '').strip())
                    if mission_count >= min_val:
                        matching_factor = float(factor)
                        # Don't break - continue to find highest matching bracket
                
                elif '-' in bracket_str:
                    # Format: "11-20" means 11 to 20 inclusive
                    parts = bracket_str.split('-')
                    if len(parts) == 2:
                        min_val = int(parts[0].strip())
                        max_val = int(parts[1].strip())
                        if min_val <= mission_count <= max_val:
                            matching_factor = float(factor)
                            break  # Found exact match
                
                else:
                    # Format: "10" means exactly 10
                    exact_val = int(bracket_str)
                    if mission_count == exact_val:
                        matching_factor = float(factor)
                        break  # Found exact match
            
            except (ValueError, TypeError):
                # Invalid bracket format, skip it
                log_message(LOGGER, f"  Warning: Invalid rank_scaling bracket format: '{bracket_str}'")
                continue
        
        return matching_factor
    
    def check_rank_promotions_v2(self, campaign_name: str, country: str,
                                  per_mission_stats: Dict, missions: List[str]) -> List[Dict]:
        """Check rank promotions mission by mission - only ONE rank per mission"""
        if country not in self.config['ranks']:
            return []
        
        ranks = self.config['ranks'][country]
        promotions = []
        running_score = 0
        
        # Get starting rank offset from campaign_mission_dates.json
        starting_rank_offset = 0
        # New JSON structure: campaigns are at root level (no 'campaigns' wrapper)
        if hasattr(self, 'mission_dates') and campaign_name in self.mission_dates and campaign_name != 'game_directory':
            campaign_data = self.mission_dates[campaign_name]
            starting_rank_offset = campaign_data.get('starting_rank_offset', 0)
            # Clamp to valid range
            starting_rank_offset = max(0, min(starting_rank_offset, len(ranks) - 1))
        
        current_rank_index = starting_rank_offset  # Start at configured rank
        
        # Get rank scaling factor based on campaign length
        scale_factor = self.get_rank_scaling_factor(campaign_name)
        
        for mission_num in sorted(missions, key=smart_mission_sort_key):
            if mission_num not in per_mission_stats:
                continue
            
            mission_score = int(per_mission_stats[mission_num].get('score', 0))
            running_score += mission_score
            
            # Check if we've reached next rank (only ONE promotion per mission)
            if current_rank_index < len(ranks) - 1:
                next_rank = ranks[current_rank_index + 1]
                # Apply scaling factor to FULL rank requirement (not reduced by starting rank)
                required_score = int(next_rank['score'] * scale_factor)
                
                if running_score >= required_score:
                    # Promotion!
                    current_rank_index += 1
                    mission_date = self.get_mission_date(campaign_name, mission_num)
                    
                    promotions.append({
                        'type': 'promotion',
                        'rank': next_rank['name'],
                        'image': next_rank['image'],
                        'mission': mission_num,
                        'date': mission_date,
                        'score': running_score
                    })
        
        return promotions
    
    def image_to_base64(self, image_path: str, rotate: bool = False) -> str:
        """
        Convert image to base64 for embedding in PDF
        Supports PNG and DDS formats (converts DDS to PNG on-the-fly)
        
        Args:
            image_path: Relative path to image (e.g., "CampaignRanksAwards/Germany/medal.png")
            rotate: If True, rotate image 90° counter-clockwise before encoding
            
        Returns:
            Base64 data URI or original path if conversion fails
        """
        import base64
        
        if not self.game_directory:
            return image_path
        
        # Construct full path - images are in data/swf/ directory!
        full_path = Path(self.game_directory) / "data" / "swf" / image_path
        
        # Check for both .png and .dds extensions
        if not full_path.exists():
            # Try .dds if .png doesn't exist
            if full_path.suffix.lower() == '.png':
                dds_path = full_path.with_suffix('.dds')
                if dds_path.exists():
                    full_path = dds_path
                else:
                    log_message(LOGGER, f"  ⚠️  Image not found: {full_path} (also tried .dds)")
                    return image_path
            else:
                log_message(LOGGER, f"  ⚠️  Image not found: {full_path}")
                return image_path
        
        try:
            ext = full_path.suffix.lower()
            
            # Handle DDS files - convert to PNG
            if ext == '.dds':
                try:
                    from PIL import Image
                    
                    # Open DDS file with PIL
                    img = Image.open(full_path)
                    
                    # Rotate if requested (before converting to PNG)
                    if rotate:
                        img = img.rotate(90, expand=True)  # 90° counter-clockwise
                    
                    # Convert to PNG in memory
                    from io import BytesIO
                    png_buffer = BytesIO()
                    img.save(png_buffer, format='PNG')
                    img_data = png_buffer.getvalue()
                    mime_type = 'image/png'
                    
                except ImportError:
                    log_message(LOGGER, f"  ⚠️  PIL not available, cannot convert DDS: {full_path.name}")
                    return image_path
                except Exception as e:
                    log_message(LOGGER, f"  ⚠️  Failed to convert DDS {full_path.name}: {e}")
                    return image_path
            
            # Handle regular image files (PNG, JPG, etc)
            else:
                # If rotation needed, load with PIL
                if rotate:
                    try:
                        from PIL import Image
                        from io import BytesIO
                        
                        img = Image.open(full_path)
                        img = img.rotate(90, expand=True)  # 90° counter-clockwise
                        
                        png_buffer = BytesIO()
                        img.save(png_buffer, format='PNG')
                        img_data = png_buffer.getvalue()
                        mime_type = 'image/png'
                        
                    except ImportError:
                        log_message(LOGGER, f"  ⚠️  PIL not available, cannot rotate image: {full_path.name}")
                        # Fallback: read without rotation
                        with open(full_path, 'rb') as f:
                            img_data = f.read()
                        mime_types = {
                            '.png': 'image/png',
                            '.jpg': 'image/jpeg',
                            '.jpeg': 'image/jpeg',
                            '.gif': 'image/gif'
                        }
                        mime_type = mime_types.get(ext, 'image/png')
                    except Exception as e:
                        log_message(LOGGER, f"  ⚠️  Failed to rotate image {full_path.name}: {e}")
                        # Fallback: read without rotation
                        with open(full_path, 'rb') as f:
                            img_data = f.read()
                        mime_types = {
                            '.png': 'image/png',
                            '.jpg': 'image/jpeg',
                            '.jpeg': 'image/jpeg',
                            '.gif': 'image/gif'
                        }
                        mime_type = mime_types.get(ext, 'image/png')
                else:
                    # No rotation needed, read directly
                    with open(full_path, 'rb') as f:
                        img_data = f.read()
                    
                    # Determine MIME type
                    mime_types = {
                        '.png': 'image/png',
                        '.jpg': 'image/jpeg',
                        '.jpeg': 'image/jpeg',
                        '.gif': 'image/gif'
                    }
                    mime_type = mime_types.get(ext, 'image/png')
            
            # Convert to base64
            b64_data = base64.b64encode(img_data).decode('utf-8')
            
            return f"data:{mime_type};base64,{b64_data}"
            
        except Exception as e:
            log_message(LOGGER, f"  ⚠️  Failed to convert image {image_path}: {e}")
            return image_path
    
    def rank_needs_rotation(self, event: Dict, country: str, country_folder: str = None) -> bool:
        """
        Determine if a rank image needs to be rotated 90° counter-clockwise
        
        Args:
            event: Event dictionary
            country: Country name
            country_folder: Country folder path (e.g., "USSR/late", "Germany")
            
        Returns:
            True if image should be rotated
        """
        # Only rotate promotions (not awards)
        if event.get('type') != 'promotion':
            return False
        
        image_name = event.get('image', '').lower()
        
        # DEBUG: Print what we're checking
        # log_message(LOGGER, f"DEBUG: Checking rotation for {country}/{country_folder}/{image_name}")
        
        # Define which ranks need rotation (based on user requirements)
        ranks_to_rotate = {
            'Germany': [
                # ALL German ranks need rotation
                'unteroffizier.png',
                'oberstleutnant.png',
                'oberleutnant.png',
                'oberfeldwebel.png',
                'major.png',
                'leutnant.png',
                'hauptmann.png',
                'feldwebel.png',
                'generalleutnant.png',
                'generalmajor.png',
                'generalfeldmarschall.png',
                'oberst.png',
            ],
            
            'Britain': [
                # Only these 5 British ranks
                'flight_lieutenant.png',
                'flying_officer.png',
                'pilot_officer.png',
                'squadron_leader.png',
                'wing_commander.png',
                'group_captain.png',
                'air_commodore.png',
                'air_vice_marshal.png',
            ],
            
            'US': [  # NOTE: Changed from 'USA' to 'US' to match country_folder!
                # All US ranks EXCEPT first_sergeant.png
                'second_lieutenant.png',
                'major_usaaf.png',
                'lt_colonel.png',
                'flight_officer.png',
                # 'first_sergeant.png',  # ← NOT rotated!
                'first_lieutenant.png',
                'chief_warrant_officer.png',
                'captain_usaaf.png',
                'brigadier_general.png',
                'colonel.png',
                'major_general.png',
            ],
            
            'USSR/late': [
                # ALL USSR/late ranks need rotation
                'sub_colonel.png',
                'sergeant_vvs.png',
                'senior_sergeant.png',
                'senior_lieutenant.png',
                'major_vvs.png',
                'lieutenant_vvs.png',
                'junior_lieutenant.png',
                'captain_vvs.png',
                'colonel.png',
                'major_general.png',
                'lt_general.png',
            ],
            # USSR/early: NONE - not in dictionary, so will return False
        }
        
        # For Soviet Union, use the country_folder to determine early/late
        if country == 'Soviet Union':
            if country_folder == 'USSR/late':
                country_key = 'USSR/late'
            else:
                # USSR/early - no rotations
                return False
        else:
            country_key = country_folder or country
        
        # Check if this rank should be rotated
        country_ranks = ranks_to_rotate.get(country_key, [])
        should_rotate = image_name in [r.lower() for r in country_ranks]
        
        # DEBUG: Print result
        # log_message(LOGGER, f"DEBUG: country_key={country_key}, should_rotate={should_rotate}")
        
        return should_rotate
    
    def format_event_html(self, event: Dict, country: str, for_pdf: bool = False) -> str:
        """Format a single event as HTML
        
        Args:
            event: Event dictionary
            country: Country name
            for_pdf: If True, embed images as base64 for PDF compatibility
        """
        
        # Get image path with special handling for Soviet Union (early/late periods)
        country_folder_map = {
            'Germany': 'Germany',
            'Britain': 'Britain',
            'USA': 'US'
        }
        
        if country == 'Soviet Union':
            # Determine early vs late based on event date
            # Historical transition: 6 January 1943 (introduction of shoulder boards / погоны)
            event_date = event.get('date')
            
            if event_date and event_date >= "1943-01-06":
                country_folder = 'USSR/late'
            else:
                # Default to early if no date or before transition
                country_folder = 'USSR/early'
        else:
            country_folder = country_folder_map.get(country, country)
        
        image_path = f"CampaignRanksAwards/{country_folder}/{event['image']}"
        
        # Check if rank needs rotation
        needs_rotation = self.rank_needs_rotation(event, country, country_folder)
        
        # Convert to base64 if generating for PDF, with rotation if needed
        if for_pdf:
            image_src = self.image_to_base64(image_path, rotate=needs_rotation)
        else:
            # For in-game: Use Windows-style backslashes (IL-2 expects this)
            image_src = image_path.replace('/', '\\')
        
        # Format date
        if event.get('mission') == 'Initial':
            # Initial events (starting rank + pilot's badge)
            # Show date of first mission if available
            if event.get('date'):
                try:
                    date_obj = datetime.strptime(event['date'], '%Y-%m-%d')
                    date_str = date_obj.strftime('%d %B, %Y')
                except:
                    date_str = "Before First Mission"
            else:
                date_str = "Before First Mission"
        elif event.get('date'):
            try:
                date_obj = datetime.strptime(event['date'], '%Y-%m-%d')
                date_str = date_obj.strftime('%d %B, %Y')
            except:
                date_str = event['date']
        else:
            date_str = f"After Mission {event['mission']}"
        
        # Format description
        if event['type'] == 'promotion':
            if event.get('mission') == 'Initial':
                description = f"Started as {event['rank']}"
            else:
                description = f"Promoted to {event['rank']}"
        else:
            if event.get('mission') == 'Initial':
                description = f"Awarded {event['name']}"
            else:
                description = f"Awarded {event['name']}"
        
        # Apply rotation:
        # - For PDF: Image is rotated via PIL in image_to_base64()
        # - For in-game: NO rotation (IL-2's browser doesn't support it well)
        
        # DEBUG: Print what we're generating
        if for_pdf:
            # PDF: Better formatting with text before image and proper alignment
            result = f"• {date_str} - {description} <span style='display: inline-block; vertical-align: middle; margin-left: 5px;'><img src='{image_src}' style='vertical-align: middle;'></span><br>"
        else:
            # In-game: IL-2 expects unquoted src, image after text
            result = f"• {date_str} - {description} <img src={image_src}><br>"
            log_message(LOGGER, f"DEBUG HTML: {result[:150]}")  # First 150 chars
        
        return result
    
    
    def generate_debriefings_html(self, campaign_name: str, completed_missions: List[str]) -> tuple:
        """
        Generate Mission Debriefings HTML section
        
        Args:
            campaign_name: Campaign folder name
            completed_missions: List of completed mission IDs
            
        Returns:
            Tuple of (html_string, debriefings_dict)
        """
        if not self.log_processor:
            return ("", {})
        
        # Get debriefing data for all missions
        debriefings = self.log_processor.get_all_debriefings(campaign_name, completed_missions)
        
        if not debriefings:
            return ("", {})
        
        # Load decoded campaign data ONCE if in PDF mode (performance optimization)
        decoded_data = None
        if self.mode == "pdf":
            # Look for campaigns_decoded.json in the tracker root directory
            # (not in reports/ subdirectory where PDFs are saved)
            decoded_path = CAMPAIGNS_DECODED_FILE
            all_decoded = _load_decoded_campaign(decoded_path)
            
            if all_decoded:
                # Try exact match first
                if campaign_name in all_decoded:
                    decoded_data = all_decoded[campaign_name]
                    log_message(LOGGER, f"  ✓ Loaded combat data for '{campaign_name}'")
                else:
                    # Try case-insensitive match
                    campaign_name_lower = campaign_name.lower()
                    for key, value in all_decoded.items():
                        if key.lower() == campaign_name_lower:
                            decoded_data = value
                            log_message(LOGGER, f"  ✓ Loaded combat data for '{campaign_name}' (matched as '{key}')")
                            break
                    
                    if not decoded_data:
                        log_message(LOGGER, f"  ⚠️  Warning: No decoded data found for campaign '{campaign_name}'")
                        log_message(LOGGER, f"      Available campaigns in decoded file: {', '.join(all_decoded.keys())}")
            else:
                log_message(LOGGER, f"  ⚠️  Warning: campaigns_decoded.json not found at: {decoded_path}")
        
        html_lines = ["<b>Mission Debriefings</b><br>", "<br>"]
        
        # Sort missions in order
        sorted_missions = sorted(debriefings.keys(), key=smart_mission_sort_key)
        
        for mission_id in sorted_missions:
            data = debriefings[mission_id]
            
            log_message(LOGGER, f"  Processing debriefing for Mission {mission_id}...")
            
            # Extract mission date and start time
            mission_date, mission_start_time = self.extract_mission_datetime(campaign_name, mission_id)
            date_str = mission_date if mission_date else None
            
            # Summary data
            aircraft = data['player']['aircraft']
            duration = data['summary']['flight_duration']
            status = data['summary']['final_state']
            aircraft_dmg = data['summary'].get('aircraft_damage', 0)
            pilot_dmg = data['summary'].get('pilot_damage', 0)
            
            # Mission header
            html_lines.append(f'<div class="mission-box">')
            html_lines.append(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━<br>")
            if date_str:
                html_lines.append(f"<b>MISSION {mission_id} | {date_str}</b><br>")
            else:
                html_lines.append(f"<b>MISSION {mission_id}</b><br>")
            html_lines.append(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━<br>")
            
            summary_parts = [f"Aircraft: {aircraft}", f"Duration: {duration}", f"Status: {status}"]
            if aircraft_dmg > 0:
                summary_parts.append(f"Aircraft Dmg: {aircraft_dmg}%")
            if pilot_dmg > 0:
                summary_parts.append(f"Pilot Dmg: {pilot_dmg}%")
            html_lines.append(f"{' | '.join(summary_parts)}<br>")
            html_lines.append(f"<br>")
            
            # ======================================================================
            # Conditional Rendering: PDF vs In-Game
            # ======================================================================
            if self.mode == "pdf":
                # PDF mode → show Combat Results from campaigns_decoded.json
                if decoded_data:
                    html_lines.append(generate_mission_combat_results_html(mission_id, decoded_data, self.game_directory))
                else:
                    html_lines.append(f"<p><i>Combat data not available for Mission {mission_id}</i></p>")
            else:
                # In-Game mode → show Flight Log instead of Combat Results
                html_lines.append(f"<b>FLIGHT LOG</b><br>")
                mission_ended_in_bailout = "Bailout" in status

                for event in data.get('events', [])[:25]:  # Max 25 events
                    time = event.get('time', '')
                    event_type = event.get('type', event.get('event', ''))
                    target = event.get('target', '')
                    altitude = event.get('altitude')
                    damage = event.get('damage')

                    if event_type == "Kill":
                        details = f" (Alt: {altitude}m)" if altitude else ""
                        html_lines.append(f"{time}  {target} destroyed{details}<br>")
                    elif event_type == "Damage Taken":
                        if mission_ended_in_bailout:
                            continue
                        html_lines.append(f"{time}  Hit by {target}<br>")
                    elif event_type in ["Takeoff", "Landing", "Crash", "Bailout"]:
                        html_lines.append(f"{time}  {event_type}<br>")
                    else:
                        html_lines.append(f"{time}  {event_type}<br>")
            
            # ======================================================================
            # End of mission box
            # ======================================================================
            #html_lines.append(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━<br>")
            html_lines.append("</div>")
            html_lines.append("<br>")
        
        return ("\n".join(html_lines), debriefings)

    
    def generate_events_html(self, events: List[Dict], country: str, for_pdf: bool = False) -> str:
        if not events:
            return ""
        
        # Page break before events in PDF mode
        if for_pdf:
            html_lines = ['<div style="page-break-before: always;"></div>', "<b>Events</b><br>"]
        else:
            html_lines = ["<b>Events</b><br>"]
        
        for event in events:
            html_lines.append(self.format_event_html(event, country, for_pdf=for_pdf))
        
        return "\n".join(html_lines)
    
    def update_campaign_info_file(self, campaign_name: str, events_html: str) -> bool:
        """
        Update all campaign info.locale=*.txt files with Events section.
        
        IL-2 loads the locale file matching the user's language setting.
        To ensure tracker content is visible regardless of language,
        we write to all existing locale files (eng, ger, rus, fra, spa, chs, etc.).
        Uses re.sub for robust removal of ALL tracker content (including duplicates)
        """
        if not self.game_directory:
            log_message(LOGGER, f"  Error: No game directory configured")
            return False
        
        campaign_path = Path(self.game_directory) / "data" / "Campaigns" / campaign_name
        
        if not campaign_path.exists():
            log_message(LOGGER, f"  Warning: Campaign folder not found: {campaign_path}")
            return False
        
        # Find all locale files
        from utils.info_locale import find_all_info_locale_files
        locale_files = find_all_info_locale_files(campaign_path)
        
        if not locale_files:
            # Fallback: check for eng file specifically (for error message)
            eng_file = campaign_path / "info.locale=eng.txt"
            log_message(LOGGER, f"  Warning: No info.locale files found in: {campaign_path}")
            log_message(LOGGER, f"  (This is normal if campaign hasn't been started)")
            return False
        
        if self.dry_run:
            log_message(LOGGER, f"  [DRY RUN] Would update {len(locale_files)} locale file(s): {[f.name for f in locale_files]}")
            return True
        
        success_count = 0
        
        for info_file in locale_files:
            try:
                # Backup once per file
                backup_file = info_file.with_suffix('.txt.backup')
                if not backup_file.exists():
                    shutil.copy(info_file, backup_file)
                    log_message(LOGGER, f"  Created backup: {backup_file.name}")
                
                raw = info_file.read_bytes()
                cleaned, detected_encoding, original = decode_and_clean_info_locale(raw)
                removed = len(original) - len(cleaned)
                if removed > 0:
                    log_message(LOGGER, f"  ✂️  [{info_file.name}] Removed {removed} chars of old tracker content")
                
                # Remove excessive <u> tags from description
                u_count = cleaned.count('<u>')
                if u_count > 3:
                    log_message(LOGGER, f"  🧹 [{info_file.name}] Cleaning {u_count} <u> tags...")
                    # Find section headers: <u>text</u><br>
                    headers = re.findall(r'<u>([^<]+)</u><br>', cleaned)
                    # Remove all <u> tags
                    cleaned = cleaned.replace('<u>', '').replace('</u>', '')
                    # Re-add as <b> for headers
                    for h in headers:
                        cleaned = cleaned.replace(f'{h}<br>', f'<b>{h}</b><br>', 1)
                
                # Build final content
                updated = cleaned + '<br><br>' + events_html
                
                # Verification: Count sections in final content
                matches = list(re.finditer(TRACKER_SECTION_HEADER_PATTERN, updated, re.IGNORECASE))
                
                if len(matches) > 2:
                    log_message(LOGGER, f"  ⚠️  [{info_file.name}] WARNING: {len(matches)} sections (expected 2)!")
                
                # Write with original encoding
                with open(info_file, "w", encoding=detected_encoding, newline="") as f:
                    f.write(updated)
                
                success_count += 1
                
            except Exception as e:
                log_message(LOGGER, f"  ❌ [{info_file.name}] Error: {e}")
                import traceback
                traceback.print_exc()
        
        if success_count > 0:
            log_message(LOGGER, f"  ✅ Updated {success_count}/{len(locale_files)} locale file(s)")
            return True
            
        else:
            log_message(LOGGER, f"  ❌ Failed to update any locale files")
            return False


    
    def get_campaign_display_name(self, campaign_name: str) -> str:
        """
        Extract campaign display name from info.locale=eng.txt
        
        Args:
            campaign_name: Campaign folder name
            
        Returns:
            Display name from &name= field, or folder name as fallback
        """
        if not self.game_directory:
            return campaign_name
        
        campaign_path = Path(self.game_directory) / "data" / "Campaigns" / campaign_name
        info_file = campaign_path / "info.locale=eng.txt"
        
        if not info_file.exists():
            return campaign_name
        
        try:
            # Read file
            with open(info_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Look for &name="Campaign Display Name"
            # Can be with or without quotes
            match = re.search(r'&name\s*=\s*"([^"]+)"', content)
            if match:
                return match.group(1)
            
            # Try without quotes
            match = re.search(r'&name\s*=\s*([^\n&]+)', content)
            if match:
                return match.group(1).strip()
            
        except Exception as e:
            log_message(LOGGER, f"  ⚠️  Could not read campaign name: {e}")
        
        return campaign_name
    
    def generate_campaign_summary_html(self, campaign_name: str, events: List[Dict], debriefings: Dict, 
                                        country: str, cumulative_stats: Dict, decoded_data: dict = None) -> str:
        """
        Generate campaign summary statistics for PDF
        
        Args:
            campaign_name: Campaign folder name
            events: List of events (awards, promotions)
            debriefings: Dict of mission debriefings
            country: Country code
            cumulative_stats: Cumulative statistics from campaigns_decoded.json (optional)
            
        Returns:
            HTML string for campaign summary
        """
        if not debriefings:
            return ""
        
        # Collect statistics
        total_air = 0
        total_ground = 0
        total_naval = 0
        total_flight_time_seconds = 0
        aircraft_usage = {}
        aircraft_kills = {}
        debrief_kills_by_aircraft = {}
        target_counts = {'air': {}, 'ground': {}, 'naval': {}}
        mission_count = len(debriefings)
        safe_landings = 0
        hard_landings = 0
        wounded_landings = 0
        bailouts = 0
        kia_mia = 0
        
        # Initialize parked kills counter
        total_air_parked = 0
        
        # Get parked kills from cumulative stats (campaigns_decoded.json)
        # These are kills that happened outside of debriefed missions
        if cumulative_stats:
            total_air_parked += cumulative_stats.get('static_plane_kills', 0)
        
        # Analyze all missions
        for mission_id, data in debriefings.items():
            summary = data.get('summary', {})
            player = data.get('player', {})
            
            # Combat stats (from summary)
            total_air += summary.get('air_kills', 0)
            total_ground += summary.get('ground_kills', 0)
            total_naval += summary.get('naval_kills', 0)
            
            # Add parked kills from this mission's debriefing
            total_air_parked += summary.get('air_kills_parked', 0)
            
            # Flight time (from summary)
            duration = summary.get('flight_duration', '')
            if duration and duration != 'N/A':
                try:
                    parts = duration.split(':')
                    if len(parts) == 3:
                        hours, minutes, seconds = map(int, parts)
                        total_flight_time_seconds += hours * 3600 + minutes * 60 + seconds
                except:
                    pass
            
            # Aircraft usage (from player)
            aircraft = player.get('aircraft', 'Unknown')
            if aircraft not in aircraft_usage:
                aircraft_usage[aircraft] = {'missions': 0}
            aircraft_usage[aircraft]['missions'] += 1
            debrief_kills_by_aircraft[aircraft] = debrief_kills_by_aircraft.get(aircraft, 0) + (
                summary.get('air_kills', 0) +
                summary.get('ground_kills', 0) +
                summary.get('naval_kills', 0)
            )
            
            # Landing status (from summary)
            status = summary.get('final_state', '').lower()
            # Priority: wounded > bailout > KIA/MIA > hard/crash > safe
            if 'wounded' in status:
                wounded_landings += 1
            elif 'bail' in status or 'bailed' in status:
                bailouts += 1
            elif 'kia' in status or 'mia' in status or 'killed' in status:
                kia_mia += 1
            elif 'hard' in status or 'crash' in status:
                hard_landings += 1
            elif 'landed' in status:
                safe_landings += 1
            
            # Target breakdown (from events)
            events_list = data.get('events', [])
            for event in events_list:
                # Get event type (try 'type' first, then 'event' as fallback)
                event_type = event.get('type', event.get('event', ''))
                
                if event_type == "Kill":
                    target = event.get('target', '')
                    # Categorize by target name patterns
                    target_lower = target.lower()
                    
                    # Naval targets
                    if any(naval in target_lower for naval in ['boat', 'ship', 'vessel', 'torpedo']):
                        category = 'naval'
                    # Ground targets  
                    elif any(ground in target_lower for ground in ['aa', 'gun', 'ml-20', 'dshk', '52-k', 'flak', 'tank', 'truck', 'artillery']):
                        category = 'ground'
                    # Air targets (default)
                    else:
                        category = 'air'
                    
                    if category == 'air':
                        target_counts['air'][target] = target_counts['air'].get(target, 0) + 1
                    elif category == 'ground':
                        target_counts['ground'][target] = target_counts['ground'].get(target, 0) + 1
                    elif category == 'naval':
                        target_counts['naval'][target] = target_counts['naval'].get(target, 0) + 1
        
        # Format flight time
        total_hours = total_flight_time_seconds // 3600
        total_minutes = (total_flight_time_seconds % 3600) // 60
        avg_seconds = total_flight_time_seconds // mission_count if mission_count > 0 else 0
        avg_minutes = avg_seconds // 60
        
        # Get campaign dates
        first_mission_date = None
        last_mission_date = None
        if campaign_name in self.mission_dates:
            mission_dates_dict = self.mission_dates[campaign_name]
            mission_ids = sorted(debriefings.keys(), key=smart_mission_sort_key)
            if mission_ids:
                first_mission_id = mission_ids[0]
                last_mission_id = mission_ids[-1]
                first_mission_date = mission_dates_dict.get(first_mission_id, {}).get('date')
                last_mission_date = mission_dates_dict.get(last_mission_id, {}).get('date')
        
        # Calculate campaign duration
        campaign_duration_days = None
        if first_mission_date and last_mission_date:
            try:
                from datetime import datetime
                fmt = '%Y.%m.%d'
                start = datetime.strptime(first_mission_date.replace('.', '-'), '%Y-%m-%d')
                end = datetime.strptime(last_mission_date.replace('.', '-'), '%Y-%m-%d')
                campaign_duration_days = (end - start).days
            except:
                pass
        
        # Get career progression
        promotions = [e for e in events if e.get('type') == 'promotion']
        awards = [e for e in events if e.get('type') == 'award']

        per_mission_kills = {}
        if decoded_data:
            per_mission_stats = decoded_data.get('characterStatisticsByFileName', {})
            per_mission_kills = self._calculate_per_mission_kill_totals(per_mission_stats)

        if per_mission_kills:
            aircraft_map = self._load_mission_aircraft_map(campaign_name)
            for mission_id, totals in per_mission_kills.items():
                aircraft_entry = aircraft_map.get(mission_id, {})
                if isinstance(aircraft_entry, dict):
                    aircraft_name = aircraft_entry.get("aircraft")
                else:
                    aircraft_name = aircraft_entry

                if not aircraft_name:
                    aircraft_name = "Unknown"

                aircraft_kills[aircraft_name] = aircraft_kills.get(aircraft_name, 0) + totals.get("total_kills", 0)
        else:
            aircraft_kills = dict(debrief_kills_by_aircraft)

        def format_kill_count(value: float) -> str:
            try:
                return f"{float(value):g}"
            except (TypeError, ValueError):
                return "0"
        
        starting_rank = promotions[0]['rank'] if promotions else 'Unknown'
        final_rank = promotions[-1]['rank'] if promotions else starting_rank
        
        # Generate HTML
        html = []
        html.append('<div style="page-break-before: always;"></div>')
        html.append('<div style="text-align: center; margin: 40px 0 30px 0;">')
        html.append('<div style="border-top: 3px double #333; border-bottom: 3px double #333; padding: 20px 0; margin: 0 50px;">')
        html.append('<h1 style="margin: 0; font-size: 24pt;">CAMPAIGN SUMMARY</h1>')
        
        campaign_display_name = self.get_campaign_display_name(campaign_name)
        html.append(f'<p style="margin: 10px 0 0 0; font-size: 14pt; font-style: italic;">{campaign_display_name}</p>')
        html.append('</div>')
        html.append('</div>')
        
        # Combat Results
        html.append('<h2 style="border-bottom: 2px solid #333; padding-bottom: 5px; margin-top: 30px;">COMBAT RESULTS</h2>')
        if decoded_data:
            html.append(generate_campaign_summary_combat_results_html(decoded_data, self.game_directory))
        else:
            html.append('<p>No combat data available.</p>')
                
        # Missions Flown
        html.append('<h2 style="border-bottom: 2px solid #333; padding-bottom: 5px; margin-top: 30px;">MISSIONS FLOWN</h2>')
        html.append(f'<table style="width: 100%; margin: 10px 0;">')
        html.append(f'<tr><td style="padding: 5px 0;"><b>Completed:</b></td><td style="text-align: right;">{mission_count} missions</td></tr>')
        html.append(f'<tr><td style="padding: 5px 0;"><b>Total Flight Time:</b></td><td style="text-align: right;">{total_hours}h {total_minutes}m</td></tr>')
        html.append(f'<tr><td style="padding: 5px 0;"><b>Average Duration:</b></td><td style="text-align: right;">{avg_minutes}m</td></tr>')
        html.append(f'<tr><td colspan="2" style="padding: 10px 0 5px 0;"></td></tr>')
        
        total_outcomes = safe_landings + hard_landings + wounded_landings + bailouts + kia_mia
        if total_outcomes > 0:
            safe_pct = int(safe_landings / total_outcomes * 100)
            html.append(f'<tr><td style="padding: 5px 0;"><b>Safe Landings:</b></td><td style="text-align: right;">{safe_landings} ({safe_pct}%)</td></tr>')
            
            if hard_landings > 0:
                hard_pct = int(hard_landings / total_outcomes * 100)
                html.append(f'<tr><td style="padding: 5px 0;"><b>Hard Landings / Crashes:</b></td><td style="text-align: right;">{hard_landings} ({hard_pct}%)</td></tr>')
            
            if wounded_landings > 0:
                wounded_pct = int(wounded_landings / total_outcomes * 100)
                html.append(f'<tr><td style="padding: 5px 0;"><b>Wounded Landings:</b></td><td style="text-align: right;">{wounded_landings} ({wounded_pct}%)</td></tr>')
            
            if bailouts > 0:
                bailout_pct = int(bailouts / total_outcomes * 100)
                html.append(f'<tr><td style="padding: 5px 0;"><b>Bailouts:</b></td><td style="text-align: right;">{bailouts} ({bailout_pct}%)</td></tr>')
            
            if kia_mia > 0:
                kia_pct = int(kia_mia / total_outcomes * 100)
                html.append(f'<tr><td style="padding: 5px 0;"><b>KIA / MIA:</b></td><td style="text-align: right;">{kia_mia} ({kia_pct}%)</td></tr>')
        
        html.append('</table>')
        
        # Aircraft Flown
        if aircraft_usage:
            html.append('<h2 style="border-bottom: 2px solid #333; padding-bottom: 5px; margin-top: 30px;">AIRCRAFT FLOWN</h2>')
            html.append(f'<table style="width: 100%; margin: 10px 0;">')
            aircraft_names = set(aircraft_usage.keys()) | set(aircraft_kills.keys())
            aircraft_rows = []
            for aircraft in aircraft_names:
                missions = aircraft_usage.get(aircraft, {}).get("missions", 0)
                kills = aircraft_kills.get(aircraft, 0)
                aircraft_rows.append((aircraft, missions, kills))

            for aircraft, missions, kills in sorted(aircraft_rows, key=lambda x: (x[1], x[2]), reverse=True):
                if missions == 0 and kills == 0:
                     continue  # Skip "Unknown: 0 missions (0 kills)"
                html.append(
                    f'<tr><td style="padding: 5px 0;"><b>{aircraft}:</b></td>'
                    f'<td style="text-align: right;">{missions} missions ({format_kill_count(kills)} kills)</td></tr>'
                )
            html.append('</table>')
        
        # Career Progression
        html.append('<h2 style="border-bottom: 2px solid #333; padding-bottom: 5px; margin-top: 30px;">CAREER PROGRESSION</h2>')
        html.append(f'<table style="width: 100%; margin: 10px 0;">')
        html.append(f'<tr><td style="padding: 5px 0;"><b>Starting Rank:</b></td><td style="text-align: right;">{starting_rank}</td></tr>')
        html.append(f'<tr><td style="padding: 5px 0;"><b>Final Rank:</b></td><td style="text-align: right;">{final_rank}</td></tr>')
        html.append(f'<tr><td style="padding: 5px 0;"><b>Promotions:</b></td><td style="text-align: right;">{len(promotions)}</td></tr>')
        html.append(f'<tr><td colspan="2" style="padding: 10px 0 5px 0;"></td></tr>')
        html.append(f'<tr><td style="padding: 5px 0;"><b>Awards Received:</b></td><td style="text-align: right;">{len(awards)}</td></tr>')
        html.append('</table>')
        
        if awards:
            html.append('<ul style="margin: 5px 0; padding-left: 20px;">')
            for award in awards:
                html.append(f'<li>{award["name"]}</li>')
            html.append('</ul>')
        
        
        
        # Campaign Timeline
        if first_mission_date and last_mission_date:
            html.append('<h2 style="border-bottom: 2px solid #333; padding-bottom: 5px; margin-top: 30px;">CAMPAIGN TIMELINE</h2>')
            html.append(f'<table style="width: 100%; margin: 10px 0;">')
            
            # Format dates nicely
            start_date_formatted = self.format_date(first_mission_date)
            end_date_formatted = self.format_date(last_mission_date)
            
            html.append(f'<tr><td style="padding: 5px 0;"><b>Start Date:</b></td><td style="text-align: right;">{start_date_formatted}</td></tr>')
            html.append(f'<tr><td style="padding: 5px 0;"><b>End Date:</b></td><td style="text-align: right;">{end_date_formatted}</td></tr>')
            if campaign_duration_days is not None:
                html.append(f'<tr><td style="padding: 5px 0;"><b>Campaign Duration:</b></td><td style="text-align: right;">{campaign_duration_days} days</td></tr>')
            html.append('</table>')
        
        return '\n'.join(html)
    def export_campaign_to_pdf(self, campaign_name: str, html_content: str) -> bool:
        """
        Export campaign report as PDF
        
        ✅ IMPROVED:
        - Better error handling with specific error messages
        - Atomic write using temporary file
        - HTML fallback when PDF fails
        - Graceful degradation (continues even if PDF fails)
        
        Args:
            campaign_name: Campaign folder name
            html_content: Complete HTML content to export
            
        Returns:
            True if successful, False otherwise
        """
        try:
            import pdfkit
        except ImportError:
            log_message(LOGGER, f"  ℹ️  PDF export skipped: pdfkit not installed")
            log_message(LOGGER, f"      Install with: pip install pdfkit")
            return False
        
        # Check if wkhtmltopdf is available
        config = None
        try:
            # First, check if we're running as PyInstaller bundle with embedded wkhtmltopdf
            if getattr(sys, 'frozen', False):
                # Running as compiled EXE
                bundle_dir = Path(sys._MEIPASS)
                wkhtmltopdf_path = bundle_dir / 'wkhtmltopdf.exe'
                
                if wkhtmltopdf_path.exists():
                    # Use bundled wkhtmltopdf
                    config = pdfkit.configuration(wkhtmltopdf=str(wkhtmltopdf_path))
                else:
                    # Try system-installed wkhtmltopdf
                    config = pdfkit.configuration()
            else:
                # Running as Python script - use system wkhtmltopdf
                config = pdfkit.configuration()
                
        except OSError:
            log_message(LOGGER, f"  ℹ️  PDF export skipped: wkhtmltopdf not found")
            log_message(LOGGER, f"      Download from: https://wkhtmltopdf.org/downloads.html")
            return False
        
        # ✅ Create reports directory if it doesn't exist
        reports_dir = BASE_DIR / 'reports'
        try:
            reports_dir.mkdir(exist_ok=True)
        except Exception as e:
            log_message(LOGGER, f"  ⚠️  Could not create reports directory: {e}")
            return False
        
        # Get campaign display name from info file
        campaign_display_name = self.get_campaign_display_name(campaign_name)
        
        # Clean campaign name for filename (remove special chars)
        safe_name = safe_campaign_filename(campaign_name)
        campaign_report_dir = reports_dir / safe_name
        campaign_report_dir.mkdir(parents=True, exist_ok=True)
        pdf_filename = campaign_report_dir / f"{safe_name}_Report.pdf"

        # If the target PDF is open/locked, write a fallback instead of failing
        if is_file_locked(pdf_filename):
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            fallback = campaign_report_dir / f"{safe_name}_Report_LOCKED_{ts}.pdf"
            log_message(LOGGER, f"  ⚠️  PDF is open/locked. Writing fallback: {fallback.name}")
            pdf_filename = fallback
        
        try:
            # Create complete HTML document
            full_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{campaign_display_name} - Campaign Report</title>
    <style>
        body {{
            font-family: 'SpecialElite', monospace, Arial, sans-serif;
            margin: 20px;
            font-size: 10pt;
        }}
        }}
        h1 {{
            text-align: center;
            border-bottom: 2px solid #333;
            padding-bottom: 10px;
        }}
        .mission-box {{
            page-break-inside: avoid;
            margin-bottom: 10px;
        }}
        /* Combat Results Grid Layout */
        .combat-results-grid {{
            width: 100%;
            margin: 20px 0;
            font-family: 'SpecialElite', monospace;
        }}

        /* CATEGORY HEADERS */
        .category-headers {{
            display: table;
            width: 100%;
            margin-bottom: 10px;
            border-bottom: 2px solid #000;
            padding-bottom: 10px;
        }}

        .category-col {{
            display: table-cell;
            width: 16.66%;
            text-align: center;
            vertical-align: top;
            padding: 0 5px;
        }}

        .category-icon img {{
            display: block;
            margin: 0 auto 5px auto;
        }}

        .category-total {{
            font-size: 20px;
            font-weight: bold;
            margin: 5px 0;
        }}

        .category-name {{
            font-size: 10px;
            font-weight: bold;
            text-transform: uppercase;
        }}

        /* SUBCATEGORIES */
        .subcategory-columns {{
            display: table;
            width: 100%;
            table-layout: fixed;
        }}

        .subcat-column {{
            display: table-cell;
            width: 16.66%;
            vertical-align: top;
            padding: 0 5px;
            border-right: 1px solid #ddd;
        }}

        .subcat-column:last-child {{
            border-right: none;
        }}

        /* SUBCATEGORY ROWS */
        .subcat-row {{
            padding: 3px 5px;
            min-height: 18px;
            overflow: hidden;
        }}

        .subcat-row:last-child {{
            border-bottom: none;
        }}

        .subcat-row::after {{
            content: "";
            display: table;
            clear: both;
        }}

        .subcat-name {{
            font-size: 9px;
            color: #666;
            float: left;
            max-width: 70%;
            line-height: 1.2;
        }}

        .subcat-value {{
            font-size: 10px;
            font-weight: bold;
            float: right;
        }}
    </style>
</head>
<body>
    <h1>{campaign_display_name}</h1>
    <p><i>Campaign Report - Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i></p>
    <hr>
    {html_content}
</body>
</html>
"""
            
            # PDF options
            options = {
                'page-size': 'A4',
                'margin-top': '15mm',
                'margin-right': '15mm',
                'margin-bottom': '15mm',
                'margin-left': '15mm',
                'encoding': 'UTF-8',
                'no-outline': None,
                'enable-local-file-access': None,
                'quiet': ''  # Suppress wkhtmltopdf warnings
            }
            
            # ✅ Replace font path placeholder with actual game directory
            full_html = full_html.replace('GAME_DIR_PLACEHOLDER', self.game_directory.replace('\\', '/'))
            
            # ✅ IMPROVED: Use temporary file for atomic write
            tmp_pdf = pdf_filename.with_suffix('.tmp.pdf')
            
            try:
                # Convert HTML to PDF (write to temp file first)
                pdfkit.from_string(full_html, str(tmp_pdf), options=options, configuration=config)
                
                # ✅ Atomic replace: if we got here, PDF generation succeeded
                tmp_pdf.replace(pdf_filename)
                
                log_message(LOGGER, f"  ✓ PDF exported: {pdf_filename}")
                return True
                
            except Exception as pdf_error:
                # ✅ IMPROVED: More specific error handling
                log_message(LOGGER, f"  ⚠️  PDF conversion failed: {pdf_error}")
                log_message(LOGGER, f"      Campaign data is still saved in JSON/HTML format")
                
                # ✅ Clean up temp file if it exists
                try:
                    if tmp_pdf.exists():
                        tmp_pdf.unlink()
                except Exception:
                    pass
                
                # ✅ IMPROVED: Save HTML fallback
                try:
                    html_fallback = pdf_filename.with_suffix('.html')
                    with open(html_fallback, 'w', encoding='utf-8') as f:
                        f.write(full_html)
                    log_message(LOGGER, f"  ℹ️  HTML fallback saved: {html_fallback}")
                except Exception as html_error:
                    log_message(LOGGER, f"  ⚠️  Could not save HTML fallback: {html_error}")
                
                return False
            
        except Exception as e:
            # ✅ IMPROVED: Catch any other errors gracefully
            log_message(LOGGER, f"  ❌ PDF export error: {e}")
            log_message(LOGGER, f"      This is not critical - campaign data is still processed")
            
            # ✅ Try to save debug info
            try:
                import traceback
                error_log = reports_dir / f"{safe_name}_PDF_ERROR.log"
                with open(error_log, 'w', encoding='utf-8') as f:
                    f.write(f"PDF Export Error for {campaign_name}\n")
                    f.write(f"Time: {datetime.now()}\n\n")
                    f.write(traceback.format_exc())
                log_message(LOGGER, f"  ℹ️  Error details saved to: {error_log}")
            except Exception:
                pass
            
            return False

    
    # def export_campaign_to_pdf(self, campaign_name: str, html_content: str) -> bool:
        # """
        # Export campaign report as PDF
        
        # Args:
            # campaign_name: Campaign folder name
            # html_content: Complete HTML content to export
            
        # Returns:
            # True if successful, False otherwise
        # """
        # try:
            # import pdfkit
        # except ImportError:
            # log_message(LOGGER, f"  ℹ️  PDF export skipped: pdfkit not installed")
            # log_message(LOGGER, f"      Install with: pip install pdfkit")
            # return False
        
        # # Check if wkhtmltopdf is available
        # config = None
        # try:
            # # First, check if we're running as PyInstaller bundle with embedded wkhtmltopdf
            # if getattr(sys, 'frozen', False):
                # # Running as compiled EXE
                # bundle_dir = Path(sys._MEIPASS)
                # wkhtmltopdf_path = bundle_dir / 'wkhtmltopdf.exe'
                
                # if wkhtmltopdf_path.exists():
                    # # Use bundled wkhtmltopdf
                    # config = pdfkit.configuration(wkhtmltopdf=str(wkhtmltopdf_path))
                # else:
                    # # Try system-installed wkhtmltopdf
                    # config = pdfkit.configuration()
            # else:
                # # Running as Python script - use system wkhtmltopdf
                # config = pdfkit.configuration()
                
        # except OSError:
            # log_message(LOGGER, f"  ℹ️  PDF export skipped: wkhtmltopdf not found")
            # log_message(LOGGER, f"      Download from: https://wkhtmltopdf.org/downloads.html")
            # return False
        
        # # Create reports directory if it doesn't exist
        # reports_dir = Path('reports')
        # reports_dir.mkdir(exist_ok=True)
        
        # # Get campaign display name from info file
        # campaign_display_name = self.get_campaign_display_name(campaign_name)
        
        # # Clean campaign name for filename (remove special chars)
        # safe_name = safe_campaign_filename(campaign_name)
        # pdf_filename = reports_dir / f"{safe_name}_Report.pdf"

        # # If the target PDF is open/locked, write a fallback instead of failing
        # if is_file_locked(pdf_filename):
            # ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            # fallback = reports_dir / f"{safe_name}_Report_LOCKED_{ts}.pdf"
            # log_message(LOGGER, f"  ⚠️  PDF is open/locked. Writing fallback: {fallback.name}")
            # pdf_filename = fallback
        
        # try:
            # # Create complete HTML document
            # full_html = f"""
# <!DOCTYPE html>
# <html>
# <head>
    # <meta charset="UTF-8">
    # <title>{campaign_display_name} - Campaign Report</title>
    # <style>
        # body {{
            # font-family: 'SpecialElite', monospace, Arial, sans-serif;
            # margin: 20px;
            # font-size: 10pt;
        # }}
        # }}
        # h1 {{
            # text-align: center;
            # border-bottom: 2px solid #333;
            # padding-bottom: 10px;
        # }}
        # .mission-box {{
            # page-break-inside: avoid;
            # margin-bottom: 10px;
        # }}
        # /* Combat Results Grid Layout */
        # .combat-results-grid {{
            # width: 100%;
            # margin: 20px 0;
            # font-family: 'SpecialElite', monospace;
        # }}

        # /* CATEGORY HEADERS */
        # .category-headers {{
            # display: table;
            # width: 100%;
            # margin-bottom: 10px;
            # border-bottom: 2px solid #000;
            # padding-bottom: 10px;
        # }}

        # .category-col {{
            # display: table-cell;
            # width: 16.66%;
            # text-align: center;
            # vertical-align: top;
            # padding: 0 5px;
        # }}

        # .category-icon img {{
            # display: block;
            # margin: 0 auto 5px auto;
        # }}

        # .category-total {{
            # font-size: 20px;
            # font-weight: bold;
            # margin: 5px 0;
        # }}

        # .category-name {{
            # font-size: 10px;
            # font-weight: bold;
            # text-transform: uppercase;
        # }}

        # /* SUBCATEGORIES */
        # .subcategory-columns {{
            # display: table;
            # width: 100%;
            # table-layout: fixed;
        # }}

        # .subcat-column {{
            # display: table-cell;
            # width: 16.66%;
            # vertical-align: top;
            # padding: 0 5px;
            # border-right: 1px solid #ddd;
        # }}

        # .subcat-column:last-child {{
            # border-right: none;
        # }}

        # /* SUBCATEGORY ROWS */
        # .subcat-row {{
            # padding: 3px 5px;
            # min-height: 18px;
            # overflow: hidden;
        # }}

        # .subcat-row:last-child {{
            # border-bottom: none;
        # }}

        # .subcat-row::after {{
            # content: "";
            # display: table;
            # clear: both;
        # }}

        # .subcat-name {{
            # font-size: 9px;
            # color: #666;
            # float: left;
            # max-width: 70%;
            # line-height: 1.2;
        # }}

        # .subcat-value {{
            # font-size: 10px;
            # font-weight: bold;
            # float: right;
        # }}
    # </style>
# </head>
# <body>
    # <h1>{campaign_display_name}</h1>
    # <p><i>Campaign Report - Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i></p>
    # <hr>
    # {html_content}
# </body>
# </html>
# """
            
            # # PDF options
            # options = {
                # 'page-size': 'A4',
                # 'margin-top': '15mm',
                # 'margin-right': '15mm',
                # 'margin-bottom': '15mm',
                # 'margin-left': '15mm',
                # 'encoding': 'UTF-8',
                # 'no-outline': None,
                # 'enable-local-file-access': None,
                # 'quiet': ''  # Suppress wkhtmltopdf warnings
            # }
            
            # # Convert HTML to PDF
            # # Replace font path placeholder with actual game directory
            # full_html = full_html.replace('GAME_DIR_PLACEHOLDER', self.game_directory.replace('\\', '/'))
            # pdfkit.from_string(full_html, str(pdf_filename), options=options, configuration=config)
            
            # log_message(LOGGER, f"  ✓ PDF exported: {pdf_filename}")
            # return True
            
        # except Exception as e:
            # log_message(LOGGER, f"  ⚠️  PDF export failed: {e}")
            # return False
    
    def process_all_campaigns(self):
        """Process all campaigns and generate events"""
        log_message(LOGGER, "="*70)
        log_message(LOGGER, "IL-2 CAMPAIGN EVENTS GENERATOR")
        log_message(LOGGER, "="*70)

        self.reload_mission_dates()
        
        # Reload popup state from disk (in case it was modified by reset checker)
        self.popup_seen = load_popup_seen(POPUP_SEEN_FILE)
        popup_state_missing = (not POPUP_SEEN_FILE.exists()) or (not self.popup_seen)
        log_message(LOGGER, f"[popups] Reloaded state: {len(self.popup_seen)} campaigns")
        
        # Detect which campaigns have new missions since last run
        campaigns_with_changes = self._get_campaigns_with_new_missions()
        
        results = {}
        files_updated = 0
        
        for campaign_name in self.save_data.keys():
            # Skip if excluded (WW1) - case-insensitive lookup
            campaign_name_lower = campaign_name.lower()
            if campaign_name_lower in self.mission_dates_lower:
                _, mission_data = self.mission_dates_lower[campaign_name_lower]
                if mission_data.get('excluded'):
                    log_message(LOGGER, f"\nSkipping {campaign_name} (excluded: WW1)")
                    continue
            
            # ============================================================
            # Rank scaling factor change detection
            # ============================================================
            # Check if rank scaling factor changed (increased) and cleanup invalid promotions
            current_factor = 1.0  # Default
            if campaign_name_lower in self.mission_dates_lower:
                _, mission_data = self.mission_dates_lower[campaign_name_lower]
                country = mission_data.get('country')
                
                if country and country in self.config.get('ranks', {}):
                    # Get required data for rank scaling check
                    ranks = self.config['ranks'][country]
                    current_factor = self.get_rank_scaling_factor(campaign_name)
                    
                    # Only do cleanup check if campaign already exists in popup_seen
                    if campaign_name in self.popup_seen:
                        # Calculate total score from campaign data
                        campaign_data = self.save_data.get(campaign_name, {})
                        per_mission_stats = campaign_data.get('characterStatisticsByFileName', {})
                        total_score = sum(int(stats.get('score', 0)) for stats in per_mission_stats.values())
                        
                        # Get starting rank offset
                        starting_rank_offset = 0
                        if campaign_name in self.mission_dates:
                            starting_rank_offset = self.mission_dates[campaign_name].get('starting_rank_offset', 0)
                        
                        # Check and cleanup if needed
                        self.popup_seen, scaling_changed = check_and_cleanup_rank_scaling(
                            campaign_name=campaign_name,
                            current_factor=current_factor,
                            ranks=ranks,
                            total_score=total_score,
                            starting_rank_offset=starting_rank_offset,
                            popup_seen_data=self.popup_seen,
                            logger_instance=LOGGER
                        )
                        
                        if scaling_changed:
                            save_popup_seen(POPUP_SEEN_FILE, self.popup_seen)
            
            events = self.generate_events_for_campaign(campaign_name)
            
            # ============================================================
            # Popups: detect, defer, or show
            # ============================================================
            baseline_synced = False
            if self.enable_popups and events and popup_state_missing and campaign_name not in self.popup_seen:
                keys_now = [make_event_key(ev) for ev in events]
                keys_now_set = set(keys_now)
                # Use set_seen_keys to handle new format properly, include scale factor
                self.popup_seen = set_seen_keys(self.popup_seen, campaign_name, sorted(keys_now_set), current_factor)
                save_popup_seen(POPUP_SEEN_FILE, self.popup_seen)
                log_message(LOGGER, f"[popups] {campaign_name}: initial sync ({len(keys_now_set)} events)")
                baseline_synced = True

            # CRITICAL: Only process popups for campaigns that changed THIS run
            if (
                self.enable_popups
                and events
                and campaign_name in campaigns_with_changes
                and not baseline_synced
            ):
                keys_now = [make_event_key(ev) for ev in events]
                keys_now_set = set(keys_now)

                # Use get_seen_keys to handle both old and new format
                campaign_seen = set(get_seen_keys(self.popup_seen, campaign_name))
                new_keys = keys_now_set - campaign_seen

                if new_keys:
                    if self.show_popups and is_il2_running():
                        # show popups IMMEDIATELY!
                        new_events = [ev for ev in events if make_event_key(ev) in new_keys]
                        log_message(LOGGER, f"[popups] {campaign_name}: {len(new_events)} new event(s) - SHOWING NOW!")

                        # Build country map for this popup
                        campaign_country_map = {}
                        campaign_name_lower = campaign_name.lower()
                        if campaign_name_lower in self.mission_dates_lower:
                            _, mission_data = self.mission_dates_lower[campaign_name_lower]
                            country = mission_data.get('country')
                            if country:
                                campaign_country_map[campaign_name] = country
                                campaign_country_map[campaign_name_lower] = country
                        
                        # Show popups RIGHT NOW (before any file writing!)
                        from popups_min import show_event_popups
                        popup_list = [(campaign_name, ev) for ev in new_events]
                        show_event_popups(
                            popup_list,
                            game_directory=self.game_directory,
                            campaign_country_map=campaign_country_map,
                            duration_seconds=5
                        )

                        # mark as seen AFTER popup
                        self.popup_seen = set_seen_keys(self.popup_seen, campaign_name, sorted(campaign_seen | new_keys))
                        save_popup_seen(POPUP_SEEN_FILE, self.popup_seen)
                    else:
                        log_message(LOGGER, 
                            f"[popups] deferred ({len(new_keys)}) "
                            f"(show_popups={self.show_popups}), il2_running={is_il2_running()})"
                        )
            elif (
                self.enable_popups
                and events
                and campaign_name not in campaigns_with_changes
                and not baseline_synced
            ):    
                # Campaign has events but didn't change - skip popup processing
                log_message(LOGGER, f"[popups] {campaign_name}: skipped (no changes detected)")

            
            if events:
                # Get country (case-insensitive)
                if campaign_name_lower in self.mission_dates_lower:
                    _, mission_data = self.mission_dates_lower[campaign_name_lower]
                    country = mission_data.get('country')
                else:
                    country = None
                
                # Generate Events HTML
                events_html = self.generate_events_html(events, country)
                
                # Generate Debriefings HTML (if available)
                completed_missions = list(self.save_data[campaign_name].get('completedMissionsByFileName', {}).keys())
                debriefings_html = ""
                debriefings = {}
                
                if self.log_processor and completed_missions:
                    log_message(LOGGER, f"  Generating debriefings for {len(completed_missions)} mission(s)...")
                    debriefings_html, debriefings = self.generate_debriefings_html(campaign_name, completed_missions)
                
                # Combine: Debriefings BEFORE Events
                if debriefings_html:
                    combined_html = debriefings_html + "\n" + events_html
                else:
                    combined_html = events_html
                
                results[campaign_name] = {
                    'country': country,
                    'events': events,
                    'debriefings_html': debriefings_html,
                    'events_html': events_html,
                    'html': combined_html
                }
                
                # Update the campaign info file
                if self.update_campaign_info_file(campaign_name, combined_html):
                    files_updated += 1
                
                # Export to PDF (only if campaign has completed missions)
                if completed_missions and not self.dry_run:
                    # Calculate cumulative stats from campaigns_decoded.json
                    cumulative_stats = None
                    try:
                        with open(CAMPAIGNS_DECODED_FILE, 'r', encoding='utf-8') as f:
                            decoded_data = json.load(f)
                            if campaign_name in decoded_data:
                                stats = decoded_data[campaign_name].get('characterStatisticsByFileName', {})
                                # Get the latest mission stats (highest mission number)
                                if stats:
                                    latest_mission = max(stats.keys(), key=lambda x: int(x) if x.isdigit() else 0)
                                    cumulative_stats = stats.get(latest_mission, {})
                    except (FileNotFoundError, json.JSONDecodeError, KeyError):
                        cumulative_stats = None
                    
                    # *** CRITICAL: Switch to PDF mode before regenerating debriefings ***
                    self.set_mode("pdf")
                    
                    # Regenerate debriefings in PDF mode (with Combat Results instead of Flight Log)
                    log_message(LOGGER, f"  Regenerating debriefings in PDF mode...")
                    debriefings_html_pdf, debriefings_pdf = self.generate_debriefings_html(campaign_name, completed_missions)
                    
                    # Generate PDF-specific HTML with base64-embedded images
                    events_html_pdf = self.generate_events_html(events, country, for_pdf=True)
                    
                    # Combine debriefings + events for PDF
                    if debriefings_html_pdf:
                        combined_html_pdf = debriefings_html_pdf + "\n" + events_html_pdf
                    else:
                        combined_html_pdf = events_html_pdf
                    
                    # Generate campaign summary (PDF only!)
                    # Use the PDF debriefings we just generated
                    summary_html = self.generate_campaign_summary_html(campaign_name, events, debriefings_pdf, country, cumulative_stats, decoded_data.get(campaign_name) if decoded_data else None)
                    
                    # Add summary at the end
                    if summary_html:
                        combined_html_pdf += "\n" + summary_html
                    
                    self.export_campaign_to_pdf(campaign_name, combined_html_pdf)
                    
                    # *** CRITICAL: Switch back to ingame mode for subsequent campaigns ***
                    self.set_mode("ingame")
        
        # Save results
        with open(CAMPAIGN_EVENTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        # Save current campaign completion state for next run
        # This enables filtering popups to only changed campaigns
        self._save_campaign_completion_state()
        
        log_message(LOGGER, f"\n{'='*70}")
        log_message(LOGGER, f"COMPLETE!")
        log_message(LOGGER, f"{'='*70}")
        log_message(LOGGER, f"Generated events for {len(results)} campaigns")
        log_message(LOGGER, f"Updated {files_updated} campaign info files")
        log_message(LOGGER, f"Results saved to: {CAMPAIGN_EVENTS_FILE}")
        log_message(LOGGER, f"PDF reports saved to: {BASE_DIR / 'reports'}")
        
        # Show sample for kerch if available
        if 'kerch' in results:
            log_message(LOGGER, f"\n{'='*70}")
            log_message(LOGGER, "SAMPLE OUTPUT (kerch):")
            log_message(LOGGER, f"{'='*70}")
            log_message(LOGGER, results['kerch']['html'])
        
        # NOTE: Popups are now shown IMMEDIATELY when events are detected
        # (see loop above - no longer deferred to end of processing)
        
        return results


def main(args=None, dry_run: bool = None, campaign: str = None, show_popups:  bool = None, test_popups:  bool = False) -> bool:
    """
    Main entry point
    
    Args: 
        dry_run: If True, don't modify files (overrides CLI arg)
        campaign: Process only this campaign (overrides CLI arg)
        show_popups: Show promotion/award popups (overrides CLI arg)
        test_popups:  Show test popup sequence
        
    Returns: 
        True if successful, False otherwise
        
    Note: If parameters are None, CLI arguments are used. 
          If parameters are provided, they override CLI arguments.
    """
    parser = argparse.ArgumentParser(
        description='IL-2 Campaign Progress Tracker - Event Generator'
    )
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without actually modifying files')
    parser.add_argument('--campaign', type=str, help='Only process specific campaign (e.g., kerch)')
    parser.add_argument('--show-popups', action='store_true', help='Show promotion/award popups (when IL-2 is running)')
    parser.add_argument('--test-popups', action='store_true', help='Show test popup sequence (does not modify seen state)')
    parser.add_argument('--auto', action='store_true', help='Run in auto mode (no user input)')

    # ✅ Parse CLI args OR provided args list
    try:
        parsed_args = parser.parse_args(args if args is not None else None)
    except SystemExit:
        parsed_args = argparse.Namespace(
            dry_run=False,
            campaign=None,
            show_popups=False,
            test_popups=False,
            auto=False
        )
    
    # ✅ Override with function parameters if explicitly set
    if dry_run is not None:
        parsed_args.dry_run = dry_run
    if campaign is not None:
        parsed_args.campaign = campaign
    if show_popups is not None:
        parsed_args.show_popups = show_popups
    if test_popups:
        parsed_args.test_popups = test_popups

    # --- Logging & Debug Info ---
    log_message(LOGGER, f"[step3] AUTO mode     = {parsed_args.auto}")
    log_message(LOGGER, f"[step3] SHOW_POPUPS   = {parsed_args.show_popups}")
    log_message(LOGGER, f"[step3] DRY_RUN       = {parsed_args.dry_run}")

    if parsed_args.auto:
        log_message(LOGGER, "⚙️ Running in AUTO mode (no user interaction).")
    
    generator = EventGenerator(
        dry_run=parsed_args.dry_run,
        show_popups=parsed_args.show_popups,
    )
    
    # Test popups (no mission flight needed)
    if parsed_args.test_popups:
        from popups_min import show_event_popups

        # Minimal country map; only needed for image folder resolution
        campaign_country_map = {}
        for cname, meta in generator. mission_dates.items():
            if isinstance(meta, dict):
                ctry = meta.get("country")
            else:
                ctry = meta
            if ctry:
                campaign_country_map[cname] = ctry

        # Build a small fake event list (uses real images if they exist)
        test_campaign = next(iter(campaign_country_map.keys()), "kerch")
        test_events = [
            (test_campaign, {
                "type": "promotion",
                "rank": "Feldwebel",
                "image":  "feldwebel. png",
                "mission": "TEST",
                "date":  "1943-11-06"
            }),
            (test_campaign, {
                "type": "award",
                "name": "Iron Cross 2nd Class",
                "image":  "iron_cross_2nd.dds",
                "mission": "TEST",
                "date": "1943-11-06"
            }),
        ]

        log_message(LOGGER, "[popups] TEST MODE: showing 2 popups...")
        show_event_popups(
            test_events,
            game_directory=generator.game_directory,
            campaign_country_map=campaign_country_map,
            duration_seconds=5
        )
        return True  # ✅ Expliziter Rückgabewert

    if parsed_args.campaign:
        log_message(LOGGER, f"Processing single campaign: {parsed_args.campaign}")
        events = generator.generate_events_for_campaign(parsed_args.campaign)
        if events:
            country = generator.mission_dates[parsed_args.campaign].get('country')
            html = generator.generate_events_html(events, country)
            log_message(LOGGER, f"\n{'='*70}\nGenerated HTML:\n{'='*70}\n{html}")
            
            if not parsed_args.dry_run:
                generator.update_campaign_info_file(parsed_args.campaign, html)
        return True
    else:
        # Process all campaigns
        results = generator.process_all_campaigns()
        return len(results) > 0  # ✅ Expliziter Rückgabewert


if __name__ == "__main__":
    
    main()
