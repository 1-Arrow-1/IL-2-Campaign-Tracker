"""
Popup State Management

Handles loading and saving of the popup_seen state which tracks which
events (promotions, awards) have already been shown as popups.

Supports two formats:
- Old format: {campaign_name: [event_keys...]}
- New format: {campaign_name: {seen: [event_keys...], rank_scale_factor: float}}

The new format also stores the rank scaling factor used when events were generated,
enabling detection of configuration changes that would invalidate previous promotions.
"""

import json
import shutil
from pathlib import Path
from typing import Dict, List, Union

from utils.logging import get_logger, log_message

logger = get_logger(__name__)

# Type alias for the popup_seen data structure
# Can be either old format (list) or new format (dict)
CampaignSeenData = Union[List[str], Dict[str, Union[List[str], float]]]
PopupSeenData = Dict[str, CampaignSeenData]


def load_popup_seen(path: Path) -> PopupSeenData:
    """
    Load already-shown popup event keys.
    
    Supports both old format (list) and new format (dict with 'seen' and 'rank_scale_factor').
    
    Returns:
        Dict mapping campaign_name to either:
        - Old format: List of event keys
        - New format: Dict with 'seen' (list) and 'rank_scale_factor' (float)
    """
    if not path.exists():
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Validate structure
        if not isinstance(data, dict):
            log_message(logger, "[popups] Warning: Invalid popup state structure, resetting")
            return {}

        # Validate each campaign's data
        validated_data: PopupSeenData = {}
        for campaign_name, campaign_data in data.items():
            if isinstance(campaign_data, list):
                # Old format - list of event keys
                validated_data[campaign_name] = campaign_data
            elif isinstance(campaign_data, dict):
                # New format - dict with 'seen' and optionally 'rank_scale_factor'
                seen = campaign_data.get('seen', [])
                if isinstance(seen, list):
                    validated_data[campaign_name] = {
                        'seen': seen,
                        'rank_scale_factor': float(campaign_data.get('rank_scale_factor', 0.0))
                    }
                else:
                    log_message(logger, f"[popups] Warning: Invalid 'seen' for '{campaign_name}', skipping")
            else:
                log_message(logger, f"[popups] Warning: Invalid data for '{campaign_name}', skipping")

        return validated_data

    except json.JSONDecodeError as e:
        log_message(logger, f"[popups] ERROR: Corrupted popup state file: {e}")
        log_message(logger, "[popups] Creating backup and resetting...")

        # Backup corrupted file
        backup_path = path.with_suffix('.corrupted')
        try:
            shutil.copy2(path, backup_path)
            log_message(logger, f"[popups] Corrupted file backed up to: {backup_path}")
        except Exception:
            pass

        return {}

    except Exception as e:
        log_message(logger, f"[popups] Warning: Could not load popup state: {e}")
        return {}


def save_popup_seen(path: Path, data: PopupSeenData) -> None:
    """
    Save already-shown popup event keys.

    Uses atomic write to prevent corruption.
    Supports both old format (list) and new format (dict).
    """
    try:
        # Validate input
        if not isinstance(data, dict):
            log_message(
                logger,
                "[popups] ERROR: Invalid data type for popup state (expected dict, got "
                f"{type(data).__name__})",
            )
            return

        # Write to temporary file first (atomic write pattern)
        tmp_file = path.with_suffix('.tmp')

        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True, ensure_ascii=False)

        # Atomic replace
        tmp_file.replace(path)

    except Exception as e:
        log_message(logger, f"[popups] ERROR: Could not save popup state: {e}")

        # Cleanup temp file if it exists
        try:
            tmp_file = path.with_suffix('.tmp')
            if tmp_file.exists():
                tmp_file.unlink()
        except Exception:
            pass


def get_seen_keys(popup_seen_data: PopupSeenData, campaign_name: str) -> List[str]:
    """
    Get the list of seen event keys for a campaign.
    
    Handles both old format (list) and new format (dict).
    
    Args:
        popup_seen_data: The popup_seen structure
        campaign_name: Name of the campaign
        
    Returns:
        List of event keys that have been seen
    """
    campaign_data = popup_seen_data.get(campaign_name)
    
    if campaign_data is None:
        return []
    
    if isinstance(campaign_data, list):
        # Old format
        return campaign_data
    
    if isinstance(campaign_data, dict):
        # New format
        return campaign_data.get('seen', [])
    
    return []


def set_seen_keys(popup_seen_data: PopupSeenData, campaign_name: str, keys: List[str], scale_factor: float = 0.0) -> PopupSeenData:
    """
    Set the list of seen event keys for a campaign.
    
    Preserves the rank_scale_factor if using new format, or sets it if provided.
    
    Args:
        popup_seen_data: The popup_seen structure (will be modified)
        campaign_name: Name of the campaign
        keys: List of event keys to set
        scale_factor: Optional rank scaling factor to set (0.0 means preserve existing or use default)
        
    Returns:
        Modified popup_seen_data
    """
    campaign_data = popup_seen_data.get(campaign_name)
    
    if campaign_data is None:
        # New campaign - use new format
        popup_seen_data[campaign_name] = {
            'seen': keys,
            'rank_scale_factor': scale_factor
        }
    elif isinstance(campaign_data, list):
        # Old format - convert to new format
        popup_seen_data[campaign_name] = {
            'seen': keys,
            'rank_scale_factor': scale_factor
        }
    elif isinstance(campaign_data, dict):
        # New format - preserve factor unless new one provided
        popup_seen_data[campaign_name]['seen'] = keys
        if scale_factor > 0:
            popup_seen_data[campaign_name]['rank_scale_factor'] = scale_factor
    
    return popup_seen_data


def add_seen_keys(popup_seen_data: PopupSeenData, campaign_name: str, new_keys: List[str]) -> PopupSeenData:
    """
    Add new event keys to the seen list for a campaign.
    
    Args:
        popup_seen_data: The popup_seen structure (will be modified)
        campaign_name: Name of the campaign
        new_keys: List of new event keys to add
        
    Returns:
        Modified popup_seen_data
    """
    existing_keys = set(get_seen_keys(popup_seen_data, campaign_name))
    all_keys = sorted(existing_keys | set(new_keys))
    return set_seen_keys(popup_seen_data, campaign_name, all_keys)


def make_event_key(ev: dict) -> str:
    """
    Build a stable key for an event so we can detect if it was already shown as a popup.
    Expected fields (from campaign_events.json structure): type, rank/name, mission, date
    """
    ev_type = str(ev.get("type", "")).strip().lower()
    mission = str(ev.get("mission", "")).strip()
    date = str(ev.get("date", "")).strip()

    if ev_type == "promotion":
        rank = str(ev.get("rank", "")).strip()
        return f"promotion|{rank}|{mission}|{date}"

    if ev_type == "award":
        name = str(ev.get("name", "")).strip()
        return f"award|{name}|{mission}|{date}"

    # fallback for unknown event types
    return f"{ev_type}|{mission}|{date}"
