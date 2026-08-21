import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from maple_reporter.gdrive import drive_service


class TestGoogleDriveOAuth(unittest.TestCase):
    def test_oauth_success_page_is_styled_traditional_chinese_html(self):
        page = drive_service.OAuthSuccessPage()
        response = {}

        def start_response(status, headers):
            response["status"] = status
            response["headers"] = dict(headers)

        body = b"".join(
            page(
                {
                    "wsgi.url_scheme": "http",
                    "SERVER_NAME": "localhost",
                    "SERVER_PORT": "65110",
                    "SCRIPT_NAME": "",
                    "PATH_INFO": "/",
                    "QUERY_STRING": "code=test&state=test",
                },
                start_response,
            )
        ).decode("utf-8")

        self.assertEqual(response["status"], "200 OK")
        self.assertEqual(
            response["headers"]["Content-Type"], "text/html; charset=utf-8"
        )
        self.assertEqual(response["headers"]["Cache-Control"], "no-store")
        self.assertIn('lang="zh-Hant"', body)
        self.assertIn("Google 帳號登入完成", body)
        self.assertIn("Google 帳號已登入", body)
        self.assertIn("localhost", body)
        self.assertIn('<svg class="result-icon"', body)
        self.assertIn('stroke-linejoin="round"', body)
        self.assertNotIn("✓", body)

    def test_oauth_failure_page_is_chinese_and_recommends_retry(self):
        flow = MagicMock()
        flow.fetch_token.side_effect = ValueError("access_denied")
        page = drive_service.OAuthSuccessPage(flow)
        response = {}

        body = b"".join(
            page(
                {
                    "wsgi.url_scheme": "http",
                    "SERVER_NAME": "localhost",
                    "SERVER_PORT": "65110",
                    "SCRIPT_NAME": "",
                    "PATH_INFO": "/",
                    "QUERY_STRING": "error=access_denied&state=test",
                },
                lambda status, headers: response.update(
                    status=status, headers=dict(headers)
                ),
            )
        ).decode("utf-8")

        self.assertEqual(response["status"], "400 Bad Request")
        self.assertIn("Google 帳號登入失敗", body)
        self.assertIn("尚未登入 Google 帳號", body)
        self.assertIn("返回應用程式後重新登入", body)
        self.assertNotIn("access_denied", body)
        self.assertIsInstance(page.error, ValueError)

    def test_local_oauth_server_fetches_token_after_rendering_success_page(self):
        fake_flow = MagicMock()
        fake_flow.authorization_url.return_value = ("https://accounts.example/auth", "state")
        fake_flow.credentials = object()
        fake_server = MagicMock()
        fake_server.server_port = 65110
        captured = {}

        def make_server(_host, _port, app, server_class):
            captured["app"] = app
            captured["server_class"] = server_class
            return fake_server

        def handle_request():
            captured["app"](
                {
                    "wsgi.url_scheme": "http",
                    "SERVER_NAME": "localhost",
                    "SERVER_PORT": "65110",
                    "SCRIPT_NAME": "",
                    "PATH_INFO": "/",
                    "QUERY_STRING": "code=test&state=state",
                },
                lambda _status, _headers: None,
            )

        fake_server.handle_request.side_effect = handle_request
        with patch.object(
            drive_service.wsgiref.simple_server,
            "make_server",
            side_effect=make_server,
        ), patch.object(drive_service.webbrowser, "open") as open_browser:
            credentials = drive_service.run_local_oauth_server(fake_flow)

        self.assertIs(credentials, fake_flow.credentials)
        self.assertEqual(fake_flow.redirect_uri, "http://localhost:65110/")
        open_browser.assert_called_once_with(
            "https://accounts.example/auth", new=1, autoraise=True
        )
        fake_flow.fetch_token.assert_called_once_with(
            authorization_response="https://localhost:65110/?code=test&state=state"
        )
        fake_server.server_close.assert_called_once_with()

    def test_scope_is_limited_to_drive_file(self):
        self.assertEqual(
            drive_service.SCOPES,
            ["https://www.googleapis.com/auth/drive.file"],
        )

    def test_frozen_build_resolves_embedded_resource(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            resource_path = Path(temp_dir) / "google_oauth_client.json"
            resource_path.write_text("{}", encoding="utf-8")

            with patch.object(drive_service.sys, "frozen", True, create=True), patch.object(
                drive_service.sys, "_MEIPASS", temp_dir, create=True
            ):
                self.assertEqual(
                    drive_service.resolve_oauth_client_config_path(), resource_path
                )

    def test_source_environment_variable_overrides_release_candidates(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            override_path = Path(temp_dir) / "oauth-client.json"
            override_path.write_text("{}", encoding="utf-8")

            with patch.object(drive_service.sys, "frozen", False, create=True), patch.dict(
                os.environ,
                {drive_service.GOOGLE_OAUTH_CONFIG_ENV_VAR: str(override_path)},
            ):
                self.assertEqual(
                    drive_service.resolve_oauth_client_config_path(), override_path
                )

    def test_source_release_candidate_is_available_without_real_user_data(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            release_path = project_root / "build_secrets" / "google_oauth_client.json"
            release_path.parent.mkdir()
            release_path.write_text("{}", encoding="utf-8")

            with patch.object(drive_service.sys, "frozen", False, create=True), patch.object(
                drive_service, "PROJECT_ROOT", project_root
            ), patch.object(drive_service, "CONFIG_DIR", project_root / "data" / "config"), patch.dict(
                os.environ,
                {drive_service.GOOGLE_OAUTH_CONFIG_ENV_VAR: ""},
            ):
                self.assertEqual(
                    drive_service.resolve_oauth_client_config_path(), release_path
                )

    def test_frozen_missing_resource_has_release_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(drive_service.sys, "frozen", True, create=True), patch.object(
                drive_service.sys, "_MEIPASS", temp_dir, create=True
            ), self.assertRaises(drive_service.OAuthConfigError) as raised:
                drive_service.resolve_oauth_client_config_path()

        self.assertIn("此發行版缺少 Google 登入設定", str(raised.exception))
        self.assertIn("重新下載正式版本", str(raised.exception))

    def test_authentication_uses_loopback_and_does_not_copy_client_json(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            client_path = temp_root / "oauth-client.json"
            client_path.write_text("{}", encoding="utf-8")
            token_path = temp_root / "data" / "config" / "token.json"

            fake_credentials = MagicMock()
            fake_credentials.valid = True
            fake_credentials.to_json.return_value = '{"token": "test-only"}'
            fake_flow = MagicMock()
            with patch.object(
                drive_service.InstalledAppFlow,
                "from_client_secrets_file",
                return_value=fake_flow,
            ) as from_file, patch.object(
                drive_service, "build", return_value=object()
            ), patch.object(
                drive_service,
                "run_local_oauth_server",
                return_value=fake_credentials,
            ) as run_local_server, patch.object(
                drive_service.sys, "frozen", False, create=True
            ), patch.dict(
                os.environ,
                {drive_service.GOOGLE_OAUTH_CONFIG_ENV_VAR: str(client_path)},
            ):
                manager = drive_service.GoogleDriveManager(token_path)
                ok, message = manager.authenticate_interactive()

            self.assertTrue(ok)
            self.assertIn("Google 帳號已登入", message)
            from_file.assert_called_once_with(str(client_path), drive_service.SCOPES)
            run_local_server.assert_called_once_with(
                fake_flow, host="localhost", port=0
            )
            self.assertTrue(token_path.is_file())
            self.assertFalse(
                (token_path.parent / drive_service.BUNDLED_OAUTH_CONFIG_FILENAME).exists()
            )

    def test_spec_embeds_oauth_client_but_not_token(self):
        spec_path = Path(__file__).resolve().parents[1] / "MapleClassicReporter.spec"
        spec_text = spec_path.read_text(encoding="utf-8")

        self.assertIn("build_secrets", spec_text)
        self.assertIn("google_oauth_client.json", spec_text)
        self.assertIn('(str(OAUTH_CLIENT_CONFIG), ".")', spec_text)
        self.assertNotIn("token.json", spec_text)


if __name__ == "__main__":
    unittest.main()
