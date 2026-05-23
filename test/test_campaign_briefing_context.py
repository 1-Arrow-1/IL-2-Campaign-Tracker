import tempfile
import unittest
from pathlib import Path

from campaign_service_record.weather_lookup import read_eng_story_context, read_eng_weather


class TestCampaignBriefingContext(unittest.TestCase):
    def test_extracts_mission_type_orders_and_weather(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            base = Path(tmp_dir) / "data" / "Campaigns" / "demo_campaign"
            base.mkdir(parents=True, exist_ok=True)

            briefing = (
                "0:demo\n"
                "1:<b>Date: </b>3.7.1941<br>"
                "<b>Time: </b>15:34:46<br>"
                "<b>Weather: </b>25 C, clear skies.<br><br>"
                "<b>Mission type: </b> Intercept <br><br>"
                "<b>Orders: </b>Patrol the area marked on the map and intercept the enemy aircraft.<br><br>"
            )
            (base / "01.eng").write_text(briefing, encoding="utf-16")

            context = read_eng_story_context(tmp_dir, "demo_campaign", "01")
            self.assertEqual(context.get("mission_type"), "Intercept")
            self.assertEqual(
                context.get("mission_objective"),
                "Patrol the area marked on the map and intercept the enemy aircraft.",
            )
            self.assertEqual(context.get("mission_start_time"), "15:34:46")

            weather = read_eng_weather(tmp_dir, "demo_campaign", "01")
            self.assertIsNotNone(weather)
            self.assertEqual(weather.get("conditions"), "25 C, clear skies.")

    def test_briefing_free_text_extracted(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            base = Path(tmp_dir) / "data" / "Campaigns" / "demo_campaign"
            base.mkdir(parents=True, exist_ok=True)

            briefing = (
                "0:title\n"
                "1:In the spring of 1945 the Allied air forces controlled the skies over Germany. "
                "A handful of veteran pilots remained to defend what was left. Their task: intercept bombers at Rheine.<br><br>"
                "2:some other key\n"
            )
            (base / "01.eng").write_text(briefing, encoding="utf-16")

            context = read_eng_story_context(tmp_dir, "demo_campaign", "01")
            free_text = context.get("briefing_free_text", "")
            self.assertTrue(len(free_text) > 0, "briefing_free_text should be non-empty")
            self.assertIn("veteran pilots", free_text)
            self.assertNotIn("<br>", free_text)
            self.assertNotIn("<b>", free_text)

    def test_briefing_free_text_truncated(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            base = Path(tmp_dir) / "data" / "Campaigns" / "demo_campaign"
            base.mkdir(parents=True, exist_ok=True)

            long_sentence = "The enemy was advancing rapidly. " * 40
            briefing = f"0:title\n1:{long_sentence}\n2:end\n"
            (base / "01.eng").write_text(briefing, encoding="utf-16")

            context = read_eng_story_context(tmp_dir, "demo_campaign", "01")
            free_text = context.get("briefing_free_text", "")
            self.assertLessEqual(len(free_text), 700, "briefing_free_text must be at most 700 chars")

    def test_flight_mission_fallback_uses_mission_file_hint(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            base = Path(tmp_dir) / "data" / "Campaigns" / "demo_campaign"
            base.mkdir(parents=True, exist_ok=True)

            briefing = (
                "0:story mission\n"
                "1:Date: October 21, 1941<br>"
                "Time: 07:35<br><br>"
                "Flight Mission: make a sortie in a pair to cover a transport plane.<br><br>"
            )
            (base / "special_name.eng").write_text(briefing, encoding="utf-16")

            context = read_eng_story_context(
                tmp_dir,
                "demo_campaign",
                "01",
                mission_file="special_name.chs",
            )
            self.assertIsNone(context.get("mission_type"))
            self.assertEqual(
                context.get("mission_objective"),
                "make a sortie in a pair to cover a transport plane.",
            )
            self.assertEqual(context.get("mission_start_time"), "07:35")


if __name__ == "__main__":
    unittest.main()

