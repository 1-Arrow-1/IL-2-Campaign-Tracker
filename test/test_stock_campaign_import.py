import tempfile
import unittest
from pathlib import Path

from settings_manager.stock_campaign_import import copy_campaign_subfolders


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


if __name__ == "__main__":
    unittest.main()
