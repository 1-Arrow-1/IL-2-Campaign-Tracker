# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for il2_debrief.exe

Creates a standalone, headless executable that analyses one IL-2 mission log
and writes the facts as JSON, for use by other programs (e.g. PWCG+).
See docs/integration/DEBRIEF_CLI.md.

Ship it next to mlg2txt.exe so it can read .mlg logs directly.
An object_categories.yaml placed next to the exe overrides the embedded copy.

Build command:
    pyinstaller il2_debrief.spec
"""

a = Analysis(
    ['il2_debrief_cli.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('object_categories.yaml', '.'),
        ('version.txt', '.'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'flask', 'openai', 'reportlab', 'PIL', 'numpy'],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='il2_debrief',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Console app: the caller reads stdout and the exit code
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
