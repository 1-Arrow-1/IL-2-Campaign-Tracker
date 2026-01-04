#!/usr/bin/env python3
"""
IL-2 Campaign Tracker - Backup Restore GUI

Shows available backups at startup and allows user to restore a previous state.
After restore, the tracker restarts automatically to process the restored state.
"""

import json
import shutil
import sys
import os
import subprocess
import hashlib
from pathlib import Path
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional, Dict, List


class BackupRestoreGUI:
    """GUI for selecting and restoring campaign backups"""
    
    def __init__(self, il2_states_path: Path, index_path: Path):
        """
        Initialize backup restore GUI
        
        Args:
            il2_states_path: Path to campaignsstates.txt
            index_path: Path to campaignsstates_hash_index.json
        """
        self.il2_states_path = il2_states_path
        self.index_path = index_path
        self. backup_dir = il2_states_path.parent
        self.selected_backup = None
        self. result = None  # 'restored', 'skipped', or 'cancelled'
        
        # Load backup index
        self. backups = self._load_backups()
        
        if not self.backups:
            self.result = 'no_backups'
            return
        
        # Get current hash to mark "currently active" backup
        self.current_hash = self._get_current_hash()
        
        # Create GUI
        self. root = tk. Tk()
        self.root.title("IL-2 Campaign Tracker - Restore Backup")
        self.root.geometry("750x500")
        self.root.resizable(True, True)
        
        # Center window on screen
        self. root.update_idletasks()
        x = (self. root.winfo_screenwidth() // 2) - (750 // 2)
        y = (self.root.winfo_screenheight() // 2) - (500 // 2)
        self.root.geometry(f"750x500+{x}+{y}")
        
        self._build_ui()
    
    def _load_backups(self) -> List[Dict]:
        """Load backup information from index file"""
        if not self.index_path.exists():
            return []
        
        try: 
            with open(self.index_path, 'r', encoding='utf-8') as f:
                index = json.load(f)
            
            backups = []
            for hash_key, entry in index.items():
                # Handle both old and new index formats
                if isinstance(entry, dict):
                    timestamp = entry.get('timestamp', '')
                    backup_file = entry.get('campaignsstates_backup', '')
                    popups_backup = entry.get('popups_backup')
                else:
                    # Old format:  entry is just timestamp string
                    timestamp = entry
                    backup_file = f"campaignsstates_{timestamp}.backup"
                    popups_backup = None
                
                # Check if backup file exists
                backup_path = self. backup_dir / backup_file
                if not backup_path.exists():
                    continue
                
                # Format display date
                try:
                    dt = datetime.strptime(timestamp, "%Y%m%d_%H%M%S")
                    display_date = dt. strftime("%Y-%m-%d %H:%M:%S")
                    sort_key = dt
                except: 
                    display_date = timestamp
                    sort_key = datetime.min
                
                # Get file size
                try:
                    file_size = backup_path.stat().st_size
                    size_str = self._format_size(file_size)
                except:
                    size_str = "Unknown"
                
                backups. append({
                    'hash': hash_key,
                    'timestamp': timestamp,
                    'display_date': display_date,
                    'sort_key': sort_key,
                    'backup_file':  backup_file,
                    'backup_path': backup_path,
                    'popups_backup': popups_backup,
                    'has_popups': popups_backup is not None,
                    'size': size_str
                })
            
            # Sort by timestamp (newest first)
            backups.sort(key=lambda x: x['sort_key'], reverse=True)
            return backups
            
        except Exception as e:
            print(f"⚠️ Could not load backup index: {e}")
            return []
    
    def _format_size(self, size_bytes: int) -> str:
        """Format file size in human-readable format"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
    
    def _get_current_hash(self) -> Optional[str]:
        """Calculate hash of current campaignsstates.txt"""
        if not self.il2_states_path. exists():
            return None
        
        try:
            with open(self.il2_states_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except: 
            return None
    
    def _build_ui(self):
        """Build the GUI interface"""
        
        # Header
        header_frame = tk.Frame(self.root, bg='#2c3e50', pady=15)
        header_frame.pack(fill='x')
        
        title_label = tk. Label(
            header_frame,
            text="🔄 Restore Campaign Backup",
            font=('Arial', 16, 'bold'),
            bg='#2c3e50',
            fg='white'
        )
        title_label.pack()
        
        subtitle_label = tk. Label(
            header_frame,
            text="Select a backup to restore your campaign progress to a previous state",
            font=('Arial', 10),
            bg='#2c3e50',
            fg='#ecf0f1'
        )
        subtitle_label.pack()
        
        # Info box
        info_frame = tk.Frame(self.root, bg='#ffeaa7', padx=10, pady=8)
        info_frame.pack(fill='x', padx=10, pady=(10, 5))
        
        info_label = tk.Label(
            info_frame,
            text="⚠️ Restoring a backup will replace your current campaign progress.  "
                 "The tracker will restart automatically after restore.  "
                 "Your popup states will also be restored if available.",
            font=('Arial', 9),
            bg='#ffeaa7',
            fg='#2d3436',
            wraplength=700,
            justify='left'
        )
        info_label. pack(anchor='w')
        
        # Backup list frame
        list_frame = tk. Frame(self.root)
        list_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Treeview for backup list
        columns = ('date', 'size', 'status', 'popups')
        self.tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=12)
        
        self.tree.heading('date', text='Backup Date & Time')
        self.tree.heading('size', text='Size')
        self.tree.heading('status', text='Status')
        self.tree.heading('popups', text='Popup State')
        
        self.tree.column('date', width=200, anchor='w')
        self.tree.column('size', width=80, anchor='center')
        self.tree.column('status', width=180, anchor='center')
        self.tree.column('popups', width=120, anchor='center')
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.tree. yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Populate list
        for i, backup in enumerate(self.backups):
            # Determine status
            if backup['hash'] == self.current_hash:
                status = "✅ Currently Active"
                tags = ('active',)
            else:
                status = ""
                tags = ('normal',) if i % 2 == 0 else ('alternate',)
            
            # Popup backup indicator
            popups = "✓ Included" if backup['has_popups'] else "✗ Not available"
            
            self.tree.insert('', 'end',
                           iid=backup['hash'],
                           values=(backup['display_date'], backup['size'], status, popups),
                           tags=tags)
        
        # Configure tag colors
        self. tree.tag_configure('active', background='#d5f5e3')
        self.tree.tag_configure('alternate', background='#f8f9fa')
        
        # Bind selection
        self.tree. bind('<<TreeviewSelect>>', self._on_select)
        self.tree.bind('<Double-1>', self._on_double_click)
        
        # Buttons frame
        button_frame = tk.Frame(self.root, pady=10)
        button_frame.pack(fill='x', padx=10)
        
        # Left side buttons
        left_buttons = tk.Frame(button_frame)
        left_buttons.pack(side='left')
        
        self. restore_btn = ttk.Button(
            left_buttons,
            text="🔄 Restore Selected Backup",
            command=self._on_restore,
            state='disabled',
            width=28
        )
        self.restore_btn.pack(side='left', padx=(0, 10))
        
        skip_btn = ttk.Button(
            left_buttons,
            text="▶ Continue Without Restore",
            command=self._on_skip,
            width=25
        )
        skip_btn.pack(side='left')
        
        # Right side button
        cancel_btn = ttk.Button(
            button_frame,
            text="✕ Exit",
            command=self._on_cancel,
            width=12
        )
        cancel_btn.pack(side='right')
        
        # Footer
        footer_frame = tk.Frame(self.root, bg='#ecf0f1', pady=8)
        footer_frame.pack(fill='x')
        
        backup_count = len(self.backups)
        footer_label = tk. Label(
            footer_frame,
            text=f"📁 {backup_count} backup(s) found in:  {self.backup_dir}",
            font=('Arial', 8),
            bg='#ecf0f1',
            fg='#7f8c8d'
        )
        footer_label. pack()
    
    def _on_select(self, event):
        """Handle backup selection"""
        selection = self. tree.selection()
        if selection: 
            self.selected_backup = selection[0]  # Hash of selected backup
            
            # Check if selected is currently active
            if self.selected_backup == self.current_hash:
                self. restore_btn.configure(state='disabled')
            else:
                self.restore_btn. configure(state='normal')
        else:
            self.selected_backup = None
            self. restore_btn.configure(state='disabled')
    
    def _on_double_click(self, event):
        """Handle double-click on backup (restore immediately)"""
        selection = self.tree. selection()
        if selection and selection[0] != self.current_hash:
            self._on_restore()
    
    def _on_restore(self):
        """Handle restore button click"""
        if not self.selected_backup: 
            return
        
        # Find backup info
        backup_info = None
        for b in self.backups:
            if b['hash'] == self.selected_backup: 
                backup_info = b
                break
        
        if not backup_info: 
            messagebox.showerror("Error", "Could not find backup information.")
            return
        
        # Build confirmation message
        msg = (
            f"Are you sure you want to restore this backup?\n\n"
            f"📅 Date: {backup_info['display_date']}\n"
            f"📦 Size: {backup_info['size']}\n"
            f"💾 Popup State: {'Will be restored' if backup_info['has_popups'] else 'Not available'}\n\n"
            f"Your current campaign progress will be replaced.\n"
            f"The tracker will restart automatically."
        )
        
        confirm = messagebox.askyesno("Confirm Restore", msg)
        
        if not confirm: 
            return
        
        # Close the GUI first to show console output
        self. root.destroy()
        
        # Perform restore with detailed logging
        try:
            backup_path = backup_info['backup_path']
            restore_path = self. il2_states_path
            
            print()
            print("=" * 70)
            print("🔄 RESTORING BACKUP")
            print("=" * 70)
            print(f"  Backup file: {backup_info['backup_file']}")
            print(f"  Backup path: {backup_path}")
            print(f"  Target path: {restore_path}")
            print()
            
            # ================================================================
            # Step 1: Verify backup exists
            # ================================================================
            if not backup_path. exists():
                print(f"❌ ERROR: Backup file not found!")
                print(f"   Path: {backup_path}")
                input("Press Enter to exit...")
                self.result = 'cancelled'
                return
            
            print(f"  ✓ Step 1: Backup file exists ({backup_info['size']})")
            
            # ================================================================
            # Step 2: Create a COPY of the backup file (preserve original)
            # ================================================================
            backup_copy_path = backup_path.parent / "campaignsstates_restore_temp.txt"
            
            try:
                shutil.copy2(backup_path, backup_copy_path)
                print(f"  ✓ Step 2: Created backup copy:  {backup_copy_path. name}")
            except Exception as e: 
                print(f"❌ ERROR:  Could not create backup copy:  {e}")
                input("Press Enter to exit...")
                self.result = 'cancelled'
                return
            
            # ================================================================
            # Step 3: Delete current campaignsstates.txt
            # ================================================================
            if restore_path.exists():
                try:
                    restore_path.unlink()
                    print(f"  ✓ Step 3: Deleted current campaignsstates.txt")
                except PermissionError: 
                    print(f"❌ ERROR:  Cannot delete campaignsstates.txt - file is locked!")
                    print(f"   Make sure IL-2 is not running.")
                    # Clean up temp file
                    if backup_copy_path.exists():
                        backup_copy_path.unlink()
                    input("Press Enter to exit...")
                    self.result = 'cancelled'
                    return
                except Exception as e: 
                    print(f"❌ ERROR:  Could not delete current file: {e}")
                    # Clean up temp file
                    if backup_copy_path.exists():
                        backup_copy_path.unlink()
                    input("Press Enter to exit...")
                    self. result = 'cancelled'
                    return
            else:
                print(f"  ℹ️ Step 3: No current campaignsstates.txt to remove")
            
            # ================================================================
            # Step 4: Rename the backup copy to campaignsstates.txt
            # ================================================================
            try:
                backup_copy_path.rename(restore_path)
                print(f"  ✓ Step 4: Renamed backup copy to campaignsstates. txt")
            except Exception as e: 
                print(f"❌ ERROR:  Could not rename backup copy: {e}")
                # Try to clean up
                if backup_copy_path.exists():
                    backup_copy_path.unlink()
                input("Press Enter to exit...")
                self.result = 'cancelled'
                return
            
            # ================================================================
            # Step 5: Verify the restore
            # ================================================================
            if restore_path.exists():
                new_size = restore_path.stat().st_size
                print(f"  ✓ Step 5: Verified - new file exists ({new_size} bytes)")
            else: 
                print(f"❌ ERROR: campaignsstates.txt was not created!")
                input("Press Enter to exit...")
                self.result = 'cancelled'
                return
            
            # ================================================================
            # Step 6: Verify original backup is still intact
            # ================================================================
            if backup_path.exists():
                print(f"  ✓ Step 6: Original backup preserved:  {backup_info['backup_file']}")
            else:
                print(f"  ⚠️ Warning: Original backup no longer exists")
            
            print()
            print("=" * 70)
            print("✅ BACKUP RESTORED SUCCESSFULLY!")
            print("=" * 70)
            print()
            print(f"  Restored from: {backup_info['display_date']}")
            print(f"  Original backup is still available for future restores.")
            print()
            print("  The tracker will now re-process the restored state...")
            print()
            
            # ✅ NO RESTART NEEDED! Just set result and let launcher continue
            self.result = 'restored'
            
            # Wait so user can read the message
            import time
            time.sleep(2)
            
        except Exception as e:
            print()
            print(f"❌ ERROR during restore: {e}")
            import traceback
            traceback.print_exc()
            print()
            input("Press Enter to exit...")
            self.result = 'cancelled'
    
    def _on_skip(self):
        """Handle skip button click"""
        self.result = 'skipped'
        self. root.destroy()
    
    def _on_cancel(self):
        """Handle cancel button click"""
        self.result = 'cancelled'
        self.root. destroy()
    
    def run(self) -> str:
        """
        Run the GUI and return result
        
        Returns: 
            'restored' - Backup was restored, tracker should restart
            'skipped' - User chose to skip, continue normally
            'cancelled' - User cancelled, exit tracker
            'no_backups' - No backups available
        """
        if self.result == 'no_backups': 
            return 'no_backups'
        
        self.root.mainloop()
        return self.result or 'cancelled'


def check_and_show_backup_gui(il2_states_path:  Path) -> str:
    """
    Check for backups and show restore GUI if available AND useful. 
    
    The GUI is shown when:
    - Multiple backups exist, OR
    - Only one backup exists AND it's not currently active
    
    The GUI is NOT shown when:
    - No backups exist
    - Only one backup exists AND it's already the current state
    
    Args:  
        il2_states_path:  Path to campaignsstates.txt
        
    Returns:  
        'restored', 'skipped', 'cancelled', or 'no_backups'
    """
    if not il2_states_path or not il2_states_path.exists():
        return 'no_backups'
    
    index_path = il2_states_path.parent / "campaignsstates_hash_index.json"
    
    if not index_path. exists():
        return 'no_backups'
    
    # Load backup index
    try:
        with open(index_path, 'r', encoding='utf-8') as f:
            index = json.load(f)
        
        if not index or len(index) == 0:
            return 'no_backups'
        
    except Exception as e:
        print(f"⚠️ Could not check backups: {e}")
        return 'no_backups'
    
    # Get current hash
    current_hash = None
    try: 
        with open(il2_states_path, 'rb') as f:
            current_hash = hashlib.md5(f.read()).hexdigest()
    except Exception: 
        pass
    
    # Count valid backups (backup file must exist)
    backup_dir = il2_states_path.parent
    valid_backups = []
    
    for hash_key, entry in index.items():
        if isinstance(entry, dict):
            backup_file = entry.get('campaignsstates_backup', '')
        else:
            backup_file = f"campaignsstates_{entry}. backup"
        
        if (backup_dir / backup_file).exists():
            valid_backups.append({
                'hash':  hash_key,
                'file': backup_file
            })
    
    if not valid_backups:
        return 'no_backups'
    
    # ================================================================
    # Decision logic:  Should we show the GUI? 
    # ================================================================
    num_backups = len(valid_backups)
    
    if num_backups == 0:
        # No valid backups
        print("ℹ️ No valid backups found")
        return 'no_backups'
    
    elif num_backups == 1:
        # Only one backup - check if it's already active
        only_backup = valid_backups[0]
        
        if only_backup['hash'] == current_hash: 
            # The only backup IS the current state - no point showing GUI
            print(f"ℹ️ Only one backup exists and it's already active - skipping GUI")
            return 'skipped'
        else: 
            # One backup exists but it's different - show GUI
            print(f"ℹ️ One backup available (not current state) - showing GUI")
    
    else: 
        # Multiple backups - always show GUI
        print(f"ℹ️ {num_backups} backups available - showing GUI")
    
    # Show GUI
    gui = BackupRestoreGUI(il2_states_path, index_path)
    return gui.run()


def restart_tracker():
    """
    NO-OP: Restart disabled due to PyInstaller + Python 3.13 DLL issues.
    
    Instead, the launcher will continue running and re-process the restored state.
    This is actually BETTER because:
    1. No process restart needed
    2. Faster
    3. No DLL extraction issues
    4. User sees continuous flow
    """
    print()
    print("=" * 70)
    print("ℹ️  CONTINUING WITHOUT RESTART")
    print("=" * 70)
    print()
    print("  The tracker will re-decode and re-process the restored backup.")
    print("  This is faster and more reliable than restarting!")
    print()
    # Just return - let the launcher continue
    return


# =============================================================================
# Test Mode
# =============================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("Backup Restore GUI - Test Mode")
    print("=" * 60)
    
    # Try to find IL-2 states path for testing
    # Check common locations
    test_paths = [
        Path("campaignsstates.txt"),
        Path.home() / "Documents" / "campaignsstates.txt",
    ]
    
    # Also try to load from campaign_mission_dates.json
    config_path = Path("campaign_mission_dates.json")
    if config_path. exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                game_dir = Path(data. get('game_directory', '')).expanduser().resolve()
                usersave_dir = game_dir / 'data' / 'swf' / 'il2' / 'usersave'
                
                if usersave_dir.exists():
                    for user_dir in usersave_dir.iterdir():
                        potential = user_dir / 'campaign' / 'campaignsstates.txt'
                        if potential.exists():
                            test_paths. insert(0, potential)
                            break
        except Exception as e: 
            print(f"Could not load config: {e}")
    
    # Find first existing path
    test_path = None
    for p in test_paths: 
        if p. exists():
            test_path = p
            break
    
    if test_path:
        print(f"Found:  {test_path}")
        print()
        result = check_and_show_backup_gui(test_path)
        print(f"\nResult: {result}")
        
        if result == 'restored':
            print("Would restart tracker here...")
    else:
        print("No campaignsstates.txt found for testing")
        print("Checked:")
        for p in test_paths: 
            print(f"  - {p}")