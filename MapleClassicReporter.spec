# -*- mode: python ; coding: utf-8 -*-

"""One-file Windows build with Playwright's driver and Chromium included."""

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


PROJECT_ROOT = Path(SPECPATH).resolve()
PLAYWRIGHT_PACKAGE = Path(__import__("playwright").__file__).resolve().parent
PLAYWRIGHT_DRIVER = PLAYWRIGHT_PACKAGE / "driver"

from playwright.sync_api import sync_playwright


with sync_playwright() as playwright:
    chromium_executable = Path(playwright.chromium.executable_path)

if not chromium_executable.is_file():
    raise SystemExit(
        "Playwright Chromium is not installed. Run "
        "'uv run playwright install chromium' before building."
    )

CHROMIUM_DIRECTORY = chromium_executable.parents[1]
if not CHROMIUM_DIRECTORY.name.startswith("chromium-"):
    raise SystemExit(f"Unexpected Playwright Chromium directory: {CHROMIUM_DIRECTORY}")

datas = [
    (str(PROJECT_ROOT / "assets" / "icon.png"), "assets"),
    (str(PROJECT_ROOT / "src" / "maple_reporter" / "ocr" / "data"), "maple_reporter/ocr/data"),
    (str(PLAYWRIGHT_DRIVER / "package"), "playwright/driver/package"),
    (str(PLAYWRIGHT_DRIVER / "node.exe"), "playwright/driver"),
    (str(CHROMIUM_DIRECTORY), f"ms-playwright/{CHROMIUM_DIRECTORY.name}"),
]
datas.extend(collect_data_files("rapidocr_onnxruntime"))

a = Analysis(
    [str(PROJECT_ROOT / "src" / "maple_reporter" / "main.py")],
    pathex=[str(PROJECT_ROOT / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=collect_submodules("playwright"),
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
    name="MapleClassicReporter",
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
    icon=[str(PROJECT_ROOT / "assets" / "icon.ico")],
)
