"""
Rank Scaling Utilities

Handles rank scaling factor tracking and cleanup of invalid promotions
when the user changes the rank scaling configuration mid-campaign.

When a user increases the rank scaling factor, previously earned promotions
may no longer be valid (the required scores are now higher). This module
detects such changes and removes invalid promotion entries from the
popup_seen state to maintain consistency.
"""

from typing import Dict, List, Tuple
from utils.logging import get_logger, log_message

logger = get_logger(__name__)


def get_reachable_ranks(
    ranks: List[Dict],
    scale_factor: float,
    total_score: int,
    starting_rank_offset: int = 0
) -> List[str]:
    """
    Calculate which ranks are reachable with given factor and score.
    
    Args:
        ranks: List of rank definitions from config (with 'name' and 'score' keys)
        scale_factor: Current rank scaling factor
        total_score: Player's total accumulated score
        starting_rank_offset: Index of starting rank (0 = lowest rank)
        
    Returns:
        List of rank names that are reachable (including starting rank)
    """
    if not ranks:
        return []
    
    # Clamp starting_rank_offset to valid range
    starting_rank_offset = max(0, min(starting_rank_offset, len(ranks) - 1))
    
    reachable = []
    
    # Starting rank is always reachable
    reachable.append(ranks[starting_rank_offset]['name'])
    
    # Check each rank above starting rank
    for i in range(starting_rank_offset + 1, len(ranks)):
        rank = ranks[i]
        required_score = int(rank['score'] * scale_factor)
        
        if total_score >= required_score:
            reachable.append(rank['name'])
        else:
            # Once we can't reach a rank, we can't reach any higher ranks either
            break
    
    return reachable


def cleanup_invalid_promotions(
    campaign_name: str,
    old_factor: float,
    new_factor: float,
    ranks: List[Dict],
    total_score: int,
    starting_rank_offset: int,
    popup_seen_data: Dict,
) -> Tuple[Dict, List[str]]:
    """
    Remove promotion entries that are no longer valid after a rank scaling factor increase.
    
    This function is called when the user increases the rank scaling factor mid-campaign.
    Promotions that were previously earned may no longer be valid because the required
    scores are now higher.
    
    Args:
        campaign_name: Name of the campaign
        old_factor: Previously used rank scaling factor
        new_factor: New (higher) rank scaling factor
        ranks: List of rank definitions from config
        total_score: Player's total accumulated score
        starting_rank_offset: Index of starting rank
        popup_seen_data: The entire popup_seen structure (will be modified)
        
    Returns:
        Tuple of (modified popup_seen_data, list of removed event keys)
    """
    removed_keys = []
    
    # Get campaign's seen data
    campaign_seen = popup_seen_data.get(campaign_name)
    if not campaign_seen:
        return popup_seen_data, removed_keys
    
    # Handle both old format (list) and new format (dict with 'seen' key)
    if isinstance(campaign_seen, list):
        seen_keys = campaign_seen
    elif isinstance(campaign_seen, dict):
        seen_keys = campaign_seen.get('seen', [])
    else:
        return popup_seen_data, removed_keys
    
    # Calculate which ranks are still reachable with new factor
    reachable_ranks = set(get_reachable_ranks(
        ranks, new_factor, total_score, starting_rank_offset
    ))
    
    # Filter out invalid promotion keys
    valid_keys = []
    for key in seen_keys:
        if key.startswith('promotion|'):
            # Extract rank name from key: "promotion|RankName|mission|date"
            parts = key.split('|')
            if len(parts) >= 2:
                rank_name = parts[1]
                if rank_name in reachable_ranks:
                    valid_keys.append(key)
                else:
                    removed_keys.append(key)
            else:
                # Malformed key, keep it
                valid_keys.append(key)
        else:
            # Not a promotion (e.g., award) - keep it
            valid_keys.append(key)
    
    # Update popup_seen_data with filtered keys
    if removed_keys:
        if isinstance(campaign_seen, list):
            # Old format - convert to new format
            popup_seen_data[campaign_name] = {
                'seen': valid_keys,
                'rank_scale_factor': new_factor
            }
        else:
            # New format - update in place
            popup_seen_data[campaign_name]['seen'] = valid_keys
            popup_seen_data[campaign_name]['rank_scale_factor'] = new_factor
    
    return popup_seen_data, removed_keys


def check_and_cleanup_rank_scaling(
    campaign_name: str,
    current_factor: float,
    ranks: List[Dict],
    total_score: int,
    starting_rank_offset: int,
    popup_seen_data: Dict,
    logger_instance=None
) -> Tuple[Dict, bool]:
    """
    Check if rank scaling factor changed and cleanup if necessary.
    
    This is the main entry point for the rank scaling cleanup logic.
    It should be called before generating events for a campaign.
    
    Args:
        campaign_name: Name of the campaign
        current_factor: Current rank scaling factor from config
        ranks: List of rank definitions from config
        total_score: Player's total accumulated score
        starting_rank_offset: Index of starting rank
        popup_seen_data: The entire popup_seen structure
        logger_instance: Optional logger for output
        
    Returns:
        Tuple of (modified popup_seen_data, whether changes were made)
    """
    log = logger_instance or logger
    
    # Get stored factor for this campaign
    old_factor = get_campaign_scale_factor(popup_seen_data, campaign_name)
    
    # Only cleanup if factor INCREASED (requirements got harder)
    if current_factor > old_factor and old_factor > 0:
        popup_seen_data, removed_keys = cleanup_invalid_promotions(
            campaign_name=campaign_name,
            old_factor=old_factor,
            new_factor=current_factor,
            ranks=ranks,
            total_score=total_score,
            starting_rank_offset=starting_rank_offset,
            popup_seen_data=popup_seen_data
        )
        
        if removed_keys:
            log_message(log, f"⚠️ Rank scaling factor changed ({old_factor} → {current_factor}) for '{campaign_name}'")
            log_message(log, f"   Removed {len(removed_keys)} invalid promotion(s) from popup state:")
            for key in removed_keys:
                log_message(log, f"   - {key}")
            
            # Update the stored factor
            popup_seen_data = set_campaign_scale_factor(popup_seen_data, campaign_name, current_factor)
            return popup_seen_data, True
    
    # Always update the factor (even if no cleanup was needed)
    # This ensures we track the factor for future comparisons
    if current_factor != old_factor:
        popup_seen_data = set_campaign_scale_factor(popup_seen_data, campaign_name, current_factor)
        return popup_seen_data, True
    
    return popup_seen_data, False


def get_campaign_scale_factor(popup_seen_data: Dict, campaign_name: str) -> float:
    """
    Get the stored rank scaling factor for a campaign.
    
    Args:
        popup_seen_data: The popup_seen structure
        campaign_name: Name of the campaign
        
    Returns:
        Stored factor, or 0.0 if not set (indicates first run or old format)
    """
    campaign_data = popup_seen_data.get(campaign_name)
    
    if campaign_data is None:
        return 0.0  # Campaign not in popup_seen yet
    
    if isinstance(campaign_data, list):
        # Old format (just a list of keys) - no factor stored
        return 0.0
    
    if isinstance(campaign_data, dict):
        return float(campaign_data.get('rank_scale_factor', 0.0))
    
    return 0.0


def set_campaign_scale_factor(popup_seen_data: Dict, campaign_name: str, factor: float) -> Dict:
    """
    Set the rank scaling factor for a campaign.
    
    If the campaign uses the old format (list), it will be migrated to the new format (dict).
    
    NOTE: This function does NOT create new campaign entries. If the campaign doesn't exist,
    it returns the data unchanged. New campaigns are created during initial sync in step3.
    
    Args:
        popup_seen_data: The popup_seen structure (will be modified)
        campaign_name: Name of the campaign
        factor: Rank scaling factor to store
        
    Returns:
        Modified popup_seen_data
    """
    campaign_data = popup_seen_data.get(campaign_name)
    
    if campaign_data is None:
        # New campaign - don't create entry here, let initial sync handle it
        # Just return unchanged data
        return popup_seen_data
    elif isinstance(campaign_data, list):
        # Old format - migrate to new format
        popup_seen_data[campaign_name] = {
            'seen': campaign_data,
            'rank_scale_factor': factor
        }
    elif isinstance(campaign_data, dict):
        # New format - just update factor
        popup_seen_data[campaign_name]['rank_scale_factor'] = factor
    
    return popup_seen_data
