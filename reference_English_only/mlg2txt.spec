# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for mlg2txt.exe

Creates a standalone executable for converting IL-2 .mlg files to .txt format.
This allows users to run the IL-2 Campaign Tracker without requiring Python.

Build command:
    pyinstaller mlg2txt.spec
"""

a = Analysis(
    ['mlg2txt.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name='mlg2txt',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Console app (needs to show output)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
