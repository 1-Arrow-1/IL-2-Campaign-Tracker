"""
IL-2 Settings Manager - Main Application

The main application window with tabbed interface.
"""

import os
import json
import queue
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
    
    def __init__(self):
        super().__init__()
        
        # Initialize translator
        self.tr = Translator()
        
        # Load current locale from settings
        self._load_initial_locale()
        
        # Configure window
        self.title(self.tr.t("app_title"))
        self.geometry("780x760")
        self.minsize(700, 620)
        
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

        # Load all data
        self._load_all_data()
        
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

        # Test connection controls
        row += 1
        self.story_test_button = ttk.Button(
            frame,
            text=self.tr.t("btn_test_connection"),
            command=self._on_test_story_connection,
        )
        self.story_test_button.grid(row=row, column=1, sticky=tk.W, pady=(10, 0), padx=(10, 0))
        self.story_refresh_models_button = ttk.Button(
            frame,
            text=self.tr.t("btn_refresh_models"),
            command=self._on_refresh_story_models,
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
            command=self._on_add_bracket
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(
            btn_frame,
            text=self.tr.t("btn_edit"),
            command=self._on_edit_bracket
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(
            btn_frame,
            text=self.tr.t("btn_remove_bracket"),
            command=self._on_remove_bracket
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
            command=self._on_edit_rank_score
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
        )
        self._stock_import_btn.pack(side=tk.LEFT)

        ttk.Label(
            action_row,
            textvariable=self._stock_import_status_var,
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
        
        self.apply_button = ttk.Button(
            btn_frame,
            text=self.tr.t("btn_apply"),
            command=self._on_apply
        )
        self.apply_button.pack(side=tk.RIGHT, padx=(5, 0))
        
        self.ok_button = ttk.Button(
            btn_frame,
            text=self.tr.t("btn_ok"),
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
        self.apply_button.configure(state=state)
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
