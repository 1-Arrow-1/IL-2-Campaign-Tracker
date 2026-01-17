"""
IL-2 Campaign Service Record - Flask Application

Entry point for the application.
Handles:
- Flask setup and configuration
- Static file serving
- Browser auto-open
- Idle shutdown monitoring
"""

import os
import sys
import time
import logging
import threading
import webbrowser
from pathlib import Path
from flask import Flask, send_from_directory

# Import configuration
from config import get_config

# Import API
from api import api_bp, init_api


# ============================================================================
# Logging Setup
# ============================================================================

def setup_logging(debug: bool = False):
    """Setup application logging."""
    level = logging.DEBUG if debug else logging.INFO
    
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Reduce Flask's verbose logging
    if not debug:
        logging.getLogger('werkzeug').setLevel(logging.WARNING)


logger = logging.getLogger(__name__)


# ============================================================================
# Flask Application Factory
# ============================================================================

def create_app():
    """
    Create and configure Flask application.
    
    Returns:
        Configured Flask app
    """
    # Get configuration
    config = get_config()
    
    # Setup logging
    setup_logging(debug=config.debug)
    
    # Validate configuration
    is_valid, error = config.validate()
    if not is_valid:
        logger.error(f"Configuration error: {error}")
        sys.exit(1)
    
    logger.info(f"Configuration: {config}")

    # Ensure persistent directories exist
    config.user_data_dir.mkdir(parents=True, exist_ok=True)
    config.pilot_photo_dir.mkdir(parents=True, exist_ok=True)
    
    # Create Flask app with NO static_folder (we handle it manually)
    app = Flask(__name__, static_folder=None, static_url_path=None)
    
    # Configure Flask
    app.config['SECRET_KEY'] = 'campaign-service-record-secret'
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0  # Disable caching in dev mode
    app.config['PILOT_PHOTO_DIR'] = config.pilot_photo_dir
    app.config['PERSONAL_DATA_DIR'] = config.user_data_dir
    app.config['FROZEN'] = config.frozen
    
    # Initialize API
    init_api(config.data_dir, config.data_dir / 'reports')
    
    # Register blueprints
    app.register_blueprint(api_bp)
    
    # ========================================================================
    # Routes
    # ========================================================================
    
    @app.route('/')
    def index():
        """Serve main HTML page."""
        return send_from_directory(config.static_dir, 'index.html')
    
    @app.route('/static/<path:path>')
    def serve_static(path):
        """Serve static files."""
        static_file = config.static_dir / path
        logger.debug(f"Static file request: {path} -> {static_file}")
        
        if not static_file.exists():
            logger.error(f"Static file not found: {static_file}")
            return f"File not found: {path}", 404
        
        return send_from_directory(config.static_dir, path)

    @app.route('/static/locales/<path:filename>')
    def serve_static_locales(filename):
        """Serve locale JSON files from the static namespace."""
        candidate_dirs = [
            config.base_dir / 'locales',
            config.base_dir.parent / 'locales'
        ]
        for locales_dir in candidate_dirs:
            locale_path = locales_dir / filename
            if locale_path.exists():
                return send_from_directory(locales_dir, filename)
        return f"Locale not found: {filename}", 404

    @app.route('/locales/<path:filename>')
    def serve_locales(filename):
        """Serve locale JSON files."""
        candidate_dirs = [
            config.base_dir / 'locales',
            config.base_dir.parent / 'locales'
        ]
        for locales_dir in candidate_dirs:
            locale_path = locales_dir / filename
            if locale_path.exists():
                return send_from_directory(locales_dir, filename)
        return f"Locale not found: {filename}", 404
    
    if config.frozen:
        # In frozen mode, serve reports from data directory
        @app.route('/reports/<path:filename>')
        def serve_report(filename):
            """Serve PDF reports."""
            reports_dir = config.data_dir / 'reports'
            return send_from_directory(reports_dir, filename)

        @app.route('/pilot_photos/<path:filename>')
        def serve_pilot_photo(filename):
            """Serve pilot photos from user data directory."""
            return send_from_directory(config.pilot_photo_dir, filename)
    
    @app.route('/favicon.ico')
    def favicon():
        """Serve favicon (if exists)."""
        favicon_path = config.static_dir / 'favicon.ico'
        if favicon_path.exists():
            return send_from_directory(config.static_dir, 'favicon.ico')
        else:
            return '', 204  # No content
    
    return app


# ============================================================================
# Browser Auto-Open
# ============================================================================

def open_browser(url: str, delay: float = 1.5):
    """
    Open browser after delay.
    
    Args:
        url: URL to open
        delay: Delay before opening (seconds)
    """
    time.sleep(delay)
    logger.info(f"Opening browser: {url}")
    webbrowser.open(url)


# ============================================================================
# Idle Shutdown Monitor
# ============================================================================

def monitor_idle_shutdown(idle_timeout: int):
    """
    Monitor for idle timeout and shutdown server.
    
    Args:
        idle_timeout: Timeout in seconds
    """
    from api.routes import get_last_ping
    
    logger.info(f"Idle shutdown monitor started (timeout={idle_timeout}s)")
    
    while True:
        time.sleep(5)  # Check every 5 seconds
        
        last_ping = get_last_ping()
        idle_time = time.time() - last_ping
        
        if idle_time > idle_timeout:
            logger.info(f"Idle timeout reached ({idle_time:.0f}s). Shutting down...")
            os._exit(0)


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    """Main entry point."""
    # Create app
    app = create_app()
    
    # Get config
    config = get_config()
    
    # Construct URL
    url = f"http://{config.host}:{config.port}"
    
    # Start browser opener thread
    if config.auto_open_browser:
        browser_thread = threading.Thread(
            target=open_browser,
            args=(url,),
            daemon=True
        )
        browser_thread.start()
    
    # Start idle shutdown monitor
    if config.shutdown_on_idle:
        monitor_thread = threading.Thread(
            target=monitor_idle_shutdown,
            args=(config.idle_timeout_seconds,),
            daemon=True
        )
        monitor_thread.start()
    
    # Print startup message
    print("\n" + "="*70)
    print("  IL-2 Campaign Service Record")
    print("="*70)
    print(f"\n  Server running at: {url}")
    print(f"  Data directory: {config.data_dir}")
    
    if config.auto_open_browser:
        print(f"\n  Browser will open automatically...")
    else:
        print(f"\n  Open your browser and navigate to: {url}")
    
    if config.shutdown_on_idle:
        print(f"  Server will shutdown after {config.idle_timeout_seconds}s of inactivity")
    
    print("\n" + "="*70 + "\n")
    
    # Run Flask
    try:
        app.run(
            host=config.host,
            port=config.port,
            debug=config.debug,
            use_reloader=False  # Disable reloader (causes issues with threads)
        )
    except KeyboardInterrupt:
        logger.info("Shutdown requested by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
