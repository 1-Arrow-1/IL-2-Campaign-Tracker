"""
CareerAggregator: transforms cp.db data into API response shapes.

Produces dicts structurally identical to those returned by CampaignAggregator,
so that the existing frontend (detail.js, landing.js) requires no changes to
render career data.

Differences from CampaignAggregator:
    - Data source is cp.db, not JSON files.
    - No award/promotion calculation: events come directly from event table.
    - Statistics read from pilot table kill counters (no per-mission aggregation).
    - Rank and award names use placeholder strings until translation tables are
      provided (rank_<id> and award_<code>). When translation tables arrive,
      only _map_event() needs updating.
    - flight_time and aircraft_usage are derived from parsed missionReport files
      via CareerDebriefingManager; empty dicts are returned when no reports are linked.
"""

import logging
import re
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional

from campaign_service_record.career.database import CareerDatabase
from campaign_service_record.career.chain_resolver import CareerChainResolver, VirtualPilotCareer
from campaign_service_record.career.statistics import StatisticsMapper
from campaign_service_record.career.mission_linker import MissionReportLinker
from campaign_service_record.career.award_index import AwardIndex
from campaign_service_record.career.rank_index import RankIndex
from campaign_service_record.career.rank_resolver import RankResolver
from campaign_service_record.career.debriefing_manager import CareerDebriefingManager
from campaign_service_record.career.other_incidences import load_other_incidences
from campaign_service_record.utils.path_utils import USSR_TRANSITION_DATE
from utils.locale_config import get_career_effective_locale

logger = logging.getLogger(__name__)

# Matches the last double-quoted field on a data line, e.g.:
#   *,"I. Gruppe of Jagdgeschwader 52","I./JG 52"|
# captures "I./JG 52"
_SQUADRON_SHORT_NAME_RE = re.compile(r'"([^"]+)"\s*\|?\s*$')

# Only confirmed event types are processed. Others are silently skipped.
_CONFIRMED_EVENT_TYPES = [6, 8, 10]

# Maps lowercase career.country strings to integer country codes used in rank lookup
_COUNTRY_CODE_MAP: Dict[str, int] = {
    'germany': 201,
    'britain': 102,
    'usa':     103,
    'ussr':    101,
}


def _rank_subfolder(country_int: int, event_date: Optional[str]) -> Optional[str]:
    """Return the CampaignRanksAwards subfolder name for a rank promotion event."""
    if country_int == 201:
        return 'Germany'
    if country_int == 102:
        return 'Britain'
    if country_int == 103:
        return 'US'
    if country_int == 101:
        if event_date:
            try:
                d = date.fromisoformat(event_date)
                return 'USSR/late' if d >= USSR_TRANSITION_DATE else 'USSR/early'
            except ValueError:
                pass
        return 'USSR/early'
    return None


class CareerAggregator:
    """
    Aggregates cp.db data into UI-ready structures matching CampaignAggregator output.
    """

    def __init__(
        self,
        db: CareerDatabase,
        chain_resolver: CareerChainResolver,
        statistics_mapper: StatisticsMapper,
        mission_linker: MissionReportLinker,
        game_dir: Optional[Path] = None,
        data_dir: Optional[Path] = None,
        cache_dir: Optional[Path] = None,
    ):
        self._db = db
        self._resolver = chain_resolver
        self._stats = statistics_mapper
        self._linker = mission_linker
        # game_dir used for squadron name lookups; falls back to db.game_dir if not supplied
        self._game_dir: Optional[Path] = game_dir or db.game_dir
        # data_dir used as fallback for CampaignRanksAwards assets when game_dir is not set
        self._data_dir: Optional[Path] = data_dir
        # cache_dir for debriefing HTML cache; falls back to data_dir if not supplied
        self._cache_dir: Optional[Path] = cache_dir or data_dir

        # Build award index from data_dir (primary) or game_dir/data/swf (fallback)
        self._award_index: AwardIndex = self._build_award_index()
        # Build rank index (same search order as award index)
        self._rank_index: RankIndex = self._build_rank_index()
        # Build rank resolver (detects mod mode from game_dir; defaults to English)
        self._rank_resolver: RankResolver = RankResolver(self._game_dir)

    # ------------------------------------------------------------------
    # Landing page list
    # ------------------------------------------------------------------

    def get_career_list(self) -> List[Dict]:
        """
        Get list of all virtual pilot careers for the landing page.

        Returns list of dicts in the same shape as CampaignAggregator.get_campaign_list(),
        with an additional theatre_chain field.
        """
        careers = self._resolver.resolve_all_careers()
        result = []
        for career in careers:
            try:
                result.append(self._build_list_item(career))
            except Exception as exc:
                logger.error(
                    "Error building list item for career root=%d: %s",
                    career.root_career_id, exc, exc_info=True
                )
        return result

    # ------------------------------------------------------------------
    # Detail page
    # ------------------------------------------------------------------

    def get_career_detail(self, root_career_id: int) -> Optional[Dict]:
        """
        Get full career detail payload for a virtual pilot career.

        Args:
            root_career_id: The career.id of the chain root (extends = -1).

        Returns:
            Detail dict matching CampaignAggregator.get_campaign_detail() shape, or None.
        """
        career = self._resolver.get_career(root_career_id)
        if career is None:
            return None

        # Each theatre segment has its own pilot row. The MOST CURRENT pilot
        # carries the accumulated kill totals for all theatres completed so far,
        # as well as the up-to-date pcp score and squadronId.
        # Root pilot_id has only the first theatre's data — always use last_pilot_id.
        current_pilot_row = self._db.get_pilot_by_id(career.last_pilot_id)

        events_raw = self._db.get_events_for_pilot(
            career.pilot_id, types=_CONFIRMED_EVENT_TYPES
        )
        seen_bonus_codes: set = set()
        bonus_incidences: list = []
        mapped_events = []
        for row in events_raw:
            ev = self._map_event(
                row, career.country,
                seen_bonus_codes=seen_bonus_codes,
                bonus_incidences=bonus_incidences,
            )
            if ev is not None:
                mapped_events.append(ev)

        # Build combat results from the most current pilot row (all-theatre totals)
        combat_results = self._stats.build_combat_results(current_pilot_row)

        # Inject PCP score from the most current pilot record (preserve decimal)
        pcp_score = self._safe_float_from_row(current_pilot_row, "pcp")
        combat_results["pcp_score"] = pcp_score

        sorties = self._db.get_sorties_for_pilot(career.pilot_id)

        # Build mission debriefings and flight-time statistics
        debrief_manager: Optional[CareerDebriefingManager] = None
        if self._cache_dir is not None:
            try:
                debrief_manager = CareerDebriefingManager(
                    db=self._db,
                    career=career,
                    linker=self._linker,
                    cache_dir=self._cache_dir,
                )
            except Exception as exc:
                logger.warning("CareerDebriefingManager init failed: %s", exc)

        debriefings_html = ""
        mission_stats_override: Optional[Dict] = None
        aircraft_usage_override: Optional[Dict] = None
        if debrief_manager is not None:
            try:
                debriefings_html = debrief_manager.build_debriefings_html()
                mission_stats_override = debrief_manager.get_mission_stats()
                aircraft_usage_override = debrief_manager.get_aircraft_usage()
            except Exception as exc:
                logger.warning("CareerDebriefingManager build failed: %s", exc)

        first_pilot_row = self._db.get_pilot_by_id(career.pilot_id)
        summary = self._build_summary(
            career, mapped_events, sorties, combat_results, mission_stats_override,
            first_pilot_row=first_pilot_row,
            last_pilot_row=current_pilot_row,
            aircraft_usage_override=aircraft_usage_override,
        )

        # Resolve current squadron short name via career chain's current squadronId
        current_career_squadron_id = (
            int(career.chain[-1]["squadronId"]) if career.chain else 0
        )
        squadron_short_name = self._resolve_squadron_name(current_career_squadron_id)

        # Build other incidences (recovery, commander, transfer) and merge bonus duplicates
        other_incidences = self._load_other_incidences(career)
        if bonus_incidences:
            other_incidences = sorted(
                other_incidences + bonus_incidences,
                key=lambda e: e["sort_key"],
            )

        return {
            # 'name' mirrors campaign convention so existing frontend code works
            "name": str(career.root_career_id),
            "display_name": career.pilot_name,
            "pilot_first_name": career.pilot_first_name,
            "pilot_last_name": career.pilot_last_name,
            "country": career.country or "unknown",
            "missions_completed": len(sorties),
            "events": mapped_events,
            "debriefings_html": debriefings_html,
            "effective_locale": get_career_effective_locale(str(career.root_career_id)),
            "summary": summary,
            # Career-specific extras
            "source": "career",
            "theatre_chain": career.theatre_labels,
            "birth_date": career.birth_date,
            "pcp_score": pcp_score,
            "squadron_short_name": squadron_short_name or "",
            "other_incidences": other_incidences,
        }

    # ------------------------------------------------------------------
    # Private: list item builder
    # ------------------------------------------------------------------

    def _build_list_item(self, career: VirtualPilotCareer) -> Dict:
        # Use most current pilot row for kill totals (each theatre has its own pilot row)
        current_pilot_row = self._db.get_pilot_by_id(career.last_pilot_id)
        events_raw = self._db.get_events_for_pilot(
            career.pilot_id, types=_CONFIRMED_EVENT_TYPES
        )
        promotions = [e for e in events_raw if e["type"] == 6]
        awards = [e for e in events_raw if e["type"] == 8]
        sorties = self._db.get_sorties_for_pilot(career.pilot_id)

        if promotions:
            last_rank_id = promotions[-1]["rankId"]
            country_int = _COUNTRY_CODE_MAP.get((career.country or '').lower(), 0)
            rank_name = self._rank_resolver.resolve(country_int, int(last_rank_id or -1))
            final_rank = rank_name.display if rank_name else f"rank_{last_rank_id}"
        else:
            final_rank = "Unknown"

        combat_results = self._stats.build_combat_results(current_pilot_row)
        total_kills = combat_results.get("total_kills", 0)

        return {
            "name": str(career.root_career_id),
            "display_name": career.pilot_name,
            "country": career.country or "unknown",
            "missions_completed": len(sorties),
            "promotions_count": len(promotions),
            "awards_count": len(awards),
            "final_rank": final_rank,
            "total_score": 0,
            "total_kills": total_kills,
            "theatre_chain": career.theatre_labels,
            "source": "career",
        }

    # ------------------------------------------------------------------
    # Private: event mapper
    # ------------------------------------------------------------------

    def _map_event(
        self,
        row,
        country: Optional[str],
        seen_bonus_codes: Optional[set] = None,
        bonus_incidences: Optional[list] = None,
    ) -> Optional[Dict]:
        """
        Map a single event row to the frontend event dict shape.

        Placeholders are used for rank/award names until translation tables
        are provided. The placeholder keys (rank_<id>, award_<code>) surface
        visibly so missing translations are immediately obvious.

        Args:
            seen_bonus_codes: Mutable set tracking USSR bonus award_codes already
                              emitted into the Awards timeline. Pass None to skip
                              bonus deduplication (e.g. list-page callers).
            bonus_incidences: Mutable list that receives BONUS entries for duplicate
                              USSR bonus awards. Ignored when seen_bonus_codes is None.
        """
        event_type = row["type"]
        event_date = self._format_date(row["date"])

        if event_type == 6:  # Promotion
            rank_id = row["rankId"]
            country_int = _COUNTRY_CODE_MAP.get((country or '').lower(), 0)
            rank_name = self._rank_resolver.resolve(country_int, int(rank_id or -1))
            image_url = None
            modal_image_url = None
            subfolder = _rank_subfolder(country_int, event_date)
            if subfolder and rank_name:
                eng = rank_name.english
                normal = self._rank_index.get(subfolder, eng, 'normal')
                big = self._rank_index.get_with_normal_fallback(subfolder, eng, 'big')

                # USSR early/late cross-subfolder fallback
                if (normal is None or big is None) and subfolder in ('USSR/early', 'USSR/late'):
                    alt = 'USSR/late' if subfolder == 'USSR/early' else 'USSR/early'
                    if normal is None:
                        normal = self._rank_index.get(alt, eng, 'normal')
                    if big is None:
                        big = self._rank_index.get_with_normal_fallback(alt, eng, 'big')

                if normal:
                    image_url = (
                        f"/api/career_assets/CampaignRanksAwards"
                        f"/{normal.subfolder}/{normal.filename}"
                    )
                if big:
                    modal_image_url = (
                        f"/api/career_assets/CampaignRanksAwards"
                        f"/{big.subfolder}/{big.filename}"
                    )
            return {
                "type": "promotion",
                "date": event_date,
                "rank": rank_name.display if rank_name else f"rank_{rank_id}",
                "rank_code": rank_name.english if rank_name else f"rank_{rank_id}",
                "rank_id": rank_id,
                "image": None,
                "image_url": image_url,
                "modal_image_url": modal_image_url,
                "country": country,
            }

        if event_type == 8:  # Award
            award_code = str(row["tpar2"]) if row["tpar2"] else ""
            name_key = None
            image_url = None
            modal_image_url = None

            if award_code and self._award_index:
                normal = self._award_index.get(award_code, 'normal')
                big = self._award_index.get(award_code, 'big')
                if normal:
                    name_key = normal.name_key
                    image_url = (
                        f"/api/career_assets/CampaignRanksAwards"
                        f"/{normal.subfolder}/{normal.filename}"
                    )
                if big:
                    modal_image_url = (
                        f"/api/career_assets/CampaignRanksAwards"
                        f"/{big.subfolder}/{big.filename}"
                    )

            # USSR bonus deduplication: first occurrence stays in Awards;
            # subsequent occurrences are diverted to Other Incidences.
            if seen_bonus_codes is not None and award_code:
                is_ussr = (country or '').lower() == 'ussr'
                is_bonus = (
                    normal is not None
                    and 'bonus' in normal.filename.lower()
                )
                if is_ussr and is_bonus:
                    if award_code in seen_bonus_codes:
                        if bonus_incidences is not None:
                            bonus_incidences.append({
                                "type":     "BONUS",
                                "date":     event_date,
                                "name":     name_key or f"award_{award_code}",
                                "sort_key": event_date or "9999-99-99",
                            })
                        return None  # suppress from Awards timeline
                    seen_bonus_codes.add(award_code)

            return {
                "type": "award",
                "date": event_date,
                "name": name_key or f"award_{award_code}",
                "award_code": award_code,
                "image": None,
                "image_url": image_url,
                "modal_image_url": modal_image_url,
                "country": country,
            }

        if event_type == 10:  # Squadron transfer
            return {
                "type": "transfer",
                "date": event_date,
                "country": country,
            }

        logger.debug("Skipping unrecognised event type %d", event_type)
        return None

    # ------------------------------------------------------------------
    # Private: summary builder
    # ------------------------------------------------------------------

    def _build_summary(
        self,
        career: VirtualPilotCareer,
        events: List[Dict],
        sorties: list,
        combat_results: Dict,
        mission_stats_override: Optional[Dict] = None,
        first_pilot_row=None,
        last_pilot_row=None,
        aircraft_usage_override: Optional[Dict] = None,
    ) -> Dict:
        """
        Build the summary dict matching CampaignAggregator._calculate_summary() shape.

        Args:
            mission_stats_override: If supplied (from CareerDebriefingManager),
                replaces the sortie-count-based missions_stats stub with real
                flight-time data derived from parsed missionReport files.
            first_pilot_row: pilot row for the root career (used for starting_rank fallback).
            last_pilot_row:  pilot row for the most recent theatre (used for final_rank fallback).
            aircraft_usage_override: If supplied (from CareerDebriefingManager),
                provides aircraft_usage dict built from linked missionReport files.
        """
        promotions = [e for e in events if e.get("type") == "promotion"]
        awards = [e for e in events if e.get("type") == "award"]

        # Read rank directly from pilot rows for reliable "career start" and
        # "current/final" values even when promotion history is incomplete.
        country_int = _COUNTRY_CODE_MAP.get((career.country or "").lower(), 0)

        def _rank_from_pilot(row) -> str:
            if row is None:
                return "Unknown"
            try:
                rank_id = row["rankId"]
            except (IndexError, KeyError):
                return "Unknown"
            if rank_id is None:
                return "Unknown"
            rank_name = self._rank_resolver.resolve(country_int, int(rank_id))
            return rank_name.display if rank_name else f"rank_{rank_id}"

        starting_rank = _rank_from_pilot(first_pilot_row)
        final_rank = _rank_from_pilot(last_pilot_row)

        event_dates = [e["date"] for e in events if e.get("date")]
        first_date = min(event_dates) if event_dates else None
        last_date = max(event_dates) if event_dates else None

        if mission_stats_override is not None:
            missions_stats = mission_stats_override
        else:
            missions_stats = {
                "total_missions": len(sorties),
                "completed_missions": len(sorties),
                "successful_missions": len(sorties),
                "success_rate": 100 if sorties else 0,
                "total_flight_time": "00:00",   # stub: sortie duration columns TBD
                "average_duration": "00:00",
                "landings": [],
            }

        return {
            "combat_results": combat_results,
            "missions_stats": missions_stats,
            "aircraft_usage": aircraft_usage_override if aircraft_usage_override is not None else {},
            "career_progression": {
                "starting_rank": starting_rank,
                "final_rank": final_rank,
                "promotions_count": len(promotions),
                "awards_count": len(awards),
                "awards_list": [a.get("name", "Unknown") for a in awards],
            },
            "timeline": {
                "first_mission_date": first_date,
                "last_mission_date": last_date,
                "duration_days": self._calc_duration_days(first_date, last_date),
            },
        }

    # ------------------------------------------------------------------
    # Private: date helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_date(raw) -> Optional[str]:
        """Normalise an event.date value to ISO "YYYY-MM-DD" string."""
        if raw is None:
            return None
        if isinstance(raw, str):
            return raw.replace(".", "-").split("T")[0][:10]
        if isinstance(raw, (int, float)):
            try:
                return datetime.fromtimestamp(raw).strftime("%Y-%m-%d")
            except (OSError, OverflowError, ValueError):
                return None
        return None

    @staticmethod
    def _calc_duration_days(first: Optional[str], last: Optional[str]) -> Optional[int]:
        if not first or not last:
            return None
        try:
            d1 = datetime.strptime(first, "%Y-%m-%d")
            d2 = datetime.strptime(last, "%Y-%m-%d")
            return (d2 - d1).days
        except ValueError:
            return None

    @staticmethod
    def _safe_int_from_row(row, column: str) -> int:
        """Read an int from a sqlite3.Row, returning 0 on any error."""
        if row is None:
            return 0
        try:
            val = row[column]
            return int(val) if val is not None else 0
        except (IndexError, TypeError, ValueError):
            return 0

    @staticmethod
    def _safe_float_from_row(row, column: str) -> float:
        """Read a float from a sqlite3.Row, returning 0.0 on any error."""
        if row is None:
            return 0.0
        try:
            val = row[column]
            return float(val) if val is not None else 0.0
        except (IndexError, TypeError, ValueError):
            return 0.0

    def _build_award_index(self) -> AwardIndex:
        """
        Build the AwardIndex from CampaignRanksAwards JSON sidecar files.

        Tries data_dir first (tracker's local copy), then falls back to
        game_dir/data/swf (IL-2 game installation).
        """
        for assets_root in filter(None, [self._data_dir, self._game_dir and self._game_dir / 'data' / 'swf']):
            cra_dir = assets_root / 'CampaignRanksAwards'
            if cra_dir.is_dir():
                index = AwardIndex.build(assets_root)
                if index:
                    return index
        logger.info(
            "AwardIndex: CampaignRanksAwards not found in data_dir or game_dir; "
            "award images will not be resolved."
        )
        return AwardIndex.empty()

    def _build_rank_index(self) -> RankIndex:
        """
        Build the RankIndex from CampaignRanksAwards JSON sidecar files.

        Tries data_dir first (tracker's local copy), then falls back to
        game_dir/data/swf (IL-2 game installation).
        """
        for assets_root in filter(None, [self._data_dir, self._game_dir and self._game_dir / 'data' / 'swf']):
            cra_dir = assets_root / 'CampaignRanksAwards'
            if cra_dir.is_dir():
                index = RankIndex.build(assets_root)
                if index:
                    return index
        logger.info(
            "RankIndex: CampaignRanksAwards not found in data_dir or game_dir; "
            "rank images will not be resolved."
        )
        return RankIndex.empty()

    def _resolve_squadron_name(self, squadron_id: int) -> Optional[str]:
        """
        Look up the squadron short name for the given squadron.id.

        Tries paths in order:
          1. <game_dir>/data/swf/CampaignRanksAwards/squadrons/<configId>/info.locale=eng.txt
          2. <data_dir>/CampaignRanksAwards/squadrons/<configId>/info.locale=eng.txt

        Args:
            squadron_id: The squadron.id (= career.squadronId for the current theatre).

        Returns the short name string, or None if not available.
        """
        if not squadron_id:
            return None

        if self._game_dir is None and self._data_dir is None:
            logger.info(
                "Squadron name lookup skipped: neither game_dir nor data_dir is set."
            )
            return None

        try:
            squadron_row = self._db.get_squadron_by_id(squadron_id)
        except Exception as exc:
            logger.info("Squadron lookup failed for id=%d: %s", squadron_id, exc)
            return None

        if squadron_row is None:
            logger.info("Squadron row not found for id=%d", squadron_id)
            return None

        config_id = self._safe_int_from_row(squadron_row, "configId")
        if not config_id:
            logger.info("Squadron id=%d has no configId", squadron_id)
            return None

        # Build candidate paths, mirroring routes.py CampaignRanksAwards lookup:
        # 1. <game_dir>/data/swf/CampaignRanksAwards/squadrons/<configId>/info.locale=eng.txt
        # 2. <data_dir>/CampaignRanksAwards/squadrons/<configId>/info.locale=eng.txt
        candidate_paths = []
        if self._game_dir:
            candidate_paths.append(
                self._game_dir / "data" / "swf" / "CampaignRanksAwards" / "squadrons"
                / str(config_id) / "info.locale=eng.txt"
            )
        if self._data_dir:
            candidate_paths.append(
                self._data_dir / "CampaignRanksAwards" / "squadrons"
                / str(config_id) / "info.locale=eng.txt"
            )

        info_path = None
        for p in candidate_paths:
            logger.info("Squadron info candidate: %s (exists=%s)", p, p.exists())
            if p.exists():
                info_path = p
                break

        if info_path is None:
            logger.info(
                "Squadron info file not found for configId=%d (tried %d path(s))",
                config_id, len(candidate_paths)
            )
            return None

        try:
            content = info_path.read_text(encoding="utf-8", errors="replace")
            name = self._parse_squadron_short_name(content)
            logger.info("Squadron short name resolved: %r", name)
            return name
        except Exception as exc:
            logger.info("Failed to read squadron info file %s: %s", info_path, exc)
            return None

    def _resolve_squadron_name_by_config(
        self, career_id: int, config_id: int
    ) -> Optional[str]:
        """
        Look up a squadron display name given a careerId + configId pair.

        This is the counterpart to _resolve_squadron_name() for cases where the
        configId is already known (e.g. from event.squadronId on a type-9 event)
        and we do not need the intermediate squadron.id lookup.

        Returns the short name string, or None if unavailable.
        """
        if not config_id:
            return None

        if self._game_dir is None and self._data_dir is None:
            return None

        candidate_paths = []
        if self._game_dir:
            candidate_paths.append(
                self._game_dir / "data" / "swf" / "CampaignRanksAwards" / "squadrons"
                / str(config_id) / "info.locale=eng.txt"
            )
        if self._data_dir:
            candidate_paths.append(
                self._data_dir / "CampaignRanksAwards" / "squadrons"
                / str(config_id) / "info.locale=eng.txt"
            )

        for p in candidate_paths:
            if p.exists():
                try:
                    content = p.read_text(encoding="utf-8", errors="replace")
                    name = self._parse_squadron_short_name(content)
                    if name:
                        logger.debug(
                            "Squadron configId=%d resolved to %r", config_id, name
                        )
                        return name
                except Exception as exc:
                    logger.debug(
                        "Failed to read squadron info for configId=%d: %s", config_id, exc
                    )

        logger.debug(
            "Squadron configId=%d info file not found (tried %d path(s))",
            config_id, len(candidate_paths),
        )
        return None

    def _load_other_incidences(self, career: "VirtualPilotCareer") -> List[Dict]:
        """
        Build the full list of 'Other Incidences' entries across all theatre
        segments in the career chain.

        Each segment is queried independently (careerId + playerId) so that the
        careerId constraint is enforced per the spec.  Results are merged and
        re-sorted by sort_key (date) ascending.
        """
        results: List[Dict] = []

        for segment in career.chain:
            seg_career_id = int(segment["id"])
            seg_player_id = int(segment["playerId"])

            def _resolve(cid: int, cfgid: int, _self=self) -> Optional[str]:
                return _self._resolve_squadron_name_by_config(cid, cfgid)

            try:
                entries = load_other_incidences(
                    self._db, seg_career_id, seg_player_id, _resolve
                )
                results.extend(entries)
            except Exception as exc:
                logger.warning(
                    "Failed to load other incidences for segment careerId=%d: %s",
                    seg_career_id, exc,
                )

        results.sort(key=lambda e: e["sort_key"])
        return results

    @staticmethod
    def _parse_squadron_short_name(content: str) -> Optional[str]:
        """
        Parse the shortName field from an info.locale=eng.txt file.

        Expected format (pipe-delimited, comma-separated quoted fields):
            &names=date,name,shortName|
            *,'Full Squadron Name','Short Name'|

        Returns the short name (3rd field) from the first data row, or None.
        """
        for line in content.splitlines():
            line = line.strip()
            if not line.startswith("*,"):
                continue
            # Find the last single-quoted value on this line (the shortName field)
            match = _SQUADRON_SHORT_NAME_RE.search(line)
            if match:
                return match.group(1)
        return None
