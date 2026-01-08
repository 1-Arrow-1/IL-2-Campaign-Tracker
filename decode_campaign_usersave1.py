#!/usr/bin/env python3
"""
decode_campaign_usersave1.py - IMPROVED VERSION
================================================

✅ FIX #1: File size check (prevents memory issues with huge/corrupt files)
✅ FIX #2: Iteration limit in deep_urldecode (prevents infinite loops)
✅ FIX #3: Better error messages
✅ FIX #4: Progress indication for large files

CHANGES FROM ORIGINAL:
----------------------
1. Added MAX_FILE_SIZE check (default: 50 MB)
2. Added max_iterations to deep_urldecode()
3. Added progress dots for large decodings
4. Better exception handling with specific error types
"""

import urllib.parse
import json
import os
from pathlib import Path

from utils.logging import get_logger, log_message
from utils.pathing import get_base_path

logger = get_logger(__name__)

# ✅ Configuration constants
MAX_FILE_SIZE_MB = 50  # Klar definiert in MB
MAX_FILE_SIZE = MAX_FILE_SIZE_MB * 1024 * 1024  # Konvertierung zu Bytes
MAX_DECODE_ITERATIONS = 10  # Prevent infinite loops in URL decoding
BASE_DIR = get_base_path(__file__)


def deep_urldecode(s, max_iterations=MAX_DECODE_ITERATIONS):
    """
    Recursively decode URL-encoded string until no encodings remain.
    
    ✅ IMPROVED: Added iteration limit to prevent infinite loops
    
    Args:
        s: String to decode
        max_iterations: Maximum number of decode attempts (default: 10)
    
    Returns:
        Decoded string
    """
    prev = None
    iterations = 0
    
    while prev != s and iterations < max_iterations:
        prev = s
        s = urllib.parse.unquote(s)
        iterations += 1
    
    # ✅ Warn if we hit the limit (shouldn't happen in normal usage)
    if iterations >= max_iterations:
        log_message(logger, f"⚠️  Warning: Max decode iterations ({max_iterations}) reached")
        log_message(logger, f"   String may not be fully decoded: {s[:80]}...")
    
    return s


def parse_campaignsstates(filename):
    """
    Parse IL-2 campaign states file
    
    ✅ IMPROVED: Added file size check and progress indication
    """
    # ✅ FIX #1: Check file size before loading
    file_path = Path(filename)
    
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {filename}")
    
    file_size = file_path.stat().st_size
    
    # Check if file is too large
    if file_size > MAX_FILE_SIZE:
        raise ValueError(
            f"Campaign save file too large: {file_size:,} bytes\n"
            f"Maximum allowed: {MAX_FILE_SIZE:,} bytes ({MAX_FILE_SIZE_MB} MB)\n"
            f"This may indicate a corrupted file or an unexpected format."
        )
    
    # Show warning for large files (but still process them)
    if file_size > 5 * 1024 * 1024:  # 5 MB
        log_message(logger, f"ℹ️  Large campaign save detected: {file_size:,} bytes")
        log_message(logger, f"   This may take a moment to process...")
    
    # Read and parse file
    with open(filename, encoding="utf-8") as f:
        raw = f.read().strip()
    
    if not raw:
        log_message(logger, "⚠️  Warning: Campaign save file is empty")
        return {}
    
    campaigns = {}
    entries = raw.split("&")
    total_entries = len(entries)
    
    # ✅ Show progress for large files
    show_progress = total_entries > 100
    if show_progress:
        log_message(logger, f"   Processing {total_entries} entries", end="", flush=True)
    
    # Split by & to get each campaign entry
    for idx, entry in enumerate(entries):
        # ✅ Show progress dots
        if show_progress and idx > 0 and idx % 50 == 0:
            log_message(logger, ".", end="", flush=True)
        
        if "=" not in entry:
            continue
        
        try:
            key, value = entry.split("=", 1)
        except ValueError:
            log_message(logger, f"\n⚠️  Warning: Malformed entry (no '=' found): {entry[:50]}...")
            continue
        
        if not key.startswith("campaigns/"):
            continue
        
        campaign_name = key[len("campaigns/"):]
        
        # URL-decode campaign name (handles spaces and special chars)
        campaign_name = urllib.parse.unquote(campaign_name)
        
        # First decode gives us the parameter string
        value_decoded = urllib.parse.unquote(value)
        
        params = {}
        
        # Now split by regular & to get parameters
        for param in value_decoded.split("&"):
            if "=" not in param:
                continue
            
            try:
                subkey, subval = param.split("=", 1)
            except ValueError:
                continue
            
            # Handle special nested structures
            if subkey in ("characterStatisticsByFileName", "completedMissionsByFileName"):
                # These contain mission data keyed by mission number
                if not subval:  # Empty value
                    params[subkey] = {}
                    continue
                
                # Decode one more level to get mission_id=stats_still_encoded format
                subval_decoded = urllib.parse.unquote(subval)
                
                missions = {}
                
                # Split by & to get each mission
                parts = subval_decoded.split("&")
                
                for part in parts:
                    if "=" not in part:
                        continue
                    
                    try:
                        mission_id, mission_data_encoded = part.split("=", 1)
                    except ValueError:
                        continue
                    
                    # URL-decode mission_id (handles spaces and special chars like %20)
                    mission_id = urllib.parse.unquote(mission_id)
                    
                    # Decode the mission data one more time
                    mission_data_decoded = urllib.parse.unquote(mission_data_encoded)
                    
                    if subkey == "characterStatisticsByFileName":
                        # Parse the stats as key=value pairs separated by &
                        mission_stats = {}
                        for stat_pair in mission_data_decoded.split("&"):
                            if "=" in stat_pair:
                                try:
                                    stat_key, stat_val = stat_pair.split("=", 1)
                                    # Try to convert to int
                                    try:
                                        mission_stats[stat_key] = int(stat_val) if stat_val else stat_val
                                    except ValueError:
                                        mission_stats[stat_key] = stat_val
                                except ValueError:
                                    continue
                        missions[mission_id] = mission_stats
                    else:
                        # For completedMissionsByFileName, convert to int
                        try:
                            missions[mission_id] = int(mission_data_decoded) if mission_data_decoded else mission_data_decoded
                        except ValueError:
                            missions[mission_id] = mission_data_decoded
                
                params[subkey] = missions
            else:
                # Regular parameter - decode fully and try to convert to int
                decoded_val = deep_urldecode(subval)
                try:
                    params[subkey] = int(decoded_val) if decoded_val else decoded_val
                except ValueError:
                    params[subkey] = decoded_val
        
        campaigns[campaign_name] = params
    
    if show_progress:
        log_message(logger)  # New line after progress dots
    
    return campaigns


def main(states_path=None) -> bool:
    """
    Main decoder function
    
    ✅ IMPROVED: Better error handling and user feedback
    
    Args:
        states_path: Path to campaignsstates.txt (default: look in CWD for backward compat)
    
    Returns:
        bool: True if successful, False otherwise
    """
    if states_path is None:
        # Backward compatibility: look in tracker base directory
        input_file = BASE_DIR / 'campaignsstates.txt'
    else:
        input_file = Path(states_path)
    
    output_file = BASE_DIR / 'campaigns_decoded.json'
    
    # ✅ Better error messages
    if not input_file.exists():
        log_message(logger, f"❌ ERROR: {input_file} not found!")
        log_message(logger, f"   Expected location: {input_file.absolute()}")
        return False
    
    try:
        log_message(logger, f"📖 Decoding: {input_file}")
        log_message(logger, f"   File size: {input_file.stat().st_size:,} bytes")
        
        # Parse campaign states
        data = parse_campaignsstates(str(input_file))
        
        # ✅ Filter existing campaigns only
        mission_dates_file = BASE_DIR / "campaign_mission_dates.json"
        game_directory = None
        mission_dates_data = {}
        ww1_campaigns = set()
        
        # Read IL-2 game directory + WW1 exclusions from mission dates file
        if mission_dates_file.exists():
            try:
                with open(mission_dates_file, "r", encoding="utf-8") as f:
                    mission_dates_data = json.load(f)
                if not isinstance(mission_dates_data, dict):
                    log_message(logger, f"⚠️  Invalid mission dates format in {mission_dates_file}")
                    mission_dates_data = {}
                game_directory_str = mission_dates_data.get("game_directory", "")
                if game_directory_str:
                    game_directory = Path(game_directory_str).expanduser().resolve()
                ww1_campaigns = {
                    name.lower()
                    for name, data in mission_dates_data.items()
                    if isinstance(data, dict) and data.get("is_ww1", False)
                }
            except Exception as e:
                log_message(logger, f"⚠️  Could not read game directory from {mission_dates_file}: {e}")

        # Fallback: current directory if not found
        if not game_directory or not game_directory.exists():
            log_message(logger, "⚠️  Using current directory as fallback (game_directory not found)")
            game_directory = Path.cwd()

        campaigns_root = game_directory / "data" / "Campaigns"

        if not campaigns_root.exists():
            log_message(logger, f"⚠️  Campaigns directory not found: {campaigns_root}")
        else:
            existing_campaigns = {folder.name.lower() for folder in campaigns_root.iterdir() if folder.is_dir()}
            log_message(logger, f"📁 Found {len(existing_campaigns)} campaign folders in {campaigns_root}")

            filtered_data = {}
            skipped_count = 0
            
            for key, campaign in data.items():
                campaign_name = key.lower()
                # 🟡 NEU: WW1-Erkennung – Kampagne überspringen, falls markiert
                if campaign_name in ww1_campaigns or campaign.get("is_ww1", False):
                    log_message(logger, f"  ⚠️  Skipping WW1 campaign: {campaign_name}")
                    continue
                if campaign_name in existing_campaigns:
                    filtered_data[key] = campaign
                else:
                    skipped_count += 1
                    if skipped_count <= 5:  # Only show first 5 to avoid spam
                        log_message(logger, f"  ⚠️  Skipping orphaned campaign: {campaign_name}")
            
            if skipped_count > 5:
                log_message(logger, f"  ⚠️  ... and {skipped_count - 5} more orphaned campaigns")

            data = filtered_data
            log_message(logger, f"✅ {len(data)} campaigns remain after filtering")
        
        # ✅ Write to JSON file with atomic write pattern
        tmp_output = output_file.with_suffix('.tmp')
        
        with open(tmp_output, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        # Atomic replace
        tmp_output.replace(output_file)
        
        log_message(logger, f"✅ Decoded {len(data)} campaigns")
        log_message(logger, f"✅ Saved to: {output_file}")
        return True
        
    except FileNotFoundError as e:
        log_message(logger, f"❌ ERROR: {e}")
        return False
    
    except ValueError as e:
        log_message(logger, f"❌ ERROR: {e}")
        return False
    
    except json.JSONDecodeError as e:
        log_message(logger, f"❌ ERROR: Failed to parse mission dates JSON: {e}")
        return False
    
    except Exception as e:
        log_message(logger, f"❌ ERROR decoding save file: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
