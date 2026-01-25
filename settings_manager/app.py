"""
IL-2 Settings Manager - Main Application

The main application window with tabbed interface.
"""

import os
import queue
import subprocess
import threading
import tkinter as tk
import time
from datetime import datetime
from tkinter import ttk, messagebox
from copy import deepcopy
from typing import Any, Dict, Optional, Iterable, Tuple, List

from settings_manager.config.paths import (
    CONFIG_YAML_PATH,
    SETTINGS_JSON_PATH,
    MISSION_DATES_PATH,
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

if HAS_RUAMEL:
    from ruamel.yaml.comments import CommentedMap
else:
    CommentedMap = dict

class SettingsManagerApp(tk.Tk):
    """Main Settings Manager Application."""
    
    def __init__(self):
        super().__init__()
        
        # Initialize translator
        self.tr = Translator()
        
        # Load current locale from settings
        self._load_initial_locale()
        
        # Configure window
        self.title(self.tr.t("app_title"))
        self.geometry("750x550")
        self.minsize(650, 450)
        
        # Data storage
        self.settings_data: Dict[str, Any] = {}
        self.config_data: Dict[str, Any] = {}
        self.mission_dates_data: Optional[Dict[str, Any]] = None
        self.original_data: Dict[str, Any] = {}
        self._refresh_thread: Optional[threading.Thread] = None
        self._close_after_refresh: bool = False
        self._refresh_status_var = tk.StringVar(value="")
        self._refresh_queue: "queue.Queue[Optional[str]]" = queue.Queue()
        self._refresh_poll_id: Optional[str] = None
        self._refresh_running: bool = False
        
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
        
        # Store originals for dirty checking
        self.original_data = {
            'settings': deepcopy(self.settings_data),
            'config': deepcopy(self.config_data),
            'mission_dates': deepcopy(self.mission_dates_data) if self.mission_dates_data else None,
        }
    
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
        
        # Treeview
        columns = ('campaign', 'country', 'offset')
        self.campaigns_tree = ttk.Treeview(
            frame,
            columns=columns,
            show='headings',
            height=12
        )
        
        self.campaigns_tree.heading('campaign', text=self.tr.t("lbl_campaign_name"))
        self.campaigns_tree.heading('country', text=self.tr.t("lbl_country"))
        self.campaigns_tree.heading('offset', text=self.tr.t("lbl_starting_rank_offset"))
        self.campaigns_tree.column('campaign', width=300, anchor=tk.W)
        self.campaigns_tree.column('country', width=100, anchor=tk.CENTER)
        self.campaigns_tree.column('offset', width=150, anchor=tk.CENTER)
        
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.campaigns_tree.yview)
        self.campaigns_tree.configure(yscrollcommand=scrollbar.set)
        
        self.campaigns_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.LEFT, fill=tk.Y)
        
        # Populate
        self._populate_campaigns_tree()
        
        # Double-click to edit
        self.campaigns_tree.bind('<Double-1>', lambda e: self._on_edit_campaign_offset())
    
    def _populate_campaigns_tree(self) -> None:
        """Populate campaigns treeview."""
        if not self.mission_dates_data:
            return
        
        for item in self.campaigns_tree.get_children():
            self.campaigns_tree.delete(item)
        
        for campaign_name, data in sorted(self.mission_dates_data.items()):
            # Skip if data is not a dict (shouldn't happen, but safety check)
            if not isinstance(data, dict):
                continue
            # Skip entries that don't have country (likely not a campaign entry)
            if 'country' not in data:
                continue
            
            country = data.get('country', 'Unknown')
            offset = data.get('starting_rank_offset', 0)
            self.campaigns_tree.insert('', tk.END, values=(campaign_name, country, offset))
    
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
        campaign_name, _, old_offset = values[0], values[1], int(values[2])
        
        dialog = OffsetDialog(self, self.tr, campaign_name, old_offset)
        if dialog.result is not None:
            self.mission_dates_data[campaign_name]['starting_rank_offset'] = dialog.result
            self._populate_campaigns_tree()
    
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
            
            # Update originals
            self.original_data = {
                'settings': deepcopy(self.settings_data),
                'config': deepcopy(self.config_data),
                'mission_dates': deepcopy(self.mission_dates_data) if self.mission_dates_data else None,
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
        
        return False
    
    def _apply_changes(self, close_after: bool = False) -> bool:
        """Apply changes and optionally close the window."""
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
                
                self._start_locale_refresh(regen_locale, close_after=close_after)
                return True

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
        """Poll the refresh queue for completion."""
        if not self._refresh_running:
            return
        try:
            refresh_errors = self._refresh_queue.get_nowait()
        except queue.Empty:
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

        if refresh_errors:
            messagebox.showerror(
                self.tr.t("msg_error_title"),
                self.tr.t("msg_locale_refresh_failed", error=refresh_errors)
            )
        else:
            messagebox.showinfo(
                self.tr.t("msg_confirm_title"),
                f"{self.tr.t('msg_save_success')}\n\n{self.tr.t('msg_locale_refresh')}"
            )

        if self._close_after_refresh:
            self.destroy()

    def _refresh_localized_artifacts(self, locale: Optional[str]) -> Optional[str]:
        """Regenerate localized mission text and PDFs after a locale change.
        
        This method MUST run IL2_CampaignTracker_v2.1_ML.exe as a subprocess because:
        1. PIL/Pillow is bundled only in the Tracker EXE (needed for image conversion)
        2. wkhtmltopdf is bundled only in the Tracker EXE (needed for PDF generation)
        
        If subprocess fails, it falls back to module import (but PDFs won't work).
        """
        if not locale:
            return None
        
        from pathlib import Path
        import sys
        
        # Determine the directory containing the EXEs
        # Both IL2_CampaignTracker_v2.1_ML.exe and IL2_Settings_Manager.exe should be in the same directory
        if getattr(sys, 'frozen', False):
            # Running as compiled EXE - get directory of this EXE
            exe_dir = Path(sys.executable).resolve().parent
            print(f"[Settings Manager] Running as EXE from: {exe_dir}")
        else:
            # Running as Python script - look in parent of settings_manager folder
            exe_dir = Path(__file__).resolve().parent.parent
            print(f"[Settings Manager] Running as script, looking in: {exe_dir}")
        
        tracker_exe = exe_dir / "IL2_CampaignTracker_v2.1_ML.exe"
        print(f"[Settings Manager] Looking for Tracker EXE at: {tracker_exe}")
        print(f"[Settings Manager] Tracker EXE exists: {tracker_exe.exists()}")
        
        # Prepare environment with FORCE_REGENERATE
        env = os.environ.copy()
        env["FORCE_REGENERATE"] = "1"
        
        # REQUIRED: Run the Tracker EXE as subprocess for proper PDF generation
        if tracker_exe.exists():
            try:
                print(f"[Settings Manager] Starting Tracker EXE with locale={locale}...")
                cmd = [
                    str(tracker_exe),
                    "--auto",
                    "--locale",
                    locale,
                    "--skip-monitor",
                    "--non-interactive",
                ]

                log_name = f"settings_manager_refresh_{datetime.now():%Y%m%d_%H%M%S}.log"
                log_path = exe_dir / log_name
                print(f"[Settings Manager] Regeneration log: {log_path}")
                
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
                        cmd,
                        env=env,
                        stdout=log_file,
                        stderr=subprocess.STDOUT,
                        text=True,
                        cwd=str(exe_dir),
                        stdin=subprocess.DEVNULL,
                        startupinfo=startupinfo,
                        creationflags=creationflags,
                    )

                print(f"[Settings Manager] Tracker EXE PID: {process.pid}")
                completion_marker = "COMPLETE!"
                timeout_seconds = 600
                poll_interval = 0.5
                log_interval = 5.0
                start_time = time.monotonic()
                next_log_time = start_time + log_interval
                log_position = 0
                completion_detected = False

                while True:
                    return_code = process.poll()
                    if return_code is not None:
                        print(f"[Settings Manager] Tracker EXE exited with return code: {return_code}")
                        if return_code != 0 and not completion_detected:
                            error_output = self._read_log_excerpt(log_path)
                            print(f"[Settings Manager] Tracker output: {error_output[:1000]}")
                            return (
                                "Tracker EXE error. "
                                f"Exit code: {return_code}. "
                                f"Log excerpt:\n{error_output}"
                            )
                        print("[Settings Manager] Locale refresh completed successfully via Tracker EXE")
                        return None

                    now = time.monotonic()
                    if now >= next_log_time:
                        elapsed = int(now - start_time)
                        print(f"[Settings Manager] Regeneration still running ({elapsed}s)...")
                        next_log_time = now + log_interval

                    if now - start_time > timeout_seconds:
                        print("[Settings Manager] Tracker EXE timed out after 10 minutes")
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
                        print("[Settings Manager] Completion marker detected; stopping tracker process.")
                        self._terminate_process(process)
                        return None

                    time.sleep(poll_interval)

            except Exception as e:
                print(f"[Settings Manager] Subprocess error: {e}")
                # Don't fall through to module import - it won't work properly
                return f"Could not run Tracker EXE: {e}"
        else:
            # Tracker EXE not found - this is a configuration error
            error_msg = (
                f"IL2_CampaignTracker_v2.1_ML.exe not found at {tracker_exe}\n"
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
