from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from career_pdf_report import (
    _build_story,
    _group_story_chapters_by_date,
    _group_story_chapters_by_mission,
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


def test_group_story_chapters_by_mission_excludes_day_scoped_ids():
    chapters = [
        {"chapter_index": 1, "mission_id": "3006", "date": "1941-09-27", "title": "Mission", "story_text": "A"},
        {"chapter_index": 2, "mission_id": "1941-09-27", "date": "1941-09-27", "title": "Day", "story_text": "B"},
        {"chapter_index": 3, "mission_id": "day:1941-09-27", "date": "1941-09-27", "title": "Day2", "story_text": "C"},
    ]

    grouped = _group_story_chapters_by_mission(chapters)

    assert list(grouped.keys()) == ["3006"]
    assert [chapter["title"] for chapter in grouped["3006"]] == ["Mission"]


def test_build_story_numbers_days_sequentially_and_attaches_stories_per_sortie():
    career_detail = {
        "display_name": "Test Pilot",
        "country": "germany",
        "events": [],
        "other_incidences": [],
        "summary": {
            "timeline": {"first_mission_date": "1941-09-27", "last_mission_date": "1941-09-27", "duration_days": 1},
            "career_progression": {"final_rank": "Unteroffizier"},
            "combat_results": {},
        },
    }
    day_contexts = [
        {
            "date": "1941-09-27",
            "mission_id": "3006",
            "pilot": {"aircraft": "Bf 109 F-4"},
            "mission": {"result": "Landed"},
            "career_progress": {"missions_completed": 1},
            "mission_progression": {"awards": [], "promotion": ""},
            "chapter_scope": {
                "scope": "mission",
                "mission_ids": ["3006"],
                "mission_jsons": [
                    {
                        "mission_id": "3006",
                        "aircraft": "Bf 109 F-4",
                        "json": {"summary": {"final_state": "Landed"}, "events": []},
                        "sortie_stats": {},
                    }
                ],
            },
        },
        {
            "date": "1941-09-27",
            "mission_id": "3007",
            "pilot": {"aircraft": "Bf 109 F-2"},
            "mission": {"result": "Landed"},
            "career_progress": {"missions_completed": 2},
            "mission_progression": {"awards": [], "promotion": ""},
            "chapter_scope": {
                "scope": "mission",
                "mission_ids": ["3007"],
                "mission_jsons": [
                    {
                        "mission_id": "3007",
                        "aircraft": "Bf 109 F-2",
                        "json": {"summary": {"final_state": "Landed"}, "events": []},
                        "sortie_stats": {},
                    }
                ],
            },
        },
    ]
    story_chapters = [
        {"chapter_index": 1, "mission_id": "3006", "date": "1941-09-27", "title": "Story One", "story_text": "Alpha"},
        {"chapter_index": 2, "mission_id": "3007", "date": "1941-09-27", "title": "Story Two", "story_text": "Bravo"},
    ]

    flowables = _build_story(career_detail, day_contexts, story_chapters, None, None)

    texts = []

    def _walk(items):
        for item in items:
            if hasattr(item, "getPlainText"):
                texts.append(item.getPlainText())
            content = getattr(item, "_content", None)
            if content:
                _walk(content)

    _walk(flowables)

    chapter_idx = next(i for i, text in enumerate(texts) if text.startswith("Chapter 1 | 1941-09-27"))
    sortie1_idx = next(i for i, text in enumerate(texts) if text.startswith("Sortie 1"))
    story1_idx = texts.index("Story One")
    sortie2_idx = next(i for i, text in enumerate(texts) if text.startswith("Sortie 2"))
    story2_idx = texts.index("Story Two")

    assert chapter_idx < sortie1_idx < story1_idx < sortie2_idx < story2_idx
