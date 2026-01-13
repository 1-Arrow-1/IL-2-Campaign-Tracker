"""
Flask API routes for Campaign Service Record.

Endpoints:
- GET /api/campaigns - List all campaigns
- GET /api/campaign/<name> - Get campaign details
- GET /api/pdf/<name> - Check PDF availability
- GET /api/health - Health check
- POST /api/ping - Keep-alive for idle shutdown
"""

import base64
import logging
import re
import time
import traceback
from io import BytesIO
from pathlib import Path
from typing import Optional

from flask import Blueprint, jsonify, request, current_app, send_file, send_from_directory

from core.data_loader import DataLoader
from core.campaign_aggregator import CampaignAggregator
from utils.formatting import safe_campaign_filename
from utils.path_utils import get_game_directory
from utils.image_utils import convert_dds_to_png_bytes, find_existing_image_path
from utils.pilot_photo import pilot_photo_path, pilot_photo_filename


logger = logging.getLogger(__name__)

# Blueprint
api_bp = Blueprint('api', __name__)

# Global instances (initialized by init_api)
_data_loader: Optional[DataLoader] = None
_aggregator: Optional[CampaignAggregator] = None
_reports_dir: Optional[Path] = None

# Last activity timestamp (for idle shutdown)
_last_ping = [time.time()]

_PILOT_DESC_DEFAULT = "campaign_pilot"


def init_api(data_dir: Path, reports_dir: Optional[Path] = None):
    """
    Initialize API with data loader and aggregator.
    
    Args:
        data_dir: Directory containing JSON files
        reports_dir: Directory containing PDF reports (optional)
    """
    global _data_loader, _aggregator, _reports_dir
    
    _data_loader = DataLoader(data_dir, enable_cache=True)
    _aggregator = CampaignAggregator(_data_loader)
    _reports_dir = reports_dir or (data_dir / 'reports')
    
    logger.info(f"API initialized with data_dir={data_dir}")


def get_last_ping() -> float:
    """Get last ping timestamp (for idle monitoring)."""
    return _last_ping[0]


@api_bp.route('/api/debug/data')
def debug_data():
    """
    Debug endpoint to see raw data.
    
    Returns raw data from all JSON files for debugging.
    """
    if not _data_loader:
        return jsonify({'error': 'API not initialized'}), 500
    
    try:
        completion_state = _data_loader.get_campaign_completion_state()
        campaigns_with_progress = _data_loader.get_campaigns_with_progress()
        events = _data_loader.get_campaign_events()
        mission_dates = _data_loader.get_campaign_mission_dates()
        
        return jsonify({
            'completion_state': completion_state,
            'campaigns_with_progress': campaigns_with_progress,
            'events_keys': list(events.keys()) if events else [],
            'mission_dates_keys': list(mission_dates.keys()) if isinstance(mission_dates, dict) else [],
            'total_campaigns': len(completion_state) if completion_state else 0,
            'campaigns_with_missions': len(campaigns_with_progress),
        })
    except Exception as e:
        logger.error(f"Debug endpoint error: {e}", exc_info=True)
        return jsonify({
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


# ============================================================================
# Health & Status Endpoints
# ============================================================================

@api_bp.route('/api/health')
def health_check():
    """
    Health check endpoint.
    
    Returns:
        JSON with status and data source info
    """
    if not _data_loader:
        return jsonify({
            'status': 'error',
            'message': 'API not initialized'
        }), 500
    
    # Check if any data is available
    campaigns = _data_loader.get_campaigns_with_progress()
    
    return jsonify({
        'status': 'ok',
        'campaigns_available': len(campaigns),
        'data_dir': str(_data_loader.data_dir),
        'cache_stats': _data_loader.get_cache_stats()
    })


@api_bp.route('/api/ping', methods=['POST'])
def ping():
    """
    Keep-alive ping endpoint.
    
    Updates last activity timestamp to prevent idle shutdown.
    Frontend should ping every 30 seconds while active.
    """
    _last_ping[0] = time.time()
    return jsonify({'ok': True})


# ============================================================================
# Pilot Photo Endpoints
# ============================================================================

@api_bp.route('/api/pilot_photo')
def get_pilot_photo():
    """Get the stored pilot photo path, if available."""
    desc = request.args.get('desc', _PILOT_DESC_DEFAULT)
    photo_dir = current_app.config.get('PILOT_PHOTO_DIR')
    frozen = current_app.config.get('FROZEN', False)

    if not photo_dir:
        return jsonify({'path': None})

    photo_path = pilot_photo_path(Path(photo_dir), desc)
    if not photo_path.exists():
        return jsonify({'path': None})

    filename = pilot_photo_filename(desc)
    if frozen:
        return jsonify({'path': f'/pilot_photos/{filename}'})
    return jsonify({'path': f'/static/pilot_photos/{filename}'})


@api_bp.route('/api/save_pilot_photo', methods=['POST'])
def save_pilot_photo():
    """Save a cropped pilot photo from the client."""
    desc = request.form.get('desc', _PILOT_DESC_DEFAULT)
    img_data = request.form.get('img_data')
    logger.info(
        "Pilot photo upload received: desc=%s content_type=%s content_length=%s",
        desc,
        request.content_type,
        request.content_length
    )
    if not img_data:
        return jsonify({'error': 'No image data'}), 400

    match = re.match(r'^data:image/(png|jpeg|jpg|bmp|gif|webp);base64,', img_data)
    if not match:
        return jsonify({'error': 'Unsupported image format'}), 400

    try:
        img_str = re.sub(r'^data:image/\\w+;base64,', '', img_data)
        img_str = ''.join(img_str.split())
        remainder = len(img_str) % 4
        if remainder == 1:
            raise ValueError("Invalid base64 length")
        if remainder:
            img_str += '=' * (4 - remainder)
        img_bytes = base64.b64decode(img_str, validate=True)
    except (ValueError, base64.binascii.Error) as exc:
        logger.warning("Invalid image payload: %s", exc)
        return jsonify({'error': 'Invalid image data. Please choose a different image.'}), 400

    photo_dir = current_app.config.get('PILOT_PHOTO_DIR')
    frozen = current_app.config.get('FROZEN', False)
    if not photo_dir:
        return jsonify({'error': 'Photo storage not configured'}), 500

    photo_path = pilot_photo_path(Path(photo_dir), desc)
    logger.info("Saving pilot photo to %s (bytes=%s)", photo_path, len(img_bytes))
    try:
        photo_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = photo_path.with_suffix(f"{photo_path.suffix}.tmp")
        with open(tmp_path, 'wb') as tmp_file:
            tmp_file.write(img_bytes)
        tmp_path.replace(photo_path)
    except OSError as exc:
        logger.error(
            "Failed to save pilot photo to %s: %s",
            photo_path,
            exc,
            exc_info=True
        )
        return jsonify({'error': 'Failed to save photo'}), 500

    filename = pilot_photo_filename(desc)
    if frozen:
        return jsonify({'path': f'/pilot_photos/{filename}'})
    return jsonify({'path': f'/static/pilot_photos/{filename}'})


# ============================================================================
# Campaign List Endpoint
# ============================================================================

@api_bp.route('/api/campaigns')
def get_campaigns():
    """
    Get list of all campaigns with progress.
    
    Used by landing page to display campaign list.
    
    Returns:
        JSON array of campaigns:
        [
            {
                "name": "kerch",
                "display_name": "Kerch Peninsula Campaign",
                "country": "ussr",
                "missions_completed": 15,
                "promotions_count": 3,
                "awards_count": 8,
                "final_rank": "Senior Sergeant"
            },
            ...
        ]
    """
    _last_ping[0] = time.time()
    
    try:
        if not _aggregator:
            return jsonify({
                'error': 'API not initialized'
            }), 500
        
        campaigns = _aggregator.get_campaign_list()
        
        logger.info(f"Served campaign list: {len(campaigns)} campaigns")
        return jsonify(campaigns)
        
    except Exception as e:
        logger.error(f"Error getting campaign list: {e}", exc_info=True)
        return jsonify({
            'error': 'Failed to load campaigns',
            'detail': str(e)
        }), 500


# ============================================================================
# Campaign Detail Endpoint
# ============================================================================

@api_bp.route('/api/campaign/<campaign_name>')
def get_campaign_detail(campaign_name: str):
    """
    Get detailed campaign data.
    
    Used by detail page to display full campaign service record.
    
    Args:
        campaign_name: Campaign identifier (e.g., "kerch")
    
    Returns:
        JSON with complete campaign data:
        {
            "name": "kerch",
            "display_name": "Kerch Peninsula Campaign",
            "country": "ussr",
            "missions_completed": 15,
            "events": [...],
            "debriefings_html": "...",
            "summary": {...}
        }
    """
    _last_ping[0] = time.time()
    
    try:
        if not _aggregator:
            return jsonify({
                'error': 'API not initialized'
            }), 500
        
        # Use campaign name directly (Flask already URL-decodes it safely)
        # Note: Campaign names come from JSON keys, so they're trusted
        # 🔧 Normalize case for consistency
        campaign_name = campaign_name.lower()# 🔧 Normalize case for consistency
        campaign_data = _aggregator.get_campaign_detail(campaign_name)
        
        if not campaign_data:
            logger.warning(f"Campaign not found: {campaign_name}")
            return jsonify({
                'error': 'Campaign not found',
                'campaign': campaign_name
            }), 404
        
        logger.info(f"Served campaign detail: {campaign_name}")
        return jsonify(campaign_data)
        
    except Exception as e:
        logger.error(f"Error getting campaign detail for {campaign_name}: {e}", exc_info=True)
        return jsonify({
            'error': 'Failed to load campaign details',
            'detail': str(e)
        }), 500


# ============================================================================
# PDF Report Endpoint
# ============================================================================

@api_bp.route('/api/pdf/<campaign_name>')
def check_pdf_exists(campaign_name: str):
    """
    Check if PDF report exists for campaign.
    
    Returns path if exists, otherwise 404.
    Frontend uses this to show/hide download button.
    
    Args:
        campaign_name: Campaign identifier
    
    Returns:
        JSON with PDF info or 404 if not found
    """
    _last_ping[0] = time.time()
    
    try:
        if not _reports_dir:
            return jsonify({
                'error': 'Reports directory not configured'
            }), 404
        
        # Generate expected PDF filename using campaign name directly
        campaign_name = campaign_name.lower()
        pdf_filename = f"{safe_campaign_filename(campaign_name)}.pdf"
        pdf_path = _reports_dir / pdf_filename
        
        if pdf_path.exists():
            # Return relative path for frontend
            return jsonify({
                'available': True,
                'filename': pdf_filename,
                'path': f'reports/{pdf_filename}',
                'size': pdf_path.stat().st_size
            })
        else:
            return jsonify({
                'available': False,
                'message': 'PDF report not generated yet'
            }), 404
            
    except Exception as e:
        logger.error(f"Error checking PDF for {campaign_name}: {e}", exc_info=True)
    return jsonify({
        'error': 'Failed to check PDF availability',
        'detail': str(e)
    }), 500


# ============================================================================
# Game Assets Endpoint
# ============================================================================

@api_bp.route('/api/game_assets/<path:asset_path>')
def get_game_asset(asset_path: str):
    """Serve game assets from the IL-2 installation swf directory."""
    if not _data_loader:
        return jsonify({'error': 'API not initialized'}), 500

    mission_dates = _data_loader.get_campaign_mission_dates()
    game_directory = get_game_directory(mission_dates)
    if not game_directory:
        return jsonify({'error': 'Game directory not configured'}), 404

    swf_dir = Path(game_directory) / 'data' / 'swf'
    requested = (swf_dir / asset_path).resolve()

    if swf_dir not in requested.parents and swf_dir != requested:
        logger.warning("Blocked invalid asset path: %s", asset_path)
        return jsonify({'error': 'Invalid asset path'}), 400

    existing = find_existing_image_path(requested)
    if not existing:
        logger.warning("Game asset not found: %s", requested)
        return jsonify({'error': 'Asset not found'}), 404

    if existing.suffix.lower() == ".dds":
        png_bytes = convert_dds_to_png_bytes(existing)
        if not png_bytes:
            return jsonify({'error': 'Failed to convert DDS asset'}), 500
        return send_file(
            BytesIO(png_bytes),
            mimetype="image/png",
            download_name=existing.with_suffix(".png").name
        )

    return send_from_directory(swf_dir, asset_path)


# ============================================================================
# Error Handlers
# ============================================================================

@api_bp.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({
        'error': 'Not found',
        'path': request.path
    }), 404


@api_bp.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    logger.error(f"Internal error: {error}", exc_info=True)
    return jsonify({
        'error': 'Internal server error',
        'detail': str(error)
    }), 500
