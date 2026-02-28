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
import re
import time
import traceback
from io import BytesIO
from pathlib import Path
from typing import Optional

from flask import Blueprint, jsonify, request, current_app, send_file, send_from_directory

from campaign_service_record.core.data_loader import DataLoader
from campaign_service_record.core.campaign_aggregator import CampaignAggregator
from campaign_service_record.core.locale_resolver import resolve_detail_page_locale
from campaign_service_record.providers.career_provider import CareerDataProvider
from campaign_service_record.core.medal_showcase import (
    load_coordinates,
    resolve_showcase_country,
    resolve_ussr_variant,
    earned_showcase_names_from_events,
    build_showcase_data,
    ASSET_FOLDER,
)
from utils.formatting import safe_campaign_filename
from campaign_service_record.utils.path_utils import get_game_directory
from campaign_service_record.utils.image_utils import convert_dds_to_png_bytes, find_existing_image_path
from campaign_service_record.utils.pilot_photo import pilot_photo_path, pilot_photo_filename, pilot_name_path
from utils.locale_config import resolve_locale
from utils.supported_locales import DEFAULT_LOCALE, get_supported_locales, normalize_locale


logger = logging.getLogger(__name__)

# Blueprint
api_bp = Blueprint('api', __name__)

# Global instances (initialized by init_api)
_data_loader: Optional[DataLoader] = None
_aggregator: Optional[CampaignAggregator] = None
_reports_dir: Optional[Path] = None

# Career mode globals (initialized by init_career, optional)
_career_provider: Optional[CareerDataProvider] = None
_career_game_dir: Optional[Path] = None   # <game_dir>/data/swf/CampaignRanksAwards/...
_career_data_dir: Optional[Path] = None   # <data_dir>/CampaignRanksAwards/...

# Last activity timestamp (for idle shutdown)
_last_ping = [time.time()]

_PILOT_DESC_DEFAULT = "campaign_pilot"
_PERSONAL_DATA_FILENAME = "campaign_personal_data.json"


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


def init_career(
    db_path: Path,
    reports_dir: Optional[Path] = None,
    game_dir: Optional[Path] = None,
    data_dir: Optional[Path] = None,
) -> bool:
    """
    Initialize the Career mode provider.

    Called from app.py only when cp.db is confirmed present and readable.
    Safe to call multiple times (re-initializes on each call).

    Args:
        db_path:     Absolute path to cp.db.
        reports_dir: Directory to search for missionReport .txt/.mlg files.
                     Defaults to <game_dir>/data/FlightLogs when not supplied.
        game_dir:    IL-2 game root directory (optional; used for FlightLogs
                     auto-detection and squadron name lookups).
                     If omitted, CareerDatabase derives it from db_path
                     (<game_dir>/data/Career/cp.db).
        data_dir:    Tracker data directory (optional; used as fallback for
                     squadron name lookups via <data_dir>/CampaignRanksAwards/).

    Returns:
        True if initialization succeeded, False otherwise.
    """
    global _career_provider, _career_game_dir, _career_data_dir

    from campaign_service_record.career.database import CareerDatabase
    from campaign_service_record.career.chain_resolver import CareerChainResolver
    from campaign_service_record.career.statistics import StatisticsMapper
    from campaign_service_record.career.mission_linker import MissionReportLinker
    from campaign_service_record.career.aggregator import CareerAggregator

    try:
        db = CareerDatabase(db_path)

        # Resolve reports_dir: prefer explicit arg, fall back to FlightLogs in game_dir,
        # then db.game_dir (derived from cp.db path), then CWD as last resort.
        resolved_reports_dir = reports_dir
        if resolved_reports_dir is None:
            _gd = game_dir or db.game_dir
            if _gd is not None:
                fl = _gd / 'data' / 'FlightLogs'
                if fl.is_dir():
                    resolved_reports_dir = fl
                    logger.info("Career reports_dir auto-detected: %s", fl)
                else:
                    logger.warning(
                        "FlightLogs not found at %s; missionReport linking will be unavailable", fl
                    )
        if resolved_reports_dir is None:
            resolved_reports_dir = Path('.')

        resolver = CareerChainResolver(db)
        stats = StatisticsMapper()
        linker = MissionReportLinker(resolved_reports_dir)
        aggregator = CareerAggregator(
            db, resolver, stats, linker, game_dir=game_dir, data_dir=data_dir
        )
        _career_provider = CareerDataProvider(db, resolver, aggregator)
        _career_game_dir = game_dir
        _career_data_dir = data_dir
        logger.info("Career mode initialized: db=%s", db_path)
        return True
    except Exception as exc:
        logger.error("Failed to initialize career mode: %s", exc, exc_info=True)
        _career_provider = None
        return False


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

@api_bp.route('/api/locale')
def get_locale():
    """
    Get current locale setting.
    
    Returns the locale from environment variable CAMPAIGN_TRACKER_LOCALE,
    or defaults to 'en'.
    
    Returns:
        JSON with locale code:
        {
            "locale": "de"
        }
    """
    locale = resolve_locale()
    return jsonify({'locale': normalize_locale(locale, DEFAULT_LOCALE)})


@api_bp.route('/api/locales')
def get_locales():
    """
    Get list of supported locales.

    Returns:
        JSON with locale list:
        {
            "locales": ["en", "de"]
        }
    """
    return jsonify({'locales': get_supported_locales(), 'default': DEFAULT_LOCALE})


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
    if frozen:
        return jsonify({'path': f'/pilot_photos/{filename}', 'name': name_value})
    return jsonify({'path': f'/static/pilot_photos/{filename}', 'name': name_value})


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

    if frozen:
        return jsonify({'path': f'/pilot_photos/{filename}', 'name': name_value})
    return jsonify({'path': f'/static/pilot_photos/{filename}', 'name': name_value})


# ============================================================================
# Campaign Personal Data Endpoints
# ============================================================================

@api_bp.route('/api/campaign/<campaign_name>/personal_data')
def get_campaign_personal_data(campaign_name: str):
    """Get stored personal data for a campaign."""
    data = _load_personal_data()
    return jsonify(data.get(campaign_name, {}))


@api_bp.route('/api/campaign/<campaign_name>/personal_data', methods=['POST'])
def save_campaign_personal_data(campaign_name: str):
    """Save personal data for a campaign."""
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
        'birth_country': _sanitize_personal_data_value(payload.get('birth_country')),
        'additional_notes': _sanitize_personal_data_value(payload.get('additional_notes'))
    }

    data = _load_personal_data()
    data[campaign_name] = cleaned
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
        
        # Use campaign name directly (Flask already URL-decodes it safely)
        # Note: Campaign names come from JSON keys, so they're trusted
        # Normalize case for consistency
        campaign_name = campaign_name.lower()
        campaign_data = _aggregator.get_campaign_detail(campaign_name)

        if not campaign_data:
            logger.warning(f"Campaign not found: {campaign_name}")
            return jsonify({
                'error': 'Campaign not found',
                'campaign': campaign_name
            }), 404

        # Add effective locale for detail page rendering
        # This respects per-campaign language override if set
        effective_locale = resolve_detail_page_locale(
            campaign_name,
            data_loader=_data_loader
        )
        campaign_data['effective_locale'] = effective_locale

        # Select the localized debriefings_html based on effective locale
        # If the localized version exists and is not empty, use it
        localized_key = f'debriefings_html_{effective_locale}'
        localized_debriefings = campaign_data.get(localized_key, '')
        if localized_debriefings and localized_debriefings.strip():
            campaign_data['debriefings_html'] = localized_debriefings
            logger.debug(f"Using localized debriefings ({effective_locale}) for {campaign_name}")
        elif effective_locale != 'en':
            # No pre-generated debriefings for this locale — fall back to English
            # and correct effective_locale so the frontend doesn't re-translate
            logger.info(f"No localized debriefings for '{effective_locale}', "
                        f"falling back to English for {campaign_name}")
            en_debriefings = campaign_data.get('debriefings_html_en', '')
            if en_debriefings and en_debriefings.strip():
                campaign_data['debriefings_html'] = en_debriefings
            effective_locale = 'en'
            campaign_data['effective_locale'] = effective_locale

        # Remove the localized versions from response (no need to send all 3)
        for locale in ('en', 'de', 'ru'):
            campaign_data.pop(f'debriefings_html_{locale}', None)

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
# Career Assets Endpoint
# ============================================================================

@api_bp.route('/api/career_assets/<path:asset_path>')
def get_career_asset(asset_path: str):
    """
    Serve CampaignRanksAwards images for the Career mode event list and modals.

    Tries candidate roots in order:
      1. <data_dir>/<asset_path>           (tracker's local CampaignRanksAwards copy)
      2. <game_dir>/data/swf/<asset_path>  (IL-2 game installation)

    DDS files are converted to PNG on-the-fly.
    """
    if not _career_provider:
        return jsonify({'error': 'Career mode not initialized'}), 500

    candidate_roots = []
    if _career_data_dir:
        candidate_roots.append(_career_data_dir)
    if _career_game_dir:
        candidate_roots.append(_career_game_dir / 'data' / 'swf')

    if not candidate_roots:
        return jsonify({'error': 'Career assets directory not configured'}), 404

    for root in candidate_roots:
        full_path = (root / asset_path).resolve()
        # Security: prevent path traversal
        try:
            full_path.relative_to(root.resolve())
        except ValueError:
            logger.warning("Blocked path traversal attempt: %s", asset_path)
            return jsonify({'error': 'Invalid asset path'}), 400

        existing = find_existing_image_path(full_path)
        if not existing:
            continue

        if existing.suffix.lower() == '.dds':
            png_bytes = convert_dds_to_png_bytes(existing)
            if not png_bytes:
                return jsonify({'error': 'Failed to convert DDS asset'}), 500
            return send_file(
                BytesIO(png_bytes),
                mimetype='image/png',
                download_name=existing.with_suffix('.png').name,
            )

        return send_file(existing, mimetype='image/png')

    logger.warning("Career asset not found: %s", asset_path)
    return jsonify({'error': 'Asset not found'}), 404


# ============================================================================
# Medal Showcase Endpoint
# ============================================================================

@api_bp.route('/api/campaign/<campaign_name>/showcase')
def get_campaign_showcase(campaign_name: str):
    """
    Build and return medal showcase data for the given campaign.

    Returns:
        JSON:
        {
            "country_key": "germany",
            "canvas_url":  "/api/tracker_assets/CampaignRanksAwards/Germany/Germany_canvas.png",
            "overlay": { "url": "...", "x": 32, "y": 0, "w": 2018, "h": 961 },
            "medals": [
                { "image_url": "...", "x": 141, "y": 134, "w": 363, "h": 503,
                  "name": "iron_cross_2nd_big1" },
                ...
            ]
        }
    """
    _last_ping[0] = __import__('time').time()

    if not _aggregator or not _data_loader:
        return jsonify({'error': 'API not initialized'}), 500

    campaign_name = campaign_name.lower()

    data_dir = _data_loader.data_dir

    # --- Locate JSON coordinate file ---
    # Primary: alongside the EXE / in data_dir (installed build).
    # Fallback: one level up (dev: Flask started from campaign_service_record/ subdir).
    excel_path = data_dir / 'IL-2_Tracker_award_coordinates.json'
    if not excel_path.exists():
        excel_path = data_dir.parent / 'IL-2_Tracker_award_coordinates.json'

    if not excel_path.exists():
        return jsonify({'error': 'Coordinate file not found', 'path': str(excel_path)}), 404

    # --- CampaignRanksAwards lives in the IL-2 game's swf directory ---
    # The installer copies CampaignRanksAwards/* there; we serve via /api/game_assets/.
    mission_dates = _data_loader.get_campaign_mission_dates()
    game_directory = get_game_directory(mission_dates)
    if game_directory:
        assets_dir = Path(game_directory) / 'data' / 'swf' / 'CampaignRanksAwards'
    else:
        assets_dir = data_dir / 'CampaignRanksAwards'  # fallback (no game dir configured)

    # --- Load / cache JSON coordinates ---
    try:
        coordinates = load_coordinates(excel_path)
    except Exception as exc:
        logger.error("Failed to parse medal coordinates: %s", exc, exc_info=True)
        return jsonify({'error': 'Failed to parse coordinate file', 'detail': str(exc)}), 500

    # --- Get campaign events ---
    events_data = _data_loader.get_campaign_events()
    campaign_events = events_data.get(campaign_name, {})
    if not campaign_events:
        return jsonify({'error': 'Campaign not found or no events'}), 404

    events = campaign_events.get('events', [])
    raw_country = campaign_events.get('country', '')

    # --- Resolve country key ---
    showcase_base = resolve_showcase_country(raw_country)
    if not showcase_base:
        return jsonify({'error': f'Unsupported country for showcase: {raw_country}'}), 404

    # For USSR, decide early vs late from the last mission date
    if showcase_base == 'ussr':
        # Find latest mission date among events
        dates = [ev.get('date') for ev in events if ev.get('date')]
        last_date = max(dates) if dates else None
        country_key = resolve_ussr_variant(last_date)
    else:
        country_key = showcase_base

    # --- Build set of earned showcase names ---
    earned = earned_showcase_names_from_events(events)

    # --- Build showcase payload ---
    try:
        payload = build_showcase_data(
            country_key=country_key,
            earned_showcase_names=earned,
            coordinates=coordinates,
            assets_dir=assets_dir,
            tracker_asset_url_prefix='/api/game_assets',
        )
    except Exception as exc:
        logger.error("Failed to build showcase data: %s", exc, exc_info=True)
        return jsonify({'error': 'Failed to build showcase data', 'detail': str(exc)}), 500

    if not payload:
        return jsonify({'error': 'No showcase data available for this country'}), 404

    return jsonify(payload)


# ============================================================================
# Tracker Assets Endpoint
# ============================================================================

@api_bp.route('/api/tracker_assets/<path:asset_path>')
def get_tracker_asset(asset_path: str):
    """
    Serve tracker-bundled assets (CampaignRanksAwards canvas, overlay,
    and *_big1.png medal images).

    These are served from <data_dir>/CampaignRanksAwards/, which is the
    tracker's own asset folder (distinct from the IL-2 game installation).
    """
    if not _data_loader:
        return jsonify({'error': 'API not initialized'}), 500

    data_dir = _data_loader.data_dir
    assets_root = data_dir / 'CampaignRanksAwards'

    requested = (assets_root / asset_path).resolve()

    # Security: prevent path traversal
    try:
        requested.relative_to(assets_root.resolve())
    except ValueError:
        logger.warning("Blocked path traversal attempt: %s", asset_path)
        return jsonify({'error': 'Invalid asset path'}), 400

    if not requested.exists():
        logger.warning("Tracker asset not found: %s", requested)
        return jsonify({'error': 'Asset not found'}), 404

    return send_from_directory(str(assets_root), asset_path)


# ============================================================================
# Mode Endpoint
# ============================================================================

@api_bp.route('/api/mode')
def get_mode():
    """
    Return which data providers are currently active and the configured app mode.

    Used by the frontend to decide which sections to render and which title to show.

    Returns:
        {
            "modes":    ["campaign"] | ["career"] | ["campaign", "career"],
            "app_mode": "campaign" | "career"
        }
    """
    from campaign_service_record.config import get_config
    app_mode = get_config().app_mode

    modes = []
    if _aggregator is not None:
        modes.append("campaign")
    if _career_provider is not None and _career_provider.is_available():
        modes.append("career")
    return jsonify({"modes": modes, "app_mode": app_mode})


# ============================================================================
# Career List Endpoint
# ============================================================================

@api_bp.route('/api/careers')
def get_careers():
    """
    Get list of all virtual pilot careers.

    Returns the same shape as /api/campaigns plus a 'theatre_chain' field
    per entry and 'source': 'career'.

    Returns:
        JSON array of career summary objects.
    """
    _last_ping[0] = time.time()

    if not _career_provider:
        return jsonify({'error': 'Career mode not available'}), 503

    try:
        careers = _career_provider.get_entry_list()
        logger.info("Served career list: %d careers", len(careers))
        return jsonify(careers)
    except Exception as exc:
        logger.error("Error getting career list: %s", exc, exc_info=True)
        return jsonify({'error': 'Failed to load careers', 'detail': str(exc)}), 500


# ============================================================================
# Career Detail Endpoint
# ============================================================================

@api_bp.route('/api/career/<int:root_career_id>')
def get_career_detail(root_career_id: int):
    """
    Get full career detail for a virtual pilot.

    Response shape is identical to /api/campaign/<name> with additional
    'theatre_chain', 'birth_date', and 'source' fields.

    Args:
        root_career_id: The id of the career chain root (extends = -1).
    """
    _last_ping[0] = time.time()

    if not _career_provider:
        return jsonify({'error': 'Career mode not available'}), 503

    try:
        detail = _career_provider.get_entry_detail(str(root_career_id))
        if detail is None:
            return jsonify({'error': 'Career not found', 'id': root_career_id}), 404
        logger.info("Served career detail: root_id=%d", root_career_id)
        return jsonify(detail)
    except Exception as exc:
        logger.error(
            "Error getting career detail for id=%d: %s", root_career_id, exc, exc_info=True
        )
        return jsonify({'error': 'Failed to load career details', 'detail': str(exc)}), 500


# ============================================================================
# Career Showcase Endpoint
# ============================================================================

@api_bp.route('/api/career/<int:root_career_id>/showcase')
def get_career_showcase(root_career_id: int):
    """
    Medal showcase for a career pilot.

    Currently returns 503 until award translation tables are provided.
    Once event.tpar2 codes are mapped to image filenames, this endpoint
    will delegate to the existing build_showcase_data() function.
    """
    _last_ping[0] = time.time()

    if not _career_provider:
        return jsonify({'error': 'Career mode not available'}), 503

    # Showcase requires award image mapping (event.tpar2 → image filename).
    # Translation table not yet available — return explicit "not yet" response.
    return jsonify({
        'error': 'Career showcase not yet available',
        'reason': 'Award image mapping pending translation table'
    }), 503


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
