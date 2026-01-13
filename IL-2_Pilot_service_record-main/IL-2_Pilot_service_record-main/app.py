import os
import sys
import threading
import time
import webbrowser
import il2_core
from flask import Flask, send_from_directory
from config import load_config, save_config, clear_config, find_il2_installation, get_config_path


# ---- PyInstaller Static Path logic ----
if getattr(sys, 'frozen', False):
    STATIC_ROOT = os.path.join(sys._MEIPASS, "static")
    FROZEN = True
else:
    STATIC_ROOT = os.path.abspath("static")
    FROZEN = False

app = Flask(__name__, static_folder=STATIC_ROOT)
    
CONFIG_PATH = get_config_path()
CONFIG_DIR = os.path.dirname(CONFIG_PATH)
if FROZEN:
    PILOT_PHOTO_DIR = os.path.join(CONFIG_DIR, "pilot_photos")
    CHARACTERSRANKS_DIR = os.path.join(CONFIG_DIR, "charactersranks")
else:
    PILOT_PHOTO_DIR = os.path.join(STATIC_ROOT, "pilot_photos")
    CHARACTERSRANKS_DIR = os.path.join(STATIC_ROOT, "charactersranks")
os.makedirs(PILOT_PHOTO_DIR, exist_ok=True)
os.makedirs(CHARACTERSRANKS_DIR, exist_ok=True)

game_path = load_config()
DB_PATH = None

if game_path:
    print(f"Startup ensure_charactersranks: {game_path}, {CONFIG_DIR}")
    il2_core.ensure_charactersranks(game_path, CONFIG_DIR)
    DB_PATH = os.path.join(game_path, "data", "Career", "cp.db")
    if not os.path.isfile(DB_PATH):
        # If the config.json path is wrong, try auto-locating!
        game_path, DB_PATH = find_il2_installation()
        if DB_PATH and os.path.isfile(DB_PATH):
            save_config(game_path)
        else:
            game_path = None
            DB_PATH = None
else:
    game_path, DB_PATH = find_il2_installation()
    if DB_PATH and os.path.isfile(DB_PATH):
        save_config(game_path)
    else:
        game_path = None
        DB_PATH = None

# Make these available to blueprints
app.config["DB_PATH"] = DB_PATH
app.config["STATIC_ROOT"] = STATIC_ROOT
app.config["PILOT_PHOTO_DIR"] = PILOT_PHOTO_DIR
app.config["FROZEN"] = FROZEN
app.config["GAME_PATH"] = game_path
app.config["CONFIG_DIR"] = CONFIG_DIR
app.config["CHARACTERSRANKS_DIR"] = CHARACTERSRANKS_DIR

# ----- Register API blueprint AFTER everything else -----
from routes import api_bp, last_ping
app.register_blueprint(api_bp)

# --- Add custom static route for charactersranks (FROZEN only!) ---
if FROZEN:
    @app.route('/charactersranks/<path:filename>')
    def serve_charactersranks(filename):
        charactersranks_dir = os.path.join(CONFIG_DIR, "charactersranks")
        return send_from_directory(charactersranks_dir, filename)

@app.route("/")
def index():
    return send_from_directory(STATIC_ROOT, 'index.html')

@app.route('/static/<path:path>')
def serve_static(path):
    return send_from_directory(STATIC_ROOT, path)

if FROZEN:
    @app.route('/pilot_photos/<path:filename>')
    def serve_pilot_photo(filename):
        return send_from_directory(PILOT_PHOTO_DIR, filename)

def ping_monitor():
    while True:
        time.sleep(5)
        if time.time() - last_ping[0] > 60:
            print("No activity detected for 60s. Exiting Flask app.")
            os._exit(0)
            
def open_browser():
    time.sleep(1)
    webbrowser.open("http://127.0.0.1:5000/")

if __name__ == "__main__":
    threading.Thread(target=open_browser, daemon=True).start()
    threading.Thread(target=ping_monitor, daemon=True).start()
    app.run(debug=False)
