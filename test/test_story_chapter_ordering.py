from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import llm_story_generator as story


def test_save_story_chapter_for_career_uses_mission_order_over_date(tmp_path, monkeypatch):
    monkeypatch.setattr(story, "STORY_DATA_DIR", tmp_path / "story_data" / "careers")

    story.save_story_chapter_for(
        "career",
        74,
        {
            "mission_id": "3135",
            "date": "1941-11-05",
            "pilot": {"aircraft": "Bf 109 F-4"},
            "mission": {"result": "Landed"},
            "career_mission_order": 4,
            "career_segment_index": 1,
        },
        "Story B",
        title="B",
        language_code="en",
    )
    story.save_story_chapter_for(
        "career",
        74,
        {
            "mission_id": "3085",
            "date": "1941-11-06",
            "pilot": {"aircraft": "Bf 109 F-2"},
            "mission": {"result": "Landed"},
            "career_mission_order": 3,
            "career_segment_index": 0,
        },
        "Story A",
        title="A",
        language_code="en",
    )

    chapters = story.load_story_chapters_for("career", 74)
    assert [ch.get("mission_id") for ch in chapters] == ["3085", "3135"]
    assert [ch.get("chapter_index") for ch in chapters] == [1, 2]
    assert [ch.get("career_mission_order") for ch in chapters] == [3, 4]
    assert [ch.get("career_segment_index") for ch in chapters] == [0, 1]


def test_save_story_chapter_for_campaign_keeps_date_order(tmp_path, monkeypatch):
    monkeypatch.setattr(story, "STORY_DATA_DIR", tmp_path / "story_data" / "careers")

    story.save_story_chapter_for(
        "campaign",
        "my_campaign",
        {
            "mission_id": "2",
            "date": "1941-11-06",
            "pilot": {"aircraft": "Bf 109 F-4"},
            "mission": {"result": "Landed"},
        },
        "Campaign Story B",
        title="B",
        language_code="en",
    )
    story.save_story_chapter_for(
        "campaign",
        "my_campaign",
        {
            "mission_id": "1",
            "date": "1941-11-05",
            "pilot": {"aircraft": "Bf 109 F-2"},
            "mission": {"result": "Landed"},
        },
        "Campaign Story A",
        title="A",
        language_code="en",
    )

    chapters = story.load_story_chapters_for("campaign", "my_campaign")
    assert [ch.get("mission_id") for ch in chapters] == ["1", "2"]
    assert [ch.get("chapter_index") for ch in chapters] == [1, 2]


def test_reindex_career_story_chapters_for_repairs_legacy_order(tmp_path, monkeypatch):
    monkeypatch.setattr(story, "STORY_DATA_DIR", tmp_path / "story_data" / "careers")
    chapters_dir = story._story_entry_dir("career", 74) / "chapters"
    chapters_dir.mkdir(parents=True, exist_ok=True)

    legacy_rows = [
        {
            "chapter_index": 1,
            "mission_id": "3135",
            "date": "1941-11-05",
            "title": "B",
            "language": "en",
            "story_text": "Story B",
            "aircraft": "Bf 109 F-4",
            "result": "Landed",
        },
        {
            "chapter_index": 2,
            "mission_id": "3085",
            "date": "1941-11-06",
            "title": "A",
            "language": "en",
            "story_text": "Story A",
            "aircraft": "Bf 109 F-2",
            "result": "Landed",
        },
    ]
    for idx, payload in enumerate(legacy_rows, start=1):
        path = chapters_dir / f"{idx:04d}_{payload['date']}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    changed = story.reindex_career_story_chapters_for(
        74,
        {"3085": 3, "3135": 4},
        {"3085": 0, "3135": 1},
    )

    assert changed == 2
    chapters = story.load_story_chapters_for("career", 74)
    assert [ch.get("mission_id") for ch in chapters] == ["3085", "3135"]
    assert [ch.get("chapter_index") for ch in chapters] == [1, 2]
    assert [ch.get("career_mission_order") for ch in chapters] == [3, 4]
    assert [ch.get("career_segment_index") for ch in chapters] == [0, 1]
