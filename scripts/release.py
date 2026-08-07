#!/usr/bin/env python3
"""
Automated Release Workflow Script for Maple Classic Auto Reporter.

Usage:
    python scripts/release.py                      # Interactive mode
    python scripts/release.py --type minor         # Bump minor version (v1.0.0 -> v1.1.0)
    python scripts/release.py --type patch         # Bump patch version (v1.1.0 -> v1.1.1)
    python scripts/release.py --type major         # Bump major version (v1.0.0 -> v2.0.0)
    python scripts/release.py --version 1.0.0      # Set explicit version
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
INIT_PY = ROOT_DIR / "src" / "maple_reporter" / "__init__.py"
PYPROJECT_TOML = ROOT_DIR / "pyproject.toml"
README_MD = ROOT_DIR / "README.md"
CONTEXT_MD = ROOT_DIR / "CONTEXT.md"
DIST_DIR = ROOT_DIR / "dist"
BUILD_SCRIPT = ROOT_DIR / "scripts" / "build_windows.ps1"


def get_current_version() -> str:
    content = INIT_PY.read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
    if not match:
        raise RuntimeError("Cannot find __version__ in src/maple_reporter/__init__.py")
    return match.group(1)


def parse_semver(version_str: str) -> tuple[int, int, int]:
    clean = version_str.lstrip("v")
    parts = clean.split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        raise ValueError(f"Invalid semver string: '{version_str}'")
    return int(parts[0]), int(parts[1]), int(parts[2])


def calculate_next_version(current: str, bump_type: str) -> str:
    major, minor, patch = parse_semver(current)
    if bump_type == "major":
        return f"{major + 1}.0.0"
    elif bump_type == "minor":
        return f"{major}.{minor + 1}.0"
    elif bump_type == "patch":
        return f"{major}.{minor}.{patch + 1}"
    else:
        raise ValueError(f"Unknown bump type: '{bump_type}'")


def update_file_version(file_path: Path, pattern: str, replacement: str):
    if not file_path.exists():
        return
    text = file_path.read_text(encoding="utf-8")
    updated_text = re.sub(pattern, replacement, text)
    file_path.write_text(updated_text, encoding="utf-8")
    print(f"  [OK] Updated {file_path.name}")


def update_all_version_files(new_version: str):
    print(f"\n[1/6] Updating version string to '{new_version}' across codebase...")

    # 1. src/maple_reporter/__init__.py
    update_file_version(
        INIT_PY,
        r'__version__\s*=\s*["\'][^"\']+["\']',
        f'__version__ = "{new_version}"'
    )

    # 2. pyproject.toml
    update_file_version(
        PYPROJECT_TOML,
        r'(version\s*=\s*["\'])[^"\']+(["\'])',
        rf'\g<1>{new_version}\g<2>'
    )

    # 3. README.md
    update_file_version(
        README_MD,
        r'v\d+\.\d+\.\d+',
        f'v{new_version}'
    )

    # 4. CONTEXT.md
    update_file_version(
        CONTEXT_MD,
        r'v\d+\.\d+\.\d+',
        f'v{new_version}'
    )


def run_unit_tests():
    print("\n[2/6] Running unit test suite...")
    venv_python = ROOT_DIR / ".venv" / "Scripts" / "python.exe"
    python_cmd = str(venv_python) if venv_python.exists() else sys.executable

    res = subprocess.run([python_cmd, "-m", "unittest", "discover", "tests"], cwd=ROOT_DIR)
    if res.returncode != 0:
        print("\n[ERROR] Unit tests failed! Aborting release.")
        sys.exit(1)
    print("  [OK] All unit tests passed!")


def build_executable():
    print("\n[3/6] Compiling standalone EXE with PyInstaller...")
    cmd = ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(BUILD_SCRIPT)]
    res = subprocess.run(cmd, cwd=ROOT_DIR)
    if res.returncode != 0:
        print("\n[ERROR] PyInstaller build failed! Aborting release.")
        sys.exit(1)

    exe_path = DIST_DIR / "MapleClassicReporter.exe"
    if not exe_path.exists():
        print(f"\n[ERROR] Compiled EXE not found at '{exe_path}'!")
        sys.exit(1)
    print("  [OK] Successfully compiled MapleClassicReporter.exe!")


def zip_release(new_version: str) -> Path:
    print("\n[4/6] Packaging release ZIP...")
    exe_path = DIST_DIR / "MapleClassicReporter.exe"
    zip_name = f"MapleClassicReporter-v{new_version}-windows-x64.zip"
    zip_path = DIST_DIR / zip_name

    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(exe_path, arcname="MapleClassicReporter.exe")

    print(f"  [OK] Created {zip_path} ({zip_path.stat().st_size / 1024 / 1024:.2f} MB)")
    return zip_path


def git_commit_tag_push(new_version: str):
    print("\n[5/6] Performing Git commit, tagging, and push...")
    tag_name = f"v{new_version}"

    # Explicitly add only version-managed files to ensure no unignored data files are committed
    files_to_stage = [
        "src/maple_reporter/__init__.py",
        "src/maple_reporter/gui/main_window.py",
        "pyproject.toml",
        "README.md",
        "CONTEXT.md",
        "tests/test_modules.py",
        "scripts/",
        ".github/"
    ]
    subprocess.run(["git", "add"] + files_to_stage, cwd=ROOT_DIR, check=True)

    # Check if there are staged changes to commit
    diff_res = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT_DIR)
    if diff_res.returncode != 0:
        subprocess.run(["git", "commit", "-m", f"release: {tag_name}"], cwd=ROOT_DIR, check=True)
    else:
        print("  [NOTICE] No staged changes to commit.")

    # Remove tag if exists locally
    subprocess.run(["git", "tag", "-d", tag_name], cwd=ROOT_DIR, capture_output=True)
    subprocess.run(["git", "tag", tag_name], cwd=ROOT_DIR, check=True)

    print("  Pushing commits and tags to GitHub...")
    subprocess.run(["git", "push", "origin", "main"], cwd=ROOT_DIR, check=True)
    subprocess.run(["git", "push", "origin", tag_name, "--force"], cwd=ROOT_DIR, check=True)
    print("  [OK] Git commit, tag, and push completed!")


def publish_github_release(new_version: str, zip_path: Path):
    print("\n[6/6] Publishing GitHub Release with auto-generated notes...")
    tag_name = f"v{new_version}"
    gh_cmd = shutil.which("gh")

    if not gh_cmd:
        print("  [NOTICE] GitHub CLI ('gh') is not installed locally.")
        print("  GitHub Actions workflow will complete the release automatically upon tag push!")
        return

    cmd = [
        gh_cmd, "release", "create", tag_name,
        str(zip_path),
        "--title", f"v{new_version}",
        "--generate-notes"
    ]
    res = subprocess.run(cmd, cwd=ROOT_DIR)
    if res.returncode == 0:
        print("  [OK] GitHub Release successfully created with auto-generated release notes!")
    else:
        print("  [WARNING] gh release command failed. GitHub Actions will handle release publishing.")


def main():
    parser = argparse.ArgumentParser(description="Maple Classic Auto Reporter Release Tool")
    parser.add_argument("--type", choices=["major", "minor", "patch"], help="Bump type (major, minor, patch)")
    parser.add_argument("--version", help="Explicit version string (e.g. 1.0.0)")
    parser.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompt")

    args = parser.parse_args()
    current_version = get_current_version()
    print(f"=== Maple Classic Auto Reporter Release Tool ===")
    print(f"Current version: v{current_version}")

    if args.version:
        new_version = args.version.lstrip("v")
    elif args.type:
        new_version = calculate_next_version(current_version, args.type)
    elif args.yes:
        new_version = calculate_next_version(current_version, "minor")
    else:
        print("\nSelect release bump type:")
        print(f"  1) Major (重大破壞性更新: v{current_version} -> v{calculate_next_version(current_version, 'major')})")
        print(f"  2) Minor (功能更新: v{current_version} -> v{calculate_next_version(current_version, 'minor')})")
        print(f"  3) Patch (Bug 修復: v{current_version} -> v{calculate_next_version(current_version, 'patch')})")
        print(f"  4) Custom (自訂版本號)")

        choice = input("\nEnter choice (1-4) [default: 2]: ").strip() or "2"
        if choice == "1":
            new_version = calculate_next_version(current_version, "major")
        elif choice == "2":
            new_version = calculate_next_version(current_version, "minor")
        elif choice == "3":
            new_version = calculate_next_version(current_version, "patch")
        elif choice == "4":
            new_version = input("Enter custom version (e.g. 1.0.0): ").strip().lstrip("v")
        else:
            print("Invalid choice. Exiting.")
            sys.exit(1)

    print(f"\n>>> Target Release Version: v{new_version} <<<")
    if not (args.version or args.type or args.yes):
        confirm = input("Proceed with release? (y/N): ").strip().lower()
        if confirm != "y":
            print("Release canceled.")
            sys.exit(0)

    update_all_version_files(new_version)
    run_unit_tests()
    build_executable()
    zip_path = zip_release(new_version)
    git_commit_tag_push(new_version)
    publish_github_release(new_version, zip_path)

    print(f"\n==========================================")
    print(f" SUCCESS! Release v{new_version} published!")
    print(f"==========================================")


if __name__ == "__main__":
    main()
