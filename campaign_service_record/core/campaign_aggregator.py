"""
Campaign data aggregator.

Transforms raw JSON data into UI-ready structures.
Handles all business logic for campaign summary calculations.

Design:
- Single Responsibility: Only concerned with data transformation
- No I/O: Works with pre-loaded data from DataLoader
- Reuses Campaign Tracker utilities for combat calculations
"""

import logging
from typing import Dict, List, Optional, Any
from pathlib import Path

# Import utilities from Campaign Tracker (copied to utils/)
try:
    from utils.combat_results import (
        calculate_kills_from_stats,
        calculate_total_air_kills_weighted,
        KILL_MAPPING
    )
    from utils.sorting import smart_mission_sort_key
except ImportError:
    # Fallback if utils not yet available
    logger = logging.getLogger(__name__)
    logger.warning("Combat results utilities not available")
    
    def calculate_kills_from_stats(stats):
        return {}
    
    def calculate_total_air_kills_weighted(stats):
        return 0.0
    
    def smart_mission_sort_key(mission_id):
        return mission_id
    
    KILL_MAPPING = {}


logger = logging.getLogger(__name__)


class CampaignAggregator:
    """
    Aggregates campaign data from multiple sources into UI-ready structures.
    
    This class implements the business logic for:
    - Campaign list generation (landing page)
    - Campaign detail aggregation (detail page)
    - Summary statistics calculation
    """
    
    def __init__(self, data_loader):
        """
        Initialize aggregator with data loader.
        
        Args:
            data_loader: DataLoader instance
        """
        self.loader = data_loader
        logger.info("CampaignAggregator initialized")
    
    def get_campaign_list(self) -> List[Dict]:
        """
        Get list of all campaigns for landing page.
        
        Returns:
            List of campaign summaries:
            [
                {
                    "name": "kerch",
                    "display_name": "Kerch Peninsula Campaign",
                    "country": "ussr",
                    "missions_completed": 15,
                    "promotions_count": 3,
                    "awards_count": 8,
                    "final_rank": "Senior Sergeant"
                }
            ]
        """
        campaigns = self.loader.get_campaigns_with_progress()
        mission_dates = self.loader.get_campaign_mission_dates()
        events_data = self.loader.get_campaign_events()
        
        result = []
        
        for campaign_name in campaigns:
            try:
                campaign_info = self._get_campaign_list_item(
                    campaign_name,
                    mission_dates,
                    events_data
                )
                if campaign_info:
                    result.append(campaign_info)
            except Exception as e:
                logger.error(f"Error processing campaign {campaign_name}: {e}", exc_info=True)
                # Continue with next campaign (defensive)
        
        # Sort alphabetically by display name
        result.sort(key=lambda x: x['display_name'].lower())
        
        logger.info(f"Generated campaign list with {len(result)} campaigns")
        return result
    
    def _get_campaign_list_item(
        self,
        campaign_name: str,
        mission_dates: Dict,
        events_data: Dict
    ) -> Optional[Dict]:
        """
        Create campaign list item for a single campaign.
        
        Args:
            campaign_name: Campaign identifier
            mission_dates: Mission dates dict (all campaigns)
            events_data: Events dict (all campaigns)
        
        Returns:
            Campaign info dict or None if data insufficient
        """
        # Get completion state
        completion_state = self.loader.get_campaign_completion_state()
        missions_completed = self._ensure_list(
            completion_state.get(campaign_name, []),
            f"completion_state[{campaign_name}]"
        )
        
        if not missions_completed:
            # Should not happen (filtered by get_campaigns_with_progress)
            return None
        
        # Get country
        campaign_dates = mission_dates.get(campaign_name, {})
        country = campaign_dates.get('country', 'unknown')
        
        # Get events
        campaign_events = self._ensure_dict(
            events_data.get(campaign_name, {}),
            f"events[{campaign_name}]"
        )
        events = self._ensure_list(
            campaign_events.get('events', []),
            f"events[{campaign_name}].events"
        )
        
        # Count promotions and awards
        promotions = [e for e in events if e.get('type') == 'promotion']
        awards = [e for e in events if e.get('type') == 'award']
        
        # Get final rank
        final_rank = "Unknown"
        if promotions:
            final_rank = promotions[-1].get('rank', 'Unknown')
        
        return {
            'name': campaign_name,
            'display_name': self._get_display_name(campaign_name, mission_dates),
            'country': country,
            'missions_completed': len(missions_completed),
            'promotions_count': len(promotions),
            'awards_count': len(awards),
            'final_rank': final_rank
        }
    
    def get_campaign_detail(self, campaign_name: str) -> Optional[Dict]:
        """
        Get complete campaign data for detail page.
        
        Args:
            campaign_name: Campaign identifier
        
        Returns:
            Complete campaign data:
            {
                "name": "kerch",
                "display_name": "Kerch Peninsula Campaign",
                "country": "ussr",
                "missions_completed": 15,
                "events": [...],              # Awards & promotions
                "debriefings_html": "...",    # Pre-generated HTML
                "summary": {...}              # Aggregated statistics
            }
        """
        # Check if campaign exists
        completion_state = self.loader.get_campaign_completion_state()
        if campaign_name not in completion_state:
            logger.warning(f"Campaign not found: {campaign_name}")
            return None
        
        completed_missions = self._ensure_list(
            completion_state.get(campaign_name, []),
            f"completion_state[{campaign_name}]"
        )
        
        # Load all data sources
        events_data = self.loader.get_campaign_events()
        decoded_data = self.loader.get_campaigns_decoded()
        mission_dates = self.loader.get_campaign_mission_dates()
        
        # Get campaign-specific data
        campaign_events = self._ensure_dict(
            events_data.get(campaign_name, {}),
            f"events[{campaign_name}]"
        )
        campaign_decoded = self._ensure_dict(
            decoded_data.get(campaign_name, {}),
            f"decoded[{campaign_name}]"
        )
        campaign_dates = self._ensure_dict(
            mission_dates.get(campaign_name, {}),
            f"mission_dates[{campaign_name}]"
        )
        
        # Extract components
        country = campaign_events.get('country') or campaign_dates.get('country', 'unknown')
        events = self._ensure_list(
            campaign_events.get('events', []),
            f"events[{campaign_name}].events"
        )
        debriefings_html = campaign_events.get('debriefings_html', '')
        
        # Calculate summary statistics
        summary = self._calculate_summary(
            campaign_name,
            campaign_decoded,
            completed_missions,
            campaign_dates,
            events
        )
        
        return {
            'name': campaign_name,
            'display_name': self._get_display_name(campaign_name, mission_dates),
            'country': country,
            'missions_completed': len(completed_missions),
            'events': events,
            'debriefings_html': debriefings_html,
            'summary': summary
        }
    
    def _calculate_summary(
        self,
        campaign_name: str,
        decoded_data: Dict,
        completed_missions: List[str],
        mission_dates: Dict,
        events: List[Dict]
    ) -> Dict:
        """
        Calculate campaign summary statistics.
        
        This is the right column of the detail page.
        
        Args:
            campaign_name: Campaign identifier
            decoded_data: Decoded save data for this campaign
            completed_missions: List of completed mission IDs
            mission_dates: Mission metadata for this campaign
            events: List of events (awards, promotions)
        
        Returns:
            Summary dict with:
            - combat_results: Kill statistics
            - missions_stats: Mission counts and flight time
            - aircraft_usage: Aircraft flown with missions/kills
            - career_progression: Ranks and awards
            - timeline: Campaign start/end dates
        """
        summary = {
            'combat_results': {},
            'missions_stats': {},
            'aircraft_usage': {},
            'career_progression': {},
            'timeline': {}
        }
        
        # Get per-mission statistics
        per_mission_stats = decoded_data.get('characterStatisticsByFileName', {})
        if not isinstance(per_mission_stats, dict):
            logger.warning(
                "Invalid per-mission statistics for %s: expected dict, got %s",
                campaign_name,
                type(per_mission_stats)
            )
            return summary
        
        if not per_mission_stats:
            logger.warning(f"No statistics available for {campaign_name}")
            return summary
        
        # Sort missions chronologically
        sorted_missions = sorted(completed_missions, key=smart_mission_sort_key)
        
        # Get cumulative stats from last mission
        if sorted_missions:
            last_mission = sorted_missions[-1]
            cumulative_stats = per_mission_stats.get(last_mission, {})
            if not isinstance(cumulative_stats, dict):
                logger.warning(
                    "Invalid cumulative stats for %s mission %s: expected dict, got %s",
                    campaign_name,
                    last_mission,
                    type(cumulative_stats)
                )
                cumulative_stats = {}
            
            # Calculate kills using Campaign Tracker logic
            summary['combat_results'] = calculate_kills_from_stats(cumulative_stats)
            summary['combat_results']['total_score'] = cumulative_stats.get('score', 0)
        
        # Calculate missions stats
        summary['missions_stats'] = self._calculate_mission_stats(
            sorted_missions,
            per_mission_stats,
            decoded_data
        )
        
        # Calculate aircraft usage
        summary['aircraft_usage'] = self._calculate_aircraft_usage(
            sorted_missions,
            mission_dates,
            per_mission_stats
        )
        
        # Extract career progression
        summary['career_progression'] = self._extract_career_progression(events)
        
        # Calculate timeline
        summary['timeline'] = self._calculate_timeline(
            sorted_missions,
            mission_dates
        )
        
        return summary
    
    def _calculate_mission_stats(
        self,
        missions: List[str],
        per_mission_stats: Dict,
        decoded_data: Dict
    ) -> Dict:
        """
        Calculate mission-level statistics.
        
        Args:
            missions: Sorted list of mission IDs
            per_mission_stats: Stats by mission
            decoded_data: Full decoded data
        
        Returns:
            Dict with mission counts, landing stats, etc.
        """
        total_missions = len(missions)
        
        # Get completed missions data
        completed_by_filename = decoded_data.get('completedMissionsByFileName', {})
        if not isinstance(completed_by_filename, dict):
            completed_by_filename = {}
        
        # Count success/failure (if available)
        successful = sum(
            1 for m in missions
            if completed_by_filename.get(m, {}).get('isSuccess', 0) == 1
        )
        
        return {
            'total_missions': total_missions,
            'successful_missions': successful,
            'success_rate': round(successful / total_missions * 100) if total_missions > 0 else 0,
            # Note: Flight time not stored in save files
            # Would need to parse mission logs for accurate time
            'total_flight_time': 'N/A',
            'average_duration': 'N/A'
        }
    
    def _calculate_aircraft_usage(
        self,
        missions: List[str],
        mission_dates: Dict,
        per_mission_stats: Dict
    ) -> Dict:
        """
        Calculate aircraft usage and kills per aircraft.
        
        Args:
            missions: Sorted list of mission IDs
            mission_dates: Mission metadata
            per_mission_stats: Stats by mission
        
        Returns:
            Dict mapping aircraft name -> {missions, kills}
        """
        aircraft_usage = {}
        
        for mission_id in missions:
            # Get aircraft for this mission
            mission_meta = mission_dates.get(mission_id, {})
            aircraft = mission_meta.get('aircraft', 'Unknown')
            
            # Initialize if not seen
            if aircraft not in aircraft_usage:
                aircraft_usage[aircraft] = {
                    'missions': 0,
                    'kills': 0
                }
            
            aircraft_usage[aircraft]['missions'] += 1
            
            # Calculate kills for this mission
            mission_stats = per_mission_stats.get(mission_id, {})
            mission_kills = self._calculate_mission_kills(mission_stats)
            aircraft_usage[aircraft]['kills'] += mission_kills
        
        # Sort by missions flown (descending)
        sorted_aircraft = sorted(
            aircraft_usage.items(),
            key=lambda x: (x[1]['missions'], x[1]['kills']),
            reverse=True
        )
        
        return dict(sorted_aircraft)
    
    def _calculate_mission_kills(self, mission_stats: Dict) -> int:
        """
        Calculate total kills for a single mission.
        
        Args:
            mission_stats: Statistics for one mission
        
        Returns:
            Total kill count
        """
        if not isinstance(mission_stats, dict):
            return 0

        # Air kills
        air_kills = mission_stats.get('planesDestroyedAir', 0)
        
        # Ground kills (planes destroyed on ground)
        ground_kills = mission_stats.get('planesDestroyed', 0) - air_kills
        
        return air_kills + ground_kills
    
    def _extract_career_progression(self, events: List[Dict]) -> Dict:
        """
        Extract career progression info from events.
        
        Args:
            events: List of all events
        
        Returns:
            Dict with starting rank, final rank, promotions, awards
        """
        promotions = [e for e in events if e.get('type') == 'promotion']
        awards = [e for e in events if e.get('type') == 'award']
        
        starting_rank = "Unknown"
        final_rank = "Unknown"
        
        if promotions:
            starting_rank = promotions[0].get('rank', 'Unknown')
            final_rank = promotions[-1].get('rank', 'Unknown')
        
        return {
            'starting_rank': starting_rank,
            'final_rank': final_rank,
            'promotions_count': len(promotions),
            'awards_count': len(awards),
            'awards_list': [a.get('name', 'Unknown') for a in awards]
        }
    
    def _calculate_timeline(
        self,
        missions: List[str],
        mission_dates: Dict
    ) -> Dict:
        """
        Calculate campaign timeline.
        
        Args:
            missions: Sorted list of mission IDs
            mission_dates: Mission metadata
        
        Returns:
            Dict with first/last mission dates
        """
        if not missions:
            return {
                'first_mission_date': None,
                'last_mission_date': None,
                'duration_days': None
            }
        
        first_mission_id = missions[0]
        last_mission_id = missions[-1]
        
        first_meta = mission_dates.get(first_mission_id, {})
        last_meta = mission_dates.get(last_mission_id, {})
        
        first_date = first_meta.get('date')
        last_date = last_meta.get('date')
        
        # Calculate duration if both dates available
        duration_days = None
        if first_date and last_date:
            try:
                from datetime import datetime
                # Dates in format: "1942.05.05"
                first_dt = datetime.strptime(first_date, '%Y.%m.%d')
                last_dt = datetime.strptime(last_date, '%Y.%m.%d')
                duration_days = (last_dt - first_dt).days
            except:
                pass
        
        return {
            'first_mission_date': first_date,
            'last_mission_date': last_date,
            'duration_days': duration_days
        }
    
    def _get_display_name(self, campaign_name: str, mission_dates: Dict) -> str:
        """
        Get user-friendly campaign display name.
        
        Strategy:
        1. Look for explicit display name in mission_dates
        2. Fallback to formatted folder name
        
        Args:
            campaign_name: Campaign folder name
            mission_dates: Mission dates dict (all campaigns)
        
        Returns:
            User-friendly campaign name
        """
        campaign_data = mission_dates.get(campaign_name, {})
        
        # Check for explicit display name (if Campaign Tracker provides it)
        display_name = campaign_data.get('display_name')
        if display_name:
            return display_name
        
        # Fallback: Format folder name
        # Replace underscores, capitalize words
        formatted = campaign_name.replace('_', ' ').title()
        
        return formatted

    def _ensure_dict(self, value: Any, label: str) -> Dict:
        if isinstance(value, dict):
            return value
        if value is None:
            return {}
        logger.warning("Invalid %s: expected dict, got %s", label, type(value))
        return {}

    def _ensure_list(self, value: Any, label: str) -> List:
        if isinstance(value, list):
            return value
        if value is None:
            return []
        if isinstance(value, dict):
            return list(value.values())
        logger.warning("Invalid %s: expected list, got %s", label, type(value))
        return []
