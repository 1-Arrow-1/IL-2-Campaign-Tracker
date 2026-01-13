import os
import re
import hashlib
import shutil

def ensure_charactersranks(mod_src, dest_dir):

    print(f"[ensure_charactersranks] Called with mod_src={mod_src}, dest_dir={dest_dir}")

    if not os.path.isdir(mod_src):
        print("ERROR: Mod source folder does not exist!")
        return False

    mod_sample = os.path.join(mod_src, "101000", "big.png")
    if not os.path.exists(mod_sample):
        print("ERROR: Mod files (101000/big.png) not found in mod_src.")
        return False

    user_sample = os.path.join(dest_dir, "101000", "big.png")
    if os.path.exists(user_sample):
        print("INFO: charactersranks already present in dest_dir. No copy performed.")
        return True

    if os.path.exists(dest_dir):
        try:
            shutil.rmtree(dest_dir)
        except Exception as e:
            print(f"ERROR: Could not remove old dest_dir: {e}")
            return False

    try:
        shutil.copytree(mod_src, dest_dir)
        print("SUCCESS: Copied modded charactersranks to dest_dir.")
        return True
    except Exception as e:
        print(f"ERROR: Failed to copy charactersranks: {e}")
        return False



        
def extract_country_id(description):
    match = re.search(r'birthCountryInfo=(\d+)', description)
    return int(match.group(1)) if match else None

def extract_fullname(description):
    m = re.search(r'fullname=([^&]+)', description)
    return m.group(1).replace('%20', ' ') if m else "Unknown"

def extract_birthdate(description):
    m = re.search(r'birthDate=([\d\.]+)', description)
    if m:
        dt = m.group(1)
        parts = dt.split('.')
        if len(parts) >= 3:
            return f"{parts[2]}.{parts[1]}.{parts[0]}"
        else:
            return dt
    return ""

def get_latest_pilot(conn, desc):
    cur = conn.cursor()
    cur.execute(
        "SELECT id, squadronId, insDate FROM pilot WHERE description=? ORDER BY insDate DESC LIMIT 1",
        (desc,)
    )
    row = cur.fetchone()
    return row  # (id, squadronId, insDate) or None
    
def collect_career_chain(conn, starting_career_id):
    """Traverse both up and down the chain, collecting all related career ids."""
    # Traverse up to find the root
    cur = conn.cursor()
    chain = set()
    current = starting_career_id
    while True:
        chain.add(current)
        cur.execute("SELECT extends FROM career WHERE id=?", (current,))
        row = cur.fetchone()
        if row and row[0] != -1:
            current = row[0]
        else:
            break

    # Traverse down (find all who extend any in the chain)
    added = True
    while added:
        added = False
        cur.execute("SELECT id, extends FROM career")
        for row in cur.fetchall():
            id_, ext = row
            if ext in chain and id_ not in chain:
                chain.add(id_)
                added = True
    return list(chain)

def get_squadron_shortname(squadron_id, conn, STATIC_ROOT):
    if not squadron_id:
        return "Unknown"
    cur = conn.cursor()
    cur.execute("SELECT configId FROM squadron WHERE id=?", (squadron_id,))
    row = cur.fetchone()
    if not row:
        return "Unknown"
    configId = row[0]
    folder = os.path.join(STATIC_ROOT, "squadrons", str(configId))
    info_file = os.path.join(folder, "info.locale=eng.txt")
    if not os.path.isfile(info_file):
        return "Unknown"
    with open(info_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("*"):
                parts = line.strip('|').split(',')
                if len(parts) >= 3:
                    shortname = parts[-1].strip().strip('"')
                    return shortname
                if "|" in line:
                    last_field = line.split('|')[0]
                    fields = last_field.split(',')
                    if len(fields) >= 3:
                        return fields[-1].strip().strip('"')
    return "Unknown"


def get_award_name_static(tpar2, STATIC_ROOT):
    info_path = os.path.join(STATIC_ROOT, 'achievements', str(tpar2), 'info.locale=eng.txt')
    if not os.path.isfile(info_path):
        return tpar2  # fallback, just the code
    try:
        with open(info_path, encoding='utf-8') as f:
            for line in f:
                if '&name=' in line:
                    match = re.search(r'&name\s*=\s*"([^"]+)"', line)
                    if match:
                        return match.group(1)
        return tpar2
    except Exception:
        return tpar2

def get_rank_name(country, rank_id, STATIC_ROOT, game_path=None, CHARACTERSRANKS_DIR=None):
    folder = str(country * 1000 + rank_id)
    info_filename = "info.locale=eng.txt"
    paths_to_try = []
    if CHARACTERSRANKS_DIR:
        mod_path = os.path.join(CHARACTERSRANKS_DIR, folder, info_filename)
        paths_to_try.append(mod_path)
    standard_static_path = os.path.join(STATIC_ROOT, "standard_charactersranks", folder, info_filename)
    paths_to_try.append(standard_static_path)
    for info_path in paths_to_try:
        if os.path.isfile(info_path):
            with open(info_path, encoding="utf-8") as f:
                for line in f:
                    if "&name=" in line:
                        match = re.search(r'&name\s*=\s*"([^"]+)"', line)
                        if match:
                            return match.group(1)
    return f"Rank {rank_id}"



def get_photo_path_for_desc(desc, PILOT_PHOTO_DIR, frozen):
    import hashlib, os
    pilot_hash = hashlib.sha256(desc.encode('utf-8')).hexdigest()[:20]
    img_path_fs = os.path.join(PILOT_PHOTO_DIR, f"{pilot_hash}.png")
    if os.path.exists(img_path_fs):
        if frozen:
            return f"/pilot_photos/{pilot_hash}.png"
        else:
            return f"/static/pilot_photos/{pilot_hash}.png"
    return "/static/images/sample_photo.jpg"
    
def find_chain_tip(conn, chain_ids):
    cur = conn.cursor()
    cur.execute("SELECT extends FROM career WHERE extends != -1")
    all_extends = set(row[0] for row in cur.fetchall())
    # The tip is a chain id that is not extended by anyone else
    tips = [cid for cid in chain_ids if cid not in all_extends]
    # Normally only one, but if not, pick the highest (latest)
    return tips[-1] if tips else chain_ids[0]
    
def get_rank_image_path(country, rank_id, date_str, STATIC_ROOT, CHARACTERSRANKS_DIR=None, FROZEN=False):
    folder = str(country * 1000 + rank_id)
    filename = "big.png"
    # Soviet 1943+ special logic
    if country == 101 and date_str:
        try:
            from datetime import datetime
            dt = datetime.strptime(date_str, "%Y.%m.%d")
            if dt >= datetime(1943, 1, 1):
                filename = "big.1943.png"
        except Exception:
            pass
    elif country == 103:
        filename = "medium.png"
        
    img_subpath = f"{folder}/{filename}"

    if CHARACTERSRANKS_DIR:
        mod_path = os.path.join(CHARACTERSRANKS_DIR, folder, filename)
        if os.path.exists(mod_path):
            if FROZEN:
                return f"/charactersranks/{img_subpath}"
            else:
                return f"/static/charactersranks/{img_subpath}"

    # Fallback to vanilla/standard_charactersranks
    vanilla_path = os.path.join(STATIC_ROOT, "standard_charactersranks", folder, filename)
    if os.path.exists(vanilla_path):
        return f"/static/standard_charactersranks/{img_subpath}"

    # Placeholder
    return "/static/images/award_placeholder.png"


def clear_config(CONFIG_PATH):
    try:
        if os.path.exists(CONFIG_PATH):
            os.remove(CONFIG_PATH)
    except Exception:
        pass