"""
Data validation for campaign data structures.

Validates JSON data conforms to expected schemas.
Provides type-safe checks and error reporting.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple


logger = logging.getLogger(__name__)


def validate_campaign_data(
    campaign_name: str,
    completion_state: List[str],
    events: Dict,
    decoded: Dict,
    mission_dates: Dict
) -> Tuple[bool, List[str]]:
    """
    Validate campaign data from all sources.
    
    Args:
        campaign_name: Campaign identifier
        completion_state: List of completed mission IDs
        events: Events dict (awards, promotions)
        decoded: Decoded save data
        mission_dates: Mission metadata
    
    Returns:
        Tuple of (is_valid, list_of_warnings)
        
    Design:
    - Non-blocking: Returns warnings but doesn't prevent display
    - Useful for debugging data inconsistencies
    """
    warnings = []
    
    # Check completion state
    if not isinstance(completion_state, list):
        warnings.append(f"completion_state is not a list: {type(completion_state)}")
    
    # Check events structure
    if events:
        if 'events' in events and not isinstance(events['events'], list):
            warnings.append("events['events'] is not a list")
        
        if 'country' in events and not isinstance(events['country'], str):
            warnings.append("events['country'] is not a string")
    
    # Check decoded structure
    if decoded:
        if 'characterStatisticsByFileName' in decoded:
            stats = decoded['characterStatisticsByFileName']
            if not isinstance(stats, dict):
                warnings.append("characterStatisticsByFileName is not a dict")
    
    # Check mission dates structure
    if mission_dates:
        if 'country' in mission_dates and not isinstance(mission_dates['country'], str):
            warnings.append("mission_dates['country'] is not a string")
    
    # Cross-reference checks
    if completion_state and decoded:
        stats = decoded.get('characterStatisticsByFileName', {})
        # Check if completed missions have corresponding stats
        for mission_id in completion_state:
            if mission_id not in stats:
                warnings.append(f"Mission {mission_id} in completion_state but not in stats")
    
    is_valid = len(warnings) == 0
    
    if warnings:
        logger.warning(f"Validation warnings for {campaign_name}: {warnings}")
    
    return is_valid, warnings


def validate_event(event: Dict) -> bool:
    """
    Validate single event structure.
    
    Args:
        event: Event dict (promotion or award)
    
    Returns:
        True if valid, False otherwise
    """
    if not isinstance(event, dict):
        return False
    
    # Required fields
    required_fields = ['type']
    for field in required_fields:
        if field not in event:
            logger.warning(f"Event missing required field: {field}")
            return False
    
    # Type-specific validation
    event_type = event.get('type')
    
    if event_type == 'promotion':
        if 'rank' not in event:
            logger.warning("Promotion event missing 'rank' field")
            return False
    
    elif event_type == 'award':
        if 'name' not in event:
            logger.warning("Award event missing 'name' field")
            return False
    
    return True


def sanitize_campaign_name(campaign_name: str) -> str:
    """
    Sanitize campaign name for safe usage in URLs and file paths.
    
    Args:
        campaign_name: Raw campaign name
    
    Returns:
        Sanitized campaign name
    """
    # Remove unsafe characters
    safe_name = ''.join(c for c in campaign_name if c.isalnum() or c in ('_', '-'))
    
    # Ensure not empty
    if not safe_name:
        safe_name = 'unknown_campaign'
    
    return safe_name


def check_data_freshness(
    completion_state: Dict,
    events: Dict,
    decoded: Dict
) -> Tuple[bool, str]:
    """
    Check if data sources are synchronized.
    
    Detects if Campaign Tracker needs to be re-run.
    
    Args:
        completion_state: Completion state dict
        events: Events dict
        decoded: Decoded data dict
    
    Returns:
        Tuple of (is_fresh, status_message)
    """
    # Get campaign names from each source
    completion_campaigns = set(completion_state.keys())
    events_campaigns = set(events.keys())
    decoded_campaigns = set(decoded.keys())
    
    # Check for campaigns in completion but missing from events/decoded
    missing_events = completion_campaigns - events_campaigns
    missing_decoded = completion_campaigns - decoded_campaigns
    
    if missing_events or missing_decoded:
        message = []
        if missing_events:
            message.append(f"Missing events for: {missing_events}")
        if missing_decoded:
            message.append(f"Missing decoded data for: {missing_decoded}")
        
        return False, "; ".join(message)
    
    return True, "Data synchronized"
