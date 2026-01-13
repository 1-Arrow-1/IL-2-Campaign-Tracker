import os
import json
import string

def get_config_path():
    base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
    folder = os.path.join(base, ".il2_pilot_passport")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "config.json")

def load_config():
    config_path = get_config_path()
    if os.path.isfile(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("game_path", "")
    return ""

def save_config(game_path):
    config_path = get_config_path()
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump({"game_path": game_path}, f)

def clear_config():
    config_path = get_config_path()
    try:
        os.remove(config_path)
    except Exception:
        pass


def find_il2_installation():
    """Attempt to locate the IL-2 installation directory and database."""
    search_paths = [
        r"Program Files (x86)\1C Game Studios\IL-2 Sturmovik Battle of Stalingrad",
        r"Program Files (x86)\Steam\steamapps\common\IL-2 Sturmovik Battle of Stalingrad",
        r"Games\IL-2 Sturmovik Battle of Stalingrad",
    ]
    for drive in string.ascii_uppercase:
        for rel_path in search_paths:
            abs_path = f"{drive}:\\{rel_path}"
            if os.path.isdir(abs_path):
                db_candidate = os.path.join(abs_path, "data", "Career", "cp.db")
                if os.path.isfile(db_candidate):
                    return abs_path, db_candidate
    return None, None

