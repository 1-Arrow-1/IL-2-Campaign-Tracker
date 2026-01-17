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
import json
import logging
import os
import random
import re
import time
import traceback
from io import BytesIO
from pathlib import Path
from typing import Optional

from flask import Blueprint, jsonify, request, current_app, send_file, send_from_directory, session

from core.data_loader import DataLoader
from core.campaign_aggregator import CampaignAggregator
from utils.formatting import safe_campaign_filename
from utils.path_utils import get_game_directory
from utils.image_utils import convert_dds_to_png_bytes, find_existing_image_path
from utils.pilot_photo import pilot_photo_path, pilot_photo_filename, pilot_name_path


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
_PERSONAL_DATA_FILENAME = "campaign_personal_data.json"
_DEFAULT_LOCALE = "en"
_LANDING_BACKGROUNDS = [
    "images/background_Britain.png",
    "images/background_Germany.png",
    "images/background_US.png",
    "images/background_USSR.png",
]


def _sanitize_pilot_name(name: Optional[str]) -> Optional[str]:
    if name is None:
        return None
    cleaned = name.strip()
    return cleaned or None


def _get_personal_data_path() -> Optional[Path]:
    base_dir = current_app.config.get('PERSONAL_DATA_DIR')
    if not base_dir:
        return None
    return Path(base_dir) / _PERSONAL_DATA_FILENAME


def _load_personal_data() -> dict:
    data_path = _get_personal_data_path()
    if not data_path or not data_path.exists():
        return {}
    try:
        with open(data_path, 'r', encoding='utf-8') as file:
            payload = json.load(file)
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("Failed to read personal data file %s: %s", data_path, exc)
        return {}
    if isinstance(payload, dict):
        return payload
    logger.error("Invalid personal data format in %s", data_path)
    return {}


def _save_personal_data(data: dict) -> bool:
    data_path = _get_personal_data_path()
    if not data_path:
        return False
    try:
        data_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = data_path.with_suffix(f"{data_path.suffix}.tmp")
        with open(tmp_path, 'w', encoding='utf-8') as file:
            json.dump(data, file, indent=2, ensure_ascii=False)
        tmp_path.replace(data_path)
        return True
    except OSError as exc:
        logger.error("Failed to save personal data to %s: %s", data_path, exc, exc_info=True)
        return False


def _sanitize_personal_data_value(value: Optional[str]) -> str:
    if value is None:
        return ''
    return str(value).strip()


def _get_tracker_settings_path() -> Path:
    base = os.environ.get('LOCALAPPDATA') or str(Path.home())
    return Path(base) / '.il2_campaign_tracker' / 'settings.json'


def _load_tracker_settings() -> dict:
    settings_path = _get_tracker_settings_path()
    if not settings_path.exists():
        return {}
    try:
        with open(settings_path, 'r', encoding='utf-8') as file:
            payload = json.load(file)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Failed to read settings from %s: %s", settings_path, exc)
        return {}
    if isinstance(payload, dict):
        return payload
    logger.warning("Invalid settings payload in %s", settings_path)
    return {}


def _resolve_campaign_name(campaign_name: str) -> str:
    if not _data_loader:
        return campaign_name
    completion_state = _data_loader.get_campaign_completion_state()
    if campaign_name in completion_state:
        return campaign_name
    normalized = campaign_name.lower()
    for key in completion_state.keys():
        if key.lower() == normalized:
            return key
    return campaign_name


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
# Settings Endpoint
# ============================================================================

@api_bp.route('/api/settings')
def get_settings():
    """Expose locale settings for the frontend i18n loader."""
    payload = _load_tracker_settings()
    locale = str(payload.get('locale') or _DEFAULT_LOCALE)
    fallback = str(payload.get('fallback_locale') or _DEFAULT_LOCALE)
    return jsonify({
        'locale': locale,
        'fallback_locale': fallback,
    })


# ============================================================================
# Landing Background Endpoint
# ============================================================================

@api_bp.route('/api/landing_background')
def get_landing_background():
    """Select a random landing background per session."""
    selected = session.get('landing_background')
    if selected not in _LANDING_BACKGROUNDS:
        selected = random.choice(_LANDING_BACKGROUNDS)
        session['landing_background'] = selected
    return jsonify({'background': f'/static/{selected}', 'filename': selected})


# ============================================================================
# Pilot Photo Endpoints
# ============================================================================

@api_bp.route('/api/pilot_photo')
def get_pilot_photo():
    """Get the stored pilot photo path, if available."""
    desc = request.args.get('desc', _PILOT_DESC_DEFAULT)
    photo_dir = current_app.config.get('PILOT_PHOTO_DIR')

    if not photo_dir:
        return jsonify({'path': None, 'name': None})

    photo_path = pilot_photo_path(Path(photo_dir), desc)
    name_path = pilot_name_path(Path(photo_dir), desc)
    name_value = None
    if name_path.exists():
        try:
            name_value = _sanitize_pilot_name(name_path.read_text(encoding='utf-8'))
        except OSError as exc:
            logger.warning("Failed to read pilot name from %s: %s", name_path, exc)

    if not photo_path.exists():
        return jsonify({'path': None, 'name': name_value})

    filename = pilot_photo_filename(desc)
    return jsonify({'path': f'/pilot_photos/{filename}', 'name': name_value})


@api_bp.route('/api/save_pilot_photo', methods=['POST'])
def save_pilot_photo():
    """Save a cropped pilot photo from the client."""
    desc = request.form.get('desc', _PILOT_DESC_DEFAULT)
    img_data = request.form.get('img_data')
    pilot_name = request.form.get('pilot_name')
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
        img_str = re.sub(r'^data:image/\w+;base64,', '', img_data)
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
    name_path = pilot_name_path(Path(photo_dir), desc)
    name_value = _sanitize_pilot_name(pilot_name)
    if pilot_name is not None:
        try:
            if name_value:
                name_path.parent.mkdir(parents=True, exist_ok=True)
                name_path.write_text(name_value, encoding='utf-8')
            elif name_path.exists():
                name_path.unlink()
        except OSError as exc:
            logger.error("Failed to save pilot name to %s: %s", name_path, exc, exc_info=True)
            return jsonify({'error': 'Failed to save pilot name'}), 500

    return jsonify({'path': f'/pilot_photos/{filename}', 'name': name_value})


# ============================================================================
# Campaign Personal Data Endpoints
# ============================================================================

@api_bp.route('/api/campaign/<campaign_name>/personal_data')
def get_campaign_personal_data(campaign_name: str):
    """Get stored personal data for a campaign."""
    resolved = _resolve_campaign_name(campaign_name)
    logger.info("Personal data read requested for campaign=%s resolved=%s", campaign_name, resolved)
    data = _load_personal_data()
    return jsonify(data.get(resolved, {}))


@api_bp.route('/api/campaign/<campaign_name>/personal_data', methods=['POST'])
def save_campaign_personal_data(campaign_name: str):
    """Save personal data for a campaign."""
    resolved = _resolve_campaign_name(campaign_name)
    logger.info("Personal data save requested for campaign=%s resolved=%s", campaign_name, resolved)
    if not request.is_json:
        return jsonify({'error': 'Invalid payload'}), 400
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify({'error': 'Invalid payload'}), 400

    cleaned = {
        'name': _sanitize_personal_data_value(payload.get('name')),
        'first_name': _sanitize_personal_data_value(payload.get('first_name')),
        'birthday': _sanitize_personal_data_value(payload.get('birthday')),
        'birth_place': _sanitize_personal_data_value(payload.get('birth_place')),
        'birth_country': _sanitize_personal_data_value(payload.get('birth_country'))
    }

    data = _load_personal_data()
    data[resolved] = cleaned
    if not _save_personal_data(data):
        return jsonify({'error': 'Failed to save personal data'}), 500
    return jsonify(cleaned)


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
        
        resolved = _resolve_campaign_name(campaign_name)
        campaign_data = _aggregator.get_campaign_detail(resolved)
        
        if not campaign_data:
            logger.warning(f"Campaign not found: {campaign_name}")
            return jsonify({
                'error': 'Campaign not found',
                'campaign': campaign_name
            }), 404
        
        logger.info(f"Served campaign detail: {resolved}")
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
        
        resolved = _resolve_campaign_name(campaign_name)
        pdf_filename = f"{safe_campaign_filename(resolved)}.pdf"
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
