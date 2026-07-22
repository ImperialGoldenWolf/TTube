# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for TTube standalone executable
# Usage: pyinstaller ttube.spec

import sys
from pathlib import Path

block_cipher = None

from PyInstaller.utils.hooks import collect_data_files

# Determine if running on Windows
is_windows = sys.platform == 'win32'

datas = [('ttube.ico', '.')]
datas += collect_data_files('ytmusicapi')

a = Analysis(
    ['ttube.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=['sounddevice', 'yt_dlp', 'imageio_ffmpeg', 'ytmusicapi', 'windows_curses' if is_windows else ''],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludedimports=[],
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
    name='ttube',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='ttube.ico',
)


