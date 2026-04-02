import tempfile
import unittest
from pathlib import Path

from settings_manager.stock_campaign_import import (
    copy_campaign_subfolders,
    snapshot_directory_state,
    summarize_direct_import,
)


class TestStockCampaignImport(unittest.TestCase):
    def test_copy_campaign_subfolders_new_folder_imported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source" / "Campaigns"
            dest = root / "dest" / "Campaigns"
            (source / "Alpha").mkdir(parents=True)
            (source / "Bravo").mkdir(parents=True)
            dest.mkdir(parents=True)
            (dest / "Bravo").mkdir()

            imported, updated, skipped = copy_campaign_subfolders(source, dest)

            self.assertEqual(["Alpha"], imported)
            self.assertEqual([], updated)
            self.assertEqual(["Bravo"], skipped)
            self.assertTrue((dest / "Alpha").is_dir())
            self.assertTrue((dest / "Bravo").is_dir())

    def test_copy_campaign_subfolders_adds_new_mission_files_to_existing_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source" / "Campaigns"
            dest = root / "dest" / "Campaigns"
            (source / "Alpha").mkdir(parents=True)
            (source / "Alpha" / "01.msnbin").write_bytes(b"mission1")
            (source / "Alpha" / "02.msnbin").write_bytes(b"mission2")
            (dest / "Alpha").mkdir(parents=True)
            # 01.msnbin already exists in destination
            (dest / "Alpha" / "01.msnbin").write_bytes(b"existing")

            imported, updated, skipped = copy_campaign_subfolders(source, dest)

            self.assertEqual([], imported)
            self.assertEqual(["Alpha"], updated)
            self.assertEqual([], skipped)
            # Existing file must not be overwritten
            self.assertEqual(b"existing", (dest / "Alpha" / "01.msnbin").read_bytes())
            # New file must be copied
            self.assertEqual(b"mission2", (dest / "Alpha" / "02.msnbin").read_bytes())

    def test_copy_campaign_subfolders_skips_when_no_new_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source" / "Campaigns"
            dest = root / "dest" / "Campaigns"
            (source / "Alpha").mkdir(parents=True)
            (source / "Alpha" / "01.msnbin").write_bytes(b"mission1")
            (dest / "Alpha").mkdir(parents=True)
            (dest / "Alpha" / "01.msnbin").write_bytes(b"existing")

            imported, updated, skipped = copy_campaign_subfolders(source, dest)

            self.assertEqual([], imported)
            self.assertEqual([], updated)
            self.assertEqual(["Alpha"], skipped)

    def test_summarize_direct_import_reports_new_and_existing_campaigns(self):
        imported, updated, skipped = summarize_direct_import(
            existing_campaigns=["Bravo", "Charlie"],
            resulting_campaigns=["Alpha", "Bravo", "Charlie"],
        )

        self.assertEqual(["Alpha"], imported)
        self.assertEqual([], updated)
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
