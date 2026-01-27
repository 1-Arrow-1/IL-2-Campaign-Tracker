"""
Campaign Service Record utility modules.

Flask-specific utilities for the Campaign Service Record web application:
- Image processing (DDS to PNG conversion, data URIs)
- Path utilities (game asset resolution)
- Pilot photo handling

Note: Core utilities (combat_results, formatting, sorting) are imported from root utils/ folder.
"""

# Flask-specific utilities remain in campaign_service_record/utils/
from .image_utils import (
    build_dds_data_uri,
    convert_dds_to_png_bytes,
    find_existing_image_path
)
from .path_utils import (
    build_award_image_relative_path,
    build_award_large_image_relative_path,
    build_game_asset_url,
    get_game_directory
)
from .pilot_photo import (
    pilot_photo_path,
    pilot_photo_filename,
    pilot_name_path
)

__all__ = [
    # Image utilities
    'build_dds_data_uri',
    'convert_dds_to_png_bytes',
    'find_existing_image_path',
    # Path utilities
    'build_award_image_relative_path',
    'build_award_large_image_relative_path',
    'build_game_asset_url',
    'get_game_directory',
    # Pilot photo utilities
    'pilot_photo_path',
    'pilot_photo_filename',
    'pilot_name_path'
]
