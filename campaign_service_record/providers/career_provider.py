"""
CareerDataProvider: adapts the career module to the DataProvider interface.

Wraps CareerDatabase, CareerChainResolver, and CareerAggregator.
All career-specific logic lives in campaign_service_record/career/.
This class is a thin dispatcher, consistent with CampaignDataProvider.
"""

import logging
from typing import Dict, List, Optional

from campaign_service_record.providers.base import DataProvider
from campaign_service_record.career.database import CareerDatabase
from campaign_service_record.career.chain_resolver import CareerChainResolver
from campaign_service_record.career.aggregator import CareerAggregator

logger = logging.getLogger(__name__)


class CareerDataProvider(DataProvider):
    """
    DataProvider backed by cp.db via CareerAggregator.
    """

    def __init__(
        self,
        db: CareerDatabase,
        chain_resolver: CareerChainResolver,
        aggregator: CareerAggregator,
    ):
        self._db = db
        self._resolver = chain_resolver
        self._aggregator = aggregator
        logger.info("CareerDataProvider initialized")

    def get_source_type(self) -> str:
        return "career"

    def is_available(self) -> bool:
        """Return True if cp.db is reachable."""
        try:
            self._db.get_all_root_careers()
            return True
        except Exception as exc:
            logger.warning("CareerDataProvider unavailable: %s", exc)
            return False

    def get_entry_list(self) -> List[Dict]:
        return self._aggregator.get_career_list()

    def get_entry_detail(self, entry_id: str) -> Optional[Dict]:
        try:
            root_id = int(entry_id)
        except (TypeError, ValueError):
            logger.warning("Invalid career entry_id (expected int): %r", entry_id)
            return None
        return self._aggregator.get_career_detail(root_id)

    def get_showcase_data(self, entry_id: str) -> Optional[Dict]:
        # Award image mapping requires the translation table (event.tpar2 → image name).
        # Return None until that table is provided and integrated.
        return None
