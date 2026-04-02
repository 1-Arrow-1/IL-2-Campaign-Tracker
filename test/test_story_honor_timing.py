from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from campaign_service_record.api.routes import (
    _dedupe_story_honors,
    _filter_story_honors_for_sortie,
    _story_other_incidences_for_date,
)


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


def test_story_other_incidences_for_date_only_returns_allowed_types_on_matching_date():
    incidences = [
        {"type": "RECOVERY", "start_date": "1941-10-05", "end_date": "1941-10-08", "duration_days": 3, "sort_key": "1941-10-05"},
        {"type": "COMMAND", "date": "1941-10-05", "squadron": "I./JG 54", "sort_key": "1941-10-05"},
        {"type": "SQUADRON_CHANGE", "date": "1941-10-05", "old_squadron": "I./JG 54", "new_squadron": "II./JG 54", "sort_key": "1941-10-05"},
        {"type": "BONUS", "date": "1941-10-05", "sort_key": "1941-10-05"},
        {"type": "RECOVERY", "start_date": "1941-10-09", "end_date": "1941-10-10", "duration_days": 1, "sort_key": "1941-10-09"},
    ]

    lines = _story_other_incidences_for_date(incidences, "1941-10-05")

    assert lines == [
        "Recovery from injury: 1941-10-05 to 1941-10-08 (3 days)",
        "Appointment as squadron commander of I./JG 54",
        "Transfer from I./JG 54 to II./JG 54",
    ]
