from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from campaign_service_record.api.routes import (
    _career_story_sort_key,
    _dedupe_story_honors,
    _filter_story_honors_for_sortie,
    _story_other_incidences_for_mission,
    _story_theatre_context_for_segment,
)
from llm_story_generator import build_story_input


def test_filter_story_honors_for_sortie_hides_honors_before_last_sortie():
    awards, promotion, squadron = _filter_story_honors_for_sortie(
        is_last_sortie_of_day=False,
        mission_awards=["German Cross in Gold", "Wound Badge in Black"],
        mission_promotion="Unteroffizier",
        squadron_context={
            "promotions": ["Squadmate promoted"],
            "awards": ["Squadmate awarded Iron Cross 2nd Class"],
            "kia": ["Another pilot missing"],
        },
    )

    assert awards == []
    assert promotion == ""
    assert squadron["promotions"] == []
    assert squadron["awards"] == []
    assert squadron["kia"] == ["Another pilot missing"]


def test_filter_story_honors_for_sortie_keeps_honors_for_last_sortie():
    awards, promotion, squadron = _filter_story_honors_for_sortie(
        is_last_sortie_of_day=True,
        mission_awards=["German Cross in Gold", "Wound Badge in Black"],
        mission_promotion="Unteroffizier",
        squadron_context={
            "promotions": ["Squadmate promoted"],
            "awards": ["Squadmate awarded Iron Cross 2nd Class"],
            "kia": ["Another pilot missing"],
        },
    )

    assert awards == ["German Cross in Gold", "Wound Badge in Black"]
    assert promotion == "Unteroffizier"
    assert squadron["promotions"] == ["Squadmate promoted"]
    assert squadron["awards"] == ["Squadmate awarded Iron Cross 2nd Class"]
    assert squadron["kia"] == ["Another pilot missing"]


def test_dedupe_story_honors_only_consumes_honors_when_present_after_filtering():
    attributed_awards = set()
    attributed_promotions = set()

    awards, promotion = _dedupe_story_honors(
        [],
        "",
        attributed_awards=attributed_awards,
        attributed_promotions=attributed_promotions,
    )
    assert awards == []
    assert promotion == ""
    assert attributed_awards == set()
    assert attributed_promotions == set()

    awards, promotion = _dedupe_story_honors(
        ["German Cross in Gold", "Wound Badge in Black"],
        "Unteroffizier",
        attributed_awards=attributed_awards,
        attributed_promotions=attributed_promotions,
    )
    assert awards == ["German Cross in Gold", "Wound Badge in Black"]
    assert promotion == "Unteroffizier"

    awards, promotion = _dedupe_story_honors(
        ["German Cross in Gold", "Wound Badge in Black"],
        "Unteroffizier",
        attributed_awards=attributed_awards,
        attributed_promotions=attributed_promotions,
    )
    assert awards == []
    assert promotion == ""


def test_story_other_incidences_for_mission_only_returns_allowed_types():
    incidences = [
        {"type": "RECOVERY", "start_date": "1941-10-05", "end_date": "1941-10-08", "duration_days": 3, "source_mission_id": 3032, "sort_key": "1941-10-05"},
        {"type": "COMMAND", "date": "1941-10-05", "squadron": "I./JG 54", "source_mission_id": 3032, "sort_key": "1941-10-05"},
        {"type": "SQUADRON_CHANGE", "date": "1941-10-05", "old_squadron": "II./JG 52", "new_squadron": "I./JG 54", "source_mission_id": 3032, "sort_key": "1941-10-05"},
        {"type": "BONUS", "date": "1941-10-05", "sort_key": "1941-10-05"},
        {"type": "RECOVERY", "start_date": "1941-10-09", "end_date": "1941-10-10", "duration_days": 1, "sort_key": "1941-10-09"},
    ]

    lines = _story_other_incidences_for_mission(incidences, "1941-10-05", 3032)

    assert lines == [
        "Recovery from injury: 1941-10-05 to 1941-10-08 (3 days)",
        "Appointment as squadron commander of I./JG 54",
        "Transfer from II./JG 52 to I./JG 54",
    ]


def test_story_other_incidences_for_mission_does_not_attach_recovery_to_other_sortie_same_day():
    incidences = [
        {"type": "RECOVERY", "start_date": "1941-10-05", "end_date": "1941-10-08", "duration_days": 3, "source_mission_id": 3032, "sort_key": "1941-10-05"},
        {"type": "COMMAND", "date": "1941-10-05", "squadron": "I./JG 54", "source_mission_id": 3032, "sort_key": "1941-10-05"},
        {"type": "SQUADRON_CHANGE", "date": "1941-10-05", "old_squadron": "II./JG 52", "new_squadron": "I./JG 54", "source_mission_id": 3032, "sort_key": "1941-10-05"},
    ]

    lines = _story_other_incidences_for_mission(incidences, "1941-10-05", 3031)

    assert lines == []


def test_story_other_incidences_for_mission_falls_back_to_date_when_no_source_mission_id_exists():
    incidences = [
        {"type": "COMMAND", "date": "1941-10-05", "squadron": "I./JG 54", "sort_key": "1941-10-05"},
        {"type": "SQUADRON_CHANGE", "date": "1941-10-05", "old_squadron": "II./JG 52", "new_squadron": "I./JG 54", "sort_key": "1941-10-05"},
    ]

    lines = _story_other_incidences_for_mission(incidences, "1941-10-05", 3031)

    assert lines == [
        "Appointment as squadron commander of I./JG 54",
        "Transfer from II./JG 52 to I./JG 54",
    ]


def test_story_theatre_context_for_segment_uses_info_id_mapping():
    theatre, location = _story_theatre_context_for_segment({"infoId": "BoL41"})

    assert theatre == "Battle of Leningrad 1941"
    assert location == "Leningrad Front"


def test_build_story_input_preserves_explicit_mission_theatre_and_location():
    story_input = build_story_input(
        {
            "player": {"aircraft": "Bf 109 F-4"},
            "summary": {"final_state": "Landed", "flight_duration": "00:34:00"},
            "events": [],
        },
        career_id=74,
        mission_id=3006,
        mission_date="1941-09-27",
        squadron="II./JG 52",
        mission_theatre="Battle of Leningrad 1941",
        mission_location="Leningrad Front",
        country="germany",
        pilot_last_name="Bleiholder",
    )

    assert story_input["mission"]["theatre"] == "Battle of Leningrad 1941"
    assert story_input["mission"]["location"] == "Leningrad Front"


def test_career_story_sort_key_prioritizes_segment_before_date():
    leningrad_later_date = _career_story_sort_key(0, "1941-11-06", 3085)
    moscow_earlier_date = _career_story_sort_key(1, "1941-11-05", 3135)

    assert leningrad_later_date < moscow_earlier_date
