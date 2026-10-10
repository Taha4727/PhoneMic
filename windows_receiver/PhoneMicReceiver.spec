# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller Spec File for PhoneMic Windows Receiver
Bundles PhoneMic Receiver, SoundDevice, PortAudio DLLs, NumPy, and all dependencies
into a single standalone Windows executable (PhoneMicReceiver.exe).
"""

import sys
import os
from PyInstaller.utils.hooks import collect_all

block_cipher = None

datas = []
binaries = []
hiddenimports = [
    'sounddevice',
    '_sounddevice_data',
    'numpy',
    'queue',
    'threading',
    'socket',
    'struct',
    'math',
    'wave',
    'webbrowser',
    'platform',
    'shutil',
    'ctypes',
]

# Collect all sounddevice binaries, PortAudio DLLs, and package data
try:
    sd_datas, sd_binaries, sd_hidden = collect_all('sounddevice')
    datas += sd_datas
    binaries += sd_binaries
    hiddenimports += sd_hidden
except Exception:
    pass

# Collect all numpy data and C-extension binaries
try:
    np_datas, np_binaries, np_hidden = collect_all('numpy')
    datas += np_datas
    binaries += np_binaries
    hiddenimports += np_hidden
except Exception:
    pass

a = Analysis(
    ['phonemic_receiver.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='PhoneMicReceiver',
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
)
