"""
il2_mission_debrief_v2_2.py
---------------------------
IL-2 Mission Debrief Parser — refined kill attribution

✅ Fix: indirect (AID:-1) kill attribution based on damage share ≥ 80 %
✅ Fix: no BotPilot/BotGunner duplicates
✅ Fix: proper aircraft name extraction
✅ Direct & indirect kill logic integrated
✅ Tracker-ready JSON output
"""

import os, re, json, yaml
from collections import defaultdict
from pathlib import Path

from utils.logging import get_logger, log_message
from utils.pathing import get_base_path

logger = get_logger(__name__)

# Maximum gap between the last player-damage hit on a target and an AID:-1
# AType:3 destruction for the kill to still be credited to the player.
# 600 s × 50 ticks/s = 30 000 ticks.  Adjust or set to 0 to disable.
_DELAYED_KILL_MAX_TICKS = 600 * 50  # 30 000 ticks (600 seconds)

# ==========================================================
# === GameObject ==========================================
# ==========================================================
class GameObject:
    _category_config = None
    def __init__(self, gid, name, type_, country):
        self.id = gid
        self.name = name
        
        # Detect and clean static planes
        self.is_static = False
        if type_ and type_.lower().startswith('static_'):
            self.is_static = True
            # Clean name: "static_il2[9337,0]" → "il2"
            clean_type = type_.replace('static_', '', 1).split('[')[0]
            self.type = clean_type
        else:
            self.type = type_
        
        self.country = country
        self.category = self.classify_type(type_)  # Use original type_ for categorization
        self.state = "Alive"
        self.time_of_kill = None
        self.altitude = None  # Altitude when destroyed

    @classmethod
    def _load_config(cls):
        """Load category definitions once from YAML."""
        if cls._category_config is None:
            # Try external file first (for user editing), then embedded
            import sys
            cfg_path = get_base_path(__file__) / "object_categories.yaml"
            
            if getattr(sys, 'frozen', False) and not cfg_path.exists():
                # Fallback to embedded
                cfg_path = Path(sys._MEIPASS) / "object_categories.yaml"
            
            try:
                with open(cfg_path, encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    cls._category_config = data.get("categories", {})
                    cls._exclude_config = [x.lower() for x in data.get("exclude", [])]
            except Exception:
                cls._category_config = {}
                cls._exclude_config = []

    @classmethod
    def classify_type(cls, type_):
        """Classify an object using YAML configuration with EXACT matching."""
        cls._load_config()
        s = (type_ or "").lower().strip()
        
        # For static planes, remove coordinates for matching but keep static_ prefix
        # e.g., "static_il2[9337,0]" → "static_il2"
        if s.startswith('static_') and '[' in s:
            s = s.split('[')[0]
        
        # Exclude unwanted object types (still using substring for exclude)
        if any(x in s for x in getattr(cls, "_exclude_config", [])):
            return "Excluded"
        
        # EXACT match: Check if the object name exactly matches any category entry
        for cat, keywords in cls._category_config.items():
            if s in [k.lower() for k in keywords]:
                return cat
        
        return "Unknown"


# ==========================================================
# === MissionStats =========================================
# ==========================================================
class MissionStats:
    def __init__(self):
        self.player_id = None
        self.player_name = None
        self.player_aircraft = None
        self.player_pid = None  # Player pilot ID
        self.player_plid = None  # Player aircraft ID
        self.player_country = None  # Player's country code for territory classification
        self.objects = {}
        self.hits = []      # {attacker,target,damage,time}
        self.kills = []     # GameObject list
        self.events = []
        self.wounded = False
        self.total_damage_taken = 0.0  # DEPRECATED - kept for compatibility
        self.total_aircraft_damage = 0.0  # Cumulative damage to aircraft
        self.total_pilot_damage = 0.0     # Cumulative damage to pilot (for wounded status)
        self.landed = False
        self.crashed = False
        self.pilot_separation_time = None  # Time (ticks) when pilot separated from aircraft (bailout)
        self.pilot_separation_pos = None   # Position (x,y,z) at bailout for territory check
        self._pilot_touchdown_time = None  # Time (ticks) when pilot touched down after bailout
        self._pilot_touchdown_pos = None   # Position (x,y,z) of pilot touchdown
        self.final_state = "Alive"
        self.takeoff_time = None
        self.landing_time = None
        self.mission_end_time = None  # Used for flight duration calc (no event emitted)
        self.flight_duration = None
        # Territory/influence polygons: {country_code: [polygon1, polygon2, ...]}
        # where each polygon is a list of (x,z) tuples
        self.influence_polygons = defaultdict(list)
        # Mapping from AID to country for AType:13/14 linkage
        self._influence_aid_to_country = {}

    def add_object(self, obj): self.objects[obj.id] = obj
    def add_hit(self, a, t, d, ts): self.hits.append({"attacker": a, "target": t, "damage": d, "time": ts})
    def add_kill(self, tid, ts):
        obj = self.objects.get(tid)
        if obj and obj.category == "Excluded":
            return  # ignore silently
        if tid in self.objects:
            obj = self.objects[tid]
            obj.state, obj.time_of_kill = "Destroyed", ts
            if obj not in self.kills: self.kills.append(obj)


# ==========================================================
# === MissionDebriefParser ================================
# ==========================================================
class MissionDebriefParser:
    def __init__(self, path, verbose=False):
        self.path = path
        self.stats = MissionStats()
        self.verbose = verbose
        # Per-target tracking for delayed-kill attribution (populated in parse())
        self._last_damager: dict = {}      # {TID: AID}  most recent attacker per Air target
        self._last_damage_tick: dict = {}  # {TID: int}  raw tick of most recent damage per Air target
        # Wingman-finish candidates: Air targets killed by a non-player attacker where the
        # player contributed damage.  Used by reconcile_plane_kills() for DB reconciliation.
        self._wingman_candidates: list = []  # [(tid, ts, player_fraction, pos_match)]

    @staticmethod
    def mission_time_to_hhmmss(t):
        # IL-2 uses 50 ticks per second (20ms per tick)
        # NOTE: This is GAME TIME (includes time compression!)
        sec = t / 50.0
        h, m, s = int(sec // 3600), int((sec % 3600) // 60), int(sec % 60)
        return f"{h:02}:{m:02}:{s:02}"

    # ------------------------------------------------------
    @staticmethod
    def _point_in_polygon(x, z, polygon):
        """
        Ray-casting algorithm to determine if point (x,z) is inside polygon.
        Polygon is a list of (x,z) tuples. Returns True if inside.
        """
        if not polygon or len(polygon) < 3:
            return False
        n = len(polygon)
        inside = False
        px, pz = x, z
        x1, z1 = polygon[0]
        for i in range(1, n + 1):
            x2, z2 = polygon[i % n]
            if pz > min(z1, z2):
                if pz <= max(z1, z2):
                    if px <= max(x1, x2):
                        if z1 != z2:
                            x_intersect = (pz - z1) * (x2 - x1) / (z2 - z1) + x1
                        if z1 == z2 or px <= x_intersect:
                            inside = not inside
            x1, z1 = x2, z2
        return inside

    def _determine_territory(self, x, z):
        """
        Determine territory for position (x,z) based on influence polygons.

        Territory logic (Section C of spec):
        - "friendly" if inside ANY polygon of player's COUNTRY
        - "enemy" if inside ANY polygon of any other COUNTRY
        - "unknown" if inside none or ambiguous (multiple countries)

        Returns: "friendly", "enemy", or "unknown"
        """
        player_country = self.stats.player_country
        if not player_country:
            return "unknown"  # No player country info, can't determine

        in_countries = []
        # Check all polygons for each country (supports multiple polygons per country)
        for country, polygons in self.stats.influence_polygons.items():
            for polygon in polygons:
                if self._point_in_polygon(x, z, polygon):
                    if country not in in_countries:
                        in_countries.append(country)
                    break  # Found match for this country, no need to check more polygons

        if not in_countries:
            return "unknown"  # Not in any influence zone

        if len(in_countries) > 1:
            # Ambiguous: point is in polygons of multiple countries (overlap)
            # Check if player's country is one of them
            if player_country in in_countries:
                # Prefer friendly if player's country is included
                return "friendly"
            return "unknown"

        # Single country match
        if in_countries[0] == player_country:
            return "friendly"
        else:
            return "enemy"

    # ------------------------------------------------------
    def parse(self):
        with open(self.path, encoding="utf-8") as f:
            lines = [l.strip() for l in f if "AType" in l]

        # --- register objects ---
        for ln in lines:
            if "AType:10" in ln:
                if "ISPL:1" in ln:
                    # 🧠 Capture both IDs for robustness
                    plid = self._i(ln, r"PLID:(\d+)")
                    pid  = self._i(ln, r"PID:(\d+)")

                    # Store both, in case IL-2 swaps them (as seen in your logs)
                    self.stats.player_plid = plid
                    self.stats.player_pid = pid
                    self.stats.player_id = pid or plid  # prefer pilot PID, fallback to plane PLID

                    self.stats.player_name = self._s(ln, r"NAME:([^ ]+)")
                    self.stats.player_aircraft = (
                        self._s(ln, r"TYPE:([^\r\n]+?)\s+COUNTRY:") or self._s(ln, r"TYPE:([^ ]+)")
                    )
                    # Store player's country for territory classification
                    self.stats.player_country = self._s(ln, r"COUNTRY:(\d+)")
                    # Debug output (optional)
                    log_message(logger, f"[DEBUG] Player detected: {self.stats.player_name} (PLID={plid}, PID={pid}, COUNTRY={self.stats.player_country})")
                gid = self._i(ln, r"AID:(\d+)")
                self.stats.add_object(GameObject(gid,
                    self._s(ln, r"NAME:([^ ]+)"),
                    self._s(ln, r"TYPE:([^\r\n]+?)\s+COUNTRY:") or self._s(ln, r"TYPE:([^ ]+)"),
                    self._s(ln, r"COUNTRY:(\d+)")
                ))

            elif "AType:12" in ln:
                gid = self._i(ln, r"ID:(\d+)")
                self.stats.add_object(GameObject(gid,
                    self._s(ln, r"NAME:([^ ]+)"),
                    self._s(ln, r"TYPE:([^\r\n]+?)\s+COUNTRY:") or self._s(ln, r"TYPE:([^ ]+)"),
                    self._s(ln, r"COUNTRY:(\d+)")
                ))

            # --- Parse influence polygons for territory classification (Section C) ---
            # AType:13: Influence area header - maps AID to COUNTRY
            elif "AType:13" in ln:
                aid = self._i(ln, r"AID:(\d+)")
                country = self._s(ln, r"COUNTRY:(\d+)")
                if aid >= 0 and country:
                    self.stats._influence_aid_to_country[aid] = country

            # AType:14: Influence polygon boundary - BP((x,z),(x,z),...)
            elif "AType:14" in ln:
                aid = self._i(ln, r"AID:(\d+)")
                bp_match = re.search(r"BP\((.+)\)", ln)
                if aid >= 0 and bp_match:
                    country = self.stats._influence_aid_to_country.get(aid)
                    if country:
                        # Parse polygon points: extract all (x,z) pairs
                        # Regex supports negative coordinates (e.g., -123.0)
                        points_str = bp_match.group(1)
                        points = []
                        for pt_match in re.finditer(r"\((-?[\d.]+),(-?[\d.]+)\)", points_str):
                            x, z = float(pt_match.group(1)), float(pt_match.group(2))
                            points.append((x, z))
                        if points:
                            # Append polygon to list (supports multiple polygons per country)
                            self.stats.influence_polygons[country].append(points)

        # --- collect events ---
        destroyed = {}  # {tid: (timestamp, altitude)}
        for ln in lines:
            t = self._i(ln, r"T:(\d+)")
            ts = self.mission_time_to_hhmmss(t)

            # AType:12 lines are also processed inline here (in addition to the
            # first pass above) so that reused TIDs (BlocksArray objects that
            # cycle through many types during a mission) reflect the correct
            # object type at the moment a kill event fires.
            if "AType:12" in ln:
                gid = self._i(ln, r"ID:(\d+)")
                self.stats.add_object(GameObject(gid,
                    self._s(ln, r"NAME:([^ ]+)"),
                    self._s(ln, r"TYPE:([^\r\n]+?)\s+COUNTRY:") or self._s(ln, r"TYPE:([^ ]+)"),
                    self._s(ln, r"COUNTRY:(\d+)")
                ))

            if "AType:2" in ln:
                a, tgt, dmg = self._i(ln, r"AID:(-?\d+)"), self._i(ln, r"TID:(-?\d+)"), self._f(ln, r"DMG:([\d.]+)")
                pos_match = re.search(r"POS\((-?[\d.]+),(-?[\d.]+),(-?[\d.]+)\)", ln)

                self.stats.add_hit(a, tgt, dmg, ts)

                # Track last *human* damager per Air target for delayed-kill attribution.
                # Ignore AID:-1 (fire / environmental damage) so burning wreckage
                # does not overwrite the actual attacker who set the aircraft alight.
                _tgt_obj = self.stats.objects.get(tgt)
                if _tgt_obj and _tgt_obj.category == "Air" and a != -1:
                    self._last_damager[tgt] = a
                    self._last_damage_tick[tgt] = t
                
                # Track damage to player or player's aircraft
                # Create SEPARATE events for aircraft and pilot damage
                damage_target_type = None

                if tgt == self.stats.player_plid and dmg > 0:
                    # Aircraft took damage
                    damage_target_type = "Aircraft"
                    self.stats.total_aircraft_damage += dmg

                    # Add aircraft damage event
                    altitude = int(float(pos_match.group(2))) if pos_match else None

                    # Handle AID=-1 (unknown attacker): use None to indicate generic damage
                    if a == -1:
                        attacker_name = None
                    else:
                        attacker_obj = self.stats.objects.get(a)
                        attacker_name = attacker_obj.type if attacker_obj else f"Unknown (ID:{a})"

                    self.stats.events.append({
                        "time": ts,
                        "type": "Damage Taken",
                        "target": attacker_name,  # None = unknown attacker (AID=-1)
                        "damage": f"{dmg*100:.1f}% aircraft",  # Include "aircraft" in string for aggregation
                        "altitude": altitude,
                        "time_raw": t,
                        "attacker_unknown": (a == -1)  # Flag for UI rendering
                    })

                if tgt in (self.stats.player_pid, self.stats.player_id) and dmg > 0:
                    # Pilot took damage (separate event!)
                    self.stats.total_pilot_damage += dmg

                    # Add pilot damage event
                    altitude = int(float(pos_match.group(2))) if pos_match else None

                    # Handle AID=-1 (unknown attacker): use None to indicate generic damage
                    if a == -1:
                        attacker_name = None
                    else:
                        attacker_obj = self.stats.objects.get(a)
                        attacker_name = attacker_obj.type if attacker_obj else f"Unknown (ID:{a})"

                    self.stats.events.append({
                        "time": ts,
                        "type": "Damage Taken",
                        "target": attacker_name,  # None = unknown attacker (AID=-1)
                        "damage": f"{dmg*100:.1f}% pilot",  # Include "pilot" in string for aggregation
                        "altitude": altitude,
                        "time_raw": t,
                        "attacker_unknown": (a == -1)  # Flag for UI rendering
                    })
                
                # Wounded status: ONLY based on PILOT damage (not aircraft!)
                # Threshold: >= 0.05 (5%) pilot damage
                if self.stats.total_pilot_damage >= 0.05:
                    self.stats.wounded = True

            elif "AType:3" in ln:
                a, tgt = self._i(ln, r"AID:(-?\d+)"), self._i(ln, r"TID:(-?\d+)")
                pos_match = re.search(r"POS\((-?[\d.]+),(-?[\d.]+),(-?[\d.]+)\)", ln)
                altitude = int(float(pos_match.group(2))) if pos_match else None
                destroyed[tgt] = (ts, altitude)  # Store with altitude
                
                obj = self.stats.objects.get(tgt)
                # 🚫 Skip excluded object types (from YAML)
                if obj and obj.category == "Excluded":
                    continue
                    
                if a in (self.stats.player_pid, self.stats.player_plid):
                    # Store altitude with the kill
                    if obj and altitude is not None:
                        obj.altitude = altitude
                    self.stats.add_kill(tgt, ts)
                elif a == -1:
                    self._resolve_indirect_kill(tgt, ts, t, pos_match)
                else:
                    # Killed by a non-player, non-environment attacker (e.g. wingman).
                    # Record as a reconciliation candidate if the player dealt any damage.
                    if obj and obj.category == "Air":
                        player_ids = (self.stats.player_pid, self.stats.player_plid)
                        hits   = [h for h in self.stats.hits if h["target"] == tgt]
                        total  = sum(h["damage"] for h in hits)
                        player = sum(h["damage"] for h in hits if h["attacker"] in player_ids)
                        if total > 0 and player > 0:
                            self._wingman_candidates.append(
                                (tgt, ts, player / total, pos_match)
                            )

            elif "AType:5" in ln:  # ✅ Takeoff
                pid = self._i(ln, r"PID:(-?\d+)")
                pos_match = re.search(r"POS\((-?[\d.]+),(-?[\d.]+),(-?[\d.]+)\)", ln)
                if pid in (self.stats.player_pid, self.stats.player_plid) and not self.stats.takeoff_time:
                    self.stats.takeoff_time = t
                    altitude = int(float(pos_match.group(2))) if pos_match else None
                    self.stats.events.append({
                        "time": ts,
                        "type": "Takeoff",
                        "altitude": altitude,
                        "time_raw": t
                    })
            
            elif "AType:18" in ln:  # ✅ Pilot Separation (Bailout indicator)
                # SECTION B.1: AType:18 is the authoritative "pilot separated/bailout started" trigger
                # BOTID = pilot that separated, PARENTID = aircraft they left
                botid = self._i(ln, r"BOTID:(-?\d+)")
                parentid = self._i(ln, r"PARENTID:(-?\d+)")
                pos_match = re.search(r"POS\((-?[\d.]+),(-?[\d.]+),(-?[\d.]+)\)", ln)

                # Check if player pilot separated from player aircraft
                # (only if player IDs are known)
                if (self.stats.player_pid and self.stats.player_plid and
                    botid == self.stats.player_pid and parentid == self.stats.player_plid):
                    # Deduplicate by checking if we already recorded this separation
                    # (IL-2 sometimes emits duplicate AType:18 lines at same tick)
                    if self.stats.pilot_separation_time is None:
                        self.stats.pilot_separation_time = t  # Store time (ticks)
                        # Store position for territory check (Section D)
                        if pos_match:
                            x = float(pos_match.group(1))
                            y = float(pos_match.group(2))
                            z = float(pos_match.group(3))
                            self.stats.pilot_separation_pos = (x, y, z)
                        if self.verbose:
                            log_message(logger, f"  Pilot separation detected at {ts} (T:{t})")

            # SECTION B.3: AType:7 MUST NOT be used as landing/crash/bailout trigger.
            # It may be recognized as a delimiter/segment boundary, but must not drive status.
            # We only log it for debugging if verbose.
            elif "AType:7" in ln:
                # AType:7 is a segment boundary/delimiter ONLY - do not drive outcome status
                if self.verbose:
                    pid = self._i(ln, r"PID:(-?\d+)")
                    if pid in (self.stats.player_pid, self.stats.player_plid):
                        log_message(logger, f"  [DELIMITER] AType:7 segment boundary at {ts} (ignored for status)")

            # SECTION B.2: AType:6 is "ground contact" - meaning depends on bailout state
            elif "AType:6" in ln:
                pid = self._i(ln, r"PID:(-?\d+)")
                pos_match = re.search(r"POS\((-?[\d.]+),(-?[\d.]+),(-?[\d.]+)\)", ln)

                # Check if this AType:6 is for player (aircraft or pilot)
                if pid in (self.stats.player_pid, self.stats.player_plid):
                    altitude = int(float(pos_match.group(2))) if pos_match else None
                    x = float(pos_match.group(1)) if pos_match else None
                    z = float(pos_match.group(3)) if pos_match else None

                    # SECTION B.2: Conditional semantics based on bailout state
                    if self.stats.pilot_separation_time and t > self.stats.pilot_separation_time:
                        # Bailout DID occur, and this AType:6 is AFTER separation
                        # → This is pilot/parachute touchdown, NOT aircraft landing
                        # Store touchdown position for territory check (Section D.1)
                        if self.stats._pilot_touchdown_time is None:
                            self.stats._pilot_touchdown_time = t
                            self.stats._pilot_touchdown_pos = (x, altitude, z) if x is not None else None

                            self.stats.events.append({
                                "time": ts,
                                "type": "Pilot Touchdown",
                                "altitude": altitude,
                                "time_raw": t
                            })
                            if self.verbose:
                                log_message(logger, f"  Pilot touchdown at {ts} (post-bailout AType:6)")
                    else:
                        # NO bailout occurred (or AType:6 is before separation - rare)
                        # → This is aircraft landing
                        if not self.stats.landing_time:
                            self.stats.landing_time = t
                            self.stats.landed = True

                            # Set provisional landing state (may be upgraded to Hard Landing later)
                            if self.stats.wounded:
                                self.stats.final_state = "Landed (Wounded)"
                            else:
                                self.stats.final_state = "Landed"

                            # Check territory for emergency landings on enemy territory
                            # Uses AType:13/14 influence polygons to determine if landing
                            # occurred in enemy-controlled territory. Pilots landing on
                            # enemy territory without bailout are treated as captured.
                            if x is not None and z is not None and self.stats.influence_polygons:
                                territory = self._determine_territory(x, z)
                                if territory == "enemy":
                                    self.stats.final_state = "MIA (Captured)"
                                    self.stats.landed = False  # Not a successful landing
                                    if self.verbose:
                                        log_message(logger, f"  [TERRITORY] Landing on enemy territory at ({x:.0f}, {z:.0f}) -> MIA (Captured)")

                            self.stats.events.append({
                                "time": ts,
                                "type": "Landing",
                                "altitude": altitude,
                                "time_raw": t
                            })

        # --- retroactive proportional kills ---
        for tid, (kill_time, altitude) in destroyed.items():
            hits = [h for h in self.stats.hits if h["target"] == tid]
            if not hits: continue
            total = sum(h["damage"] for h in hits)
            player_dmg = sum(h["damage"] for h in hits if h["attacker"] in (self.stats.player_pid, self.stats.player_plid))
            if total > 0 and player_dmg / total >= 0.8:
                if all(k.id != tid for k in self.stats.kills):
                    obj = self.stats.objects.get(tid)
                    if obj and altitude is not None:
                        obj.altitude = altitude
                    self.stats.add_kill(tid, hits[-1]["time"])
                    
        # --- detect bail-out ---
        # REMOVED: Redundant parachute detection
        # Time-based bailout detection (lines 307-315) is more reliable
        # and avoids conflicts with "Bailed Out" vs "Bailout" strings

        # --- compute flight duration ---
        if self.stats.takeoff_time:
            # Use landing time if available, otherwise use last event time (mission end)
            end_time = self.stats.landing_time
            if not end_time and self.stats.events:
                # No landing recorded - use last event as mission end
                end_time = max((e.get('time_raw', 0) for e in self.stats.events), default=self.stats.takeoff_time)
                # Store mission_end_time for duration calc and self-damage filtering
                # NOTE: We do NOT emit a "Mission End" event to the timeline anymore
                if end_time > self.stats.takeoff_time:
                    self.stats.mission_end_time = end_time

            if end_time:
                duration = end_time - self.stats.takeoff_time
                # IL-2 uses 50 ticks per second (20ms per tick)
                # NOTE: This is GAME TIME (includes time compression!)
                sec = duration / 50.0
                h, m, s = int(sec // 3600), int((sec % 3600) // 60), int(sec % 60)
                self.stats.flight_duration = f"{h:02}:{m:02}:{s:02}"

        # ==============================================================
        # SECTION E & F: FINAL STATUS CLEANUP / OUTCOME MAPPING
        # ==============================================================
        # Finalize sortie outcome based on bailout state and territory

        if self.stats.pilot_separation_time:
            # ==============================================================
            # BAILOUT OCCURRED - Apply capture/MIA logic (Section E, bailout case)
            # ==============================================================

            # SECTION D: Determine best position for territory check
            # Priority: 1) pilot touchdown pos, 2) AType:18 separation pos, 3) fallback
            pilot_pos = None
            touchdown_observed = False

            # D.1: Check for post-bailout AType:6 (pilot touchdown)
            if self.stats._pilot_touchdown_pos:
                pilot_pos = self.stats._pilot_touchdown_pos
                touchdown_observed = True
            # D.2: Fallback to AType:18 separation position
            elif self.stats.pilot_separation_pos:
                pilot_pos = self.stats.pilot_separation_pos
            # D.3: No position available - territory unknown

            # Determine territory using position (Section C)
            territory = "unknown"
            if pilot_pos and len(pilot_pos) >= 3:
                x, _, z = pilot_pos  # (x, y, z) - use x and z for 2D polygon test
                territory = self._determine_territory(x, z)

            if self.verbose:
                log_message(logger, f"  [TERRITORY] Bailout territory check: pos={pilot_pos}, territory={territory}, touchdown={touchdown_observed}")

            # SECTION E: Map bailout outcome based on territory and touchdown
            if touchdown_observed:
                # Pilot touched down (post-bailout AType:6 exists)
                if territory == "friendly":
                    if self.stats.wounded:
                        self.stats.final_state = "Bailout (Survived, Wounded)"
                    else:
                        self.stats.final_state = "Bailout (Survived)"
                elif territory == "enemy":
                    self.stats.final_state = "MIA (Captured)"
                else:  # unknown
                    self.stats.final_state = "MIA (Unknown)"
            else:
                # Mission ended mid-descent (no post-bailout AType:6)
                if territory == "friendly":
                    if self.stats.wounded:
                        self.stats.final_state = "Bailout (Survived, Wounded)"
                    else:
                        self.stats.final_state = "Bailout (Survived)"
                elif territory == "enemy":
                    self.stats.final_state = "MIA (Likely Captured)"
                else:  # unknown
                    self.stats.final_state = "MIA (Unknown)"

            log_message(logger, f"[BAILOUT] Final state: {self.stats.final_state} (territory={territory}, touchdown={touchdown_observed})")

        elif self.stats.final_state == "Alive":
            # ==============================================================
            # NO BAILOUT AND NO LANDING - status still "Alive"
            # Keep existing fallback behavior (mission ended without resolution)
            # ==============================================================
            pass  # Leave as "Alive" - no additional states introduced

        return self.stats

    # ------------------------------------------------------
    def _resolve_indirect_kill(self, tid, ts, destroy_tick=None, pos_match=None):
        """
        Attribute an AID:-1 destruction to the player if justified.

        Priority 1 – Last-damager (delayed kill):
            If the last AType:2 hit on *tid* came from the player and the gap
            between that hit and the AType:3 event is ≤ _DELAYED_KILL_MAX_TICKS,
            credit the kill as a delayed crash caused by player damage.

        Priority 2 – Proportional damage (legacy safety net):
            If the player dealt ≥ 80 % of all recorded damage on *tid*, credit
            the kill regardless of time gap (handles cases where many zero-damage
            hits dilute the last-damager signal).
        """
        # Guard: already credited for this target
        if any(k.id == tid for k in self.stats.kills):
            return

        player_ids = (self.stats.player_pid, self.stats.player_plid)
        credited = False

        # --- Priority 1: last-damager check ---
        last_aid  = self._last_damager.get(tid)
        last_tick = self._last_damage_tick.get(tid)
        if last_aid is not None and last_aid in player_ids:
            elapsed_ticks = (
                (destroy_tick - last_tick)
                if (destroy_tick is not None and last_tick is not None)
                else 0
            )
            if elapsed_ticks <= _DELAYED_KILL_MAX_TICKS:
                credited = True
                elapsed_s = elapsed_ticks / 50.0
                log_message(
                    logger,
                    f"[DELAYED KILL] Credited: TID={tid}, destroyed at tick={destroy_tick}, "
                    f"last_damager=player (AID={last_aid}), last_damage_tick={last_tick}, "
                    f"elapsed={elapsed_s:.1f}s",
                )

        # --- Priority 2: proportional damage (legacy safety net) ---
        if not credited:
            hits   = [h for h in self.stats.hits if h["target"] == tid]
            total  = sum(h["damage"] for h in hits)
            player = sum(h["damage"] for h in hits if h["attacker"] in player_ids)
            if total > 0 and player / total >= 0.8:
                credited = True

        # --- Priority 3: sole human damager (no time limit) ---
        # Fire/environment ticks (AID=-1) inflate the denominator and can push
        # the player's fraction below 80%.  If the player is the ONLY human who
        # ever hit this target, the kill was inevitably caused by the player
        # alone — credit it regardless of elapsed time.
        if not credited:
            hits = [h for h in self.stats.hits if h["target"] == tid]
            human_hits = [h for h in hits if h["attacker"] != -1]
            if human_hits and all(h["attacker"] in player_ids for h in human_hits):
                credited = True
                log_message(
                    logger,
                    f"[SOLE ATTACKER] Credited: TID={tid}, player was the only human damager",
                )

        if credited:
            obj = self.stats.objects.get(tid)
            if obj and pos_match:
                obj.altitude = int(float(pos_match.group(2)))
            self.stats.add_kill(tid, ts)

    def reconcile_plane_kills(self, expected_total: int) -> None:
        """
        Career-mode DB reconciliation for plane kills only.

        After parse(), if the career DB credits more Air (plane) kills than the
        log attributed directly to the player, try to bridge the gap using
        wingman-finish candidates — Air targets killed by a non-player attacker
        where the player contributed damage (stored in _wingman_candidates).

        Candidates are sorted by player damage fraction descending; only the
        best-matching ones are credited, up to the deficit.

        Called by the career debriefing manager after querying the sortie table;
        never called by the Campaign Service Record.
        """
        def _air_kill_count():
            return sum(
                1 for k in self.stats.kills
                if k.category == "Air"
                and not any(x in k.type.lower() for x in ["botpilot", "botgunner"])
            )

        deficit = expected_total - _air_kill_count()
        if deficit <= 0:
            return

        # Deduplicate candidates: keep best fraction per TID
        best: dict = {}
        for tid, ts, fraction, pos_match in self._wingman_candidates:
            if tid not in best or fraction > best[tid][1]:
                best[tid] = (ts, fraction, pos_match)

        # Sort by player damage fraction descending
        ranked = sorted(best.items(), key=lambda x: -x[1][1])

        for tid, (ts, fraction, pos_match) in ranked:
            if deficit <= 0:
                break
            if any(k.id == tid for k in self.stats.kills):
                continue
            obj = self.stats.objects.get(tid)
            if obj and obj.category == "Air":
                if pos_match:
                    obj.altitude = int(float(pos_match.group(2)))
                log_message(
                    logger,
                    f"[DB RECONCILE] Credited: TID={tid} ({obj.type}), "
                    f"player_damage={fraction:.1%}, expected_total={expected_total}",
                )
                self.stats.add_kill(tid, ts)
                deficit -= 1

    # ------------------------------------------------------
    def _detect_landing_damage(self, events, data):
        """
        Detect and mark landing damage events.

        Criteria (ALL must match):
        1. Attacker is player's aircraft OR unknown (AID=-1)
        2. Time before landing < 60 seconds
        3. Time since last kill > 60 seconds (not in combat)
        4. Relative altitude < 150m above airfield

        Args:
            events: List of events
            data: Mission data dict with player info

        Returns:
            Modified events list with landing damage marked
        """
        player_aircraft = data['player']['aircraft']

        # Find takeoff and landing altitudes (airfield elevation)
        takeoff_alt = None
        landing_alt = None
        landing_time = None

        for evt in events:
            if evt.get('type') == 'Takeoff' and evt.get('altitude') is not None:
                takeoff_alt = evt['altitude']
            if evt.get('type') in ['Landing', 'Crash']:
                landing_time = evt.get('time')
                if evt.get('altitude') is not None:
                    landing_alt = evt['altitude']

        # Use average of takeoff/landing as airfield elevation
        airfield_alt = None
        if takeoff_alt is not None and landing_alt is not None:
            airfield_alt = (takeoff_alt + landing_alt) / 2
        elif takeoff_alt is not None:
            airfield_alt = takeoff_alt
        elif landing_alt is not None:
            airfield_alt = landing_alt

        if not landing_time:
            return events  # No landing, can't detect landing damage

        # Find last kill time
        last_kill_time = None
        for evt in reversed(events):
            if evt.get('type') == 'Kill':
                last_kill_time = evt.get('time')
                break

        # Check each damage event
        modified_events = []
        has_hard_landing = False

        for evt in events:
            if evt.get('type') == 'Damage Taken':
                is_landing_dmg = False

                # Criterion 1: Attacker is player's aircraft OR unknown (AID=-1)
                # Both cases indicate potential landing/self damage
                is_self_or_unknown = (
                    evt.get('target') == player_aircraft or
                    evt.get('attacker_unknown') is True
                )
                if is_self_or_unknown:
                    damage_time = evt.get('time')
                    damage_alt = evt.get('altitude')
                    
                    # Criterion 2: Time before landing < 60 seconds (increased from 30s)
                    time_diff = self._time_diff_seconds(damage_time, landing_time)
                    if 0 < time_diff < 60:
                        
                        # Criterion 3: Time since last kill > 60 seconds (or no kills)
                        if last_kill_time is None:
                            time_since_kill = 999999  # No kills = not in combat
                        else:
                            time_since_kill = self._time_diff_seconds(last_kill_time, damage_time)
                        
                        if time_since_kill > 60:
                            
                            # Criterion 4: Relative altitude < 150m above airfield
                            if airfield_alt is not None and damage_alt is not None:
                                relative_alt = damage_alt - airfield_alt
                                if relative_alt < 150:
                                    is_landing_dmg = True
                            else:
                                # No altitude data, use other criteria only
                                is_landing_dmg = True
                
                if is_landing_dmg:
                    # Mark as landing damage
                    evt_copy = evt.copy()
                    evt_copy['type'] = 'Landing Damage'
                    evt_copy['original_target'] = evt['target']  # Keep original for reference
                    modified_events.append(evt_copy)
                    has_hard_landing = True
                else:
                    modified_events.append(evt)
            else:
                # Mark landing event as "hard" if we detected landing damage
                if evt.get('type') in ['Landing', 'Crash'] and has_hard_landing:
                    evt_copy = evt.copy()
                    evt_copy['hard_landing'] = True
                    modified_events.append(evt_copy)
                else:
                    modified_events.append(evt)
        
        # Update final state if hard landing detected
        # NOTE: Only upgrade states starting with "Landed" - never touch MIA/Bailout states
        # This ensures enemy territory landings ("MIA (Captured)") are preserved
        if has_hard_landing:
            current_state = data['summary']['final_state']
            if current_state == 'Landed':
                data['summary']['final_state'] = 'Landed (Hard Landing)'
            elif current_state == 'Landed (Wounded)':
                data['summary']['final_state'] = 'Landed (Hard Landing, Wounded)'

        return modified_events
    
    # ------------------------------------------------------
    def _time_diff_seconds(self, time1, time2):
        """Calculate difference in seconds between two time strings (HH:MM or HH:MM:SS)"""
        try:
            def parse_time(t):
                parts = t.split(':')
                if len(parts) == 3:
                    h, m, s = map(int, parts)
                elif len(parts) == 2:
                    h, m, s = int(parts[0]), int(parts[1]), 0
                else:
                    return 0
                return h * 3600 + m * 60 + s
            
            return parse_time(time2) - parse_time(time1)
        except:
            return 0

    # ------------------------------------------------------
    def to_json(self, out_path):
        # Filter out BotPilot/BotGunner from kills
        def valid(k): return not any(x in k.type.lower() for x in ["botpilot", "botgunner"])
        kills = [k for k in self.stats.kills if valid(k)]
        
        # Note: static plane name cleaning and is_static flag are now set in GameObject __init__
        
        # Calculate total damage to aircraft and pilot separately
        aircraft_damage = 0.0
        pilot_damage = 0.0
        
        for hit in self.stats.hits:
            if hit["target"] == self.stats.player_plid:
                aircraft_damage += hit["damage"]
            elif hit["target"] in (self.stats.player_pid, self.stats.player_id):
                pilot_damage += hit["damage"]
        
        # Count air kills separately (flying vs parked)
        air_kills_all = [k for k in kills if k.category == "Air"]
        air_kills_flying = sum(1 for k in air_kills_all if not getattr(k, 'is_static', False))
        air_kills_parked = sum(1 for k in air_kills_all if getattr(k, 'is_static', False))

        data = {
            "player": {
                "id": self.stats.player_id,
                "name": self.stats.player_name,
                "aircraft": self.stats.player_aircraft
            },
            "summary": {
                "air_kills": len(air_kills_all),
                "air_kills_flying": air_kills_flying,
                "air_kills_parked": air_kills_parked,
                "ground_kills": sum(1 for k in kills if k.category in ["Ground", "Building"]),
                "naval_kills": sum(1 for k in kills if k.category == "Naval"),
                "flight_duration": self.stats.flight_duration or "N/A",
                "wounded": self.stats.wounded,
                "total_damage_taken": round(self.stats.total_damage_taken, 2),
                "aircraft_damage": round(aircraft_damage * 100, 1),  # As percentage
                "pilot_damage": round(pilot_damage * 100, 1),  # As percentage
                "landed": self.stats.landed,
                "crashed": self.stats.crashed,
                "final_state": self.stats.final_state
            }
        }
        
        # Start with existing events (Takeoff, Landing, Damage)
        events = list(self.stats.events)
        
        # Add kill events (filter out BotPilot/BotGunner)
        for k in kills:
            if k.time_of_kill:
                evt = {
                    "time": k.time_of_kill,
                    "type": "Kill",
                    "target": k.type,
                    "category": k.category
                }
                if k.altitude is not None:
                    evt["altitude"] = k.altitude
                events.append(evt)
        
        # Aggregate damage events by minute (not exact second)
        damage_by_time = {}
        non_damage_events = []

        for evt in events:
            if evt.get("type") == "Damage Taken":
                # Group by minute (HH:MM) instead of exact time
                full_time = evt.get("time")
                if full_time and len(full_time.split(':')) >= 2:
                    time_key = ':'.join(full_time.split(':')[:2])  # Take HH:MM only for grouping
                else:
                    time_key = full_time

                if time_key not in damage_by_time:
                    damage_by_time[time_key] = {
                        "time": full_time,  # Keep full time with seconds from first event
                        "time_raw": evt.get("time_raw"),
                        "aircraft_damage": 0.0,
                        "pilot_damage": 0.0,
                        "attacker": evt.get("target"),
                        "altitude": evt.get("altitude"),
                        "attacker_unknown": evt.get("attacker_unknown", False)  # Preserve AID=-1 flag
                    }

                # Accumulate damage
                damage_str = evt.get("damage", "")

                # Parse aggregated damage strings like "4.2% aircraft, 19.2% pilot"
                if "aircraft" in damage_str and "pilot" in damage_str:
                    parts = damage_str.split(",")
                    for part in parts:
                        if "aircraft" in part:
                            dmg_val = float(part.strip().split("%")[0])
                            damage_by_time[time_key]["aircraft_damage"] += dmg_val
                        elif "pilot" in part:
                            dmg_val = float(part.strip().split("%")[0])
                            damage_by_time[time_key]["pilot_damage"] += dmg_val
                elif "aircraft" in damage_str:
                    dmg_val = float(damage_str.split("%")[0])
                    damage_by_time[time_key]["aircraft_damage"] += dmg_val
                elif "pilot" in damage_str:
                    dmg_val = float(damage_str.split("%")[0])
                    damage_by_time[time_key]["pilot_damage"] += dmg_val

                # If any event in this group has unknown attacker, mark the whole group
                if evt.get("attacker_unknown"):
                    damage_by_time[time_key]["attacker_unknown"] = True
            else:
                non_damage_events.append(evt)

        # Convert aggregated damage back to events
        for time_key, dmg_data in damage_by_time.items():
            base_evt = {
                "time": dmg_data["time"],
                "type": "Damage Taken",
                "target": dmg_data["attacker"],
                "altitude": dmg_data["altitude"],
                "time_raw": time_key
            }
            # Add attacker_unknown flag if true
            if dmg_data.get("attacker_unknown"):
                base_evt["attacker_unknown"] = True

            if dmg_data["aircraft_damage"] > 0 and dmg_data["pilot_damage"] > 0:
                # Both aircraft and pilot hit
                base_evt["damage"] = f"{dmg_data['aircraft_damage']:.1f}% aircraft, {dmg_data['pilot_damage']:.1f}% pilot"
                non_damage_events.append(base_evt)
            elif dmg_data["aircraft_damage"] > 0:
                # Only aircraft
                base_evt["damage"] = f"{dmg_data['aircraft_damage']:.1f}% aircraft"
                non_damage_events.append(base_evt)
            elif dmg_data["pilot_damage"] > 0:
                # Only pilot
                base_evt["damage"] = f"{dmg_data['pilot_damage']:.1f}% pilot"
                non_damage_events.append(base_evt)
        
        # Detect landing damage and mark appropriately
        non_damage_events = self._detect_landing_damage(non_damage_events, data)

        # Filter out ALL self-damage for Bailout/MIA outcomes
        # These events show "Hit by <player aircraft>" which is misleading when the aircraft
        # is destroyed/abandoned (crash impact damage displayed as if hit by own plane).
        # We keep self-damage for Landed* outcomes so hard-landing detection remains intact.
        final_state = data['summary']['final_state']
        if final_state.startswith('MIA') or final_state.startswith('Bailout'):
            player_aircraft = data['player']['aircraft']
            filtered_events = []
            for evt in non_damage_events:
                # Filter ALL self-damage events (target == player's own aircraft type)
                if evt.get('type') == 'Damage Taken' and evt.get('target') == player_aircraft:
                    # Skip this event - don't show "Hit by <own aircraft>" for MIA/Bailout
                    continue
                filtered_events.append(evt)
            non_damage_events = filtered_events

        # Sort all events by time
        def _time_key(evt):
            t = evt.get("time")
            if not t:
                return 999999
            try:
                parts = t.split(":")
                if len(parts) == 3:
                    h, m, s = [int(x) for x in parts]
                elif len(parts) == 2:
                    h, m = [int(x) for x in parts]
                    s = 0  # No seconds, assume :00
                else:
                    return 999999
                return h * 3600 + m * 60 + s
            except Exception:
                return 999999

        non_damage_events.sort(key=_time_key)
        data["events"] = non_damage_events
        
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        log_message(logger, f"✓ JSON exported to {out_path}")

    # ------------------------------------------------------
    @staticmethod
    def _i(t, p): m = re.search(p, t); return int(m.group(1)) if m else -1
    @staticmethod
    def _f(t, p): m = re.search(p, t); return float(m.group(1)) if m else 0.0
    @staticmethod
    def _s(t, p): m = re.search(p, t); return m.group(1).strip() if m else ""



# ==========================================================
def main(args=None):
    """
    Main entry point for IL-2 Mission Debrief Parser.

    Args:
        args: Optional list of CLI-style arguments (e.g., ['missionReport.txt'])
    """
    import sys
    if args is None:
        args = sys.argv[1:]

    if len(args) < 1:
        log_message(logger, "Usage: python il2_mission_debrief.py <missionReport.txt>")
        return False

    f = args[0]
    p = MissionDebriefParser(f)
    s = p.parse()
    p.to_json(f.replace(".txt", ".events.json"))
    return True


if __name__ == "__main__":
    import sys
    main(sys.argv[1:])
