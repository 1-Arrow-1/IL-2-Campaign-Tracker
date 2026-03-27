# -*- mode: python ; coding:  utf-8 -*-

import os
from pathlib import Path

from PyInstaller.building.datastruct import Tree
from PyInstaller.utils.hooks import collect_dynamic_libs

base_path = Path(SPECPATH)

# psutil binaries (.pyd Dateien)
psutil_binaries = collect_dynamic_libs('psutil')

wkhtmltopdf_candidate = os.environ.get(
    "WKHTMLTOPDF_PATH",
    r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe",
)
wkhtmltopdf_path = Path(wkhtmltopdf_candidate)
wkhtmltopdf_binaries = []
if wkhtmltopdf_path.exists():
    wkhtmltopdf_binaries.append((str(wkhtmltopdf_path), "."))

datas = [
    (str(base_path / "IBMPlexSans-Light.ttf"), "."),
    (str(base_path / "NotoSansSC-VF.ttf"), "."),
    (str(base_path / "campaign_progress_config.yaml"), "."),
    (str(base_path / "object_categories.yaml"), "."),
    (str(base_path / "stock_campaigns.yaml"), "."),
    (str(base_path / "locales"), "locales"),
    (str(base_path / "historical_context"), "historical_context"),
]

a = Analysis(
    ['il2_tracker_launcher.py'],
    pathex=[str(base_path)],
    binaries=wkhtmltopdf_binaries + psutil_binaries,
    datas=datas,
    hiddenimports=[
        'tkinter',
        'tkinter.ttk',
        '_tkinter',
        'pdfkit',
        'country_validator_gui',
        'step1_extract_mission_dates',
        'step3_generate_events',
        'step4_process_mission_logs',
        'decode_campaign_usersave1',
        'monitor_campaigns',
        'il2_mission_debrief',
        'cleanup_failed_missions',
        'backup_restore_gui',
        'popups_min',
        'campaign_reset_checker',
		'sync_campaign_mission_states',
        'llm_story_generator',
        'campaign_service_record',
        'campaign_service_record.utils',
        'utils',
        'utils.formatting',
        'utils.info_locale',
        'utils.pathing',
		'utils.il2_paths',
        'utils.combat_results',
		'utils.combat_results_html',
		'utils.filesystem',
		'utils.popup_state',
		'utils.process',
		'utils.sorting',
		'utils.logging',
        'utils.rank_scaling',
        'openai',
        'campaign_service_record.utils.i18n',  # NEW: i18n module
        'utils.locale_config',  # NEW: locale config module
		'regex',
        'PIL',
        'PIL.Image',
        'PIL.DdsImagePlugin',
        'psutil',
        'psutil._common',
        'psutil._compat',
        'psutil._psplatform',
        'psutil._psutil_windows',
        'psutil._pswindows',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a. pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    name='IL2_CampaignTracker_v2.2_ML',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    uac_admin=True,
    icon='il2_tracker_icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='IL2_CampaignTracker_v2.2_ML',
)
