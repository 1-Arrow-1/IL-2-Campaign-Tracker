"""
IL-2 Settings Manager - Main Application

The main application window with tabbed interface.
"""

import os
import json
import queue
import shutil
import zipfile
import re
import sqlite3
import subprocess
import sys
import threading
import tkinter as tk
import time
import logging
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, ttk, messagebox
from copy import deepcopy
from typing import Any, Dict, Optional, Iterable, Tuple, List

from settings_manager.config.paths import (
    CONFIG_YAML_PATH,
    SETTINGS_JSON_PATH,
    MISSION_DATES_PATH,
    STOCK_CAMPAIGNS_PATH,
)
from settings_manager.config.file_handlers import (
    load_json,
    save_json_atomic,
    load_yaml,
    save_yaml_atomic,
    HAS_RUAMEL,
)
from settings_manager.config.validators import (
    BracketValidator,
    ScoreValidator,
    OffsetValidator,
)
from settings_manager.i18n import Translator, LANGUAGE_NAMES
from settings_manager.stock_campaign_import import (
    StockCampaignImportResult,
    get_bundled_resource_path,
    import_stock_campaigns,
    validate_game_directory,
)

if HAS_RUAMEL:
    from ruamel.yaml.comments import CommentedMap
else:
    CommentedMap = dict

logger = logging.getLogger(__name__)

# Windows elevation constants
_ERROR_ELEVATION_REQUIRED = 740
_ERROR_CANCELLED = 1223

# Tracker EXE name for process detection
_TRACKER_EXE_NAME = "IL2_CampaignTracker_v2.2_ML.exe"


def _is_tracker_running() -> bool:
    """Check if the Tracker EXE is currently running."""
    try:
        import psutil
        tracker_name_lower = _TRACKER_EXE_NAME.lower()
        for proc in psutil.process_iter(['name']):
            try:
                if proc.info['name'] and proc.info['name'].lower() == tracker_name_lower:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return False
    except ImportError:
        # psutil not available, try Windows tasklist
        try:
            result = subprocess.run(
                ['tasklist', '/FI', f'IMAGENAME eq {_TRACKER_EXE_NAME}', '/NH'],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0,
            )
            return _TRACKER_EXE_NAME.lower() in result.stdout.lower()
        except Exception:
            return False  # Can't detect, assume not running


def _run_elevated_windows(
    exe_path: str,
    args: List[str],
    working_dir: str,
    log_path: str,
    env: Optional[Dict[str, str]] = None,
    timeout_seconds: int = 600,
) -> Tuple[bool, int, str]:
    """
    Run a process with elevation (admin rights) on Windows using ShellExecuteEx.

    Since ShellExecute cannot capture stdout directly, we use cmd.exe to redirect
    output to a log file.

    Args:
        exe_path: Path to the executable
        args: List of command-line arguments
        working_dir: Working directory for the process
        log_path: Path to write stdout/stderr
        env: Environment variables (note: only partially supported via cmd.exe)
        timeout_seconds: Maximum time to wait for process completion

    Returns:
        Tuple of (success, return_code, error_message)
    """
    import ctypes
    from ctypes import wintypes

    # ShellExecuteEx constants
    SEE_MASK_NOCLOSEPROCESS = 0x00000040
    SEE_MASK_NO_CONSOLE = 0x00008000
    SW_SHOWNORMAL = 1

    # WaitForSingleObject return values
    WAIT_OBJECT_0 = 0x00000000
    WAIT_TIMEOUT = 0x00000102

    class SHELLEXECUTEINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("fMask", wintypes.ULONG),
            ("hwnd", wintypes.HWND),
            ("lpVerb", wintypes.LPCWSTR),
            ("lpFile", wintypes.LPCWSTR),
            ("lpParameters", wintypes.LPCWSTR),
            ("lpDirectory", wintypes.LPCWSTR),
            ("nShow", ctypes.c_int),
            ("hInstApp", wintypes.HINSTANCE),
            ("lpIDList", ctypes.c_void_p),
            ("lpClass", wintypes.LPCWSTR),
            ("hkeyClass", wintypes.HKEY),
            ("dwHotKey", wintypes.DWORD),
            ("hIcon", wintypes.HANDLE),
            ("hProcess", wintypes.HANDLE),
        ]

    shell32 = ctypes.windll.shell32
    kernel32 = ctypes.windll.kernel32

    # Build command line for cmd.exe to handle redirection
    # cmd.exe /c "entire command" - outer quotes delimit the command
    # Inner quotes around paths with spaces are handled by cmd.exe
    args_str = " ".join(f'"{a}"' if " " in a else a for a in args)

    # Build the inner command (exe + args + redirect)
    inner_cmd = f'"{exe_path}" {args_str} > "{log_path}" 2>&1'

    # Prepend environment variable setup if provided
    if env:
        # Use set VAR=value (no quotes around the assignment)
        env_sets = " && ".join(f"set {k}={v}" for k, v in env.items() if k != "PATH")
        if env_sets:
            inner_cmd = f"{env_sets} && {inner_cmd}"

    # Wrap entire command in quotes for /c
    cmd_params = f'/c "{inner_cmd}"'

    print(f"[Settings Manager] Requesting elevation for Tracker EXE...")
    print(f"[Settings Manager] Command: cmd.exe {cmd_params}")

    sei = SHELLEXECUTEINFO()
    sei.cbSize = ctypes.sizeof(sei)
    sei.fMask = SEE_MASK_NOCLOSEPROCESS
    sei.hwnd = None
    sei.lpVerb = "runas"
    sei.lpFile = "cmd.exe"
    sei.lpParameters = cmd_params
    sei.lpDirectory = working_dir
    sei.nShow = SW_SHOWNORMAL

    # Attempt elevated launch
    if not shell32.ShellExecuteExW(ctypes.byref(sei)):
        error_code = ctypes.GetLastError()
        if error_code == _ERROR_CANCELLED:
            return (False, -1, "UAC_CANCELLED")
        return (False, -1, f"ShellExecuteEx failed with error code {error_code}")

    if not sei.hProcess:
        return (False, -1, "ShellExecuteEx succeeded but no process handle returned")

    print(f"[Settings Manager] Elevated process launched, waiting for completion...")

    # Poll with timeout
    timeout_ms = timeout_seconds * 1000
    poll_interval_ms = 500
    elapsed_ms = 0

    while elapsed_ms < timeout_ms:
        result = kernel32.WaitForSingleObject(sei.hProcess, poll_interval_ms)
        if result == WAIT_OBJECT_0:
            # Process completed
            exit_code = wintypes.DWORD()
            kernel32.GetExitCodeProcess(sei.hProcess, ctypes.byref(exit_code))
            kernel32.CloseHandle(sei.hProcess)
            return (True, exit_code.value, "")
        elif result == WAIT_TIMEOUT:
            elapsed_ms += poll_interval_ms
            continue
        else:
            # Unexpected result
            kernel32.CloseHandle(sei.hProcess)
            return (False, -1, f"WaitForSingleObject returned unexpected value {result}")

    # Timeout reached
    print(f"[Settings Manager] Elevated process timed out after {timeout_seconds}s")
    kernel32.TerminateProcess(sei.hProcess, 1)
    kernel32.CloseHandle(sei.hProcess)
    return (False, -1, "TIMEOUT")


class SettingsManagerApp(tk.Tk):
    """Main Settings Manager Application."""

    COUNTRY_OPTIONS = ["Germany", "Soviet Union", "Britain", "USA"]
    STORY_PROVIDER_OPTIONS = ["openai", "openrouter", "anthropic", "google", "microsoft", "custom"]
    STORY_PROVIDER_DEFAULT_BASE_URLS = {
        "openai": "https://api.openai.com/v1",
        "openrouter": "https://openrouter.ai/api/v1",
        "anthropic": "https://api.anthropic.com/v1",
        "google": "https://generativelanguage.googleapis.com/v1beta/openai",
        "microsoft": "https://YOUR-RESOURCE-NAME.openai.azure.com/openai/v1",
        "custom": "",
    }
    STORY_PROVIDER_MODEL_HINTS = {
        "openai": "Example: gpt-5-mini or gpt-5",
        "openrouter": "Example: x-ai/grok-4.1-fast or google/gemini-2.0-flash-001",
        "anthropic": "Example: claude-sonnet-4-5",
        "google": "Example: gemini-2.0-flash-001",
        "microsoft": "Use your Azure deployment model/deployment name.",
        "custom": "Enter the exact model ID required by your custom endpoint.",
    }
    STORY_PROVIDER_MODELS = {
        "openai": [],
        "openrouter": [],
        "anthropic": [],
        "google": [],
        "microsoft": [],
        "custom": [],
    }
    STORY_PROVIDER_RECOMMENDED_MODELS = {
        "openai": ["gpt-5-mini", "gpt-5", "gpt-4.1"],
        "openrouter": [
            "x-ai/grok-4.1-fast",
            "google/gemini-2.0-flash-001",
            "openai/gpt-5-mini",
            "anthropic/claude-sonnet-4.5",
        ],
        "anthropic": ["claude-sonnet-4.5", "claude-3.5-sonnet", "claude-3.5-haiku"],
        "google": ["gemini-2.0-flash-001", "gemini-2.0-flash-lite-001", "gemini-1.5-pro"],
        "microsoft": ["gpt-5-mini", "gpt-5", "gpt-4.1"],
        "custom": [],
    }

    # Detail page language options: stored value -> i18n key
    # None means "Default" (follow global language)
    DETAIL_PAGE_LOCALE_OPTIONS = {
        None: "lbl_language_default",
        "en": "lbl_language_english",
        "de": "lbl_language_german",
        "ru": "lbl_language_russian",
    }

    # Career language override options: stored value -> i18n key
    CAREER_LOCALE_OPTIONS = {
        None: "lbl_language_default",
        "en": "lbl_language_english",
        "de": "lbl_language_german",
        "ru": "lbl_language_russian",
    }

    # Squadron Roster: pilot state integer → display name
    PILOT_STATES: Dict[int, str] = {
        0: "Active",
        1: "Squadron Commander",
        2: "KIA",
        3: "MIA",
        4: "WIA",
        5: "Transferred",
        8: "Deputy Commander",
    }
    # States the user may SET in the roster — only non-invasive role changes.
    # KIA/MIA/WIA/Transferred are set by the game; we never write them.
    _PILOT_STATE_FROM_NAME: Dict[str, int] = {
        "Active":             0,
        "Squadron Commander": 1,
        "Deputy Commander":   8,
    }
    # States that lock the row — double-clicking state cell does nothing.
    _PILOT_STATE_READONLY = {4}   # WIA only — Transferred is editable
    # (tree_col_id, db_col_name, pixel_width, is_numeric)
    _ROSTER_TREE_COLS: List[Tuple[str, str, int, bool]] = [
        ("first_name",   "name",        120, False),
        ("last_name",    "lastName",    120, False),
        ("ai_level",     "AILevel",      70, True),
        ("pcp",          "pcp",          70, True),
        ("sorties",      "sorties",      70, True),
        ("good_sorties", "goodSorties",  90, True),
        ("state",        "state",       150, False),
    ]

    # One background colour per tab (index matches tab creation order).
    _TAB_COLORS = [
        "#455a64",  # 0 General              – blue-grey
        "#1565c0",  # 1 Rank Scaling         – cobalt blue
        "#6a1b9a",  # 2 Rank Values          – purple
        "#2e7d32",  # 3 Campaigns            – forest green
        "#00695c",  # 4 Career Languages     – teal
        "#bf360c",  # 5 German Awards        – deep burnt orange
        "#b71c1c",  # 6 Updates              – dark red
        "#01579b",  # 7 Squadron Roster      – navy blue
        "#4a148c",  # 8 Copy Squadron Pilot  – deep violet
    ]

    def __init__(self):
        super().__init__()
        
        # Initialize translator
        self.tr = Translator()
        
        # Load current locale from settings
        self._load_initial_locale()
        
        # Configure window
        self.title(self.tr.t("app_title"))
        self.geometry("1280x760")
        self.minsize(1280, 620)
        
        # Data storage
        self.settings_data: Dict[str, Any] = {}
        self.config_data: Dict[str, Any] = {}
        self.mission_dates_data: Optional[Dict[str, Any]] = None
        self.stock_campaigns_data: Optional[Dict[str, Any]] = None
        self.original_data: Dict[str, Any] = {}
        self._refresh_thread: Optional[threading.Thread] = None
        self._close_after_refresh: bool = False
        self._refresh_status_var = tk.StringVar(value="")
        self._refresh_queue: "queue.Queue[Optional[str]]" = queue.Queue()
        self._refresh_poll_id: Optional[str] = None
        self._refresh_running: bool = False
        self._refresh_start_time: float = 0.0
        self._pending_locale: Optional[str] = None  # set when locale change triggered restart
        self._country_editor: Optional[ttk.Combobox] = None
        self._country_editor_item: Optional[str] = None
        self._language_editor: Optional[ttk.Combobox] = None
        self._language_editor_item: Optional[str] = None
        self._campaign_display_name_map: Optional[Dict[str, str]] = None
        # Track campaigns that need localized debriefings regeneration
        self._campaigns_needing_debriefings_regen: set = set()
        # Career language tab editor state
        self._career_lang_editor: Optional[ttk.Combobox] = None
        self._career_lang_editor_item: Optional[str] = None
        self._career_list_cache: List[Tuple[int, str]] = []
        self._button_icons: Dict[str, tk.PhotoImage] = {}
        self._stock_import_btn: Optional[ttk.Button] = None
        self._stock_import_status_var = tk.StringVar(value="")
        self._stock_import_thread: Optional[threading.Thread] = None
        self._stock_import_queue: "queue.Queue[Dict[str, Any]]" = queue.Queue()
        self._stock_import_poll_id: Optional[str] = None
        self._force_regen_btn: Optional[ttk.Button] = None
        self._force_regen_status_var = tk.StringVar(value="")
        self._force_regen_thread: Optional[threading.Thread] = None
        self._force_regen_queue: "queue.Queue[Dict[str, Any]]" = queue.Queue()
        self._force_regen_poll_id: Optional[str] = None
        self._force_regen_start_time: float = 0.0
        self._story_test_thread: Optional[threading.Thread] = None
        self._story_test_queue: "queue.Queue[Dict[str, Any]]" = queue.Queue()
        self._story_test_poll_id: Optional[str] = None
        self._story_models_refresh_thread: Optional[threading.Thread] = None
        self._story_models_refresh_queue: "queue.Queue[Dict[str, Any]]" = queue.Queue()
        self._story_models_refresh_poll_id: Optional[str] = None
        self._story_provider_models_runtime: Dict[str, List[str]] = {
            key: list(values) for key, values in self.STORY_PROVIDER_MODELS.items()
        }
        self._story_provider_api_keys: Dict[str, str] = {}
        self._story_last_provider: str = "openai"

        # German awards tab state
        self._german_awards_var: Optional[tk.StringVar] = None
        self._german_awards_status_var: Optional[tk.StringVar] = None
        self._german_awards_swap_btn: Optional[ttk.Button] = None
        self._german_awards_radio_1957: Optional[ttk.Radiobutton] = None
        self._german_awards_radio_ww2: Optional[ttk.Radiobutton] = None
        self._german_uncensored_var: Optional[tk.BooleanVar] = None

        # Update tab state
        self._update_zip_path: Optional[Path] = None
        self._update_manifest = None          # UpdateManifest | None
        self._update_entries: list = []       # list[FileEntry]
        self._update_install_btn: Optional[ttk.Button] = None
        self._update_status_var = tk.StringVar(value="")
        self._update_progress_var = tk.IntVar(value=0)
        self._update_progress_bar: Optional[ttk.Progressbar] = None
        self._update_progress_frame: Optional[ttk.Frame] = None
        self._update_log_btn: Optional[ttk.Button] = None
        self._update_log_path: Optional[Path] = None
        self._update_restart_btn: Optional[ttk.Button] = None
        self._update_pending_files: List[str] = []
        self._update_post_install_row: Optional[ttk.Frame] = None
        self._restore_zip_path: Optional[Path] = None
        self._update_thread: Optional[threading.Thread] = None
        self._update_queue: "queue.Queue[Dict[str, Any]]" = queue.Queue()
        self._update_poll_id: Optional[str] = None
        self._update_zip_label_var = tk.StringVar(value="")
        self._update_new_version_var = tk.StringVar(value="")
        self._update_tree: Optional[ttk.Treeview] = None
        self._update_proc_warn_var = tk.StringVar(value="")
        self._update_proc_warn_label: Optional[ttk.Label] = None
        self._update_manifest_frame: Optional[ttk.Frame] = None

        # Squadron Roster tab state
        self._roster_tree: Optional[ttk.Treeview] = None
        self._roster_career_combo: Optional[ttk.Combobox] = None
        self._roster_career_ids: List[int] = []
        self._roster_current_career_id: Optional[int] = None
        self._roster_pilot_data: Dict[str, Dict] = {}
        self._roster_pending_changes: Dict[str, Dict] = {}
        self._roster_editor: Optional[tk.Widget] = None
        self._roster_editor_item: Optional[str] = None
        self._roster_editor_col: Optional[str] = None
        self._roster_status_var = tk.StringVar(value="")

        # Copy Squadron Pilot tab state
        self._copy_pilot_career_ids: List[int] = []
        self._copy_pilot_career_combo: Optional[ttk.Combobox] = None
        self._copy_pilot_n_career_id: Optional[int] = None
        self._copy_pilot_n_squadron_id: Optional[int] = None
        self._copy_pilot_n_config_id: Optional[int] = None
        self._copy_pilot_n1_career_id: Optional[int] = None
        self._copy_pilot_rows: Dict[int, Dict] = {}
        self._copy_pilot_check_vars: Dict[int, tk.BooleanVar] = {}
        self._copy_pilot_status_var = tk.StringVar(value="")
        self._copy_pilot_apply_btn: Optional[ttk.Button] = None
        self._copy_pilot_no_prev_label: Optional[ttk.Label] = None
        self._copy_pilot_pilot_frame: Optional[ttk.Frame] = None
        self._copy_pilot_canvas: Optional[tk.Canvas] = None
        self._copy_pilot_inner_frame: Optional[ttk.Frame] = None

        # Load all data
        self._load_all_data()

        # Apply custom styles (must come before widget creation)
        self._setup_styles()

        # Create UI
        self._create_widgets()
        
        # Center window
        self._center_window()
        
        # Bind close event
        self.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _load_initial_locale(self) -> None:
        """Load locale from settings file."""
        try:
            settings = load_json(SETTINGS_JSON_PATH)
            if settings and 'locale' in settings:
                self.tr.set_locale(settings['locale'])
        except Exception:
            pass
    
    def _load_all_data(self) -> None:
        """Load all configuration files."""
        # Load settings JSON
        try:
            self.settings_data = load_json(SETTINGS_JSON_PATH) or {'locale': 'en'}
        except ValueError as e:
            messagebox.showerror(self.tr.t("msg_error_title"), str(e))
            self.settings_data = {'locale': 'en'}
        
        # Load config YAML
        try:
            self.config_data = load_yaml(CONFIG_YAML_PATH) or {}
        except ValueError as e:
            messagebox.showerror(self.tr.t("msg_error_title"), str(e))
            self.config_data = {}
        
        # Load mission dates JSON (optional)
        try:
            self.mission_dates_data = load_json(MISSION_DATES_PATH)
        except ValueError:
            self.mission_dates_data = None

        # Load stock campaigns YAML (optional)
        try:
            self.stock_campaigns_data = load_yaml(STOCK_CAMPAIGNS_PATH)
        except ValueError as e:
            messagebox.showerror(self.tr.t("msg_error_title"), str(e))
            self.stock_campaigns_data = None
        
        # Store originals for dirty checking
        self.original_data = {
            'settings': deepcopy(self.settings_data),
            'config': deepcopy(self.config_data),
            'mission_dates': deepcopy(self.mission_dates_data) if self.mission_dates_data else None,
            'stock_campaigns': deepcopy(self.stock_campaigns_data) if self.stock_campaigns_data else None,
        }
        self._campaign_display_name_map = None

    def _load_button_icon(self, relative_path: str, cache_key: str) -> Optional[tk.PhotoImage]:
        """Load a small PNG button icon from bundled resources."""
        if cache_key in self._button_icons:
            return self._button_icons[cache_key]

        icon_path = get_bundled_resource_path(relative_path)
        if not icon_path.exists():
            logger.debug("Button icon not found: %s", icon_path)
            return None

        try:
            image = tk.PhotoImage(file=str(icon_path))
            self._button_icons[cache_key] = image
            return image
        except Exception as exc:
            logger.debug("Could not load button icon %s: %s", icon_path, exc)
            return None
    
    def _setup_styles(self) -> None:
        """Configure custom ttk styles: action buttons + coloured tab headers."""
        style = ttk.Style()
        # 'clam' lets us set arbitrary background colours on tabs and buttons
        # on all platforms (the native 'vista' theme on Windows ignores bg).
        style.theme_use("clam")

        # Action button – steel blue, white text
        _ACT_BG  = "#1976d2"
        _ACT_HOV = "#1255a0"
        style.configure(
            "Action.TButton",
            background=_ACT_BG,
            foreground="white",
            relief="raised",
            padding=(8, 4),
            font=("TkDefaultFont", 9),
        )
        style.map(
            "Action.TButton",
            background=[("active", _ACT_HOV), ("disabled", "#9e9e9e")],
            foreground=[("disabled", "#e0e0e0")],
            relief=[("pressed", "sunken")],
        )

        # Per-tab coloured header styles
        for i, bg in enumerate(self._TAB_COLORS):
            name = f"Tab{i}.TNotebook.Tab"
            style.configure(
                name,
                background=bg,
                foreground="white",
                padding=(10, 5),
                font=("TkDefaultFont", 9, "bold"),
            )
            style.map(
                name,
                background=[("selected", bg), ("active", bg)],
                foreground=[("selected", "white"), ("active", "white")],
            )

    def _create_widgets(self) -> None:
        """Create all UI widgets."""
        # Main frame with padding
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Notebook (tabs)
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Tab 1: General Settings
        self._create_general_tab()
        
        # Tab 2: Rank Scaling
        self._create_rank_scaling_tab()
        
        # Tab 3: Rank Values
        self._create_rank_values_tab()
        
        # Tab 4: Campaigns (conditional)
        self._create_campaigns_tab()

        # Tab 5: Career Language Settings
        self._create_career_languages_tab()

        # Tab 6: German Awards style switcher
        self._create_german_awards_tab()

        # Tab 7: Update installer
        self._create_updates_tab()

        # Tab 8: Squadron Roster
        self._create_squadron_roster_tab()

        # Tab 9: Copy Squadron Pilot
        self._create_copy_pilot_tab()

        # Add a small coloured square icon to each tab header.
        # PhotoImage.put() is reliable on all platforms; no Pillow needed.
        for _i in range(self.notebook.index("end")):
            if _i < len(self._TAB_COLORS):
                _img = tk.PhotoImage(width=10, height=10)
                _img.put(self._TAB_COLORS[_i], to=(0, 0, 10, 10))
                self._button_icons[f"_tab_color_{_i}"] = _img  # prevent GC
                self.notebook.tab(_i, image=_img, compound=tk.LEFT)

        # Button frame
        self._create_button_bar(main_frame)
    
    def _create_general_tab(self) -> None:
        """Create General Settings tab."""
        frame = ttk.Frame(self.notebook, padding=20)
        self.notebook.add(frame, text=self.tr.t("tab_general"))
        
        # Language
        row = 0
        ttk.Label(frame, text=self.tr.t("lbl_language")).grid(
            row=row, column=0, sticky=tk.W, pady=10
        )
        
        self.language_var = tk.StringVar()
        lang_options = list(LANGUAGE_NAMES.values())
        self.language_combo = ttk.Combobox(
            frame,
            textvariable=self.language_var,
            values=lang_options,
            state='readonly',
            width=30
        )
        self.language_combo.grid(row=row, column=1, sticky=tk.W, pady=10, padx=(10, 0))
        
        # Set current value
        current_locale = self.settings_data.get('locale', 'en')
        current_name = LANGUAGE_NAMES.get(current_locale, 'English')
        self.language_var.set(current_name)
        
        # Enable popups
        row += 1
        ttk.Label(frame, text=self.tr.t("lbl_enable_popups")).grid(
            row=row, column=0, sticky=tk.W, pady=10
        )
        
        self.popups_var = tk.StringVar()
        self.popups_combo = ttk.Combobox(
            frame,
            textvariable=self.popups_var,
            values=['True', 'False'],
            state='readonly',
            width=30
        )
        self.popups_combo.grid(row=row, column=1, sticky=tk.W, pady=10, padx=(10, 0))
        
        current_popups = self.config_data.get('enable_popups', True)
        self.popups_var.set('True' if current_popups else 'False')
        
        # Rank scaling enabled
        row += 1
        ttk.Label(frame, text=self.tr.t("lbl_rank_scaling_enabled")).grid(
            row=row, column=0, sticky=tk.W, pady=10
        )
        
        self.scaling_var = tk.StringVar()
        self.scaling_combo = ttk.Combobox(
            frame,
            textvariable=self.scaling_var,
            values=['True', 'False'],
            state='readonly',
            width=30
        )
        self.scaling_combo.grid(row=row, column=1, sticky=tk.W, pady=10, padx=(10, 0))
        
        rank_scaling = self.config_data.get('rank_scaling', {})
        current_scaling = rank_scaling.get('enabled', True) if isinstance(rank_scaling, dict) else True
        self.scaling_var.set('True' if current_scaling else 'False')

        story_settings = self.settings_data.get('stories', {})
        if not isinstance(story_settings, dict):
            story_settings = {}

        # AI stories enabled
        row += 1
        ttk.Label(frame, text=self.tr.t("lbl_ai_stories_enabled")).grid(
            row=row, column=0, sticky=tk.W, pady=10
        )

        self.ai_stories_var = tk.StringVar()
        self.ai_stories_combo = ttk.Combobox(
            frame,
            textvariable=self.ai_stories_var,
            values=['True', 'False'],
            state='readonly',
            width=30
        )
        self.ai_stories_combo.grid(row=row, column=1, sticky=tk.W, pady=10, padx=(10, 0))
        self.ai_stories_var.set('True' if story_settings.get('enabled', False) else 'False')

        # Story provider
        row += 1
        ttk.Label(frame, text=self.tr.t("lbl_story_provider")).grid(
            row=row, column=0, sticky=tk.W, pady=10
        )
        provider_value = str(story_settings.get('provider', 'openai') or 'openai').strip().lower()
        if provider_value not in self.STORY_PROVIDER_OPTIONS:
            provider_value = 'openai'
        provider_api_keys = story_settings.get('api_keys', {})
        api_keys_map: Dict[str, str] = {}
        if isinstance(provider_api_keys, dict):
            for key, value in provider_api_keys.items():
                normalized_key = str(key or '').strip().lower()
                if normalized_key in self.STORY_PROVIDER_OPTIONS:
                    api_keys_map[normalized_key] = str(value or '').strip()
        legacy_key = str(story_settings.get('api_key', '') or '').strip()
        if legacy_key and not api_keys_map.get(provider_value):
            api_keys_map[provider_value] = legacy_key
        self._story_provider_api_keys = api_keys_map
        self._story_last_provider = provider_value
        self.story_provider_var = tk.StringVar(value=provider_value)
        self.story_provider_combo = ttk.Combobox(
            frame,
            textvariable=self.story_provider_var,
            values=self.STORY_PROVIDER_OPTIONS,
            state='readonly',
            width=30
        )
        self.story_provider_combo.grid(row=row, column=1, sticky=tk.W, pady=10, padx=(10, 0))
        self.story_provider_combo.bind("<<ComboboxSelected>>", self._on_story_provider_changed)

        # Story API key
        row += 1
        ttk.Label(frame, text=self.tr.t("lbl_story_api_key")).grid(
            row=row, column=0, sticky=tk.W, pady=10
        )
        self.story_api_key_var = tk.StringVar(value=self._story_provider_api_keys.get(provider_value, ''))
        self.openai_api_key_entry = ttk.Entry(
            frame,
            textvariable=self.story_api_key_var,
            show='*',
            width=33
        )
        self.openai_api_key_entry.grid(row=row, column=1, sticky=tk.W, pady=10, padx=(10, 0))

        # Story base URL
        row += 1
        ttk.Label(frame, text=self.tr.t("lbl_story_base_url")).grid(
            row=row, column=0, sticky=tk.W, pady=10
        )
        base_url_value = str(story_settings.get('base_url', '') or '').strip()
        if not base_url_value:
            base_url_value = self.STORY_PROVIDER_DEFAULT_BASE_URLS.get(provider_value, '')
        self.story_base_url_var = tk.StringVar(value=base_url_value)
        self.story_base_url_entry = ttk.Entry(
            frame,
            textvariable=self.story_base_url_var,
            width=33
        )
        self.story_base_url_entry.grid(row=row, column=1, sticky=tk.W, pady=10, padx=(10, 0))

        # Story model
        row += 1
        ttk.Label(frame, text=self.tr.t("lbl_story_model")).grid(
            row=row, column=0, sticky=tk.W, pady=10
        )

        self.story_model_var = tk.StringVar()
        self.story_model_combo = ttk.Combobox(
            frame,
            textvariable=self.story_model_var,
            values=[],
            state='disabled',
            width=30
        )
        self.story_model_combo.grid(row=row, column=1, sticky=tk.W, pady=10, padx=(10, 0))
        # Model field starts disabled — user must click "Refresh Models" to populate it.
        # Preserve the saved model value in the var so it can be restored after refresh.
        self._story_saved_model = str(story_settings.get('model') or '').strip()
        row += 1
        self.story_model_hint_var = tk.StringVar(value="")
        self.story_model_hint_label = ttk.Label(
            frame,
            textvariable=self.story_model_hint_var,
            foreground='gray',
            wraplength=380,
            justify=tk.LEFT,
        )
        self.story_model_hint_label.grid(row=row, column=1, sticky=tk.W, pady=(2, 0), padx=(10, 0))
        self._update_story_model_hint()

        # Auto-generate stories
        row += 1
        ttk.Label(frame, text=self.tr.t("lbl_story_auto_generate")).grid(
            row=row, column=0, sticky=tk.W, pady=10
        )

        self.story_auto_generate_var = tk.StringVar()
        self.story_auto_generate_combo = ttk.Combobox(
            frame,
            textvariable=self.story_auto_generate_var,
            values=['True', 'False'],
            state='readonly',
            width=30
        )
        self.story_auto_generate_combo.grid(row=row, column=1, sticky=tk.W, pady=10, padx=(10, 0))
        self.story_auto_generate_var.set('True' if story_settings.get('auto_generate', False) else 'False')

        # Award citations enabled
        row += 1
        ttk.Label(frame, text=self.tr.t("lbl_citations_enabled")).grid(
            row=row, column=0, sticky=tk.W, pady=10
        )

        self.citations_enabled_var = tk.StringVar()
        self.citations_enabled_combo = ttk.Combobox(
            frame,
            textvariable=self.citations_enabled_var,
            values=['True', 'False'],
            state='readonly',
            width=30
        )
        self.citations_enabled_combo.grid(row=row, column=1, sticky=tk.W, pady=10, padx=(10, 0))
        self.citations_enabled_var.set('True' if story_settings.get('citations_enabled', False) else 'False')

        # Test connection controls
        row += 1
        self.story_test_button = ttk.Button(
            frame,
            text=self.tr.t("btn_test_connection"),
            command=self._on_test_story_connection,
            style="Action.TButton",
        )
        self.story_test_button.grid(row=row, column=1, sticky=tk.W, pady=(10, 0), padx=(10, 0))
        self.story_refresh_models_button = ttk.Button(
            frame,
            text=self.tr.t("btn_refresh_models"),
            command=self._on_refresh_story_models,
            style="Action.TButton",
        )
        self.story_refresh_models_button.grid(row=row, column=1, sticky=tk.W, pady=(10, 0), padx=(140, 0))

        row += 1
        self.story_status_var = tk.StringVar(value="")
        self.story_status_label = ttk.Label(
            frame,
            textvariable=self.story_status_var,
            foreground='gray'
        )
        self.story_status_label.grid(row=row, column=1, sticky=tk.W, pady=(6, 0), padx=(10, 0))

        # Configure grid
        frame.columnconfigure(1, weight=1)
    
    def _create_rank_scaling_tab(self) -> None:
        """Create Rank Scaling Factors tab."""
        frame = ttk.Frame(self.notebook, padding=20)
        self.notebook.add(frame, text=self.tr.t("tab_rank_scaling"))
        
        # Treeview for bracket/factor table
        columns = ('bracket', 'factor')
        self.scaling_tree = ttk.Treeview(
            frame,
            columns=columns,
            show='headings',
            height=10
        )
        
        self.scaling_tree.heading('bracket', text=self.tr.t("lbl_bracket"))
        self.scaling_tree.heading('factor', text=self.tr.t("lbl_factor"))
        self.scaling_tree.column('bracket', width=150, anchor=tk.CENTER)
        self.scaling_tree.column('factor', width=100, anchor=tk.CENTER)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.scaling_tree.yview)
        self.scaling_tree.configure(yscrollcommand=scrollbar.set)
        
        # Layout
        self.scaling_tree.grid(row=0, column=0, sticky=tk.NSEW, pady=(0, 10))
        scrollbar.grid(row=0, column=1, sticky=tk.NS, pady=(0, 10))
        
        # Populate data
        self._populate_scaling_tree()
        
        # Button frame
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=1, column=0, columnspan=2, sticky=tk.W)
        
        ttk.Button(
            btn_frame,
            text=self.tr.t("btn_add_bracket"),
            command=self._on_add_bracket,
            style="Action.TButton",
        ).pack(side=tk.LEFT, padx=(0, 5))

        ttk.Button(
            btn_frame,
            text=self.tr.t("btn_edit"),
            command=self._on_edit_bracket,
            style="Action.TButton",
        ).pack(side=tk.LEFT, padx=(0, 5))

        ttk.Button(
            btn_frame,
            text=self.tr.t("btn_remove_bracket"),
            command=self._on_remove_bracket,
            style="Action.TButton",
        ).pack(side=tk.LEFT)
        
        # Double-click to edit
        self.scaling_tree.bind('<Double-1>', lambda e: self._on_edit_bracket())
        
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
    
    def _populate_scaling_tree(self) -> None:
        """Populate rank scaling treeview."""
        # Clear existing items
        for item in self.scaling_tree.get_children():
            self.scaling_tree.delete(item)
        
        # Get factors
        rank_scaling = self.config_data.get('rank_scaling', {})
        factors = rank_scaling.get('factors', {}) if isinstance(rank_scaling, dict) else {}
        
        sorted_factors = sorted(
            factors.items(),
            key=lambda item: self._bracket_sort_key(item[0]),
        )
        
        for bracket, factor in sorted_factors:
            self.scaling_tree.insert('', tk.END, values=(bracket, factor))
    
    def _create_rank_values_tab(self) -> None:
        """Create Rank Values tab."""
        frame = ttk.Frame(self.notebook, padding=20)
        self.notebook.add(frame, text=self.tr.t("tab_rank_values"))
        
        # Info label
        info_text = self.tr.t("lbl_rank_values_helper")
        ttk.Label(frame, text=info_text, foreground='gray').grid(
            row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 10)
        )

        self.rank_warning_label = ttk.Label(
            frame,
            text=self.tr.t("msg_rank_scores_mismatch"),
            foreground='darkorange'
        )
        self.rank_warning_label.grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=(0, 10))
        
        # Treeview
        self.rank_country_columns = [
            (f"country_{idx}", country) for idx, country in enumerate(self._get_rank_countries())
        ]
        columns = ('index', 'score', *[col_id for col_id, _ in self.rank_country_columns])
        self.ranks_tree = ttk.Treeview(
            frame,
            columns=columns,
            show='headings',
            height=12
        )
        
        self.ranks_tree.heading('index', text=self.tr.t("lbl_rank_index_header"))
        self.ranks_tree.heading('score', text=self.tr.t("lbl_rank_score"))
        self.ranks_tree.column('index', width=90, anchor=tk.W)
        self.ranks_tree.column('score', width=90, anchor=tk.CENTER)
        for col_id, country in self.rank_country_columns:
            self.ranks_tree.heading(col_id, text=country)
            self.ranks_tree.column(col_id, width=160, anchor=tk.W)
        
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.ranks_tree.yview)
        self.ranks_tree.configure(yscrollcommand=scrollbar.set)
        
        self.ranks_tree.grid(row=2, column=0, sticky=tk.NSEW, pady=(0, 10))
        scrollbar.grid(row=2, column=1, sticky=tk.NS, pady=(0, 10))
        
        # Populate
        self._populate_ranks_tree()
        
        # Edit button
        ttk.Button(
            frame,
            text=self.tr.t("btn_edit"),
            command=self._on_edit_rank_score,
            style="Action.TButton",
        ).grid(row=3, column=0, sticky=tk.W)
        
        # Double-click to edit
        self.ranks_tree.bind('<Double-1>', lambda e: self._on_edit_rank_score())
        
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(2, weight=1)
    
    def _populate_ranks_tree(self) -> None:
        """Populate ranks treeview."""
        for item in self.ranks_tree.get_children():
            self.ranks_tree.delete(item)
        
        countries, rows, mismatch_found = self._build_rank_grid_model()
        if mismatch_found:
            self.rank_warning_label.grid()
        else:
            self.rank_warning_label.grid_remove()

        for row in rows:
            values = [
                self._format_rank_index_label(row["index"], row["mismatched"]),
                row["score"],
            ]
            for country in countries:
                values.append(row["names"].get(country, "—"))
            self.ranks_tree.insert('', tk.END, values=values)

    def _get_rank_countries(self) -> list[str]:
        ranks = self.config_data.get('ranks', {})
        if isinstance(ranks, dict):
            return list(ranks.keys())
        return []

    def _format_rank_index_label(self, index: int, mismatched: bool = False) -> str:
        label = self.tr.t("lbl_rank_index_format", index=index)
        if mismatched:
            return f"{label} ⚠"
        return label

    def _build_rank_grid_model(self) -> tuple[list[str], list[dict], bool]:
        ranks_by_country = self.config_data.get('ranks', {})
        if not isinstance(ranks_by_country, dict):
            return [], [], False

        if hasattr(self, "rank_country_columns"):
            countries = [country for _, country in self.rank_country_columns]
        else:
            countries = list(ranks_by_country.keys())
        max_len = max((len(rank_list) for rank_list in ranks_by_country.values()), default=0)
        rows = []
        mismatch_found = False

        for idx in range(max_len):
            scores = []
            names = {}

            for country in countries:
                rank_list = ranks_by_country.get(country, [])
                if idx < len(rank_list):
                    entry = rank_list[idx] or {}
                    score = entry.get('score', 0)
                    scores.append(score)
                    raw_name = entry.get('name', '')
                    names[country] = self.tr.translate_rank_name(raw_name, country)
                else:
                    names[country] = "—"

            mismatched = len({score for score in scores}) > 1
            if mismatched:
                mismatch_found = True

            rows.append({
                "index": idx,
                "score": scores[0] if scores else 0,
                "names": names,
                "mismatched": mismatched,
            })

        return countries, rows, mismatch_found
    
    def _create_campaigns_tab(self) -> None:
        """Create Campaigns tab."""
        frame = ttk.Frame(self.notebook, padding=20)
        self.notebook.add(frame, text=self.tr.t("tab_campaigns"))
        
        if not self.mission_dates_data:
            # Show disabled message
            ttk.Label(
                frame,
                text=self.tr.t("msg_campaigns_tab_disabled"),
                foreground='gray'
            ).pack(pady=50)
            return

        ttk.Label(
            frame,
            text=self.tr.t("lbl_import_stock_campaigns_helper"),
            foreground='gray',
            wraplength=520,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(0, 10))

        action_row = ttk.Frame(frame)
        action_row.pack(fill=tk.X, pady=(0, 12))

        import_icon = self._load_button_icon("tools/icons/import.png", "import")
        self._stock_import_btn = ttk.Button(
            action_row,
            text=self.tr.t("btn_import_stock_campaigns"),
            command=self._on_import_stock_campaigns,
            image=import_icon,
            compound=tk.LEFT,
            style="Action.TButton",
        )
        self._stock_import_btn.pack(side=tk.LEFT)

        ttk.Label(
            action_row,
            textvariable=self._stock_import_status_var,
            foreground='gray',
        ).pack(side=tk.LEFT, padx=(12, 0))

        rebuild_row = ttk.Frame(frame)
        rebuild_row.pack(fill=tk.X, pady=(0, 12))

        self._force_regen_btn = ttk.Button(
            rebuild_row,
            text=self.tr.t("btn_rebuild_campaign_data"),
            command=self._on_force_regen_campaigns,
            style="Action.TButton",
        )
        self._force_regen_btn.pack(side=tk.LEFT)

        ttk.Label(
            rebuild_row,
            textvariable=self._force_regen_status_var,
            foreground='gray',
        ).pack(side=tk.LEFT, padx=(12, 0))

        # Treeview
        columns = ('campaign', 'country', 'language', 'offset')
        self.campaigns_tree = ttk.Treeview(
            frame,
            columns=columns,
            show='headings',
            height=12
        )

        self.campaigns_tree.heading('campaign', text=self.tr.t("lbl_campaign_name"))
        self.campaigns_tree.heading('country', text=self.tr.t("lbl_country"))
        self.campaigns_tree.heading('language', text=self.tr.t("lbl_detail_page_language"))
        self.campaigns_tree.heading('offset', text=self.tr.t("lbl_starting_rank_offset"))
        self.campaigns_tree.column('campaign', width=220, anchor=tk.W)
        self.campaigns_tree.column('country', width=100, anchor=tk.CENTER)
        self.campaigns_tree.column('language', width=130, anchor=tk.CENTER)
        self.campaigns_tree.column('offset', width=130, anchor=tk.CENTER)
        
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.campaigns_tree.yview)
        self.campaigns_tree.configure(yscrollcommand=scrollbar.set)
        
        self.campaigns_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.LEFT, fill=tk.Y)
        
        # Populate
        self._populate_campaigns_tree()
        
        # Double-click to edit
        self.campaigns_tree.bind('<ButtonRelease-1>', self._on_campaigns_tree_click)
        self.campaigns_tree.bind('<Double-1>', self._on_campaigns_tree_double_click)
    
    def _populate_campaigns_tree(self) -> None:
        """Populate campaigns treeview."""
        if not self.mission_dates_data:
            return

        stock_campaigns = self._get_stock_campaigns_map_readonly() or {}

        for item in self.campaigns_tree.get_children():
            self.campaigns_tree.delete(item)

        for campaign_name, data in sorted(self.mission_dates_data.items()):
            # Skip if data is not a dict (shouldn't happen, but safety check)
            if not isinstance(data, dict):
                continue

            stock_key = self._resolve_stock_campaign_key(campaign_name, stock_campaigns) if stock_campaigns else None
            country = (
                stock_campaigns.get(stock_key)
                if stock_key
                else data.get('country', 'Unknown')
            )
            offset = data.get('starting_rank_offset', 0)

            # Get detail page language (translated display value)
            detail_locale = data.get('detail_page_locale')
            lang_key = self.DETAIL_PAGE_LOCALE_OPTIONS.get(detail_locale, "lbl_language_default")
            language_display = self.tr.t(lang_key)

            self.campaigns_tree.insert('', tk.END, values=(campaign_name, country, language_display, offset))

    def _set_stock_import_running(self, running: bool, status_text: str = "") -> None:
        """Update stock-campaign import UI state."""
        self._stock_import_status_var.set(status_text)
        if self._stock_import_btn is not None:
            self._stock_import_btn.config(state='disabled' if running else 'normal')

    def _choose_game_directory_for_stock_import(self) -> Optional[Path]:
        """Prompt for the IL-2 game directory, preferring the configured path."""
        initial_dir = ""
        configured = (self.mission_dates_data or {}).get('game_directory')
        if configured and os.path.isdir(str(configured)):
            initial_dir = str(configured)

        selected = filedialog.askdirectory(
            parent=self,
            title=self.tr.t("msg_stock_campaigns_select_directory"),
            initialdir=initial_dir or None,
            mustexist=True,
        )
        if not selected:
            return None

        game_dir = Path(selected)
        validate_game_directory(game_dir)
        return game_dir

    def _on_import_stock_campaigns(self) -> None:
        """Handle the stock-campaign import button."""
        if self._stock_import_thread is not None and self._stock_import_thread.is_alive():
            return

        try:
            game_dir = self._choose_game_directory_for_stock_import()
        except Exception as exc:
            messagebox.showerror(
                self.tr.t("msg_error_title"),
                self.tr.t("msg_stock_campaigns_invalid_directory", error=str(exc)),
                parent=self,
            )
            return

        if game_dir is None:
            return

        confirmed = messagebox.askyesno(
            self.tr.t("msg_confirm_title"),
            self.tr.t("msg_stock_campaigns_confirm", path=str(game_dir)),
            parent=self,
        )
        if not confirmed:
            return

        self._set_stock_import_running(True, self.tr.t("msg_stock_campaigns_import_running"))
        self._stock_import_thread = threading.Thread(
            target=self._run_stock_campaign_import_worker,
            args=(game_dir,),
            daemon=True,
        )
        self._stock_import_thread.start()
        if self._stock_import_poll_id is None:
            self._stock_import_poll_id = self.after(200, self._poll_stock_import_queue)

    def _run_stock_campaign_import_worker(self, game_dir: Path) -> None:
        """Run stock-campaign import off the Tk main thread."""
        try:
            result = import_stock_campaigns(game_dir)
            payload = {"status": "success", "result": result}
        except Exception as exc:
            winerror = getattr(exc, "winerror", None)
            if isinstance(exc, PermissionError) or winerror in (_ERROR_ELEVATION_REQUIRED, 5):
                payload = self._run_stock_campaign_import_elevated(game_dir)
            else:
                payload = {"status": "error", "error": str(exc)}
        self._stock_import_queue.put(payload)

    def _run_stock_campaign_import_elevated(self, game_dir: Path) -> Dict[str, Any]:
        """Retry stock-campaign import with elevation."""
        import tempfile

        try:
            with tempfile.NamedTemporaryFile(
                prefix="il2_stock_campaign_import_",
                suffix=".log",
                delete=False,
                mode="w",
            ) as log_file:
                log_path = log_file.name
            with tempfile.NamedTemporaryFile(
                prefix="il2_stock_campaign_import_",
                suffix=".json",
                delete=False,
                mode="w",
            ) as result_file:
                result_path = result_file.name
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

        if getattr(sys, "frozen", False):
            exe_path = sys.executable
            args = ["--import-stock-campaigns", str(game_dir), result_path]
            working_dir = str(Path(sys.executable).parent)
        else:
            exe_path = sys.executable
            args = [str(Path(__file__).with_name("main.py")), "--import-stock-campaigns", str(game_dir), result_path]
            working_dir = str(Path(__file__).resolve().parent.parent)

        success, exit_code, err = _run_elevated_windows(
            exe_path=exe_path,
            args=args,
            working_dir=working_dir,
            log_path=log_path,
            timeout_seconds=600,
        )

        if not success and err == "UAC_CANCELLED":
            return {"status": "cancelled"}
        if not success or exit_code != 0:
            detail = ""
            try:
                with open(log_path, encoding="utf-8", errors="replace") as handle:
                    detail = handle.read().strip()
            except Exception:
                pass
            return {"status": "error", "error": detail or err or self.tr.t("msg_stock_campaigns_import_failed_generic")}

        try:
            data = load_json(Path(result_path))
            result = StockCampaignImportResult(**data)
        except Exception as exc:
            return {"status": "error", "error": str(exc)}
        return {"status": "success", "result": result}

    def _poll_stock_import_queue(self) -> None:
        """Poll background stock-campaign import results."""
        try:
            payload = self._stock_import_queue.get_nowait()
        except queue.Empty:
            self._stock_import_poll_id = self.after(200, self._poll_stock_import_queue)
            return

        self._stock_import_poll_id = None
        self._set_stock_import_running(False, "")

        status = payload.get("status")
        if status == "success":
            result = payload["result"]
            messagebox.showinfo(
                self.tr.t("msg_confirm_title"),
                self._format_stock_campaign_import_summary(result),
                parent=self,
            )
        elif status == "cancelled":
            messagebox.showwarning(
                self.tr.t("msg_warning_title"),
                self.tr.t("msg_stock_campaigns_uac_cancelled"),
                parent=self,
            )
        else:
            messagebox.showerror(
                self.tr.t("msg_error_title"),
                self.tr.t(
                    "msg_stock_campaigns_import_failed",
                    error=payload.get("error", self.tr.t("msg_stock_campaigns_import_failed_generic")),
                ),
                parent=self,
            )

    def _format_stock_campaign_import_summary(self, result: StockCampaignImportResult) -> str:
        """Build a concise result message for stock-campaign import."""
        imported_count = len(result.imported_campaigns)
        updated_count = len(result.updated_campaigns)
        skipped_count = len(result.skipped_campaigns)

        imported_line = self.tr.t(
            "msg_stock_campaigns_summary_imported",
            count=imported_count,
            campaigns=", ".join(result.imported_campaigns) if result.imported_campaigns else self.tr.t("msg_stock_campaigns_summary_none"),
        )
        updated_line = self.tr.t(
            "msg_stock_campaigns_summary_updated",
            count=updated_count,
            campaigns=", ".join(result.updated_campaigns) if result.updated_campaigns else self.tr.t("msg_stock_campaigns_summary_none"),
        )
        skipped_line = self.tr.t(
            "msg_stock_campaigns_summary_skipped",
            count=skipped_count,
            campaigns=", ".join(result.skipped_campaigns) if result.skipped_campaigns else self.tr.t("msg_stock_campaigns_summary_none"),
        )

        return self.tr.t(
            "msg_stock_campaigns_import_success",
            imported_line=imported_line,
            updated_line=updated_line,
            skipped_line=skipped_line,
        )

    # === Force Regenerate Campaign Data ===

    def _set_force_regen_running(self, running: bool, status_text: str = "") -> None:
        self._force_regen_status_var.set(status_text)
        if self._force_regen_btn is not None:
            self._force_regen_btn.config(state='disabled' if running else 'normal')
        if self._stock_import_btn is not None:
            self._stock_import_btn.config(state='disabled' if running else 'normal')

    def _on_force_regen_campaigns(self) -> None:
        if self._force_regen_thread is not None and self._force_regen_thread.is_alive():
            return
        confirmed = messagebox.askyesno(
            self.tr.t("msg_confirm_title"),
            self.tr.t("msg_force_regen_confirm"),
            parent=self,
        )
        if not confirmed:
            return
        self._set_force_regen_running(True, self.tr.t("msg_force_regen_running"))
        self._force_regen_queue = queue.Queue()
        if self._force_regen_poll_id:
            self.after_cancel(self._force_regen_poll_id)
            self._force_regen_poll_id = None
        self._force_regen_start_time = time.monotonic()
        self._force_regen_thread = threading.Thread(
            target=self._run_force_regen_worker,
            daemon=True,
        )
        self._force_regen_thread.start()
        self._force_regen_poll_id = self.after(200, self._poll_force_regen_queue)

    def _run_force_regen_worker(self) -> None:
        locale = (self.settings_data or {}).get("locale") or "en"
        error = self._refresh_localized_artifacts(locale)
        self._force_regen_queue.put({"error": error})

    def _poll_force_regen_queue(self) -> None:
        try:
            payload = self._force_regen_queue.get_nowait()
        except queue.Empty:
            elapsed_s = int(time.monotonic() - self._force_regen_start_time)
            mm, ss = elapsed_s // 60, elapsed_s % 60
            base = self.tr.t("msg_force_regen_running")
            self._force_regen_status_var.set(f"{base} {mm:02d}:{ss:02d}")
            self._force_regen_poll_id = self.after(200, self._poll_force_regen_queue)
            return
        self._force_regen_poll_id = None
        error = payload.get("error")
        self._set_force_regen_running(False, "")
        if error:
            messagebox.showerror(
                self.tr.t("msg_error_title"),
                self.tr.t("msg_force_regen_failed", error=error),
                parent=self,
            )
        else:
            messagebox.showinfo(
                self.tr.t("msg_confirm_title"),
                self.tr.t("msg_force_regen_success"),
                parent=self,
            )

    # === Career Language Settings Tab ===

    def _create_career_languages_tab(self) -> None:
        """Create Career Language Settings tab."""
        frame = ttk.Frame(self.notebook, padding=20)
        self.notebook.add(frame, text=self.tr.t("tab_career_languages"))

        # Helper description
        ttk.Label(
            frame,
            text=self.tr.t("lbl_career_languages_helper"),
            foreground='gray',
            wraplength=500,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(0, 10))

        careers = self._load_careers_from_db()

        if careers is None:
            # cp.db not found or game_dir unavailable
            ttk.Label(
                frame,
                text=self.tr.t("msg_career_db_not_found"),
                foreground='gray',
            ).pack(pady=50)
            return

        if not careers:
            # db accessible but no careers yet
            ttk.Label(
                frame,
                text=self.tr.t("msg_no_careers"),
                foreground='gray',
            ).pack(pady=50)
            return

        # Treeview
        columns = ('pilot', 'language')
        self.career_lang_tree = ttk.Treeview(
            frame, columns=columns, show='headings', height=12
        )
        self.career_lang_tree.heading('pilot',    text=self.tr.t("lbl_career_pilot"))
        self.career_lang_tree.heading('language', text=self.tr.t("lbl_detail_page_language"))
        self.career_lang_tree.column('pilot',    width=300, anchor=tk.W)
        self.career_lang_tree.column('language', width=160, anchor=tk.CENTER)

        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL,
                                   command=self.career_lang_tree.yview)
        self.career_lang_tree.configure(yscrollcommand=scrollbar.set)
        self.career_lang_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.LEFT, fill=tk.Y)

        self._career_list_cache = careers
        self._populate_career_lang_tree()
        self.career_lang_tree.bind('<ButtonRelease-1>', self._on_career_lang_tree_click)

    def _load_careers_from_db(self) -> Optional[List[Tuple[int, str]]]:
        """
        Query cp.db for all root careers (extends = -1).

        Returns:
            List of (root_career_id, pilot_display_name) sorted by id DESC,
            None if game_dir cannot be determined or cp.db is missing,
            [] if the db is present but contains no careers.
        """
        game_dir = (self.mission_dates_data or {}).get('game_directory')
        if not game_dir or not os.path.isdir(str(game_dir)):
            return None

        db_path = os.path.join(str(game_dir), 'data', 'Career', 'cp.db')
        if not os.path.isfile(db_path):
            return None

        try:
            uri = f"file:{db_path}?mode=ro"
            con = sqlite3.connect(uri, uri=True, timeout=5)
            con.row_factory = sqlite3.Row
            cur = con.execute(
                """
                SELECT c.id,
                       COALESCE(p.name, '') || ' ' || COALESCE(p.lastName, '') AS pilot_name
                FROM career c
                JOIN pilot p ON c.playerId = p.id
                WHERE c.extends = -1
                ORDER BY c.id DESC
                """
            )
            rows = cur.fetchall()
            con.close()
            return [
                (row['id'], row['pilot_name'].strip() or f"Career {row['id']}")
                for row in rows
            ]
        except Exception as exc:
            logger.warning("Could not read cp.db for career list: %s", exc)
            return []

    def _populate_career_lang_tree(self) -> None:
        """Populate the career language treeview from settings_data."""
        overrides = self.settings_data.get('careerLanguageOverrides', {})
        for item in self.career_lang_tree.get_children():
            self.career_lang_tree.delete(item)
        for career_id, pilot_name in self._career_list_cache:
            stored = overrides.get(str(career_id))
            lang_key = self.CAREER_LOCALE_OPTIONS.get(stored, "lbl_language_default")
            self.career_lang_tree.insert(
                '', tk.END,
                iid=str(career_id),
                values=(pilot_name, self.tr.t(lang_key)),
            )

    def _on_career_lang_tree_click(self, event: tk.Event) -> None:
        """Handle single click for career language editing."""
        region = self.career_lang_tree.identify("region", event.x, event.y)
        if region != "cell":
            self._destroy_career_lang_editor()
            return
        column = self.career_lang_tree.identify_column(event.x)
        item   = self.career_lang_tree.identify_row(event.y)
        if not item:
            self._destroy_career_lang_editor()
            return
        if column == "#2":
            self._start_career_lang_edit(item)
        else:
            self._destroy_career_lang_editor()

    def _start_career_lang_edit(self, item: str) -> None:
        """Begin inline editing of a career's language override."""
        self._destroy_career_lang_editor()
        values = self.career_lang_tree.item(item, 'values')
        if not values:
            return
        current_display = values[1]
        bbox = self.career_lang_tree.bbox(item, "#2")
        if not bbox:
            return
        x, y, width, height = bbox

        options = [self.tr.t(k) for k in self.CAREER_LOCALE_OPTIONS.values()]
        editor = ttk.Combobox(self.career_lang_tree, values=options, state='readonly')
        editor.set(current_display if current_display in options else options[0])
        editor.place(x=x, y=y, width=width, height=height)
        editor.focus_set()
        editor.bind(
            "<<ComboboxSelected>>",
            lambda e: self._on_career_lang_selected(item, editor.get()),
        )
        editor.bind("<FocusOut>", lambda e: self._destroy_career_lang_editor())
        editor.bind("<Escape>",   lambda e: self._destroy_career_lang_editor())
        self._career_lang_editor = editor
        self._career_lang_editor_item = item

    def _destroy_career_lang_editor(self) -> None:
        """Destroy any active career language editor."""
        if self._career_lang_editor is not None:
            self._career_lang_editor.destroy()
        self._career_lang_editor = None
        self._career_lang_editor_item = None

    def _on_career_lang_selected(self, item: str, selected_display: str) -> None:
        """Persist career language selection to settings_data."""
        self._destroy_career_lang_editor()
        if not selected_display:
            return

        # Convert display text back to stored value (None, 'en', 'de', 'ru')
        stored_value = None
        for locale_val, key in self.CAREER_LOCALE_OPTIONS.items():
            if self.tr.t(key) == selected_display:
                stored_value = locale_val
                break

        # item is the iid which equals str(career_id)
        overrides = self.settings_data.setdefault('careerLanguageOverrides', {})
        if stored_value is None:
            overrides.pop(item, None)
        else:
            overrides[item] = stored_value
        self._populate_career_lang_tree()

    # ------------------------------------------------------------------
    # Tab 6: German Awards
    # ------------------------------------------------------------------

    def _get_german_awards_dir(self):
        """
        Return the CampaignRanksAwards Path for the current game_dir, or None.
        """
        from settings_manager.german_awards import get_awards_dir
        game_dir = (self.mission_dates_data or {}).get('game_directory')
        if not game_dir or not os.path.isdir(str(game_dir)):
            return None
        return get_awards_dir(Path(game_dir))

    def _create_german_awards_tab(self) -> None:
        """Create German Awards style-switcher tab."""
        frame = ttk.Frame(self.notebook, padding=20)
        self.notebook.add(frame, text=self.tr.t("tab_german_awards"))

        from settings_manager.german_awards import (
            detect_current_style, has_alternate_folders,
            STYLE_1957, STYLE_WW2,
        )

        awards_dir = self._get_german_awards_dir()

        # --- helper text -------------------------------------------------------
        ttk.Label(
            frame,
            text=self.tr.t("lbl_german_awards_helper"),
            foreground='gray',
            wraplength=520,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(0, 16))

        # --- German imagery (flag + background): censored vs uncensored ---------
        ttk.Separator(frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(0, 12))

        img_frame = ttk.LabelFrame(frame, text="German flag and background image", padding=12)
        img_frame.pack(anchor=tk.W, pady=(0, 12))

        _current_uncensored = bool((self.settings_data or {}).get("german_uncensored", False))
        self._german_uncensored_var = tk.BooleanVar(value=_current_uncensored)

        ttk.Radiobutton(
            img_frame,
            text="Censored (default — uses game-style Iron Cross flag)",
            variable=self._german_uncensored_var,
            value=False,
        ).pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(
            img_frame,
            text="Uncensored (historical insignia — Swastika flag and background)",
            variable=self._german_uncensored_var,
            value=True,
        ).pack(anchor=tk.W, pady=2)

        ttk.Button(
            frame,
            text="Apply",
            command=self._on_apply_german_uncensored,
            style="Action.TButton",
        ).pack(anchor=tk.W, pady=(0, 16))

        ttk.Separator(frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(0, 16))

        # --- unavailable states ------------------------------------------------
        if awards_dir is None:
            ttk.Label(
                frame,
                text=self.tr.t("msg_german_awards_not_available"),
                foreground='gray',
                wraplength=520,
                justify=tk.LEFT,
            ).pack(pady=40)
            return

        if not has_alternate_folders(awards_dir):
            ttk.Label(
                frame,
                text=self.tr.t("msg_german_awards_folders_missing"),
                foreground='gray',
                wraplength=520,
                justify=tk.LEFT,
            ).pack(pady=40)
            return

        # --- current style detection -------------------------------------------
        current = detect_current_style(awards_dir)

        # --- status row --------------------------------------------------------
        status_row = ttk.Frame(frame)
        status_row.pack(anchor=tk.W, pady=(0, 16))

        ttk.Label(
            status_row,
            text=self.tr.t("lbl_german_awards_current"),
            font=("TkDefaultFont", 9, "bold"),
        ).pack(side=tk.LEFT)

        self._german_awards_status_var = tk.StringVar()
        ttk.Label(
            status_row,
            textvariable=self._german_awards_status_var,
        ).pack(side=tk.LEFT, padx=(6, 0))

        # --- radio buttons -----------------------------------------------------
        self._german_awards_var = tk.StringVar(
            value=STYLE_WW2 if current == STYLE_1957 else STYLE_1957
        )

        radio_frame = ttk.LabelFrame(frame, padding=12)
        radio_frame.pack(anchor=tk.W, pady=(0, 12))

        self._german_awards_radio_1957 = ttk.Radiobutton(
            radio_frame,
            text=self.tr.t("lbl_radio_use_1957"),
            variable=self._german_awards_var,
            value=STYLE_1957,
        )
        self._german_awards_radio_1957.pack(anchor=tk.W, pady=4)

        self._german_awards_radio_ww2 = ttk.Radiobutton(
            radio_frame,
            text=self.tr.t("lbl_radio_use_ww2"),
            variable=self._german_awards_var,
            value=STYLE_WW2,
        )
        self._german_awards_radio_ww2.pack(anchor=tk.W, pady=4)

        # --- elevation note ----------------------------------------------------
        ttk.Label(
            frame,
            text=self.tr.t("lbl_german_awards_elevation_note"),
            foreground='gray',
            wraplength=520,
            justify=tk.LEFT,
            font=("TkDefaultFont", 8),
        ).pack(anchor=tk.W, pady=(0, 12))

        # --- swap button -------------------------------------------------------
        self._german_awards_swap_btn = ttk.Button(
            frame,
            text=self.tr.t("btn_swap_award_style"),
            command=self._on_swap_german_awards,
            style="Action.TButton",
        )
        self._german_awards_swap_btn.pack(anchor=tk.W)

        # Apply initial state to widgets
        self._refresh_german_awards_ui(current)

    def _refresh_german_awards_ui(self, current_style: Optional[str]) -> None:
        """Update status label and radio enabled/disabled states."""
        from settings_manager.german_awards import STYLE_1957, STYLE_WW2

        if self._german_awards_status_var is None:
            return

        if current_style == STYLE_1957:
            label = self.tr.t("lbl_german_awards_style_1957")
        elif current_style == STYLE_WW2:
            label = self.tr.t("lbl_german_awards_style_ww2")
        else:
            label = self.tr.t("lbl_german_awards_style_unknown")

        self._german_awards_status_var.set(label)

        # Disable the radio for the currently active style; enable the other
        if self._german_awards_radio_1957 and self._german_awards_radio_ww2:
            if current_style == STYLE_1957:
                self._german_awards_radio_1957.config(state='disabled')
                self._german_awards_radio_ww2.config(state='normal')
                self._german_awards_var.set(STYLE_WW2)
            elif current_style == STYLE_WW2:
                self._german_awards_radio_ww2.config(state='disabled')
                self._german_awards_radio_1957.config(state='normal')
                self._german_awards_var.set(STYLE_1957)
            else:
                # Ambiguous – disable both and the swap button
                self._german_awards_radio_1957.config(state='disabled')
                self._german_awards_radio_ww2.config(state='disabled')
                if self._german_awards_swap_btn:
                    self._german_awards_swap_btn.config(state='disabled')

    def _on_apply_german_uncensored(self) -> None:
        """Save the censored/uncensored German imagery preference."""
        if self._german_uncensored_var is None:
            return
        val = bool(self._german_uncensored_var.get())
        if self.settings_data is None:
            self.settings_data = {}
        self.settings_data["german_uncensored"] = val
        save_json_atomic(SETTINGS_JSON_PATH, self.settings_data)
        messagebox.showinfo(
            "German imagery",
            "Setting saved.\nRestart the Career / Campaign Service Record to apply.",
            parent=self,
        )

    def _on_swap_german_awards(self) -> None:
        """Handle the Swap Award Style button."""
        import ctypes
        import tempfile
        from settings_manager.german_awards import (
            detect_current_style, perform_swap, STYLE_1957, STYLE_WW2,
        )

        awards_dir = self._get_german_awards_dir()
        if awards_dir is None:
            return

        target = self._german_awards_var.get() if self._german_awards_var else None
        if target not in (STYLE_1957, STYLE_WW2):
            return

        style_label = (
            self.tr.t("lbl_german_awards_style_1957")
            if target == STYLE_1957
            else self.tr.t("lbl_german_awards_style_ww2")
        )

        confirmed = messagebox.askyesno(
            self.tr.t("msg_confirm_title"),
            self.tr.t("msg_german_awards_swap_confirm", style=style_label),
            parent=self,
        )
        if not confirmed:
            return

        # --- check elevation ---------------------------------------------------
        try:
            already_admin = bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            already_admin = False

        if already_admin:
            # Run directly in-process
            try:
                perform_swap(awards_dir, target)
                new_style = detect_current_style(awards_dir)
                self._refresh_german_awards_ui(new_style)
                messagebox.showinfo(
                    self.tr.t("msg_confirm_title"),
                    self.tr.t("msg_german_awards_swap_success", style=style_label),
                    parent=self,
                )
            except Exception as exc:
                messagebox.showerror(
                    self.tr.t("msg_error_title"),
                    self.tr.t("msg_german_awards_swap_failed", error=str(exc)),
                    parent=self,
                )
            return

        # --- elevation required: relaunch exe with swap argument ---------------
        try:
            with tempfile.NamedTemporaryFile(
                prefix="il2_award_swap_", suffix=".log",
                delete=False, mode='w',
            ) as lf:
                log_path = lf.name
        except Exception:
            log_path = str(Path(sys.executable).parent / "_award_swap.log")

        success, exit_code, err = _run_elevated_windows(
            exe_path=sys.executable,
            args=["--swap-german-awards", target, str(awards_dir)],
            working_dir=str(Path(sys.executable).parent),
            log_path=log_path,
            timeout_seconds=60,
        )

        if not success and err == "UAC_CANCELLED":
            messagebox.showwarning(
                self.tr.t("msg_warning_title"),
                self.tr.t("msg_german_awards_uac_cancelled"),
                parent=self,
            )
            return

        if not success or exit_code != 0:
            # Try to read any error output from the log file
            detail = ""
            try:
                with open(log_path, encoding="utf-8", errors="replace") as lf:
                    detail = lf.read().strip()
            except Exception:
                pass
            messagebox.showerror(
                self.tr.t("msg_error_title"),
                self.tr.t("msg_german_awards_swap_failed",
                           error=detail or self.tr.t("msg_german_awards_elevation_failed")),
                parent=self,
            )
            return

        # Swap succeeded – refresh the UI to reflect the new state
        new_style = detect_current_style(awards_dir)
        self._refresh_german_awards_ui(new_style)
        messagebox.showinfo(
            self.tr.t("msg_confirm_title"),
            self.tr.t("msg_german_awards_swap_success", style=style_label),
            parent=self,
        )

    # ------------------------------------------------------------------
    # Tab 7: Updates
    # ------------------------------------------------------------------

    def _create_updates_tab(self) -> None:
        """Create the Update Installer tab."""
        from settings_manager.updater import read_current_version
        from settings_manager.config.paths import get_base_dir

        outer = ttk.Frame(self.notebook, padding=20)
        self.notebook.add(outer, text=self.tr.t("tab_updates"))

        # --- startup notice (applied / pending) ---------------------------
        from settings_manager.updater import RESTART_PENDING_FILENAME
        base_dir = get_base_dir()
        applied_marker = base_dir / "_update_applied"
        restart_sentinel = base_dir / RESTART_PENDING_FILENAME

        if applied_marker.exists():
            tk.Label(
                outer,
                text=self.tr.t("lbl_update_applied_notice"),
                background="#d4edda",
                foreground="#155724",
                font=("TkDefaultFont", 9, "bold"),
                padx=10,
                pady=6,
                anchor=tk.W,
                justify=tk.LEFT,
            ).pack(fill=tk.X, pady=(0, 12))
            try:
                applied_marker.unlink()
            except Exception:
                pass
        elif restart_sentinel.exists():
            try:
                pending_rel = json.loads(restart_sentinel.read_text(encoding="utf-8"))
            except Exception:
                pending_rel = []
            if pending_rel:
                pending_frame = tk.Frame(outer, background="#fff3cd")
                pending_frame.pack(fill=tk.X, pady=(0, 12))
                tk.Label(
                    pending_frame,
                    text=self.tr.t("lbl_update_pending_notice"),
                    background="#fff3cd",
                    foreground="#856404",
                    font=("TkDefaultFont", 9, "bold"),
                    padx=10,
                    pady=6,
                    anchor=tk.W,
                    justify=tk.LEFT,
                    wraplength=420,
                ).pack(side=tk.LEFT, fill=tk.X, expand=True)
                tk.Button(
                    pending_frame,
                    text=self.tr.t("btn_restart_and_apply"),
                    command=lambda pr=pending_rel: self._apply_pending_update_and_restart(pr),
                    background="#e07b00",
                    foreground="white",
                    activebackground="#c06800",
                    activeforeground="white",
                    font=("TkDefaultFont", 9, "bold"),
                    relief=tk.RAISED,
                    padx=10,
                    pady=4,
                    cursor="hand2",
                ).pack(side=tk.RIGHT, padx=10, pady=6)

        # --- helper text --------------------------------------------------
        ttk.Label(
            outer,
            text=self.tr.t("lbl_updates_helper"),
            foreground="gray",
            wraplength=520,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(0, 14))

        # --- current version row ------------------------------------------
        ver_frame = ttk.Frame(outer)
        ver_frame.pack(anchor=tk.W, pady=(0, 4))
        ttk.Label(ver_frame, text=self.tr.t("lbl_current_version")).pack(side=tk.LEFT)
        cur_ver = read_current_version(get_base_dir()) or self.tr.t("lbl_version_unknown")
        ttk.Label(ver_frame, text=cur_ver, font=("TkDefaultFont", 9, "bold")).pack(
            side=tk.LEFT, padx=(6, 0)
        )

        # --- update-version row (hidden until zip selected) ---------------
        new_ver_frame = ttk.Frame(outer)
        new_ver_frame.pack(anchor=tk.W, pady=(0, 12))
        ttk.Label(new_ver_frame, text=self.tr.t("lbl_update_version")).pack(side=tk.LEFT)
        ttk.Label(
            new_ver_frame,
            textvariable=self._update_new_version_var,
            font=("TkDefaultFont", 9, "bold"),
        ).pack(side=tk.LEFT, padx=(6, 0))

        ttk.Separator(outer, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(0, 14))

        # --- select package button ----------------------------------------
        btn_row = ttk.Frame(outer)
        btn_row.pack(anchor=tk.W, pady=(0, 10))
        ttk.Button(
            btn_row,
            text=self.tr.t("btn_select_update_package"),
            command=self._on_select_update_package,
            style="Action.TButton",
        ).pack(side=tk.LEFT)

        # selected zip filename label
        ttk.Label(
            btn_row,
            textvariable=self._update_zip_label_var,
            foreground="gray",
        ).pack(side=tk.LEFT, padx=(10, 0))

        # --- restore backup button ----------------------------------------
        restore_row = ttk.Frame(outer)
        restore_row.pack(anchor=tk.W, pady=(0, 10))
        ttk.Button(
            restore_row,
            text=self.tr.t("btn_restore_backup"),
            command=self._on_restore_backup,
            style="Action.TButton",
        ).pack(side=tk.LEFT)
        ttk.Label(
            restore_row,
            text=self.tr.t("lbl_restore_backup_helper"),
            foreground="gray",
        ).pack(side=tk.LEFT, padx=(10, 0))

        # --- manifest / file list (hidden until zip loaded) ---------------
        self._update_manifest_frame = ttk.Frame(outer)
        # (packed later when a valid zip is loaded)

        # Running-process warning
        self._update_proc_warn_label = ttk.Label(
            self._update_manifest_frame,
            textvariable=self._update_proc_warn_var,
            foreground="#cc0000",
            wraplength=520,
            justify=tk.LEFT,
        )
        self._update_proc_warn_label.pack(anchor=tk.W, pady=(0, 8))

        # File list tree
        tree_frame = ttk.Frame(self._update_manifest_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        cols = ("file", "status")
        self._update_tree = ttk.Treeview(
            tree_frame,
            columns=cols,
            show="headings",
            height=10,
            selectmode="none",
        )
        self._update_tree.heading("file",   text=self.tr.t("lbl_col_update_file"))
        self._update_tree.heading("status", text=self.tr.t("lbl_col_update_status"))
        self._update_tree.column("file",   width=420, stretch=True)
        self._update_tree.column("status", width=100, stretch=False, anchor=tk.CENTER)

        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self._update_tree.yview)
        self._update_tree.configure(yscrollcommand=vsb.set)
        self._update_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        # Install button
        install_row = ttk.Frame(self._update_manifest_frame)
        install_row.pack(anchor=tk.W, pady=(4, 0))
        self._update_install_btn = ttk.Button(
            install_row,
            text=self.tr.t("btn_install_update"),
            command=self._on_install_update,
            state="disabled",
            style="Action.TButton",
        )
        self._update_install_btn.pack(side=tk.LEFT)

        # --- progress area (hidden until install starts) ------------------
        self._update_progress_frame = ttk.Frame(outer)
        # (packed later)

        self._update_progress_bar = ttk.Progressbar(
            self._update_progress_frame,
            variable=self._update_progress_var,
            maximum=100,
            length=500,
        )
        self._update_progress_bar.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(
            self._update_progress_frame,
            textvariable=self._update_status_var,
            foreground="gray",
        ).pack(anchor=tk.W)

        # --- post-install buttons (not packed until install completes) ------
        self._update_post_install_row = ttk.Frame(outer)
        # children packed into this row by _poll_update_queue after install

        self._update_log_btn = ttk.Button(
            self._update_post_install_row,
            text=self.tr.t("btn_view_install_log"),
            command=self._on_view_install_log,
            style="Action.TButton",
        )

        self._update_restart_btn = tk.Button(
            self._update_post_install_row,
            text=self.tr.t("btn_restart_and_apply"),
            command=self._on_restart_and_apply,
            background="#e07b00",
            foreground="white",
            activebackground="#c06800",
            activeforeground="white",
            font=("TkDefaultFont", 9, "bold"),
            relief=tk.RAISED,
            padx=10,
            pady=4,
            cursor="hand2",
        )

    # -- Update tab helpers ------------------------------------------------

    def _on_select_update_package(self) -> None:
        """Open file dialog, parse the selected zip, populate the manifest UI."""
        from settings_manager.updater import (
            parse_zip, detect_running_trackers, UpdateManifest,
        )
        from settings_manager.config.paths import get_base_dir

        zip_path = filedialog.askopenfilename(
            parent=self,
            title=self.tr.t("msg_update_select_zip"),
            filetypes=[("Zip files", "*.zip"), ("All files", "*.*")],
        )
        if not zip_path:
            return

        zip_path = Path(zip_path)
        self._update_zip_label_var.set(zip_path.name)

        # Parse
        manifest, entries, error = parse_zip(zip_path, get_base_dir())
        if error or manifest is None:
            messagebox.showerror(
                self.tr.t("msg_error_title"),
                self.tr.t("msg_update_invalid_zip", error=error or "Unknown error"),
                parent=self,
            )
            self._update_zip_path = None
            self._update_manifest_frame.pack_forget()
            return

        if not entries:
            messagebox.showwarning(
                self.tr.t("msg_warning_title"),
                self.tr.t("msg_update_no_files"),
                parent=self,
            )
            self._update_zip_path = None
            self._update_manifest_frame.pack_forget()
            return

        self._update_zip_path = zip_path
        self._update_manifest = manifest
        self._update_entries = entries

        # Version label
        self._update_new_version_var.set(
            manifest.version or self.tr.t("lbl_version_unknown")
        )

        # Running-process check
        running = detect_running_trackers()
        if running:
            self._update_proc_warn_var.set(
                self.tr.t("msg_update_running_procs", names=", ".join(running))
            )
            self._update_proc_warn_label.pack(anchor=tk.W, pady=(0, 8))
        else:
            self._update_proc_warn_var.set("")
            self._update_proc_warn_label.pack_forget()

        # Populate file tree
        self._update_tree.delete(*self._update_tree.get_children())
        installable = 0
        for entry in entries:
            if entry.is_protected:
                status_text = self.tr.t("lbl_update_status_protected")
                tag = "protected"
            elif entry.is_new:
                status_text = self.tr.t("lbl_update_status_new")
                tag = "new"
                installable += 1
            else:
                status_text = self.tr.t("lbl_update_status_updated")
                tag = "update"
                installable += 1
            self._update_tree.insert(
                "", tk.END, values=(entry.dest_path, status_text), tags=(tag,)
            )

        self._update_tree.tag_configure("new",       foreground="#006600")
        self._update_tree.tag_configure("update",    foreground="#000000")
        self._update_tree.tag_configure("protected", foreground="#999999")

        # Enable install button only if there is something to install and
        # no blocking running processes.
        can_install = installable > 0 and not running
        self._update_install_btn.config(state="normal" if can_install else "disabled")

        # Show manifest frame
        self._update_manifest_frame.pack(fill=tk.BOTH, expand=True, pady=(4, 0))

    def _on_install_update(self) -> None:
        """Confirm and kick off the background install worker."""
        if not self._update_zip_path or not self._update_entries:
            return

        manifest = self._update_manifest
        installable = [e for e in self._update_entries if not e.is_protected]
        version_str = (manifest.version if manifest else "") or self.tr.t("lbl_version_unknown")

        confirmed = messagebox.askyesno(
            self.tr.t("msg_update_confirm_title"),
            self.tr.t(
                "msg_update_confirm",
                version=version_str,
                count=len(installable),
            ),
            parent=self,
        )
        if not confirmed:
            return

        # Disable the install button to prevent double-clicks.
        if self._update_install_btn:
            self._update_install_btn.config(state="disabled")

        # Show progress area
        self._update_progress_var.set(0)
        self._update_status_var.set(self.tr.t("msg_update_preparing"))
        self._update_progress_frame.pack(fill=tk.X, pady=(10, 0))

        # Launch background thread
        self._update_thread = threading.Thread(
            target=self._run_install_worker,
            daemon=True,
        )
        self._update_thread.start()
        self._poll_update_queue()

    def _run_install_worker(self) -> None:
        """Background thread: runs install_update and posts result to queue."""
        from settings_manager.updater import install_update, write_install_log
        from settings_manager.config.paths import get_base_dir

        base_dir = get_base_dir()
        total_installable = len([e for e in self._update_entries if not e.is_protected])

        def _progress(current: int, total: int, filename: str) -> None:
            pct = int(current / total * 100) if total else 100
            self._update_queue.put({
                "type": "progress",
                "pct": pct,
                "label": self.tr.t(
                    "msg_update_installing_file",
                    current=current,
                    total=total,
                    file=os.path.basename(filename),
                ),
            })

        try:
            result = install_update(
                self._update_zip_path,
                base_dir,
                self._update_entries,
                progress_callback=_progress,
            )
            log_path = write_install_log(
                base_dir,
                self._update_zip_path,
                self._update_manifest or __import__(
                    "settings_manager.updater", fromlist=["UpdateManifest"]
                ).UpdateManifest(),
                result,
            )
            self._update_queue.put({
                "type": "done",
                "result": result,
                "log_path": log_path,
            })
        except Exception as exc:
            self._update_queue.put({"type": "error", "error": str(exc)})

    def _poll_update_queue(self) -> None:
        """Poll the install queue and update the UI."""
        try:
            payload = self._update_queue.get_nowait()
        except queue.Empty:
            self._update_poll_id = self.after(150, self._poll_update_queue)
            return

        kind = payload.get("type")

        if kind == "progress":
            self._update_progress_var.set(payload["pct"])
            self._update_status_var.set(payload["label"])
            self._update_poll_id = self.after(150, self._poll_update_queue)
            return

        # Terminal states: done or error
        if kind == "done":
            result = payload["result"]
            mode = payload.get("mode", "install")
            log_path = payload.get("log_path")
            self._update_progress_var.set(100)

            if mode == "restore":
                if result.success:
                    self._update_status_var.set(self.tr.t("msg_restore_done"))
                    messagebox.showinfo(
                        self.tr.t("msg_restore_confirm_title"),
                        self.tr.t("msg_restore_success", count=len(result.installed)),
                        parent=self,
                    )
                    if result.pending_restart:
                        self._update_pending_files = result.pending_restart
                        self._update_post_install_row.pack(anchor=tk.W, pady=(10, 0))
                        self._update_restart_btn.pack(side=tk.LEFT, padx=(8, 0))
                else:
                    failed_lines = "\n".join(
                        f"  • {f}: {err}" for f, err in result.failed[:8]
                    )
                    self._update_status_var.set(self.tr.t("msg_update_done_failed"))
                    messagebox.showerror(
                        self.tr.t("msg_error_title"),
                        self.tr.t("msg_restore_failed",
                            count=len(result.failed),
                            details=failed_lines,
                        ),
                        parent=self,
                    )
                return

            # --- install mode ---
            if result.success:
                backup_note = ""
                if result.backup_path:
                    backup_note = "\n\n" + self.tr.t(
                        "msg_update_backup_created", path=result.backup_path
                    )
                self._update_status_var.set(self.tr.t("msg_update_done_success"))
                messagebox.showinfo(
                    self.tr.t("msg_update_confirm_title"),
                    self.tr.t(
                        "msg_update_success",
                        count=len(result.installed),
                    ) + backup_note,
                    parent=self,
                )
                # Show post-install button row below the progress area
                self._update_post_install_row.pack(anchor=tk.W, pady=(10, 0))
                if log_path:
                    self._update_log_path = Path(log_path)
                    self._update_log_btn.pack(side=tk.LEFT)
                if result.pending_restart:
                    self._update_pending_files = result.pending_restart
                    self._update_restart_btn.pack(side=tk.LEFT, padx=(8, 0))
            else:
                failed_lines = "\n".join(
                    f"  • {f}: {err}" for f, err in result.failed[:8]
                )
                if len(result.failed) > 8:
                    failed_lines += f"\n  … and {len(result.failed) - 8} more"
                self._update_status_var.set(self.tr.t("msg_update_done_failed"))
                messagebox.showerror(
                    self.tr.t("msg_error_title"),
                    self.tr.t(
                        "msg_update_partial",
                        installed=len(result.installed),
                        failed=len(result.failed),
                        details=failed_lines,
                    ),
                    parent=self,
                )

        elif kind == "error":
            self._update_status_var.set(self.tr.t("msg_update_done_failed"))
            messagebox.showerror(
                self.tr.t("msg_error_title"),
                self.tr.t("msg_update_failed", error=payload.get("error", "")),
                parent=self,
            )

    def _on_view_install_log(self) -> None:
        """Open update_log.txt in the default text editor."""
        if not self._update_log_path or not self._update_log_path.exists():
            return
        try:
            os.startfile(str(self._update_log_path))
        except Exception as exc:
            messagebox.showerror(
                self.tr.t("msg_error_title"),
                str(exc),
                parent=self,
            )

    def _on_restore_backup(self) -> None:
        """Open a backup zip and restore its files, undoing a previous update."""
        from settings_manager.config.paths import get_base_dir

        base_dir = get_base_dir()
        backups_dir = base_dir / "backups"

        if not backups_dir.exists() or not any(backups_dir.glob("*.zip")):
            messagebox.showinfo(
                self.tr.t("msg_restore_confirm_title"),
                self.tr.t("msg_restore_no_backups"),
                parent=self,
            )
            return

        zip_path_str = filedialog.askopenfilename(
            parent=self,
            title=self.tr.t("msg_restore_select_zip"),
            initialdir=str(backups_dir),
            filetypes=[("Zip files", "*.zip"), ("All files", "*.*")],
        )
        if not zip_path_str:
            return

        zip_path = Path(zip_path_str)
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                count = sum(1 for n in zf.namelist() if not n.endswith("/"))
        except Exception as exc:
            messagebox.showerror(self.tr.t("msg_error_title"), str(exc), parent=self)
            return

        if not messagebox.askyesno(
            self.tr.t("msg_restore_confirm_title"),
            self.tr.t("msg_restore_confirm", count=count, name=zip_path.name),
            parent=self,
        ):
            return

        self._restore_zip_path = zip_path
        self._update_status_var.set(self.tr.t("msg_update_preparing"))
        self._update_progress_var.set(0)
        self._update_progress_frame.pack(fill=tk.X, pady=(10, 0))

        self._update_thread = threading.Thread(
            target=self._run_restore_worker,
            daemon=True,
        )
        self._update_thread.start()
        self._poll_update_queue()

    def _run_restore_worker(self) -> None:
        """Background thread: runs restore_backup and posts result to queue."""
        from settings_manager.updater import restore_backup
        from settings_manager.config.paths import get_base_dir

        base_dir = get_base_dir()

        def _progress(current: int, total: int, filename: str) -> None:
            pct = int(current / total * 100) if total else 100
            self._update_queue.put({
                "type": "progress",
                "pct": pct,
                "label": self.tr.t(
                    "msg_update_installing_file",
                    current=current,
                    total=total,
                    file=os.path.basename(filename),
                ),
            })

        try:
            result = restore_backup(
                self._restore_zip_path,
                base_dir,
                progress_callback=_progress,
            )
            self._update_queue.put({
                "type": "done",
                "mode": "restore",
                "result": result,
            })
        except Exception as exc:
            self._update_queue.put({"type": "error", "error": str(exc)})

    def _on_restart_and_apply(self) -> None:
        """Called by the post-install Restart & Apply button."""
        self._apply_pending_update_and_restart(self._update_pending_files)

    def _apply_pending_update_and_restart(self, pending_files: List[str]) -> None:
        """
        Launch a cmd.exe batch script that waits a few seconds for this process
        to exit, moves each .pending file over the real destination, then relaunches.
        """
        from settings_manager.config.paths import get_base_dir
        import tempfile

        if not getattr(sys, "frozen", False):
            messagebox.showinfo(
                self.tr.t("msg_update_confirm_title"),
                "Restart & Apply is only available when running the installed version.",
                parent=self,
            )
            return

        from settings_manager.updater import RESTART_PENDING_FILENAME
        exe_path = Path(sys.executable)
        base_dir = get_base_dir()
        marker_path = base_dir / "_update_applied"
        sentinel_path = base_dir / RESTART_PENDING_FILENAME

        move_lines: list[str] = []
        for rel_path in pending_files:
            dest = base_dir / rel_path
            pending = dest.with_suffix(dest.suffix + ".pending")
            move_lines.append(f'move /Y "{pending}" "{dest}"')

        moves_bat = "\r\n".join(move_lines)

        bat_script = (
            f"@echo off\r\n"
            f"ping -n 4 127.0.0.1 > nul\r\n"   # ~3 s delay — enough for the app to close
            f"{moves_bat}\r\n"
            f'del "{sentinel_path}"\r\n'
            f'echo.> "{marker_path}"\r\n'
            f'start "" "{exe_path}"\r\n'
            f'del "%~f0"\r\n'
        )

        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".bat", delete=False, encoding="utf-8"
            ) as f:
                f.write(bat_script)
                script_path = f.name

            subprocess.Popen(
                ["cmd.exe", "/C", script_path],
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
            )
        except Exception as exc:
            logger.error("Could not launch restart script: %s", exc)
            messagebox.showerror(
                self.tr.t("msg_error_title"),
                f"Could not launch restart script:\n{exc}",
                parent=self,
            )
            return

        self.destroy()

    def _create_button_bar(self, parent) -> None:
        """Create bottom button bar."""
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill=tk.X)
        
        # Left side
        self.restore_defaults_button = ttk.Button(
            btn_frame,
            text=self.tr.t("btn_restore_defaults"),
            command=self._on_restore_defaults
        )
        self.restore_defaults_button.pack(side=tk.LEFT)
        
        ttk.Label(
            btn_frame,
            textvariable=self._refresh_status_var
        ).pack(side=tk.LEFT, padx=(10, 0))
        
        # Right side
        self.cancel_button = ttk.Button(
            btn_frame,
            text=self.tr.t("btn_cancel"),
            command=self._on_cancel
        )
        self.cancel_button.pack(side=tk.RIGHT, padx=(5, 0))

        self.ok_button = ttk.Button(
            btn_frame,
            text=self.tr.t("btn_save"),
            command=self._on_ok
        )
        self.ok_button.pack(side=tk.RIGHT)
    
    def _center_window(self) -> None:
        """Center window on screen."""
        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.geometry(f"+{x}+{y}")
    
    # === Event Handlers ===
    
    def _on_add_bracket(self) -> None:
        """Add new bracket."""
        dialog = BracketDialog(self, self.tr, "", 1.0)
        if dialog.result:
            bracket, factor = dialog.result

            self._apply_bracket_update(bracket, factor)
    
    def _on_edit_bracket(self) -> None:
        """Edit selected bracket."""
        selection = self.scaling_tree.selection()
        if not selection:
            return
        
        item = selection[0]
        values = self.scaling_tree.item(item, 'values')
        old_bracket, old_factor = values[0], float(values[1])
        
        dialog = BracketDialog(self, self.tr, old_bracket, old_factor)
        if dialog.result:
            new_bracket, new_factor = dialog.result

            self._apply_bracket_update(new_bracket, new_factor, old_bracket=old_bracket)
    
    def _on_remove_bracket(self) -> None:
        """Remove selected bracket."""
        selection = self.scaling_tree.selection()
        if not selection:
            return
        
        item = selection[0]
        bracket = self.scaling_tree.item(item, 'values')[0]
        
        if messagebox.askyesno(
            self.tr.t("msg_confirm_title"),
            self.tr.t("msg_confirm_delete", bracket=bracket)
        ):
            factors = self._get_rank_scaling_factors()
            if bracket in factors:
                del factors[bracket]
            self._rebuild_rank_scaling_factors()
            self._populate_scaling_tree()
    
    def _on_edit_rank_score(self) -> None:
        """Edit selected rank score."""
        selection = self.ranks_tree.selection()
        if not selection:
            return
        
        item = selection[0]
        idx = self.ranks_tree.index(item)
        values = self.ranks_tree.item(item, 'values')
        rank_label = self.tr.t("lbl_rank_index_format", index=idx)
        old_score = int(values[1])
        
        dialog = ScoreDialog(self, self.tr, rank_label, old_score)
        if dialog.result is not None:
            new_score = dialog.result
            
            # Update all countries
            ranks = self.config_data.get('ranks', {})
            for country, rank_list in ranks.items():
                if idx < len(rank_list):
                    rank_list[idx]['score'] = new_score
            
            self._populate_ranks_tree()
    
    def _on_edit_campaign_offset(self) -> None:
        """Edit selected campaign offset."""
        if not self.mission_dates_data:
            return

        selection = self.campaigns_tree.selection()
        if not selection:
            return

        item = selection[0]
        values = self.campaigns_tree.item(item, 'values')
        # Columns: campaign(0), country(1), language(2), offset(3)
        campaign_name = values[0]
        old_offset = int(values[3])

        dialog = OffsetDialog(self, self.tr, campaign_name, old_offset)
        if dialog.result is not None:
            self.mission_dates_data[campaign_name]['starting_rank_offset'] = dialog.result
            self._populate_campaigns_tree()

    def _on_campaigns_tree_click(self, event: tk.Event) -> None:
        """Handle single click for campaign country/language editing."""
        region = self.campaigns_tree.identify("region", event.x, event.y)
        if region != "cell":
            self._destroy_country_editor()
            self._destroy_language_editor()
            return
        column = self.campaigns_tree.identify_column(event.x)
        item = self.campaigns_tree.identify_row(event.y)
        if not item:
            return

        # Column #2 = country, Column #3 = language
        if column == "#2":
            self._destroy_language_editor()
            self._start_campaign_country_edit(item)
        elif column == "#3":
            self._destroy_country_editor()
            self._start_campaign_language_edit(item)
        else:
            self._destroy_country_editor()
            self._destroy_language_editor()

    def _on_campaigns_tree_double_click(self, event: tk.Event) -> None:
        """Handle double click for campaign offset editing."""
        region = self.campaigns_tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        column = self.campaigns_tree.identify_column(event.x)
        # Column #4 = offset (after adding language column)
        if column == "#4":
            self._on_edit_campaign_offset()

    def _start_campaign_country_edit(self, item: str) -> None:
        """Begin inline editing of a campaign country."""
        self._destroy_country_editor()

        values = self.campaigns_tree.item(item, 'values')
        if not values:
            return
        campaign_name, current_country = values[0], values[1]
        bbox = self.campaigns_tree.bbox(item, "#2")
        if not bbox:
            return
        x, y, width, height = bbox
        editor = ttk.Combobox(
            self.campaigns_tree,
            values=self.COUNTRY_OPTIONS,
            state='readonly'
        )
        if current_country in self.COUNTRY_OPTIONS:
            editor.set(current_country)
        else:
            editor.set("")
        editor.place(x=x, y=y, width=width, height=height)
        editor.focus_set()
        editor.bind(
            "<<ComboboxSelected>>",
            lambda e: self._on_campaign_country_selected(item, campaign_name, editor.get())
        )
        editor.bind("<FocusOut>", lambda e: self._destroy_country_editor())
        editor.bind("<Escape>", lambda e: self._destroy_country_editor())

        self._country_editor = editor
        self._country_editor_item = item

    def _destroy_country_editor(self) -> None:
        """Destroy any active country editor."""
        if self._country_editor is not None:
            self._country_editor.destroy()
        self._country_editor = None
        self._country_editor_item = None

    def _start_campaign_language_edit(self, item: str) -> None:
        """Begin inline editing of a campaign's detail page language."""
        self._destroy_language_editor()

        values = self.campaigns_tree.item(item, 'values')
        if not values:
            return
        campaign_name = values[0]
        current_language_display = values[2]

        bbox = self.campaigns_tree.bbox(item, "#3")
        if not bbox:
            return
        x, y, width, height = bbox

        # Build translated options list
        options = [self.tr.t(key) for key in self.DETAIL_PAGE_LOCALE_OPTIONS.values()]

        editor = ttk.Combobox(
            self.campaigns_tree,
            values=options,
            state='readonly'
        )
        if current_language_display in options:
            editor.set(current_language_display)
        else:
            editor.set(options[0])  # Default
        editor.place(x=x, y=y, width=width, height=height)
        editor.focus_set()
        editor.bind(
            "<<ComboboxSelected>>",
            lambda e: self._on_campaign_language_selected(item, campaign_name, editor.get())
        )
        editor.bind("<FocusOut>", lambda e: self._destroy_language_editor())
        editor.bind("<Escape>", lambda e: self._destroy_language_editor())

        self._language_editor = editor
        self._language_editor_item = item

    def _destroy_language_editor(self) -> None:
        """Destroy any active language editor."""
        if self._language_editor is not None:
            self._language_editor.destroy()
        self._language_editor = None
        self._language_editor_item = None

    def _on_campaign_language_selected(self, item: str, campaign_name: str, selected_display: str) -> None:
        """Update campaign detail page language selection."""
        if not selected_display:
            self._destroy_language_editor()
            return

        # Convert display text back to stored value (None, 'en', 'de', 'ru')
        stored_value = None
        for locale_val, key in self.DETAIL_PAGE_LOCALE_OPTIONS.items():
            if self.tr.t(key) == selected_display:
                stored_value = locale_val
                break

        # Update mission_dates_data
        if (
            self.mission_dates_data
            and campaign_name in self.mission_dates_data
            and isinstance(self.mission_dates_data[campaign_name], dict)
        ):
            if stored_value is None:
                # Remove the key if setting to default (cleaner JSON)
                self.mission_dates_data[campaign_name].pop('detail_page_locale', None)
            else:
                self.mission_dates_data[campaign_name]['detail_page_locale'] = stored_value

            # Mark this campaign for debriefings regeneration on save
            # Compare with original value to determine if regeneration is needed
            original_locale = None
            if (
                self.original_data.get('mission_dates')
                and campaign_name in self.original_data['mission_dates']
                and isinstance(self.original_data['mission_dates'][campaign_name], dict)
            ):
                original_locale = self.original_data['mission_dates'][campaign_name].get('detail_page_locale')

            if stored_value != original_locale:
                # Value changed - mark for regeneration if specific language is set
                if stored_value is not None:
                    self._campaigns_needing_debriefings_regen.add(campaign_name)
                    logger.info(
                        "Campaign '%s' marked for localized debriefings regeneration (locale=%s)",
                        campaign_name, stored_value
                    )
                else:
                    # Changed back to Default - remove from regeneration set if present
                    self._campaigns_needing_debriefings_regen.discard(campaign_name)
                    logger.info(
                        "Campaign '%s' removed from debriefings regeneration set (set to Default)",
                        campaign_name
                    )
            else:
                # Value unchanged from original - remove from regeneration set
                self._campaigns_needing_debriefings_regen.discard(campaign_name)

        # Update tree view
        values = list(self.campaigns_tree.item(item, 'values'))
        if len(values) >= 3:
            values[2] = selected_display
            self.campaigns_tree.item(item, values=values)

        self._destroy_language_editor()

    def _read_campaign_display_name(self, info_path: str) -> Optional[str]:
        """Read display name from an info.locale=eng.txt file."""
        try:
            content = None
            for encoding in ['utf-8', 'utf-8-sig', 'iso-8859-1', 'cp1252']:
                try:
                    with open(info_path, 'r', encoding=encoding) as handle:
                        content = handle.read(1000)
                    break
                except UnicodeDecodeError:
                    continue
            if not content:
                return None
            match = re.search(r'&name="([^"]+)"', content)
            if not match:
                match = re.search(r'&name=([^\s\n;]+)', content)
            if match:
                return match.group(1)
        except Exception as exc:
            logger.debug("Failed reading campaign display name from %s: %s", info_path, exc)
        return None

    def _get_campaign_display_name_map(self) -> Dict[str, str]:
        """Map campaign folder names to display names."""
        if self._campaign_display_name_map is not None:
            return self._campaign_display_name_map

        mapping: Dict[str, str] = {}
        game_dir = None
        if isinstance(self.mission_dates_data, dict):
            game_dir = self.mission_dates_data.get('game_directory')

        if game_dir and os.path.isdir(game_dir):
            campaigns_dir = os.path.join(game_dir, "data", "Campaigns")
            if os.path.isdir(campaigns_dir):
                for entry in os.listdir(campaigns_dir):
                    entry_path = os.path.join(campaigns_dir, entry)
                    if not os.path.isdir(entry_path):
                        continue
                    info_path = os.path.join(entry_path, "info.locale=eng.txt")
                    if not os.path.isfile(info_path):
                        continue
                    display_name = self._read_campaign_display_name(info_path)
                    if display_name:
                        mapping[entry] = display_name

        self._campaign_display_name_map = mapping
        return mapping

    def _get_stock_campaigns_map_readonly(self) -> Optional[Dict[str, str]]:
        """Return stock campaigns mapping if loaded, without creating new entries."""
        if not isinstance(self.stock_campaigns_data, dict):
            return None
        stock_campaigns = self.stock_campaigns_data.get("stock_campaigns")
        if not isinstance(stock_campaigns, dict):
            return None
        return stock_campaigns

    def _resolve_stock_campaign_key(
        self,
        campaign_name: str,
        stock_campaigns: Dict[str, str],
    ) -> Optional[str]:
        """Resolve campaign folder name to stock_campaigns.yaml key."""
        if campaign_name in stock_campaigns:
            return campaign_name
        display_name = self._get_campaign_display_name_map().get(campaign_name)
        if not display_name:
            return None
        for key in stock_campaigns.keys():
            if key.lower() == display_name.lower():
                return key
        return None

    def _get_stock_campaigns_map(self) -> Dict[str, str]:
        """Return mutable stock campaigns mapping, creating as needed."""
        if not isinstance(self.stock_campaigns_data, dict):
            self.stock_campaigns_data = CommentedMap()
        stock_campaigns = self.stock_campaigns_data.get("stock_campaigns")
        if not isinstance(stock_campaigns, dict):
            stock_campaigns = CommentedMap() if HAS_RUAMEL else {}
            self.stock_campaigns_data["stock_campaigns"] = stock_campaigns
        return stock_campaigns

    def _on_campaign_country_selected(self, item: str, campaign_name: str, new_country: str) -> None:
        """Update campaign country selection."""
        if not new_country:
            self._destroy_country_editor()
            return

        stock_campaigns = self._get_stock_campaigns_map_readonly()
        if not stock_campaigns:
            messagebox.showerror(
                self.tr.t("msg_error_title"),
                "Unable to update campaign country: stock_campaigns.yaml is missing or invalid."
            )
            logger.error("Stock campaigns data unavailable; cannot update %s.", campaign_name)
            self._destroy_country_editor()
            return

        stock_key = self._resolve_stock_campaign_key(campaign_name, stock_campaigns)
        if not stock_key:
            messagebox.showerror(
                self.tr.t("msg_error_title"),
                f"Unable to update campaign country: no stock mapping found for '{campaign_name}'."
            )
            logger.error(
                "Stock campaigns mapping not found for campaign '%s'.", campaign_name
            )
            self._destroy_country_editor()
            return

        if stock_key not in stock_campaigns:
            messagebox.showerror(
                self.tr.t("msg_error_title"),
                f"Unable to update campaign country: '{stock_key}' not present in stock_campaigns.yaml."
            )
            logger.error(
                "Resolved stock key '%s' not present in stock_campaigns.yaml (campaign '%s').",
                stock_key,
                campaign_name,
            )
            self._destroy_country_editor()
            return

        stock_campaigns[stock_key] = new_country

        if (
            self.mission_dates_data
            and campaign_name in self.mission_dates_data
            and isinstance(self.mission_dates_data[campaign_name], dict)
        ):
            self.mission_dates_data[campaign_name]['country'] = new_country

        values = list(self.campaigns_tree.item(item, 'values'))
        if len(values) >= 2:
            values[1] = new_country
            self.campaigns_tree.item(item, values=values)

        self._destroy_country_editor()
    
    def _on_restore_defaults(self) -> None:
        """Restore default values."""
        if messagebox.askyesno(
            self.tr.t("msg_confirm_title"),
            "Restore all settings to defaults?"
        ):
            # Reload from files
            self._load_all_data()
            
            # Refresh UI
            self._populate_scaling_tree()
            self._populate_ranks_tree()
            if self.mission_dates_data:
                self._populate_campaigns_tree()
            
            # Reset general settings UI
            current_locale = self.settings_data.get('locale', 'en')
            self.language_var.set(LANGUAGE_NAMES.get(current_locale, 'English'))
            self.popups_var.set('True' if self.config_data.get('enable_popups', True) else 'False')
            
            rank_scaling = self.config_data.get('rank_scaling', {})
            scaling_enabled = rank_scaling.get('enabled', True) if isinstance(rank_scaling, dict) else True
            self.scaling_var.set('True' if scaling_enabled else 'False')

            story_settings = self.settings_data.get('stories', {})
            if not isinstance(story_settings, dict):
                story_settings = {}
            self.ai_stories_var.set('True' if story_settings.get('enabled', False) else 'False')
            provider_value = str(story_settings.get('provider', 'openai') or 'openai').strip().lower()
            if provider_value not in self.STORY_PROVIDER_OPTIONS:
                provider_value = 'openai'
            provider_api_keys = story_settings.get('api_keys', {})
            api_keys_map: Dict[str, str] = {}
            if isinstance(provider_api_keys, dict):
                for key, value in provider_api_keys.items():
                    normalized_key = str(key or '').strip().lower()
                    if normalized_key in self.STORY_PROVIDER_OPTIONS:
                        api_keys_map[normalized_key] = str(value or '').strip()
            legacy_key = str(story_settings.get('api_key', '') or '').strip()
            if legacy_key and not api_keys_map.get(provider_value):
                api_keys_map[provider_value] = legacy_key
            self._story_provider_api_keys = api_keys_map
            self._story_last_provider = provider_value
            self.story_provider_var.set(provider_value)
            self.story_api_key_var.set(self._story_provider_api_keys.get(provider_value, ''))
            self.story_base_url_var.set(
                str(story_settings.get('base_url') or self._story_default_base_url(provider_value))
            )
            self._story_saved_model = str(story_settings.get('model') or '').strip()
            self.story_model_var.set('')
            self.story_model_combo.configure(values=[], state='disabled')
            self.story_auto_generate_var.set('True' if story_settings.get('auto_generate', False) else 'False')
            self.citations_enabled_var.set('True' if story_settings.get('citations_enabled', False) else 'False')
            self._update_story_model_hint()
            self.story_status_var.set("")
    
    def _collect_changes(self) -> None:
        """Collect all UI changes into data structures."""
        # General settings
        lang_name = self.language_var.get()
        for code, name in LANGUAGE_NAMES.items():
            if name == lang_name:
                self.settings_data['locale'] = code
                break
        
        self.config_data['enable_popups'] = self.popups_var.get() == 'True'
        
        if 'rank_scaling' not in self.config_data:
            self.config_data['rank_scaling'] = {}
        self.config_data['rank_scaling']['enabled'] = self.scaling_var.get() == 'True'

        stories = self.settings_data.get('stories', {})
        if not isinstance(stories, dict):
            stories = {}
        provider_value = self.story_provider_var.get().strip().lower() or 'openai'
        if provider_value not in self.STORY_PROVIDER_OPTIONS:
            provider_value = 'openai'
        if hasattr(self, 'story_api_key_var'):
            current_key = self.story_api_key_var.get().strip()
            if current_key:
                self._story_provider_api_keys[provider_value] = current_key
            elif provider_value in self._story_provider_api_keys:
                self._story_provider_api_keys[provider_value] = ""
        stories['enabled'] = self.ai_stories_var.get() == 'True'
        stories['provider'] = provider_value
        stories['api_key'] = self._story_provider_api_keys.get(provider_value, '')
        stories['api_keys'] = {
            key: value for key, value in self._story_provider_api_keys.items()
            if key in self.STORY_PROVIDER_OPTIONS and str(value or '').strip()
        }
        stories['base_url'] = self.story_base_url_var.get().strip() or self._story_default_base_url(provider_value)
        stories['model'] = self.story_model_var.get().strip() or getattr(self, '_story_saved_model', '') or 'gpt-4o-mini'
        stories['auto_generate'] = self.story_auto_generate_var.get() == 'True'
        stories['citations_enabled'] = self.citations_enabled_var.get() == 'True'
        self.settings_data['stories'] = stories

    def _set_story_test_running(self, running: bool) -> None:
        state = tk.DISABLED if running else tk.NORMAL
        if hasattr(self, 'story_test_button') and self.story_test_button:
            self.story_test_button.configure(state=state)
        if hasattr(self, 'story_refresh_models_button') and self.story_refresh_models_button:
            self.story_refresh_models_button.configure(state=state)

    def _story_default_base_url(self, provider: str) -> str:
        key = str(provider or "").strip().lower()
        return self.STORY_PROVIDER_DEFAULT_BASE_URLS.get(key, "")

    def _on_story_provider_changed(self, _event=None) -> None:
        provider = self.story_provider_var.get().strip().lower()
        if provider not in self.STORY_PROVIDER_OPTIONS:
            provider = 'openai'
            self.story_provider_var.set(provider)

        previous_provider = self._story_last_provider if self._story_last_provider in self.STORY_PROVIDER_OPTIONS else None
        if previous_provider and hasattr(self, 'story_api_key_var'):
            self._story_provider_api_keys[previous_provider] = self.story_api_key_var.get().strip()
        if hasattr(self, 'story_api_key_var'):
            self.story_api_key_var.set(self._story_provider_api_keys.get(provider, ''))
        self._story_last_provider = provider

        current = self.story_base_url_var.get().strip()
        default_current = self._story_default_base_url(provider)
        if not current or current in self.STORY_PROVIDER_DEFAULT_BASE_URLS.values():
            self.story_base_url_var.set(default_current)

        # Clear and disable the model combo — user must refresh for the new provider.
        if hasattr(self, 'story_model_var'):
            self.story_model_var.set('')
        if hasattr(self, 'story_model_combo'):
            self.story_model_combo.configure(values=[], state='disabled')
        self._update_story_model_hint()

    def _update_story_model_hint(self) -> None:
        provider = self.story_provider_var.get().strip().lower() if hasattr(self, 'story_provider_var') else 'openai'
        hint = self.STORY_PROVIDER_MODEL_HINTS.get(provider, "")
        if hasattr(self, 'story_model_hint_var'):
            self.story_model_hint_var.set(hint)

    def _update_story_model_options(self, keep_current: bool = True) -> None:
        if not hasattr(self, 'story_model_combo') or not self.story_model_combo:
            return
        provider = self.story_provider_var.get().strip().lower() if hasattr(self, 'story_provider_var') else 'openai'
        provider_models = list(self._story_provider_models_runtime.get(provider, self.STORY_PROVIDER_MODELS.get(provider, [])))
        current = self.story_model_var.get().strip() if hasattr(self, 'story_model_var') else ""
        if keep_current and current and current not in provider_models:
            provider_models.append(current)
        ordered_models = self._order_story_models_for_ui(provider, provider_models)
        self.story_model_combo.configure(values=ordered_models)

    def _order_story_models_for_ui(self, provider: str, models: List[str]) -> List[str]:
        provider_key = str(provider or "").strip().lower()
        recommended = [
            str(m).strip() for m in self.STORY_PROVIDER_RECOMMENDED_MODELS.get(provider_key, [])
            if str(m).strip()
        ]
        all_models = [str(m).strip() for m in models if str(m).strip()]
        unique_all = sorted(set(all_models), key=lambda x: x.lower())

        ordered: List[str] = []
        seen: set[str] = set()
        for model_id in recommended:
            if model_id in unique_all and model_id not in seen:
                ordered.append(model_id)
                seen.add(model_id)
        for model_id in unique_all:
            if model_id not in seen:
                ordered.append(model_id)
                seen.add(model_id)
        return ordered

    @staticmethod
    def _validate_story_model_text(model: str, provider: str) -> Optional[str]:
        model_value = str(model or "").strip()
        provider_value = str(provider or "").strip().lower()
        if not model_value:
            return "Model is required."
        if " " in model_value:
            return "Model must not contain spaces."
        if len(model_value) > 140:
            return "Model value is too long."
        if provider_value == "openrouter":
            if "/" not in model_value:
                return "OpenRouter model should use vendor/model format (for example: x-ai/grok-4.1-fast)."
        return None

    def _validate_story_settings_for_save(self) -> list[str]:
        errors: list[str] = []
        if not isinstance(self.settings_data, dict):
            return errors

        stories = self.settings_data.get("stories", {})
        if not isinstance(stories, dict):
            errors.append("stories must be an object.")
            return errors

        enabled = bool(stories.get("enabled", False))
        provider = str(stories.get("provider") or "openai").strip().lower() or "openai"
        model = str(stories.get("model") or "").strip()
        api_key = str(stories.get("api_key") or "").strip()
        base_url = str(stories.get("base_url") or "").strip()

        if provider not in self.STORY_PROVIDER_OPTIONS:
            errors.append(f"Invalid story provider: {provider}.")

        model_error = self._validate_story_model_text(model, provider)
        if model_error:
            errors.append(model_error)

        if enabled:
            if not api_key:
                errors.append("Story API key is required when AI stories are enabled.")
            if not base_url:
                errors.append("Story API Base URL is required when AI stories are enabled.")
            elif not (base_url.startswith("http://") or base_url.startswith("https://")):
                errors.append("Story API Base URL must start with http:// or https://.")

            if provider == "microsoft" and "YOUR-RESOURCE-NAME" in base_url:
                errors.append("Microsoft provider requires a real Azure base URL (replace YOUR-RESOURCE-NAME).")

        return errors

    def _fetch_provider_models(self, provider: str, api_key: str, base_url: str) -> List[str]:
        provider_value = provider.strip().lower()
        if provider_value not in {"openai", "openrouter", "anthropic", "google", "microsoft"}:
            raise ValueError("Model refresh is not supported for this provider.")

        def _http_json_get(url: str, headers: Dict[str, str]) -> Any:
            req = urllib.request.Request(url, headers=headers, method="GET")
            try:
                with urllib.request.urlopen(req, timeout=20) as resp:
                    raw = resp.read().decode("utf-8", errors="replace")
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"HTTP {exc.code}: {detail[:240]}") from exc
            except urllib.error.URLError as exc:
                raise RuntimeError(f"Network error: {exc}") from exc

            try:
                return json.loads(raw)
            except json.JSONDecodeError as exc:
                raise RuntimeError("Provider returned invalid JSON.") from exc

        def _extract_model_ids(payload: Any) -> List[str]:
            if isinstance(payload, dict):
                items = payload.get("data")
                if not isinstance(items, list):
                    items = payload.get("models")
                if not isinstance(items, list):
                    items = payload.get("value")
            else:
                items = payload

            if not isinstance(items, list):
                return []

            models: List[str] = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                model_id = str(item.get("id") or "").strip()
                if not model_id:
                    model_id = str(item.get("name") or "").strip()
                if model_id.startswith("models/"):
                    model_id = model_id.split("/", 1)[1].strip()
                if model_id:
                    models.append(model_id)
            return sorted(set(models), key=lambda x: x.lower())

        base = base_url.rstrip("/")

        if provider_value in {"openai", "openrouter"}:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
            }
            if provider_value == "openrouter":
                headers["HTTP-Referer"] = "https://il2-campaign-tracker.local"
                headers["X-Title"] = "IL-2 Campaign Tracker"
            payload = _http_json_get(f"{base}/models", headers=headers)
            models = _extract_model_ids(payload)
            if not models:
                raise RuntimeError("Provider /models response has no model list.")
            return models

        if provider_value == "anthropic":
            headers = {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Accept": "application/json",
            }
            payload = _http_json_get(f"{base}/models", headers=headers)
            models = _extract_model_ids(payload)
            if not models:
                raise RuntimeError("Anthropic /models response has no model list.")
            return models

        if provider_value == "google":
            # Try OpenAI-compatible endpoint first, then Gemini native fallback.
            headers_openai = {
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
            }
            try:
                payload = _http_json_get(f"{base}/models", headers=headers_openai)
                models = _extract_model_ids(payload)
                if models:
                    return models
            except Exception:
                pass

            native_base = base
            if native_base.endswith("/openai"):
                native_base = native_base[:-len("/openai")]
            payload = _http_json_get(f"{native_base}/models?key={api_key}", headers={"Accept": "application/json"})
            models = _extract_model_ids(payload)
            if not models:
                raise RuntimeError("Google models endpoint returned no model list.")
            return models

        # microsoft / azure openai
        # Azure supports api-key authentication. Try /models and /openai/models variants.
        headers_azure = {
            "api-key": api_key,
            "Accept": "application/json",
        }
        base_no_v1 = base[:-3] if base.endswith("/v1") else base
        candidate_urls = [
            f"{base}/models",
            f"{base_no_v1}/models",
            f"{base_no_v1}/openai/models?api-version=2024-10-01-preview",
        ]
        last_error: Optional[Exception] = None
        for url in candidate_urls:
            try:
                payload = _http_json_get(url, headers=headers_azure)
                models = _extract_model_ids(payload)
                if models:
                    return models
            except Exception as exc:
                last_error = exc
                continue
        if last_error:
            raise RuntimeError(str(last_error)) from last_error
        raise RuntimeError("Azure model refresh failed.")

    def _on_refresh_story_models(self) -> None:
        provider = self.story_provider_var.get().strip().lower() or "openai"
        api_key = self.story_api_key_var.get().strip()
        base_url = self.story_base_url_var.get().strip() or self._story_default_base_url(provider)

        if provider == "custom":
            messagebox.showwarning(
                self.tr.t("msg_warning_title"),
                self.tr.t("msg_story_refresh_provider_not_supported"),
            )
            return
        if not api_key:
            messagebox.showwarning(
                self.tr.t("msg_warning_title"),
                self.tr.t("msg_story_test_missing_key"),
            )
            return
        if not base_url:
            messagebox.showwarning(
                self.tr.t("msg_warning_title"),
                "API Base URL is required.",
            )
            return
        if self._story_models_refresh_thread and self._story_models_refresh_thread.is_alive():
            return

        self.story_status_var.set(self.tr.t("msg_story_refresh_running", provider=provider))
        self._set_story_test_running(True)
        self._story_models_refresh_queue = queue.Queue()
        if self._story_models_refresh_poll_id:
            self.after_cancel(self._story_models_refresh_poll_id)
            self._story_models_refresh_poll_id = None

        def worker() -> None:
            try:
                models = self._fetch_provider_models(provider, api_key, base_url)
                self._story_models_refresh_queue.put({
                    "ok": True,
                    "provider": provider,
                    "models": models,
                })
            except Exception as exc:
                self._story_models_refresh_queue.put({
                    "ok": False,
                    "provider": provider,
                    "error": str(exc),
                })

        self._story_models_refresh_thread = threading.Thread(target=worker, daemon=True)
        self._story_models_refresh_thread.start()
        self._poll_story_models_refresh_queue()

    def _poll_story_models_refresh_queue(self) -> None:
        try:
            payload = self._story_models_refresh_queue.get_nowait()
        except queue.Empty:
            self._story_models_refresh_poll_id = self.after(150, self._poll_story_models_refresh_queue)
            return

        self._story_models_refresh_poll_id = None
        self._set_story_test_running(False)

        provider = str(payload.get("provider") or self.story_provider_var.get() or "provider")
        if payload.get("ok"):
            models = payload.get("models") or []
            existing = self._story_provider_models_runtime.get(provider, [])
            merged = self._order_story_models_for_ui(
                provider,
                list(existing) + [str(m).strip() for m in models if str(m).strip()],
            )
            self._story_provider_models_runtime[provider] = merged
            self._update_story_model_options(keep_current=False)
            # Enable the combo now that models are available.
            if hasattr(self, 'story_model_combo'):
                self.story_model_combo.configure(state='readonly')
            # Restore saved model if it is in the list, otherwise pick the first available.
            if hasattr(self, 'story_model_var') and hasattr(self, 'story_model_combo'):
                saved = getattr(self, '_story_saved_model', '')
                current = self.story_model_var.get().strip()
                available = list(self.story_model_combo.cget('values'))
                if current in available:
                    pass  # already set correctly
                elif saved and saved in available:
                    self.story_model_var.set(saved)
                elif available:
                    self.story_model_var.set(available[0])
            self.story_status_var.set(self.tr.t("msg_story_refresh_success", provider=provider, count=len(merged)))
            messagebox.showinfo(
                self.tr.t("msg_confirm_title"),
                self.tr.t("msg_story_refresh_success", provider=provider, count=len(merged)),
            )
        else:
            error_text = str(payload.get("error") or self.tr.t("msg_story_test_unknown_error"))
            self.story_status_var.set(error_text)
            messagebox.showwarning(
                self.tr.t("msg_warning_title"),
                self.tr.t("msg_story_refresh_failed", error=error_text),
            )

    def _classify_story_test_error(self, error: Exception) -> str:
        name = error.__class__.__name__
        message = str(error)
        combined = f"{name}: {message}".lower()

        if "api_key" in combined or "authentication" in combined or "unauthorized" in combined:
            return self.tr.t("msg_story_test_auth_error")
        if "insufficient_quota" in combined or "quota" in combined or "billing" in combined:
            return self.tr.t("msg_story_test_quota_error")
        if "connection" in combined or "timeout" in combined or "network" in combined:
            return self.tr.t("msg_story_test_network_error")
        return self.tr.t("msg_story_test_generic_error", error=message or name)

    def _on_test_story_connection(self) -> None:
        provider = self.story_provider_var.get().strip().lower() or 'openai'
        api_key = self.story_api_key_var.get().strip()
        base_url = self.story_base_url_var.get().strip() or self._story_default_base_url(provider)
        model = self.story_model_var.get().strip() or getattr(self, '_story_saved_model', '') or 'gpt-4o-mini'

        if not api_key:
            messagebox.showwarning(
                self.tr.t("msg_warning_title"),
                self.tr.t("msg_story_test_missing_key"),
            )
            return
        if not base_url:
            messagebox.showwarning(
                self.tr.t("msg_warning_title"),
                "API Base URL is required for the selected provider.",
            )
            return
        model_error = self._validate_story_model_text(model, provider)
        if model_error:
            messagebox.showwarning(
                self.tr.t("msg_warning_title"),
                model_error,
            )
            return

        if self._story_test_thread and self._story_test_thread.is_alive():
            return

        self.story_status_var.set(self.tr.t("msg_story_test_running", provider=provider))
        self._set_story_test_running(True)
        self._story_test_queue = queue.Queue()
        if self._story_test_poll_id:
            self.after_cancel(self._story_test_poll_id)
            self._story_test_poll_id = None

        def worker() -> None:
            try:
                from openai import OpenAI

                client = OpenAI(api_key=api_key, base_url=base_url)
                _test_messages = [{"role": "user", "content": "Reply with exactly: connection ok"}]
                try:
                    response = client.chat.completions.create(
                        model=model,
                        messages=_test_messages,
                        max_tokens=16,
                    )
                except Exception as _e:
                    if "max_tokens" in str(_e) and "max_completion_tokens" in str(_e):
                        response = client.chat.completions.create(
                            model=model,
                            messages=_test_messages,
                            max_completion_tokens=16,
                        )
                    else:
                        raise
                reply = ""
                if response.choices:
                    reply = (getattr(response.choices[0].message, "content", "") or "").strip()
                self._story_test_queue.put({
                    "ok": True,
                    "provider": provider,
                    "text": reply,
                })
            except Exception as exc:
                self._story_test_queue.put({
                    "ok": False,
                    "provider": provider,
                    "error": self._classify_story_test_error(exc),
                })

        self._story_test_thread = threading.Thread(target=worker, daemon=True)
        self._story_test_thread.start()
        self._poll_story_test_queue()

    def _poll_story_test_queue(self) -> None:
        try:
            payload = self._story_test_queue.get_nowait()
        except queue.Empty:
            self._story_test_poll_id = self.after(150, self._poll_story_test_queue)
            return

        self._story_test_poll_id = None
        self._set_story_test_running(False)
        provider = str(payload.get("provider") or self.story_provider_var.get() or "provider")

        if payload.get("ok"):
            self.story_status_var.set(self.tr.t("msg_story_test_success", provider=provider))
            messagebox.showinfo(
                self.tr.t("msg_confirm_title"),
                self.tr.t("msg_story_test_success", provider=provider),
            )
        else:
            error_text = payload.get("error", self.tr.t("msg_story_test_unknown_error"))
            self.story_status_var.set(error_text)
            messagebox.showwarning(
                self.tr.t("msg_warning_title"),
                error_text,
            )

    def _bracket_sort_key(self, bracket: str) -> Tuple[int, float]:
        try:
            start, end = BracketValidator.parse(bracket)
        except ValueError:
            return (9999, float("inf"))
        end_value = end if end is not None else float("inf")
        return (start, end_value)

    def _sort_brackets(self, brackets: Iterable[str]) -> List[str]:
        return sorted(brackets, key=self._bracket_sort_key)

    def _brackets_overlap(self, bracket_a: str, bracket_b: str) -> bool:
        start_a, end_a = BracketValidator.parse(bracket_a)
        start_b, end_b = BracketValidator.parse(bracket_b)
        end_a_value = end_a if end_a is not None else float("inf")
        end_b_value = end_b if end_b is not None else float("inf")
        return start_a <= end_b_value and start_b <= end_a_value

    def _find_overlaps(self, bracket: str, existing: Iterable[str]) -> List[str]:
        overlaps = []
        for existing_bracket in existing:
            if existing_bracket == bracket:
                continue
            if self._brackets_overlap(bracket, existing_bracket):
                overlaps.append(existing_bracket)
        return overlaps

    def _get_rank_scaling_factors(self) -> Dict[str, Any]:
        if 'rank_scaling' not in self.config_data or not isinstance(self.config_data['rank_scaling'], dict):
            self.config_data['rank_scaling'] = {}
        rank_scaling = self.config_data['rank_scaling']
        factors = rank_scaling.get('factors', {})
        if not isinstance(factors, dict):
            factors = {}
            rank_scaling['factors'] = factors
        return factors

    def _rebuild_rank_scaling_factors(self) -> None:
        factors = self._get_rank_scaling_factors()
        ordered_factors = CommentedMap()
        for bracket in self._sort_brackets(factors.keys()):
            ordered_factors[bracket] = factors[bracket]
        self.config_data['rank_scaling']['factors'] = ordered_factors

    def _apply_bracket_update(
        self,
        bracket: str,
        factor: float,
        old_bracket: Optional[str] = None,
    ) -> None:
        factors = self._get_rank_scaling_factors()
        existing = [key for key in factors.keys() if key != old_bracket]

        if bracket in existing:
            messagebox.showerror(
                self.tr.t("msg_error_title"),
                self.tr.t("err_bracket_duplicate")
            )
            return

        overlaps = self._find_overlaps(bracket, existing)
        removed = []
        for overlap in overlaps:
            if overlap in factors:
                removed.append(overlap)
                del factors[overlap]

        if old_bracket and old_bracket != bracket and old_bracket in factors:
            del factors[old_bracket]

        factors[bracket] = factor
        self._rebuild_rank_scaling_factors()
        self._populate_scaling_tree()

        if removed:
            removed_display = ", ".join(self._sort_brackets(removed))
            messagebox.showwarning(
                self.tr.t("msg_warning_title"),
                f"Removed overlapping brackets: {removed_display}"
            )

    def _format_type_error(self, field: str, expected: str, value: Any) -> str:
        preview = repr(value)
        if len(preview) > 120:
            preview = preview[:117] + "..."
        return f"{field}: expected {expected}, got {type(value).__name__} ({preview})"

    def _coerce_bool(self, value: Any, field: str, errors: list[str], default: Optional[bool] = None) -> Any:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in ("true", "yes", "1"):
                return True
            if normalized in ("false", "no", "0"):
                return False
        errors.append(self._format_type_error(field, "bool", value))
        return default if default is not None else value

    def _coerce_int(self, value: Any, field: str, errors: list[str]) -> Any:
        if isinstance(value, int) and not isinstance(value, bool):
            return value
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.isdigit() or (stripped.startswith("-") and stripped[1:].isdigit()):
                try:
                    return int(stripped)
                except ValueError:
                    pass
        errors.append(self._format_type_error(field, "int", value))
        return value

    def _coerce_float(self, value: Any, field: str, errors: list[str]) -> Any:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value.strip())
            except ValueError:
                pass
        errors.append(self._format_type_error(field, "float", value))
        return value

    def _normalize_all(self) -> list[str]:
        """Normalize UI data into expected types before validation."""
        errors: list[str] = []

        if not isinstance(self.settings_data, dict):
            errors.append(self._format_type_error("settings", "dict", self.settings_data))
            self.settings_data = {}
        locale = self.settings_data.get("locale")
        if locale is not None and not isinstance(locale, str):
            errors.append(self._format_type_error("settings.locale", "str", locale))

        if not isinstance(self.config_data, dict):
            errors.append(self._format_type_error("config", "dict", self.config_data))
            self.config_data = {}

        self.config_data["enable_popups"] = self._coerce_bool(
            self.config_data.get("enable_popups", True),
            "config.enable_popups",
            errors,
            default=True,
        )

        rank_scaling = self.config_data.get("rank_scaling", {})
        if not isinstance(rank_scaling, dict):
            errors.append(self._format_type_error("config.rank_scaling", "dict", rank_scaling))
            rank_scaling = {}
        self.config_data["rank_scaling"] = rank_scaling
        rank_scaling["enabled"] = self._coerce_bool(
            rank_scaling.get("enabled", True),
            "config.rank_scaling.enabled",
            errors,
            default=True,
        )

        factors = rank_scaling.get("factors", {})
        if not isinstance(factors, dict):
            errors.append(self._format_type_error("config.rank_scaling.factors", "dict", factors))
            factors = {}
        normalized_factors: Dict[str, Any] = {}
        for bracket, factor in factors.items():
            bracket_key = bracket if isinstance(bracket, str) else str(bracket)
            if not isinstance(bracket, str):
                errors.append(self._format_type_error("config.rank_scaling.factors.<key>", "str", bracket))
            normalized_factors[bracket_key] = self._coerce_float(
                factor, f"config.rank_scaling.factors.{bracket_key}", errors
            )
        rank_scaling["factors"] = normalized_factors

        ranks = self.config_data.get("ranks", {})
        original_ranks = {}
        if isinstance(self.original_data.get("config"), dict):
            original_ranks = self.original_data["config"].get("ranks", {})
        if ranks and not isinstance(ranks, dict):
            errors.append(self._format_type_error("config.ranks", "dict", ranks))
            ranks = {}
        if isinstance(ranks, dict):
            for country, rank_list in ranks.items():
                if not isinstance(rank_list, list):
                    errors.append(self._format_type_error(f"config.ranks.{country}", "list", rank_list))
                    ranks[country] = []
                    continue
                normalized_rank_list = []
                for idx, entry in enumerate(rank_list):
                    if not isinstance(entry, dict):
                        errors.append(
                            self._format_type_error(f"config.ranks.{country}[{idx}]", "dict", entry)
                        )
                        continue
                    original_entry = None
                    if isinstance(original_ranks, dict):
                        original_list = original_ranks.get(country)
                        if isinstance(original_list, list) and idx < len(original_list):
                            if isinstance(original_list[idx], dict):
                                original_entry = original_list[idx]
                    score = self._coerce_int(
                        entry.get("score", 0), f"config.ranks.{country}[{idx}].score", errors
                    )
                    name = entry.get("name", "")
                    if name is not None and not isinstance(name, str):
                        errors.append(
                            self._format_type_error(f"config.ranks.{country}[{idx}].name", "str", name)
                        )
                    normalized_entry = dict(entry)
                    normalized_entry["score"] = score
                    normalized_entry["name"] = name
                    if not normalized_entry.get("image") and isinstance(original_entry, dict):
                        original_image = original_entry.get("image")
                        if original_image:
                            normalized_entry["image"] = original_image
                    normalized_rank_list.append(normalized_entry)
                ranks[country] = normalized_rank_list
        self.config_data["ranks"] = ranks

        if self.mission_dates_data is not None:
            if not isinstance(self.mission_dates_data, dict):
                errors.append(self._format_type_error("mission_dates", "dict", self.mission_dates_data))
                self.mission_dates_data = {}
            else:
                normalized_mission_dates = {}
                for campaign, data in self.mission_dates_data.items():
                    if campaign == "game_directory":
                        if data is not None and not isinstance(data, str):
                            errors.append(
                                self._format_type_error("mission_dates.game_directory", "str", data)
                            )
                        normalized_mission_dates[campaign] = data
                        continue
                    if not isinstance(data, dict):
                        errors.append(
                            self._format_type_error(f"mission_dates.{campaign}", "dict", data)
                        )
                        normalized_mission_dates[campaign] = {}
                        continue
                    offset = self._coerce_int(
                        data.get("starting_rank_offset", 0),
                        f"mission_dates.{campaign}.starting_rank_offset",
                        errors,
                    )
                    normalized_entry = dict(data)
                    normalized_entry["starting_rank_offset"] = offset
                    normalized_mission_dates[campaign] = normalized_entry
                self.mission_dates_data = normalized_mission_dates

        return errors

    def _log_normalized_settings(self) -> None:
        """Log a summary of normalized settings for debugging."""
        summary = {
            "settings": {key: type(value).__name__ for key, value in self.settings_data.items()},
            "config": {key: type(value).__name__ for key, value in self.config_data.items()},
            "mission_dates": type(self.mission_dates_data).__name__,
        }
        print(f"Settings Manager: normalized settings types: {summary}")
    
    def _validate_all(self) -> list[str]:
        """Validate all data. Returns list of errors."""
        errors = []
        
        # Validate rank scaling factors
        rank_scaling = self.config_data.get('rank_scaling', {})
        if not isinstance(rank_scaling, dict):
            errors.append(self._format_type_error("config.rank_scaling", "dict", rank_scaling))
            rank_scaling = {}
        factors = rank_scaling.get('factors', {})
        if not isinstance(factors, dict):
            errors.append(self._format_type_error("config.rank_scaling.factors", "dict", factors))
            factors = {}
        
        for bracket, factor in factors.items():
            if not isinstance(bracket, str):
                errors.append(self._format_type_error("config.rank_scaling.factors.<key>", "str", bracket))
                continue
            try:
                BracketValidator.parse(bracket)
            except ValueError as e:
                errors.append(f"Bracket '{bracket}': {e}")
            
            if not isinstance(factor, (int, float)) or isinstance(factor, bool):
                errors.append(self._format_type_error(f"config.rank_scaling.factors.{bracket}", "float", factor))
                continue
            if not BracketValidator.validate_factor(factor):
                errors.append(self.tr.t("err_factor_range") + f" ('{bracket}': {factor})")
        
        # Validate rank scores
        ranks = self.config_data.get('ranks', {})
        if ranks:
            if not isinstance(ranks, dict):
                errors.append(self._format_type_error("config.ranks", "dict", ranks))
            else:
                for country, rank_list in ranks.items():
                    if not isinstance(rank_list, list):
                        errors.append(self._format_type_error(f"config.ranks.{country}", "list", rank_list))
                        continue
                    scores = []
                    for idx, entry in enumerate(rank_list):
                        if not isinstance(entry, dict):
                            errors.append(
                                self._format_type_error(f"config.ranks.{country}[{idx}]", "dict", entry)
                            )
                            continue
                        score = entry.get('score', 0)
                        if not isinstance(score, int) or isinstance(score, bool):
                            errors.append(
                                self._format_type_error(
                                    f"config.ranks.{country}[{idx}].score",
                                    "int",
                                    score,
                                )
                            )
                            continue
                        scores.append(score)
                    is_valid, invalid_idx = ScoreValidator.validate_ascending(scores)
                    if scores and not is_valid:
                        errors.append(
                            self.tr.t("err_score_not_ascending", index=invalid_idx) + f" ({country})"
                        )
        
        # Validate campaign offsets
        if self.mission_dates_data:
            min_off, max_off = OffsetValidator.get_range()
            if not isinstance(self.mission_dates_data, dict):
                errors.append(self._format_type_error("mission_dates", "dict", self.mission_dates_data))
            else:
                for campaign, data in self.mission_dates_data.items():
                    if campaign == "game_directory":
                        if data is not None and not isinstance(data, str):
                            errors.append(
                                self._format_type_error("mission_dates.game_directory", "str", data)
                            )
                        continue
                    if not isinstance(data, dict):
                        errors.append(self._format_type_error(f"mission_dates.{campaign}", "dict", data))
                        continue
                    offset = data.get('starting_rank_offset', 0)
                    if not isinstance(offset, int) or isinstance(offset, bool):
                        errors.append(
                            self._format_type_error(
                                f"mission_dates.{campaign}.starting_rank_offset",
                                "int",
                                offset,
                            )
                        )
                        continue
                    if not OffsetValidator.validate(offset):
                        errors.append(
                            self.tr.t("err_offset_range", min=min_off, max=max_off) + f" ({campaign})"
                        )

        # Validate AI story provider/model/url settings
        errors.extend(self._validate_story_settings_for_save())

        return errors
    
    def _save_all(self) -> bool:
        """Save all changes. Returns True on success."""
        try:
            # Save settings JSON
            if self.settings_data != self.original_data['settings']:
                save_json_atomic(SETTINGS_JSON_PATH, self.settings_data)
            
            # Save config YAML
            if self.config_data != self.original_data['config']:
                save_yaml_atomic(CONFIG_YAML_PATH, self.config_data)
            
            # Save mission dates JSON
            if self.mission_dates_data and self.mission_dates_data != self.original_data['mission_dates']:
                save_json_atomic(MISSION_DATES_PATH, self.mission_dates_data)

            # Save stock campaigns YAML
            if self.stock_campaigns_data != self.original_data['stock_campaigns']:
                save_yaml_atomic(STOCK_CAMPAIGNS_PATH, self.stock_campaigns_data or {"stock_campaigns": {}})
            
            # Update originals
            self.original_data = {
                'settings': deepcopy(self.settings_data),
                'config': deepcopy(self.config_data),
                'mission_dates': deepcopy(self.mission_dates_data) if self.mission_dates_data else None,
                'stock_campaigns': deepcopy(self.stock_campaigns_data) if self.stock_campaigns_data else None,
            }
            
            return True
            
        except Exception as e:
            messagebox.showerror(
                self.tr.t("msg_error_title"),
                self.tr.t("msg_save_error", error=str(e))
            )
            return False
    
    def _has_unsaved_changes(self) -> bool:
        """Check if there are unsaved changes."""
        self._collect_changes()
        
        if self.settings_data != self.original_data['settings']:
            return True
        if self.config_data != self.original_data['config']:
            return True
        if self.mission_dates_data and self.mission_dates_data != self.original_data['mission_dates']:
            return True
        if self.stock_campaigns_data != self.original_data['stock_campaigns']:
            return True
        
        return False
    
    def _apply_changes(self, close_after: bool = False) -> bool:
        """Apply changes and optionally close the window."""
        # Check if Tracker is running - warn user to avoid file locking issues
        if _is_tracker_running():
            result = messagebox.askyesno(
                self.tr.t("msg_confirm_title"),
                self.tr.t("msg_tracker_running_warning"),
            )
            if not result:
                return False

        previous_locale = None
        previous_rank_scaling = None
        previous_ranks = None

        if isinstance(self.original_data.get("settings"), dict):
            previous_locale = self.original_data["settings"].get("locale")
        
        if isinstance(self.original_data.get("config"), dict):
            previous_rank_scaling = deepcopy(self.original_data["config"].get("rank_scaling"))
            previous_ranks = deepcopy(self.original_data["config"].get("ranks"))

        self._collect_changes()
        self._rebuild_rank_scaling_factors()

        normalization_errors = self._normalize_all()
        if normalization_errors:
            messagebox.showerror(
                self.tr.t("msg_error_title"),
                "\n".join(normalization_errors)
            )
            return False

        self._log_normalized_settings()
        
        # Validate
        errors = self._validate_all()
        if errors:
            messagebox.showerror(
                self.tr.t("msg_error_title"),
                "\n".join(errors)
            )
            return False
        
        # Save
        if self._save_all():
            current_locale = self.settings_data.get("locale")
            current_rank_scaling = self.config_data.get("rank_scaling")
            current_ranks = self.config_data.get("ranks")
            
            locale_changed = bool(current_locale and current_locale != previous_locale)
            rank_scaling_changed = current_rank_scaling != previous_rank_scaling
            ranks_changed = current_ranks != previous_ranks
            
            # Force regenerate if locale, rank_scaling, or ranks changed
            needs_regenerate = locale_changed or rank_scaling_changed or ranks_changed
            
            if needs_regenerate:
                # Use current locale for regeneration
                regen_locale = current_locale or previous_locale or "en"

                # Log what changed
                changes = []
                if locale_changed:
                    changes.append("locale")
                if rank_scaling_changed:
                    changes.append("rank_scaling")
                if ranks_changed:
                    changes.append("ranks")
                print(f"[Settings Manager] Changes detected: {', '.join(changes)} - triggering regeneration")

                # Full regeneration will handle all campaigns, so clear the per-campaign set
                self._campaigns_needing_debriefings_regen.clear()

                # Track locale change so _on_locale_refresh_complete can restart the GUI
                self._pending_locale = current_locale if locale_changed else None

                self._start_locale_refresh(regen_locale, close_after=close_after)
                return True

            # Regenerate localized debriefings for campaigns with changed language setting
            if self._campaigns_needing_debriefings_regen:
                campaigns_to_regen = list(self._campaigns_needing_debriefings_regen)
                print(f"[Settings Manager] Regenerating localized debriefings for {len(campaigns_to_regen)} campaign(s): {campaigns_to_regen}")

                error = self._regenerate_debriefings_subprocess(campaigns_to_regen)
                if error:
                    messagebox.showwarning(
                        self.tr.t("msg_confirm_title"),
                        f"Debriefings regeneration issue:\n{error}\n\nSettings were saved successfully."
                    )

                self._campaigns_needing_debriefings_regen.clear()

            messagebox.showinfo(
                self.tr.t("msg_confirm_title"),
                self.tr.t("msg_save_success")
            )
            if close_after:
                self.destroy()
            return True
        return False

    def _set_refresh_controls(self, running: bool) -> None:
        """Enable/disable controls during locale refresh."""
        state = tk.DISABLED if running else tk.NORMAL
        self.ok_button.configure(state=state)
        print(f"[Settings Manager] Refresh controls {'disabled' if running else 'enabled'}")

    def _start_locale_refresh(self, locale: Optional[str], close_after: bool) -> None:
        """Start locale refresh in a background thread."""
        if not locale:
            return
        if self._refresh_thread and self._refresh_thread.is_alive():
            return

        self._close_after_refresh = close_after
        self._refresh_status_var.set(self.tr.t("msg_locale_refresh_running"))
        self._set_refresh_controls(True)
        self._refresh_running = True
        self._refresh_start_time = time.monotonic()
        self._refresh_queue = queue.Queue()
        if self._refresh_poll_id:
            self.after_cancel(self._refresh_poll_id)
            self._refresh_poll_id = None

        def worker() -> None:
            refresh_errors = self._refresh_localized_artifacts(locale)
            self._refresh_queue.put(refresh_errors)

        self._refresh_thread = threading.Thread(target=worker, daemon=True)
        self._refresh_thread.start()
        self._poll_refresh_queue()

    def _poll_refresh_queue(self) -> None:
        """Poll the refresh queue for completion; update elapsed-time label while waiting."""
        if not self._refresh_running:
            return
        try:
            refresh_errors = self._refresh_queue.get_nowait()
        except queue.Empty:
            elapsed_s = int(time.monotonic() - self._refresh_start_time)
            mm, ss = elapsed_s // 60, elapsed_s % 60
            base = self.tr.t("msg_locale_refresh_running")
            self._refresh_status_var.set(f"{base} {mm:02d}:{ss:02d}")
            self._refresh_poll_id = self.after(200, self._poll_refresh_queue)
            return
        self._on_locale_refresh_complete(refresh_errors)

    def _on_locale_refresh_complete(self, refresh_errors: Optional[str]) -> None:
        """Handle completion of locale refresh."""
        if self._refresh_poll_id:
            self.after_cancel(self._refresh_poll_id)
            self._refresh_poll_id = None
        self._refresh_running = False
        self._refresh_status_var.set("")
        self._set_refresh_controls(False)

        locale_did_change = bool(self._pending_locale)
        self._pending_locale = None

        if refresh_errors:
            messagebox.showerror(
                self.tr.t("msg_error_title"),
                self.tr.t("msg_locale_refresh_failed", error=refresh_errors)
            )
            if self._close_after_refresh:
                self.destroy()
            return

        if locale_did_change:
            # Language changed: restart the Settings Manager so the GUI reflects the new locale.
            messagebox.showinfo(
                self.tr.t("msg_confirm_title"),
                f"{self.tr.t('msg_save_success')}\n\n{self.tr.t('msg_locale_refresh')}\n\n"
                "Settings Manager will restart to apply the new language."
            )
            self._restart_app()
            return

        messagebox.showinfo(
            self.tr.t("msg_confirm_title"),
            f"{self.tr.t('msg_save_success')}\n\n{self.tr.t('msg_locale_refresh')}"
        )
        if self._close_after_refresh:
            self.destroy()

    def _restart_app(self) -> None:
        """Close and relaunch the Settings Manager so the GUI picks up the new locale."""
        import subprocess
        try:
            if getattr(sys, 'frozen', False):
                subprocess.Popen([sys.executable])
            else:
                subprocess.Popen([sys.executable] + sys.argv)
        except Exception as exc:
            print(f"[Settings Manager] Failed to restart: {exc}")
        self.destroy()

    def _regenerate_debriefings_subprocess(self, campaigns: List[str]) -> Optional[str]:
        """Regenerate localized debriefings for specific campaigns via Tracker EXE.

        This runs the Tracker EXE with --regen-debriefings to regenerate localized
        debriefings (en/de/ru) for campaigns where the user changed the detail page
        language setting. Uses elevation if required (for reading FlightLogs).

        Args:
            campaigns: List of campaign names to regenerate debriefings for

        Returns:
            None on success, error message string on failure
        """
        if not campaigns:
            return None

        from pathlib import Path
        import sys

        # Determine the directory containing the EXEs
        if getattr(sys, 'frozen', False):
            exe_dir = Path(sys.executable).resolve().parent
        else:
            exe_dir = Path(__file__).resolve().parent.parent

        tracker_exe = exe_dir / "IL2_CampaignTracker_v2.2_ML.exe"
        print(f"[Settings Manager] Looking for Tracker EXE at: {tracker_exe}")

        if not tracker_exe.exists():
            # Fallback: try direct Python import (won't have elevation)
            print("[Settings Manager] Tracker EXE not found, trying direct Python import...")
            try:
                from step3_generate_events import regenerate_campaign_localized_debriefings
                for campaign in campaigns:
                    regenerate_campaign_localized_debriefings(campaign)
                return None
            except Exception as e:
                return f"Failed to regenerate debriefings: {e}"

        # Build command args
        cmd_args = ["--regen-debriefings"] + campaigns

        log_name = f"settings_manager_debriefings_{datetime.now():%Y%m%d_%H%M%S}.log"
        log_path = exe_dir / log_name
        print(f"[Settings Manager] Debriefings regeneration log: {log_path}")

        # Try normal subprocess launch first
        needs_elevation = False

        try:
            startupinfo = None
            creationflags = 0
            if sys.platform == 'win32':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
                creationflags = subprocess.CREATE_NO_WINDOW

            with open(log_path, "w", encoding="utf-8") as log_file:
                result = subprocess.run(
                    [str(tracker_exe)] + cmd_args,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    text=True,
                    cwd=str(exe_dir),
                    stdin=subprocess.DEVNULL,
                    startupinfo=startupinfo,
                    creationflags=creationflags,
                    timeout=300,  # 5 minute timeout
                )

            if result.returncode == 0:
                print("[Settings Manager] Debriefings regeneration completed successfully")
                return None
            else:
                error_output = self._read_log_excerpt(log_path)
                # Check if it's a permission error
                if "Permission denied" in error_output or "Errno 13" in error_output:
                    needs_elevation = True
                else:
                    return f"Debriefings regeneration failed (exit code {result.returncode}):\n{error_output}"

        except OSError as e:
            if sys.platform == 'win32' and getattr(e, 'winerror', None) == _ERROR_ELEVATION_REQUIRED:
                print("[Settings Manager] Elevation required (WinError 740)")
                needs_elevation = True
            else:
                return f"Could not run Tracker EXE: {e}"
        except subprocess.TimeoutExpired:
            return "Debriefings regeneration timed out (5 minutes)"
        except Exception as e:
            return f"Debriefings regeneration error: {e}"

        # Handle elevated launch if required
        if needs_elevation:
            print("[Settings Manager] Requesting elevation for debriefings regeneration...")
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(f"[Settings Manager] Launching with elevation at {datetime.now()}\n")

            success, return_code, error_msg = _run_elevated_windows(
                str(tracker_exe),
                cmd_args,
                str(exe_dir),
                str(log_path),
                env=None,
                timeout_seconds=300,
            )

            if not success:
                if error_msg == "UAC_CANCELLED":
                    return (
                        "Administrator rights are required to regenerate debriefings.\n\n"
                        "Please click 'Yes' on the User Account Control prompt when asked."
                    )
                elif error_msg == "TIMEOUT":
                    return "Debriefings regeneration timed out (5 minutes)"
                else:
                    return f"Elevated launch failed: {error_msg}"

            if return_code != 0:
                error_output = self._read_log_excerpt(log_path)
                return f"Debriefings regeneration failed (exit code {return_code}):\n{error_output}"

            print("[Settings Manager] Debriefings regeneration completed successfully via elevation")

        return None

    def _refresh_localized_artifacts(self, locale: Optional[str]) -> Optional[str]:
        """Regenerate localized mission text and PDFs after a locale change.
        
        This method MUST run IL2_CampaignTracker_v2.2_ML.exe as a subprocess because:
        1. PIL/Pillow is bundled only in the Tracker EXE (needed for image conversion)
        2. wkhtmltopdf is bundled only in the Tracker EXE (needed for PDF generation)
        
        If subprocess fails, it falls back to module import (but PDFs won't work).
        """
        if not locale:
            return None
        
        from pathlib import Path
        import sys
        
        # Determine the directory containing the EXEs
        # Both IL2_CampaignTracker_v2.2_ML.exe and IL2_Settings_Manager.exe should be in the same directory
        if getattr(sys, 'frozen', False):
            # Running as compiled EXE - get directory of this EXE
            exe_dir = Path(sys.executable).resolve().parent
            print(f"[Settings Manager] Running as EXE from: {exe_dir}")
        else:
            # Running as Python script - look in parent of settings_manager folder
            exe_dir = Path(__file__).resolve().parent.parent
            print(f"[Settings Manager] Running as script, looking in: {exe_dir}")
        
        tracker_exe = exe_dir / "IL2_CampaignTracker_v2.2_ML.exe"
        print(f"[Settings Manager] Looking for Tracker EXE at: {tracker_exe}")
        print(f"[Settings Manager] Tracker EXE exists: {tracker_exe.exists()}")
        
        # Prepare environment with FORCE_REGENERATE (for non-elevated launch)
        env = os.environ.copy()
        env["FORCE_REGENERATE"] = "1"

        # REQUIRED: Run the Tracker EXE as subprocess for proper PDF generation
        if tracker_exe.exists():
            print(f"[Settings Manager] Starting Tracker EXE with locale={locale}...")
            # Use --force-regen flag (works reliably for both normal and elevated launches)
            cmd_args = ["--auto", "--locale", locale, "--skip-monitor", "--non-interactive", "--force-regen"]

            log_name = f"settings_manager_refresh_{datetime.now():%Y%m%d_%H%M%S}.log"
            log_path = exe_dir / log_name
            print(f"[Settings Manager] Regeneration log: {log_path}")

            # Try normal subprocess launch first
            needs_elevation = False
            process = None

            try:
                # Use CREATE_NO_WINDOW on Windows to prevent console popup
                startupinfo = None
                creationflags = 0
                if sys.platform == 'win32':
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    startupinfo.wShowWindow = subprocess.SW_HIDE
                    creationflags = subprocess.CREATE_NO_WINDOW

                with open(log_path, "w", encoding="utf-8") as log_file:
                    process = subprocess.Popen(
                        [str(tracker_exe)] + cmd_args,
                        env=env,
                        stdout=log_file,
                        stderr=subprocess.STDOUT,
                        text=True,
                        cwd=str(exe_dir),
                        stdin=subprocess.DEVNULL,
                        startupinfo=startupinfo,
                        creationflags=creationflags,
                    )
            except OSError as e:
                # Check for Windows elevation required error (WinError 740)
                if sys.platform == 'win32' and getattr(e, 'winerror', None) == _ERROR_ELEVATION_REQUIRED:
                    print(f"[Settings Manager] Elevation required (WinError 740), requesting admin rights...")
                    needs_elevation = True
                else:
                    print(f"[Settings Manager] Subprocess error: {e}")
                    return f"Could not run Tracker EXE: {e}"
            except Exception as e:
                print(f"[Settings Manager] Subprocess error: {e}")
                return f"Could not run Tracker EXE: {e}"

            # Handle elevated launch if required
            if needs_elevation:
                # Create empty log file for elevated process to write to
                with open(log_path, "w", encoding="utf-8") as f:
                    f.write(f"[Settings Manager] Launching with elevation at {datetime.now()}\n")

                # --force-regen flag in cmd_args handles regeneration; no env vars needed
                success, return_code, error_msg = _run_elevated_windows(
                    str(tracker_exe),
                    cmd_args,
                    str(exe_dir),
                    str(log_path),
                    env=None,  # No environment variables needed (--force-regen flag handles it)
                    timeout_seconds=600,
                )

                if not success:
                    if error_msg == "UAC_CANCELLED":
                        return (
                            "Administrator rights are required to regenerate mission texts and PDFs.\n\n"
                            "Please click 'Yes' on the User Account Control prompt when asked."
                        )
                    elif error_msg == "TIMEOUT":
                        return "Tracker process timed out (10 minutes)"
                    else:
                        return f"Elevated launch failed: {error_msg}"

                if return_code != 0:
                    error_output = self._read_log_excerpt(log_path)
                    print(f"[Settings Manager] Elevated Tracker output: {error_output[:1000]}")
                    return (
                        f"Tracker EXE error. Exit code: {return_code}.\n\n"
                        f"Full log: {log_path}\n\n"
                        f"Log excerpt:\n{error_output}"
                    )

                print("[Settings Manager] Locale refresh completed successfully via elevated Tracker EXE")
                return None

            # Normal (non-elevated) launch succeeded - continue with polling loop
            if process is None:
                return "Failed to start Tracker process"

            print(f"[Settings Manager] Tracker EXE PID: {process.pid}")
            completion_marker = "COMPLETE!"
            timeout_seconds = 600
            poll_interval = 0.5
            log_interval = 1.0
            start_time = time.monotonic()
            next_log_time = start_time + log_interval
            log_position = 0
            completion_detected = False

            try:
                while True:
                    return_code = process.poll()
                    if return_code is not None:
                        elapsed_s = int(time.monotonic() - start_time)
                        mm, ss = elapsed_s // 60, elapsed_s % 60
                        print(f"[Settings Manager] Tracker EXE exited with return code: {return_code}")
                        if return_code != 0 and not completion_detected:
                            error_output = self._read_log_excerpt(log_path)
                            print(f"[Settings Manager] Tracker output: {error_output[:1000]}")
                            return (
                                "Tracker EXE error. "
                                f"Exit code: {return_code}.\n\n"
                                f"Log: {log_path}\n\n"
                                f"Log excerpt:\n{error_output}"
                            )
                        print(f"[Settings Manager] Completed in {mm:02d}:{ss:02d}")
                        return None

                    now = time.monotonic()
                    if now >= next_log_time:
                        elapsed_s = int(now - start_time)
                        mm, ss = elapsed_s // 60, elapsed_s % 60
                        print(f"[Settings Manager] Applying language\u2026 elapsed {mm:02d}:{ss:02d}")
                        next_log_time = now + log_interval

                    if now - start_time > timeout_seconds:
                        elapsed_s = int(now - start_time)
                        mm, ss = elapsed_s // 60, elapsed_s % 60
                        print(f"[Settings Manager] Tracker EXE timed out after {mm:02d}:{ss:02d}")
                        self._terminate_process(process)
                        return "Tracker process timed out (10 minutes)"

                    log_position_holder = [log_position]
                    completion_detected = completion_detected or self._log_has_marker(
                        log_path,
                        completion_marker,
                        log_position_holder=log_position_holder,
                    )
                    log_position = log_position_holder[0]

                    if completion_detected:
                        elapsed_s = int(time.monotonic() - start_time)
                        mm, ss = elapsed_s // 60, elapsed_s % 60
                        print(f"[Settings Manager] Completion marker detected. Completed in {mm:02d}:{ss:02d}")
                        self._terminate_process(process)
                        return None

                    time.sleep(poll_interval)
            except Exception as e:
                print(f"[Settings Manager] Polling error: {e}")
                if process:
                    self._terminate_process(process)
                return f"Error during Tracker execution: {e}"
        else:
            # Tracker EXE not found - this is a configuration error
            error_msg = (
                f"IL2_CampaignTracker_v2.2_ML.exe not found at {tracker_exe}\n"
                "Please ensure both EXE files are in the same directory.\n"
                "PDF generation requires the Tracker EXE."
            )
            print(f"[Settings Manager] ERROR: {error_msg}")
            
            # Fall back to module import (won't generate PDFs properly)
            print("[Settings Manager] Falling back to module import (PDFs will NOT be generated)")
            try:
                from step3_generate_events import main as generate_events_main
            except Exception as exc:
                return f"Tracker EXE not found and module import failed: {exc}"

            previous_force = os.environ.get("FORCE_REGENERATE")
            os.environ["FORCE_REGENERATE"] = "1"
            try:
                success = generate_events_main(args=["--auto", "--locale", locale])
                if not success:
                    return "Event regeneration failed (and PDFs were not generated - Tracker EXE required)"
            except Exception as exc:
                return str(exc)
            finally:
                if previous_force is None:
                    os.environ.pop("FORCE_REGENERATE", None)
                else:
                    os.environ["FORCE_REGENERATE"] = previous_force
            
            # Return warning that PDFs weren't generated
            return None  # Locale files updated, but warn about PDFs

    @staticmethod
    def _read_log_excerpt(log_path, max_lines: int = 20) -> str:
        """Read the last lines of a log file for error reporting."""
        try:
            with open(log_path, "r", encoding="utf-8") as log_file:
                lines = log_file.readlines()
        except Exception as exc:
            return f"Could not read log file {log_path}: {exc}"

        excerpt = lines[-max_lines:]
        return "".join(excerpt).strip() or "No log output captured."

    @staticmethod
    def _log_has_marker(
        log_path,
        marker: str,
        log_position_holder: list,
    ) -> bool:
        """Check if a log file contains a marker since the last read position."""
        try:
            with open(log_path, "r", encoding="utf-8", errors="ignore") as log_file:
                log_file.seek(log_position_holder[0])
                chunk = log_file.read()
                log_position_holder[0] = log_file.tell()
        except FileNotFoundError:
            return False
        except Exception as exc:
            print(f"[Settings Manager] Log read error: {exc}")
            return False
        if not chunk:
            return False
        return marker in chunk

    @staticmethod
    def _terminate_process(process) -> None:
        """Terminate a process (and its children on Windows)."""
        try:
            if process.poll() is not None:
                return
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            else:
                process.terminate()
            try:
                process.wait(timeout=5)
            except Exception:
                process.kill()
        except Exception as exc:
            print(f"[Settings Manager] Failed to terminate process: {exc}")

    def _on_apply(self) -> bool:
        """Apply changes."""
        return self._apply_changes(close_after=False)
    
    def _on_ok(self) -> None:
        """OK button - apply and close."""
        self._apply_changes(close_after=True)
    
    def _on_cancel(self) -> None:
        """Cancel button."""
        if self._refresh_thread and self._refresh_thread.is_alive():
            messagebox.showinfo(
                self.tr.t("msg_confirm_title"),
                self.tr.t("msg_locale_refresh_running")
            )
            return
        if self._has_unsaved_changes():
            if not messagebox.askyesno(
                self.tr.t("msg_confirm_title"),
                self.tr.t("msg_unsaved_changes")
            ):
                return
        self.destroy()
    
    def _on_close(self) -> None:
        """Window close handler."""
        self._on_cancel()

    # ------------------------------------------------------------------
    # Tab 8: Squadron Roster
    # ------------------------------------------------------------------

    def _create_squadron_roster_tab(self) -> None:
        """Create Squadron Roster tab for editing pilot data in cp.db."""
        frame = ttk.Frame(self.notebook, padding=20)
        self.notebook.add(frame, text=self.tr.t("tab_squadron_roster"))

        careers = self._load_careers_from_db()
        if careers is None:
            ttk.Label(
                frame,
                text=self.tr.t("msg_career_db_not_found"),
                foreground="gray",
            ).pack(pady=50)
            return
        if not careers:
            ttk.Label(
                frame,
                text=self.tr.t("msg_no_careers"),
                foreground="gray",
            ).pack(pady=50)
            return

        # Helper text
        ttk.Label(
            frame,
            text=self.tr.t("lbl_squadron_roster_helper"),
            foreground="gray",
            wraplength=520,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(0, 10))

        # Career selection dropdown — one entry per distinct career chain.
        # The roster always shows the latest theatre segment for the chosen career.
        sel_row = ttk.Frame(frame)
        sel_row.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(sel_row, text=self.tr.t("lbl_select_career")).pack(side=tk.LEFT)

        self._roster_career_ids = [cid for cid, _ in careers]
        self._roster_career_combo = ttk.Combobox(
            sel_row,
            values=[name for _, name in careers],
            state="readonly",
            width=40,
        )
        self._roster_career_combo.pack(side=tk.LEFT, padx=(10, 0))
        self._roster_career_combo.current(0)
        self._roster_career_combo.bind("<<ComboboxSelected>>", self._on_roster_career_selected)

        # Treeview in a sub-frame
        tree_frame = ttk.Frame(frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        cols = [col_id for col_id, *_ in self._ROSTER_TREE_COLS]
        self._roster_tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=14)

        col_labels = {
            "first_name":   self.tr.t("lbl_first_name"),
            "last_name":    self.tr.t("lbl_last_name"),
            "ai_level":     self.tr.t("lbl_ai_level"),
            "pcp":          self.tr.t("lbl_pcp"),
            "sorties":      self.tr.t("lbl_sorties"),
            "good_sorties": self.tr.t("lbl_good_sorties"),
            "state":        self.tr.t("lbl_state"),
        }
        for col_id, _db_col, width, is_num in self._ROSTER_TREE_COLS:
            self._roster_tree.heading(col_id, text=col_labels[col_id])
            self._roster_tree.column(col_id, width=width, anchor=tk.CENTER if is_num else tk.W)

        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self._roster_tree.yview)
        self._roster_tree.configure(yscrollcommand=vsb.set)
        self._roster_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        self._roster_tree.bind("<Double-1>", self._on_roster_cell_double_click)

        # Bottom bar
        bar = ttk.Frame(frame)
        bar.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(bar, text=self.tr.t("btn_save_changes"), command=self._on_roster_save, style="Action.TButton").pack(side=tk.LEFT)
        ttk.Button(bar, text=self.tr.t("btn_discard_changes"), command=self._on_roster_discard).pack(
            side=tk.LEFT, padx=(8, 0)
        )
        ttk.Button(bar, text="Restore Database", command=self._restore_database).pack(
            side=tk.RIGHT, padx=(8, 0)
        )
        ttk.Label(bar, textvariable=self._roster_status_var, foreground="gray").pack(
            side=tk.LEFT, padx=(12, 0)
        )

        # Load roster for the first (most recently started) career
        self._load_roster_for_career(self._roster_career_ids[0])

    def _on_roster_career_selected(self, event: tk.Event) -> None:
        """Reload the roster when the user picks a different career."""
        if self._roster_career_combo is None:
            return
        idx = self._roster_career_combo.current()
        if 0 <= idx < len(self._roster_career_ids):
            self._load_roster_for_career(self._roster_career_ids[idx])

    def _load_roster_for_career(self, career_id: int) -> None:
        """Query cp.db for all pilots in the squadron of the given root career."""
        self._roster_current_career_id = career_id
        game_dir = (self.mission_dates_data or {}).get("game_directory")
        if not game_dir:
            return
        db_path = os.path.join(str(game_dir), "data", "Career", "cp.db")
        if not os.path.isfile(db_path):
            return

        self._roster_pilot_data = {}
        self._roster_pending_changes = {}
        if self._roster_status_var:
            self._roster_status_var.set("")

        try:
            uri = f"file:{db_path}?mode=ro"
            con = sqlite3.connect(uri, uri=True, timeout=5)
            con.row_factory = sqlite3.Row

            # Traverse the career chain to find the latest segment's squadronId
            cur = con.execute(
                """
                WITH RECURSIVE chain(id, playerId) AS (
                    SELECT id, playerId FROM career WHERE id = ?
                    UNION ALL
                    SELECT c.id, c.playerId FROM career c JOIN chain ON c.extends = chain.id
                )
                SELECT p.squadronId
                FROM chain
                JOIN pilot p ON p.id = chain.playerId
                ORDER BY chain.id DESC
                LIMIT 1
                """,
                [career_id],
            )
            row = cur.fetchone()
            if row is None:
                con.close()
                return
            squadron_id = row[0]

            # Fetch all non-deleted pilots in that squadron
            cur = con.execute(
                """
                SELECT id, name, lastName, AILevel, pcp, sorties, goodSorties, state
                FROM pilot
                WHERE squadronId = ? AND isDeleted = 0
                ORDER BY rankId DESC,
                         (COALESCE(killLightPlane,0) + COALESCE(killMediumPlane,0)
                          + COALESCE(killHeavyPlane,0) + COALESCE(killStaticPlane,0)) DESC
                """,
                [squadron_id],
            )
            rows = cur.fetchall()
            con.close()

            for r in rows:
                iid = str(r["id"])
                self._roster_pilot_data[iid] = {
                    "id":          r["id"],
                    "name":        r["name"] or "",
                    "lastName":    r["lastName"] or "",
                    "AILevel":     r["AILevel"] if r["AILevel"] is not None else 1,
                    "pcp":         float(r["pcp"]) if r["pcp"] is not None else 0.0,
                    "sorties":     int(r["sorties"]) if r["sorties"] is not None else 0,
                    "goodSorties": int(r["goodSorties"]) if r["goodSorties"] is not None else 0,
                    "state":       int(r["state"]) if r["state"] is not None else 0,
                }

            self._populate_roster_tree()

        except Exception as exc:
            logger.warning("_load_roster_for_career failed: %s", exc, exc_info=True)

    def _populate_roster_tree(self) -> None:
        """Rebuild the roster treeview from _roster_pilot_data (with pending changes overlaid)."""
        if self._roster_tree is None:
            return
        self._destroy_roster_editor()
        self._roster_tree.delete(*self._roster_tree.get_children())

        for iid, data in self._roster_pilot_data.items():
            changes = self._roster_pending_changes.get(iid, {})
            merged = dict(data)
            merged.update(changes)

            state_int = int(merged.get("state", 0))
            state_text = self.PILOT_STATES.get(state_int, str(state_int))

            values = (
                merged.get("name", ""),
                merged.get("lastName", ""),
                merged.get("AILevel", 1),
                f"{float(merged.get('pcp', 0.0)):.1f}",
                merged.get("sorties", 0),
                merged.get("goodSorties", 0),
                state_text,
            )
            tag = "pending" if iid in self._roster_pending_changes else ""
            self._roster_tree.insert(
                "", tk.END, iid=iid, values=values, tags=(tag,) if tag else ()
            )

        self._roster_tree.tag_configure("pending", foreground="#cc6600")

    def _on_roster_cell_double_click(self, event: tk.Event) -> None:
        """Start inline editing on double-click of a roster cell."""
        if self._roster_tree is None:
            return
        region = self._roster_tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        col = self._roster_tree.identify_column(event.x)
        item = self._roster_tree.identify_row(event.y)
        if not item or not col:
            return
        col_idx = int(col[1:]) - 1
        if col_idx < 0 or col_idx >= len(self._ROSTER_TREE_COLS):
            return
        col_id = self._ROSTER_TREE_COLS[col_idx][0]
        self._start_roster_cell_edit(item, col_id, col_idx)

    def _start_roster_cell_edit(self, item: str, col_id: str, col_idx: int) -> None:
        """Place an inline editor widget over the given treeview cell."""
        self._destroy_roster_editor()
        if self._roster_tree is None:
            return
        bbox = self._roster_tree.bbox(item, f"#{col_idx + 1}")
        if not bbox:
            return
        x, y, width, height = bbox

        values = self._roster_tree.item(item, "values")
        if not values or col_idx >= len(values):
            return
        current_display = values[col_idx]

        if col_id == "state":
            # WIA and Transferred are set by the game — block manual editing.
            _cur_state = int(
                self._roster_pending_changes.get(item, {}).get(
                    "state",
                    self._roster_pilot_data.get(item, {}).get("state", 0),
                )
            )
            if _cur_state in self._PILOT_STATE_READONLY:
                return
            options = list(self._PILOT_STATE_FROM_NAME.keys())
            editor = ttk.Combobox(self._roster_tree, values=options, state="readonly")
            if current_display in options:
                editor.set(current_display)
            else:
                editor.current(0)
            editor.place(x=x, y=y, width=width, height=height)
            editor.focus_set()
            editor.bind(
                "<<ComboboxSelected>>",
                lambda e: self._commit_roster_edit(item, col_id, editor.get()),
            )
            editor.bind("<FocusOut>", lambda e: self._destroy_roster_editor())
            editor.bind("<Escape>", lambda e: self._destroy_roster_editor())
        else:
            var = tk.StringVar(value=current_display)
            editor = ttk.Entry(self._roster_tree, textvariable=var)
            editor.place(x=x, y=y, width=width, height=height)
            editor.focus_set()
            editor.select_range(0, tk.END)
            editor.bind("<Return>", lambda e: self._commit_roster_edit(item, col_id, var.get()))
            editor.bind("<FocusOut>", lambda e: self._commit_roster_edit(item, col_id, var.get()))
            editor.bind("<Escape>", lambda e: self._destroy_roster_editor())

        self._roster_editor = editor
        self._roster_editor_item = item
        self._roster_editor_col = col_id

    def _commit_roster_edit(self, item: str, col_id: str, raw_value: str) -> None:
        """Validate and record a cell edit, then refresh the tree row."""
        if self._roster_editor_item != item:
            return
        self._destroy_roster_editor()
        if item not in self._roster_pilot_data:
            return

        original = self._roster_pilot_data[item]
        pending = self._roster_pending_changes.get(item, {})

        try:
            if col_id == "state":
                new_val = self._PILOT_STATE_FROM_NAME.get(raw_value)
                if new_val is None:
                    return
            elif col_id == "ai_level":
                new_val = int(raw_value)
            elif col_id == "pcp":
                new_val = float(raw_value)
            elif col_id in ("sorties", "good_sorties"):
                new_val = int(raw_value)
            else:
                new_val = raw_value.strip()
        except (ValueError, TypeError):
            return

        # Map tree column id to DB column name
        db_col = next(
            (db for cid, db, *_ in self._ROSTER_TREE_COLS if cid == col_id), None
        )
        if not db_col:
            return

        # Compare against current effective value (pending overrides original)
        current_val = pending.get(db_col, original.get(db_col))
        if new_val == current_val:
            return

        if item not in self._roster_pending_changes:
            self._roster_pending_changes[item] = {}
        self._roster_pending_changes[item][db_col] = new_val

        self._populate_roster_tree()
        if self._roster_status_var:
            count = len(self._roster_pending_changes)
            self._roster_status_var.set(f"{count} pending change(s)")

    def _destroy_roster_editor(self) -> None:
        """Destroy any active inline editor in the roster treeview."""
        if self._roster_editor is not None:
            try:
                self._roster_editor.destroy()
            except Exception:
                pass
        self._roster_editor = None
        self._roster_editor_item = None
        self._roster_editor_col = None

    def _restore_database(self) -> None:
        """Let the user pick a cp_backup_*.db file and restore it as cp.db."""
        game_dir = (self.mission_dates_data or {}).get("game_directory")
        if not game_dir:
            messagebox.showerror("Error", "Game directory not set.", parent=self)
            return
        career_dir = os.path.join(str(game_dir), "data", "Career")
        backups = sorted(
            [
                f for f in os.listdir(career_dir)
                if f.startswith("cp_backup_") and f.endswith(".db")
            ],
            reverse=True,
        )
        if not backups:
            messagebox.showinfo("Restore Database", "No backups found.", parent=self)
            return

        dlg = tk.Toplevel(self)
        dlg.title("Restore Database")
        dlg.resizable(False, False)
        dlg.grab_set()

        ttk.Label(dlg, text="Select a backup to restore:").pack(
            padx=16, pady=(12, 4), anchor="w"
        )

        lb_var = tk.StringVar(value=backups)  # type: ignore[arg-type]
        lb = tk.Listbox(dlg, listvariable=lb_var, selectmode=tk.SINGLE,
                        width=38, height=min(len(backups), 12))
        lb.pack(padx=16, pady=4)
        lb.selection_set(0)

        def _do_restore() -> None:
            sel = lb.curselection()
            if not sel:
                return
            chosen = backups[sel[0]]
            if not messagebox.askokcancel(
                "Restore Database",
                f"This will replace the current cp.db with:\n\n{chosen}\n\n"
                "The current cp.db will be saved as cp.db.bak.\n\nProceed?",
                parent=dlg,
            ):
                return
            db_path = os.path.join(career_dir, "cp.db")
            bak_path = os.path.join(career_dir, "cp.db.bak")
            src_path = os.path.join(career_dir, chosen)
            try:
                if os.path.isfile(db_path):
                    shutil.move(db_path, bak_path)
                shutil.move(src_path, db_path)
            except OSError as e:
                messagebox.showerror("Error", str(e), parent=dlg)
                return
            dlg.destroy()
            messagebox.showinfo(
                "Restore Database",
                f"Restored successfully.\nPrevious cp.db saved as cp.db.bak.",
                parent=self,
            )

        btn_frame = ttk.Frame(dlg)
        btn_frame.pack(padx=16, pady=(4, 12), fill=tk.X)
        ttk.Button(btn_frame, text="Restore", command=_do_restore,
                   style="Action.TButton").pack(side=tk.LEFT)
        ttk.Button(btn_frame, text="Cancel", command=dlg.destroy).pack(
            side=tk.LEFT, padx=(8, 0)
        )

    def _on_roster_save(self) -> None:
        """Write all pending roster changes to cp.db."""
        if not self._roster_pending_changes:
            if self._roster_status_var:
                self._roster_status_var.set(self.tr.t("msg_roster_no_changes"))
            return

        count = len(self._roster_pending_changes)
        game_dir = (self.mission_dates_data or {}).get("game_directory")
        if not game_dir:
            messagebox.showerror(
                self.tr.t("msg_error_title"),
                "Game directory not set.",
                parent=self,
            )
            return
        db_path = os.path.join(str(game_dir), "data", "Career", "cp.db")
        if not os.path.isfile(db_path):
            messagebox.showerror(
                self.tr.t("msg_error_title"),
                "cp.db not found.",
                parent=self,
            )
            return

        # ── Auto-backup before every save ───────────────────────────────────────
        _ts = datetime.now().strftime("%Y.%m.%d_%H.%M.%S")
        _backup_path = os.path.join(
            os.path.dirname(db_path), f"cp_backup_{_ts}.db"
        )
        try:
            shutil.copy2(db_path, _backup_path)
        except OSError as _be:
            messagebox.showerror(
                self.tr.t("msg_error_title"),
                f"Could not create backup:\n{_be}",
                parent=self,
            )
            return

        # ── Pre-save: warn if pending changes create duplicate Commander/Deputy ──
        _role_holders: Dict[tuple, list] = {}
        for _iid, _data in self._roster_pilot_data.items():
            _st = int(
                self._roster_pending_changes.get(_iid, {}).get(
                    "state", _data.get("state", 0)
                )
            )
            if _st in (1, 8):
                _sq = int(_data.get("squadronId", 0))
                _role_holders.setdefault((_sq, _st), []).append(
                    f"{_data.get('name', '')} {_data.get('lastName', '')}".strip()
                )
        _conflict_lines = []
        for (_sq, _st), _names in _role_holders.items():
            if len(_names) > 1:
                _role_lbl = (
                    "Squadron Commander" if _st == 1 else "Deputy Commander"
                )
                _conflict_lines.append(
                    f"{_role_lbl}: {', '.join(_names)}"
                    " — one must be demoted to Active"
                )
        if _conflict_lines:
            _msg = (
                "Saving would result in duplicate command roles:\n\n"
                + "\n".join(_conflict_lines)
                + "\n\nThe existing holder will be automatically demoted to Active."
                "\n\nProceed?"
            )
            if not messagebox.askokcancel(
                "Command conflict", _msg, parent=self
            ):
                return

        # Collect (old_first, old_last, new_first, new_last) for each renamed pilot
        # so we can update story files after the DB commit.
        _name_changes: List[Tuple[str, str, str, str]] = []

        try:
            con = sqlite3.connect(str(db_path), timeout=5)
            con.row_factory = sqlite3.Row

            for iid, changes in self._roster_pending_changes.items():
                pilot_id = int(iid)
                original = self._roster_pilot_data.get(iid, {})

                # ── Pre-process state change ────────────────────────────────
                _new_st = int(changes["state"]) if "state" in changes else None
                _old_st = int(original.get("state", 0)) if "state" in changes else None
                _is_res = (
                    _old_st in (2, 3, 4) and _new_st in (0, 1, 8)
                    if _new_st is not None else False
                )

                # For resurrections, also update stateDate to the in-game date.
                if _is_res and "stateDate" not in changes:
                    _dr = con.execute(
                        "SELECT currentDate FROM career"
                        " WHERE playerId = ? AND isDeleted = 0 ORDER BY id DESC LIMIT 1",
                        [pilot_id],
                    ).fetchone()
                    if _dr:
                        changes["stateDate"] = _dr["currentDate"]
                    else:
                        _er = con.execute(
                            "SELECT MAX(date) AS d FROM event"
                            " WHERE pilotId = ? AND isDeleted = 0",
                            [pilot_id],
                        ).fetchone()
                        changes["stateDate"] = (
                            _er["d"][:10] if _er and _er["d"]
                            else datetime.now().strftime("%Y.%m.%d")
                        )

                # ── Main pilot UPDATE ────────────────────────────────────────
                set_parts: List[str] = []
                values: List = []
                for db_col, new_val in changes.items():
                    set_parts.append(f"{db_col} = ?")
                    values.append(new_val)
                values.append(pilot_id)
                con.execute(
                    f"UPDATE pilot SET {', '.join(set_parts)} WHERE id = ?",
                    values,
                )

                # ── Cascade name change to all denormalized fields ────────────
                # The game stores the full pilot name in sortie.name,
                # award.pilotName, and event.tpar1. A player pilot also has
                # one pilot row per theatre (all sharing the same name), so we
                # must update ALL of them together or the game sees inconsistency
                # and can crash when launching a mission.
                if "name" in changes or "lastName" in changes:
                    old_first = str(original.get("name") or "").strip()
                    old_last  = str(original.get("lastName") or "").strip()
                    new_first = str(changes.get("name",     old_first)).strip()
                    new_last  = str(changes.get("lastName", old_last)).strip()

                    if old_first != new_first or old_last != new_last:
                        old_full = f"{old_first} {old_last}".strip()
                        new_full = f"{new_first} {new_last}".strip()
                        _name_changes.append((old_first, old_last, new_first, new_last))

                        # Determine if this is a player pilot by checking whether
                        # any career row references this pilot as playerId.
                        career_entry = con.execute(
                            "SELECT id, extends FROM career"
                            " WHERE playerId = ? AND isDeleted = 0 LIMIT 1",
                            [pilot_id],
                        ).fetchone()

                        if career_entry:
                            # Player pilot: walk UP to the chain root, then DOWN
                            # to collect every theatre's pilot ID.
                            cur_id  = career_entry["id"]
                            extends = career_entry["extends"]
                            while extends != -1:
                                parent = con.execute(
                                    "SELECT id, extends FROM career WHERE id = ?",
                                    [extends],
                                ).fetchone()
                                if not parent:
                                    break
                                cur_id  = parent["id"]
                                extends = parent["extends"]
                            root_id = cur_id

                            chain_pilot_ids: List[int] = []
                            cur_id = root_id
                            while cur_id is not None:
                                c = con.execute(
                                    "SELECT playerId FROM career WHERE id = ?",
                                    [cur_id],
                                ).fetchone()
                                if c:
                                    pid = int(c["playerId"])
                                    if pid not in chain_pilot_ids:
                                        chain_pilot_ids.append(pid)
                                nxt = con.execute(
                                    "SELECT id FROM career"
                                    " WHERE extends = ? AND isDeleted = 0"
                                    " ORDER BY id LIMIT 1",
                                    [cur_id],
                                ).fetchone()
                                cur_id = nxt["id"] if nxt else None
                        else:
                            # AI pilot: single pilot row, no theatre chain.
                            chain_pilot_ids = [pilot_id]

                        ph = ",".join("?" for _ in chain_pilot_ids)

                        # Update name on every theatre copy in pilot table
                        con.execute(
                            f"UPDATE pilot SET name = ?, lastName = ? WHERE id IN ({ph})",
                            [new_first, new_last] + chain_pilot_ids,
                        )
                        # Update denormalized full-name in sortie
                        con.execute(
                            f"UPDATE sortie SET name = ?"
                            f" WHERE pilotId IN ({ph}) AND name = ?",
                            [new_full] + chain_pilot_ids + [old_full],
                        )
                        # Update denormalized full-name in award
                        con.execute(
                            f"UPDATE award SET pilotName = ?"
                            f" WHERE pilotId IN ({ph}) AND pilotName = ?",
                            [new_full] + chain_pilot_ids + [old_full],
                        )
                        # Update tpar1 in event (stores pilot full name for
                        # appointment / squadron-change event types)
                        con.execute(
                            f"UPDATE event SET tpar1 = ?"
                            f" WHERE pilotId IN ({ph}) AND tpar1 = ?",
                            [new_full] + chain_pilot_ids + [old_full],
                        )

                if _new_st is not None and _new_st != _old_st:
                    # ── Sortie update ────────────────────────────────────────
                    sortie_row = con.execute(
                        "SELECT id, missionId FROM sortie"
                        " WHERE pilotId = ? AND status = ? AND isDeleted = 0"
                        " ORDER BY id DESC LIMIT 1",
                        [pilot_id, _old_st],
                    ).fetchone()
                    if sortie_row:
                        if _is_res:
                            con.execute(
                                "UPDATE sortie SET status = ?, planeStatus = 1 WHERE id = ?",
                                [_new_st, sortie_row["id"]],
                            )
                            # Hard-delete the linked death event (type 3/4/5)
                            msn_id = sortie_row["missionId"]
                            if msn_id and msn_id != -1:
                                con.execute(
                                    "DELETE FROM event"
                                    " WHERE pilotId = ? AND missionId = ?"
                                    " AND type IN (3, 4, 5)",
                                    [pilot_id, msn_id],
                                )
                        else:
                            con.execute(
                                "UPDATE sortie SET status = ? WHERE id = ?",
                                [_new_st, sortie_row["id"]],
                            )

                    # ── Career reset (player only, resurrection only) ─────────
                    if _is_res:
                        _cr = con.execute(
                            "SELECT id FROM career"
                            " WHERE playerId = ? AND isDeleted = 0 ORDER BY id DESC LIMIT 1",
                            [pilot_id],
                        ).fetchone()
                        if _cr:
                            con.execute(
                                "UPDATE career SET state = 0 WHERE id = ?",
                                [_cr["id"]],
                            )

                    # ── Commander / Deputy appointment ───────────────────────
                    if _new_st in (1, 8):
                        _ev_type = 7 if _new_st == 1 else 24
                        _sq_id = int(original.get("squadronId", 0))

                        # Enforce uniqueness: demote any existing holder
                        for _ex in con.execute(
                            "SELECT id FROM pilot WHERE squadronId = ? AND state = ?"
                            " AND id != ? AND isDeleted = 0",
                            [_sq_id, _new_st, pilot_id],
                        ).fetchall():
                            con.execute(
                                "UPDATE pilot SET state = 0 WHERE id = ?", [_ex["id"]]
                            )
                            _ex_sortie = con.execute(
                                "SELECT id FROM sortie WHERE pilotId = ? AND status = ?"
                                " AND isDeleted = 0 ORDER BY id DESC LIMIT 1",
                                [_ex["id"], _new_st],
                            ).fetchone()
                            if _ex_sortie:
                                con.execute(
                                    "UPDATE sortie SET status = 0 WHERE id = ?",
                                    [_ex_sortie["id"]],
                                )

                        # Date for the appointment event
                        _ev_date = changes.get(
                            "stateDate", datetime.now().strftime("%Y.%m.%d")
                        )
                        if len(_ev_date) == 10:
                            _ev_date += " 00:00:00"

                        _pr = con.execute(
                            "SELECT name, lastName, rankId FROM pilot WHERE id = ?",
                            [pilot_id],
                        ).fetchone()
                        if _pr:
                            _ca = con.execute(
                                "SELECT id FROM career WHERE playerId = ? AND isDeleted = 0"
                                " ORDER BY id DESC LIMIT 1",
                                [pilot_id],
                            ).fetchone()
                            _care_id = (
                                _ca["id"] if _ca
                                else (self._roster_current_career_id or -1)
                            )
                            _sq_cfg = con.execute(
                                "SELECT configId FROM squadron WHERE id = ?", [_sq_id]
                            ).fetchone()
                            _cfg_id = int(_sq_cfg["configId"]) if _sq_cfg else -1
                            _pname = f"{_pr['name']} {_pr['lastName']}".strip()
                            con.execute(
                                """INSERT INTO event
                                       (date, type, pilotId, rankId, missionId,
                                        squadronId, careerId,
                                        ipar1, ipar2, ipar3, ipar4,
                                        tpar1, tpar2, tpar3, tpar4,
                                        insdate, isDeleted)
                                   VALUES (?, ?, ?, ?, -1, ?, ?,
                                           -1, -1, -1, -1, ?, '', '', '',
                                           ?, 0)""",
                                [
                                    _ev_date, _ev_type, pilot_id,
                                    _pr["rankId"], _cfg_id, _care_id, _pname,
                                    datetime.now().strftime("%Y.%m.%d %H:%M:%S"),
                                ],
                            )

                    # ── Transfer arrival (5 → 0) ─────────────────────────────
                    if _old_st == 5 and _new_st == 0 and self._roster_current_career_id:
                        p_row = con.execute(
                            "SELECT name, lastName, rankId, squadronId"
                            " FROM pilot WHERE id = ?",
                            [pilot_id],
                        ).fetchone()
                        if p_row:
                            sq_row = con.execute(
                                "SELECT configId FROM squadron WHERE id = ?",
                                [p_row["squadronId"]],
                            ).fetchone()
                            if sq_row:
                                cfg_id = int(sq_row["configId"])
                                pilot_name = (
                                    f"{p_row['name']} {p_row['lastName']}".strip()
                                )
                                date_row = con.execute(
                                    "SELECT MAX(date) AS last_date FROM event"
                                    " WHERE careerId = ? AND isDeleted = 0",
                                    [self._roster_current_career_id],
                                ).fetchone()
                                event_date = (
                                    date_row["last_date"]
                                    if date_row and date_row["last_date"]
                                    else datetime.now().strftime("%Y.%m.%d 00:00:00")
                                )
                                con.execute(
                                    """INSERT INTO event
                                           (date, type, pilotId, rankId, missionId,
                                            squadronId, careerId,
                                            ipar1, ipar2, ipar3, ipar4,
                                            tpar1, tpar2, tpar3, tpar4,
                                            insdate, isDeleted)
                                       VALUES (?, 10, ?, ?, -1, ?, ?,
                                               -1, -1, -1, -1, ?, ?, '', '',
                                               ?, 0)""",
                                    [
                                        event_date,
                                        pilot_id,
                                        p_row["rankId"],
                                        cfg_id,
                                        self._roster_current_career_id,
                                        pilot_name,
                                        str(cfg_id),
                                        datetime.now().strftime("%Y.%m.%d %H:%M:%S"),
                                    ],
                                )

            con.commit()
            con.close()

            # Rename pilot names in AI story files (chapters, memory, citations)
            if _name_changes and self._roster_current_career_id:
                _story_files_updated = 0
                for _nf, _nl, _nn_f, _nn_l in _name_changes:
                    _story_files_updated += self._rename_pilot_in_story_files(
                        self._roster_current_career_id, _nf, _nl, _nn_f, _nn_l
                    )
                if _story_files_updated:
                    logger.info(
                        "Roster save: updated pilot name in %d story file(s) for career %d",
                        _story_files_updated,
                        self._roster_current_career_id,
                    )

            # Merge changes into authoritative data and clear pending
            for iid, changes in self._roster_pending_changes.items():
                if iid in self._roster_pilot_data:
                    self._roster_pilot_data[iid].update(changes)
            self._roster_pending_changes.clear()
            self._populate_roster_tree()

            if self._roster_status_var:
                self._roster_status_var.set(
                    self.tr.t("msg_roster_save_success", count=count)
                )

        except Exception as exc:
            logger.warning("_on_roster_save failed: %s", exc, exc_info=True)
            messagebox.showerror(
                self.tr.t("msg_error_title"),
                self.tr.t("msg_roster_save_error", error=str(exc)),
                parent=self,
            )

    def _on_roster_discard(self) -> None:
        """Discard all pending roster changes."""
        if not self._roster_pending_changes:
            if self._roster_status_var:
                self._roster_status_var.set(self.tr.t("msg_roster_no_changes"))
            return
        self._roster_pending_changes.clear()
        self._populate_roster_tree()
        if self._roster_status_var:
            self._roster_status_var.set("")

    def _rename_pilot_in_story_files(
        self,
        root_career_id: int,
        old_first: str,
        old_last: str,
        new_first: str,
        new_last: str,
    ) -> int:
        """
        Replace pilot name strings in every JSON file under the career's story
        directory (chapters, memory, citations, etc.).  Returns the number of
        files actually rewritten.

        Replacement order:
          1. Full name  "Hans Schmidt" → "Max Müller"  (exact, no boundary check needed)
          2. Last name  "Schmidt"      → "Müller"      (word-boundary, handles solo rank usage)
          3. First name "Hans"         → "Max"         (word-boundary, only when first name changed)
        """
        localappdata = os.environ.get("LOCALAPPDATA") or str(Path.home())
        story_dir = (
            Path(localappdata)
            / ".il2_campaign_service_record"
            / "story_data"
            / "careers"
            / str(root_career_id)
        )
        if not story_dir.is_dir():
            return 0

        old_full = f"{old_first} {old_last}".strip()
        new_full = f"{new_first} {new_last}".strip()
        first_changed = old_first != new_first
        last_changed  = old_last  != new_last

        def _fix_text(text: str) -> str:
            if old_full and old_full != new_full:
                text = text.replace(old_full, new_full)
            if last_changed and old_last:
                text = re.sub(r'\b' + re.escape(old_last) + r'\b', new_last, text)
            if first_changed and old_first:
                text = re.sub(r'\b' + re.escape(old_first) + r'\b', new_first, text)
            return text

        def _fix_value(obj: Any) -> Any:
            if isinstance(obj, str):
                return _fix_text(obj)
            if isinstance(obj, dict):
                return {k: _fix_value(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [_fix_value(item) for item in obj]
            return obj

        modified = 0
        for json_path in story_dir.rglob("*.json"):
            try:
                raw  = json_path.read_text(encoding="utf-8")
                data = json.loads(raw)
                new_data = _fix_value(data)
                new_raw  = json.dumps(new_data, ensure_ascii=False, indent=2)
                orig_normalized = json.dumps(data, ensure_ascii=False, indent=2)
                if new_raw != orig_normalized:
                    json_path.write_text(new_raw, encoding="utf-8")
                    modified += 1
            except Exception as exc:
                logger.warning(
                    "Story rename: could not process %s: %s", json_path, exc
                )
        return modified

    # ------------------------------------------------------------------
    # Tab 9: Copy Squadron Pilot
    # ------------------------------------------------------------------

    def _create_copy_pilot_tab(self) -> None:
        """Create 'Copy Squadron Pilot' tab."""
        frame = ttk.Frame(self.notebook, padding=20)
        self.notebook.add(frame, text=self.tr.t("tab_copy_squadron_pilot"))

        careers = self._load_careers_from_db()
        if careers is None:
            ttk.Label(frame, text=self.tr.t("msg_career_db_not_found"), foreground="gray").pack(pady=50)
            return
        if not careers:
            ttk.Label(frame, text=self.tr.t("msg_no_careers"), foreground="gray").pack(pady=50)
            return

        ttk.Label(
            frame,
            text=self.tr.t("lbl_copy_pilot_helper"),
            foreground="gray",
            wraplength=520,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(0, 10))

        sel_row = ttk.Frame(frame)
        sel_row.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(sel_row, text=self.tr.t("lbl_select_career")).pack(side=tk.LEFT)

        self._copy_pilot_career_ids = [cid for cid, _ in careers]
        self._copy_pilot_career_combo = ttk.Combobox(
            sel_row,
            values=[name for _, name in careers],
            state="readonly",
            width=40,
        )
        self._copy_pilot_career_combo.pack(side=tk.LEFT, padx=(10, 0))
        self._copy_pilot_career_combo.current(0)
        self._copy_pilot_career_combo.bind("<<ComboboxSelected>>", self._on_copy_pilot_career_selected)

        # Placeholder shown when the tab is not applicable for the selected career
        self._copy_pilot_no_prev_label = ttk.Label(
            frame,
            text=self.tr.t("lbl_no_prev_squadron"),
            foreground="gray",
            wraplength=520,
            justify=tk.LEFT,
        )

        # Main content frame (shown when previous theatre differs from current)
        self._copy_pilot_pilot_frame = ttk.Frame(frame)

        ctrl_row = ttk.Frame(self._copy_pilot_pilot_frame)
        ctrl_row.pack(anchor=tk.W, pady=(0, 6))
        ttk.Button(ctrl_row, text=self.tr.t("btn_select_all"), command=self._on_copy_pilot_select_all).pack(
            side=tk.LEFT
        )
        ttk.Button(ctrl_row, text=self.tr.t("btn_deselect_all"), command=self._on_copy_pilot_deselect_all).pack(
            side=tk.LEFT, padx=(6, 0)
        )

        cf = ttk.Frame(self._copy_pilot_pilot_frame)
        cf.pack(fill=tk.BOTH, expand=True)

        self._copy_pilot_canvas = tk.Canvas(cf, borderwidth=0, highlightthickness=0)
        vsb = ttk.Scrollbar(cf, orient=tk.VERTICAL, command=self._copy_pilot_canvas.yview)
        self._copy_pilot_canvas.configure(yscrollcommand=vsb.set)
        self._copy_pilot_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        self._copy_pilot_inner_frame = ttk.Frame(self._copy_pilot_canvas)
        self._copy_pilot_canvas.create_window((0, 0), window=self._copy_pilot_inner_frame, anchor="nw")
        self._copy_pilot_inner_frame.bind(
            "<Configure>",
            lambda e: self._copy_pilot_canvas.configure(
                scrollregion=self._copy_pilot_canvas.bbox("all")
            ),
        )
        self._copy_pilot_canvas.bind(
            "<MouseWheel>",
            lambda e: self._copy_pilot_canvas.yview_scroll(-1 * (e.delta // 120), "units"),
        )

        apply_bar = ttk.Frame(self._copy_pilot_pilot_frame)
        apply_bar.pack(fill=tk.X, pady=(8, 0))
        self._copy_pilot_apply_btn = ttk.Button(
            apply_bar,
            text=self.tr.t("btn_copy_pilots"),
            command=self._on_copy_pilot_apply,
            style="Action.TButton",
        )
        self._copy_pilot_apply_btn.pack(side=tk.LEFT)
        ttk.Label(apply_bar, textvariable=self._copy_pilot_status_var, foreground="gray").pack(
            side=tk.LEFT, padx=(12, 0)
        )

        self._load_copy_pilots_for_career(self._copy_pilot_career_ids[0])

    def _on_copy_pilot_career_selected(self, event: tk.Event) -> None:
        """Reload pilot list when user picks a different career."""
        if self._copy_pilot_career_combo is None:
            return
        idx = self._copy_pilot_career_combo.current()
        if 0 <= idx < len(self._copy_pilot_career_ids):
            self._load_copy_pilots_for_career(self._copy_pilot_career_ids[idx])

    def _load_copy_pilots_for_career(self, career_id: int) -> None:
        """
        Find the most appropriate previous squadron for the given root career.

        Priority 1 — n-1 career segment: if the immediately preceding career
        segment has a different squadron.configId from n, use it.  This covers
        both cross-theatre and intra-theatre transfers that IL-2 records as a
        new career row.

        Priority 2 — intra-career transfer: if n-1 is absent or has the same
        configId, check the squadron table for any squadron whose careerId
        equals n's career id but whose configId differs from the current one.
        This handles in-place squadron changes within a single career segment.
        In this case awards are sourced from career n (not n-1).
        """
        if self._copy_pilot_no_prev_label:
            self._copy_pilot_no_prev_label.pack_forget()
        if self._copy_pilot_pilot_frame:
            self._copy_pilot_pilot_frame.pack_forget()

        self._copy_pilot_n_career_id = None
        self._copy_pilot_n_squadron_id = None
        self._copy_pilot_n_config_id = None
        self._copy_pilot_n1_career_id = None
        self._copy_pilot_rows = {}
        self._copy_pilot_check_vars = {}
        if self._copy_pilot_status_var:
            self._copy_pilot_status_var.set("")

        def _show_no_prev() -> None:
            if self._copy_pilot_no_prev_label:
                self._copy_pilot_no_prev_label.pack(anchor=tk.W, pady=(20, 0))

        game_dir = (self.mission_dates_data or {}).get("game_directory")
        if not game_dir:
            _show_no_prev()
            return
        db_path = os.path.join(str(game_dir), "data", "Career", "cp.db")
        if not os.path.isfile(db_path):
            _show_no_prev()
            return

        try:
            uri = f"file:{db_path}?mode=ro"
            con = sqlite3.connect(uri, uri=True, timeout=5)
            con.row_factory = sqlite3.Row

            # Fetch only the two most recent career segments (n and n-1).
            chain_rows = con.execute(
                """
                WITH RECURSIVE chain(id, squadronId) AS (
                    SELECT id, squadronId FROM career WHERE id = ?
                    UNION ALL
                    SELECT c.id, c.squadronId FROM career c JOIN chain ON c.extends = chain.id
                )
                SELECT id, squadronId FROM chain ORDER BY id DESC LIMIT 2
                """,
                [career_id],
            ).fetchall()

            if not chain_rows:
                con.close()
                _show_no_prev()
                return

            n_career_id   = int(chain_rows[0]["id"])
            n_squadron_id = int(chain_rows[0]["squadronId"])

            sq = con.execute(
                "SELECT configId FROM squadron WHERE id = ?", [n_squadron_id]
            ).fetchone()
            if sq is None:
                con.close()
                _show_no_prev()
                return
            n_config_id = int(sq["configId"])

            # ------------------------------------------------------------------
            # Priority 1: n-1 career segment with a different squadron
            # ------------------------------------------------------------------
            source_career_id   = None
            source_squadron_id = None

            if len(chain_rows) >= 2:
                n1_squadron_id = int(chain_rows[1]["squadronId"])
                n1_sq = con.execute(
                    "SELECT configId FROM squadron WHERE id = ?", [n1_squadron_id]
                ).fetchone()
                if n1_sq and int(n1_sq["configId"]) != n_config_id:
                    source_career_id   = int(chain_rows[1]["id"])
                    source_squadron_id = n1_squadron_id

            # ------------------------------------------------------------------
            # Priority 2: intra-career squadron transfer (squadron.careerId)
            # ------------------------------------------------------------------
            if source_career_id is None:
                prev_sq = con.execute(
                    """
                    SELECT id FROM squadron
                    WHERE careerId = ? AND configId != ?
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    [n_career_id, n_config_id],
                ).fetchone()
                if prev_sq:
                    source_career_id   = n_career_id        # awards live in career n
                    source_squadron_id = int(prev_sq["id"])

            if source_career_id is None:
                con.close()
                _show_no_prev()
                return

            pilots = con.execute(
                """
                SELECT id, name, lastName, AILevel, state
                FROM pilot
                WHERE squadronId = ? AND isDeleted = 0 AND AILevel > 0
                ORDER BY lastName, name
                """,
                [source_squadron_id],
            ).fetchall()
            con.close()

            self._copy_pilot_n_career_id   = n_career_id
            self._copy_pilot_n_squadron_id = n_squadron_id
            self._copy_pilot_n_config_id   = n_config_id
            self._copy_pilot_n1_career_id  = source_career_id

            for r in pilots:
                pid = int(r["id"])
                self._copy_pilot_rows[pid] = {
                    "name":     r["name"] or "",
                    "lastName": r["lastName"] or "",
                    "AILevel":  r["AILevel"] if r["AILevel"] is not None else 1,
                    "state":    int(r["state"]) if r["state"] is not None else 0,
                }

            self._populate_copy_pilot_list()

            if self._copy_pilot_pilot_frame:
                self._copy_pilot_pilot_frame.pack(fill=tk.BOTH, expand=True)

        except Exception as exc:
            logger.warning("_load_copy_pilots_for_career failed: %s", exc, exc_info=True)
            _show_no_prev()

    def _populate_copy_pilot_list(self) -> None:
        """Rebuild the scrollable checkbox list of copyable pilots."""
        if self._copy_pilot_inner_frame is None:
            return

        for widget in self._copy_pilot_inner_frame.winfo_children():
            widget.destroy()
        self._copy_pilot_check_vars = {}

        header = ttk.Frame(self._copy_pilot_inner_frame)
        header.pack(fill=tk.X, pady=(0, 2))
        ttk.Label(header, text="", width=3).pack(side=tk.LEFT)
        for text, width in (
            (self.tr.t("lbl_first_name"), 16),
            (self.tr.t("lbl_last_name"), 16),
            (self.tr.t("lbl_state"), 18),
        ):
            ttk.Label(header, text=text, width=width, anchor=tk.W,
                      font=("TkDefaultFont", 9, "bold")).pack(side=tk.LEFT, padx=(4, 0))

        ttk.Separator(self._copy_pilot_inner_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(0, 4))

        for pid, data in self._copy_pilot_rows.items():
            var = tk.BooleanVar(value=False)
            self._copy_pilot_check_vars[pid] = var

            row = ttk.Frame(self._copy_pilot_inner_frame)
            row.pack(fill=tk.X, pady=2)
            ttk.Checkbutton(row, variable=var).pack(side=tk.LEFT)
            state_text = self.PILOT_STATES.get(data["state"], str(data["state"]))
            for text, width in (
                (data["name"],     16),
                (data["lastName"], 16),
                (state_text,       18),
            ):
                ttk.Label(row, text=text, width=width, anchor=tk.W).pack(side=tk.LEFT, padx=(4, 0))

        if self._copy_pilot_canvas:
            self._copy_pilot_inner_frame.update_idletasks()
            self._copy_pilot_canvas.configure(scrollregion=self._copy_pilot_canvas.bbox("all"))

    def _on_copy_pilot_select_all(self) -> None:
        for var in self._copy_pilot_check_vars.values():
            var.set(True)

    def _on_copy_pilot_deselect_all(self) -> None:
        for var in self._copy_pilot_check_vars.values():
            var.set(False)

    def _on_copy_pilot_apply(self) -> None:
        """Copy selected n-1 pilots into the current (n) squadron, including awards."""
        selected_ids = [pid for pid, var in self._copy_pilot_check_vars.items() if var.get()]
        if not selected_ids:
            self._copy_pilot_status_var.set(self.tr.t("msg_copy_pilot_no_selection"))
            return

        if (self._copy_pilot_n_career_id is None
                or self._copy_pilot_n_squadron_id is None
                or self._copy_pilot_n1_career_id is None):
            return

        game_dir = (self.mission_dates_data or {}).get("game_directory")
        if not game_dir:
            messagebox.showerror(self.tr.t("msg_error_title"), "Game directory not set.", parent=self)
            return
        db_path = os.path.join(str(game_dir), "data", "Career", "cp.db")
        if not os.path.isfile(db_path):
            messagebox.showerror(self.tr.t("msg_error_title"), "cp.db not found.", parent=self)
            return

        n_career_id   = self._copy_pilot_n_career_id
        n_squadron_id = self._copy_pilot_n_squadron_id
        n1_career_id  = self._copy_pilot_n1_career_id

        try:
            con = sqlite3.connect(str(db_path), timeout=5)
            con.row_factory = sqlite3.Row

            sq_row = con.execute(
                "SELECT configId FROM squadron WHERE id = ?", [n_squadron_id]
            ).fetchone()
            if sq_row is None:
                con.close()
                raise RuntimeError(f"Squadron row not found for id={n_squadron_id}")
            n_squad_config_id = int(sq_row["configId"])

            columns = [col[1] for col in con.execute("PRAGMA table_info(pilot)").fetchall()]
            insert_cols = [c for c in columns if c != "id"]
            now_str = datetime.now().strftime("%Y.%m.%d %H:%M:%S")
            copied = 0

            with con:
                for source_pilot_id in selected_ids:
                    source_row = con.execute(
                        "SELECT * FROM pilot WHERE id = ? AND isDeleted = 0",
                        [source_pilot_id],
                    ).fetchone()
                    if source_row is None:
                        continue

                    values = [source_row[c] for c in insert_cols]
                    overrides = {
                        "squadronId": n_squadron_id,
                        "insDate":    now_str,
                        "isDeleted":  0,
                    }
                    for key, val in overrides.items():
                        if key in insert_cols:
                            values[insert_cols.index(key)] = val

                    placeholders = ", ".join("?" for _ in insert_cols)
                    col_list = ", ".join(insert_cols)
                    con.execute(
                        f"INSERT INTO pilot ({col_list}) VALUES ({placeholders})",
                        values,
                    )
                    new_pilot_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]

                    con.execute(
                        "DELETE FROM award WHERE careerId = ? AND pilotId = ?",
                        [n_career_id, new_pilot_id],
                    )
                    award_rows = con.execute(
                        """
                        SELECT type, date, pilotName, pilotRank, squadName, isDeleted,
                               PersonageId, x, y, CausedByType, CausedById, Show,
                               GameTime, CAST(PersonageAwardId AS BLOB) AS PersonageAwardId
                        FROM award
                        WHERE careerId = ? AND pilotId = ?
                        ORDER BY date, id
                        """,
                        [n1_career_id, source_pilot_id],
                    ).fetchall()
                    for award in award_rows:
                        con.execute(
                            """
                            INSERT INTO award (
                                careerId, type, date, pilotId, pilotName, pilotRank,
                                squadName, insDate, isDeleted, PersonageId, x, y,
                                CausedByType, CausedById, Show, SquadId, squadConfigId,
                                GameTime, PersonageAwardId
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                n_career_id,
                                award["type"],
                                award["date"],
                                new_pilot_id,
                                award["pilotName"],
                                award["pilotRank"],
                                award["squadName"],
                                now_str,
                                award["isDeleted"],
                                award["PersonageId"],
                                award["x"],
                                award["y"],
                                award["CausedByType"],
                                award["CausedById"],
                                award["Show"],
                                n_squadron_id,
                                n_squad_config_id,
                                award["GameTime"],
                                award["PersonageAwardId"],
                            ),
                        )
                    copied += 1

            con.close()

            self._copy_pilot_status_var.set(self.tr.t("msg_copy_pilot_success", count=copied))
            messagebox.showinfo(
                self.tr.t("msg_confirm_title"),
                self.tr.t("msg_copy_pilot_success", count=copied),
                parent=self,
            )

            for var in self._copy_pilot_check_vars.values():
                var.set(False)

        except Exception as exc:
            logger.warning("_on_copy_pilot_apply failed: %s", exc, exc_info=True)
            messagebox.showerror(
                self.tr.t("msg_error_title"),
                self.tr.t("msg_copy_pilot_error", error=str(exc)),
                parent=self,
            )


# === Dialogs ===

class BracketDialog(tk.Toplevel):
    """Dialog for editing bracket and factor."""
    
    def __init__(self, parent, tr: Translator, bracket: str, factor: float):
        super().__init__(parent)
        self.tr = tr
        self.result = None
        
        self.title(self.tr.t("dlg_edit_bracket_title"))
        self.geometry("300x150")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        
        # Content
        frame = ttk.Frame(self, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text=self.tr.t("dlg_edit_bracket_label")).grid(
            row=0, column=0, sticky=tk.W, pady=5
        )
        self.bracket_var = tk.StringVar(value=bracket)
        self.bracket_entry = ttk.Entry(frame, textvariable=self.bracket_var, width=20)
        self.bracket_entry.grid(row=0, column=1, sticky=tk.W, pady=5, padx=(10, 0))
        
        ttk.Label(frame, text=self.tr.t("dlg_edit_factor_label")).grid(
            row=1, column=0, sticky=tk.W, pady=5
        )
        self.factor_var = tk.StringVar(value=str(factor))
        self.factor_entry = ttk.Entry(frame, textvariable=self.factor_var, width=20)
        self.factor_entry.grid(row=1, column=1, sticky=tk.W, pady=5, padx=(10, 0))
        
        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=2, column=0, columnspan=2, pady=(20, 0))
        
        ttk.Button(btn_frame, text=self.tr.t("btn_ok"), command=self._on_ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=self.tr.t("btn_cancel"), command=self.destroy).pack(side=tk.LEFT, padx=5)
        
        # Center
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
        
        self.bracket_entry.focus_set()
        self.wait_window()
    
    def _on_ok(self) -> None:
        bracket = self.bracket_var.get().strip()
        
        # Validate bracket
        try:
            BracketValidator.parse(bracket)
        except ValueError as e:
            messagebox.showerror(self.tr.t("msg_error_title"), str(e))
            return
        
        # Validate factor
        try:
            factor = float(self.factor_var.get())
            if not BracketValidator.validate_factor(factor):
                raise ValueError()
        except ValueError:
            messagebox.showerror(
                self.tr.t("msg_error_title"),
                self.tr.t("err_factor_range")
            )
            return
        
        self.result = (bracket, factor)
        self.destroy()


class ScoreDialog(tk.Toplevel):
    """Dialog for editing rank score."""
    
    def __init__(self, parent, tr: Translator, rank_name: str, score: int):
        super().__init__(parent)
        self.tr = tr
        self.result = None
        
        self.title(self.tr.t("dlg_edit_score_title"))
        self.geometry("300x120")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        
        frame = ttk.Frame(self, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text=self.tr.t("dlg_edit_score_label", rank=rank_name)).grid(
            row=0, column=0, sticky=tk.W, pady=5
        )
        self.score_var = tk.StringVar(value=str(score))
        self.score_entry = ttk.Entry(frame, textvariable=self.score_var, width=15)
        self.score_entry.grid(row=0, column=1, sticky=tk.W, pady=5, padx=(10, 0))
        
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=1, column=0, columnspan=2, pady=(20, 0))
        
        ttk.Button(btn_frame, text=self.tr.t("btn_ok"), command=self._on_ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=self.tr.t("btn_cancel"), command=self.destroy).pack(side=tk.LEFT, padx=5)
        
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
        
        self.score_entry.focus_set()
        self.wait_window()
    
    def _on_ok(self) -> None:
        try:
            score = int(self.score_var.get())
            if score < 0:
                raise ValueError()
        except ValueError:
            messagebox.showerror(
                self.tr.t("msg_error_title"),
                self.tr.t("err_score_negative")
            )
            return
        
        self.result = score
        self.destroy()


class OffsetDialog(tk.Toplevel):
    """Dialog for editing campaign offset."""
    
    def __init__(self, parent, tr: Translator, campaign_name: str, offset: int):
        super().__init__(parent)
        self.tr = tr
        self.result = None
        
        self.title(self.tr.t("dlg_edit_offset_title"))
        self.geometry("450x150")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        
        frame = ttk.Frame(self, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)
        
        min_off, max_off = OffsetValidator.get_range()
        
        # Campaign name on its own row (above the input)
        ttk.Label(
            frame, 
            text=self.tr.t("dlg_edit_offset_label", campaign=campaign_name),
            wraplength=400
        ).grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=(0, 10))
        
        # Offset input on second row
        self.offset_var = tk.IntVar(value=offset)
        self.offset_spin = ttk.Spinbox(
            frame,
            from_=min_off,
            to=max_off,
            textvariable=self.offset_var,
            width=10
        )
        self.offset_spin.grid(row=1, column=0, sticky=tk.W, pady=5)
        
        ttk.Label(frame, text=f"(Range: {min_off}-{max_off})", foreground='gray').grid(
            row=1, column=1, sticky=tk.W, pady=5, padx=(10, 0)
        )
        
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=2, column=0, columnspan=3, pady=(20, 0))
        
        ttk.Button(btn_frame, text=self.tr.t("btn_ok"), command=self._on_ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=self.tr.t("btn_cancel"), command=self.destroy).pack(side=tk.LEFT, padx=5)
        
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
        
        self.offset_spin.focus_set()
        self.wait_window()
    
    def _on_ok(self) -> None:
        try:
            offset = self.offset_var.get()
            if not OffsetValidator.validate(offset):
                raise ValueError()
        except (ValueError, tk.TclError):
            min_off, max_off = OffsetValidator.get_range()
            messagebox.showerror(
                self.tr.t("msg_error_title"),
                self.tr.t("err_offset_range", min=min_off, max=max_off)
            )
            return
        
        self.result = offset
        self.destroy()
