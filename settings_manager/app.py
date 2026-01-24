"""
IL-2 Settings Manager - Main Application

The main application window with tabbed interface.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from copy import deepcopy
from typing import Any, Dict, Optional

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
)
from settings_manager.config.validators import (
    BracketValidator,
    ScoreValidator,
    OffsetValidator,
)
from settings_manager.i18n import Translator, LANGUAGE_NAMES


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
            width=25
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
            width=25
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
            width=25
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
        
        # Sort by bracket start value
        def sort_key(item):
            bracket = item[0]
            try:
                start, _ = BracketValidator.parse(bracket)
                return start
            except ValueError:
                return 9999
        
        sorted_factors = sorted(factors.items(), key=sort_key)
        
        for bracket, factor in sorted_factors:
            self.scaling_tree.insert('', tk.END, values=(bracket, factor))
    
    def _create_rank_values_tab(self) -> None:
        """Create Rank Values tab."""
        frame = ttk.Frame(self.notebook, padding=20)
        self.notebook.add(frame, text=self.tr.t("tab_rank_values"))
        
        # Info label
        info_text = "Edit score thresholds for ranks. Changes apply to all countries."
        ttk.Label(frame, text=info_text, foreground='gray').grid(
            row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 10)
        )
        
        # Treeview
        columns = ('rank', 'score')
        self.ranks_tree = ttk.Treeview(
            frame,
            columns=columns,
            show='headings',
            height=12
        )
        
        self.ranks_tree.heading('rank', text=self.tr.t("lbl_rank_name"))
        self.ranks_tree.heading('score', text=self.tr.t("lbl_rank_score"))
        self.ranks_tree.column('rank', width=200, anchor=tk.W)
        self.ranks_tree.column('score', width=100, anchor=tk.CENTER)
        
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.ranks_tree.yview)
        self.ranks_tree.configure(yscrollcommand=scrollbar.set)
        
        self.ranks_tree.grid(row=1, column=0, sticky=tk.NSEW, pady=(0, 10))
        scrollbar.grid(row=1, column=1, sticky=tk.NS, pady=(0, 10))
        
        # Populate
        self._populate_ranks_tree()
        
        # Edit button
        ttk.Button(
            frame,
            text=self.tr.t("btn_edit"),
            command=self._on_edit_rank_score
        ).grid(row=2, column=0, sticky=tk.W)
        
        # Double-click to edit
        self.ranks_tree.bind('<Double-1>', lambda e: self._on_edit_rank_score())
        
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)
    
    def _populate_ranks_tree(self) -> None:
        """Populate ranks treeview."""
        for item in self.ranks_tree.get_children():
            self.ranks_tree.delete(item)
        
        # Use Germany as reference (all countries have same scores)
        ranks = self.config_data.get('ranks', {})
        germany_ranks = ranks.get('Germany', [])
        
        for rank in germany_ranks:
            name = rank.get('name', 'Unknown')
            score = rank.get('score', 0)
            self.ranks_tree.insert('', tk.END, values=(name, score))
    
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
        self.campaigns_tree.column('campaign', width=250, anchor=tk.W)
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
        ttk.Button(
            btn_frame,
            text=self.tr.t("btn_restore_defaults"),
            command=self._on_restore_defaults
        ).pack(side=tk.LEFT)
        
        # Right side
        ttk.Button(
            btn_frame,
            text=self.tr.t("btn_cancel"),
            command=self._on_cancel
        ).pack(side=tk.RIGHT, padx=(5, 0))
        
        ttk.Button(
            btn_frame,
            text=self.tr.t("btn_apply"),
            command=self._on_apply
        ).pack(side=tk.RIGHT, padx=(5, 0))
        
        ttk.Button(
            btn_frame,
            text=self.tr.t("btn_ok"),
            command=self._on_ok
        ).pack(side=tk.RIGHT)
    
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
            
            # Get existing brackets
            rank_scaling = self.config_data.setdefault('rank_scaling', {})
            factors = rank_scaling.setdefault('factors', {})
            existing = list(factors.keys())
            
            # Check duplicate
            if bracket in existing:
                messagebox.showerror(
                    self.tr.t("msg_error_title"),
                    self.tr.t("err_bracket_duplicate")
                )
                return
            
            # Check overlap
            overlap = BracketValidator.check_overlap(bracket, existing)
            if overlap:
                if not messagebox.askyesno(
                    self.tr.t("msg_warning_title"),
                    self.tr.t("err_bracket_overlap", bracket=overlap) + "\n\nContinue anyway?"
                ):
                    return
            
            # Add
            factors[bracket] = factor
            self._populate_scaling_tree()
    
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
            
            rank_scaling = self.config_data.get('rank_scaling', {})
            factors = rank_scaling.get('factors', {})
            
            # Remove old, add new
            if old_bracket in factors:
                del factors[old_bracket]
            factors[new_bracket] = new_factor
            
            self._populate_scaling_tree()
    
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
            rank_scaling = self.config_data.get('rank_scaling', {})
            factors = rank_scaling.get('factors', {})
            if bracket in factors:
                del factors[bracket]
            self._populate_scaling_tree()
    
    def _on_edit_rank_score(self) -> None:
        """Edit selected rank score."""
        selection = self.ranks_tree.selection()
        if not selection:
            return
        
        item = selection[0]
        idx = self.ranks_tree.index(item)
        values = self.ranks_tree.item(item, 'values')
        rank_name, old_score = values[0], int(values[1])
        
        dialog = ScoreDialog(self, self.tr, rank_name, old_score)
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
    
    def _validate_all(self) -> list[str]:
        """Validate all data. Returns list of errors."""
        errors = []
        
        # Validate rank scaling factors
        rank_scaling = self.config_data.get('rank_scaling', {})
        factors = rank_scaling.get('factors', {}) if isinstance(rank_scaling, dict) else {}
        
        for bracket, factor in factors.items():
            try:
                BracketValidator.parse(bracket)
            except ValueError as e:
                errors.append(f"Bracket '{bracket}': {e}")
            
            if not BracketValidator.validate_factor(factor):
                errors.append(self.tr.t("err_factor_range") + f" ('{bracket}': {factor})")
        
        # Validate rank scores
        ranks = self.config_data.get('ranks', {})
        if ranks:
            first_country = next(iter(ranks.values()), [])
            scores = [r.get('score', 0) for r in first_country]
            is_valid, invalid_idx = ScoreValidator.validate_ascending(scores)
            if not is_valid:
                errors.append(self.tr.t("err_score_not_ascending", index=invalid_idx))
        
        # Validate campaign offsets
        if self.mission_dates_data:
            min_off, max_off = OffsetValidator.get_range()
            for campaign, data in self.mission_dates_data.items():
                offset = data.get('starting_rank_offset', 0)
                if not OffsetValidator.validate(offset):
                    errors.append(self.tr.t("err_offset_range", min=min_off, max=max_off) + f" ({campaign})")
        
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
    
    def _on_apply(self) -> bool:
        """Apply changes."""
        self._collect_changes()
        
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
            messagebox.showinfo(
                self.tr.t("msg_confirm_title"),
                self.tr.t("msg_save_success")
            )
            return True
        return False
    
    def _on_ok(self) -> None:
        """OK button - apply and close."""
        if self._on_apply():
            self.destroy()
    
    def _on_cancel(self) -> None:
        """Cancel button."""
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
        self.geometry("350x120")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        
        frame = ttk.Frame(self, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)
        
        min_off, max_off = OffsetValidator.get_range()
        
        ttk.Label(frame, text=self.tr.t("dlg_edit_offset_label", campaign=campaign_name)).grid(
            row=0, column=0, sticky=tk.W, pady=5
        )
        
        self.offset_var = tk.IntVar(value=offset)
        self.offset_spin = ttk.Spinbox(
            frame,
            from_=min_off,
            to=max_off,
            textvariable=self.offset_var,
            width=10
        )
        self.offset_spin.grid(row=0, column=1, sticky=tk.W, pady=5, padx=(10, 0))
        
        ttk.Label(frame, text=f"(Range: {min_off}-{max_off})", foreground='gray').grid(
            row=0, column=2, sticky=tk.W, pady=5, padx=(10, 0)
        )
        
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=1, column=0, columnspan=3, pady=(20, 0))
        
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
