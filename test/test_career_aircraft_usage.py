import unittest
from types import SimpleNamespace

from campaign_service_record.career.aggregator import CareerAggregator


class _FakeDb:
    def __init__(self):
        self._missions = {
            10: [
                {"id": 100, "plane0": "graphics/planes/bf109f2.txt"},
                {"id": 101, "plane0": "graphics/planes/bf109f4.txt"},
            ]
        }
        self._sorties = {
            100: {
                "killLightPlane": 0,
                "killMediumPlane": 0,
                "killHeavyPlane": 0,
                "killStaticPlane": 0,
            },
            101: {
                "killLightPlane": 0,
                "killMediumPlane": 0,
                "killHeavyPlane": 0,
                "killStaticPlane": 0,
            },
        }

    def get_missions_for_career(self, career_id, player_id):
        return self._missions.get(career_id, [])

    def get_sortie_for_mission(self, mission_id, player_id):
        return self._sorties.get(mission_id)


class TestCareerAircraftUsage(unittest.TestCase):
    def test_duplicate_debrief_labels_do_not_overwrite_distinct_planes(self):
        aggregator = CareerAggregator.__new__(CareerAggregator)
        aggregator._db = _FakeDb()
        career = SimpleNamespace(chain=[{"id": 10, "playerId": 20}])
        debrief_results = [
            SimpleNamespace(mission_id=100, aircraft="Bf 109 F"),
            SimpleNamespace(mission_id=101, aircraft="Bf 109 F"),
        ]

        usage = aggregator._calculate_aircraft_usage_from_db(career, debrief_results)

        self.assertEqual(2, len(usage))
        self.assertIn("Bf 109 F-2", usage)
        self.assertIn("Bf 109 F-4", usage)
        self.assertEqual(1, usage["Bf 109 F-2"]["missions"])
        self.assertEqual(1, usage["Bf 109 F-4"]["missions"])


if __name__ == "__main__":
    unittest.main()
