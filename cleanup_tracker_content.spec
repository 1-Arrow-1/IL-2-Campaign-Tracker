# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for cleanup_tracker_content.exe

This creates a small standalone executable for the uninstaller.
Run with: pyinstaller cleanup_tracker_content.spec
"""

a = Analysis(
    ['cleanup_tracker_content.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'utils.info_locale',
        'regex',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude unnecessary modules to keep size small
        'tkinter',
        'PIL',
        'numpy',
        'pandas',
        'matplotlib',
        'scipy',
        'PyQt5',
        'PyQt6',
        'PySide2',
        'PySide6',
        'wx',
        'unittest',
        'test',
        'xmlrpc',
        'html',
        'http',
        'email',
        'pydoc',
        'doctest',
        'distutils',
    ],
    noarchive=False,
    optimize=2,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='cleanup_tracker_content',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Console app for uninstaller use
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Optional: Add icon if desired
)
