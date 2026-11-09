# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for PhoneMic Windows Receiver v0.11.0

    pyinstaller --clean PhoneMicReceiver.spec                 -> dist\PhoneMicReceiver.exe        (single file, portable)
    set PM_ONEDIR=1 && pyinstaller --clean PhoneMicReceiver.spec
                                                              -> dist\PhoneMicReceiver\            (folder, starts instantly)
"""
import os
from PyInstaller.utils.hooks import collect_all

ONEDIR = os.environ.get("PM_ONEDIR", "") == "1"
ICON = os.path.join("assets", "phonemic.ico")

datas, binaries = [], []
hiddenimports = [
    "sounddevice", "_sounddevice_data", "numpy", "pystray", "pystray._win32", "PIL", "PIL.Image", "PIL.ImageDraw", "winsound",
    "tkinter", "tkinter.ttk", "tkinter.messagebox", "tkinter.filedialog", "_tkinter",
    "winreg", "wave", "webbrowser",
    # the application package (listed explicitly so the lazy imports in gui/launcher are always bundled)
    "phonemic", "phonemic.const", "phonemic.config", "phonemic.system", "phonemic.dsp", "phonemic.engine",
    "phonemic.widgets", "phonemic.ui_kit", "phonemic.gui", "phonemic.pages", "phonemic.wizard", "phonemic.cli", "phonemic.icon",
    "phonemic.bindings", "phonemic.settings_meta", "phonemic.presets_io", "phonemic.hotkeys", "phonemic.tray", "phonemic.cues",
    "phonemic.selftest", "phonemic.qr", "phonemic.qrcodegen",
]

# PortAudio DLL + sounddevice package data
for pkg in ("sounddevice", "_sounddevice_data", "pystray"):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

# Things that may be installed in your global Python but are never used here (keeps the exe small)
excludes = ["scipy", "matplotlib", "pandas", "IPython", "pytest", "notebook", "sphinx", "numba", "torch", "cv2"]

a = Analysis(
    ["phonemic_receiver.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data)

exe_kwargs = dict(
    name="PhoneMicReceiver",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                 # UPX makes startup slower and triggers antivirus false positives
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON if os.path.exists(ICON) else None,
)

if ONEDIR:
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, **exe_kwargs)
    coll = COLLECT(exe, a.binaries, a.zipfiles, a.datas, strip=False, upx=False, name="PhoneMicReceiver")
else:
    exe = EXE(pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [], runtime_tmpdir=None, **exe_kwargs)
