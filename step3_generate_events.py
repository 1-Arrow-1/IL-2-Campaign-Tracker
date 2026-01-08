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
from utils.combat_results_html import (
    KILL_MAPPING,
    generate_mission_combat_results_html,
    generate_campaign_summary_combat_results_html,
)
from utils.filesystem import is_file_locked
from utils.popup_state import load_popup_seen, save_popup_seen, make_event_key
from utils.process import is_il2_running
from utils.sorting import smart_mission_sort_key
from utils.logging import get_logger

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
            self.logger.info("[state] No campaign changes detected")
        
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
        """
        Calculate cumulative statistics from characterStatisticsByFileName
        
        Args:
            campaign_stats: characterStatisticsByFileName from save data
            
        Returns:
            Dictionary of cumulative statistics
        """
        cumulative = {
            'missions_completed': 0,
            'total_air_kills': 0,
            'fighter_kills': 0,  # killLightPlane + killMediumPlane
            'bomber_kills': 0,   # killHeavyPlane
            'static_plane_kills': 0,  # killStaticPlane (parked aircraft)
            'air_combat_score': 0,  # fighters + static_planes*0.5 + (bombers*2)
            'ground_kills': 0,
            'tank_kills': 0,
            'ship_kills': 0,
            'total_kills': 0,  # air + ground + ship
            'deaths': 0,
            'total_flight_time': 0,  # seconds
            'flight_hours': 0,
            'aircraft_flown': 0,
            'aircraft_lost': 0,
            'takeoffs': 0,
            'landings': 0,
            'total_score': 0,
            'air_kill_score': 0,
            'ground_kill_score': 0,
            'ship_kill_score': 0,
            'balloons': 0,
            'wounded': 0,
            'sorties': 0,
            'aircraft_crashes': 0,
            'bailouts': 0,
            'kia_mia': 0,
            'wounded_after_mission': 0,
            'mission_stats': {},
            'aircraft_usage': {},
            'outcomes': {
                'survived': 0,
                'kia_mia': 0,
                'wounded': 0,
                'aircraft_lost': 0,
                'bailout': 0,
                'crash': 0
            }
        }
        
        # Campaign-level counters
        total_score = 0
        
        for mission_num, stats in campaign_stats.items():
            if not isinstance(stats, dict):
                self.logger.warning(
                    "    Warning: Stats for mission %s is not a dict: %s = %s",
                    mission_num,
                    type(stats),
                    stats,
                )
                continue
                
            # Skip if mission has no stats
            if not stats:
                continue
            
            # Track mission count
            cumulative['missions_completed'] += 1
            cumulative['sorties'] += 1
            
            # Store stats for this mission
            cumulative['mission_stats'][mission_num] = stats
            
            # Air kills
            air_kills = (
                stats.get('killLightPlane', 0) + 
                stats.get('killMediumPlane', 0) + 
                stats.get('killHeavyPlane', 0)
            )
            cumulative['total_air_kills'] += air_kills
            cumulative['fighter_kills'] += stats.get('killLightPlane', 0) + stats.get('killMediumPlane', 0)
            cumulative['bomber_kills'] += stats.get('killHeavyPlane', 0)
            cumulative['static_plane_kills'] += stats.get('killStaticPlane', 0)
            
            # Air combat score
            air_score = (
                (stats.get('killLightPlane', 0) + stats.get('killMediumPlane', 0)) * 1.0 +
                stats.get('killHeavyPlane', 0) * 2.0 +
                stats.get('killStaticPlane', 0) * 0.5
            )
            cumulative['air_combat_score'] += air_score
            
            # Ground kills
            ground_kills = (
                stats.get('killVehicle', 0) + 
                stats.get('killArtillery', 0) + 
                stats.get('killTank', 0) +
                stats.get('killShip', 0) +
                stats.get('killAirfield', 0) +
                stats.get('killTrain', 0)
            )
            cumulative['ground_kills'] += ground_kills
            cumulative['tank_kills'] += stats.get('killTank', 0)
            cumulative['ship_kills'] += stats.get('killShip', 0)
            
            # Total kills
            cumulative['total_kills'] += (air_kills + ground_kills)
            
            # Deaths and wounds
            if stats.get('death') or stats.get('kia') or stats.get('mialost'):
                cumulative['deaths'] += 1
                cumulative['outcomes']['kia_mia'] += 1
            else:
                cumulative['outcomes']['survived'] += 1
            
            if stats.get('wounded'):
                cumulative['wounded'] += 1
                cumulative['outcomes']['wounded'] += 1
            
            # Aircraft lost
            if stats.get('planeLost'):
                cumulative['aircraft_lost'] += 1
                cumulative['outcomes']['aircraft_lost'] += 1
            
            # Bailout
            if stats.get('bailout'):
                cumulative['bailouts'] += 1
                cumulative['outcomes']['bailout'] += 1
            
            # Crash
            if stats.get('crash'):
                cumulative['aircraft_crashes'] += 1
                cumulative['outcomes']['crash'] += 1
            
            # Flight time
            flight_time = stats.get('flightTime', 0)
            cumulative['total_flight_time'] += flight_time
            
            # Score
            mission_score = stats.get('score', 0)
            total_score += mission_score
            
            # Aircraft usage tracking
            plane = stats.get('plane', 'Unknown')
            if plane not in cumulative['aircraft_usage']:
                cumulative['aircraft_usage'][plane] = {
                    'missions': 0,
                    'kills': 0,
                    'deaths': 0
                }
            
            cumulative['aircraft_usage'][plane]['missions'] += 1
            cumulative['aircraft_usage'][plane]['kills'] += air_kills
            if stats.get('death'):
                cumulative['aircraft_usage'][plane]['deaths'] += 1
        
        # Calculate totals
        cumulative['total_score'] = total_score
        cumulative['flight_hours'] = round(cumulative['total_flight_time'] / 3600, 1)
        
        return cumulative
    
    def calculate_mission_stats(self, mission_data: Dict) -> Dict:
        """
        Calculate mission statistics from a single mission's data
        Uses same logic as calculate_cumulative_stats but for one mission
        """
        stats = {
            'air_kills': 0,
            'fighter_kills': 0,
            'bomber_kills': 0,
            'static_plane_kills': 0,
            'air_combat_score': 0,
            'ground_kills': 0,
            'tank_kills': 0,
            'ship_kills': 0,
            'total_kills': 0,
            'death': False,
            'wounded': False,
            'aircraft_lost': False,
            'bailout': False,
            'crash': False,
            'flight_time': 0,
            'score': 0,
            'plane': 'Unknown',
        }
        
        if not mission_data:
            return stats
        
        # Air kills
        stats['fighter_kills'] = mission_data.get('killLightPlane', 0) + mission_data.get('killMediumPlane', 0)
        stats['bomber_kills'] = mission_data.get('killHeavyPlane', 0)
        stats['static_plane_kills'] = mission_data.get('killStaticPlane', 0)
        stats['air_kills'] = stats['fighter_kills'] + stats['bomber_kills']
        
        # Air combat score
        stats['air_combat_score'] = (
            stats['fighter_kills'] * 1.0 +
            stats['bomber_kills'] * 2.0 +
            stats['static_plane_kills'] * 0.5
        )
        
        # Ground kills
        stats['ground_kills'] = (
            mission_data.get('killVehicle', 0) + 
            mission_data.get('killArtillery', 0) + 
            mission_data.get('killTank', 0) +
            mission_data.get('killShip', 0) +
            mission_data.get('killAirfield', 0) +
            mission_data.get('killTrain', 0)
        )
        stats['tank_kills'] = mission_data.get('killTank', 0)
        stats['ship_kills'] = mission_data.get('killShip', 0)
        
        # Total kills
        stats['total_kills'] = stats['air_kills'] + stats['ground_kills']
        
        # Death, wounds, aircraft lost
        stats['death'] = bool(mission_data.get('death') or mission_data.get('kia') or mission_data.get('mialost'))
        stats['wounded'] = bool(mission_data.get('wounded'))
        stats['aircraft_lost'] = bool(mission_data.get('planeLost'))
        stats['bailout'] = bool(mission_data.get('bailout'))
        stats['crash'] = bool(mission_data.get('crash'))
        
        # Flight time
        stats['flight_time'] = mission_data.get('flightTime', 0)
        
        # Score
        stats['score'] = mission_data.get('score', 0)
        
        # Plane
        stats['plane'] = mission_data.get('plane', 'Unknown')
        
        return stats
    
    def calculate_mission_outcome(self, mission_stats: Dict) -> str:
        """
        Determine outcome category for a mission based on stats
        
        Returns:
            String outcome: "Survived", "Killed/MIA", "Wounded", "Aircraft Lost", "Bailed Out", "Crashed"
        """
        if mission_stats['death']:
            return "Killed/MIA"
        elif mission_stats['wounded']:
            return "Wounded"
        elif mission_stats['aircraft_lost']:
            return "Aircraft Lost"
        elif mission_stats['bailout']:
            return "Bailed Out"
        elif mission_stats['crash']:
            return "Crashed"
        else:
            return "Survived"
    
    def check_rank_promotions(self, country: str, cumulative_stats: Dict) -> List[Dict]:
        """
        Check if player earned any rank promotions based on cumulative stats
        
        Returns:
            List of promotion events
        """
        if country not in self.config['ranks']:
            return []
        
        ranks = self.config['ranks'][country]
        promotions = []
        
        # Get rank thresholds from config
        thresholds = self.config.get('rank_thresholds', {})
        country_thresholds = thresholds.get(country, {})
        
        # Starting rank is based on the number of missions completed
        # (assume player starts at lowest rank)
        current_rank_index = 0
        
        # Calculate promotions based on missions completed
        missions = cumulative_stats['missions_completed']
        
        for i, rank in enumerate(ranks):
            if i == 0:
                # First rank is starting rank, no promotion event
                continue
                
            # Check if there's a threshold for this rank
            rank_name = rank['name']
            threshold = country_thresholds.get(rank_name)
            
            if threshold and missions >= threshold:
                # Promotion earned
                promotion_event = {
                    'type': 'promotion',
                    'rank': rank_name,
                    'image': rank['image'],
                    'mission': 'Initial',  # Will be updated later with actual mission
                    'date': None,  # Will be updated later
                }
                promotions.append(promotion_event)
                current_rank_index = i
        
        return promotions
    
    def check_awards(self, country: str, cumulative_stats: Dict, per_mission_stats: Dict, 
                    completed_missions: List[str], campaign_name: str, 
                    debriefing_wounds: Dict = None) -> List[Dict]:
        """
        Check if player earned any awards based on cumulative stats
        
        Args:
            country: Country name (e.g., "germany")
            cumulative_stats: Cumulative stats for the campaign
            per_mission_stats: Stats for each mission
            completed_missions: List of completed missions
            campaign_name: Campaign name
            debriefing_wounds: Optional dict of wounds from debriefings for accurate count
        
        Returns:
            List of award events
        """
        if country not in self.config['awards']:
            return []
        
        awards_config = self.config['awards'][country]
        awards = []
        
        # Special handling for wounds: prefer debriefing data if available
        wounds = cumulative_stats['wounded']
        if debriefing_wounds:
            wounds = sum(1 for w in debriefing_wounds.values() if w)
        
        # Check each award
        for award in awards_config:
            # Skip if award has no requirements
            if 'requirements' not in award:
                continue
            
            requirements = award['requirements']
            
            # Check if requirements are met
            meets_requirements = True
            
            for req, threshold in requirements.items():
                if req == 'air_kills':
                    if cumulative_stats['total_air_kills'] < threshold:
                        meets_requirements = False
                        break
                elif req == 'ground_kills':
                    if cumulative_stats['ground_kills'] < threshold:
                        meets_requirements = False
                        break
                elif req == 'missions':
                    if cumulative_stats['missions_completed'] < threshold:
                        meets_requirements = False
                        break
                elif req == 'wounds':
                    if wounds < threshold:
                        meets_requirements = False
                        break
                elif req == 'score':
                    if cumulative_stats['total_score'] < threshold:
                        meets_requirements = False
                        break
            
            if meets_requirements:
                # Find first mission where requirements are met
                awarded_mission = self.find_award_mission(
                    award, completed_missions, per_mission_stats, campaign_name, debriefing_wounds
                )
                
                if awarded_mission:
                    award_event = {
                        'type': 'award',
                        'name': award['name'],
                        'image': award['image'],
                        'mission': awarded_mission['mission'],
                        'date': awarded_mission['date']
                    }
                    awards.append(award_event)
                    if award.get('requirements', {}).get('wounds'):
                        cumulative_wounds = award.get('requirements', {}).get('wounds')
                        if cumulative_wounds:
                            self.logger.info("  ✓ Awarded %s after %s wounds", award['name'], cumulative_wounds)
        
        return awards
    
    def find_award_mission(self, award: Dict, completed_missions: List[str], 
                           per_mission_stats: Dict, campaign_name: str,
                           debriefing_wounds: Dict = None) -> Dict:
        """
        Find the mission when an award was earned
        
        Args:
            award: Award config
            completed_missions: List of completed missions
            per_mission_stats: Stats per mission
            campaign_name: Campaign name
            debriefing_wounds: Optional dict of wounds from debriefings
        
        Returns:
            Dict with 'mission' and 'date'
        """
        requirements = award.get('requirements', {})
        
        # Sort missions in chronological order
        # (use smart sorting to handle mission IDs like "1941-07-02a")
        sorted_missions = sorted(completed_missions, key=smart_mission_sort_key)
        
        # Track cumulative stats
        running_stats = {
            'total_air_kills': 0,
            'ground_kills': 0,
            'missions_completed': 0,
            'total_score': 0,
            'wounded': 0
        }
        
        # If using debriefing wounds, track those separately
        wounds_to_date = {}
        if debriefing_wounds:
            wounds_to_date = {mission: False for mission in sorted_missions}
        
        # For each mission, check if award requirements are met
        for mission_num in sorted_missions:
            # Update running stats
            stats = per_mission_stats.get(mission_num, {})
            if not isinstance(stats, dict):
                continue
            
            running_stats['missions_completed'] += 1
            running_stats['total_air_kills'] += (
                stats.get('killLightPlane', 0) + 
                stats.get('killMediumPlane', 0) + 
                stats.get('killHeavyPlane', 0)
            )
            running_stats['ground_kills'] += (
                stats.get('killVehicle', 0) + 
                stats.get('killArtillery', 0) + 
                stats.get('killTank', 0) +
                stats.get('killShip', 0) +
                stats.get('killAirfield', 0) +
                stats.get('killTrain', 0)
            )
            running_stats['total_score'] += stats.get('score', 0)
            
            # Update wounds
            if debriefing_wounds and mission_num in debriefing_wounds:
                if debriefing_wounds[mission_num]:
                    running_stats['wounded'] += 1
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
            self.logger.warning("  Warning: No mission dates found for %s", campaign_name)
            return []
        
        # Get original campaign name and data from mission_dates
        original_name, mission_data = self.mission_dates_lower[campaign_name_lower]
        country = mission_data.get('country')
        if not country:
            self.logger.warning("  Warning: No country detected for %s", campaign_name)
            return []
        
        self.logger.info("Processing: %s (%s)", campaign_name, country)
        self.logger.info("  Missions completed: %s", len(completed))
        
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
                    self.logger.info(
                        "  Debriefings loaded: %s missions, %s wounded",
                        len(debriefings),
                        wound_count,
                    )
            except Exception as e:
                self.logger.warning("  Warning: Could not load debriefings: %s", e)
        
        try:
            # Calculate statistics
            per_mission_stats = campaign_data.get('characterStatisticsByFileName', {})
            cumulative_stats = self.calculate_cumulative_stats(per_mission_stats)
            
            self.logger.info("  Total score: %s", cumulative_stats['total_score'])
            self.logger.info("  Air kills: %s", cumulative_stats['total_air_kills'])
            self.logger.info("  Air combat score: %s", cumulative_stats['air_combat_score'])
            
            # Show rank scaling info
            scale_factor = self.get_rank_scaling_factor(campaign_name)
            if scale_factor != 1.0:
                mission_count = len(completed)
                self.logger.info(
                    "  Rank scaling: %sx (campaign length: %s missions)",
                    scale_factor,
                    mission_count,
                )
            
            # Sort completed missions chronologically
            completed_missions = sorted(completed.keys(), key=smart_mission_sort_key)
            
            # Check rank promotions
            promotions = self.check_rank_promotions_v2(
                campaign_name, country, per_mission_stats, completed_missions
            )
            
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
            
            self.logger.info(
                "  Generated %s events (%s promotions, %s awards)",
                len(events),
                len(promotions),
                len(awards),
            )
            
            return events
            
        except Exception as e:
            self.logger.error("  ERROR in %s: %s", campaign_name, e)
            self.logger.exception("Event generation failed", exc_info=True)
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
                self.logger.warning("  Warning: Invalid rank_scaling bracket format: '%s'", bracket_str)
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
        
        # Add initial rank event (for display)
        promotions.append({
            'type': 'promotion',
            'rank': ranks[current_rank_index]['name'],
            'image': ranks[current_rank_index]['image'],
            'mission': 'Initial',
            'date': None,
            'score': 0
        })
        
        for mission_num in missions:
            stats = per_mission_stats.get(mission_num, {})
            if not isinstance(stats, dict):
                continue
            
            # Calculate total score (use configured score_key, fallback to 'score')
            score_key = self.config.get('score_key', 'score')
            mission_score = stats.get(score_key, stats.get('score', 0))
            running_score += mission_score
            
            # Check if next rank is earned
            if current_rank_index + 1 < len(ranks):
                next_rank = ranks[current_rank_index + 1]
                required_score = next_rank.get('score', 0)
                
                if running_score >= required_score:
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
                    self.logger.warning("  ⚠️  Image not found: %s (also tried .dds)", full_path)
                    return image_path
            else:
                self.logger.warning("  ⚠️  Image not found: %s", full_path)
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
                    self.logger.warning("  ⚠️  PIL not available, cannot convert DDS: %s", full_path.name)
                    return image_path
                except Exception as e:
                    self.logger.warning("  ⚠️  Failed to convert DDS %s: %s", full_path.name, e)
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
                        self.logger.warning("  ⚠️  PIL not available, cannot rotate image: %s", full_path.name)
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
                        self.logger.warning("  ⚠️  Failed to rotate image %s: %s", full_path.name, e)
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
            self.logger.warning("  ⚠️  Failed to convert image %s: %s", image_path, e)
            return image_path
    
    def rank_needs_rotation(self, event: Dict, country: str, country_folder: str = None) -> bool:
        """
        Check if rank image needs rotation for proper display
        
        Args:
            event: Event dict with rank info
            country: Country name
            country_folder: Optional country folder override
            
        Returns:
            True if image should be rotated
        """
        if event.get('type') != 'promotion':
            return False
        
        rank_name = event.get('rank', '').lower()
        
        # Handle country-specific cases
        if country_folder is None:
            country_folder = self.get_country_folder(country)
        
        # Define rotation rules by country/rank
        # (Some rank insignias need 90° rotation in PDF)
        rotation_rules = {
            'germany': ['leutnant', 'oberleutnant', 'hauptmann', 'major', 'oberstleutnant', 'oberst'],
            'russia': ['mld', 'lt', 'st lt', 'capt', 'maj', 'lt col', 'col'],
            'uk': ['p/o', 'f/o', 'flt lt', 'sqn ldr', 'wing cdr'],
            'usa': ['2nd lt', '1st lt', 'capt', 'maj', 'lt col', 'col'],
        }
        
        # Check if this rank needs rotation
        for country_key, ranks in rotation_rules.items():
            if country_key in country_folder.lower():
                for rank in ranks:
                    if rank in rank_name:
                        return True
        
        return False
    
    def format_event_html(self, event: Dict, country: str, for_pdf: bool = False) -> str:
        """
        Format an event as HTML with image, including rotation if needed for PDF
        
        Args:
            event: Event dict
            country: Country name
            for_pdf: If True, use PDF formatting
        """
        # Determine image path
        if event['type'] == 'promotion':
            image_path = f"CampaignRanksAwards/{self.get_country_folder(country)}/{event['image']}"
        else:
            image_path = f"CampaignRanksAwards/{self.get_country_folder(country)}/{event['image']}"
        
        # Determine if image needs rotation
        rotate = False
        if for_pdf and event['type'] == 'promotion':
            rotate = self.rank_needs_rotation(event, country)
        
        # Convert image to base64 for PDF
        if for_pdf:
            image_src = self.image_to_base64(image_path, rotate=rotate)
        else:
            image_src = image_path
        
        # Format date
        if event['mission'] == 'Initial':
            # Use campaign start date if available
            campaign_date = self.get_campaign_start_date(country)
            if campaign_date:
                try:
                    date_obj = datetime.strptime(campaign_date, '%Y-%m-%d')
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
            self.logger.debug("DEBUG HTML: %s", result[:150])  # First 150 chars
        
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
                    self.logger.info("  ✓ Loaded combat data for '%s'", campaign_name)
                else:
                    # Try case-insensitive match
                    campaign_name_lower = campaign_name.lower()
                    for key, value in all_decoded.items():
                        if key.lower() == campaign_name_lower:
                            decoded_data = value
                            self.logger.info(
                                "  ✓ Loaded combat data for '%s' (matched as '%s')",
                                campaign_name,
                                key,
                            )
                            break
                    
                    if not decoded_data:
                        self.logger.warning(
                            "  ⚠️  Warning: No decoded data found for campaign '%s'",
                            campaign_name,
                        )
                        self.logger.warning(
                            "      Available campaigns in decoded file: %s",
                            ", ".join(all_decoded.keys()),
                        )
            else:
                self.logger.warning("  ⚠️  Warning: campaigns_decoded.json not found at: %s", decoded_path)
        
        html_lines = ["<b>Mission Debriefings</b><br>", "<br>"]
        
        # Sort missions in order
        sorted_missions = sorted(debriefings.keys(), key=smart_mission_sort_key)
        
        for mission_id in sorted_missions:
            data = debriefings[mission_id]
            
            self.logger.info("  Processing debriefing for Mission %s...", mission_id)
            
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
                summary_parts.append(f"Aircraft Damage: {aircraft_dmg}%")
            if pilot_dmg > 0:
                summary_parts.append(f"Pilot Damage: {pilot_dmg}%")
            
            # Start time
            if mission_start_time:
                summary_parts.append(f"Start Time: {mission_start_time}")
            
            html_lines.append(f"<b>{' | '.join(summary_parts)}</b><br>")
            html_lines.append(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━<br>")
            
            # Combat results for this mission (if in PDF mode)
            if self.mode == "pdf":
                # Generate combat results HTML (use decoded data if available)
                combat_html = generate_mission_combat_results_html(
                    data,
                    decoded_data,
                    mission_id,
                    KILL_MAPPING,
                    self.game_directory
                )
                if combat_html:
                    html_lines.append("<br>")
                    html_lines.append(combat_html)
                    html_lines.append("<br>")
            
            # Player events
            html_lines.append("<b>EVENTS</b><br>")
            
            # List events (truncate if too many)
            events = data.get('events', [])
            if events:
                # Show up to 25 events (most important)
                for event in events[:25]:
                    time = event.get('time', '')
                    event_type = event.get('type', event.get('event', ''))
                    target = event.get('target', '')
                    altitude = event.get('altitude')
                    damage = event.get('damage')
                    
                    if event_type == "Kill":
                        details = f" (Alt: {altitude}m)" if altitude else ""
                        html_lines.append(f"{time}  {target} destroyed{details}<br>")
                    elif event_type == "Damage Taken":
                        # Skip damage events if mission ended with bailout (too many)
                        if "Bailout" in status:
                            continue
                        html_lines.append(f"{time}  Hit by {target}<br>")
                    elif event_type in ["Takeoff", "Landing", "Crash", "Bailout"]:
                        html_lines.append(f"{time}  {event_type}<br>")
                    else:
                        html_lines.append(f"{time}  {event_type}<br>")
            
            # Summary
            html_lines.append("<br>")
            html_lines.append("<b>SUMMARY</b><br>")
            
            # Key stats
            stats = data['summary']
            summary_lines = []
            
            # Add key summary stats
            if stats.get('player_kills'):
                summary_lines.append(f"Enemy aircraft destroyed: {stats['player_kills']}")
            if stats.get('player_ground_kills'):
                summary_lines.append(f"Ground targets destroyed: {stats['player_ground_kills']}")
            if stats.get('player_assists'):
                summary_lines.append(f"Assists: {stats['player_assists']}")
            
            # Add damage summary
            if pilot_dmg > 0:
                summary_lines.append(f"Pilot damage: {pilot_dmg}%")
            if aircraft_dmg > 0:
                summary_lines.append(f"Aircraft damage: {aircraft_dmg}%")
            
            # Add flight time
            flight_time = stats.get('flight_time', '')
            if flight_time:
                summary_lines.append(f"Flight time: {flight_time}")
            
            # Add mission result
            mission_result = stats.get('mission_result', '')
            if mission_result:
                summary_lines.append(f"Mission result: {mission_result}")
            
            # Add final state
            final_state = stats.get('final_state', '')
            if final_state:
                summary_lines.append(f"Final state: {final_state}")
            
            # Add summary lines
            for line in summary_lines:
                html_lines.append(f"• {line}<br>")
            
            # Add flight log for non-PDF mode (in-game display)
            if self.mode != "pdf":
                html_lines.append("<br>")
                html_lines.append("<b>FLIGHT LOG</b><br>")
                flight_log = data.get('flight_log', [])
                if flight_log:
                    # Show up to 10 log entries
                    for log_entry in flight_log[:10]:
                        html_lines.append(f"{log_entry}<br>")
            
            # End of mission box
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
        Update campaign info.locale=eng.txt with Events section
        Uses re.sub for robust removal of ALL tracker content (including duplicates)
        """
        if not self.game_directory:
            self.logger.error("  Error: No game directory configured")
            return False
        
        info_file = Path(self.game_directory) / "data" / "Campaigns" / campaign_name / "info.locale=eng.txt"
        
        if not info_file.exists():
            self.logger.warning("  Warning: Info file not found: %s", info_file)
            self.logger.info("  (This is normal if campaign hasn't been started)")
            return False
        
        if self.dry_run:
            self.logger.info("  [DRY RUN] Would update: %s", info_file)
            return True
        
        try:
            # Backup once
            backup_file = info_file.with_suffix('.txt.backup')
            if not backup_file.exists():
                shutil.copy(info_file, backup_file)
                self.logger.info("  Created backup: %s", backup_file.name)
            
            raw = info_file.read_bytes()
            cleaned, detected_encoding, original = decode_and_clean_info_locale(raw)
            removed = len(original) - len(cleaned)
            if removed > 0:
                self.logger.info("  ✂️  Removed %s chars of old tracker content", removed)
            else:
                self.logger.info("  ℹ️  No old tracker sections (first run)")
            
            # Remove excessive <u> tags from description
            u_count = cleaned.count('<u>')
            if u_count > 3:
                self.logger.info("  🧹 Cleaning %s <u> tags from description...", u_count)
                # Find section headers: <u>text</u><br>
                headers = re.findall(r'<u>([^<]+)</u><br>', cleaned)
                # Remove all <u> tags
                cleaned = cleaned.replace('<u>', '').replace('</u>', '')
                # Re-add as <b> for headers
                for h in headers:
                    cleaned = cleaned.replace(f'{h}<br>', f'<b>{h}</b><br>', 1)
                self.logger.info("  ✓ Converted headers to bold")
            
            # Build final content
            updated = cleaned + '<br><br>' + events_html
            
            # ====================================================================
            # VERIFICATION: Count sections in final content
            # ====================================================================
            matches = list(re.finditer(TRACKER_SECTION_HEADER_PATTERN, updated, re.IGNORECASE))
            
            if len(matches) > 2:
                self.logger.warning(
                    "  ⚠️  WARNING: %s sections in final content (expected 2)!",
                    len(matches),
                )
                self.logger.warning("     Positions: %s", [m.start() for m in matches])
                self.logger.warning("     Found: %s", [m.group() for m in matches])
            elif len(matches) == 2:
                self.logger.info("  ✓ Verified: 2 sections (Debriefings + Events)")
            else:
                self.logger.info("  ℹ️  %s section(s) found", len(matches))
            
            # Write with original encoding
            with open(info_file, "w", encoding=detected_encoding, newline="") as f:
                f.write(updated)
            
            self.logger.info(
                "  ✅ Updated: %s (%s chars, %s)",
                info_file.name,
                len(updated),
                detected_encoding,
            )
            return True
            
        except Exception as e:
            self.logger.error("  ❌ Error: %s", e)
            self.logger.exception("Failed to update campaign info file", exc_info=True)
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
            self.logger.warning("  ⚠️  Could not read campaign name: %s", e)
        
        return campaign_name
    
    def generate_campaign_summary_html(self, campaign_name: str, events: List[Dict], debriefings: Dict, 
                                        country: str, cumulative_stats: Dict, decoded_data: dict = None) -> str:
        """
        Generate campaign summary statistics for PDF
        
        Args:
            campaign_name: Campaign folder name
            events: List of events
            debriefings: Dict of debriefings data
            country: Country name
            cumulative_stats: Cumulative stats
            decoded_data: Optional decoded data for additional stats
        
        Returns:
            HTML string
        """
        # Placeholder for campaign summary HTML (implementation omitted for brevity)
        # ...
        return ""

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
            self.logger.info("  ℹ️  PDF export skipped: pdfkit not installed")
            self.logger.info("      Install with: pip install pdfkit")
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
            self.logger.info("  ℹ️  PDF export skipped: wkhtmltopdf not found")
            self.logger.info("      Download from: https://wkhtmltopdf.org/downloads.html")
            return False
        
        # ✅ Create reports directory if it doesn't exist
        reports_dir = BASE_DIR / 'reports'
        try:
            reports_dir.mkdir(exist_ok=True)
        except Exception as e:
            self.logger.warning("  ⚠️  Could not create reports directory: %s", e)
            return False
        
        # Get campaign display name from info file
        campaign_display_name = self.get_campaign_display_name(campaign_name)
        
        # Clean campaign name for filename (remove special chars)
        safe_name = safe_campaign_filename(campaign_name)
        pdf_filename = reports_dir / f"{safe_name}_Report.pdf"

        # If the target PDF is open/locked, write a fallback instead of failing
        if is_file_locked(pdf_filename):
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            fallback = reports_dir / f"{safe_name}_Report_LOCKED_{ts}.pdf"
            self.logger.warning("  ⚠️  PDF is open/locked. Writing fallback: %s", fallback.name)
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
                
                self.logger.info("  ✓ PDF exported: %s", pdf_filename)
                return True
                
            except Exception as pdf_error:
                # ✅ IMPROVED: More specific error handling
                self.logger.warning("  ⚠️  PDF conversion failed: %s", pdf_error)
                self.logger.info("      Campaign data is still saved in JSON/HTML format")
                
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
                    self.logger.info("  ℹ️  HTML fallback saved: %s", html_fallback)
                except Exception as html_error:
                    self.logger.warning("  ⚠️  Could not save HTML fallback: %s", html_error)
                
                return False
            
        except Exception as e:
            # ✅ IMPROVED: Catch any other errors gracefully
            self.logger.error("  ❌ PDF export error: %s", e)
            self.logger.info("      This is not critical - campaign data is still processed")
            
            # ✅ Try to save debug info
            try:
                import traceback
                error_log = reports_dir / f"{safe_name}_PDF_ERROR.log"
                with open(error_log, 'w', encoding='utf-8') as f:
                    f.write(f"PDF Export Error for {campaign_name}\n")
                    f.write(f"Time: {datetime.now()}\n\n")
                    f.write(traceback.format_exc())
                self.logger.info("  ℹ️  Error details saved to: %s", error_log)
            except Exception:
                pass
            
            return False
    
    def process_all_campaigns(self):
        """Process all campaigns and generate events"""
        self.logger.info("=" * 70)
        self.logger.info("IL-2 CAMPAIGN EVENTS GENERATOR")
        self.logger.info("=" * 70)

        self.reload_mission_dates()
        
        # Reload popup state from disk (in case it was modified by reset checker)
        self.popup_seen = load_popup_seen(POPUP_SEEN_FILE)
        popup_state_missing = (not POPUP_SEEN_FILE.exists()) or (not self.popup_seen)
        self.logger.info("[popups] Reloaded state: %s campaigns", len(self.popup_seen))
        
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
                    self.logger.info("Skipping %s (excluded: WW1)", campaign_name)
                    continue
            
            events = self.generate_events_for_campaign(campaign_name)
            
            # ============================================================
            # Popups: detect, defer, or show
            # ============================================================
            baseline_synced = False
            if self.enable_popups and events and popup_state_missing and campaign_name not in self.popup_seen:
                keys_now = [make_event_key(ev) for ev in events]
                keys_now_set = set(keys_now)
                self.popup_seen[campaign_name] = sorted(keys_now_set)
                save_popup_seen(POPUP_SEEN_FILE, self.popup_seen)
                self.logger.info(
                    "[popups] %s: initial sync (%s events)",
                    campaign_name,
                    len(keys_now_set),
                )
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

                campaign_seen = set(self.popup_seen.get(campaign_name, []))
                new_keys = keys_now_set - campaign_seen

                if new_keys:
                    if self.show_popups and is_il2_running():
                        # show popups IMMEDIATELY!
                        new_events = [ev for ev in events if make_event_key(ev) in new_keys]
                        self.logger.info(
                            "[popups] %s: %s new event(s) - SHOWING NOW!",
                            campaign_name,
                            len(new_events),
                        )

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
                        self.popup_seen[campaign_name] = sorted(campaign_seen | new_keys)
                        save_popup_seen(POPUP_SEEN_FILE, self.popup_seen)
                    else:
                        self.logger.info(
                            "[popups] deferred (%s) (show_popups=%s, il2_running=%s)",
                            len(new_keys),
                            self.show_popups,
                            is_il2_running(),
                        )
            elif (
                self.enable_popups
                and events
                and campaign_name not in campaigns_with_changes
                and not baseline_synced
            ):    
                # Campaign has events but didn't change - skip popup processing
                self.logger.info("[popups] %s: skipped (no changes detected)", campaign_name)

            
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
                    self.logger.info(
                        "  Generating debriefings for %s mission(s)...",
                        len(completed_missions),
                    )
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
                    self.logger.info("  Regenerating debriefings in PDF mode...")
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
        
        self.logger.info("=" * 70)
        self.logger.info("COMPLETE!")
        self.logger.info("=" * 70)
        self.logger.info("Generated events for %s campaigns", len(results))
        self.logger.info("Updated %s campaign info files", files_updated)
        self.logger.info("Results saved to: %s", CAMPAIGN_EVENTS_FILE)
        self.logger.info("PDF reports saved to: %s", BASE_DIR / 'reports')
        
        # Show sample for kerch if available
        if 'kerch' in results:
            self.logger.info("=" * 70)
            self.logger.info("SAMPLE OUTPUT (kerch):")
            self.logger.info("=" * 70)
            self.logger.info(results['kerch']['html'])
        
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
    LOGGER.info("[step3] AUTO mode     = %s", parsed_args.auto)
    LOGGER.info("[step3] SHOW_POPUPS   = %s", parsed_args.show_popups)
    LOGGER.info("[step3] DRY_RUN       = %s", parsed_args.dry_run)

    if parsed_args.auto:
        LOGGER.info("⚙️ Running in AUTO mode (no user interaction).")
    
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

        LOGGER.info("[popups] TEST MODE: showing 2 popups...")
        show_event_popups(
            test_events,
            game_directory=generator.game_directory,
            campaign_country_map=campaign_country_map,
            duration_seconds=5
        )
        return True  # ✅ Expliziter Rückgabewert

    if parsed_args.campaign:
        LOGGER.info("Processing single campaign: %s", parsed_args.campaign)
        events = generator.generate_events_for_campaign(parsed_args.campaign)
        if events:
            country = generator.mission_dates[parsed_args.campaign].get('country')
            html = generator.generate_events_html(events, country)
            LOGGER.info("%s\nGenerated HTML:\n%s\n%s", "=" * 70, "=" * 70, html)
            
            if not parsed_args.dry_run:
                generator.update_campaign_info_file(parsed_args.campaign, html)
        return True
    else:
        # Process all campaigns
        results = generator.process_all_campaigns()
        return len(results) > 0  # ✅ Expliziter Rückgabewert


if __name__ == "__main__":
    
    main()