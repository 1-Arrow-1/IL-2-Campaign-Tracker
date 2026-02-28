#!/usr/bin/env python3
"""
IL-2 Campaign Tracker - Control GUI

A central launcher/control center for the IL-2 Campaign Tracker ecosystem.
This GUI provides a simple interface to start/stop the tracker and access
related tools.

Features:
- Start/Stop the Campaign Tracker
- Open Campaign Service Record
- Open Settings Manager
- Uninstall Tracker

Usage:
    python tools/il2_tracker_control_gui.py       # Development
    IL2_Tracker_Control_GUI.exe                   # Installed

All EXE paths are resolved relative to this script/executable location.
"""

import ctypes
import os
import re
import sys
import subprocess
import tkinter as tk
from tkinter import messagebox
from pathlib import Path
from typing import Dict, List, Optional
import random

# Detect frozen state and set paths
if getattr(sys, 'frozen', False):
    # Running as compiled EXE
    # INSTALL_DIR: Where the EXE and other executables are located
    INSTALL_DIR = Path(sys.executable).parent
    # ASSETS_DIR: Where bundled assets (icons) are extracted by PyInstaller
    ASSETS_DIR = Path(sys._MEIPASS)
    FROZEN = True
else:
    # Running as script
    # INSTALL_DIR: Parent of tools/ directory (repo root)
    INSTALL_DIR = Path(__file__).parent.parent
    # ASSETS_DIR: Same as INSTALL_DIR in dev mode
    ASSETS_DIR = INSTALL_DIR
    FROZEN = False
    # Add parent to path for imports
    sys.path.insert(0, str(INSTALL_DIR))

# Try to import psutil for process management (optional but preferred)
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

# Initialize i18n system
try:
    from utils.i18n import t, init_i18n
    from utils.locale_config import resolve_locale
    # Initialize with user's locale
    user_locale = resolve_locale()
    init_i18n(user_locale)
    HAS_I18N = True
except ImportError:
    HAS_I18N = False
    # Fallback translation function that returns the key
    def t(key: str, **kwargs) -> str:
        # Return the last part of the key as a readable fallback
        fallback = key.split('.')[-1].replace('_', ' ').title()
        return fallback


# EXE names (relative to INSTALL_DIR)
TRACKER_EXE = "IL2_CampaignTracker_v2.2_ML.exe"
SERVICE_RECORD_EXE = "Campaign_Service_Record.exe"
CAREER_SERVICE_RECORD_EXE = "Career_Service_Record.exe"
SETTINGS_MANAGER_EXE = "IL2_Settings_Manager.exe"
UNINSTALLER_EXE = "unins000.exe"

# Icon asset paths (relative to ASSETS_DIR - all PNG for Tkinter compatibility)
# These are in tools/icons/ directory
TRACKER_ICON_PNG = "tools/icons/tracker.png"
SERVICE_RECORD_ICON_PNG = "tools/icons/service_record.png"
CAREER_ICON_PNG = "tools/icons/career.png"
SETTINGS_ICON_PNG = "tools/icons/settings.png"
STOP_ICON_PNG = "tools/icons/stop.png"
UNINSTALL_ICON_PNG = "tools/icons/uninstall.png"
PDF_ICON_PNG = "tools/icons/pdf.png"

# Window icon (ICO format for window decoration)
WINDOW_ICON = "oak_leaves.ico"

# Window configuration
WINDOW_TITLE = "IL-2 Campaign Tracker Control"
BUTTON_WIDTH = 200
BUTTON_HEIGHT = 110
ICON_SIZE = 64
FONT_FAMILY = "Segoe UI"
FONT_SIZE = 10

# Colors
BG_COLOR = "#241b14"
BTN_BG_COLOR = "#2f251b"
BTN_ACTIVE_COLOR = "#3a2d21"
BTN_DISABLED_COLOR = "#3f352b"
TEXT_COLOR = "#ccb899"
STATUS_RUNNING_COLOR = TEXT_COLOR
STATUS_STOPPED_COLOR = TEXT_COLOR


def run_elevated(exe_path: str, args: str = "", workdir: str = "") -> bool:
    """
    Run an executable with elevated privileges (UAC) on Windows.

    Args:
        exe_path: Full path to the executable
        args: Command line arguments
        workdir: Working directory

    Returns:
        True if launch was successful, False if user cancelled UAC or error
    """
    if sys.platform != 'win32':
        # Non-Windows: just use subprocess
        try:
            subprocess.Popen([exe_path] + (args.split() if args else []), cwd=workdir or None)
            return True
        except Exception:
            return False

    try:
        # Use ShellExecuteW with "runas" verb for elevation
        # Returns value > 32 on success
        result = ctypes.windll.shell32.ShellExecuteW(
            None,           # hwnd
            "runas",        # verb - request elevation
            exe_path,       # file
            args,           # parameters
            workdir,        # directory
            1               # nShowCmd (SW_SHOWNORMAL)
        )
        # ShellExecuteW returns >32 on success
        return result > 32
    except Exception:
        return False


def run_normal(exe_path: str, args: str = "", workdir: str = "") -> bool:
    """
    Run an executable without elevation using ShellExecuteW.

    Args:
        exe_path: Full path to the executable
        args: Command line arguments
        workdir: Working directory

    Returns:
        True if launch was successful, False otherwise
    """
    if sys.platform != 'win32':
        try:
            subprocess.Popen([exe_path] + (args.split() if args else []), cwd=workdir or None)
            return True
        except Exception:
            return False

    try:
        result = ctypes.windll.shell32.ShellExecuteW(
            None,           # hwnd
            "open",         # verb - normal open
            exe_path,       # file
            args,           # parameters
            workdir,        # directory
            1               # nShowCmd (SW_SHOWNORMAL)
        )
        return result > 32
    except Exception:
        return False


def _safe_campaign_filename(name: str) -> str:
    """Sanitise a campaign name for filesystem use (mirrors utils.formatting)."""
    cleaned = re.sub(r"[^\w\s-]", "", name)
    return cleaned.strip().replace(" ", "_")


def get_available_campaign_pdfs() -> Dict[str, Path]:
    """Return a mapping of campaign display-name -> PDF path for all existing PDFs.

    Scans ``<INSTALL_DIR>/reports/`` for sub-folders that contain a
    ``<safe_name>_Report.pdf`` file.
    """
    reports_dir = INSTALL_DIR / "reports"
    if not reports_dir.is_dir():
        return {}

    result: Dict[str, Path] = {}
    for entry in reports_dir.iterdir():
        if not entry.is_dir():
            continue
        safe_name = entry.name
        pdf_path = entry / f"{safe_name}_Report.pdf"
        if pdf_path.is_file():
            # Use the folder name as the display name (replace underscores with spaces)
            display_name = safe_name.replace("_", " ")
            result[display_name] = pdf_path

    return dict(sorted(result.items(), key=lambda item: item[0].lower()))


def open_pdf(path: Path) -> None:
    """Open a PDF file with the system default viewer (Windows only)."""
    try:
        os.startfile(str(path))
    except Exception as exc:
        messagebox.showerror(
            t('settings_manager.message.error_title'),
            f"{t('control_gui.message.error_open_pdf')}\n\n{path}\n\n{exc}",
        )


class ControlGUI(tk.Tk):
    """Main Control GUI window."""

    def __init__(self):
        super().__init__()

        self.title(t('control_gui.window_title'))
        self.configure(bg=BG_COLOR)
        self.resizable(False, False)

        # State
        self._tracker_process: Optional[subprocess.Popen] = None
        self._icons = {}
        self._check_timer_id = None
        self._bg_image = None
        self._bg_label = None

        # Set window icon
        self._set_window_icon()

        # Load icons
        self._load_icons()

        # Create UI
        self._create_ui()

        # Apply textured background
        self._apply_background_texture()

        # Start status monitoring
        self._start_status_monitor()

        # Center window
        self._center_window()

    def _set_window_icon(self):
        """Set the window icon."""
        # Window icon can be ICO format - look in INSTALL_DIR first, then ASSETS_DIR
        icon_path = INSTALL_DIR / WINDOW_ICON
        if not icon_path.exists():
            icon_path = ASSETS_DIR / WINDOW_ICON
        if icon_path.exists():
            try:
                self.iconbitmap(str(icon_path))
            except tk.TclError:
                pass  # Icon format not supported

    def _load_icons(self):
        """Load button icons from PNG files."""
        icon_configs = [
            ("tracker", TRACKER_ICON_PNG),
            ("service_record", SERVICE_RECORD_ICON_PNG),
            ("career", CAREER_ICON_PNG),
            ("settings", SETTINGS_ICON_PNG),
            ("stop", STOP_ICON_PNG),
            ("uninstall", UNINSTALL_ICON_PNG),
            ("pdf", PDF_ICON_PNG),
        ]

        for name, rel_path in icon_configs:
            # In frozen mode, assets are in ASSETS_DIR (_MEIPASS)
            # In dev mode, assets are relative to repo root
            icon_path = ASSETS_DIR / rel_path
            self._icons[name] = self._load_icon(icon_path, ICON_SIZE)

    def _load_icon(self, path: Path, size: int) -> Optional[tk.PhotoImage]:
        """Load and resize a PNG icon image."""
        if not path.exists():
            print(f"Icon not found: {path}")
            return self._create_placeholder_icon(size, path.stem)

        try:
            # Try loading with PIL for better quality resizing
            try:
                from PIL import Image, ImageTk
                img = Image.open(path)
                img = img.convert('RGBA')
                img = img.resize((size, size), Image.Resampling.LANCZOS)
                return ImageTk.PhotoImage(img)
            except ImportError:
                # Fallback to tkinter (only supports PNG/GIF)
                if path.suffix.lower() in ('.png', '.gif'):
                    img = tk.PhotoImage(file=str(path))
                    # Simple subsample for downscaling if needed
                    if img.width() > size:
                        factor = img.width() // size
                        if factor > 1:
                            img = img.subsample(factor)
                    return img
                return self._create_placeholder_icon(size, path.stem)
        except Exception as e:
            print(f"Error loading icon {path}: {e}")
            return self._create_placeholder_icon(size, path.stem)

    def _create_placeholder_icon(self, size: int, name: str) -> Optional[tk.PhotoImage]:
        """Create a placeholder icon when the real one is missing."""
        try:
            from PIL import Image, ImageDraw, ImageTk

            img = Image.new('RGBA', (size, size), (60, 63, 65, 255))
            draw = ImageDraw.Draw(img)

            # Draw specific icons based on name
            if 'stop' in name.lower():
                self._draw_stop_sign(draw, size)
            elif 'uninstall' in name.lower():
                self._draw_uninstall_icon(draw, size)
            else:
                # Generic icon - just a rounded box
                margin = size // 8
                draw.rounded_rectangle(
                    [margin, margin, size - margin, size - margin],
                    radius=size // 8,
                    fill=(80, 80, 80),
                    outline=(120, 120, 120)
                )

            return ImageTk.PhotoImage(img)
        except ImportError:
            return None

    def _draw_stop_sign(self, draw, size: int):
        """Draw a stop sign octagon."""
        try:
            margin = size // 10
            s = size - 2 * margin
            cx, cy = size // 2, size // 2
            d = s // 3
            points = [
                (cx - d, margin),
                (cx + d, margin),
                (cx + s//2, cy - d),
                (cx + s//2, cy + d),
                (cx + d, size - margin),
                (cx - d, size - margin),
                (margin, cy + d),
                (margin, cy - d),
            ]
            draw.polygon(points, fill=(220, 53, 69), outline=(180, 30, 50))
            draw.rectangle(
                [cx - s//4, cy - s//8, cx + s//4, cy + s//8],
                fill=(255, 255, 255)
            )
        except Exception:
            pass

    def _draw_uninstall_icon(self, draw, size: int):
        """Draw an uninstall X icon."""
        try:
            margin = size // 6
            line_width = size // 8
            draw.ellipse(
                [margin, margin, size - margin, size - margin],
                fill=(220, 53, 69),
                outline=(180, 30, 50)
            )
            inner_margin = size // 4
            draw.line(
                [(inner_margin, inner_margin), (size - inner_margin, size - inner_margin)],
                fill=(255, 255, 255),
                width=line_width
            )
            draw.line(
                [(size - inner_margin, inner_margin), (inner_margin, size - inner_margin)],
                fill=(255, 255, 255),
                width=line_width
            )
        except Exception:
            pass

    def _create_ui(self):
        """Create the main UI layout."""
        # Main frame with padding
        main_frame = tk.Frame(self, bg=BG_COLOR, padx=20, pady=20)
        main_frame.pack()

        # Status label at top
        self.status_label = tk.Label(
            main_frame,
            text=t('control_gui.status.checking'),
            font=(FONT_FAMILY, FONT_SIZE),
            bg=BG_COLOR,
            fg=TEXT_COLOR
        )
        self.status_label.pack(pady=(0, 15))

        # Button grid
        btn_frame = tk.Frame(main_frame, bg=BG_COLOR)
        btn_frame.pack()

        # Row 1: Start/Close Tracker
        self.btn_start = self._create_button(
            btn_frame, t('control_gui.button.start_tracker'),
            self._icons.get("tracker"),
            self._on_start_tracker,
            0, 0
        )

        self.btn_stop = self._create_button(
            btn_frame, t('control_gui.button.close_tracker'),
            self._icons.get("stop"),
            self._on_stop_tracker,
            0, 1
        )

        # Row 2: Campaign Service Record / Career Service Record
        self.btn_service_record = self._create_button(
            btn_frame, t('control_gui.button.service_record'),
            self._icons.get("service_record"),
            self._on_open_service_record,
            1, 0
        )

        self.btn_career_service_record = self._create_button(
            btn_frame, t('control_gui.button.career_service_record'),
            self._icons.get("career"),
            self._on_open_career_service_record,
            1, 1
        )

        # Row 3: Settings Manager / PDF Reports
        self.btn_settings = self._create_button(
            btn_frame, t('control_gui.button.settings_manager'),
            self._icons.get("settings"),
            self._on_open_settings,
            2, 0
        )

        self.btn_pdf = self._create_button(
            btn_frame, t('control_gui.button.pdf_reports'),
            self._icons.get("pdf"),
            self._on_pdf_reports,
            2, 1
        )

        # Row 4: Uninstall (full width)
        self.btn_uninstall = self._create_button(
            btn_frame, t('control_gui.button.uninstall'),
            self._icons.get("uninstall"),
            self._on_uninstall,
            3, 0,
            columnspan=2
        )

    def _create_button(
        self,
        parent: tk.Frame,
        text: str,
        icon: Optional[tk.PhotoImage],
        command: callable,
        row: int,
        col: int,
        columnspan: int = 1
    ) -> tk.Frame:
        """Create a styled button with icon and label."""
        # Frame to hold icon and label vertically
        btn_frame = tk.Frame(
            parent,
            bg=BTN_BG_COLOR,
            width=BUTTON_WIDTH,
            height=BUTTON_HEIGHT,
            cursor="hand2"
        )
        btn_frame.grid(row=row, column=col, columnspan=columnspan, padx=5, pady=5)
        btn_frame.pack_propagate(False)

        # Make frame clickable
        def on_click(event=None):
            if getattr(btn_frame, '_enabled', True):
                command()

        def on_enter(event):
            if getattr(btn_frame, '_enabled', True):
                btn_frame.configure(bg=BTN_ACTIVE_COLOR)
                for child in btn_frame.winfo_children():
                    try:
                        child.configure(bg=BTN_ACTIVE_COLOR)
                    except tk.TclError:
                        pass

        def on_leave(event):
            bg = BTN_BG_COLOR if getattr(btn_frame, '_enabled', True) else BTN_DISABLED_COLOR
            btn_frame.configure(bg=bg)
            for child in btn_frame.winfo_children():
                try:
                    child.configure(bg=bg)
                except tk.TclError:
                    pass

        btn_frame.bind("<Button-1>", on_click)
        btn_frame.bind("<Enter>", on_enter)
        btn_frame.bind("<Leave>", on_leave)

        # Icon (always create the label, even if icon is None)
        icon_label = tk.Label(btn_frame, bg=BTN_BG_COLOR)
        if icon:
            icon_label.configure(image=icon)
        icon_label.pack(pady=(10, 5))
        icon_label.bind("<Button-1>", on_click)
        icon_label.bind("<Enter>", on_enter)
        icon_label.bind("<Leave>", on_leave)

        # Text label (always visible)
        text_label = tk.Label(
            btn_frame,
            text=text,
            font=(FONT_FAMILY, FONT_SIZE, "bold"),
            bg=BTN_BG_COLOR,
            fg=TEXT_COLOR
        )
        text_label.pack(pady=(0, 10))
        text_label.bind("<Button-1>", on_click)
        text_label.bind("<Enter>", on_enter)
        text_label.bind("<Leave>", on_leave)

        # Store references for enable/disable
        btn_frame._text_label = text_label
        btn_frame._icon_label = icon_label
        btn_frame._command = command
        btn_frame._enabled = True

        return btn_frame

    def _apply_background_texture(self):
        """Apply a textured background similar to the provided reference."""
        self.update_idletasks()
        width = max(self.winfo_width(), 1)
        height = max(self.winfo_height(), 1)

        texture = self._build_texture_image(width, height)
        if texture is None:
            return

        self._bg_image = texture
        self._bg_label = tk.Label(self, image=self._bg_image, borderwidth=0, highlightthickness=0)
        self._bg_label.place(x=0, y=0, relwidth=1, relheight=1)
        self._bg_label.lower()

    def _build_texture_image(self, width: int, height: int) -> Optional[tk.PhotoImage]:
        """Generate a mottled, dark-brown texture using Tkinter only."""
        try:
            img = tk.PhotoImage(width=width, height=height)
            rng = random.Random(42)
            base_r, base_g, base_b = (36, 28, 20)

            for y in range(height):
                row_colors = []
                for _ in range(width):
                    n = rng.randint(-18, 18)
                    if rng.random() < 0.04:
                        n += rng.randint(10, 28)
                    r = max(0, min(255, base_r + n))
                    g = max(0, min(255, base_g + n))
                    b = max(0, min(255, base_b + n))
                    row_colors.append(f"#{r:02x}{g:02x}{b:02x}")
                img.put("{" + " ".join(row_colors) + "}", to=(0, y))

            return img
        except Exception:
            return None

    def _set_button_enabled(self, btn: tk.Frame, enabled: bool):
        """Enable or disable a button."""
        btn._enabled = enabled
        color = BTN_BG_COLOR if enabled else BTN_DISABLED_COLOR
        btn.configure(bg=color)
        for child in btn.winfo_children():
            try:
                child.configure(bg=color)
            except tk.TclError:
                pass

        if enabled:
            btn.configure(cursor="hand2")
        else:
            btn.configure(cursor="arrow")

    def _center_window(self):
        """Center the window on screen."""
        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.geometry(f"+{x}+{y}")

    def _start_status_monitor(self):
        """Start periodic status checking."""
        self._update_status()

    def _update_status(self):
        """Update tracker running status."""
        running = self._is_tracker_running()

        if running:
            self.status_label.configure(
                text="● " + t('control_gui.status.running'),
                fg=STATUS_RUNNING_COLOR
            )
            self._set_button_enabled(self.btn_start, False)
            self._set_button_enabled(self.btn_stop, True)
        else:
            self.status_label.configure(
                text="○ " + t('control_gui.status.not_running'),
                fg=STATUS_STOPPED_COLOR
            )
            self._set_button_enabled(self.btn_start, True)
            self._set_button_enabled(self.btn_stop, False)

        # Schedule next check
        self._check_timer_id = self.after(2000, self._update_status)

    def _is_tracker_running(self) -> bool:
        """Check if the tracker process is running."""
        # First check our own subprocess
        if self._tracker_process is not None:
            poll = self._tracker_process.poll()
            if poll is None:
                return True
            else:
                self._tracker_process = None

        # Check system-wide using psutil
        if HAS_PSUTIL:
            tracker_name = TRACKER_EXE.lower()
            for proc in psutil.process_iter(['name']):
                try:
                    if proc.info['name'] and proc.info['name'].lower() == tracker_name:
                        return True
                except (psutil.NoSuchProcess, psutil.AccessDenied, KeyError):
                    pass

        return False

    def _find_tracker_processes(self) -> list:
        """Find all tracker processes."""
        processes = []
        if HAS_PSUTIL:
            tracker_name = TRACKER_EXE.lower()
            for proc in psutil.process_iter(['name', 'pid']):
                try:
                    if proc.info['name'] and proc.info['name'].lower() == tracker_name:
                        processes.append(proc)
                except (psutil.NoSuchProcess, psutil.AccessDenied, KeyError):
                    pass
        return processes

    def _on_start_tracker(self):
        """Start the Campaign Tracker with elevation."""
        exe_path = INSTALL_DIR / TRACKER_EXE

        if not exe_path.exists():
            messagebox.showerror(
                t('settings_manager.message.error_title'),
                f"{t('control_gui.message.tracker_not_found')}\n{exe_path}"
            )
            return

        # Use ShellExecuteW with "runas" to request elevation
        if run_elevated(str(exe_path), "", str(INSTALL_DIR)):
            self.status_label.configure(
                text=t('control_gui.status.starting'),
                fg=TEXT_COLOR
            )
            # Schedule status update after a short delay
            self.after(1000, self._update_status)
        else:
            # User cancelled UAC or error occurred
            messagebox.showwarning(
                t('control_gui.message.launch_cancelled'),
                t('control_gui.message.launch_cancelled_detail')
            )

    def _on_stop_tracker(self):
        """Stop the Campaign Tracker."""
        # Try graceful shutdown first via our subprocess
        if self._tracker_process is not None:
            try:
                self._tracker_process.terminate()
                try:
                    self._tracker_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._tracker_process.kill()
                self._tracker_process = None
                self._update_status()
                return
            except Exception:
                pass

        # Find and terminate any running tracker processes
        processes = self._find_tracker_processes()
        if not processes:
            self._update_status()
            return

        for proc in processes:
            try:
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except psutil.TimeoutExpired:
                    proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        self._update_status()

    def _on_open_service_record(self):
        """Open the Campaign Service Record."""
        exe_path = INSTALL_DIR / SERVICE_RECORD_EXE

        if not exe_path.exists():
            messagebox.showerror(
                t('settings_manager.message.error_title'),
                f"{t('control_gui.message.service_record_not_found')}\n{exe_path}"
            )
            return

        if not run_normal(str(exe_path), "", str(INSTALL_DIR)):
            messagebox.showerror(
                t('settings_manager.message.error_title'),
                t('control_gui.message.error_open_service_record')
            )

    def _on_open_career_service_record(self):
        """Open the Career Service Record."""
        exe_path = INSTALL_DIR / CAREER_SERVICE_RECORD_EXE

        if not exe_path.exists():
            messagebox.showerror(
                t('settings_manager.message.error_title'),
                f"{t('control_gui.message.career_service_record_not_found')}\n{exe_path}"
            )
            return

        if not run_normal(str(exe_path), "", str(INSTALL_DIR)):
            messagebox.showerror(
                t('settings_manager.message.error_title'),
                t('control_gui.message.error_open_career_service_record')
            )

    def _on_open_settings(self):
        """Open the Settings Manager."""
        exe_path = INSTALL_DIR / SETTINGS_MANAGER_EXE

        if not exe_path.exists():
            messagebox.showerror(
                t('settings_manager.message.error_title'),
                f"{t('control_gui.message.settings_not_found')}\n{exe_path}"
            )
            return

        if not run_normal(str(exe_path), "", str(INSTALL_DIR)):
            messagebox.showerror(
                t('settings_manager.message.error_title'),
                t('control_gui.message.error_open_settings')
            )

    def _on_pdf_reports(self):
        """Show a popup menu listing available campaign PDFs."""
        pdfs = get_available_campaign_pdfs()

        menu = tk.Menu(self, tearoff=0, bg="#2f251b", fg=TEXT_COLOR,
                       activebackground=BTN_ACTIVE_COLOR, activeforeground=TEXT_COLOR,
                       font=(FONT_FAMILY, FONT_SIZE))

        if pdfs:
            for display_name, pdf_path in pdfs.items():
                # Capture pdf_path in default argument to avoid late-binding issue
                menu.add_command(
                    label=display_name,
                    command=lambda p=pdf_path: open_pdf(p),
                )
        else:
            menu.add_command(
                label=t('control_gui.message.no_pdfs_found'),
                state="disabled",
            )

        # Show the menu near the PDF button
        try:
            x = self.btn_pdf.winfo_rootx()
            y = self.btn_pdf.winfo_rooty() + self.btn_pdf.winfo_height()
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def _on_uninstall(self):
        """Launch the uninstaller."""
        exe_path = INSTALL_DIR / UNINSTALLER_EXE

        if not exe_path.exists():
            messagebox.showerror(
                t('settings_manager.message.error_title'),
                f"{t('control_gui.message.uninstaller_not_found')}\n{exe_path}\n\n"
                f"{t('control_gui.message.uninstall_manual')}"
            )
            return

        # Confirm uninstall
        if not messagebox.askyesno(
            t('control_gui.message.confirm_uninstall'),
            t('control_gui.message.confirm_uninstall_detail')
        ):
            return

        # Uninstaller typically needs elevation
        if run_elevated(str(exe_path), "", str(INSTALL_DIR)):
            # Close the control GUI after launching uninstaller
            self.quit()
        else:
            messagebox.showwarning(
                t('control_gui.message.uninstall_cancelled'),
                t('control_gui.message.uninstall_cancelled_detail')
            )

    def destroy(self):
        """Clean up on window close."""
        if self._check_timer_id:
            self.after_cancel(self._check_timer_id)
        super().destroy()


def main():
    """Main entry point."""
    app = ControlGUI()
    app.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
