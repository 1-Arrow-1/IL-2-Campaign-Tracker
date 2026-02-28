"""
CampaignDataProvider: adapts the existing DataLoader + CampaignAggregator
to the DataProvider interface.

This is a thin, zero-logic wrapper. All data loading and transformation
remains in the existing DataLoader and CampaignAggregator classes unchanged.

The showcase endpoint retains its direct implementation in routes.py because
it has HTTP-layer concerns (game directory resolution, asset URL building).
get_showcase_data() returns a sentinel value that routes.py detects and
handles via its existing code path.
"""

import logging
from typing import Dict, List, Optional

from campaign_service_record.providers.base import DataProvider
from campaign_service_record.core.data_loader import DataLoader
from campaign_service_record.core.campaign_aggregator import CampaignAggregator

logger = logging.getLogger(__name__)


class CampaignDataProvider(DataProvider):
    """
    DataProvider backed by Campaign Tracker JSON files.

    Delegates all calls to the injected DataLoader and CampaignAggregator
    instances — the same instances already used by routes.py before this
    abstraction layer was introduced.
    """

    def __init__(self, data_loader: DataLoader, aggregator: CampaignAggregator):
        self._loader = data_loader
        self._aggregator = aggregator
        logger.info("CampaignDataProvider initialized")

    def get_source_type(self) -> str:
        return "campaign"

    def is_available(self) -> bool:
        try:
            self._loader.get_campaigns_with_progress()
            return True
        except Exception as exc:
            logger.warning("CampaignDataProvider unavailable: %s", exc)
            return False

    def get_entry_list(self) -> List[Dict]:
        entries = self._aggregator.get_campaign_list()
        for entry in entries:
            entry['source'] = 'campaign'
        return entries

    def get_entry_detail(self, entry_id: str) -> Optional[Dict]:
        return self._aggregator.get_campaign_detail(entry_id.lower())

    def get_showcase_data(self, entry_id: str) -> Optional[Dict]:
        # The campaign showcase endpoint builds its payload directly in routes.py
        # using HTTP-layer context (game directory, asset URL prefix).
        # Return None here — routes.py calls its own showcase builder for campaigns.
        return None
