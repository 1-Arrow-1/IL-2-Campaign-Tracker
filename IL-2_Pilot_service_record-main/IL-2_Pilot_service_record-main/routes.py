import os
import sqlite3
import re
import base64
import hashlib
import time
import signal
from collections import OrderedDict
from flask import Blueprint, jsonify, request, current_app, Response
import json
import il2_core
from config import save_config, clear_config

api_bp = Blueprint("api", __name__)

# Use your *display order* in friendly_label form (see note below)
stat_order_labels = [
    "Flight Time", "Good Sorties", "Sorties", "Success Rate",
    "Light Fighter", "Light Attack Plane", "Light Bomber", "Light Recon", "Light Transport",
    "Medium Fighter", "Medium Attack Plane", "Medium Bomber", "Medium Recon", "Medium Transport",
    "Heavy Fighter", "Heavy Attack Plane", "Heavy Bomber", "Heavy Recon", "Heavy Transport",
    "Heavy Armoured", "Heavy Tank", "Medium Tank", "Vehicle", "Light Tank", "Armoured Vehicle",
    "Truck", "Car", "Train Locomotive", "Train Vagon", "Howitzer", "Field Gun",
    "Naval Gun", "Rocket Launcher", "Machine Gun", "Searchlight", "Static Plane",
    "Air Defence", "Heavy Flak", "Light Flak", "AAA Machine Gun", "Ships",
    "Light Ship", "Destroyer Ship", "Submarine", "Large Cargo Ship", "Building",
    "Rural Yard", "Town Building", "Factory Building", "Railway Station Facility", "Bridge",
    "Airfield Facility", "Air Crew", "Pilot", "Plane Gunner", "Driver", "Vehicle Gunner",
    "Infantry", "Turrets", "Plane Turrets", "Vehicle Turrets", "Plane In Group", "Assist"
]

@api_bp.route("/api/set_game_path", methods=["POST"])
def set_game_path():
    print("set_game_path route CALLED!")
    user_path = request.json.get("game_path", "").strip()
    if not user_path:
        return {"error": "No path provided"}, 400
    db_candidate = os.path.join(user_path, "data", "Career", "cp.db")
    if not os.path.isfile(db_candidate):
        return {"error": "cp.db not found in the provided path"}, 404

    # Save config and update app config
    current_app.config["GAME_PATH"] = user_path
    current_app.config["DB_PATH"] = db_candidate
    save_config(user_path)

    # Where to copy/read charactersranks
    FROZEN = current_app.config["FROZEN"]
    if FROZEN:
        CHARACTERSRANKS_DIR = os.path.join(
            os.path.dirname(current_app.config["PILOT_PHOTO_DIR"]), "charactersranks"
        )
    else:
        CHARACTERSRANKS_DIR = os.path.join(current_app.config["STATIC_ROOT"], "charactersranks")
    os.makedirs(CHARACTERSRANKS_DIR, exist_ok=True)

    # Only copy if mod folder exists, else skip
    mod_src = os.path.join(user_path, "data", "swf", "il2", "charactersranks")
    if os.path.isdir(mod_src):
        print(f"Calling ensure_charactersranks with: {mod_src}, {CHARACTERSRANKS_DIR}")
        il2_core.ensure_charactersranks(mod_src, CHARACTERSRANKS_DIR)
    else:
        print("No modded charactersranks found. Fallback to standard_charactersranks only.")
    current_app.config["CHARACTERSRANKS_DIR"] = CHARACTERSRANKS_DIR

    return {"ok": True, "game_path": user_path, "db_path": db_candidate}



@api_bp.route("/api/save_photo", methods=["POST"])
def save_photo():
    desc = request.form.get("desc")
    if not desc:
        return {"error": "No pilot description"}, 400
    img_data = request.form.get("img_data")
    if not img_data:
        return {"error": "No image data"}, 400
    img_str = re.sub(r"^data:image/\w+;base64,", "", img_data)
    img_bytes = base64.b64decode(img_str)
    pilot_hash = hashlib.sha256(desc.encode("utf-8")).hexdigest()[:20]
    PILOT_PHOTO_DIR = current_app.config["PILOT_PHOTO_DIR"]
    frozen = current_app.config["FROZEN"]
    img_path = os.path.join(PILOT_PHOTO_DIR, f"{pilot_hash}.png")
    with open(img_path, "wb") as f:
        f.write(img_bytes)
    if frozen:
        return {"path": f"/pilot_photos/{pilot_hash}.png"}
    return {"path": f"/static/pilot_photos/{pilot_hash}.png"}


@api_bp.route("/api/pilots")
def api_pilots():
    DB_PATH = current_app.config["DB_PATH"]
    STATIC_ROOT = current_app.config["STATIC_ROOT"]
    if not DB_PATH or not os.path.isfile(DB_PATH):
        clear_config()
        return jsonify({"error": "IL-2 not found. Please provide the correct game path."}), 400

    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, playerId FROM career WHERE extends = -1")
        roots = cur.fetchall()

        country_map = {
            101: "Soviet Union",
            102: "Great Britain",
            103: "United States of America",
            201: "Germany"
        }

        pilots = []
        for root_id, player_id in roots:
            career_chain = il2_core.collect_career_chain(conn, root_id)
            tip_career_id = il2_core.find_chain_tip(conn, career_chain)
            cur.execute("SELECT playerId FROM career WHERE id = ?", (tip_career_id,))
            row = cur.fetchone()
            if not row:
                continue
            tip_pilot_id = row[0]
            cur.execute("SELECT description, squadronId FROM pilot WHERE id = ?", (tip_pilot_id,))
            row = cur.fetchone()
            if not row:
                continue
            desc, squadronId = row
            name = il2_core.extract_fullname(desc)
            country_id = il2_core.extract_country_id(desc)
            country_name = country_map.get(country_id, "Unknown")
            squadron_short = il2_core.get_squadron_shortname(
                squadronId, conn, STATIC_ROOT
            ) if squadronId else "Unknown"
            pilots.append({
                "desc": desc,
                "display": name,
                "country": country_name,
                "squadron": squadron_short,
                "pilot_id": tip_pilot_id,
                "root_career_id": root_id
            })
        return jsonify(pilots)
    finally:
        conn.close()


@api_bp.route("/api/service_record")
def api_service_record():
    DB_PATH = current_app.config["DB_PATH"]
    PILOT_PHOTO_DIR = current_app.config["PILOT_PHOTO_DIR"]
    STATIC_ROOT = current_app.config["STATIC_ROOT"]
    frozen = current_app.config["FROZEN"]
    game_path = current_app.config.get("GAME_PATH")
    if frozen:
        CHARACTERSRANKS_DIR = os.path.join(
            os.path.dirname(PILOT_PHOTO_DIR), "charactersranks"
        )
    else:
        CHARACTERSRANKS_DIR = os.path.join(STATIC_ROOT, "charactersranks")
    current_app.config["CHARACTERSRANKS_DIR"] = CHARACTERSRANKS_DIR

    if not DB_PATH or not os.path.isfile(DB_PATH):
        return jsonify({"error": "IL-2 not found. Please provide the correct game path."}), 400

    desc = request.args.get("desc")
    if not desc:
        return jsonify({"error": "Missing desc"}), 400
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id FROM pilot WHERE description = ?", (desc,))
    row = cur.fetchone()
    if not row:
        return jsonify({"error": "Pilot not found"}), 404
    pilot_id = row[0]
    cur.execute("SELECT id FROM career WHERE playerId = ?", (pilot_id,))
    row = cur.fetchone()
    if not row:
        return jsonify({"error": "Career not found"}), 404
    starting_career_id = row[0]
    career_chain = il2_core.collect_career_chain(conn, starting_career_id)
    pilot_ids = []
    for cid in career_chain:
        cur.execute("SELECT playerId FROM career WHERE id=?", (cid,))
        prow = cur.fetchone()
        if prow:
            pilot_ids.append(prow[0])

    tip_career_id = il2_core.find_chain_tip(conn, career_chain)
    cur.execute("SELECT playerId FROM career WHERE id = ?", (tip_career_id,))
    row = cur.fetchone()
    if not row:
        return jsonify({"error": "Career not found"}), 404
    latest_pilot_id = row[0]
    cur.execute("SELECT description, squadronId FROM pilot WHERE id = ?", (latest_pilot_id,))
    row = cur.fetchone()
    if not row:
        return jsonify({"error": "Pilot not found"}), 404
    desc, squadron_id = row
    name = il2_core.extract_fullname(desc)
    name_parts = name.split(' ', 1)
    first_name = name_parts[0]
    last_name = name_parts[1] if len(name_parts) > 1 else ""
    birthdate = il2_core.extract_birthdate(desc)
    country_id = il2_core.extract_country_id(desc)
    country_map = {
        101: "Soviet Union",
        102: "Great Britain",
        103: "United States of America",
        201: "Germany"
    }
    country_name = country_map.get(country_id, "Unknown")
    squadron_short = il2_core.get_squadron_shortname(
        squadron_id, conn, STATIC_ROOT
    ) if squadron_id else "Unknown"

    cur.execute("SELECT rankId FROM pilot WHERE id = ?", (latest_pilot_id,))
    rank_row = cur.fetchone()
    if rank_row:
        current_rank_id = rank_row[0]
        rank_name = il2_core.get_rank_name(
            country_id, current_rank_id, STATIC_ROOT, game_path, CHARACTERSRANKS_DIR
        )
    else:
        current_rank_id = None
        rank_name = "Unknown"

    ids_qs = ",".join(str(i) for i in pilot_ids)
    query = f"""SELECT date, type, rankId, tpar2, squadronId FROM event WHERE type IN (6,8) AND pilotId IN ({ids_qs}) ORDER BY date ASC"""
    cur.execute(query)
    promotions, awards = [], []
    for date, etype, rank_id, tpar2, squadron_id in cur.fetchall():
        d = date.split()[0] if date else ""
        dt_parts = d.split('.')
        if len(dt_parts) == 3:
            dt_formatted = f"{dt_parts[2]}.{dt_parts[1]}.{dt_parts[0]}"
            date_for_check = f"{dt_parts[0]}.{dt_parts[1]}.{dt_parts[2]}"
        else:
            dt_formatted = d
            date_for_check = d
        if etype == 6:
            rname = il2_core.get_rank_name(
                country_id, rank_id, STATIC_ROOT, game_path, CHARACTERSRANKS_DIR
            )
            rimg = il2_core.get_rank_image_path(
                country_id, rank_id, date_for_check, STATIC_ROOT, CHARACTERSRANKS_DIR
                
            )
            promotions.append({"desc": rname, "date": dt_formatted, "img": rimg})
        elif etype == 8:
            aname = il2_core.get_award_name_static(tpar2, STATIC_ROOT)
            if "rubles" in aname.lower():
                continue
            awards.append({"desc": aname, "date": dt_formatted, "tpar2": tpar2})

    photo_url = il2_core.get_photo_path_for_desc(desc, PILOT_PHOTO_DIR, frozen)
    return jsonify({
        "pilot_info": {
            "full_name": name,
            "first_name": first_name,
            "last_name": last_name,
            "birth_date": birthdate,
            "birth_country": country_name,
            "pilot_id": latest_pilot_id,
            "squadron": squadron_short,
            "rank_name": rank_name,
            "photo_url": photo_url
        },
        "promotions": promotions,
        "awards": awards
    })


@api_bp.route("/api/pilot_stats")
def api_pilot_stats():
    DB_PATH = current_app.config["DB_PATH"]
    if not DB_PATH or not os.path.isfile(DB_PATH):
        return jsonify({"error": "IL-2 not found. Please provide the correct game path."}), 400

    desc = request.args.get('desc')
    if not desc:
        return jsonify({"error": "Missing desc"}), 400
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id FROM pilot WHERE description = ?", (desc,))
    row = cur.fetchone()
    if not row:
        return jsonify({"error": "Pilot not found"}), 404
    pilot_id = row[0]
    cur.execute("SELECT id FROM career WHERE playerId = ?", (pilot_id,))
    row = cur.fetchone()
    if not row:
        return jsonify({"error": "Career not found"}), 404
    starting_career_id = row[0]
    career_chain = il2_core.collect_career_chain(conn, starting_career_id)
    tip_career_id = il2_core.find_chain_tip(conn, career_chain)
    cur.execute("SELECT playerId FROM career WHERE id = ?", (tip_career_id,))
    row = cur.fetchone()
    if not row:
        return jsonify({"error": "Career not found"}), 404
    latest_pilot_id = row[0]
    cur.execute("PRAGMA table_info(pilot)")
    columns = [row[1] for row in cur.fetchall()]
    cur.execute(f"SELECT * FROM pilot WHERE id = ?", (latest_pilot_id,))
    pilot_row = cur.fetchone()
    stats = dict(zip(columns, pilot_row))

    # Your field skip list as before
    skip_fields = {
        'description', 'id', 'name', 'lastName', 'personageId', 'avatarPath', 'birthDay',
        'isDeleted', 'penalty', 'penaltyPot', 'pcp', 'squadronId', 'rankId', 'state',
        'stateDate', 'statePeriod', 'trainPot', 'vehPot', 'shipPot', 'buildingPot', 'score',
        'transferProb', 'wounded', 'nickname', 'deathDate', 'bioInfo', 'startDate',
        'playerCountryId', 'startSquadronInfo', 'virtualSquadronId', 'playerPremiumStatus',
        'startRankInfo', 'careerStartDate', 'insDate', 'killLightPlane', 'killMediumPlane',
        'killHeavyPlane', 'sorties', 'goodSorties', 'success_rate'
    }

    def friendly_label(field):
        if field.lower().startswith('kill'):
            field = field[4:]
        field = re.sub(r'([A-Z]{2,})([A-Z][a-z])', r'\1 \2', field)
        field = re.sub(r'(?<=[a-z])([A-Z])', r' \1', field)
        words = field.split()
        new_words = [w if w.isupper() and len(w) > 1 else w.capitalize() for w in words]
        return ' '.join(new_words)

    # Build mapping from display label to value (skipping skip_fields)
    label_value_map = {}
    for col in columns:
        if col in skip_fields:
            continue
        val = stats.get(col)
        if val is None or (isinstance(val, (int, float)) and val == 0):
            continue
        label = friendly_label(col)
        label_value_map[label] = val

    # Always show these 3 at the top, exactly as in your display order
    output = OrderedDict()
    # Flight Time (special formatting)
    if 'flightTime' in stats and stats.get('flightTime'):
        t = stats['flightTime']
        output["Flight Time"] = f"{int((t // 3600))}h {int((t % 3600) // 60)}m"
    # Good Sorties
    output["Good Sorties"] = stats.get('goodSorties', 0)
    # Sorties
    output["Sorties"] = stats.get('sorties', 0)
    # Success Rate
    sorties = stats.get('sorties') or 0
    good = stats.get('goodSorties') or 0
    output["Success Rate"] = f"{(good / sorties * 100):.1f}%" if sorties else "0.0%"

    # Use your *display order* (friendly_label form) and fill from label_value_map
    for label in stat_order_labels:
        if label in output:
            continue  # already added above
        if label in label_value_map:
            output[label] = label_value_map[label]

    # (Optional) Add any remaining items (shouldn't be needed, but for completeness)
    for label in label_value_map:
        if label not in output:
            output[label] = label_value_map[label]

    return Response(
        json.dumps(output, ensure_ascii=False, sort_keys=False),
        mimetype="application/json"
    )

@api_bp.route("/api/pilot_sorties")
def api_pilot_sorties():
    DB_PATH = current_app.config["DB_PATH"]
    desc = request.args.get("desc")
    if not desc:
        return jsonify({"error": "Missing desc"}), 400

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Pilot + career resolution
    cur.execute("SELECT id FROM pilot WHERE description = ?", (desc,))
    row = cur.fetchone()
    if not row:
        return jsonify({"error": "Pilot not found"}), 404
    pilot_id = row["id"] if "id" in row.keys() else row[0]

    cur.execute("SELECT id FROM career WHERE playerId = ?", (pilot_id,))
    row = cur.fetchone()
    if not row:
        return jsonify({"error": "Career not found"}), 404
    root_career_id = row["id"] if "id" in row.keys() else row[0]

    career_chain = il2_core.collect_career_chain(conn, root_career_id)
    pilot_ids = []
    for cid in career_chain:
        cur.execute("SELECT playerId FROM career WHERE id = ?", (cid,))
        prow = cur.fetchone()
        if prow:
            pilot_ids.append(prow["playerId"] if "playerId" in prow.keys() else prow[0])

    if not pilot_ids:
        return jsonify([])

    # Inspect schema for sortie table
    cur.execute("PRAGMA table_info(sortie);")
    cols_info = cur.fetchall()
    col_names = [c[1] for c in cols_info]

    def exists(cols):
        return [c for c in cols if c in col_names]

    air_kill_cols = exists(["killLightPlane", "killMediumPlane", "killHeavyPlane"])
    ground_kill_cols = exists([
        'killHeavyTank', 'killMediumTank', 'killVehicle', 'killLightTank', 'killArmouredVehicle',
        'killTruck', 'killCar'
    ])
    artillery_kills_cols = exists([
        'killHowitzer', 'killFieldGun', 'killNavalGun', 'killRocketLauncher',
        'killHeavyFlak', 'killLightFlak', 'killAAAMachineGun'
    ])
    naval_kill_cols = exists(['killLightShip', 'killDestroyerShip', 'killSubmarine', 'killLargeCargoShip'])
    railway_kills_cols = exists(['killTrainLocomotive', 'killTrainVagon'])
    structure_kills_cols = exists([
        'killRuralYard', 'killTownBuilding', 'killFactoryBuilding',
        'killRailwayStationFacility', 'killBridge', 'killAirfieldFacility'
    ])

    bucket_columns = (
        air_kill_cols + ground_kill_cols + naval_kill_cols +
        artillery_kills_cols + railway_kills_cols + structure_kills_cols
    )

    select_fields = ["date", "model", "missionId"] + bucket_columns + ["flightTime"]

    qmarks = ",".join(["?"] * len(pilot_ids))
    query = f"""
        SELECT {', '.join(select_fields)}
        FROM sortie
        WHERE pilotId IN ({qmarks})
        ORDER BY date ASC
    """

    try:
        cur.execute(query, pilot_ids)
    except sqlite3.OperationalError as e:
        current_app.logger.warning("Sorties query failed: %s", e)
        return jsonify([])

    def extract_plane_name(raw_model: str) -> str:
        if not raw_model:
            return ""
        try:
            base = raw_model.split("/")[-1]
            name = base.replace(".txt", "")
            return name.upper()
        except Exception:
            return raw_model.upper()

    def normalize_mtemplate(template: str) -> str:
        if not template:
            return ""
        if '@' in template:
            template = template.split('@', 1)[0]
        else:
            idx = template.find('_p0')
            if idx != -1:
                template = template[:idx]
        template = template.replace('-', ' ').replace('_', ' ').strip()
        return " ".join(word.capitalize() for word in template.split())

    sorties = []
    for row in cur.fetchall():
        idx = 0
        date = row[idx]; idx += 1
        raw_model = row[idx]; idx += 1
        mission_id = row[idx]; idx += 1

        bucket_vals = row[idx: idx + len(bucket_columns)]
        bucket_map = dict(zip(bucket_columns, bucket_vals))
        idx += len(bucket_columns)

        flight_time = row[idx] if idx < len(row) else None

        # Aggregate kills
        air_kills = sum(bucket_map.get(c, 0) or 0 for c in air_kill_cols)
        ground_kills = sum(bucket_map.get(c, 0) or 0 for c in ground_kill_cols)
        naval_kills = sum(bucket_map.get(c, 0) or 0 for c in naval_kill_cols)
        artillery_kills = sum(bucket_map.get(c, 0) or 0 for c in artillery_kills_cols)
        railway_kills = sum(bucket_map.get(c, 0) or 0 for c in railway_kills_cols)
        structure_kills = sum(bucket_map.get(c, 0) or 0 for c in structure_kills_cols)

        # Mission type normalization
        mission_type = ""
        if mission_id is not None:
            cur.execute("SELECT mTemplate FROM mission WHERE id = ?", (mission_id,))
            mrow = cur.fetchone()
            if mrow:
                template = mrow["mTemplate"] if "mTemplate" in mrow.keys() else mrow[0]
                mission_type = normalize_mtemplate(template)

        # Build sortie dict with separate kill fields
        sortie = {
            "date": date,
            "aircraft": extract_plane_name(raw_model),
            "mission_type": mission_type,
            "air_kills": air_kills,
            "ground_kills": ground_kills,
            "naval_kills": naval_kills,
            "artillery_kills": artillery_kills,
            "railway_kills": railway_kills,
            "structure_kills": structure_kills,
        }

        # Flight time formatting
        if flight_time is not None:
            hours = int(flight_time // 3600)
            minutes = int((flight_time % 3600) // 60)
            if hours > 0 and minutes > 0:
                sortie["flight_time"] = f"{hours}h {minutes}m"
            elif hours > 0:
                sortie["flight_time"] = f"{hours}h"
            else:
                sortie["flight_time"] = f"{minutes}m"
        else:
            sortie["flight_time"] = ""

        sorties.append(sortie)

    return jsonify(sorties)







# --- API: Ping to keep server alive (for auto-exit) ---
last_ping = [time.time()]

@api_bp.route('/api/ping', methods=['POST'])
def ping():
    last_ping[0] = time.time()
    print("Ping received at", time.strftime("%H:%M:%S"))
    return {'ok': True}


# --- API: Shutdown server ---
@api_bp.route('/shutdown', methods=['POST'])
def shutdown():
    shutdown_func = request.environ.get('werkzeug.server.shutdown')
    if shutdown_func:
        shutdown_func()
    else:
        os.kill(os.getpid(), signal.SIGTERM)
    return 'Server shutting down...'
