# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller specification for Campaign Service Record

Builds standalone executable with all dependencies bundled.
"""

from PyInstaller.utils.hooks import collect_data_files
import sys
from pathlib import Path

# Determine base path
block_cipher = None
base_path = Path(SPECPATH)

# Collect data files
datas = [
    (str(base_path / 'static'), 'static'),
    (str(base_path / 'utils'), 'utils'),
    (str(base_path.parent / 'locales'), 'locales'),
    (str(base_path.parent / 'IBMPlexSans-Light.ttf'), '.'),
]

# Hidden imports (modules not auto-detected)
hiddenimports = [
    'flask',
    'werkzeug',
    'jinja2',
    'logging',
    'json',
    'pathlib',
    'utils.path_utils',
    'utils.pilot_photo',
    'campaign_service_record.utils.i18n',
    'PIL',
]

# Analysis
a = Analysis(
    ['app.py'],
    pathex=[str(base_path)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',  # Matplotlib not needed
        'numpy',  # NumPy not needed unless used by utils
        'pandas',  # Pandas not needed
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# PYZ
pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher
)

# EXE
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Campaign_Service_Record',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='Campaign_Service_Record.ico'
)

# Collect
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Campaign_Service_Record',
)
