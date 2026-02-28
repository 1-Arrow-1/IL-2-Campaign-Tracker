"""
Data provider abstraction layer for Campaign Service Record.

Provides:
- DataProvider: abstract base class
- CampaignDataProvider: wraps existing DataLoader + CampaignAggregator
- CareerDataProvider: wraps cp.db via CareerDatabase + CareerAggregator
"""

from campaign_service_record.providers.base import DataProvider
from campaign_service_record.providers.campaign_provider import CampaignDataProvider

__all__ = ['DataProvider', 'CampaignDataProvider']
