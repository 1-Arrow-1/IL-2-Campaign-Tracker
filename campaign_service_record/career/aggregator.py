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
    - flight_time / landing outcomes come from parsed missionReport files via
      CareerDebriefingManager when available.
    - aircraft_usage is derived from cp.db mission/sortie rows so the career
      detail page matches the authoritative database totals.
"""

from collections import Counter
import json
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

# Only confirmed event types are processed. Others are silently skipped.
_CONFIRMED_EVENT_TYPES = [6, 8, 10]

# Maps lowercase career.country strings to integer country codes used in rank lookup
_COUNTRY_CODE_MAP: Dict[str, int] = {
    'germany': 201,
    'britain': 102,
    'usa':     103,
    'ussr':    101,
}

_OPERATIONAL_AWARD_BRANCH_PATTERNS = (
    ("fighters", re.compile(r"^(front_flying_clasp_for_fighters_in_|fighters_)")),
    ("bombers", re.compile(r"^(front_flying_clasp_for_bombers_in_|bombers_|bomber_)")),
    ("transport", re.compile(r"^(front_flying_clasp_for_transport_in_|transport_)")),
    ("attack_heavy_fighters", re.compile(r"^(attack_badge_for_destroyers_in_|attack_heavy_fighters_)")),
    ("attack", re.compile(r"^(ground_attack_badge_in_|attack_)")),
)

_OPERATIONAL_AWARD_GRADE_PATTERNS = (
    ("gold_with_pendant", re.compile(r"(gold_with_pendant|gold_clasp)$")),
    ("gold", re.compile(r"gold$")),
    ("silver", re.compile(r"silver$")),
    ("bronze", re.compile(r"bronze$")),
)

_OPERATIONAL_AWARD_GRADE_RANK = {
    "bronze": 1,
    "silver": 2,
    "gold": 3,
    "gold_with_pendant": 4,
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
        # Squadron name table: configId (str) -> {locale -> shortName}
        self._squadron_names: Dict[str, Dict[str, str]] = self._load_squadron_names()

        logger.info(
            "CareerAggregator init: game_dir=%s data_dir=%s "
            "award_index_entries=%d rank_index_entries=%d squadron_name_entries=%d",
            self._game_dir, self._data_dir,
            len(self._award_index), len(self._rank_index), len(self._squadron_names),
        )

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

    def has_debrief_cache(self, root_career_id: int) -> bool:
        """
        Return True if a valid, version-matched debrief cache_index.json exists
        for this career.

        Checks both file existence and the _version field so that a stale cache
        (wrong version) is treated the same as no cache — causing the API to set
        skip_debriefs=True and triggering the background-job / timer path on the
        frontend instead of a silent synchronous rebuild.
        """
        if self._cache_dir is None:
            return False
        cache_path = self._cache_dir / "career" / str(root_career_id) / "cache_index.json"
        if not cache_path.exists():
            return False
        try:
            data = json.loads(cache_path.read_text(encoding="utf-8"))
            return data.get("_version") == CareerDebriefingManager._CACHE_VERSION
        except (OSError, ValueError):
            return False

    def run_debrief_parse(
        self,
        root_career_id: int,
        progress_callback=None,
    ) -> None:
        """
        Build and cache the debriefing HTML for a career in a background thread.

        Creates a CareerDebriefingManager with an optional progress_callback and
        drives the full pipeline (build_debriefings_html → get_mission_stats →
        get_aircraft_usage).  Results are written to the cache by the manager;
        this method does not return HTML.

        Args:
            root_career_id:    The career.id of the chain root (extends = -1).
            progress_callback: Optional callable(current, total, message) called
                               after each mission is processed.

        Raises:
            ValueError if the career is not found.
            Any exception from CareerDebriefingManager propagates to the caller
            (background worker) for job-level error reporting.
        """
        career = self._resolver.get_career(root_career_id)
        if career is None:
            raise ValueError(f"Career not found: root_career_id={root_career_id}")
        if self._cache_dir is None:
            raise ValueError("cache_dir is not configured; cannot run debrief parse")

        debrief_manager = CareerDebriefingManager(
            db=self._db,
            career=career,
            linker=self._linker,
            cache_dir=self._cache_dir,
            progress_callback=progress_callback,
        )
        debrief_manager.build_debriefings_html()
        debrief_manager.get_mission_stats()
        debrief_manager.get_aircraft_usage()

    def get_career_detail(
        self, root_career_id: int, skip_debriefs: bool = False
    ) -> Optional[Dict]:
        """
        Get full career detail payload for a virtual pilot career.

        Args:
            root_career_id: The career.id of the chain root (extends = -1).
            skip_debriefs:  When True AND no cache exists, skip the slow
                            debriefing parse and return debriefings_pending=True
                            in the response so the frontend can trigger a
                            background parse job.  When False (default) or when
                            a cache already exists, the full parse runs inline.

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

        events_raw = self._db.get_events_for_pilots(
            career.all_pilot_ids, types=_CONFIRMED_EVENT_TYPES
        )
        # Sort by (segment_index, date) to enforce theatre chain order.
        # Pure date-sort is wrong when theatres have overlapping in-game date ranges
        # (a game bug): the player always experiences theatres sequentially, so all
        # events from segment 0 must precede segment 1, regardless of in-game dates.
        _pilot_segment = {pid: i for i, pid in enumerate(career.all_pilot_ids)}
        events_raw.sort(
            key=lambda r: (_pilot_segment.get(r["pilotId"], 0), r["date"] or "")
        )
        seen_bonus_codes: set = set()
        bonus_incidences: list = []
        mapped_events = []
        for row in events_raw:
            try:
                ev = self._map_event(
                    row, career.country,
                    seen_bonus_codes=seen_bonus_codes,
                    bonus_incidences=bonus_incidences,
                )
            except Exception as exc:
                logger.warning(
                    "Skipping event id=%s type=%s due to mapping error: %s",
                    row["id"] if "id" in row.keys() else "?",
                    row["type"] if "type" in row.keys() else "?",
                    exc,
                    exc_info=True,
                )
                continue
            if ev is not None:
                mapped_events.append(ev)
        mapped_events, award_repeat_incidences, showcase_awards = self._normalize_award_events(
            mapped_events
        )

        # Build combat results from the most current pilot row (all-theatre totals)
        combat_results = self._stats.build_combat_results(current_pilot_row)

        # Inject PCP score from the most current pilot record (preserve decimal)
        pcp_score = self._safe_float_from_row(current_pilot_row, "pcp")
        combat_results["pcp_score"] = pcp_score

        sorties = self._db.get_sorties_for_pilot(career.all_pilot_ids)

        # Determine whether to run the debriefing pipeline or defer it.
        # skip_debriefs=True defers parsing to a background job when no cache exists.
        cache_exists = self.has_debrief_cache(root_career_id)
        debriefings_pending = False

        debrief_manager: Optional[CareerDebriefingManager] = None
        if self._cache_dir is not None and (cache_exists or not skip_debriefs):
            try:
                debrief_manager = CareerDebriefingManager(
                    db=self._db,
                    career=career,
                    linker=self._linker,
                    cache_dir=self._cache_dir,
                )
            except Exception as exc:
                logger.warning("CareerDebriefingManager init failed: %s", exc)
        elif skip_debriefs and not cache_exists:
            debriefings_pending = True

        debriefings_html = ""
        mission_stats_override: Optional[Dict] = None
        air_kills_by_type_override: Optional[Dict] = None
        debrief_results = None
        if debrief_manager is not None:
            try:
                debriefings_html = debrief_manager.build_debriefings_html()
                mission_stats_override = debrief_manager.get_mission_stats()
                air_kills_by_type_override = debrief_manager.get_air_kills_by_type()
                debrief_results = debrief_manager._get_results()
            except Exception as exc:
                logger.warning("CareerDebriefingManager build failed: %s", exc)

        first_pilot_row = self._db.get_pilot_by_id(career.pilot_id)
        aircraft_usage = self._calculate_aircraft_usage_from_db(career, debrief_results)
        summary = self._build_summary(
            career, mapped_events, sorties, combat_results, mission_stats_override,
            first_pilot_row=first_pilot_row,
            last_pilot_row=current_pilot_row,
            aircraft_usage_override=aircraft_usage,
            air_kills_by_type_override=air_kills_by_type_override,
        )

        # Resolve current squadron short name via career chain's current squadronId
        current_career_squadron_id = (
            int(career.chain[-1]["squadronId"]) if career.chain else 0
        )
        squadron_short_name = self._resolve_squadron_name(current_career_squadron_id)

        # Resolve pilot role from current pilot state
        # state=1 → Commander, state=8 → Deputy Commander
        _pilot_state = current_pilot_row["state"] if current_pilot_row else None
        pilot_role = (
            "commander" if _pilot_state == 1
            else "deputy_commander" if _pilot_state == 8
            else ""
        )

        # Build other incidences (recovery, commander, transfer) and merge bonus duplicates
        other_incidences = self._load_other_incidences(career)
        if bonus_incidences or award_repeat_incidences:
            other_incidences = sorted(
                other_incidences + bonus_incidences + award_repeat_incidences,
                key=lambda e: e["sort_key"],
            )

        squadron_records = self._build_squadron_records(career)
        current_squadron_record = next(
            (record for record in squadron_records if record.get("is_current")),
            None,
        )
        squadron_members = (
            current_squadron_record.get("members", [])
            if current_squadron_record else []
        )
        squadron_totals = (
            current_squadron_record.get("totals", {})
            if current_squadron_record else {}
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
            "showcase_awards": showcase_awards,
            "debriefings_html": debriefings_html,
            "debriefings_pending": debriefings_pending,
            "effective_locale": get_career_effective_locale(str(career.root_career_id)),
            "summary": summary,
            # Career-specific extras
            "source": "career",
            "theatre_chain": career.theatre_labels,
            "birth_date": career.birth_date,
            "pcp_score": pcp_score,
            "squadron_short_name": squadron_short_name or "",
            "pilot_role": pilot_role,
            "other_incidences": other_incidences,
            "squadron_members": squadron_members,
            "squadron_totals": squadron_totals,
            "squadron_records": squadron_records,
        }

    # ------------------------------------------------------------------
    # Private: list item builder
    # ------------------------------------------------------------------

    def _build_list_item(self, career: VirtualPilotCareer) -> Dict:
        # Use most current pilot row for kill totals (each theatre has its own pilot row)
        current_pilot_row = self._db.get_pilot_by_id(career.last_pilot_id)
        events_raw = self._db.get_events_for_pilots(
            career.all_pilot_ids, types=_CONFIRMED_EVENT_TYPES
        )
        _pilot_segment = {pid: i for i, pid in enumerate(career.all_pilot_ids)}
        events_raw.sort(
            key=lambda r: (_pilot_segment.get(r["pilotId"], 0), r["date"] or "")
        )
        promotions = [
            e for e in events_raw
            if e["type"] == 6
            and (self._rank_resolver.is_mod_mode or int(e["rankId"] or -1) <= 4)
        ]
        awards = [e for e in events_raw if e["type"] == 8]
        sorties = self._db.get_sorties_for_pilot(career.all_pilot_ids)

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
            # Ranks > 4 only exist in the expanded mod. Hide them when the mod
            # is not installed so that rank_5 / rank_6 … placeholders never surface.
            if not self._rank_resolver.is_mod_mode and int(rank_id or -1) > 4:
                return None
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
            normal = None  # initialised here so USSR bonus-dedup block can safely reference it
            big = None

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

    def _normalize_award_events(self, events: List[Dict]) -> tuple[List[Dict], List[Dict], List[Dict]]:
        """Normalize repeated operational clasp/badge awards for timeline and showcase use."""
        normalized_events: List[Dict] = []
        incidences: List[Dict] = []
        showcase_awards: List[Dict] = []
        highest_branch_grade: Dict[str, int] = {}
        latest_operational_award: Optional[Dict] = None

        for event in events:
            if event.get("type") != "award":
                normalized_events.append(event)
                continue

            classification = self._classify_operational_award(event)
            if classification is None:
                normalized_events.append(event)
                showcase_awards.append(event)
                continue

            branch = classification["branch"]
            grade_rank = _OPERATIONAL_AWARD_GRADE_RANK[classification["grade"]]
            latest_operational_award = event

            if grade_rank <= highest_branch_grade.get(branch, 0):
                incidences.append({
                    "type": "AWARD_REPEAT",
                    "date": event.get("date"),
                    "name": event.get("name") or event.get("award_code") or "Unknown",
                    "sort_key": event.get("date") or "9999-99-99",
                })
                continue

            highest_branch_grade[branch] = grade_rank
            normalized_events.append(event)
            showcase_awards.append(event)

        if latest_operational_award is not None:
            showcase_awards = [
                ev for ev in showcase_awards
                if self._classify_operational_award(ev) is None
            ]
            showcase_awards.append(latest_operational_award)

        return normalized_events, incidences, showcase_awards

    def _classify_operational_award(self, event: Dict) -> Optional[Dict[str, str]]:
        """Return branch/grade for German operational clasp and badge awards, else None."""
        name_key = str(event.get("name") or "").strip().lower()
        if not name_key:
            return None

        branch = None
        for candidate_branch, pattern in _OPERATIONAL_AWARD_BRANCH_PATTERNS:
            if pattern.search(name_key):
                branch = candidate_branch
                break
        if branch is None:
            return None

        grade = None
        for candidate_grade, pattern in _OPERATIONAL_AWARD_GRADE_PATTERNS:
            if pattern.search(name_key):
                grade = candidate_grade
                break
        if grade is None:
            return None

        return {"branch": branch, "grade": grade}

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
        air_kills_by_type_override: Optional[Dict] = None,
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
            air_kills_by_type_override: If supplied (from CareerDebriefingManager),
                provides exact destroyed aircraft types for flying air kills only.
        """
        promotions = [e for e in events if e.get("type") == "promotion"]
        awards = [e for e in events if e.get("type") == "award"]

        # Starting rank is the rank immediately before the first promotion.
        # Promotion events store the rank gained at that event, so we derive
        # start as (first_promotion_rank_id - 1) when possible.
        country_int = _COUNTRY_CODE_MAP.get((career.country or "").lower(), 0)

        def _rank_from_id(rank_id) -> str:
            if rank_id is None:
                return "Unknown"
            try:
                rank_id_int = int(rank_id)
            except (TypeError, ValueError):
                return "Unknown"
            if rank_id_int < 0:
                return "Unknown"
            rank_name = self._rank_resolver.resolve(country_int, rank_id_int)
            return rank_name.display if rank_name else f"rank_{rank_id_int}"

        def _rank_from_pilot(row) -> str:
            if row is None:
                return "Unknown"
            try:
                rank_id = row["rankId"]
            except (IndexError, KeyError):
                return "Unknown"
            return _rank_from_id(rank_id)

        valid_promotion_rank_ids = []
        valid_promotion_ranks = []
        for p in promotions:
            rank_text = p.get("rank")
            if not rank_text or str(rank_text).lower() in {"unknown", "rank_-1"}:
                continue
            try:
                rank_id_int = int(p.get("rank_id", -1))
            except (TypeError, ValueError):
                continue
            if rank_id_int < 0:
                continue
            valid_promotion_rank_ids.append(rank_id_int)
            valid_promotion_ranks.append(rank_text)

        if valid_promotion_rank_ids:
            derived_start_rank = _rank_from_id(valid_promotion_rank_ids[0] - 1)
            if derived_start_rank != "Unknown":
                starting_rank = derived_start_rank
            else:
                starting_rank = _rank_from_pilot(first_pilot_row)
        else:
            starting_rank = _rank_from_pilot(first_pilot_row)

        final_rank = _rank_from_pilot(last_pilot_row)
        if final_rank == "Unknown" and valid_promotion_ranks:
            final_rank = valid_promotion_ranks[-1]

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
            "air_kills_by_type": air_kills_by_type_override if air_kills_by_type_override is not None else {},
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

    def _calculate_aircraft_usage_from_db(
        self,
        career: VirtualPilotCareer,
        debrief_results: Optional[List] = None,
    ) -> Dict:
        """
        Build aircraft usage from cp.db mission/sortie rows.

        Missions and plane kills come from cp.db and therefore include parked
        aircraft. If debrief results are available, they are used only to pick a
        readable aircraft display label for each cp.db plane key.
        """
        usage: Dict[str, Dict[str, int]] = {}
        label_votes: Dict[str, Counter] = {}
        debrief_by_mission: Dict[int, str] = {}

        if debrief_results:
            for result in debrief_results:
                aircraft_label = str(getattr(result, "aircraft", "") or "").strip()
                if aircraft_label:
                    debrief_by_mission[int(result.mission_id)] = aircraft_label

        for chain_row in career.chain:
            career_id = int(chain_row["id"])
            player_id = int(chain_row["playerId"])
            missions = self._db.get_missions_for_career(career_id, player_id)
            for mission in missions:
                mission_id = int(mission["id"])
                sortie = self._db.get_sortie_for_mission(mission_id, player_id)
                if sortie is None:
                    continue

                plane_key = self._normalize_plane_key(mission["plane0"])
                if plane_key not in usage:
                    usage[plane_key] = {"missions": 0, "kills": 0}

                usage[plane_key]["missions"] += 1
                usage[plane_key]["kills"] += (
                    int(sortie["killLightPlane"] or 0)
                    + int(sortie["killMediumPlane"] or 0)
                    + int(sortie["killHeavyPlane"] or 0)
                    + int(sortie["killStaticPlane"] or 0)
                )

                hinted_label = debrief_by_mission.get(mission_id)
                if hinted_label:
                    label_votes.setdefault(plane_key, Counter())[hinted_label] += 1

        resolved: Dict[str, Dict[str, int]] = {}
        for plane_key, data in sorted(
            usage.items(),
            key=lambda item: (item[1]["missions"], item[1]["kills"]),
            reverse=True,
        ):
            label_counter = label_votes.get(plane_key)
            if label_counter:
                label = label_counter.most_common(1)[0][0]
            else:
                label = self._format_plane_label(plane_key)
            resolved[label] = data

        return resolved

    @staticmethod
    def _normalize_plane_key(raw_plane) -> str:
        """Reduce cp.db mission.plane0 values to a stable basename key."""
        raw = str(raw_plane or "").strip().lower().replace("\\", "/")
        base = raw.split("/")[-1]
        return base[:-4] if base.endswith(".txt") else base

    @staticmethod
    def _format_plane_label(plane_key: str) -> str:
        """Best-effort fallback label when no linked debrief label exists."""
        if not plane_key:
            return "Unknown"
        special = {
            "bf109f2": "Bf 109 F-2",
            "bf109f4": "Bf 109 F-4",
            "bf109g4": "Bf 109 G-4",
            "bf109g6": "Bf 109 G-6",
            "bf109g6late": "Bf 109 G-6 Late",
            "bf109g6as": "Bf 109 G-6AS",
        }
        if plane_key in special:
            return special[plane_key]
        return plane_key

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

    def _load_squadron_names(self) -> Dict[str, Dict[str, str]]:
        """
        Load squadrons.json from data_dir/CampaignRanksAwards/squadrons.json.

        Returns a dict of {configId_str: {locale: shortName}}.
        Falls back to an empty dict when the file is missing or unreadable.
        """
        if self._data_dir is None:
            return {}
        path = self._data_dir / "squadrons.json"
        if not path.exists():
            logger.warning("squadrons.json not found at %s", path)
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            logger.info("Loaded %d squadron name entries from %s", len(data), path)
            return data
        except (OSError, ValueError) as exc:
            logger.warning("Failed to load squadrons.json: %s", exc)
            return {}

    def _squadron_short_name(self, config_id: int, locale: str = "en") -> Optional[str]:
        """
        Return the localised short name for a squadron configId.

        Falls back to 'en' when the requested locale is absent.
        Returns None when configId is unknown.
        """
        entry = self._squadron_names.get(str(config_id))
        if not entry:
            return None
        return entry.get(locale) or entry.get("en")

    def _resolve_squadron_name(self, squadron_id: int, locale: str = "en") -> Optional[str]:
        """
        Look up the squadron short name for the given squadron.id.

        Resolves squadron.id → configId via cp.db, then looks up the name in
        the in-memory squadrons.json table loaded at startup.

        Returns the short name string, or None if not available.
        """
        if not squadron_id:
            return None
        try:
            squadron_row = self._db.get_squadron_by_id(squadron_id)
        except Exception as exc:
            logger.debug("Squadron lookup failed for id=%d: %s", squadron_id, exc)
            return None
        if squadron_row is None:
            logger.debug("Squadron row not found for id=%d", squadron_id)
            return None
        config_id = self._safe_int_from_row(squadron_row, "configId")
        if not config_id:
            return None
        name = self._squadron_short_name(config_id, locale)
        logger.debug("Squadron id=%d configId=%d -> %r", squadron_id, config_id, name)
        return name

    def _resolve_squadron_name_by_config(
        self, career_id: int, config_id: int, locale: str = "en"
    ) -> Optional[str]:
        """
        Look up a squadron display name given a configId (no extra DB round-trip).

        Used for type-10 squadron-change events where configId is already known.
        Returns the short name string, or None if unavailable.
        """
        if not config_id:
            return None
        name = self._squadron_short_name(config_id, locale)
        logger.debug("Squadron configId=%d -> %r", config_id, name)
        return name

    # Combat award precedence: award_code (str) -> rank (int, lower = higher honour).
    # Only combat/gallantry awards are listed; all others are ignored when resolving
    # the highest award for a pilot.
    _COMBAT_AWARD_PRECEDENCE: Dict[str, int] = {
        # Germany
        "201038": 1,  "201037": 2,  "201036": 3,  "201008": 4,  "201007": 5,
        "201006": 6,  "201005": 7,  "201004": 10, "201035": 12, "201003": 14,
        "201002": 16, "201001": 18,
        # Britain
        "102020": 1,  "102019": 2,  "102012": 4,  "102011": 5,  "102010": 6,
        "102009": 7,  "102008": 10, "102007": 11, "102006": 12, "102005": 18,
        "102004": 19, "102003": 20,
        # USA
        "103026": 1,  "103025": 3,  "103024": 4,  "103023": 5,  "103022": 6,
        "103021": 7,  "103020": 9,  "103019": 10, "103018": 11, "103017": 13,
        "103016": 15, "103015": 16, "103014": 17, "103013": 18, "103012": 19,
        "103011": 20, "103010": 22, "103009": 23, "103008": 24, "103007": 26,
        "103006": 27, "103005": 28, "103004": 29, "103003": 30, "103002": 31,
        # USSR
        "101021": 1,  "101022": 1,  "101023": 3,  "101024": 3,  "101019": 5,
        "101020": 5,  "101017": 6,  "101018": 6,  "101015": 7,  "101016": 7,
        "101013": 9,  "101014": 9,  "101011": 11, "101012": 11, "101009": 13,
        "101010": 13, "101007": 15, "101008": 15, "101006": 17, "101001": 19,
        "101002": 19, "101003": 21, "101004": 21, "101005": 23,
    }

    # Kill-bucket definitions for squadron member rows (subset of _KILL_BUCKETS)
    _SQ_KILL_BUCKETS = [
        ("kills_air",       ["killLightPlane", "killMediumPlane", "killHeavyPlane", "killStaticPlane"]),
        ("kills_vehicles",  ["killTruck", "killCar", "killLightTank", "killMediumTank", "killHeavyTank"]),
        ("kills_railroad",  ["killTrainLocomotive", "killTrainVagon", "killRailwayStationFacility"]),
        ("kills_armaments", ["killMachineGun", "killFieldGun", "killHowitzer", "killNavalGun",
                             "killAirDefence", "killRocketLauncher", "killSearchlight"]),
        ("kills_buildings", ["killTownBuilding", "killRuralYard", "killFactoryBuilding",
                             "killAirfieldFacility", "killBridge"]),
        ("kills_marine",    ["killLightShip", "killLargeCargoShip", "killSubmarine", "killDestroyerShip"]),
    ]

    def _build_squadron_members(
        self, squadron_id: int, country: Optional[str],
        player_all_pilot_ids: Optional[List[int]] = None,
        max_award_date: Optional[str] = None,
    ):
        """
        Build squadron_members list and squadron_totals dict for the detail response.

        Returns (members: List[Dict], totals: Dict).
        Empty lists/dicts are returned when squadron_id is 0 or the query fails.
        """
        if not squadron_id:
            return [], {}

        try:
            rows = self._db.get_squadron_members(squadron_id)
        except Exception as exc:
            logger.warning("get_squadron_members(%d) failed: %s", squadron_id, exc)
            return [], {}

        country_int = _COUNTRY_CODE_MAP.get((country or '').lower(), 0)
        subfolder = _rank_subfolder(country_int, None)  # date not needed for preview lookup

        totals: Dict = {key: 0 for key, _ in self._SQ_KILL_BUCKETS}
        totals["kill_assist"] = 0
        members = []

        for row in rows:
            member: Dict = {}

            # --- Name ---
            first = (row["name"] or "").strip()
            last  = (row["lastName"] or "").strip()
            member["name"] = f"{first} {last}".strip() if first or last else "—"
            # Keep raw parts for cross-theatre ID lookup (popped in second pass)
            member["_first_name"] = first
            member["_last_name"]  = last

            # --- Rank ---
            rank_id = row["rankId"] if "rankId" in row.keys() else None
            member["rank_id"] = int(rank_id) if rank_id is not None else -1
            rank_image_url = None
            rank_display = ""
            if rank_id is not None and subfolder:
                rank_name = self._rank_resolver.resolve(country_int, int(rank_id))
                if rank_name:
                    rank_display = rank_name.display
                    asset = self._rank_index.get(subfolder, rank_name.english, 'normal')
                    # USSR cross-subfolder fallback
                    if asset is None and subfolder in ('USSR/early', 'USSR/late'):
                        alt = 'USSR/late' if subfolder == 'USSR/early' else 'USSR/early'
                        asset = self._rank_index.get(alt, rank_name.english, 'normal')
                    if asset:
                        rank_image_url = (
                            f"/api/career_assets/CampaignRanksAwards"
                            f"/{asset.subfolder}/{asset.filename}"
                        )
            member["rank_display"] = rank_display
            member["rank_image_url"] = rank_image_url

            # --- State ---
            member["state"] = int(row["state"]) if "state" in row.keys() and row["state"] is not None else 0

            # --- Kill buckets ---
            for key, columns in self._SQ_KILL_BUCKETS:
                total = sum(self._safe_int_from_row(row, col) for col in columns)
                member[key] = total
                totals[key] += total

            member["kill_assist"] = self._safe_int_from_row(row, "killAssist")
            totals["kill_assist"] += member["kill_assist"]

            # --- Sorties / flight time ---
            member["sorties"]      = self._safe_int_from_row(row, "sorties")
            member["sorties_good"] = self._safe_int_from_row(row, "goodSorties")
            # flightTime is stored in seconds in cp.db
            member["flight_time_sec"] = self._safe_int_from_row(row, "flightTime")

            # Store pilot id for award lookup (resolved in second pass below)
            member["_pilot_id"] = self._safe_int_from_row(row, "id")
            member["_ins_date"] = str(row["insDate"]) if "insDate" in row.keys() and row["insDate"] else ""

            members.append(member)

        # --- Highest combat award (batch query, second pass) ---
        # Each theatre creates a NEW pilot row (new id) for each pilot, while
        # award events remain under the old row's id.  We resolve all historical
        # ids for every squadron member via name lookup, then build a map:
        #   historical_id → canonical_current_id
        # so every award is credited to the right row regardless of which
        # theatre it was earned in.
        #
        # player_all_pilot_ids is merged as an extra safety net: the player's
        # name lookup already covers all their theatre rows, but passing the
        # explicit list costs nothing and guards against unlikely name clashes.
        player_ids_set = set(player_all_pilot_ids or [])
        historical_to_canonical: Dict[int, int] = {}
        normalized_max_award_date = self._format_date(max_award_date) if max_award_date else None

        for member in members:
            canonical_id = member["_pilot_id"]
            if not canonical_id:
                continue
            fname = member.get("_first_name", "")
            lname = member.get("_last_name", "")
            max_ins_date = member.get("_ins_date", "")
            try:
                hist_ids = self._db.get_pilot_ids_by_name_before_ins_date(
                    fname, lname, max_ins_date
                )
            except Exception as exc:
                logger.warning(
                    "get_pilot_ids_by_name_before_ins_date(%s %s, %s) failed: %s",
                    fname, lname, max_ins_date, exc,
                )
                hist_ids = [canonical_id]
            for hid in hist_ids:
                historical_to_canonical[hid] = canonical_id

        # Also map every explicit player historical ID to the player's current row
        # (handles theatres where the player changed country / name would differ)
        member_ids = {m["_pilot_id"] for m in members if m["_pilot_id"]}
        player_canonical_id: Optional[int] = next(iter(player_ids_set & member_ids), None)
        if player_canonical_id:
            for hid in player_ids_set:
                historical_to_canonical.setdefault(hid, player_canonical_id)

        try:
            award_rows = self._db.get_award_events_for_pilots(list(historical_to_canonical))
        except Exception as exc:
            logger.warning("get_award_events_for_pilots failed: %s", exc)
            award_rows = []

        # Build best-award-code per canonical pilot_id
        best_award: Dict[int, str] = {}
        for ar in award_rows:
            award_date = self._format_date(ar["date"]) if "date" in ar.keys() else None
            if normalized_max_award_date and award_date and award_date >= normalized_max_award_date:
                continue
            raw_pid = int(ar["pilotId"])
            code    = str(ar["tpar2"]) if ar["tpar2"] else ""
            if not code:
                continue
            rank = self._COMBAT_AWARD_PRECEDENCE.get(code)
            if rank is None:
                continue  # not a combat award
            pid = historical_to_canonical.get(raw_pid, raw_pid)
            existing = best_award.get(pid)
            if existing is None or rank < self._COMBAT_AWARD_PRECEDENCE.get(existing, 9999):
                best_award[pid] = code

        # Resolve image URL for each pilot's best award, then clean up temp fields
        for member in members:
            member.pop("_first_name", None)
            member.pop("_last_name", None)
            member.pop("_ins_date", None)
            pid  = member.pop("_pilot_id", None)
            code = best_award.get(pid) if pid else None
            if code and self._award_index:
                asset = self._award_index.get(code, 'normal')
                if asset:
                    member["highest_award_code"]        = code
                    member["highest_award_precedence"]  = self._COMBAT_AWARD_PRECEDENCE.get(code)
                    member["highest_award_name_key"]    = f"progression.awards.{asset.name_key}"
                    member["highest_award_image_url"]   = (
                        f"/api/career_assets/CampaignRanksAwards"
                        f"/{asset.subfolder}/{asset.filename}"
                    )
                    continue
            member["highest_award_code"]        = None
            member["highest_award_precedence"]  = None
            member["highest_award_name_key"]    = None
            member["highest_award_image_url"]   = None

        return members, totals

    def _build_squadron_records(self, career: "VirtualPilotCareer") -> List[Dict]:
        """
        Build selectable squadron-stat snapshots for each theatre segment.

        Each theatre segment has its own player row and squadronId. The detail
        page can therefore offer a historical end-of-theatre roster selector by
        building one record per segment.
        """
        records: List[Dict] = []

        for idx, segment in enumerate(career.chain):
            segment_pilot_id = self._safe_int_from_row(segment, "playerId")
            segment_career_id = self._safe_int_from_row(segment, "id")
            next_segment = career.chain[idx + 1] if idx + 1 < len(career.chain) else None
            next_segment_start_date = (
                str(next_segment["startDate"])
                if next_segment is not None and "startDate" in next_segment.keys() and next_segment["startDate"]
                else None
            )
            pilot_row = self._db.get_pilot_by_id(segment_pilot_id) if segment_pilot_id else None
            squadron_id = self._safe_int_from_row(pilot_row, "squadronId")
            squadron_name = self._resolve_squadron_name(squadron_id) or ""
            members, totals = self._build_squadron_members(
                squadron_id,
                career.country,
                player_all_pilot_ids=career.all_pilot_ids[: idx + 1],
                max_award_date=next_segment_start_date,
            )
            pilot_state = self._safe_int_from_row(pilot_row, "state")
            pilot_role = (
                "commander" if pilot_state == 1
                else "deputy_commander" if pilot_state == 8
                else ""
            )

            records.append({
                "theatre_index": idx,
                "theatre_label": (
                    career.theatre_labels[idx]
                    if idx < len(career.theatre_labels)
                    else f"Theatre {idx + 1}"
                ),
                "career_id": segment_career_id,
                "pilot_id": segment_pilot_id,
                "squadron_id": squadron_id,
                "squadron_short_name": squadron_name,
                "pilot_role": pilot_role,
                "is_current": idx == len(career.chain) - 1,
                "members": members,
                "totals": totals,
            })

        return records

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
