import json
import unittest
from pathlib import Path
from typing import Optional


ROOT = Path(__file__).resolve().parents[1]
LOCALES_DIR = ROOT / 'campaign_service_record' / 'static' / 'locales'
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

    def test_rank_narrative_falls_back_to_en(self) -> None:
        expected = (
            'Now you carry a commission and the weight that comes with it. '
            'You still fly the same sky, just with more eyes depending on you.'
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


if __name__ == '__main__':
    unittest.main()
