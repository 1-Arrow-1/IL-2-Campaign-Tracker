import tempfile
import unittest
from pathlib import Path

from campaign_service_record.core.medal_showcase import resolve_award_asset_path


class TestMedalShowcaseAssetResolution(unittest.TestCase):
    def test_career_context_prefers_big1_then_big_then_base(self):
        with tempfile.TemporaryDirectory() as td:
            assets_root = Path(td)
            germany_dir = assets_root / "Germany"
            germany_dir.mkdir(parents=True, exist_ok=True)

            # Case 1: big1 present -> choose big1.
            (germany_dir / "iron_cross_big1.png").touch()
            (germany_dir / "iron_cross_big.png").touch()
            (germany_dir / "iron_cross.png").touch()
            p = resolve_award_asset_path(
                "iron_cross",
                "germany",
                assets_root,
                context="career_detail_showcase",
            )
            self.assertIsNotNone(p)
            self.assertEqual(p.name, "iron_cross_big1.png")

            # Case 2: big1 removed -> choose big.
            (germany_dir / "iron_cross_big1.png").unlink()
            p = resolve_award_asset_path(
                "iron_cross_big",
                "germany",
                assets_root,
                context="career_detail_showcase",
            )
            self.assertIsNotNone(p)
            self.assertEqual(p.name, "iron_cross_big.png")

            # Case 3: only base remains -> choose base.
            (germany_dir / "iron_cross_big.png").unlink()
            p = resolve_award_asset_path(
                "iron_cross_big1",
                "germany",
                assets_root,
                context="career_detail_showcase",
            )
            self.assertIsNotNone(p)
            self.assertEqual(p.name, "iron_cross.png")

    def test_campaign_context_keeps_incoming_name(self):
        with tempfile.TemporaryDirectory() as td:
            assets_root = Path(td)
            germany_dir = assets_root / "Germany"
            germany_dir.mkdir(parents=True, exist_ok=True)

            (germany_dir / "iron_cross.png").touch()
            (germany_dir / "iron_cross_big1.png").touch()

            p = resolve_award_asset_path(
                "iron_cross",
                "germany",
                assets_root,
                context="campaign_showcase",
            )
            self.assertIsNotNone(p)
            self.assertEqual(p.name, "iron_cross.png")


if __name__ == "__main__":
    unittest.main()
