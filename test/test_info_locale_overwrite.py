import re
import unittest

from utils.info_locale import apply_tracker_content, TRACKER_SECTION_HEADER_PATTERN


class TestInfoLocaleOverwrite(unittest.TestCase):
    def test_tracker_content_overwrite_is_idempotent(self) -> None:
        base_content = (
            "Campaign intro text<br><br>"
            "<b>Mission Debriefings</b><br>OLD DEBRIEFINGS<br>"
            "<b>Events</b><br>OLD EVENTS"
        )
        new_block = (
            "<b>Mission Debriefings</b><br>NEW DEBRIEFINGS<br>"
            "<b>Events</b><br>NEW EVENTS"
        )

        updated_once, _, _, _ = apply_tracker_content(base_content.encode("utf-8"), new_block)
        updated_twice, _, _, _ = apply_tracker_content(updated_once.encode("utf-8"), new_block)

        self.assertEqual(updated_twice.count("<b>Mission Debriefings</b>"), 1)
        self.assertEqual(updated_twice.count("<b>Events</b>"), 1)

        matches = re.findall(TRACKER_SECTION_HEADER_PATTERN, updated_twice, flags=re.IGNORECASE)
        self.assertEqual(len(matches), 2)


if __name__ == "__main__":
    unittest.main()
