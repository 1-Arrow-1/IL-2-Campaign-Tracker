#!/usr/bin/env python3
"""
IL-2 Campaign Mission Cleanup Tool

Detects and allows deletion of unsuccessful last missions (takeOffStatus = 1)
from campaignsstates.txt, enabling replay for better results.
"""

import json
import re
import shutil
import urllib.parse
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Set
import tkinter as tk
from tkinter import ttk, messagebox


# File to store "don't ask again" preferences
IGNORE_FILE = Path("cleanup_ignored_missions.json")


def load_ignored_missions() -> Set[str]:
    """
    Load list of missions that user chose to ignore
    
    Returns:
        Set of mission keys in format "campaign_name::mission_id"
    """
    if not IGNORE_FILE.exists():
        return set()
    
    try:
        with open(IGNORE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return set(data.get('ignored', []))
    except Exception as e:
        print(f"Warning: Could not load ignored missions: {e}")
        return set()


def save_ignored_missions(ignored: Set[str]):
    """
    Save list of ignored missions
    
    Args:
        ignored: Set of mission keys in format "campaign_name::mission_id"
    """
    try:
        data = {
            'ignored': sorted(list(ignored)),
            'last_updated': datetime.now().isoformat()
        }
        with open(IGNORE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Warning: Could not save ignored missions: {e}")


def add_to_ignored(campaign_name: str, mission_id: str):
    """
    Add a mission to the ignore list
    
    Args:
        campaign_name: Campaign name
        mission_id: Mission identifier
    """
    ignored = load_ignored_missions()
    key = f"{campaign_name}::{mission_id}"
    ignored.add(key)
    save_ignored_missions(ignored)
    print(f"✓ Added to ignore list: {campaign_name} - Mission {mission_id}")


def is_ignored(campaign_name: str, mission_id: str) -> bool:
    """
    Check if a mission is in the ignore list
    
    Args:
        campaign_name: Campaign name
        mission_id: Mission identifier
        
    Returns:
        True if mission should be ignored
    """
    ignored = load_ignored_missions()
    key = f"{campaign_name}::{mission_id}"
    return key in ignored
    
def _md5_file(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def _load_hash_index(index_path: Path) -> dict:
    if not index_path.exists():
        return {}
    try:
        with open(index_path, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


class MissionCleanup:
    """Handle cleanup of failed campaign missions"""
    
    def __init__(self, decoded_json_path: str = 'campaigns_decoded.json',
                 mission_dates_path: str = 'campaign_mission_dates.json',
                 campaignstates_path: str = None):
        """
        Initialize cleanup tool
        
        Args:
            decoded_json_path: Path to decoded campaign states
            mission_dates_path: Path to campaign mission dates
            campaignstates_path: Path to raw campaign states file (if None, auto-detect from game directory)
        """
        self.decoded_path = Path(decoded_json_path)
        self.dates_path = Path(mission_dates_path)
        
        # Auto-detect campaignsstates.txt location from game directory
        if campaignstates_path is None:
            self.states_path = self._find_campaignstates_file()
        else:
            self.states_path = Path(campaignstates_path)
        
        self.max_backups = 50
        
        print(f"Using campaignsstates.txt: {self.states_path}")
    
    def _find_campaignstates_file(self) -> Path:
        """
        Find campaignsstates.txt in IL-2 game directory (new structure supported)
        """
        if self.dates_path.exists():
            try:
                with open(self.dates_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    game_dir = data.get('game_directory', '')
                    if game_dir:
                        game_path = Path(game_dir).expanduser().resolve()

                        # ✅ Try new user-specific path
                        usersave_dir = game_path / 'data' / 'swf' / 'il2' / 'usersave'
                        if usersave_dir.exists():
                            for subdir in usersave_dir.iterdir():
                                potential = subdir / 'campaign' / 'campaignsstates.txt'
                                if potential.exists():
                                    print(f"✓ Found campaignsstates.txt in {potential}")
                                    return potential

                        # Legacy fallback (old versions)
                        legacy_path = game_path / 'data' / 'campaignsstates.txt'
                        if legacy_path.exists():
                            print(f"✓ Found legacy campaignsstates.txt: {legacy_path}")
                            return legacy_path

                        print(f"⚠️  campaignsstates.txt not found in either path")
            except Exception as e:
                print(f"⚠️  Could not read game directory: {e}")

        # Fallback to current working directory
        fallback = Path('campaignsstates.txt')
        if fallback.exists():
            print(f"⚠️  Using campaignsstates.txt from current directory (fallback)")
            return fallback

        print("❌ campaignsstates.txt not found! Please verify your IL-2 user save path.")
        raise FileNotFoundError("campaignsstates.txt not found in expected IL-2 user directory structure")

    
    def find_cleanup_opportunities(self) -> Dict:
        """
        Find ALL missions with takeOffStatus = 1 (unsuccessful)
        
        Returns:
            Dict of campaigns needing cleanup with their details
            Format: {campaign_name: {mission_id: details, ...}}
            (excludes missions marked as "don't ask again")
        """
        if not self.decoded_path.exists():
            print(f"⚠️  {self.decoded_path} not found - cannot scan")
            return {}
        
        # Load decoded campaign states
        with open(self.decoded_path, 'r', encoding='utf-8') as f:
            decoded = json.load(f)
        
        # Load mission order (if available)
        mission_dates = {}
        if self.dates_path.exists():
            with open(self.dates_path, 'r', encoding='utf-8') as f:
                mission_dates = json.load(f)
        
        # Load ignored missions
        ignored = load_ignored_missions()
        
        opportunities = {}
        
        for campaign_name, campaign_data in decoded.items():
            # Skip non-campaign entries
            if campaign_name == 'game_directory':
                continue
            
            # Get mission stats
            stats = campaign_data.get('characterStatisticsByFileName', {})
            if not stats:
                continue
            
            # Determine mission order
            dates_data = mission_dates.get(campaign_name, {})
            all_missions = dates_data.get('missions', {})
            
            if all_missions:
                # Use chronological order from campaign_mission_dates
                mission_order = sorted(all_missions.keys(),
                                     key=lambda x: int(x) if x.isdigit() else 0)
            else:
                # Fallback: numeric sort
                mission_order = sorted(stats.keys(),
                                     key=lambda x: int(x) if x.isdigit() else 0)
            
            # *** NEW: Check ALL flown missions, not just last ***
            campaign_opportunities = {}
            
            for mission_id in mission_order:
                # Skip missions not in stats
                if mission_id not in stats:
                    continue
                
                # Check if ignored
                if is_ignored(campaign_name, mission_id):
                    continue
                
                mission_stats = stats[mission_id]
                
                # Check takeOffStatus
                takeoff_status = mission_stats.get('takeOffStatus', 2)
                
                # Mission is considered "locked" only if it both failed (takeOffStatus=1)
                # AND still exists in completedMissionsByFileName
                completed_missions = campaign_data.get('completedMissionsByFileName', {})
                if takeoff_status == 1 and mission_id in completed_missions:
                    # This mission needs cleanup!
                    
                    # Calculate kills
                    air_kills = (mission_stats.get('killLightPlane', 0) + 
                               mission_stats.get('killMediumPlane', 0) +
                               mission_stats.get('killHeavyPlane', 0))
                    
                    ground_kills = (mission_stats.get('killLightArmoredVehicle', 0) +
                                  mission_stats.get('killMediumArmoredVehicle', 0) +
                                  mission_stats.get('killHeavyArmoredVehicle', 0) +
                                  mission_stats.get('killCannon', 0) +
                                  mission_stats.get('killAAAGun', 0) +
                                  mission_stats.get('killMachinegun', 0))
                    
                    naval_kills = (mission_stats.get('killLightShip', 0) +
                                 mission_stats.get('killDestroyerShip', 0) +
                                 mission_stats.get('killLargeCargoShip', 0))
                    
                    # Format flight time
                    flight_time_seconds = mission_stats.get('totalFlightTime', 0)
                    minutes = int(flight_time_seconds / 60)
                    seconds = int(flight_time_seconds % 60)
                    flight_time_str = f"{minutes:02d}:{seconds:02d}"
                    
                    # Get mission position in campaign
                    flown_missions = [m for m in mission_order if m in stats]
                    mission_position = flown_missions.index(mission_id) + 1 if mission_id in flown_missions else 0
                    
                    campaign_opportunities[mission_id] = {
                        'mission_id': mission_id,
                        'mission_number': f"{mission_position} of {len(mission_order)}",
                        'air_kills': air_kills,
                        'ground_kills': ground_kills,
                        'naval_kills': naval_kills,
                        'flight_time': flight_time_str,
                        'raw_stats': mission_stats
                    }
            
            # Only add campaign if it has opportunities
            if campaign_opportunities:
                opportunities[campaign_name] = campaign_opportunities
        
        return opportunities
    
    def create_backup(self) -> Optional[Path]:
        """
        Create timestamped backup and manage backup count
        
        Returns:
            Path to backup file, or None if failed
        """
        if not self.states_path.exists():
            print(f"⚠️  {self.states_path} not found - cannot backup")
            return None
        
        # Create backup with timestamp in SAME directory as campaignsstates.txt
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f'campaignsstates_{timestamp}.backup'
        backup_path = self.states_path.parent / backup_filename
        index_path = self.states_path.parent / "campaignsstates_hash_index.json"
        
        try:
            shutil.copy(self.states_path, backup_path)
            print(f"✓ Backup created: {backup_path}")
            
            # NEW: update hash index
            backup_hash = _md5_file(self.states_path)
            index = _load_hash_index(index_path)
            index[backup_hash] = timestamp
            with open(index_path, "w", encoding="utf-8") as f:
                json.dump(index, f, indent=2, sort_keys=True)
                
            # Cleanup old backups (keep only last 10)
            self.cleanup_old_backups()
            
            return backup_path
            
        except Exception as e:
            print(f"❌ Failed to create backup: {e}")
            return None
            
    
    def cleanup_old_backups(self):
        """Keep only the last N backups in game directory"""
        backup_pattern = 'campaignsstates_*.backup'
        backup_dir = self.states_path.parent
        backups = sorted(backup_dir.glob(backup_pattern))
        
        if len(backups) > self.max_backups:
            # Remove oldest backups
            to_remove = backups[:-self.max_backups]
            for backup in to_remove:
                try:
                    backup.unlink()
                    print(f"  Removed old backup: {backup.name}")
                except Exception as e:
                    print(f"  ⚠️  Could not remove {backup.name}: {e}")
    
    def delete_mission_entry(self, campaign_name: str, mission_id: str) -> bool:
        """
        Delete mission from completedMissionsByFileName in campaignsstates.txt
        
        SIMPLIFIED: Only removes mission from completedMissionsByFileName,
        leaving characterStatisticsByFileName intact. IL-2 will overwrite
        those stats when you replay the mission.
        
        Args:
            campaign_name: Campaign folder name
            mission_id: Mission identifier (e.g., "04")
            
        Returns:
            True if successful, False otherwise
        """
        if not self.states_path.exists():
            print(f"❌ {self.states_path} not found")
            return False
        
        print(f"\n{'='*70}")
        print(f"DELETING: {campaign_name} - Mission {mission_id}")
        print(f"{'='*70}")
        print(f"Target: completedMissionsByFileName entry only")
        
        # Create backup FIRST
        backup_path = self.create_backup()
        if not backup_path:
            print("❌ Cannot proceed without backup!")
            return False
        
        try:
            # Read file
            with open(self.states_path, 'rb') as f:
                content = f.read().decode('utf-8', errors='ignore')
            
            print(f"✓ Loaded {self.states_path.name} ({len(content)} chars)")
            
            # Find campaign section (between =kampagne= tags)
            campaign_start_tag = f'{campaign_name}='
            campaign_start = content.find(campaign_start_tag)
            
            if campaign_start == -1:
                print(f"❌ Campaign '{campaign_name}' not found in file")
                return False
            
            # Find end of campaign (next =kampagne= or end of file)
            next_campaign_start = content.find('=', campaign_start + len(campaign_start_tag))
            if next_campaign_start == -1:
                campaign_end = len(content)
            else:
                # Search for next campaign start tag
                temp_pos = campaign_start + len(campaign_start_tag)
                while temp_pos < len(content):
                    next_eq = content.find('=', temp_pos)
                    if next_eq == -1:
                        campaign_end = len(content)
                        break
                    # Check if this is a campaign tag (has another = after it)
                    if next_eq + 1 < len(content) and content[next_eq + 1] != '=':
                        # Check if this looks like start of campaign name
                        potential_end = content.find('=', next_eq + 1)
                        if potential_end != -1 and potential_end - next_eq < 50:
                            campaign_end = next_eq
                            break
                    temp_pos = next_eq + 1
                else:
                    campaign_end = len(content)
            
            # Extract campaign section
            campaign_section = content[campaign_start:campaign_end]
            before_campaign = content[:campaign_start]
            after_campaign = content[campaign_end:]
            
            print(f"✓ Found campaign section ({len(campaign_section)} chars)")
            
            # Find and delete from completedMissionsByFileName
            # Format: completedMissionsByFileName%3D05%253D1%252604%253D1%252607%253D1...
            #                                     ↑ first    ↑ second   ↑ third
            # - First mission: %3D{mission_id}%253D1
            # - Following missions: %2526{mission_id}%253D1
            patterns_to_try = [
                (f'%3D{mission_id}%253D1', 'first mission (starts with %3D)'),
                (f'%2526{mission_id}%253D1', 'following mission (starts with %2526)'),
            ]
            
            deleted = False
            for pattern, description in patterns_to_try:
                if pattern in campaign_section:
                    old_length = len(campaign_section)
                    campaign_section = campaign_section.replace(pattern, '', 1)  # Only first occurrence
                    new_length = len(campaign_section)
                    print(f"✓ Deleted mission {mission_id} from completedMissionsByFileName")
                    print(f"  Pattern: {pattern} ({description})")
                    print(f"  Removed: {old_length - new_length} chars")
                    deleted = True
                    break
            
            if not deleted:
                print(f"⚠️  Mission {mission_id} not found in completedMissionsByFileName")
                print(f"   Searched for patterns:")
                for p, desc in patterns_to_try:
                    print(f"     - {p} ({desc})")
                print(f"\n   This might mean:")
                print(f"   - Mission was never completed (not in completedMissionsByFileName)")
                print(f"   - Mission has different ID encoding")
                return False
            
            # Reconstruct file
            new_content = before_campaign + campaign_section + after_campaign
            
            print(f"\n{'='*70}")
            print(f"WRITING CHANGES")
            print(f"{'='*70}")
            print(f"Original file size: {len(content)} chars")
            print(f"New file size: {len(new_content)} chars")
            print(f"Difference: {len(content) - len(new_content)} chars")
            
            # Write back
            with open(self.states_path, 'wb') as f:
                f.write(new_content.encode('utf-8'))
            
            print(f"✓ Saved {self.states_path.name}")
            
            # Cleanup old backups
            self.cleanup_old_backups()
            
            # Verify deletion
            print(f"\n{'='*70}")
            print(f"VERIFICATION")
            print(f"{'='*70}")
            
            # Re-read and check
            with open(self.states_path, 'rb') as f:
                verify_content = f.read().decode('utf-8', errors='ignore')
            
            verification_failed = False
            for pattern, desc in patterns_to_try:
                if pattern in verify_content[campaign_start:campaign_start + len(campaign_section) + 1000]:
                    print(f"⚠️  WARNING: Pattern still found: {pattern}")
                    verification_failed = True
            
            if not verification_failed:
                print(f"✓ Verification passed - mission entry removed")
            
            print(f"\n{'='*70}")
            print(f"SUCCESS!")
            print(f"{'='*70}")
            print(f"Mission {mission_id} removed from completedMissionsByFileName")
            print(f"characterStatisticsByFileName remains intact")
            print(f"\nWhen you replay the mission:")
            print(f"  - IL-2 will let you fly it again")
            print(f"  - New stats will overwrite old stats")
            print(f"  - Mission will be re-added to completedMissionsByFileName on success")
            
            return True
            
        except Exception as e:
            print(f"\n❌ ERROR during deletion: {e}")
            print(f"   Restoring from backup...")
            
            # Restore backup
            try:
                shutil.copy2(backup_path, self.states_path)
                print(f"✓ Restored from backup: {backup_path.name}")
            except Exception as restore_error:
                print(f"❌ CRITICAL: Could not restore backup: {restore_error}")
                print(f"   Backup location: {backup_path}")
                print(f"   You may need to manually restore this file!")
            
            return False
            
    def verify_deletion(self, campaign_name: str, mission_id: str) -> bool:
        """
        Verify mission was actually deleted
        
        Args:
            campaign_name: Campaign folder name
            mission_id: Mission number
            
        Returns:
            True if mission is gone, False if still exists
        """
        try:
            # Simple verification: read file and check if mission ID still exists
            with open(self.states_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Find campaign section
            campaign_pattern = f'campaigns/{campaign_name}='
            if campaign_pattern not in content:
                print(f"⚠️  Campaign {campaign_name} not found in file")
                return False
            
            # Extract campaign section
            start = content.index(campaign_pattern)
            # Find next campaign or end of file
            next_campaign = content.find('&campaigns/', start + 1)
            if next_campaign == -1:
                campaign_section = content[start:]
            else:
                campaign_section = content[start:next_campaign]
            
            # Decode and check if mission exists
            decoded = urllib.parse.unquote(campaign_section)
            
            # Mission should NOT exist in the characterStatisticsByFileName section
            # Pattern: &{mission_id}= or ={mission_id}=
            mission_patterns = [
                f'&{mission_id}=',
                f'={mission_id}=',
            ]
            
            for pattern in mission_patterns:
                if pattern in decoded:
                    print(f"⚠️  Mission {mission_id} still found with pattern: {pattern}")
                    return False
            
            # Double check with URL-encoded version
            encoded_patterns = [
                urllib.parse.quote(f'&{mission_id}='),
                urllib.parse.quote(f'={mission_id}='),
            ]
            
            for pattern in encoded_patterns:
                if pattern in campaign_section:
                    print(f"⚠️  Mission {mission_id} still found (encoded)")
                    return False
            
            return True
            
        except Exception as e:
            print(f"⚠️  Could not verify deletion: {e}")
            import traceback
            traceback.print_exc()
            return False


class CleanupGUI:
    """Tkinter GUI for mission cleanup"""
    
    def __init__(self, opportunities: Dict):
        """
        Initialize GUI
        
        Args:
            opportunities: Dict of campaigns with missions needing cleanup
                          Format: {campaign_name: {mission_id: details, ...}}
        """
        self.opportunities = opportunities
        self.selected = {}  # "campaign_name::mission_id" -> selected (bool)
        self.ignore_flags = {}  # "campaign_name::mission_id" -> ignore flag (bool)
        self.cleanup_tool = MissionCleanup()
        
        self.root = tk.Tk()
        self.root.title("IL-2 Campaign Mission Cleanup")
        self.root.geometry("800x600")
        
        self.create_widgets()
    
    def create_widgets(self):
        """Create GUI widgets"""
        
        # Title
        title_frame = ttk.Frame(self.root, padding="10")
        title_frame.pack(fill=tk.X)
        
        ttk.Label(title_frame, text="Campaign Mission Cleanup",
                 font=('Arial', 14, 'bold')).pack()
        
        ttk.Label(title_frame, 
                 text="Found unsuccessful missions that can be replayed:",
                 font=('Arial', 10)).pack()
        
        # Scrollable frame for campaigns
        canvas_frame = ttk.Frame(self.root)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        canvas = tk.Canvas(canvas_frame)
        scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor=tk.NW)
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Create campaign cards - now handling multiple missions per campaign
        for campaign_name, missions in self.opportunities.items():
            # If missions is a dict (new format), iterate over it
            if isinstance(missions, dict):
                for mission_id, data in missions.items():
                    self.create_mission_card(scrollable_frame, campaign_name, mission_id, data)
            else:
                # Old format compatibility (single mission)
                self.create_mission_card(scrollable_frame, campaign_name, missions['mission_id'], missions)
        
        # Buttons
        button_frame = ttk.Frame(self.root, padding="10")
        button_frame.pack(fill=tk.X)
        
        ttk.Button(button_frame, text="Apply Changes", 
                  command=self.on_apply, width=20).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", 
                  command=self.on_cancel, width=20).pack(side=tk.LEFT, padx=5)
        
        # Note
        note_frame = ttk.Frame(self.root, padding="10")
        note_frame.pack(fill=tk.X)
        
        ttk.Label(note_frame, 
                 text="Note: Backup will be created automatically before deletion. "
                      "Ignored missions can be managed in cleanup_ignored_missions.json",
                 font=('Arial', 9, 'italic'),
                 foreground='gray').pack()
    
    
    def create_mission_card(self, parent, campaign_name: str, mission_id: str, data: Dict):
        """Create a card for one mission"""
        
        card = ttk.LabelFrame(parent, text=f"{campaign_name.upper()} - Mission {mission_id}", padding="10")
        card.pack(fill=tk.X, padx=5, pady=5)
        
        # Mission info
        info_text = f"Mission Position: {data['mission_number']}"
        ttk.Label(card, text=info_text, font=('Arial', 10, 'bold')).pack(anchor=tk.W)
        
        ttk.Label(card, text="Status: ⚠️  Unsuccessful (takeOffStatus = 1)",
                 foreground='orange').pack(anchor=tk.W)
        
        # Stats
        stats_text = f"Result: {data['air_kills']} air, {data['ground_kills']} ground"
        if data['naval_kills'] > 0:
            stats_text += f", {data['naval_kills']} naval"
        stats_text += f" | Flight Time: {data['flight_time']}"
        
        ttk.Label(card, text=stats_text).pack(anchor=tk.W)
        
        # Warning
        ttk.Label(card, 
                 text="⚠️  This mission entry is locked. Delete it to replay for a better result.",
                 foreground='red',
                 font=('Arial', 9)).pack(anchor=tk.W, pady=(5, 0))
        
        # Separator
        ttk.Separator(card, orient='horizontal').pack(fill=tk.X, pady=8)
        
        # Action frame for checkboxes
        action_frame = ttk.Frame(card)
        action_frame.pack(fill=tk.X, anchor=tk.W)
        
        # Unique key for this mission
        mission_key = f"{campaign_name}::{mission_id}"
        
        # Delete checkbox
        delete_var = tk.BooleanVar(value=False)
        self.selected[mission_key] = delete_var
        
        ttk.Checkbutton(action_frame, 
                       text=f"Delete Mission {mission_id} entry",
                       variable=delete_var).pack(anchor=tk.W)
        
        # Ignore checkbox (with distinctive styling)
        ignore_var = tk.BooleanVar(value=False)
        self.ignore_flags[mission_key] = ignore_var
        
        ignore_frame = ttk.Frame(action_frame)
        ignore_frame.pack(anchor=tk.W, pady=(5, 0))
        
        ignore_cb = ttk.Checkbutton(ignore_frame, 
                                   text="Don't ask me about this mission again",
                                   variable=ignore_var)
        ignore_cb.pack(side=tk.LEFT)
        
        # Info icon/text
        ttk.Label(ignore_frame, 
                 text="ℹ️",
                 foreground='blue',
                 cursor='hand2').pack(side=tk.LEFT, padx=(5, 0))
        
        # Tooltip would be nice here but keeping it simple
        ttk.Label(ignore_frame,
                 text="(Hide this mission from future checks)",
                 font=('Arial', 8, 'italic'),
                 foreground='gray').pack(side=tk.LEFT, padx=(2, 0))
    
    def on_apply(self):
        """Handle Apply button"""
        
        # Get selected missions for deletion and ignoring
        to_delete = []
        to_ignore = []
        
        for mission_key, delete_var in self.selected.items():
            if delete_var.get():
                # Parse "campaign_name::mission_id"
                campaign_name, mission_id = mission_key.split('::', 1)
                # Find mission data
                if campaign_name in self.opportunities:
                    missions = self.opportunities[campaign_name]
                    if isinstance(missions, dict) and mission_id in missions:
                        to_delete.append((campaign_name, mission_id, missions[mission_id]))
                    elif not isinstance(missions, dict):
                        # Old format compatibility
                        to_delete.append((campaign_name, mission_id, missions))
        
        for mission_key, ignore_var in self.ignore_flags.items():
            if ignore_var.get():
                campaign_name, mission_id = mission_key.split('::', 1)
                if campaign_name in self.opportunities:
                    missions = self.opportunities[campaign_name]
                    if isinstance(missions, dict) and mission_id in missions:
                        to_ignore.append((campaign_name, mission_id, missions[mission_id]))
                    elif not isinstance(missions, dict):
                        to_ignore.append((campaign_name, mission_id, missions))
        
        if not to_delete and not to_ignore:
            messagebox.showinfo("No Changes", "No missions selected for cleanup or ignore")
            return
        
        # Build confirmation message
        msg_parts = []
        
        if to_delete:
            msg_parts.append(f"Delete {len(to_delete)} mission entr{'y' if len(to_delete) == 1 else 'ies'}:")
            for campaign_name, mission_id, data in to_delete:
                msg_parts.append(f"  • {campaign_name} - Mission {mission_id}")
        
        if to_ignore:
            msg_parts.append("")
            msg_parts.append(f"Hide {len(to_ignore)} mission{'s' if len(to_ignore) > 1 else ''} from future checks:")
            for campaign_name, mission_id, data in to_ignore:
                msg_parts.append(f"  • {campaign_name} - Mission {mission_id}")
        
        if to_delete:
            msg_parts.append("")
            msg_parts.append("Backup will be created automatically.")
        
        msg = "\n".join(msg_parts)
        
        if not messagebox.askyesno("Confirm Changes", msg):
            return
        
        # Process ignore flags FIRST (before any deletion)
        for campaign_name, mission_id, data in to_ignore:
            add_to_ignored(campaign_name, mission_id)
        
        # Perform deletions
        success_count = 0
        if to_delete:
            for campaign_name, mission_id, data in to_delete:
                if self.cleanup_tool.delete_mission_entry(campaign_name, mission_id):
                    success_count += 1
        
        # Build result message
        result_parts = []
        
        if to_delete:
            if success_count == len(to_delete):
                result_parts.append(f"✓ Successfully deleted {success_count} mission entr{'y' if success_count == 1 else 'ies'}!")
                result_parts.append("You can now replay these missions for better results.")
            else:
                result_parts.append(f"⚠️  Deleted {success_count} of {len(to_delete)} missions.")
                result_parts.append("Check console for details.")
        
        if to_ignore:
            result_parts.append("")
            result_parts.append(f"✓ Added {len(to_ignore)} mission{'s' if len(to_ignore) > 1 else ''} to ignore list.")
            result_parts.append("You won't be asked about them again.")
        
        result_msg = "\n".join(result_parts)
        
        if success_count == len(to_delete) or not to_delete:
            messagebox.showinfo("Success", result_msg)
        else:
            messagebox.showwarning("Partial Success", result_msg)
        
        # ✅ Automatically re-decode campaignsstates.txt after all deletions
        if success_count > 0:
            print("\nRe-decoding campaignsstates.txt to update campaigns_decoded.json...")
            try:
                # Copy the in-game campaignsstates.txt to local working directory
                source_file = self.cleanup_tool.states_path
                local_copy = Path.cwd() / "campaignsstates.txt"

                if source_file.exists():
                    shutil.copy2(source_file, local_copy)
                    print(f"✓ Copied {source_file} → {local_copy}")
                else:
                    print(f"⚠️ Source file not found at {source_file}, skipping copy")
                    
                # Decode using local file    
                from decode_campaign_usersave1 import main as decode_campaignsstates
                success = decode_campaignsstates()
                if success:
                    print("✓ campaigns_decoded.json successfully regenerated.")
                else:
                    print("⚠️ Decoder reported failure; campaigns_decoded.json may be outdated.")
            except Exception as e:
                print(f"⚠️ Could not re-decode campaigns_decoded.json: {e}")
                
        self.root.destroy()
    
    def on_cancel(self):
        """Handle Cancel button"""
        self.root.destroy()
    
    def run(self):
        """Run the GUI"""
        self.root.mainloop()


def startup_cleanup_check():
    """
    Run at tracker startup to check for cleanup opportunities
    
    Returns:
        True if cleanup was performed, False otherwise
    """
    print("\n" + "="*70)
    print("SCANNING FOR UNSUCCESSFUL MISSIONS...")
    print("="*70)
    
    cleanup = MissionCleanup()
    opportunities = cleanup.find_cleanup_opportunities()
    
    # Show info about ignored missions (if any exist)
    ignored = load_ignored_missions()
    if ignored:
        print(f"ℹ️  {len(ignored)} mission(s) currently in ignore list")
        print(f"   (To manage: edit cleanup_ignored_missions.json)")
        print()
    
    if not opportunities:
        print("✓ All campaigns clean - no unsuccessful missions found")
        return False
    
    # Count total missions across all campaigns
    total_missions = sum(len(missions) if isinstance(missions, dict) else 1 
                        for missions in opportunities.values())
    
    print(f"\n⚠️  Found {total_missions} unsuccessful mission(s) across {len(opportunities)} campaign(s):")
    for campaign_name, missions in opportunities.items():
        if isinstance(missions, dict):
            for mission_id in missions.keys():
                print(f"  • {campaign_name} - Mission {mission_id}")
        else:
            # Old format compatibility
            print(f"  • {campaign_name} - Mission {missions['mission_id']}")
    
    # Show GUI
    gui = CleanupGUI(opportunities)
    gui.run()
    
    return True


if __name__ == '__main__':
    startup_cleanup_check()
