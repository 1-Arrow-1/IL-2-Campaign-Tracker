# -*- mode: python ; coding:  utf-8 -*-

from PyInstaller.utils. hooks import collect_dynamic_libs

# psutil binaries (. pyd Dateien)
psutil_binaries = collect_dynamic_libs('psutil')
#import os
#wkhtml_path = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'
#print(f"wkhtmltopdf exists: {os.path.exists(wkhtml_path)}")

a = Analysis(
    ['il2_tracker_launcher.py'],
    pathex=[],
    binaries=[
        (r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe', '.'),
    ] + psutil_binaries,
    datas=[
        ('IBMPlexSans-Light.ttf', '.'),
        ('locales/*.json', 'locales'),  # i18n translation files
    ],
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
    a.binaries,
    a.datas,
    [],
    name='IL2_CampaignTracker_v2.0',
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
    icon='il2_tracker_icon.ico',
)
