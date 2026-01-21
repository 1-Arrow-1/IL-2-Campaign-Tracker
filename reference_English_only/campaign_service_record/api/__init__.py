"""
API package for Campaign Service Record.

Provides REST endpoints for:
- Campaign list (landing page)
- Campaign details (detail page)
- PDF availability checks
"""

from .routes import api_bp, init_api

__all__ = ['api_bp', 'init_api']
