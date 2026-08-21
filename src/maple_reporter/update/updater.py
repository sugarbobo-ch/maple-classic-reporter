"""Transactional application of a downloaded update package.

This module intentionally uses only the Python standard library.  The small
updater executable can therefore be built independently of the 400 MiB main
bundle and can replace files while the main process is stopped.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
import zipfile
from pathlib import Path
from typing import Any

from maple_reporter.update.manifest import safe_relative_path, sha256_file

LOGGER = logging.getLogger(__name__)
_MAX_MEMBER_SIZE = 2 * 1024 * 1024 * 1024


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def _wait_for_pid(pid: int, timeout: float = 90.0) -> bool:
    """Wait for a Windows process without importing psutil."""

    if pid <= 0 or pid == os.getpid():
        return True
    if os.name == "nt":
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(0x00100000 | 0x00000100, False, pid)
            if not handle:
                return True
            try:
                result = kernel32.WaitForSingleObject(handle, int(timeout * 1000))
                return result == 0
            finally:
                kernel32.CloseHandle(handle)
        except Exception:
            pass

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except (OSError, ProcessLookupError):
            return True
        time.sleep(0.2)
    return False


def _safe_zip_members(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    members = []
    total_size = 0
    for member in archive.infolist():
        if member.is_dir():
            continue
        safe_relative_path(member.filename)
        if member.file_size > _MAX_MEMBER_SIZE:
            raise ValueError(f"Update member is too large: {member.filename}")
        total_size += member.file_size
        if total_size > 8 * 1024 * 1024 * 1024:
            raise ValueError("Update archive is too large")
        # Reject Unix symlinks and other non-regular entries.
        if (member.external_attr >> 16) & 0o170000 == 0o120000:
            raise ValueError(f"Update archive contains a symlink: {member.filename}")
        members.append(member)
    return members


def _extract_safe(archive: zipfile.ZipFile, destination: Path) -> None:
    members = _safe_zip_members(archive)
    destination.mkdir(parents=True, exist_ok=True)
    for member in members:
        relative = Path(safe_relative_path(member.filename))
        target = (destination / relative).resolve()
        if destination.resolve() not in target.parents:
            raise ValueError(f"Archive path escaped staging directory: {member.filename}")
        target.parent.mkdir(parents=True, exist_ok=True)
        with archive.open(member, "r") as source, target.open("wb") as output:
            shutil.copyfileobj(source, output, length=1024 * 1024)


def _copy_backup(source: Path, backup_root: Path, relative: str) -> bool:
    target = backup_root / Path(relative)
    if not source.exists():
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return True


def _restore_patch(install_dir: Path, backup_dir: Path, records: list[dict[str, Any]]) -> None:
    for record in reversed(records):
        relative = safe_relative_path(record["path"])
        target = install_dir / Path(relative)
        if record.get("existed"):
            source = backup_dir / Path(relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            if source.is_file():
                shutil.copy2(source, target)
        elif target.exists():
            target.unlink()


def _verify_expected_files(install_dir: Path, expected: dict[str, str]) -> None:
    for relative, expected_hash in expected.items():
        safe = safe_relative_path(relative)
        path = install_dir / Path(safe)
        if not path.is_file() or sha256_file(path).lower() != str(expected_hash).lower():
            raise ValueError(f"Updated file failed verification: {relative}")


def _apply_delta(archive_path: Path, install_dir: Path, transaction_dir: Path) -> Path:
    with zipfile.ZipFile(archive_path) as archive:
        _safe_zip_members(archive)
        try:
            patch = json.loads(archive.read("patch.json"))
        except KeyError as error:
            raise ValueError("Delta archive is missing patch.json") from error
        if not isinstance(patch, dict) or patch.get("kind") != "delta":
            raise ValueError("Invalid delta patch metadata")
        files = patch.get("files", {})
        deletes = patch.get("delete", [])
        expected = patch.get("target_files", {})
        if not isinstance(files, dict) or not isinstance(deletes, list):
            raise ValueError("Invalid delta patch file list")

        staging = transaction_dir / "staging"
        backup = transaction_dir / "backup"
        staging.mkdir(parents=True, exist_ok=True)
        backup.mkdir(parents=True, exist_ok=True)
        records: list[dict[str, Any]] = []
        _write_json(transaction_dir / "backup-index.json", {"records": records})

        for relative, expected_hash in files.items():
            safe = safe_relative_path(relative)
            target = install_dir / Path(safe)
            staged = staging / Path(safe)
            try:
                member = archive.getinfo(f"files/{safe}")
            except KeyError as error:
                raise ValueError(f"Delta archive is missing {safe}") from error
            staged.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member, "r") as source, staged.open("wb") as output:
                shutil.copyfileobj(source, output, length=1024 * 1024)
            if sha256_file(staged).lower() != str(expected_hash).lower():
                raise ValueError(f"Delta file failed verification: {safe}")
            existed = _copy_backup(target, backup, safe)
            records.append({"path": safe, "existed": existed})
            _write_json(transaction_dir / "backup-index.json", {"records": records})

        for relative in deletes:
            safe = safe_relative_path(relative)
            target = install_dir / Path(safe)
            existed = _copy_backup(target, backup, safe)
            records.append({"path": safe, "existed": existed})
            _write_json(transaction_dir / "backup-index.json", {"records": records})

        _write_json(transaction_dir / "state.json", {"phase": "applying", "kind": "delta", "install_dir": str(install_dir)})
        for relative in files:
            safe = safe_relative_path(relative)
            target = install_dir / Path(safe)
            staged = staging / Path(safe)
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(staged, target)
        for relative in deletes:
            safe = safe_relative_path(relative)
            target = install_dir / Path(safe)
            if target.exists():
                target.unlink()
            if target.exists():
                raise ValueError(f"Deleted file is still present after verification: {safe}")
        _verify_expected_files(install_dir, expected if isinstance(expected, dict) else {})
        _write_json(transaction_dir / "state.json", {"phase": "applied", "kind": "delta", "install_dir": str(install_dir)})
        return backup


def _safe_move_directory(src: Path, dst: Path, retries: int = 12, delay: float = 0.4) -> None:
    """Safely move a directory on Windows with retry to handle brief file locks."""
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            if dst.exists():
                shutil.rmtree(dst, ignore_errors=True)
            shutil.move(str(src), str(dst))
            return
        except (PermissionError, OSError) as exc:
            last_error = exc
            time.sleep(delay)
    # Fallback to copytree with overwrite + rmtree
    try:
        shutil.copytree(str(src), str(dst), dirs_exist_ok=True)
        shutil.rmtree(str(src), ignore_errors=True)
        return
    except Exception as exc:
        LOGGER.warning("copytree fallback failed: %s", exc)
    if last_error:
        raise last_error


def _apply_full(archive_path: Path, install_dir: Path, transaction_dir: Path) -> Path:
    staging_parent = transaction_dir / "full-staging"
    staging_parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path) as archive:
        _extract_safe(archive, staging_parent)
    staged_bundle = staging_parent / install_dir.name
    if not staged_bundle.is_dir() or not (staged_bundle / "MapleClassicReporter.exe").is_file():
        staged_bundle = staging_parent / "MapleClassicReporter"
    if not staged_bundle.is_dir() or not (staged_bundle / "MapleClassicReporter.exe").is_file():
        if (staging_parent / "MapleClassicReporter.exe").is_file():
            staged_bundle = staging_parent
    if not staged_bundle.is_dir() or not (staged_bundle / "MapleClassicReporter.exe").is_file():
        raise ValueError("Full update archive does not contain a valid MapleClassicReporter bundle")
    bundle_manifest = staging_parent / "bundle-manifest-v1.json"
    if bundle_manifest.is_file():
        metadata = _read_json(bundle_manifest)
        files = metadata.get("files", {})
        if not isinstance(files, dict):
            raise ValueError("Full update bundle manifest is invalid")
        _verify_expected_files(
            staged_bundle,
            {relative: info["sha256"] for relative, info in files.items() if isinstance(info, dict) and "sha256" in info},
        )
    backup = install_dir.parent / f".{install_dir.name}.rollback-{transaction_dir.name}"
    if backup.exists():
        shutil.rmtree(backup, ignore_errors=True)
    _write_json(transaction_dir / "state.json", {"phase": "ready-to-swap", "kind": "full", "backup": str(backup), "install_dir": str(install_dir)})
    _safe_move_directory(install_dir, backup)
    try:
        _safe_move_directory(staged_bundle, install_dir)
    except Exception:
        if backup.exists() and not install_dir.exists():
            _safe_move_directory(backup, install_dir)
        raise
    _write_json(transaction_dir / "state.json", {"phase": "applied", "kind": "full", "backup": str(backup), "install_dir": str(install_dir)})
    return backup


def _launch(executable: Path, token: str) -> subprocess.Popen[Any]:
    return subprocess.Popen(
        [str(executable), "--post-update", f"--update-token={token}"],
        cwd=str(executable.parent),
        close_fds=True,
    )


class UpdateProgressUI:
    """Lightweight Windows progress dialog with project camera icon."""

    def __init__(self, target_version: str = "", install_dir: Path | None = None) -> None:
        self._root = None
        try:
            import tkinter as tk
            from tkinter import ttk

            root = tk.Tk()
            root.title("新楓之谷：經典版 - 套用更新")
            root.geometry("380x130")
            root.resizable(False, False)
            root.attributes("-topmost", True)

            # Set camera icon if available
            if install_dir:
                icon_path = install_dir / "assets" / "icon.ico"
                if not icon_path.is_file():
                    icon_path = install_dir / "_internal" / "assets" / "icon.ico"
                if icon_path.is_file():
                    try:
                        root.iconbitmap(str(icon_path))
                    except Exception:
                        pass

            root.update_idletasks()
            width = root.winfo_width()
            height = root.winfo_height()
            x = (root.winfo_screenwidth() // 2) - (width // 2)
            y = (root.winfo_screenheight() // 2) - (height // 2)
            root.geometry(f"+{x}+{y}")

            frame = ttk.Frame(root, padding="16 16 16 16")
            frame.pack(fill="both", expand=True)

            title_text = f"正在套用新版本 v{target_version}…" if target_version else "正在套用更新…"
            lbl = ttk.Label(frame, text=title_text, font=("Microsoft JhengHei UI", 10, "bold"))
            lbl.pack(anchor="w", pady=(0, 8))

            progress = ttk.Progressbar(frame, mode="indeterminate", length=340)
            progress.pack(fill="x", pady=(0, 4))
            progress.start(15)

            self._root = root
            self._root.update()
        except Exception:
            self._root = None

    def tick(self) -> None:
        if self._root:
            try:
                self._root.update()
            except Exception:
                pass

    def close(self) -> None:
        if self._root:
            try:
                self._root.destroy()
            except Exception:
                pass
            self._root = None


def apply_update(
    *,
    package_path: Path,
    install_dir: Path,
    update_dir: Path,
    pid: int = 0,
    target_version: str = "",
    timeout: float = 90.0,
) -> bool:
    """Apply a full ZIP or delta package and verify a clean relaunch."""

    log_path = update_dir / "updater.log"
    def _log(msg: str) -> None:
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
        except Exception:
            pass

    _log(f"Starting update: package={package_path}, install_dir={install_dir}, pid={pid}, target={target_version}")
    ui = UpdateProgressUI(target_version=target_version, install_dir=install_dir)
    try:
        package_path = package_path.resolve()
        install_dir = install_dir.resolve()
        update_dir.mkdir(parents=True, exist_ok=True)
        token = uuid.uuid4().hex
        transaction = update_dir / f"transaction-{token}"
        transaction.mkdir(parents=True, exist_ok=True)
        _write_json(
            transaction / "state.json",
            {"phase": "waiting", "package": str(package_path), "install_dir": str(install_dir), "target_version": target_version},
        )
        _log("Waiting for main process to exit...")
        if not _wait_for_pid(pid, timeout=timeout):
            _log("Timeout waiting for main process exit")
            raise TimeoutError("Main application did not exit before the update timeout")

        _log("Main process exited. Swapping files...")
        ui.tick()
        backup: Path | None = None
        kind = "full"
        try:
            with zipfile.ZipFile(package_path) as archive:
                names = set(archive.namelist())
            kind = "delta" if "patch.json" in names else "full"
            ui.tick()
            backup = _apply_delta(package_path, install_dir, transaction) if kind == "delta" else _apply_full(package_path, install_dir, transaction)
            ui.tick()
            _log(f"Files replaced successfully ({kind}). Launching updated application...")
            executable = install_dir / "MapleClassicReporter.exe"
            if not executable.is_file():
                _log("Updated executable is missing!")
                raise ValueError("Updated executable is missing")
            marker = update_dir / f"success-{token}.json"
            process = _launch(executable, token)
            _log(f"New process launched, waiting for confirmation token {token}...")
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                ui.tick()
                if marker.is_file():
                    _log("Confirmed new process is running successfully!")
                    _write_json(transaction / "state.json", {"phase": "confirmed", "kind": kind, "target_version": target_version})
                    if backup and backup.exists():
                        shutil.rmtree(backup, ignore_errors=True)
                    try:
                        marker.unlink(missing_ok=True)
                    except Exception:
                        pass
                    try:
                        (update_dir / "pending-update.json").unlink(missing_ok=True)
                    except Exception:
                        pass
                    for helper_copy in update_dir.glob("MapleClassicReporterUpdater-*.exe"):
                        try:
                            if helper_copy.resolve() != Path(sys.executable).resolve():
                                helper_copy.unlink(missing_ok=True)
                        except Exception:
                            pass
                    shutil.rmtree(transaction, ignore_errors=True)
                    try:
                        package_path.unlink(missing_ok=True)
                    except Exception:
                        pass
                    return True
                if process.poll() is not None and process.returncode not in (0, None):
                    _log(f"New process exited early with code {process.returncode}")
                    break
                time.sleep(0.25)
            _log("Timeout or early exit waiting for new process confirmation")
            raise TimeoutError("Updated application did not report a healthy startup")
        except Exception as err:
            _log(f"Exception during update application: {err}")
            LOGGER.exception("Update transaction failed; attempting rollback")
            try:
                if kind == "full" and backup and backup.exists():
                    if install_dir.exists():
                        shutil.rmtree(install_dir, ignore_errors=True)
                    _safe_move_directory(backup, install_dir)
                elif kind == "delta":
                    index_path = transaction / "backup-index.json"
                    if index_path.is_file():
                        records = _read_json(index_path).get("records", [])
                        _restore_patch(install_dir, transaction / "backup", records)
            finally:
                shutil.rmtree(transaction, ignore_errors=True)
            raise
    finally:
        ui.close()


def recover_interrupted_update(update_dir: Path) -> None:
    """Recover a transaction left behind by a crash or forced shutdown."""

    if not update_dir.is_dir():
        return
    for transaction in update_dir.glob("transaction-*"):
        state_path = transaction / "state.json"
        if not state_path.is_file():
            shutil.rmtree(transaction, ignore_errors=True)
            continue
        try:
            state = _read_json(state_path)
        except Exception:
            shutil.rmtree(transaction, ignore_errors=True)
            continue
        phase = state.get("phase")
        if phase == "confirmed":
            shutil.rmtree(transaction, ignore_errors=True)
            continue
        if phase not in {"applying", "applied", "ready-to-swap"}:
            continue
        try:
            install_dir = Path(state.get("install_dir") or "").resolve()
            if state.get("kind") == "full":
                backup_value = state.get("backup")
                backup = Path(backup_value).resolve() if backup_value else None
                if backup and backup.is_dir():
                    if install_dir.exists():
                        shutil.rmtree(install_dir, ignore_errors=True)
                    os.replace(backup, install_dir)
            elif state.get("kind") == "delta":
                index_path = transaction / "backup-index.json"
                if index_path.is_file():
                    records = _read_json(index_path).get("records", [])
                    _restore_patch(install_dir, transaction / "backup", records)
            shutil.rmtree(transaction, ignore_errors=True)
        except Exception:
            LOGGER.exception("Unable to recover interrupted update transaction: %s", transaction)
    # A normal launch after recovery must not keep pointing at a package that
    # has already been rolled back or discarded.
    if not list(update_dir.glob("transaction-*")):
        (update_dir / "pending-update.json").unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Maple Classic Reporter portable updater")
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--install-dir", type=Path, required=True)
    parser.add_argument("--update-dir", type=Path, required=True)
    parser.add_argument("--pid", type=int, default=0)
    parser.add_argument("--target-version", default="")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [updater] %(message)s")
    try:
        return 0 if apply_update(
            package_path=args.package,
            install_dir=args.install_dir,
            update_dir=args.update_dir,
            pid=args.pid,
            target_version=args.target_version,
        ) else 1
    except Exception as error:
        LOGGER.error("Update failed: %s", error)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
