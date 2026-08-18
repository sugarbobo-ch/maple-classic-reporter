#!/usr/bin/env python3
"""Safe, explicit release workflow for Maple Classic Auto Reporter.

The script is intentionally conservative: it refuses to start from a dirty
worktree, creates a new commit/tag without force operations, builds from that
exact commit, and only pushes after the build succeeds.
"""

from __future__ import annotations

import argparse
import os
import re
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
RELEASE_BUNDLE_DIR = DIST_DIR / "MapleClassicReporter"
RELEASE_EXE = RELEASE_BUNDLE_DIR / "MapleClassicReporter.exe"
RELEASE_NOTES_DIR = ROOT_DIR / "docs" / "releases"
BUILD_SCRIPT = ROOT_DIR / "scripts" / "build_windows.ps1"
SENSITIVE_PATH_PARTS = {
    "build_secrets",
    "client_secrets.json",
    "google_oauth_client.json",
    "token.json",
    ".dpapi",
}


def _run_git(*arguments: str, capture_output: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *arguments],
        cwd=ROOT_DIR,
        check=True,
        text=True,
        capture_output=capture_output,
    )


def get_worktree_status() -> list[str]:
    result = _run_git(
        "status", "--porcelain=v1", "--untracked-files=all", capture_output=True
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


def ensure_clean_worktree() -> None:
    dirty = get_worktree_status()
    if dirty:
        preview = "\n".join(dirty[:20])
        raise RuntimeError(
            "Release requires a clean worktree. Commit or stash these changes first:\n"
            + preview
        )


def get_current_version() -> str:
    content = INIT_PY.read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
    if not match:
        raise RuntimeError("Cannot find __version__ in src/maple_reporter/__init__.py")
    return match.group(1)


SEMVER_PATTERN = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>[0-9A-Za-z.-]+))?"
    r"(?:\+(?P<build>[0-9A-Za-z.-]+))?$"
)


def parse_semver(version_str: str) -> tuple[int, int, int, str | None]:
    clean = version_str.lstrip("v")
    match = SEMVER_PATTERN.match(clean)
    if not match:
        raise ValueError(f"Invalid semver string: '{version_str}'")
    return (
        int(match.group("major")),
        int(match.group("minor")),
        int(match.group("patch")),
        match.group("prerelease"),
    )


def calculate_next_version(current: str, bump_type: str) -> str:
    major, minor, patch, _ = parse_semver(current)
    if bump_type == "major":
        return f"{major + 1}.0.0"
    if bump_type == "minor":
        return f"{major}.{minor + 1}.0"
    if bump_type == "patch":
        return f"{major}.{minor}.{patch + 1}"
    raise ValueError(f"Unknown bump type: '{bump_type}'")


def update_file_version(file_path: Path, pattern: str, replacement: str) -> None:
    if not file_path.exists():
        return
    text = file_path.read_text(encoding="utf-8")
    updated_text = re.sub(pattern, replacement, text)
    file_path.write_text(updated_text, encoding="utf-8")
    print(f"  [OK] Updated {file_path.name}")


def update_all_version_files(new_version: str) -> None:
    parse_semver(new_version)
    print(f"\n[1/6] Updating version string to '{new_version}' across codebase...")
    update_file_version(
        INIT_PY,
        r'__version__\s*=\s*["\'][^"\']+["\']',
        f'__version__ = "{new_version}"',
    )
    update_file_version(
        PYPROJECT_TOML,
        r'(version\s*=\s*["\'])[^"\']+(["\'])',
        rf"\g<1>{new_version}\g<2>",
    )
    update_file_version(
        ROOT_DIR / "web" / "package.json",
        r'("version":\s*")[^"]+(")',
        rf"\g<1>{new_version}\g<2>",
    )
    update_file_version(
        README_MD,
        r"(?m)^(# .*? v)\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?",
        rf"\g<1>{new_version}",
    )
    update_file_version(
        README_MD,
        r"(MapleClassicReporter-v)\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(-windows-x64\.zip)",
        rf"\g<1>{new_version}\g<2>",
    )
    update_file_version(
        CONTEXT_MD,
        r"(?m)^- \*\*Version\*\*: `[^`]+`",
        f"- **Version**: `{new_version}`",
    )
    update_file_version(
        CONTEXT_MD,
        r"(MapleClassicReporter-v)\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(-windows-x64\.zip)",
        rf"\g<1>{new_version}\g<2>",
    )
    major, minor, patch, _ = parse_semver(new_version)
    version_info_path = ROOT_DIR / "assets" / "version_info.txt"
    if version_info_path.is_file():
        update_file_version(
            version_info_path,
            r"filevers=\(\d+,\s*\d+,\s*\d+,\s*\d+\)",
            f"filevers=({major}, {minor}, {patch}, 0)",
        )
        update_file_version(
            version_info_path,
            r"prodvers=\(\d+,\s*\d+,\s*\d+,\s*\d+\)",
            f"prodvers=({major}, {minor}, {patch}, 0)",
        )
        update_file_version(
            version_info_path,
            r"StringStruct\('FileVersion',\s*'[^']+'\)",
            f"StringStruct('FileVersion', '{major}.{minor}.{patch}.0')",
        )
        update_file_version(
            version_info_path,
            r"StringStruct\('ProductVersion',\s*'[^']+'\)",
            f"StringStruct('ProductVersion', '{new_version}')",
        )


def refresh_lockfile() -> None:
    """Regenerate uv.lock after the project version is changed."""

    print("  [OK] Refreshing uv.lock for the new project version...")
    result = subprocess.run(["uv", "lock"], cwd=ROOT_DIR)
    if result.returncode != 0:
        raise RuntimeError("uv lock failed after updating the project version.")


def run_unit_tests() -> None:
    print("\n[2/6] Running unit test suite...")
    python_cmd = sys.executable
    test_env = os.environ.copy()
    source_path = str(ROOT_DIR / "src")
    test_env["PYTHONPATH"] = os.pathsep.join(
        path for path in (source_path, test_env.get("PYTHONPATH", "")) if path
    )
    result = subprocess.run(
        [python_cmd, "-m", "unittest", "discover", "tests"],
        cwd=ROOT_DIR,
        env=test_env,
    )
    if result.returncode != 0:
        raise RuntimeError("Unit tests failed; release was not pushed.")
    print("  [OK] All unit tests passed!")


def build_executable(expected_commit: str | None = None) -> Path:
    print("\n[3/6] Compiling onedir Windows bundle with PyInstaller...")
    if expected_commit:
        actual_commit = _run_git("rev-parse", "HEAD", capture_output=True).stdout.strip()
        if actual_commit != expected_commit:
            raise RuntimeError("Build source changed after the release commit was created.")
    result = subprocess.run(
        ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(BUILD_SCRIPT)],
        cwd=ROOT_DIR,
    )
    if result.returncode != 0:
        raise RuntimeError("PyInstaller build failed; release was not pushed.")

    if not RELEASE_EXE.exists():
        raise RuntimeError(f"Compiled EXE not found at '{RELEASE_EXE}'.")
    print(f"  [OK] Successfully compiled {RELEASE_BUNDLE_DIR}")
    return RELEASE_BUNDLE_DIR


def zip_release(new_version: str) -> Path:
    print("\n[4/6] Packaging release ZIP...")
    if not RELEASE_EXE.exists():
        raise RuntimeError("Cannot package a missing onedir executable.")
    zip_path = DIST_DIR / f"MapleClassicReporter-v{new_version}-windows-x64.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for file_path in sorted(RELEASE_BUNDLE_DIR.rglob("*")):
            if not file_path.is_file():
                continue
            relative_path = file_path.relative_to(RELEASE_BUNDLE_DIR)
            archive.write(
                file_path,
                arcname=(Path(RELEASE_BUNDLE_DIR.name) / relative_path).as_posix(),
            )
    print(f"  [OK] Created {zip_path} ({zip_path.stat().st_size / 1024 / 1024:.2f} MB)")
    return zip_path


def _assert_tag_does_not_exist(tag_name: str) -> None:
    local = subprocess.run(
        ["git", "rev-parse", "--verify", f"refs/tags/{tag_name}"],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
    )
    if local.returncode == 0:
        raise RuntimeError(f"Tag {tag_name} already exists locally; refusing to overwrite it.")

    remote = subprocess.run(
        ["git", "ls-remote", "--exit-code", "--tags", "origin", f"refs/tags/{tag_name}"],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
    )
    if remote.returncode == 0:
        raise RuntimeError(f"Tag {tag_name} already exists on origin; refusing to overwrite it.")


def create_release_commit_and_tag(new_version: str) -> tuple[str, str]:
    """Stage changes, commit when needed, and create a non-overwriting tag."""

    clean_version = new_version.lstrip("v")
    tag_name = f"v{clean_version}"
    _assert_tag_does_not_exist(tag_name)
    _run_git("add", "-A")
    staged = _run_git("diff", "--cached", "--name-only", capture_output=True).stdout.splitlines()
    for path in staged:
        normalized = path.replace("\\", "/")
        if any(part in normalized for part in SENSITIVE_PATH_PARTS):
            _run_git("reset", "--", path)
            raise RuntimeError(f"Refusing to stage sensitive release path: {path}")
    if not staged:
        if get_current_version() != new_version:
            raise RuntimeError("No staged changes are available for the release commit.")
        print("  [OK] Release version is already committed; tagging the current HEAD.")
        commit_hash = _run_git("rev-parse", "HEAD", capture_output=True).stdout.strip()
        _run_git("tag", "-a", tag_name, commit_hash, "-m", f"Release {tag_name}")
        return commit_hash, tag_name

    print("\n[5/6] Creating release commit and tag...")
    _run_git("commit", "-m", f"release: {tag_name}")
    commit_hash = _run_git("rev-parse", "HEAD", capture_output=True).stdout.strip()
    _run_git("tag", "-a", tag_name, commit_hash, "-m", f"Release {tag_name}")
    return commit_hash, tag_name


def push_release(commit_hash: str, tag_name: str) -> None:
    current_branch = _run_git("branch", "--show-current", capture_output=True).stdout.strip()
    if not current_branch:
        raise RuntimeError("Release must run from a named branch, not detached HEAD.")
    actual_commit = _run_git("rev-parse", "HEAD", capture_output=True).stdout.strip()
    if actual_commit != commit_hash:
        raise RuntimeError("HEAD changed before push; refusing to publish a different commit.")
    subprocess.run(["git", "push", "origin", current_branch], cwd=ROOT_DIR, check=True)
    # No --force: an existing remote tag is a hard failure instead of an
    # overwrite. The tag points to the explicit commit created above.
    subprocess.run(["git", "push", "origin", tag_name], cwd=ROOT_DIR, check=True)


def git_commit_tag_push(new_version: str) -> None:
    """Compatibility entry point: create, then safely push a release."""

    commit_hash, tag_name = create_release_commit_and_tag(new_version)
    push_release(commit_hash, tag_name)


def publish_github_release(new_version: str, zip_path: Path) -> None:
    """Hand the release to the tag-triggered GitHub Actions workflow.

    The workflow is the single publisher. Creating a release locally after
    pushing the tag would race the workflow and could create a duplicate.
    """

    tag_name = f"v{new_version}"
    release_notes_path = RELEASE_NOTES_DIR / f"{tag_name}.md"
    print("\n[6/6] Handing release publication to GitHub Actions...")
    print(f"  [OK] Tag {tag_name} pushed; workflow will publish {zip_path.name}.")
    if release_notes_path.is_file():
        print(f"  [OK] Project release notes: {release_notes_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Maple Classic Auto Reporter Release Tool")
    parser.add_argument("--type", choices=["major", "minor", "patch"], help="Bump type")
    parser.add_argument("--version", help="Explicit version string (e.g. 1.0.0)")
    parser.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompt")
    args = parser.parse_args()

    ensure_clean_worktree()
    current_version = get_current_version()
    print(f"=== Maple Classic Auto Reporter Release Tool ===\nCurrent version: v{current_version}")

    if args.version:
        new_version = args.version.lstrip("v")
    elif args.type:
        new_version = calculate_next_version(current_version, args.type)
    elif args.yes:
        new_version = calculate_next_version(current_version, "minor")
    else:
        choice = input("Choose bump type: 1=major, 2=minor, 3=patch, 4=custom [2]: ").strip() or "2"
        if choice == "1":
            new_version = calculate_next_version(current_version, "major")
        elif choice == "2":
            new_version = calculate_next_version(current_version, "minor")
        elif choice == "3":
            new_version = calculate_next_version(current_version, "patch")
        elif choice == "4":
            new_version = input("Enter custom version (e.g. 1.0.0): ").strip().lstrip("v")
        else:
            raise SystemExit("Invalid choice.")
    parse_semver(new_version)

    print(f"\n>>> Target Release Version: v{new_version} <<<")
    if not (args.version or args.type or args.yes):
        if input("Proceed with release? (y/N): ").strip().lower() != "y":
            raise SystemExit("Release canceled.")

    update_all_version_files(new_version)
    refresh_lockfile()
    run_unit_tests()
    commit_hash, tag_name = create_release_commit_and_tag(new_version)
    build_executable(expected_commit=commit_hash)
    zip_path = zip_release(new_version)
    push_release(commit_hash, tag_name)
    publish_github_release(new_version, zip_path)
    print(f"\nSUCCESS! Release tag {tag_name} pushed; GitHub Actions is publishing it.")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError) as error:
        print(f"[ERROR] {error}", file=sys.stderr)
        raise SystemExit(1)
