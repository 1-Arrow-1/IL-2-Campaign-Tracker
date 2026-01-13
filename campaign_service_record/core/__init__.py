"""
Core business logic for Campaign Service Record.

This package contains:
- data_loader: JSON file loading and caching
- campaign_aggregator: Data transformation and aggregation
- validation: Data validation and schema checks
"""

from .data_loader import DataLoader
from .campaign_aggregator import CampaignAggregator
from .validation import validate_campaign_data

__all__ = ['DataLoader', 'CampaignAggregator', 'validate_campaign_data']
