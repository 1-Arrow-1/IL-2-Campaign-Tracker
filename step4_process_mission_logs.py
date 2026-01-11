#!/usr/bin/env python3
"""
IL-2 Campaign Progress Tracker - Step 4: Mission Log Processor

Processes mission report files (.mlg) from FlightLogs folder:
1. Finds .mlg files for completed missions
2. Converts .mlg to .txt using mlg2txt
3. Parses .txt to .events.json using il2_mission_debrief
4. Returns debriefing data for HTML generation

Usage:
    from step4_process_mission_logs import MissionLogProcessor
    processor = MissionLogProcessor(game_directory)
    debriefings = processor.get_all_debriefings(campaign_name, completed_missions)
"""

import re
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import shutil

from utils.logging import get_logger, log_message
from utils.pathing import get_base_path
from utils.formatting import safe_campaign_filename

logger = get_logger(__name__)

class MissionLogProcessor:
    def __init__(
        self,
        game_directory: str,
        verbose: bool = False,
        snapshot_dt=None,
        max_mlg_scan: int = 3000,
    ):
        """
        Initialize mission log processor
        
        Args:
            game_directory: Path to IL-2 game directory
            verbose: Enable detailed logging
        """
        self.game_directory = Path(game_directory)
        self.flight_logs_dir = self.game_directory / "data" / "FlightLogs"
        self.verbose = verbose
        self.snapshot_dt = snapshot_dt
        self.max_mlg_scan = max_mlg_scan
        self._mlg_scan_warning_emitted = False
        
        # Working directory for temporary files
        self.work_dir = Path.cwd()
        
        # Import required modules
        self._import_modules()
        
        if self.verbose:
            log_message(logger, f"MissionLogProcessor initialized")
            log_message(logger, f"  Game directory: {self.game_directory}")
            log_message(logger, f"  FlightLogs: {self.flight_logs_dir}")
            log_message(logger, f"  Exists: {self.flight_logs_dir.exists()}")

    def _get_aircraft_cache_path(self, campaign_name: str) -> Path:
        safe_name = safe_campaign_filename(campaign_name)
        return get_base_path(__file__) / "reports" / safe_name / "mission_aircraft_map.json"

    def _load_aircraft_cache(self, campaign_name: str) -> Dict:
        cache_path = self._get_aircraft_cache_path(campaign_name)
        if not cache_path.exists():
            return {"campaign_name": campaign_name, "missions": {}}

        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            if self.verbose:
                log_message(logger, f"  ⚠️  Could not read aircraft cache: {exc}")
            return {"campaign_name": campaign_name, "missions": {}}

        if isinstance(data, dict) and "missions" in data and isinstance(data["missions"], dict):
            data.setdefault("campaign_name", campaign_name)
            return data

        if isinstance(data, dict):
            return {"campaign_name": campaign_name, "missions": data}

        return {"campaign_name": campaign_name, "missions": {}}

    def _write_aircraft_cache(self, campaign_name: str, cache_data: Dict) -> None:
        cache_path = self._get_aircraft_cache_path(campaign_name)
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
        except OSError as exc:
            if self.verbose:
                log_message(logger, f"  ⚠️  Could not write aircraft cache: {exc}")

    def _should_update_aircraft_cache(self, existing_entry: Optional[Dict], new_entry: Dict) -> bool:
        if not existing_entry:
            return True

        def parse_timestamp(value: Optional[str]) -> Optional[datetime]:
            if not value:
                return None
            try:
                return datetime.strptime(value, "%Y-%m-%d_%H-%M-%S")
            except ValueError:
                return None

        existing_ts = parse_timestamp(existing_entry.get("timestamp"))
        new_ts = parse_timestamp(new_entry.get("timestamp"))

        if existing_ts and new_ts:
            if new_ts > existing_ts:
                return True
            if new_ts < existing_ts:
                return False

        existing_mtime = existing_entry.get("mlg_mtime", 0)
        new_mtime = new_entry.get("mlg_mtime", 0)
        if new_mtime and existing_mtime:
            return new_mtime > existing_mtime

        return bool(new_entry.get("mlg_filename")) and new_entry.get("mlg_filename") != existing_entry.get("mlg_filename")

    def _update_aircraft_cache(
        self,
        campaign_name: str,
        mission_id: str,
        aircraft: str,
        mlg_file: Path,
        timestamp: Optional[str],
    ) -> None:
        cache = self._load_aircraft_cache(campaign_name)
        missions = cache.setdefault("missions", {})

        new_entry = {
            "campaign_name": campaign_name,
            "mission_id": mission_id,
            "aircraft": aircraft,
            "timestamp": timestamp,
            "mlg_filename": mlg_file.name,
            "mlg_mtime": mlg_file.stat().st_mtime,
            "mlg_size": mlg_file.stat().st_size,
            "updated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        }

        existing_entry = missions.get(mission_id)
        if self._should_update_aircraft_cache(existing_entry, new_entry):
            missions[mission_id] = new_entry
            cache["campaign_name"] = campaign_name
            cache["updated_at"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
            self._write_aircraft_cache(campaign_name, cache)
            if self.verbose:
                log_message(logger, f"  ✓ Cached aircraft for {mission_id}: {aircraft}")
    
    def _import_modules(self):
        """Import il2_mission_debrief module (mlg2txt used via subprocess only)"""
        # Note: mlg2txt is NOT imported because it runs argparse at module level
        # We use subprocess instead
        self.mlg2txt = None
        
        try:
            import il2_mission_debrief
            self.debrief_parser = il2_mission_debrief
        except ImportError as e:
            log_message(logger, f"Warning: Could not import il2_mission_debrief: {e}")
            self.debrief_parser = None
    
    def get_all_debriefings(self, campaign_name: str, completed_missions: List[str]) -> Dict:
        """
        Get debriefing data for all completed missions in a campaign
        
        Args:
            campaign_name: Name of campaign (e.g., "kerch")
            completed_missions: List of completed mission IDs (e.g., ["01", "02", "08"])
        
        Returns:
            Dict mapping mission_id -> debriefing_data
            {
                "08": {
                    "aircraft": "Bf 109 G-6",
                    "duration": "01:17:50",
                    "air_kills": 4,
                    "ground_kills": 3,
                    "events": [...],
                    "timestamp": "2025-12-22_15-47-53"
                }
            }
        """
        if not self.flight_logs_dir.exists():
            if self.verbose:
                log_message(logger, f"FlightLogs directory not found: {self.flight_logs_dir}")
            return {}
        
        debriefings = {}
        
        for mission_id in completed_missions:
            try:
                log_message(logger, f"  Looking for debriefing: {campaign_name}/{mission_id}")
                debriefing = self.get_mission_debriefing(campaign_name, mission_id)
                if debriefing:
                    debriefings[mission_id] = debriefing
                    log_message(logger, f"    ✓ Debriefing loaded for Mission {mission_id}")
                else:
                    log_message(logger, f"    ⚠️  No debriefing data returned for Mission {mission_id}")
            except Exception as e:
                log_message(logger, f"    ❌ Error processing mission {campaign_name}/{mission_id}: {e}")
                if self.verbose:
                    import traceback
                    traceback.print_exc()
                continue
        
        return debriefings
    
    def get_mission_debriefing(self, campaign_name: str, mission_id: str) -> Optional[Dict]:
        """
        Get debriefing data for a single mission
        
        Args:
            campaign_name: Campaign name (e.g., "kerch")
            mission_id: Mission ID (e.g., "08" or "1943-07-04a-FW190-A5U17-IISG1")
        
        Returns:
            Debriefing data dict or None if not found/failed
        """
        # Find newest .mlg file for this mission
        mlg_file = self._find_newest_mlg(campaign_name, mission_id)
        
        if not mlg_file:
            if self.verbose:
                log_message(logger, f"  No .mlg file found for {campaign_name}/{mission_id}")
            return None
        
        if self.verbose:
            log_message(logger, f"  Found .mlg: {mlg_file.name}")
        
        # Process pipeline: .mlg → .txt → .json
        try:
            # Step 1: Convert .mlg to .txt (creates ONE complete file without --split)
            txt_file = self._mlg_to_txt(mlg_file)
            if not txt_file or not txt_file.exists():
                if self.verbose:
                    log_message(logger, f"  Failed to convert .mlg to .txt")
                return None
            
            # Step 2: Parse .txt to .events.json
            json_file = self._txt_to_json(txt_file)
            if not json_file or not json_file.exists():
                if self.verbose:
                    log_message(logger, f"  Failed to parse .txt to .json")
                return None
            
            # Step 3: Load and return JSON data
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Add metadata
            timestamp = self._extract_timestamp(mlg_file.name)
            data['timestamp'] = timestamp
            data['mission_id'] = mission_id

            aircraft = data.get("player", {}).get("aircraft")
            if aircraft:
                self._update_aircraft_cache(
                    campaign_name=campaign_name,
                    mission_id=mission_id,
                    aircraft=aircraft,
                    mlg_file=mlg_file,
                    timestamp=timestamp,
                )
            
            if self.verbose:
                log_message(logger, f"  ✓ Debriefing loaded: {data['summary']}")
            
            return data
            
        except Exception as e:
            log_message(logger, f"  Error processing {mlg_file.name}: {e}")
            if self.verbose:
                import traceback
                traceback.print_exc()
            return None
    
    def _find_newest_mlg(self, campaign_name: str, mission_id: str) -> Optional[Path]:
        """
        Find newest .mlg file for a specific mission
        
        Searches for .mlg files containing "campaigns/<campaign>/<mission>.msnbin"
        and returns the one with the newest timestamp.
        
        Args:
            campaign_name: Campaign name (lowercase)
            mission_id: Mission ID (e.g., "08" or "1940-11-27a-BoB I JG51-BF109F1-fighter-sweep")
        
        Returns:
            Path to newest .mlg file or None
        """
        import urllib.parse
        
        # Pattern to search for in .mlg files
        # Handle both .msnbin and .cmpbin
        # Also handle URL-encoded variants (spaces as %20, etc.)
        patterns = []
        
        # Normal version (decoded)
        patterns.append(f"campaigns/{campaign_name}/{mission_id}.msnbin".encode('utf-8'))
        patterns.append(f"campaigns/{campaign_name}/{mission_id}.cmpbin".encode('utf-8'))
        
        # URL-encoded version (if mission_id contains spaces or special chars)
        mission_id_encoded = urllib.parse.quote(mission_id)
        if mission_id_encoded != mission_id:
            patterns.append(f"campaigns/{campaign_name}/{mission_id_encoded}.msnbin".encode('utf-8'))
            patterns.append(f"campaigns/{campaign_name}/{mission_id_encoded}.cmpbin".encode('utf-8'))
        
        matching_files = []
        
        # Scan all .mlg files (guard against huge directories)
        mlg_files = list(self.flight_logs_dir.glob("*.mlg"))
        if self.max_mlg_scan > 0 and len(mlg_files) > self.max_mlg_scan:
            if not self._mlg_scan_warning_emitted:
                log_message(logger, 
                    f"  ⚠️  Found {len(mlg_files)} mission logs; "
                    f"scanning newest {self.max_mlg_scan} files only"
                )
                self._mlg_scan_warning_emitted = True
            mlg_files = sorted(
                mlg_files,
                key=lambda path: path.stat().st_mtime,
                reverse=True,
            )[: self.max_mlg_scan]

        for mlg_file in mlg_files:
            try:
                # Read file and search for campaign mission pattern
                with open(mlg_file, "rb") as f:
                    content = f.read()

                # Check if this .mlg contains our mission
                if any(pattern in content for pattern in patterns):
                    # Extract timestamp from filename (string like "2025-12-22_15-47-53")
                    timestamp = self._extract_timestamp(mlg_file.name)
                    if timestamp:
                        # NEW: parse to datetime for correct comparisons/sorting
                        try:
                            ts_dt = datetime.strptime(timestamp, "%Y-%m-%d_%H-%M-%S")
                        except ValueError:
                            if self.verbose:
                                log_message(logger, f"    Skipping {mlg_file.name}: invalid timestamp format '{timestamp}'")
                            continue

                        matching_files.append((mlg_file, ts_dt))
                        if self.verbose:
                            log_message(logger, f"    Found: {mlg_file.name} ({timestamp})")

            except Exception as e:
                if self.verbose:
                    log_message(logger, f"    Error reading {mlg_file.name}: {e}")
                continue

        if not matching_files:
            return None

        # NEW: if snapshot_dt is provided, prefer newest file <= snapshot
        if self.snapshot_dt is not None:
            eligible = [x for x in matching_files if x[1] <= self.snapshot_dt]
            if eligible:
                eligible.sort(key=lambda x: x[1], reverse=True)
                return eligible[0][0]

        # Fallback: existing behavior (newest overall)
        matching_files.sort(key=lambda x: x[1], reverse=True)
        newest = matching_files[0][0]

        if self.verbose and len(matching_files) > 1:
            log_message(logger, f"    Multiple versions found, using newest: {newest.name}")

        return newest
    
    def _extract_timestamp(self, filename: str) -> Optional[str]:
        """
        Extract timestamp from .mlg filename
        
        Example: "missionReport(2025-12-22_15-47-53).mlg" → "2025-12-22_15-47-53"
        
        Returns:
            Timestamp string or None if pattern doesn't match
        """
        match = re.search(r'(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})', filename)
        return match.group(1) if match else None
    
    def _mlg_to_txt(self, mlg_file: Path) -> Optional[Path]:
        """
        Convert .mlg to .txt using mlg2txt module via subprocess
        
        Note: mlg2txt ALWAYS creates files with [N] suffix in the filename.
        Without --split: Creates ONE file named [0].txt with all events.
        With --split: Creates MULTIPLE files [0].txt, [1].txt, [2].txt with fragmented events.
        
        Args:
            mlg_file: Path to .mlg file
        
        Returns:
            Path to generated .txt file or None
        """
        try:
            base_name = mlg_file.stem  # Without .mlg
            # mlg2txt ALWAYS creates [0].txt, even without --split flag
            txt_file = mlg_file.parent / f"{base_name}[0].txt"
            
            # Check if already converted AND if .txt is newer than .mlg
            if txt_file.exists():
                # Compare modification times
                mlg_mtime = mlg_file.stat().st_mtime
                txt_mtime = txt_file.stat().st_mtime
                
                if txt_mtime >= mlg_mtime:
                    # TXT is up-to-date
                    if self.verbose:
                        log_message(logger, f"    Using existing .txt: {txt_file.name}")
                    return txt_file
                else:
                    # MLG is newer - need to reconvert
                    if self.verbose:
                        log_message(logger, f"    .mlg is newer than .txt, reconverting...")
            
            if self.verbose:
                log_message(logger, f"    Converting .mlg to .txt...")
            
            # Find mlg2txt executable
            import sys
            
            if getattr(sys, 'frozen', False):
                # Running as compiled EXE
                # mlg2txt.exe should be in same directory as the EXE
                exe_dir = get_base_path(__file__)
                mlg2txt_executable = exe_dir / 'mlg2txt.exe'
                
                if not mlg2txt_executable.exists():
                    log_message(logger, f"    Error: mlg2txt.exe not found at {mlg2txt_executable}")
                    log_message(logger, f"    Please ensure mlg2txt.exe is in the same folder as IL2_CampaignTracker.exe")
                    return None
            else:
                # Running as Python script
                # Use mlg2txt.py with Python
                mlg2txt_executable = get_base_path(__file__) / 'mlg2txt.py'
                
                if not mlg2txt_executable.exists():
                    log_message(logger, f"    Error: mlg2txt.py not found at {mlg2txt_executable}")
                    return None
            
            # Use subprocess to run mlg2txt
            import subprocess
            import sys
            
            # Determine command based on whether we're running as EXE or script
            if getattr(sys, 'frozen', False):
                # Running as EXE - call mlg2txt.exe directly
                cmd = [str(mlg2txt_executable), '--output', str(mlg_file.parent), str(mlg_file)]
            else:
                # Running as script - call mlg2txt.py with Python
                cmd = [sys.executable, str(mlg2txt_executable), '--output', str(mlg_file.parent), str(mlg_file)]
            
            # Run conversion
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            
            if result.returncode != 0:
                log_message(logger, f"    mlg2txt failed: {result.stderr}")
                return None
            
            # Check if file was created
            if txt_file.exists():
                if self.verbose:
                    log_message(logger, f"    ✓ Created: {txt_file.name}")
                return txt_file
            else:
                log_message(logger, f"    Error: Expected output not found: {txt_file}")
                return None
                
        except Exception as e:
            log_message(logger, f"    Error in mlg2txt conversion: {e}")
            if self.verbose:
                import traceback
                traceback.print_exc()
            return None
    
    def _txt_to_json(self, txt_file: Path) -> Optional[Path]:
        """
        Parse .txt to .events.json using il2_mission_debrief
        
        Args:
            txt_file: Path to .txt file
        
        Returns:
            Path to generated .events.json file
        """
        if not self.debrief_parser:
            log_message(logger, "Error: il2_mission_debrief module not available")
            return None
        
        try:
            # Expected output: same name with .events.json
            json_file = txt_file.with_suffix('.events.json')
            
            # ALWAYS regenerate JSON to ensure it reflects the latest mission report
            # This is important when user re-flies missions (e.g., after being shot down)
            if self.verbose:
                if json_file.exists():
                    log_message(logger, f"    Regenerating .json from latest report...")
                else:
                    log_message(logger, f"    Parsing .txt to .json...")
            
            # Create parser and process
            parser = self.debrief_parser.MissionDebriefParser(str(txt_file))
            stats = parser.parse()
            parser.to_json(str(json_file))
            
            if json_file.exists():
                if self.verbose:
                    log_message(logger, f"    ✓ Created: {json_file.name}")
                return json_file
            else:
                log_message(logger, f"    Error: JSON output not created")
                return None
                
        except Exception as e:
            log_message(logger, f"    Error in debrief parsing: {e}")
            if self.verbose:
                import traceback
                traceback.print_exc()
            return None


def main():
    """Test/demo function"""
    import argparse
    
    # Parse OUR arguments BEFORE importing mlg2txt (which has its own argparser)
    parser = argparse.ArgumentParser(description="Process IL-2 mission logs")
    parser.add_argument("game_directory", help="Path to IL-2 game directory")
    parser.add_argument("campaign", help="Campaign name (e.g., kerch)")
    parser.add_argument("missions", nargs='+', help="Mission IDs (e.g., 01 02 08)")
    parser.add_argument("-v", "--verbose", action='store_true', help="Verbose output")
    
    args = parser.parse_args()
    
    log_message(logger, "="*70)
    log_message(logger, "IL-2 MISSION LOG PROCESSOR - Step 4")
    log_message(logger, "="*70)
    log_message(logger)
    
    processor = MissionLogProcessor(args.game_directory, verbose=args.verbose)
    debriefings = processor.get_all_debriefings(args.campaign, args.missions)
    
    log_message(logger)
    log_message(logger, f"Processed {len(debriefings)} mission(s):")
    for mission_id, data in debriefings.items():
        log_message(logger, f"  Mission {mission_id}:")
        log_message(logger, f"    Aircraft: {data['player']['aircraft']}")
        log_message(logger, f"    Duration: {data['summary']['flight_duration']}")
        log_message(logger, f"    Air Kills: {data['summary']['air_kills']}")
        log_message(logger, f"    Ground Kills: {data['summary']['ground_kills']}")
        log_message(logger, f"    Status: {data['summary']['final_state']}")


if __name__ == "__main__":
    main()
