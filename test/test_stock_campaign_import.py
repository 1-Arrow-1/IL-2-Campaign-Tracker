import tempfile
import unittest
from pathlib import Path

from settings_manager.stock_campaign_import import (
    copy_campaign_subfolders,
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


if __name__ == "__main__":
    unittest.main()
