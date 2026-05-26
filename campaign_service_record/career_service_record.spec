# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller specification for Career Service Record

Builds standalone executable for the Career Service Record app.
Entry point: career_main.py (sets CSR_APP_MODE=career before Flask starts).
Port: 5001 (to avoid conflict with Campaign Service Record on 5000).
"""

from pathlib import Path


block_cipher = None
base_path = Path(SPECPATH)

# Collect data files (identical to campaign_service_record.spec)
datas = [
    (str(base_path / 'static'), 'static'),
    (str(base_path / 'utils'), 'utils'),
    (str(base_path / 'career' / 'mission_types.json'), 'campaign_service_record/career'),
    (str(base_path.parent / 'locales'), 'locales'),
    (str(base_path.parent / 'IBMPlexSans-Light.ttf'), '.'),
    (str(base_path.parent / 'IL-2_Tracker_award_coordinates.json'), '.'),
]

# Hidden imports (same as campaign spec)
hiddenimports = [
    'flask',
    'werkzeug',
    'jinja2',
    'logging',
    'json',
    'pathlib',
    'campaign_service_record.utils.path_utils',
    'campaign_service_record.utils.pilot_photo',
    'campaign_service_record.utils.i18n',
    'campaign_service_record.utils.image_utils',
    'campaign_service_record.career.db_maintenance',
    'PIL',
    'PIL.Image',
    'PIL.DdsImagePlugin',
    'career_book_pdf',
]

a = Analysis(
    ['career_main.py'],
    pathex=[str(base_path)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'numpy',
        'pandas',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher
)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Career_Service_Record',
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

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Career_Service_Record',
)
