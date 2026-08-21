from __future__ import annotations

import hashlib
import json
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from maple_reporter.update.manifest import SemVer, safe_relative_path
from maple_reporter.update.service import UpdateService, UpdateState
from maple_reporter.update.updater import _apply_delta, apply_update


class _Response:
    def __init__(self, payload=None, chunks=None, status_code=200, headers=None):
        self._payload = payload
        self._chunks = chunks or []
        self.status_code = status_code
        self.headers = headers or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size=0):
        yield from self._chunks


class _Session:
    def __init__(self, releases, download_url, data):
        self.releases = releases
        self.download_url = download_url
        self.data = data

    def get(self, url, **kwargs):
        if url.startswith("https://api.github.com"):
            return _Response(self.releases)
        return _Response(
            chunks=[self.data[:3], self.data[3:]],
            headers={"Content-Length": str(len(self.data))},
        )


class UpdateTests(unittest.TestCase):
    def test_semver_prerelease_order_and_safe_paths(self):
        self.assertLess(SemVer.parse("2.0.0-pre"), SemVer.parse("2.0.0"))
        self.assertGreater(SemVer.parse("2.0.0-pre.2"), SemVer.parse("2.0.0-pre"))
        self.assertEqual(safe_relative_path(r"web\dist\index.html"), "web/dist/index.html")
        with self.assertRaises(ValueError):
            safe_relative_path("../../outside.txt")
        with self.assertRaises(ValueError):
            safe_relative_path("C:/outside.txt")

    def test_service_checks_and_downloads_full_asset(self):
        payload = b"portable update payload"
        digest = hashlib.sha256(payload).hexdigest()
        releases = [
            {
                "tag_name": "v2.0.0",
                "prerelease": False,
                "html_url": "https://github.com/sugarbobo-ch/maple-classic-reporter/releases/tag/v2.0.0",
                "body": "Fixes",
                "assets": [
                    {
                        "name": "MapleClassicReporter-v2.0.0-windows-x64.zip",
                        "browser_download_url": "https://github.com/download/update.zip",
                        "size": len(payload),
                        "digest": f"sha256:{digest}",
                    }
                ],
            }
        ]
        events = []
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            service = UpdateService(
                emit_event=lambda event, data: events.append((event, data)),
                get_config=lambda: {"auto_update_enabled": False, "update_channel": "stable"},
                is_busy=lambda: False,
                session=_Session(releases, "https://github.com/download/update.zip", payload),
                install_dir=root / "MapleClassicReporter",
                update_dir=root / "updates",
            )
            self.assertTrue(service.start_check(force=True))
            deadline = time.time() + 3
            while time.time() < deadline and service.status()["state"] in {
                UpdateState.IDLE.value,
                UpdateState.CHECKING.value,
            }:
                time.sleep(0.01)
            self.assertEqual(service.status()["state"], UpdateState.AVAILABLE.value)
            self.assertTrue(service.start_download())
            deadline = time.time() + 3
            while time.time() < deadline and service.status()["state"] not in {
                UpdateState.READY.value,
                UpdateState.ERROR.value,
            }:
                time.sleep(0.01)
            self.assertEqual(service.status()["state"], UpdateState.READY.value)
            self.assertEqual(service.status()["progress_percent"], 100)
            self.assertTrue(any(event == "UPDATE_STATUS" for event, _ in events))
            service.shutdown()

    def test_delta_application_changes_and_deletes_only_managed_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            install = root / "MapleClassicReporter"
            install.mkdir()
            (install / "MapleClassicReporter.exe").write_bytes(b"old exe")
            (install / "keep.txt").write_bytes(b"keep")
            (install / "remove.txt").write_bytes(b"remove")
            changed = b"new exe"
            expected = {
                "MapleClassicReporter.exe": hashlib.sha256(changed).hexdigest(),
                "keep.txt": hashlib.sha256(b"keep").hexdigest(),
            }
            archive_path = root / "patch.zip"
            patch_metadata = {
                "kind": "delta",
                "from_version": "1.0.0",
                "to_version": "1.1.0",
                "files": {"MapleClassicReporter.exe": expected["MapleClassicReporter.exe"]},
                "delete": ["remove.txt"],
                "target_files": expected,
            }
            with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("patch.json", json.dumps(patch_metadata))
                archive.writestr("files/MapleClassicReporter.exe", changed)
            backup = _apply_delta(archive_path, install, root / "transaction")
            self.assertEqual((install / "MapleClassicReporter.exe").read_bytes(), changed)
            self.assertFalse((install / "remove.txt").exists())
            self.assertTrue((install / "keep.txt").exists())
            self.assertEqual((backup / "MapleClassicReporter.exe").read_bytes(), b"old exe")

    def test_delta_rejects_zip_slip(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive_path = root / "bad.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("../outside.txt", b"bad")
                archive.writestr("patch.json", json.dumps({"kind": "delta", "files": {}, "delete": []}))
            with self.assertRaises(ValueError):
                _apply_delta(archive_path, root / "install", root / "transaction")

    def test_multi_version_delta_chain_is_composed_into_final_patch(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            install = root / "MapleClassicReporter"
            install.mkdir()
            (install / "MapleClassicReporter.exe").write_bytes(b"v0")

            def make_patch(path: Path, from_version: str, to_version: str, payload: bytes):
                digest = hashlib.sha256(payload).hexdigest()
                metadata = {
                    "kind": "delta",
                    "from_version": from_version,
                    "to_version": to_version,
                    "files": {"MapleClassicReporter.exe": digest},
                    "delete": [],
                    "target_files": {"MapleClassicReporter.exe": digest},
                }
                with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
                    archive.writestr("patch.json", json.dumps(metadata))
                    archive.writestr("files/MapleClassicReporter.exe", payload)

            first = root / "first.patch.zip"
            second = root / "second.patch.zip"
            make_patch(first, "1.0.0", "1.1.0", b"v1")
            make_patch(second, "1.1.0", "1.2.0", b"v2")
            service = UpdateService(
                emit_event=lambda *_: None,
                get_config=lambda: {"auto_update_enabled": False},
                is_busy=lambda: False,
                install_dir=install,
                update_dir=root / "updates",
            )
            composed = service._compose_delta_chain([first, second], "1.2.0")
            _apply_delta(composed, install, root / "transaction")
            self.assertEqual((install / "MapleClassicReporter.exe").read_bytes(), b"v2")
            service.shutdown()

    def test_full_update_swaps_bundle_and_cleans_backup_after_health_marker(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            install = root / "MapleClassicReporter"
            install.mkdir()
            (install / "MapleClassicReporter.exe").write_bytes(b"old")
            package = root / "full.zip"
            with zipfile.ZipFile(package, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("MapleClassicReporter/MapleClassicReporter.exe", b"new")
                archive.writestr("MapleClassicReporter/MapleClassicReporterUpdater.exe", b"updater")

            update_dir = root / "updates"

            class Process:
                def poll(self):
                    return None

            def fake_launch(executable, token):
                (update_dir / f"success-{token}.json").parent.mkdir(parents=True, exist_ok=True)
                (update_dir / f"success-{token}.json").write_text('{"ok": true}')
                return Process()

            with patch("maple_reporter.update.updater._launch", side_effect=fake_launch):
                self.assertTrue(
                    apply_update(
                        package_path=package,
                        install_dir=install,
                        update_dir=update_dir,
                        timeout=1,
                    )
                )
            self.assertEqual((install / "MapleClassicReporter.exe").read_bytes(), b"new")
            self.assertFalse(package.exists())
            self.assertFalse(list(root.glob(".MapleClassicReporter.rollback-*")))

    def test_full_update_rolls_back_when_new_process_never_reports_health(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            install = root / "MapleClassicReporter"
            install.mkdir()
            (install / "MapleClassicReporter.exe").write_bytes(b"old")
            package = root / "full.zip"
            with zipfile.ZipFile(package, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("MapleClassicReporter/MapleClassicReporter.exe", b"new")

            class Process:
                returncode = 1

                def poll(self):
                    return self.returncode

            with patch("maple_reporter.update.updater._launch", return_value=Process()):
                with self.assertRaises(TimeoutError):
                    apply_update(
                        package_path=package,
                        install_dir=install,
                        update_dir=root / "updates",
                        timeout=0.1,
                    )
            self.assertEqual((install / "MapleClassicReporter.exe").read_bytes(), b"old")


if __name__ == "__main__":
    unittest.main()
