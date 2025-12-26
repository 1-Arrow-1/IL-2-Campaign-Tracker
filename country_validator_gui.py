#!/usr/bin/env python3
"""
Country Validator GUI

Shows popup for user to validate/correct automatically detected countries.
Displays after initial campaign scan or when new campaigns are detected.

Usage:
    from country_validator_gui import validate_countries
    validate_countries('campaign_mission_dates.json')
"""

import tkinter as tk
from tkinter import ttk
import json
from pathlib import Path
from typing import Dict, List


COUNTRIES = ['Germany', 'Soviet Union', 'USA', 'Britain']

# Detection method descriptions for user context
METHOD_DESCRIPTIONS = {
    'Campaign/Mission names': 'Campaign or mission filenames contain country-specific keywords',
    'Aircraft type': 'Aircraft type detected from campaign files',
    'Campaign description': 'Campaign description contains country keywords',
    'Mission briefing keywords': 'Mission briefing text contains country indicators',
    'Unknown': 'Could not automatically detect - please select'
}


class CountryValidatorGUI:
    def __init__(self, campaigns: Dict[str, Dict]):
        """
        Initialize country validator GUI
        
        Args:
            campaigns: Dict of campaign_name -> campaign_data
        """
        self.campaigns = campaigns
        self.result = None
        self.dropdowns = {}  # Store dropdown references
        
        # Create main window
        self.root = tk.Tk()
        self.root.title("IL-2 Campaign Tracker - Verify Countries")
        self.root.geometry("700x500")
        self.root.resizable(True, True)
        
        # Build UI
        self._build_ui()
        
    def _build_ui(self):
        """Build the GUI interface"""
        
        # Header
        header_frame = tk.Frame(self.root, bg='#2c3e50', pady=15)
        header_frame.pack(fill='x')
        
        title_label = tk.Label(
            header_frame,
            text="Campaign Country Detection - Please Verify",
            font=('Arial', 14, 'bold'),
            bg='#2c3e50',
            fg='white'
        )
        title_label.pack()
        
        subtitle_label = tk.Label(
            header_frame,
            text="Review and correct the automatically detected countries for your campaigns",
            font=('Arial', 9),
            bg='#2c3e50',
            fg='#ecf0f1'
        )
        subtitle_label.pack()
        
        # Scrollable campaign list
        canvas_frame = tk.Frame(self.root)
        canvas_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Create canvas with scrollbar
        canvas = tk.Canvas(canvas_frame, bg='white')
        scrollbar = ttk.Scrollbar(canvas_frame, orient='vertical', command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='white')
        
        scrollable_frame.bind(
            '<Configure>',
            lambda e: canvas.configure(scrollregion=canvas.bbox('all'))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Add campaigns
        for idx, (campaign_name, campaign_data) in enumerate(self.campaigns.items()):
            self._add_campaign_row(scrollable_frame, campaign_name, campaign_data, idx)
        
        # Footer with buttons
        footer_frame = tk.Frame(self.root, bg='#ecf0f1', pady=10)
        footer_frame.pack(fill='x')
        
        button_frame = tk.Frame(footer_frame, bg='#ecf0f1')
        button_frame.pack()
        
        cancel_btn = tk.Button(
            button_frame,
            text="Cancel",
            command=self._on_cancel,
            width=15,
            bg='#95a5a6',
            fg='white',
            font=('Arial', 10),
            relief='flat',
            cursor='hand2'
        )
        cancel_btn.pack(side='left', padx=5)
        
        save_btn = tk.Button(
            button_frame,
            text="Save & Continue",
            command=self._on_save,
            width=15,
            bg='#27ae60',
            fg='white',
            font=('Arial', 10, 'bold'),
            relief='flat',
            cursor='hand2'
        )
        save_btn.pack(side='left', padx=5)
        
        # Bind mouse wheel for scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
    def _add_campaign_row(self, parent, campaign_name: str, campaign_data: Dict, index: int):
        """Add a single campaign row to the GUI"""
        
        # Campaign frame with alternating background
        bg_color = '#f8f9fa' if index % 2 == 0 else 'white'
        campaign_frame = tk.Frame(parent, bg=bg_color, pady=10, padx=10)
        campaign_frame.pack(fill='x', pady=2)
        
        # Campaign name (bold)
        name_label = tk.Label(
            campaign_frame,
            text=campaign_name,
            font=('Arial', 11, 'bold'),
            bg=bg_color,
            anchor='w'
        )
        name_label.grid(row=0, column=0, columnspan=2, sticky='w', pady=(0, 3))
        
        # Mission count
        mission_count = campaign_data.get('mission_count', 0)
        missions_label = tk.Label(
            campaign_frame,
            text=f"Missions: {mission_count}",
            font=('Arial', 9),
            fg='#7f8c8d',
            bg=bg_color,
            anchor='w'
        )
        missions_label.grid(row=1, column=0, sticky='w')
        
        # Country dropdown
        country_frame = tk.Frame(campaign_frame, bg=bg_color)
        country_frame.grid(row=1, column=1, sticky='e', padx=(10, 0))
        
        country_label = tk.Label(
            country_frame,
            text="Country:",
            font=('Arial', 9),
            bg=bg_color
        )
        country_label.pack(side='left', padx=(0, 5))
        
        current_country = campaign_data.get('country', 'Unknown')
        country_var = tk.StringVar(value=current_country)
        
        country_dropdown = ttk.Combobox(
            country_frame,
            textvariable=country_var,
            values=COUNTRIES,
            state='readonly',
            width=15,
            font=('Arial', 9)
        )
        country_dropdown.pack(side='left')
        
        # Store reference for later retrieval
        self.dropdowns[campaign_name] = country_var
        
        # Detection method info (if available)
        # Note: We don't have this info in campaign_mission_dates.json yet
        # Could be added in future if we store detection metadata
        
        # Separator line
        separator = tk.Frame(campaign_frame, height=1, bg='#dee2e6')
        separator.grid(row=2, column=0, columnspan=2, sticky='ew', pady=(10, 0))
        
    def _on_cancel(self):
        """Cancel button clicked - exit without saving"""
        self.result = None
        self.root.quit()
        self.root.destroy()
        
    def _on_save(self):
        """Save button clicked - collect all selections and save"""
        self.result = {}
        
        for campaign_name, country_var in self.dropdowns.items():
            selected_country = country_var.get()
            self.result[campaign_name] = selected_country
        
        self.root.quit()
        self.root.destroy()
        
    def show(self) -> Dict[str, str]:
        """
        Show the GUI and wait for user input
        
        Returns:
            Dict mapping campaign_name -> selected_country
            or None if cancelled
        """
        # Center window on screen
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')
        
        # Show window and wait
        self.root.mainloop()
        
        return self.result


def validate_countries(json_file_path: str) -> bool:
    """
    Load campaign data, show validation GUI, and save corrections
    
    Args:
        json_file_path: Path to campaign_mission_dates.json
        
    Returns:
        True if user saved changes, False if cancelled
    """
    json_path = Path(json_file_path)
    
    if not json_path.exists():
        print(f"Error: {json_file_path} not found!")
        return False
    
    # Load campaign data
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Extract campaigns - exclude game_directory AND stock campaigns (via is_stock flag)
    campaigns = {}
    stock_count = 0
    for k, v in data.items():
        if k == 'game_directory':
            continue
        # Skip stock campaigns (detected via is_stock flag in JSON)
        if isinstance(v, dict) and v.get('is_stock', False):
            print(f"  Skipping stock campaign: {k}")
            stock_count += 1
            continue
        campaigns[k] = v
    
    if stock_count > 0:
        print(f"  {stock_count} stock campaign(s) auto-detected")
    
    if not campaigns:
        print("No user campaigns to validate! (All campaigns are stock)")
        return False
    
    # Show GUI
    gui = CountryValidatorGUI(campaigns)
    result = gui.show()
    
    if result is None:
        print("Country validation cancelled by user")
        return False
    
    # Apply corrections
    changes_made = False
    for campaign_name, new_country in result.items():
        old_country = data[campaign_name].get('country')
        if old_country != new_country:
            data[campaign_name]['country'] = new_country
            changes_made = True
            print(f"  Updated {campaign_name}: {old_country} → {new_country}")
    
    # Save updated data
    if changes_made:
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"✓ Saved corrections to {json_file_path}")
    else:
        print("No changes made")
    
    return True


def validate_new_campaigns(json_file_path: str, new_campaign_names: List[str]) -> bool:
    """
    Show validation GUI for only newly detected campaigns
    
    Args:
        json_file_path: Path to campaign_mission_dates.json
        new_campaign_names: List of newly detected campaign names
        
    Returns:
        True if user saved changes, False if cancelled
    """
    json_path = Path(json_file_path)
    
    if not json_path.exists():
        print(f"Error: {json_file_path} not found!")
        return False
    
    # Load campaign data
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Extract only new campaigns (exclude stock campaigns via is_stock flag)
    new_campaigns = {}
    stock_count = 0
    for k, v in data.items():
        if k in new_campaign_names and k != 'game_directory':
            # Skip stock campaigns
            if isinstance(v, dict) and v.get('is_stock', False):
                print(f"  Skipping stock campaign: {k}")
                stock_count += 1
                continue
            new_campaigns[k] = v
    
    if stock_count > 0:
        print(f"  {stock_count} new stock campaign(s) auto-detected")
    
    if not new_campaigns:
        print("No new user campaigns to validate!")
        return True  # Not an error, just nothing to do
    
    # Show GUI
    gui = CountryValidatorGUI(new_campaigns)
    result = gui.show()
    
    if result is None:
        print("Country validation cancelled by user")
        return False
    
    # Apply corrections
    changes_made = False
    for campaign_name, new_country in result.items():
        old_country = data[campaign_name].get('country')
        if old_country != new_country:
            data[campaign_name]['country'] = new_country
            changes_made = True
            print(f"  Updated {campaign_name}: {old_country} → {new_country}")
    
    # Save updated data
    if changes_made:
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"✓ Saved corrections to {json_file_path}")
    
    return True


# Test function
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python country_validator_gui.py <campaign_mission_dates.json>")
        sys.exit(1)
    
    validate_countries(sys.argv[1])
