"""
API package for Campaign Service Record.

Provides REST endpoints for:
- Campaign list (landing page)
- Campaign details (detail page)
- PDF availability checks
- Career mode list and details (when cp.db is available)
"""

from .routes import api_bp, init_api, init_career

__all__ = ['api_bp', 'init_api', 'init_career']
