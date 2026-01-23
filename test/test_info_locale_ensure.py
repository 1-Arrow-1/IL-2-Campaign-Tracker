import tempfile
import unittest
from pathlib import Path

from utils.info_locale import apply_tracker_content, ensure_info_locale_files
from utils.supported_locales import APP_TO_IL2_LOCALE, get_supported_locales


class TestEnsureInfoLocaleFiles(unittest.TestCase):
    def test_ensure_info_locale_files_creates_missing_locales_and_updates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            campaign_path = Path(temp_dir)
            base_content = 'Campaign intro text<br>&name="Test Campaign"<br>'
            source_file = campaign_path / "info.locale=eng.txt"
            source_file.write_text(base_content, encoding="utf-8")

            supported_locales = get_supported_locales()
            all_files, created_files, source_file_used = ensure_info_locale_files(
                campaign_path,
                supported_locales,
            )

            self.assertTrue(all_files)
            self.assertIsNotNone(source_file_used)
            self.assertGreaterEqual(len(all_files), len(created_files))

            for locale in supported_locales:
                il2_locale = APP_TO_IL2_LOCALE.get(locale)
                if not il2_locale:
                    continue
                target_file = campaign_path / f"info.locale={il2_locale}.txt"
                self.assertTrue(target_file.exists())

                updated, _, _, _ = apply_tracker_content(
                    target_file.read_bytes(),
                    f"<b>Events</b><br>{locale}",
                )
                target_file.write_text(updated, encoding="utf-8")

                updated_content = target_file.read_text(encoding="utf-8")
                self.assertIn("Campaign intro text", updated_content)
                self.assertIn("<b>Events</b>", updated_content)
                self.assertIn(locale, updated_content)


if __name__ == "__main__":
    unittest.main()
