# -*- mode: python ; coding: utf-8 -*-

"""One-directory Windows build with Playwright, Chromium, and OAuth client included."""

import json
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


PROJECT_ROOT = Path(SPECPATH).resolve()
PLAYWRIGHT_PACKAGE = Path(__import__("playwright").__file__).resolve().parent
PLAYWRIGHT_DRIVER = PLAYWRIGHT_PACKAGE / "driver"
OAUTH_CLIENT_CONFIG = PROJECT_ROOT / "build_secrets" / "google_oauth_client.json"

if not OAUTH_CLIENT_CONFIG.is_file():
    raise SystemExit(
        "Release build requires build_secrets/google_oauth_client.json. "
        "The OAuth client resource is intentionally not committed to Git."
    )

try:
    with OAUTH_CLIENT_CONFIG.open("r", encoding="utf-8") as oauth_file:
        oauth_config = json.load(oauth_file)
except (OSError, ValueError) as error:
    raise SystemExit(
        "build_secrets/google_oauth_client.json is not valid JSON."
    ) from error

if not isinstance(oauth_config, dict) or not isinstance(oauth_config.get("installed"), dict):
    raise SystemExit(
        "build_secrets/google_oauth_client.json must contain an installed OAuth client."
    )

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
    (str(PROJECT_ROOT / "assets" / "icon.ico"), "assets"),
    (str(PROJECT_ROOT / "web" / "dist"), "web/dist"),
    (str(PROJECT_ROOT / "src" / "maple_reporter" / "ocr" / "data"), "maple_reporter/ocr/data"),
    (str(OAUTH_CLIENT_CONFIG), "."),
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
    hiddenimports=collect_submodules("playwright") + collect_submodules("windows_capture"),
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
    [],
    exclude_binaries=True,
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

# Keep the native dependencies, Playwright driver, Chromium, and data files
# beside the executable.  The one-file bootloader would unpack all of these
# files into a fresh _MEI directory on every launch, which is especially slow
# for the bundled Chromium runtime.
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="MapleClassicReporter",
)
