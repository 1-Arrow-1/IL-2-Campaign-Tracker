import tempfile
import unittest
from pathlib import Path

from settings_manager.stock_campaign_import import (
    copy_campaign_subfolders,
    snapshot_directory_state,
    summarize_direct_import,
)


class TestStockCampaignImport(unittest.TestCase):
    def test_copy_campaign_subfolders_skips_existing_subfolders_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source" / "Campaigns"
            dest = root / "dest" / "Campaigns"
            (source / "Alpha").mkdir(parents=True)
            (source / "Bravo").mkdir(parents=True)
            dest.mkdir(parents=True)
            (dest / "Bravo").mkdir()

            imported, skipped = copy_campaign_subfolders(source, dest)

            self.assertEqual(["Alpha"], imported)
            self.assertEqual(["Bravo"], skipped)
            self.assertTrue((dest / "Alpha").is_dir())
            self.assertTrue((dest / "Bravo").is_dir())

    def test_summarize_direct_import_reports_new_and_existing_campaigns(self):
        imported, skipped = summarize_direct_import(
            existing_campaigns=["Bravo", "Charlie"],
            resulting_campaigns=["Alpha", "Bravo", "Charlie"],
        )

        self.assertEqual(["Alpha"], imported)
        self.assertEqual(["Bravo", "Charlie"], skipped)

    def test_snapshot_directory_state_changes_when_files_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            campaigns = root / "Campaigns"
            campaigns.mkdir()

            initial = snapshot_directory_state(campaigns)
            self.assertEqual((0, 0, 0), initial)

            mission_file = campaigns / "mission.txt"
            mission_file.write_text("alpha", encoding="utf-8")
            after_write = snapshot_directory_state(campaigns)

            self.assertIsNotNone(after_write)
            self.assertNotEqual(initial, after_write)


if __name__ == "__main__":
    unittest.main()
