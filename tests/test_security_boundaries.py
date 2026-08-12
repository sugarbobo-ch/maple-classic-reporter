import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PIL import Image

from maple_reporter.discord.webhook_service import (
    is_valid_discord_webhook_url,
    upload_evidence_to_discord,
)
from maple_reporter.gdrive.drive_service import escape_drive_query_literal
from maple_reporter.gdrive.token_store import SECRET_DPAPI_HEADER
from maple_reporter.ocr import win_ocr
from maple_reporter.recorder.window_recorder import capture_screenshot
from maple_reporter.utils import config
from maple_reporter.utils.urls import is_safe_https_url


class TestSecurityBoundaries(unittest.TestCase):
    def test_user_app_data_dir_uses_local_appdata(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {"LOCALAPPDATA": temp_dir}):
                self.assertEqual(
                    config.get_user_app_data_dir(),
                    Path(temp_dir) / "MapleClassicReporter",
                )

    def test_discord_webhook_url_is_strictly_validated(self):
        valid = "https://discord.com/api/webhooks/123456789012345678/token_value-1"
        self.assertTrue(is_valid_discord_webhook_url(valid))
        self.assertFalse(is_valid_discord_webhook_url(valid.replace("https://", "http://")))
        self.assertFalse(is_valid_discord_webhook_url(valid.replace("discord.com", "example.com")))
        self.assertFalse(is_valid_discord_webhook_url(valid + "?thread_id=1"))
        self.assertFalse(
            is_valid_discord_webhook_url(
                "https://user:password@discord.com/api/webhooks/123/token"
            )
        )

    def test_discord_rejects_untrusted_destination_before_reading_file(self):
        with patch("maple_reporter.discord.webhook_service.requests.post") as post:
            ok, message = upload_evidence_to_discord(
                "https://example.com/collect",
                "C:/does-not-exist.mp4",
                "description",
            )
        self.assertFalse(ok)
        self.assertIn("Discord", message)
        post.assert_not_called()

    def test_discord_rejects_untrusted_attachment_url(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            evidence = Path(temp_dir) / "evidence.mp4"
            evidence.write_bytes(b"evidence")
            response = MagicMock(status_code=200)
            response.json.return_value = {"attachments": [{"url": "javascript:alert(1)"}]}
            with patch(
                "maple_reporter.discord.webhook_service.requests.post",
                return_value=response,
            ):
                ok, message = upload_evidence_to_discord(
                    "https://discord.com/api/webhooks/123/token",
                    str(evidence),
                    "description",
                )
        self.assertFalse(ok)
        self.assertIn("Discord", message)

    def test_drive_query_literal_escaping_and_validation(self):
        self.assertEqual(escape_drive_query_literal("a'b\\c"), "a\\'b\\\\c")
        with self.assertRaises(ValueError):
            escape_drive_query_literal("bad\nname")

    def test_browser_urls_allow_https_only(self):
        self.assertTrue(is_safe_https_url("https://drive.google.com/file?id=123"))
        self.assertFalse(is_safe_https_url("http://drive.google.com/file?id=123"))
        self.assertFalse(is_safe_https_url("httpsx://example.com"))
        self.assertFalse(is_safe_https_url("https://user:pass@example.com/file"))

    def test_gemini_key_is_sent_in_header_not_url(self):
        response = MagicMock(status_code=200)
        response.json.return_value = {
            "candidates": [
                {"content": {"parts": [{"text": '{"ids": [], "map_name": ""}'}]}}
            ]
        }
        image = Image.new("RGB", (10, 10), color="white")
        with patch.object(win_ocr.requests, "post", return_value=response) as post:
            win_ocr.recognize_with_gemini_unified(image, "test-api-key")

        url, kwargs = post.call_args
        self.assertNotIn("key=", url)
        self.assertEqual(kwargs["headers"]["x-goog-api-key"], "test-api-key")

    @unittest.skipUnless(os.name == "nt", "application secret storage uses Windows DPAPI")
    def test_config_json_does_not_contain_application_secrets(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_file = root / "config" / "config.json"
            recordings_dir = root / "recordings"
            with patch.object(config, "CONFIG_DIR", config_file.parent), patch.object(
                config, "CONFIG_FILE", config_file
            ), patch.object(config, "HISTORY_FILE", config_file.parent / "history.json"), patch.object(
                config, "RECORDINGS_DIR", recordings_dir
            ), patch.dict(os.environ, {"LOCALAPPDATA": str(root / "appdata")}):
                config.save_config(
                    {
                        "default_server": "test",
                        "gemini_api_key": "gemini-secret",
                        "discord_webhook_url": "https://discord.com/api/webhooks/123/token",
                    }
                )

                raw = json.loads(config_file.read_text(encoding="utf-8"))
                self.assertNotIn("gemini_api_key", raw)
                self.assertNotIn("discord_webhook_url", raw)
                self.assertTrue(
                    (root / "appdata" / "MapleClassicReporter" / "gemini_api_key.dpapi").is_file()
                )
                if os.name == "nt":
                    self.assertTrue(
                        (
                            root
                            / "appdata"
                            / "MapleClassicReporter"
                            / "gemini_api_key.dpapi"
                        ).read_bytes().startswith(SECRET_DPAPI_HEADER)
                    )

                loaded = config.load_config()
                self.assertEqual(loaded["gemini_api_key"], "gemini-secret")

    def test_only_owned_recordings_are_deletable(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            recordings_dir = Path(temp_dir) / "recordings"
            recordings_dir.mkdir()
            generated = recordings_dir / "maple_evidence_123.mp4"
            generated.write_bytes(b"evidence")
            imported = Path(temp_dir) / "user-original.mp4"
            imported.write_bytes(b"original")
            with patch.object(config, "RECORDINGS_DIR", recordings_dir):
                self.assertTrue(config.is_owned_recording_path(generated))
                self.assertFalse(config.is_owned_recording_path(imported))

    def test_screenshot_requires_an_explicit_region(self):
        with self.assertRaises(ValueError):
            capture_screenshot()


if __name__ == "__main__":
    unittest.main()
