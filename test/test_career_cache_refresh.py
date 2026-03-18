import unittest
from pathlib import Path
from unittest.mock import patch

from campaign_service_record.career.mission_linker import MissionReportLinker


class _FakeMlgPath:
    def __init__(self, name: str, mtime: float):
        self.name = name
        self.stem = Path(name).stem
        self.parent = Path(".")
        self._mtime = mtime

    def stat(self):
        return type("Stat", (), {"st_mtime": self._mtime})()


class TestCareerCacheRefresh(unittest.TestCase):
    def test_find_newer_career_report_outside_insdate_window(self):
        fixtures = Path(__file__).parent / "fixtures" / "career_cache_refresh"
        older_mlg = _FakeMlgPath("missionReport(2026-03-17_23-25-53).mlg", 100.0)
        newer_mlg = _FakeMlgPath("missionReport(2026-03-18_10-33-54).mlg", 200.0)
        older_txt = fixtures / "missionReport(2026-03-17_23-25-53)[0].txt"
        newer_txt = fixtures / "missionReport(2026-03-18_10-33-54)[0].txt"

        linker = MissionReportLinker(fixtures)
        mission_row = {
            "startTime": "1944.06.13 16:37:52",
            "endTime": "1944.06.13 17:15:22",
        }

        with patch.object(Path, "rglob", return_value=[older_mlg, newer_mlg]):
            with patch.object(
                linker,
                "_ensure_txt",
                side_effect=lambda path, _: newer_txt if "2026-03-18" in path.name else older_txt,
            ):
                result = linker.find_newer_career_report(
                    mission_row,
                    cached_mlg_timestamp="2026-03-17_23-25-53",
                    mlg2txt_path=None,
                )

        self.assertEqual(newer_txt, result)


if __name__ == "__main__":
    unittest.main()
