"""
Data loader for Campaign Tracker JSON files.

Responsibilities:
- Load JSON files with error handling
- Cache loaded data with file modification tracking
- Provide type-safe accessors for different data sources

Design:
- Single responsibility: Only concerned with file I/O and caching
- Defensive: Returns empty structures on errors, never crashes
- Observable: Logs all load attempts and failures
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

from utils.formatting import safe_campaign_filename

logger = logging.getLogger(__name__)


class DataLoader:
    """
    Loads and caches Campaign Tracker JSON files.
    
    Thread-safe for read operations (no writes).
    Cache invalidation based on file modification time.
    """
    
    # JSON file names (centralized to avoid magic strings)
    COMPLETION_STATE_FILE = 'campaign_completion_state.json'
    EVENTS_FILE = 'campaign_events.json'
    DECODED_FILE = 'campaigns_decoded.json'
    MISSION_DATES_FILE = 'campaign_mission_dates.json'
    
    def __init__(self, data_dir: Path, enable_cache: bool = True):
        """
        Initialize data loader.
        
        Args:
            data_dir: Directory containing JSON files
            enable_cache: If False, always reload from disk (useful for testing)
        """
        self.data_dir = Path(data_dir)
        self.enable_cache = enable_cache
        
        # Cache: {filename: (data, mtime)}
        self._cache: Dict[str, tuple[Any, float]] = {}
        
        logger.info(f"DataLoader initialized with data_dir={self.data_dir}")
    
    def _load_json(self, filename: str) -> Optional[Any]:
        """
        Load JSON file with caching and error handling.
        
        Args:
            filename: Name of JSON file
        
        Returns:
            Parsed JSON data, or None if file missing/corrupt
        
        Design Decision:
        - Returns None instead of raising exceptions to allow graceful degradation
        - Logs errors for debugging but doesn't crash the application
        """
        filepath = self.data_dir / filename
        
        # Check if file exists
        if not filepath.exists():
            logger.warning(f"JSON file not found: {filepath}")
            return None
        
        try:
            # Get current modification time
            current_mtime = filepath.stat().st_mtime
            
            # Check cache
            if self.enable_cache and filename in self._cache:
                cached_data, cached_mtime = self._cache[filename]
                if current_mtime <= cached_mtime:
                    logger.debug(f"Cache hit: {filename}")
                    return cached_data
            
            # Load from disk
            logger.info(f"Loading JSON: {filepath}")
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Update cache
            if self.enable_cache:
                self._cache[filename] = (data, current_mtime)
            
            return data
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {filepath}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error reading {filepath}: {e}")
            return None
    
    def get_campaign_completion_state(self) -> Dict[str, List[str]]:
        """
        Get campaign completion state.
        
        This is the PRIMARY filter for determining which campaigns to display.
        Only campaigns with non-empty mission lists are considered "active".
        
        Returns:
            Dict mapping campaign_name -> list of completed mission IDs
            Example: {"kerch": ["01", "02"], "moscow_pe2": []}
        """
        data = self._load_json(self.COMPLETION_STATE_FILE)
        if data is None:
            logger.warning("Campaign completion state unavailable - no campaigns will be shown")
            return {}
        
        if not isinstance(data, dict):
            logger.error(f"Invalid completion state format: expected dict, got {type(data)}")
            return {}
        
        return data
    
    def get_campaign_events(self) -> Dict[str, Dict]:
        """
        Get campaign events (awards, promotions, debriefings).
        
        Returns:
            Dict mapping campaign_name -> campaign data
            Structure:
            {
                "kerch": {
                    "country": "ussr",
                    "events": [...],
                    "debriefings_html": "...",
                    "events_html": "...",
                    "html": "..."
                }
            }
        """
        data = self._load_json(self.EVENTS_FILE)
        if data is None:
            logger.warning("Campaign events unavailable")
            return {}
        
        if not isinstance(data, dict):
            logger.error(f"Invalid events format: expected dict, got {type(data)}")
            return {}
        
        return data
    
    def get_campaigns_decoded(self) -> Dict[str, Dict]:
        """
        Get decoded campaign save data (statistics).
        
        Returns:
            Dict mapping campaign_name -> campaign save data
            Structure:
            {
                "kerch": {
                    "characterStatisticsByFileName": {
                        "01": {"score": 150, "planesDestroyed": 2, ...},
                        "02": {...}
                    },
                    "completedMissionsByFileName": {...}
                }
            }
        """
        data = self._load_json(self.DECODED_FILE)
        if data is None:
            logger.warning("Decoded campaign data unavailable")
            return {}
        
        if not isinstance(data, dict):
            logger.error(f"Invalid decoded data format: expected dict, got {type(data)}")
            return {}
        
        return data
    
    def get_campaign_mission_dates(self) -> Dict[str, Any]:
        """
        Get mission metadata (dates, times, aircraft, squadron).
        
        Returns:
            Dict with 'game_directory' key and per-campaign data
            Structure:
            {
                "game_directory": "C:\\...",
                "kerch": {
                    "country": "ussr",
                    "starting_rank_offset": 0,
                    "excluded": false,
                    "01": {
                        "date": "1942.05.05",
                        "time": "09:30",
                        "aircraft": "IL-2 mod.1941",
                        ...
                    }
                }
            }
        """
        data = self._load_json(self.MISSION_DATES_FILE)
        if data is None:
            logger.warning("Mission dates unavailable")
            return {'game_directory': ''}
        
        if not isinstance(data, dict):
            logger.error(f"Invalid mission dates format: expected dict, got {type(data)}")
            return {'game_directory': ''}
        
        return data

    def get_mission_dates_for_campaign(self, campaign_name: str) -> Dict[str, Any]:
        """
        Get mission dates for a specific campaign with case-insensitive lookup.
        
        This method handles the case mismatch between campaign_mission_dates.json
        (which may have mixed-case keys like 'Luftwaffe-WW2-Career-40-45') and
        other files (which use lowercase keys like 'luftwaffe-ww2-career-40-45').
        
        Args:
            campaign_name: Campaign name (case-insensitive)
        
        Returns:
            Campaign mission dates dict, or empty dict if not found
        """
        mission_dates = self.get_campaign_mission_dates()
        
        # Direct lookup first
        if campaign_name in mission_dates:
            return mission_dates[campaign_name]
        
        # Case-insensitive fallback
        campaign_name_lower = campaign_name.lower()
        for key, value in mission_dates.items():
            if key == 'game_directory':
                continue
            if key.lower() == campaign_name_lower:
                logger.debug(f"Case-insensitive match: '{campaign_name}' -> '{key}'")
                return value
        
        return {}
    
    def get_campaigns_with_progress(self) -> List[str]:
        """
        Get list of campaigns that have completed at least one mission.

        This is the filter used for the landing page campaign list.
        WW1 campaigns (excluded=true OR is_ww1=true) are filtered out here.

        Returns:
            List of campaign names with non-empty mission lists
        """
        completion_state = self.get_campaign_completion_state()
        mission_dates = self.get_campaign_mission_dates()

        # Filter out campaigns marked as excluded OR detected as WW1
        excluded_lower = {
            name.lower()
            for name, meta in mission_dates.items()
            if name != "game_directory"
            and isinstance(meta, dict)
            and (meta.get("excluded") or meta.get("is_ww1"))
        }

        campaigns = [
            campaign_name
            for campaign_name, missions in completion_state.items()
            if missions and campaign_name.lower() not in excluded_lower
        ]

        logger.info(f"Found {len(campaigns)} campaigns with progress (excluded {len(excluded_lower)} WW1/excluded)")
        return campaigns

    def is_campaign_excluded(self, campaign_name: str) -> bool:
        """
        Check if a campaign should be hidden from the landing page.

        A campaign is excluded if it has either:
        - excluded=true (explicitly marked)
        - is_ww1=true (detected as WW1 Flying Circus campaign)

        Args:
            campaign_name: Campaign name (case-insensitive)

        Returns:
            True if campaign should be hidden from landing page
        """
        campaign_data = self.get_mission_dates_for_campaign(campaign_name)
        if not campaign_data:
            return False
        return bool(campaign_data.get("excluded") or campaign_data.get("is_ww1"))

    def get_mission_aircraft_map(self, campaign_name: str) -> Dict[str, Dict]:
        """
        Load mission -> aircraft mapping for a campaign.

        Source: reports/{campaign}/mission_aircraft_map.json
        """
        safe_name = safe_campaign_filename(campaign_name)
        cache_path = self.data_dir / 'reports' / safe_name / 'mission_aircraft_map.json'

        if not cache_path.exists():
            logger.warning("mission_aircraft_map.json not found for %s", campaign_name)
            return {}

        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            logger.error("Failed to read mission_aircraft_map.json for %s: %s", campaign_name, exc)
            return {}

        if isinstance(data, dict) and isinstance(data.get('missions'), dict):
            return data['missions']
        if isinstance(data, dict):
            return data
        return {}
    
    def get_campaign_data(self, campaign_name: str) -> Optional[Dict]:
        """
        Get all data for a specific campaign.
        
        Convenience method that aggregates data from all sources.
        
        Args:
            campaign_name: Campaign folder name
        
        Returns:
            Dict with all campaign data, or None if campaign not found
        """
        completion_state = self.get_campaign_completion_state()
        
        if campaign_name not in completion_state:
            logger.warning(f"Campaign not found: {campaign_name}")
            return None
        
        return {
            'completion_state': completion_state.get(campaign_name, []),
            'events': self.get_campaign_events().get(campaign_name, {}),
            'decoded': self.get_campaigns_decoded().get(campaign_name, {}),
            'mission_dates': self.get_mission_dates_for_campaign(campaign_name)
        }
    
    def invalidate_cache(self, filename: Optional[str] = None):
        """
        Invalidate cache for specific file or all files.
        
        Args:
            filename: If provided, only invalidate this file. Otherwise clear all.
        """
        if filename:
            self._cache.pop(filename, None)
            logger.debug(f"Cache invalidated: {filename}")
        else:
            self._cache.clear()
            logger.debug("All cache invalidated")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics (useful for debugging).
        
        Returns:
            Dict with cache hit counts, sizes, etc.
        """
        return {
            'cached_files': list(self._cache.keys()),
            'cache_size': len(self._cache),
            'data_dir': str(self.data_dir),
            'cache_enabled': self.enable_cache
        }
