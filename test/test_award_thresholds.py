"""Tests for random_threshold / random_threshold_min award evaluation semantics.

These tests verify the three properties of the threshold gate used in
step3_generate_events.py at the point where `award_earned` / `award_granted`
is gated by a random roll:

  random.seed(f"{campaign_name}_{mission_num}_{award_name}")
  random_roll = random.randint(0, 999)          # 0 … 999 inclusive (1 000 values)

  random_threshold     N  →  award granted when roll < N  (fails when roll >= N)
  random_threshold_min N  →  award granted when roll >= N (fails when roll < N)

The tests also verify that the Britain AFM/AFC entries in
campaign_progress_config.yaml carry the expected threshold values
(50/50/25 for each series, giving ~5 % / ~5 % / ~2.5 % grant chances).
"""

import random
import unittest
import yaml
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROGRESS_CONFIG = ROOT / 'campaign_progress_config.yaml'


# ---------------------------------------------------------------------------
# Helper – mirrors the exact logic in step3_generate_events.py
# ---------------------------------------------------------------------------

def apply_threshold(award: dict, campaign_name: str, mission_num: int, award_name: str) -> bool:
    """Return True if the random threshold gate passes (award should be granted)."""
    if 'random_threshold' not in award and 'random_threshold_min' not in award:
        return True

    random.seed(f"{campaign_name}_{mission_num}_{award_name}")
    roll = random.randint(0, 999)

    if 'random_threshold' in award:
        if roll >= award['random_threshold']:
            return False

    if 'random_threshold_min' in award:
        if roll < award['random_threshold_min']:
            return False

    return True


# ---------------------------------------------------------------------------
# Helper – force a specific roll to exercise boundary conditions
# ---------------------------------------------------------------------------

def _forced_result(threshold_type: str, threshold_val: int, roll: int) -> bool:
    """Evaluate a threshold directly against a known roll value."""
    if threshold_type == 'random_threshold':
        return roll < threshold_val
    if threshold_type == 'random_threshold_min':
        return roll >= threshold_val
    raise ValueError(f'Unknown threshold type: {threshold_type}')


class TestRandomThresholdSemantics(unittest.TestCase):
    """Verify roll < threshold semantics (standard threshold)."""

    # ---- boundary: roll strictly below threshold ----

    def test_roll_zero_passes(self) -> None:
        self.assertTrue(_forced_result('random_threshold', 50, 0))

    def test_roll_one_below_threshold_passes(self) -> None:
        self.assertTrue(_forced_result('random_threshold', 50, 49))

    # ---- boundary: roll at and above threshold ----

    def test_roll_equal_threshold_fails(self) -> None:
        self.assertFalse(_forced_result('random_threshold', 50, 50))

    def test_roll_above_threshold_fails(self) -> None:
        self.assertFalse(_forced_result('random_threshold', 50, 999))

    # ---- effective probabilities ----

    def test_threshold_50_approx_5pct(self) -> None:
        # 50 out of 1000 possible rolls (0-49) pass → exactly 5.0 %
        passing = sum(1 for r in range(1000) if _forced_result('random_threshold', 50, r))
        self.assertEqual(passing, 50)

    def test_threshold_25_approx_2pt5pct(self) -> None:
        # 25 out of 1000 possible rolls (0-24) pass → exactly 2.5 %
        passing = sum(1 for r in range(1000) if _forced_result('random_threshold', 25, r))
        self.assertEqual(passing, 25)

    def test_threshold_800_approx_80pct(self) -> None:
        # 800 out of 1000 possible rolls (0-799) pass → exactly 80.0 %
        passing = sum(1 for r in range(1000) if _forced_result('random_threshold', 800, r))
        self.assertEqual(passing, 800)


class TestRandomThresholdMinSemantics(unittest.TestCase):
    """Verify roll >= threshold_min semantics (minimum threshold)."""

    def test_roll_equal_threshold_min_passes(self) -> None:
        self.assertTrue(_forced_result('random_threshold_min', 800, 800))

    def test_roll_above_threshold_min_passes(self) -> None:
        self.assertTrue(_forced_result('random_threshold_min', 800, 999))

    def test_roll_below_threshold_min_fails(self) -> None:
        self.assertFalse(_forced_result('random_threshold_min', 800, 799))

    def test_roll_zero_fails_when_min_is_800(self) -> None:
        self.assertFalse(_forced_result('random_threshold_min', 800, 0))

    def test_threshold_min_800_approx_20pct(self) -> None:
        # 200 out of 1000 possible rolls (800-999) pass → exactly 20.0 %
        passing = sum(1 for r in range(1000) if _forced_result('random_threshold_min', 800, r))
        self.assertEqual(passing, 200)


class TestDeterministicSeeding(unittest.TestCase):
    """Verify that identical seed inputs always produce the same roll."""

    def _roll(self, campaign: str, mission: int, award: str) -> int:
        random.seed(f"{campaign}_{mission}_{award}")
        return random.randint(0, 999)

    def test_same_inputs_same_roll(self) -> None:
        r1 = self._roll('CampaignA', 5, 'Air Force Medal')
        r2 = self._roll('CampaignA', 5, 'Air Force Medal')
        self.assertEqual(r1, r2)

    def test_different_campaign_different_roll(self) -> None:
        r1 = self._roll('CampaignA', 5, 'Air Force Medal')
        r2 = self._roll('CampaignB', 5, 'Air Force Medal')
        self.assertNotEqual(r1, r2)

    def test_different_mission_different_roll(self) -> None:
        r1 = self._roll('CampaignA', 5, 'Air Force Medal')
        r2 = self._roll('CampaignA', 6, 'Air Force Medal')
        self.assertNotEqual(r1, r2)

    def test_different_award_name_different_roll(self) -> None:
        r1 = self._roll('CampaignA', 5, 'Air Force Medal')
        r2 = self._roll('CampaignA', 5, 'Air Force Cross')
        self.assertNotEqual(r1, r2)


class TestAFMAFCYAMLConfig(unittest.TestCase):
    """Verify Britain AFM/AFC entries in campaign_progress_config.yaml carry
    the expected random_threshold values.

    AFM series  (max_rank_index: 2, NCO awards): base=50, bar=50, second-bar=25
    AFC series  (min_rank_index: 3, officer awards): base=50, bar=50, second-bar=25
    """

    @classmethod
    def setUpClass(cls) -> None:
        with open(PROGRESS_CONFIG, encoding='utf-8') as fh:
            config = yaml.safe_load(fh)

        # Build a flat lookup: award name → award dict.
        # config['awards'] is a dict keyed by nation name; each value is a list
        # of award dicts (e.g. config['awards']['Britain']).
        cls.awards: dict[str, dict] = {}
        for nation_name, award_list in config.get('awards', {}).items():
            if isinstance(award_list, list):
                for award in award_list:
                    if isinstance(award, dict) and 'name' in award:
                        cls.awards[award['name']] = award

    def _threshold(self, name: str) -> int:
        award = self.awards.get(name)
        self.assertIsNotNone(award, f'Award not found in config: {name!r}')
        self.assertIn('random_threshold', award,
                      f'random_threshold missing for {name!r}')
        return award['random_threshold']

    # AFM series
    def test_afm_base_threshold_50(self) -> None:
        self.assertEqual(self._threshold('Air Force Medal'), 50)

    def test_afm_bar_threshold_50(self) -> None:
        self.assertEqual(self._threshold('Bar to the Air Force Medal'), 50)

    def test_afm_second_bar_threshold_25(self) -> None:
        self.assertEqual(self._threshold('Second Bar to the Air Force Medal'), 25)

    # AFC series
    def test_afc_base_threshold_50(self) -> None:
        self.assertEqual(self._threshold('Air Force Cross'), 50)

    def test_afc_bar_threshold_50(self) -> None:
        self.assertEqual(self._threshold('Bar to the Air Force Cross'), 50)

    def test_afc_second_bar_threshold_25(self) -> None:
        self.assertEqual(self._threshold('Second Bar to the Air Force Cross'), 25)


if __name__ == '__main__':
    unittest.main()
