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
import re
from typing import Dict, List, Optional, Any
from pathlib import Path

# Import utilities from Campaign Tracker (copied to utils/)
try:
    from campaign_service_record.utils.combat_results import (
        calculate_kills_from_stats,
        calculate_total_air_kills_weighted,
        aggregate_kills_from_missions,
        KILL_MAPPING
    )
    from campaign_service_record.utils.sorting import smart_mission_sort_key
    from campaign_service_record.utils.image_utils import build_dds_data_uri
    from campaign_service_record.utils.path_utils import (
        build_award_image_relative_path,
        build_award_large_image_relative_path,
        build_game_asset_url,
        get_game_directory
    )
except ImportError:
    # Fallback if utils not yet available
    logger = logging.getLogger(__name__)
    logger.warning("Combat results utilities not available")
    
    def calculate_kills_from_stats(stats):
        return {}
    
    def calculate_total_air_kills_weighted(stats):
        return 0.0

    def aggregate_kills_from_missions(stats_by_mission):
        return {}
    
    def smart_mission_sort_key(mission_id):
        return mission_id
    
    KILL_MAPPING = {}

    def build_award_image_relative_path(country, image_name, event_date):
        return ''

    def build_award_large_image_relative_path(country, image_name, event_date):
        return ''

    def build_game_asset_url(relative_path):
        return ''

    def get_game_directory(mission_dates):
        return ''

    def build_dds_data_uri(game_directory, relative_path):
        return None



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
        
        # Get country - use case-insensitive lookup for mission_dates
        campaign_dates = self._ensure_dict(
            self.loader.get_mission_dates_for_campaign(campaign_name),
            f"mission_dates[{campaign_name}]"
        )
        
        # Get events
        campaign_events = self._ensure_dict(
            events_data.get(campaign_name, {}),
            f"events[{campaign_name}]"
        )
        country = self._resolve_country(campaign_events, campaign_dates)
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
        # Use case-insensitive lookup for mission_dates
        campaign_dates = self._ensure_dict(
            self.loader.get_mission_dates_for_campaign(campaign_name),
            f"mission_dates[{campaign_name}]"
        )
        
        # Extract components
        country = self._resolve_country(campaign_events, campaign_dates)
        events = self._ensure_list(
            campaign_events.get('events', []),
            f"events[{campaign_name}].events"
        )
        game_directory = get_game_directory(mission_dates)
        events = self._decorate_events(events, country, game_directory)
        debriefings_html = self._extract_debriefings_html(campaign_events)
        
        # Calculate summary statistics
        summary = self._calculate_summary(
            campaign_name,
            campaign_decoded,
            completed_missions,
            campaign_dates,
            events,
            debriefings_html
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

    @staticmethod
    def _extract_debriefings_html(campaign_events: Dict) -> str:
        debriefings_html = campaign_events.get('debriefings_html', '')
        if isinstance(debriefings_html, str) and debriefings_html.strip():
            return debriefings_html

        combined_html = campaign_events.get('html', '')
        if not isinstance(combined_html, str) or not combined_html.strip():
            return ''

        match = re.search(
            r'(?is)(<b>\s*Mission Debriefings\s*</b>.*?)(?:<b>\s*Events\s*</b>|$)',
            combined_html
        )
        if match:
            return match.group(1).strip()

        return combined_html.strip()
    
    def _calculate_summary(
        self,
        campaign_name: str,
        decoded_data: Dict,
        completed_missions: List[str],
        mission_dates: Dict,
        events: List[Dict],
        debriefings_html: str
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

        # Aggregate stats across all missions
        stats_by_mission = {
            mission_id: per_mission_stats.get(mission_id, {})
            for mission_id in sorted_missions
            if isinstance(per_mission_stats.get(mission_id, {}), dict)
        }

        if stats_by_mission:
            summary['combat_results'] = aggregate_kills_from_missions(stats_by_mission)
            summary['combat_results']['total_score'] = sum(
                int(stats.get('score', 0)) for stats in stats_by_mission.values()
            )
        
        # Calculate missions stats
        summary['missions_stats'] = self._calculate_mission_stats(
            sorted_missions,
            per_mission_stats,
            decoded_data,
            debriefings_html
        )
        
        # Calculate aircraft usage
        mission_aircraft_map = self.loader.get_mission_aircraft_map(campaign_name)
        summary['aircraft_usage'] = self._calculate_aircraft_usage(
            campaign_name,
            sorted_missions,
            mission_dates,
            per_mission_stats,
            mission_aircraft_map
        )
        
        # Extract career progression
        summary['career_progression'] = self._extract_career_progression(events)
        
        # Calculate timeline
        summary['timeline'] = self._calculate_timeline(
            campaign_name,
            sorted_missions,
            mission_dates
        )
        
        return summary
    
    def _calculate_mission_stats(
        self,
        missions: List[str],
        per_mission_stats: Dict,
        decoded_data: Dict,
        debriefings_html: str
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
            if self._mission_success(completed_by_filename, m)
        )

        total_flight_seconds = sum(
            self._extract_flight_seconds(per_mission_stats.get(mission_id, {}))
            for mission_id in missions
        )

        duration_seconds, statuses = self._parse_debriefings(debriefings_html)
        if total_flight_seconds == 0 and duration_seconds:
            total_flight_seconds = sum(duration_seconds)

        average_seconds = int(total_flight_seconds / total_missions) if total_missions > 0 else 0
        landings = self._aggregate_landing_outcomes(statuses)

        return {
            'total_missions': total_missions,
            'completed_missions': total_missions,
            'successful_missions': successful,
            'success_rate': round(successful / total_missions * 100) if total_missions > 0 else 0,
            'total_flight_time': self._format_duration(total_flight_seconds),
            'average_duration': self._format_duration(average_seconds),
            'landings': landings
        }
    
    def _calculate_aircraft_usage(
        self,
        campaign_name: str,
        missions: List[str],
        mission_dates: Dict,
        per_mission_stats: Dict,
        mission_aircraft_map: Dict
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
            # Get aircraft for this mission (prefer aircraft map)
            aircraft_entry = mission_aircraft_map.get(mission_id, {})
            aircraft = None
            if isinstance(aircraft_entry, dict):
                aircraft = aircraft_entry.get('aircraft')

            if not aircraft:
                mission_meta = self._get_mission_meta(campaign_name, mission_dates, mission_id)
                if isinstance(mission_meta, dict):
                    aircraft = mission_meta.get('aircraft')

            if not aircraft:
                aircraft = 'Unknown'
            
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
        kills = calculate_kills_from_stats(mission_stats)
        return int(kills.get('total_kills', 0))

    def _mission_success(self, completed_by_filename: Dict, mission_id: str) -> bool:
        mission_entry = completed_by_filename.get(mission_id, {})
        if not isinstance(mission_entry, dict):
            return False
        return mission_entry.get('isSuccess', 0) == 1

    @staticmethod
    def _extract_flight_seconds(mission_stats: Dict) -> int:
        if not isinstance(mission_stats, dict):
            return 0
        for key in ('totalFlightTime', 'flightTime', 'total_flight_time', 'flight_time'):
            value = mission_stats.get(key)
            if value is None:
                continue
            try:
                return int(value)
            except (TypeError, ValueError):
                continue
        return 0

    @staticmethod
    def _format_duration(seconds: int) -> str:
        if not seconds or seconds < 0:
            return "00:00"
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours:02d}:{minutes:02d}"

    @staticmethod
    def _parse_debriefings(debriefings_html: str) -> tuple[List[int], List[str]]:
        if not debriefings_html:
            return [], []
        durations: List[int] = []
        statuses: List[str] = []
        pattern = re.compile(
            r"Duration:\s*(\d{2}:\d{2}:\d{2})\s*\|\s*Status:\s*([^<|]+)",
            re.IGNORECASE
        )
        for duration_str, status in pattern.findall(debriefings_html):
            parts = duration_str.split(":")
            if len(parts) == 3:
                try:
                    hours, minutes, seconds = (int(part) for part in parts)
                    durations.append(hours * 3600 + minutes * 60 + seconds)
                except ValueError:
                    continue
            statuses.append(status.strip())
        return durations, statuses

    @staticmethod
    def _aggregate_landing_outcomes(statuses: List[str]) -> List[Dict]:
        safe_landings = 0
        hard_landings = 0
        wounded_landings = 0
        bailouts = 0
        kia_mia = 0

        for status in statuses:
            normalized = status.lower().strip()
            if "wound" in normalized:
                wounded_landings += 1
            elif "bail" in normalized or "bailed" in normalized:
                bailouts += 1
            elif any(token in normalized for token in ("kia", "mia", "killed")):
                kia_mia += 1
            elif "hard" in normalized or "crash" in normalized:
                hard_landings += 1
            elif "landed" in normalized:
                safe_landings += 1

        return [
            {'label': 'Safe Landings', 'value': safe_landings},
            {'label': 'Hard Landings / Crashes', 'value': hard_landings},
            {'label': 'Wounded Landings', 'value': wounded_landings},
            {'label': 'Bailouts', 'value': bailouts},
            {'label': 'KIA / MIA', 'value': kia_mia}
        ]
    
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
        campaign_name: str,
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
        
        first_meta = self._get_mission_meta(campaign_name, mission_dates, first_mission_id)
        last_meta = self._get_mission_meta(campaign_name, mission_dates, last_mission_id)
        
        first_date = first_meta.get('date')
        last_date = last_meta.get('date')
        
        # Calculate duration if both dates available
        duration_days = None
        if first_date and last_date:
            try:
                from datetime import datetime
                # Dates in format: "1942.05.05" or "1942-05-05"
                date_formats = ('%Y.%m.%d', '%Y-%m-%d')
                first_dt = next(
                    datetime.strptime(first_date, fmt) for fmt in date_formats
                    if self._can_parse_date(first_date, fmt)
                )
                last_dt = next(
                    datetime.strptime(last_date, fmt) for fmt in date_formats
                    if self._can_parse_date(last_date, fmt)
                )
                duration_days = (last_dt - first_dt).days
            except:
                pass
        
        return {
            'first_mission_date': first_date,
            'last_mission_date': last_date,
            'duration_days': duration_days
        }

    def _get_mission_meta(
        self,
        campaign_name: str,
        mission_dates: Dict,
        mission_id: str
    ) -> Dict:
        if not isinstance(mission_dates, dict):
            return {}

        # Campaign-specific structure
        if isinstance(mission_dates.get('missions'), dict):
            return mission_dates['missions'].get(mission_id, {})

        # Full mission_dates.json structure
        campaign_data = mission_dates.get(campaign_name, {})
        if isinstance(campaign_data, dict):
            missions = campaign_data.get('missions')
            if isinstance(missions, dict):
                return missions.get(mission_id, {})

        return mission_dates.get(mission_id, {}) if isinstance(mission_dates, dict) else {}

    def _decorate_events(
        self,
        events: List[Dict],
        country: str,
        game_directory: str
    ) -> List[Dict]:
        """Attach image URLs and country to events for display."""
        decorated = []
        for event in events:
            if not isinstance(event, dict):
                continue
            enriched = dict(event)
            # Add country to each event for frontend translation
            enriched['country'] = country
            image_name = event.get('image')
            if image_name:
                relative_path = build_award_image_relative_path(country, image_name, event.get('date'))
                data_uri = build_dds_data_uri(game_directory, relative_path)
                enriched['image_url'] = data_uri or build_game_asset_url(relative_path)
                if event.get('type') == 'award':
                    large_relative_path = build_award_large_image_relative_path(
                        country,
                        image_name,
                        event.get('date')
                    )
                    large_data_uri = build_dds_data_uri(game_directory, large_relative_path)
                    enriched['modal_image_url'] = large_data_uri or build_game_asset_url(large_relative_path)
            decorated.append(enriched)
        return decorated
    
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
        # Use case-insensitive lookup
        campaign_data = self.loader.get_mission_dates_for_campaign(campaign_name)
        
        # Check for explicit display name (if Campaign Tracker provides it)
        display_name = campaign_data.get('display_name')
        if display_name:
            return display_name
        
        # Fallback: Format folder name
        # Replace underscores, capitalize words
        formatted = campaign_name.replace('_', ' ').title()
        
        return formatted

    @staticmethod
    def _resolve_country(campaign_events: Dict, campaign_dates: Dict) -> str:
        events_country = campaign_events.get('country')
        if isinstance(events_country, str) and events_country.strip():
            return events_country
        dates_country = campaign_dates.get('country')
        if isinstance(dates_country, str) and dates_country.strip():
            return dates_country
        return 'unknown'

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

    @staticmethod
    def _can_parse_date(raw_date: str, fmt: str) -> bool:
        try:
            from datetime import datetime
            datetime.strptime(raw_date, fmt)
            return True
        except ValueError:
            return False
