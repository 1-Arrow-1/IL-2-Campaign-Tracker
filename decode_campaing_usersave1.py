import urllib.parse
import json
from pathlib import Path

def deep_urldecode(s):
    """Recursively decode URL-encoded string until no encodings remain."""
    prev = None
    while prev != s:
        prev = s
        s = urllib.parse.unquote(s)
    return s

def parse_campaignsstates(filename):
    with open(filename, encoding="utf-8") as f:
        raw = f.read().strip()
    if not raw:
        return {}
    
    campaigns = {}
    
    # Split by & to get each campaign entry
    for entry in raw.split("&"):
        if "=" not in entry:
            continue
        key, value = entry.split("=", 1)
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
                
            subkey, subval = param.split("=", 1)
            
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
                    
                    mission_id, mission_data_encoded = part.split("=", 1)
                    
                    # URL-decode mission_id (handles spaces and special chars like %20)
                    mission_id = urllib.parse.unquote(mission_id)
                    
                    # Decode the mission data one more time
                    mission_data_decoded = urllib.parse.unquote(mission_data_encoded)
                    
                    if subkey == "characterStatisticsByFileName":
                        # Parse the stats as key=value pairs separated by &
                        mission_stats = {}
                        for stat_pair in mission_data_decoded.split("&"):
                            if "=" in stat_pair:
                                stat_key, stat_val = stat_pair.split("=", 1)
                                # Try to convert to int
                                try:
                                    mission_stats[stat_key] = int(stat_val) if stat_val else stat_val
                                except ValueError:
                                    mission_stats[stat_key] = stat_val
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
    
    return campaigns

def main():
    """Main decoder function"""
    input_file = Path('campaignsstates.txt')
    output_file = Path('campaigns_decoded.json')
    
    if not input_file.exists():
        print(f"ERROR: {input_file} not found!")
        return False
    
    try:
        data = parse_campaignsstates(str(input_file))
        # --- 🧹 FILTER EXISTING CAMPAIGNS ONLY ---
        mission_dates_file = Path("campaign_mission_dates.json")
        game_directory = None

        # Read IL-2 game directory from mission dates file
        if mission_dates_file.exists():
            try:
                with open(mission_dates_file, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                    game_directory = Path(meta.get("game_directory", "")).expanduser().resolve()
            except Exception as e:
                print(f"⚠️ Could not read game directory from {mission_dates_file}: {e}")

        # Fallback: current directory if not found
        if not game_directory or not game_directory.exists():
            print("⚠️ Using current directory as fallback (game_directory not found)")
            game_directory = Path.cwd()

        campaigns_root = game_directory / "data" / "Campaigns"

        if not campaigns_root.exists():
            print(f"⚠️ Campaigns directory not found: {campaigns_root}")
        else:
            existing_campaigns = {folder.name.lower() for folder in campaigns_root.iterdir() if folder.is_dir()}
            print(f"Found {len(existing_campaigns)} campaign folders in {campaigns_root}")

            filtered_data = {}
            for key, campaign in data.items():
                campaign_name = key.lower()
                if campaign_name in existing_campaigns:
                    filtered_data[key] = campaign
                else:
                    print(f"  ⚠️ Skipping orphaned campaign: {campaign_name}")

            data = filtered_data
            print(f"✓ {len(data)} campaigns remain after filtering")
        # Write to JSON file
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"✓ Decoded {len(data)} campaigns")
        print(f"✓ Saved to: {output_file}")
        return True
        
    except Exception as e:
        print(f"ERROR decoding save file: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    main()
