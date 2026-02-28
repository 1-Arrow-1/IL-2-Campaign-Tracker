"""
Abstract base class for all data providers.

Defines the interface that both CampaignDataProvider and CareerDataProvider
must implement, ensuring the API route layer and frontend remain source-agnostic.

Both providers must return response shapes identical to the existing
/api/campaign/* endpoints so that the existing JS (detail.js, medal_showcase.js)
requires no structural changes.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional


class DataProvider(ABC):
    """
    Abstract interface for campaign/career data sources.

    Implemented by:
        CampaignDataProvider  -- backed by JSON files via DataLoader + CampaignAggregator
        CareerDataProvider    -- backed by cp.db via CareerDatabase + CareerAggregator
    """

    @abstractmethod
    def get_source_type(self) -> str:
        """
        Return the source type identifier.

        Returns:
            "campaign" or "career"
        """

    @abstractmethod
    def is_available(self) -> bool:
        """
        Return True if the backing data source is accessible.

        CampaignDataProvider: True when data_dir is valid and readable.
        CareerDataProvider:   True when cp.db exists and is openable.
        """

    @abstractmethod
    def get_entry_list(self) -> List[Dict]:
        """
        Get list of entries for the landing page.

        Returns list of dicts with at minimum:
            name          -- string identifier (campaign name or str(root_career_id))
            display_name  -- human-readable name
            country       -- "ussr" | "germany" | "britain" | "usa"
            missions_completed  -- int
            promotions_count    -- int
            awards_count        -- int
            final_rank          -- str
            total_score         -- int
            total_kills         -- int
            source              -- "campaign" | "career"

        Career entries additionally include:
            theatre_chain  -- List[str]  e.g. ["Battle of Moscow", "Battle of Stalingrad"]
        """

    @abstractmethod
    def get_entry_detail(self, entry_id: str) -> Optional[Dict]:
        """
        Get full detail page payload for an entry.

        Args:
            entry_id: Campaign name (for campaigns) or str(root_career_id) (for careers).

        Returns:
            Detail dict or None if not found.
            Shape matches the existing /api/campaign/<name> response so that
            detail.js renders it without structural changes.
        """

    @abstractmethod
    def get_showcase_data(self, entry_id: str) -> Optional[Dict]:
        """
        Get medal showcase payload for an entry.

        Args:
            entry_id: Campaign name or str(root_career_id).

        Returns:
            Showcase dict or None.
            Shape matches the existing /api/campaign/<name>/showcase response.
        """
