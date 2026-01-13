"""
Configuration management for Campaign Service Record.

Handles:
- Data directory resolution
- Static file paths (frozen vs development)
- Server configuration
- Feature flags
"""

import os
import sys
from pathlib import Path
from typing import Optional


class Config:
    """
    Application configuration with automatic environment detection.
    
    Design Decisions:
    - Frozen mode (PyInstaller) vs development mode auto-detected
    - Data directory defaults to CWD (same as Campaign Tracker)
    - Static files bundled in frozen mode via sys._MEIPASS
    """
    
    def __init__(self):
        self.frozen = getattr(sys, 'frozen', False)
        self.base_dir = self._resolve_base_dir()
        self.data_dir = self._resolve_data_dir()
        self.static_dir = self._resolve_static_dir()
        self.user_data_dir = self._resolve_user_data_dir()
        self.pilot_photo_dir = self._resolve_pilot_photo_dir()
        
        # Server configuration
        self.host = '127.0.0.1'
        self.port = 5000
        self.debug = not self.frozen
        
        # Feature flags
        self.auto_open_browser = True
        self.shutdown_on_idle = True
        self.idle_timeout_seconds = 60
        
        # Caching
        self.enable_json_cache = True
        self.cache_ttl_seconds = 5  # Refresh if file modified
    
    def _resolve_base_dir(self) -> Path:
        """
        Get the base directory of the application.
        
        Returns:
            Path to directory containing app.py (or exe in frozen mode)
        """
        if self.frozen:
            # PyInstaller creates a temp folder and stores path in _MEIPASS
            return Path(sys.executable).parent
        else:
            return Path(__file__).parent.absolute()
    
    def _resolve_data_dir(self) -> Path:
        """
        Resolve data directory containing Campaign Tracker JSON files.
        
        Priority:
        1. DATA_DIR environment variable
        2. Current working directory (same as Campaign Tracker)
        
        Returns:
            Path to directory containing JSON data files
        """
        env_dir = os.environ.get('DATA_DIR')
        if env_dir:
            return Path(env_dir).absolute()
        
        # Default: Use CWD (where user launched the EXE)
        # This allows placing the tool in the same folder as Campaign Tracker
        return Path.cwd()
    
    def _resolve_static_dir(self) -> Path:
        """
        Resolve static files directory.
        
        Returns:
            Path to static/ directory (bundled in frozen mode)
        """
        if self.frozen:
            # PyInstaller bundles static/ into _MEIPASS
            return Path(sys._MEIPASS) / 'static'
        else:
            return self.base_dir / 'static'

    def _resolve_user_data_dir(self) -> Path:
        """
        Resolve user-specific data directory.

        Used for persistent files when running as an EXE.
        """
        base = os.environ.get('LOCALAPPDATA') or str(Path.home())
        return Path(base) / '.il2_campaign_service_record'

    def _resolve_pilot_photo_dir(self) -> Path:
        """
        Resolve directory for pilot photo storage.

        Mirrors IL-2 Pilot Service Record behavior:
        - Frozen EXE: user data directory
        - Source: static directory
        """
        if self.frozen:
            return self.user_data_dir / 'pilot_photos'
        return self.static_dir / 'pilot_photos'
    
    def get_json_path(self, filename: str) -> Path:
        """
        Get full path to a JSON data file.
        
        Args:
            filename: Name of JSON file (e.g., 'campaign_events.json')
        
        Returns:
            Full path to JSON file in data directory
        """
        return self.data_dir / filename
    
    def validate(self) -> tuple[bool, Optional[str]]:
        """
        Validate configuration.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check static directory exists
        if not self.static_dir.exists():
            return False, f"Static directory not found: {self.static_dir}"
        
        # Check data directory is writable (for potential future features)
        if not os.access(self.data_dir, os.R_OK):
            return False, f"Data directory not readable: {self.data_dir}"
        
        return True, None
    
    def __repr__(self) -> str:
        return (
            f"Config(frozen={self.frozen}, "
            f"base_dir={self.base_dir}, "
            f"data_dir={self.data_dir}, "
            f"static_dir={self.static_dir})"
        )


# Global singleton instance
_config: Optional[Config] = None


def get_config() -> Config:
    """
    Get global configuration instance (singleton).
    
    Returns:
        Application configuration
    """
    global _config
    if _config is None:
        _config = Config()
    return _config


def reset_config():
    """Reset configuration (useful for testing)."""
    global _config
    _config = None
