import json
import unittest
from pathlib import Path
from typing import Optional


ROOT = Path(__file__).resolve().parents[1]
LOCALES_DIR = ROOT / 'locales'
MISSING_PLACEHOLDER = '[missing narrative]'


def load_locale(locale: str) -> dict:
    path = LOCALES_DIR / f'{locale}.json'
    return json.loads(path.read_text(encoding='utf-8'))


def get_narrative(data: dict, nation: str, category: str, code: str) -> Optional[str]:
    return (
        data
        .get('narratives', {})
        .get(nation, {})
        .get(category, {})
        .get(code)
    )


def resolve_popup_narrative(locale_data: dict, en_data: dict, nation: str, category: str, code: str) -> str:
    value = get_narrative(locale_data, nation, category, code)
    if not value:
        value = get_narrative(en_data, nation, category, code)
    return value or MISSING_PLACEHOLDER


class TestPopupNarratives(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.en = load_locale('en')
        cls.de = load_locale('de')

    def test_award_narrative_matches_en_catalog(self) -> None:
        expected = (
            'A first hard mark of combat service. Not glory—just proof you were there when it counted.'
        )
        narrative = resolve_popup_narrative(
            self.en,
            self.en,
            nation='germany',
            category='awards',
            code='iron_cross_2nd_class'
        )
        self.assertEqual(narrative, expected)

    def test_rank_narrative_returns_locale_text_when_available(self) -> None:
        # de.json has a German translation for 'leutnant' (added in locale-additions sprint).
        # The resolver should return the German text rather than the English fallback.
        expected = (
            'Mit dem Offizierspatent kommt Verantwortung. '
            'Der Himmel ist derselbe geblieben, doch jetzt hängen mehr Leben von dir ab.'
        )
        narrative = resolve_popup_narrative(
            self.de,
            self.en,
            nation='germany',
            category='ranks',
            code='leutnant'
        )
        self.assertEqual(narrative, expected)

    def test_missing_narrative_returns_placeholder(self) -> None:
        narrative = resolve_popup_narrative(
            self.de,
            self.en,
            nation='germany',
            category='ranks',
            code='does_not_exist'
        )
        self.assertEqual(narrative, MISSING_PLACEHOLDER)


class TestGermanyFrontFlyingClaspNarratives(unittest.TestCase):
    """Verify that the short-form narrative keys used after JS key normalisation exist.

    The YAML names are e.g. "Front Flying Clasp for Fighters in Bronze".
    nameToI18nKey() converts that to 'front_flying_clasp_for_fighters_in_bronze'.
    normalizeGermanyAwardNarrativeKey() in detail.js then maps it to the
    short-form key 'front_flying_clasp_fighters_bronze' that has an actual
    narrative in en.json.  These tests confirm the short-form keys are present
    and the long-form keys have no narrative (so the normaliser is necessary).
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.en = load_locale('en')

    # ---- Short-form keys (post-normalisation) must resolve ----

    def test_fighters_bronze_normalised_key_resolves(self) -> None:
        narrative = get_narrative(self.en, 'germany', 'awards', 'front_flying_clasp_fighters_bronze')
        self.assertIsNotNone(narrative, 'Missing narrative: front_flying_clasp_fighters_bronze')
        self.assertIn('sorties', narrative)

    def test_fighters_silver_normalised_key_resolves(self) -> None:
        narrative = get_narrative(self.en, 'germany', 'awards', 'front_flying_clasp_fighters_silver')
        self.assertIsNotNone(narrative, 'Missing narrative: front_flying_clasp_fighters_silver')

    def test_fighters_gold_normalised_key_resolves(self) -> None:
        narrative = get_narrative(self.en, 'germany', 'awards', 'front_flying_clasp_fighters_gold')
        self.assertIsNotNone(narrative, 'Missing narrative: front_flying_clasp_fighters_gold')

    # ---- Long-form keys (pre-normalisation) must NOT exist in narratives ----
    # This confirms that without normalizeGermanyAwardNarrativeKey the popup
    # would fall through to [missing narrative].

    def test_fighters_bronze_raw_key_has_no_narrative(self) -> None:
        narrative = get_narrative(self.en, 'germany', 'awards',
                                  'front_flying_clasp_for_fighters_in_bronze')
        self.assertIsNone(narrative,
                          'Raw key should have no narrative entry — normalisation required')

    def test_fighters_gold_with_pendant_raw_key_has_no_narrative(self) -> None:
        narrative = get_narrative(self.en, 'germany', 'awards',
                                  'front_flying_clasp_for_fighters_in_gold_with_pendant')
        self.assertIsNone(narrative,
                          'Raw key should have no narrative entry — normalisation required')


class TestBritainAFMAFCNarratives(unittest.TestCase):
    """Verify that Britain AFM/AFC narrative keys exist in en.json."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.en = load_locale('en')

    _EXPECTED_KEYS = [
        'air_force_medal',
        'bar_to_the_air_force_medal',
        'second_bar_to_the_air_force_medal',
        'air_force_cross',
        'bar_to_the_air_force_cross',
        'second_bar_to_the_air_force_cross',
    ]

    def _check(self, code: str) -> None:
        narrative = get_narrative(self.en, 'britain', 'awards', code)
        self.assertIsNotNone(narrative, f'Missing Britain narrative key: {code}')
        self.assertTrue(narrative.strip(), f'Empty Britain narrative for key: {code}')

    def test_air_force_medal(self) -> None:
        self._check('air_force_medal')

    def test_bar_to_the_air_force_medal(self) -> None:
        self._check('bar_to_the_air_force_medal')

    def test_second_bar_to_the_air_force_medal(self) -> None:
        self._check('second_bar_to_the_air_force_medal')

    def test_air_force_cross(self) -> None:
        self._check('air_force_cross')

    def test_bar_to_the_air_force_cross(self) -> None:
        self._check('bar_to_the_air_force_cross')

    def test_second_bar_to_the_air_force_cross(self) -> None:
        self._check('second_bar_to_the_air_force_cross')


if __name__ == '__main__':
    unittest.main()
