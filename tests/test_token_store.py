import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from maple_reporter.gdrive import drive_service
from maple_reporter.gdrive.token_store import DPAPI_HEADER, ProtectedTokenStore
from maple_reporter.utils import config


class TestProtectedTokenStore(unittest.TestCase):
    def test_authentication_refreshes_credentials_that_expire_while_running(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            token_path = Path(temp_dir) / "oauth_token.dpapi"
            credentials = MagicMock()
            credentials.expired = False
            credentials.valid = True
            credentials.refresh_token = "test-only-refresh-token"
            credentials.to_json.return_value = '{"token":"refreshed-test-token"}'

            with patch.object(
                drive_service.GoogleDriveManager,
                "_load_credentials",
                return_value=True,
            ), patch.object(drive_service, "build", return_value=object()):
                manager = drive_service.GoogleDriveManager(token_path)

            manager.creds = credentials
            manager.service = object()
            credentials.expired = True
            credentials.valid = False

            def mark_refreshed(_request):
                credentials.expired = False
                credentials.valid = True

            credentials.refresh.side_effect = mark_refreshed

            self.assertTrue(manager.is_authenticated())
            credentials.refresh.assert_called_once()
            self.assertTrue(token_path.is_file())

    def test_authentication_retries_after_startup_refresh_failure(self):
        credentials = MagicMock()
        credentials.expired = True
        credentials.valid = False
        credentials.refresh_token = "test-only-refresh-token"
        credentials.to_json.return_value = '{"token":"refreshed-test-token"}'

        def mark_refreshed(_request):
            credentials.expired = False
            credentials.valid = True

        refresh_attempts = 0

        def refresh_with_transient_failure(request):
            nonlocal refresh_attempts
            refresh_attempts += 1
            if refresh_attempts == 1:
                raise RuntimeError("temporary network failure")
            mark_refreshed(request)

        credentials.refresh.side_effect = refresh_with_transient_failure

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(
                drive_service.GoogleDriveManager,
                "_load_token_info",
                return_value={"token": "expired-test-token"},
            ), patch.object(
                drive_service.Credentials,
                "from_authorized_user_info",
                return_value=credentials,
            ), patch.object(drive_service, "build", return_value=object()):
                manager = drive_service.GoogleDriveManager(
                    Path(temp_dir) / "oauth_token.dpapi"
                )

            self.assertTrue(manager.is_authenticated())
            self.assertEqual(credentials.refresh.call_count, 2)

    def test_round_trip_protects_token_at_rest_on_windows(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            token_path = Path(temp_dir) / "oauth_token.dpapi"
            store = ProtectedTokenStore(token_path)
            payload = {
                "token": "test-only-access-token",
                "refresh_token": "test-only-refresh-token",
            }

            store.save(payload)
            raw = token_path.read_bytes()

            if os.name == "nt":
                self.assertTrue(raw.startswith(DPAPI_HEADER))
                self.assertNotIn(b"test-only-refresh-token", raw)
            self.assertEqual(store.load(), payload)

    def test_default_token_path_uses_local_app_data(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(
            os.environ, {"LOCALAPPDATA": temp_dir}
        ):
            self.assertEqual(
                config.get_default_token_path(),
                Path(temp_dir) / "MapleClassicReporter" / "oauth_token.dpapi",
            )

    def test_legacy_plaintext_token_is_migrated_and_removed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            legacy_path = temp_root / "data" / "config" / "token.json"
            secure_path = temp_root / "appdata" / "oauth_token.dpapi"
            legacy_path.parent.mkdir(parents=True)
            legacy_raw = b'{"token":"legacy-test-token"}'
            legacy_path.write_bytes(legacy_raw)

            fake_credentials = MagicMock()
            fake_credentials.expired = False
            fake_credentials.valid = True
            fake_credentials.to_json.return_value = (
                '{"token":"migrated-test-token"}'
            )

            with patch.object(
                drive_service, "CONFIG_DIR", legacy_path.parent
            ), patch.object(
                drive_service, "get_default_token_path", return_value=secure_path
            ), patch.object(
                drive_service.Credentials,
                "from_authorized_user_info",
                return_value=fake_credentials,
            ) as from_info, patch.object(
                drive_service, "build", return_value=object()
            ):
                manager = drive_service.GoogleDriveManager()

            self.assertTrue(manager.is_authenticated())
            self.assertFalse(legacy_path.exists())
            self.assertTrue(secure_path.is_file())
            from_info.assert_called_once_with(
                {"token": "legacy-test-token"}, drive_service.SCOPES
            )
            migrated_raw = secure_path.read_bytes()
            if os.name == "nt":
                self.assertTrue(migrated_raw.startswith(DPAPI_HEADER))
                self.assertNotIn(b"migrated-test-token", migrated_raw)
            else:
                self.assertNotEqual(migrated_raw, legacy_raw)


if __name__ == "__main__":
    unittest.main()
