# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


PROJECT_ROOT = Path(SPECPATH).resolve()
CAMERA_ICON = PROJECT_ROOT / "assets" / "icon.ico"

a = Analysis(
    [str(PROJECT_ROOT / "src" / "maple_reporter" / "update" / "updater_main.py")],
    pathex=[str(PROJECT_ROOT / "src")],
    binaries=[],
    # Keep the camera icon beside the one-file updater so the Tk title bar and
    # taskbar can use the same artwork as the executable resource.
    datas=[(str(CAMERA_ICON), "assets")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="MapleClassicReporterUpdater",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(CAMERA_ICON),
)
