#!/usr/bin/env python3
"""Verify a PyInstaller onedir bundle and optionally run its smoke mode."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUNDLE = ROOT / "dist" / "MapleClassicReporter"


def verify_bundle(bundle: Path) -> list[str]:
    resource_root = bundle / "_internal" if (bundle / "_internal").is_dir() else bundle
    required_files = {
        "executable": bundle / "MapleClassicReporter.exe",
        "updater executable": bundle / "MapleClassicReporterUpdater.exe",
        "React entrypoint": resource_root / "web" / "dist" / "index.html",
        "application icon": resource_root / "assets" / "icon.png",
        "PyInstaller icon": resource_root / "assets" / "icon.ico",
        "OAuth client": resource_root / "google_oauth_client.json",
        "Playwright driver": resource_root / "playwright" / "driver" / "node.exe",
    }
    errors = [f"Missing {label}: {path}" for label, path in required_files.items() if not path.is_file()]

    oauth_path = required_files["OAuth client"]
    if oauth_path.is_file():
        try:
            oauth_config = json.loads(oauth_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            errors.append(f"Invalid OAuth client JSON: {error}")
        else:
            if not isinstance(oauth_config, dict) or not isinstance(oauth_config.get("installed"), dict):
                errors.append("OAuth client JSON must contain an installed object")

    chromium = list((resource_root / "ms-playwright").glob("chromium-*/chrome-win*/chrome.exe"))
    if not chromium:
        errors.append(
            f"Bundled Chromium executable not found under {resource_root / 'ms-playwright'}"
        )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-dir", type=Path, default=DEFAULT_BUNDLE)
    parser.add_argument(
        "--launch-smoke",
        action="store_true",
        help="Run MapleClassicReporter.exe --smoke-test after static checks.",
    )
    args = parser.parse_args()
    bundle = args.bundle_dir.expanduser().resolve()
    errors = verify_bundle(bundle)
    if errors:
        print("Release bundle verification failed:")
        print("\n".join(f"- {error}" for error in errors))
        return 1

    print(f"Release bundle files verified: {bundle}")
    if args.launch_smoke:
        executable = bundle / "MapleClassicReporter.exe"
        try:
            result = subprocess.run(
                [str(executable), "--smoke-test"],
                cwd=bundle,
                check=False,
                capture_output=True,
                text=True,
                timeout=120,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            print(f"Bundle smoke process failed: {error}")
            return 1
        if result.stdout:
            print(result.stdout.rstrip())
        if result.stderr:
            print(result.stderr.rstrip())
        if result.returncode != 0:
            print(f"Bundle smoke process exited with {result.returncode}")
            return result.returncode or 1
        print("Bundle executable smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
