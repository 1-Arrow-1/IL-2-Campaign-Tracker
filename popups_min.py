from __future__ import annotations

from pathlib import Path
from typing import List, Tuple, Dict, Any
import tkinter as tk
import logging
import os, json

from utils.il2_paths import read_game_directory
from utils.pathing import get_base_path

logger = logging.getLogger(__name__)


def _is_debug_enabled() -> bool:
    env_value = os.environ.get("IL2_TRACKER_DEBUG", "")
    return env_value.strip().lower() in {"1", "true", "yes", "on"}


def _configure_logging():
    if not _is_debug_enabled():
        return

    logger.setLevel(logging.DEBUG)
    if not logging.getLogger().handlers and not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
        logger.addHandler(handler)
        logger.propagate = False


_configure_logging()

# Pillow is optional; if missing, we show text-only popups
try:
    from PIL import Image, ImageTk  # type: ignore
    PIL_OK = True
except Exception:
    PIL_OK = False

def _get_game_dir_from_json() -> Path | None:
    """
    Liest den 'game_directory' aus campaign_mission_dates.json.
    Unterstützt sowohl Python- als auch EXE-Modus.
    """

    try:
        base_path = get_base_path(__file__)
        game_dir = read_game_directory(base_path)

        if not game_dir:
            config_file = base_path / "campaign_mission_dates.json"
            print(f"[popups] ⚠️ Kein 'game_directory' in {config_file} gefunden.")
            return None

        if game_dir.exists():
            print(f"[popups] ✅ game_directory aus JSON geladen: {game_dir}")
            return game_dir

        print(f"[popups] ⚠️ Ungültiger game_directory-Pfad: {game_dir}")
        return None
    
    except Exception as e:
        print(f"[popups] ⚠️ Fehler beim Lesen von campaign_mission_dates.json: {e}")
        return None

def _resolve_image_path(game_directory: Path, country: str, ev: Dict[str, Any]) -> Path:
    """
    Resolve the full path to the rank/award image file.

    Structure:
      <game>\data\swf\CampaignRanksAwards\<country>\[early|late]\image.png|.dds

    USSR only: has 'early'/'late' subfolders based on date.
    Ranks: plain .png
    Awards: prefer *_big.dds
    """

    # 1️⃣ Pfad aus JSON sicherstellen (für EXE + Testmodus)   
    game_dir_path = Path(game_directory) if game_directory else None
    if (
        not game_dir_path
        or str(game_dir_path).strip() in {"", "."}
        or not game_dir_path.exists()
    ):
        json_dir = _get_game_dir_from_json()
        if json_dir and json_dir.exists():
            game_directory = json_dir
            print(f"[popups] Game directory loaded from JSON: {game_directory}")
        else:
            print("[popups] ⚠️ Kein gültiger game_directory gefunden.")
            return Path()
    else:
        game_directory = game_dir_path
    
    # 2️⃣ Bildname aus Event
    image_name = str(ev.get("image", "")).strip()
    if not image_name:
        print("[popups] ⚠️ Kein Bildname im Event definiert.")
        return Path()

    # 🔧 Doppelte Ordnerstruktur vermeiden
    if image_name.lower().startswith("campaignranksawards\\") or image_name.lower().startswith("campaignranksawards/"):
        image_name = image_name.split("\\", 1)[-1].split("/", 1)[-1]
        print(f"[popups] Normalized image name -> {image_name}")

    # 3️⃣ Basispfad
    base = Path(game_directory) / "data" / "swf" / "CampaignRanksAwards"

    # 4️⃣ Länderordner vereinheitlichen
    country = str(country).strip()
    country_folder_map = {
        "germany": "Germany",
        "britain": "Britain",
        "uk": "Britain",
        "usa": "US",
        "us": "US",
        "soviet": "USSR",
        "ussr": "USSR",
        "soviet union": "USSR",
    }
    country_folder = country_folder_map.get(country.lower(), country)
    if not country_folder:
        print(f"[popups] ⚠️ Kein gültiger country_folder für {country}")
        return Path()

    # 5️⃣ early/late nur bei USSR
    date_str = str(ev.get("date", ""))[:10]
    cutoff = "1943-07-01"
    subfolders = ["early"] if country_folder == "USSR" and (not date_str or date_str < cutoff) else []
    if country_folder == "USSR" and date_str >= cutoff:
        subfolders = ["late"]
    if not subfolders:
        subfolders = [""]

    # 6️⃣ Kandidaten aufbauen
    ev_type = str(ev.get("type", "")).strip().lower()
    candidates: List[Path] = []

    for sub in subfolders:
        folder = base / country_folder
        if sub:
            folder = folder / sub

        # Bildname (kann relativ sein)
        image_path = folder / Path(image_name)

        # Für Awards: *_big.dds bevorzugen
        if ev_type == "award":
            big_path = image_path.with_name(f"{image_path.stem}_big{image_path.suffix}")
            candidates.append(big_path)
            candidates.append(image_path)
            logger.debug(
                "Added award candidates: %s, %s",
                big_path,
                image_path,
            )
        else:
            candidates.append(image_path)
            logger.debug("Added rank candidate: %s", image_path)

    # 7️⃣ Existenzprüfung
    for p in candidates:
        exists = p.exists()
        logger.debug("Trying: %s -> exists=%s", p, exists)
        if exists:
            print(f"[popups] ✅ Using image: {p}")
            return p

    print(f"[popups] ⚠️ Kein Bild gefunden. Versucht: {', '.join(str(x) for x in candidates)}")
    return candidates[0]


def _make_popup(
    root: tk.Tk,
    title: str,
    line1: str,
    image_path: Path | None,
    duration_ms: int,
    subtitle: str = "",
    position: str = "center",
    image_max: tuple[int, int] = (220, 220),
) -> None:
    win = tk.Toplevel(root)

    # Borderless / toast style
    win.overrideredirect(True)
    win.attributes("-topmost", True)
    try:
        win.attributes("-alpha", 0.95)  # slight transparency
    except Exception:
        pass

    # Base colors (dark)
    bg = "#141414"
    fg = "#F2F2F2"
    sub_fg = "#C8C8C8"
    border = "#2A2A2A"

    outer = tk.Frame(win, bg=border, padx=2, pady=2)
    outer.pack(fill="both", expand=True)

    frame = tk.Frame(outer, bg=bg, padx=16, pady=14)
    frame.pack(fill="both", expand=True)

    # Title (small)
    title_lbl = tk.Label(
        frame,
        text=title.upper(),
        bg=bg,
        fg=sub_fg,
        font=("Segoe UI", 9, "bold"),
    )
    title_lbl.pack(anchor="w")

    # Main line
    main_lbl = tk.Label(
        frame,
        text=line1,
        bg=bg,
        fg=fg,
        font=("Segoe UI", 12, "bold"),
        justify="left",
        wraplength=420,
    )
    main_lbl.pack(anchor="w", pady=(6, 8))

    # Image (optional)
    if image_path and PIL_OK and image_path.exists():
        try:
            im = Image.open(image_path)
            
            # Calculate scaling to fit within image_max while maintaining aspect ratio
            # Unlike thumbnail(), this WILL upscale small images
            original_width, original_height = im.size
            max_width, max_height = image_max
            
            # Calculate scale factor
            scale_w = max_width / original_width
            scale_h = max_height / original_height
            scale = min(scale_w, scale_h)  # Use smaller scale to fit within bounds
            
            # Calculate new size
            new_width = int(original_width * scale)
            new_height = int(original_height * scale)
            
            # Resize (this will upscale if needed!)
            im = im.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            img_ref = ImageTk.PhotoImage(im)
            img_label = tk.Label(frame, image=img_ref, bg=bg)
            img_label.image = img_ref  # keep reference
            img_label.pack(anchor="center", pady=(0, 8))
        except Exception as e:
            print(f"[popups] ⚠️ Fehler beim Laden des Bildes {image_path}: {e}")
            # text-only popup is still useful

    # Subtitle (optional)
    if subtitle:
        sub_lbl = tk.Label(
            frame,
            text=subtitle,
            bg=bg,
            fg=sub_fg,
            font=("Segoe UI", 9),
            justify="left",
            wraplength=420,
        )
        sub_lbl.pack(anchor="w")

    # Auto close
    win.after(duration_ms, win.destroy)

    # Positioning
    win.update_idletasks()
    w = win.winfo_width()
    h = win.winfo_height()
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()

    margin = 18
    if position == "top_right":
        x = sw - w - margin
        y = margin
    elif position == "bottom_right":
        x = sw - w - margin
        y = sh - h - margin
    elif position == "center":
        x = int((sw - w) / 2)
        y = int((sh - h) / 2)  # true center
    else:
        x = int((sw - w) / 2)
        y = int((sh - h) / 2)

    win.geometry(f"{w}x{h}+{x}+{y}")

    # Ensure focus (helps when IL-2 is fullscreen/windowed)
    try:
        win.lift()
        win.focus_force()
    except Exception:
        pass


def show_event_popups(
    popup_events: List[Tuple[str, Dict[str, Any]]],
    game_directory: Path,
    campaign_country_map: Dict[str, str],
    duration_seconds: int = 5,
) -> None:
    """
    Show queued popups for new promotion/award events.

    popup_events: list of (campaign_name, event_dict)
    campaign_country_map: dict campaign_name -> country folder name (Germany/Britain/US/USSR)
    """
    if not popup_events:
        print("[popups] Keine Popup-Events gefunden – nichts zu tun.")
        return

    def _is_initial_rank_or_pilot_badge(event: Dict[str, Any]) -> bool:
        mission = str(event.get("mission", "")).strip().lower()
        if mission != "initial":
            return False

        ev_type = str(event.get("type", "")).strip().lower()
        if ev_type == "promotion":
            return True

        if ev_type != "award":
            return False

        award_name = str(event.get("name", "")).strip()
        award_image = str(event.get("image", "")).strip().lower()
        return (
            "Pilot's Badge" in award_name
            or "Aviation Badge" in award_name
            or "Aviation Emblem" in award_name
            or "pilots_badge" in award_image
            or "pilots_emblem" in award_image
        )

    # GUI vorbereiten
    root = tk.Tk()
    root.withdraw()  # kein Hauptfenster

    duration_ms = max(1, int(duration_seconds)) * 1000
    queue = []

    for campaign_name, ev in popup_events:
        ev_type = str(ev.get("type", "")).strip().lower()
        country = (
            campaign_country_map.get(campaign_name)
            or campaign_country_map.get(campaign_name.lower())
            or ""
        ).strip()

        if _is_initial_rank_or_pilot_badge(ev):
            print(
                "[popups][TRACE] skipping initial rank/pilot badge for campaign '%s'",
                campaign_name,
            )
            continue

        print(f"[popups][TRACE] processing event '{ev_type}' for campaign '{campaign_name}' (country='{country}')")

        # Pfad zum Bild sicher auflösen
        img_path = None
        if country:
            try:
                img_path = _resolve_image_path(Path(game_directory), country, ev)
                if img_path and img_path.exists():
                    print(f"[popups][TRACE] resolved image path OK: {img_path}")
                else:
                    print(f"[popups][TRACE] image path invalid or missing: {img_path}")
            except Exception as e:
                print(f"[popups][ERROR] Exception in _resolve_image_path: {e}")
                img_path = None
        else:
            print(f"[popups][WARN] Kein Landseintrag für campaign '{campaign_name}' gefunden!")

        # Titel und Text je nach Eventtyp
        if ev_type == "promotion":
            rank = str(ev.get("rank", "")).strip()
            line1 = f"You have been promoted to {rank}" if rank else "You have been promoted!"
            title = "Promotion"
            img_max = (308, 308)  # 20% larger for promotions
        elif ev_type == "award":
            name = str(ev.get("name", "")).strip()
            line1 = f"You have been awarded with {name}" if name else "You have received an award!"
            title = "Award"
            img_max = (512, 512)
        else:
            line1 = "New campaign event"
            title = "Event"
            img_max = (256, 256)

        # Untertitel (Mission + Datum)
        mission = str(ev.get("mission", "")).strip()
        date = str(ev.get("date", "")).strip()
        parts = [campaign_name]
        if mission:
            parts.append(f"Mission {mission}")
        if date:
            parts.append(date)
        subtitle = "  •  ".join(parts)

        # Einzelnes Popup erzeugen
        def _show_one(line1=line1, title=title, img_path=img_path, subtitle=subtitle, img_max=img_max):
            print(f"[popups][TRACE] showing popup '{title}' (image={img_path})")
            _make_popup(
                root,
                title=title,
                line1=line1,
                image_path=img_path,
                duration_ms=duration_ms,
                subtitle=subtitle,
                position="center",
                image_max=img_max,
            )

        queue.append(_show_one)

    # Popups nacheinander anzeigen
    def _next():
        if not queue:
            root.destroy()
            return
        fn = queue.pop(0)
        fn()
        root.after(duration_ms + 500, _next)

    _next()
    root.mainloop()


