from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from career_pdf_report import (
    _group_story_chapters_by_date,
    _normalize_day_contexts_for_pdf,
)


def test_normalize_day_contexts_for_pdf_merges_same_day_missions():
    day_contexts = [
        {
            "date": "1941-09-27",
            "mission_id": "3006",
            "pilot": {"aircraft": "Bf 109 F-4"},
            "mission": {"result": "Landed"},
            "career_progress": {"missions_completed": 1},
            "mission_progression": {"awards": ["Iron Cross 2nd Class"], "promotion": ""},
            "chapter_scope": {
                "scope": "mission",
                "mission_ids": ["3006"],
                "mission_jsons": [{"mission_id": "3006"}],
            },
        },
        {
            "date": "1941-09-27",
            "mission_id": "3007",
            "pilot": {"aircraft": "Bf 109 F-2"},
            "mission": {"result": "Bailout"},
            "career_progress": {"missions_completed": 2},
            "mission_progression": {"awards": ["Pilot's Badge"], "promotion": "Unteroffizier"},
            "chapter_scope": {
                "scope": "mission",
                "mission_ids": ["3007"],
                "mission_jsons": [{"mission_id": "3007"}],
            },
        },
    ]

    normalized = _normalize_day_contexts_for_pdf(day_contexts)

    assert len(normalized) == 1
    merged = normalized[0]
    assert merged["date"] == "1941-09-27"
    assert merged["mission_id"] == "3007"
    assert merged["mission"]["result"] == "Multiple Sorties"
    assert merged["career_progress"]["missions_completed"] == 2
    assert merged["mission_progression"]["awards"] == [
        "Iron Cross 2nd Class",
        "Pilot's Badge",
    ]
    assert merged["mission_progression"]["promotion"] == "Unteroffizier"
    assert merged["chapter_scope"]["scope"] == "day"
    assert merged["chapter_scope"]["mission_ids"] == ["3006", "3007"]
    assert [entry["mission_id"] for entry in merged["chapter_scope"]["mission_jsons"]] == [
        "3006",
        "3007",
    ]


def test_group_story_chapters_by_date_uses_date_for_numeric_mission_ids():
    chapters = [
        {
            "chapter_index": 2,
            "mission_id": "3007",
            "date": "1941-09-27",
            "title": "Second sortie",
            "story_text": "Story 2",
        },
        {
            "chapter_index": 1,
            "mission_id": "3006",
            "date": "1941-09-27",
            "title": "First sortie",
            "story_text": "Story 1",
        },
    ]

    grouped = _group_story_chapters_by_date(chapters)

    assert list(grouped.keys()) == ["1941-09-27"]
    assert [chapter["mission_id"] for chapter in grouped["1941-09-27"]] == ["3006", "3007"]
