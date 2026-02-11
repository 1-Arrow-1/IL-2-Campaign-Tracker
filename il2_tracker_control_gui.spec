# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for IL-2 Tracker Control GUI

Build command:
    pyinstaller --noconfirm --clean il2_tracker_control_gui.spec
"""

import sys
from pathlib import Path

block_cipher = None

# Get the directory containing this spec file
SPEC_DIR = Path(SPECPATH)

a = Analysis(
    ['tools/il2_tracker_control_gui.py'],
    pathex=[str(SPEC_DIR)],
    binaries=[],
    datas=[
        # Include all PNG icon assets (required for button display)
        ('tools/icons/tracker.png', 'tools/icons'),
        ('tools/icons/service_record.png', 'tools/icons'),
        ('tools/icons/settings.png', 'tools/icons'),
        ('tools/icons/stop.png', 'tools/icons'),
        ('tools/icons/uninstall.png', 'tools/icons'),
        ('tools/icons/pdf.png', 'tools/icons'),
        # Include window icon (ICO format for window decoration)
        ('oak_leaves.ico', '.'),
    ],
    hiddenimports=[
        'tkinter',
        'tkinter.ttk',
        'tkinter.messagebox',
        'PIL',
        'PIL.Image',
        'PIL.ImageTk',
        'PIL.ImageDraw',
        'psutil',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'pytest',
        'unittest',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='IL2_Tracker_Control_GUI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console window - GUI only
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='oak_leaves.ico',
)
