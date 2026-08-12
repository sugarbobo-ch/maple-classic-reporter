import unittest
from pathlib import Path
from unittest.mock import patch

from maple_reporter.automation.playwright_runtime import (
    PLAYWRIGHT_DOWNLOAD_URL,
    PlaywrightBrowserError,
    PlaywrightErrorDetails,
    get_bundled_browser_dir,
    get_bundled_driver_path,
)
from maple_reporter.utils.config import get_base_dir


class TestPlaywrightRuntime(unittest.TestCase):
    def test_error_details_include_every_copyable_field(self):
        details = PlaywrightErrorDetails(
            summary="找不到可用的 Playwright Chromium。",
            technical_error="FileNotFoundError: chrome.exe",
            executable_path="C:\\temp\\chrome.exe",
            bundled_browser_dir="C:\\temp\\ms-playwright",
            driver_path="C:\\temp\\node.exe",
        )

        text = details.as_text()

        self.assertIn("找不到可用的 Playwright Chromium。", text)
        self.assertIn("FileNotFoundError: chrome.exe", text)
        self.assertIn("C:\\temp\\chrome.exe", text)
        self.assertIn("C:\\temp\\ms-playwright", text)
        self.assertIn("C:\\temp\\node.exe", text)
        self.assertIn(PLAYWRIGHT_DOWNLOAD_URL, text)
        self.assertIn("playwright install chromium", text)

    def test_error_keeps_structured_details(self):
        error = PlaywrightBrowserError(
            "Playwright Chromium 啟動失敗。",
            technical_error="OSError: launch failed",
            executable_path=Path("C:/chrome.exe"),
        )

        self.assertEqual(error.details.summary, "Playwright Chromium 啟動失敗。")
        self.assertEqual(error.details.technical_error, "OSError: launch failed")
        self.assertEqual(error.details.executable_path, "C:\\chrome.exe")

    def test_frozen_data_directory_is_next_to_the_executable(self):
        with patch("maple_reporter.utils.config.sys.frozen", True, create=True), patch(
            "maple_reporter.utils.config.sys.executable", "C:/Apps/MapleClassicReporter.exe"
        ):
            self.assertEqual(get_base_dir(), Path("C:/Apps"))

    def test_onedir_runtime_resources_resolve_from_internal_directory(self):
        with patch(
            "maple_reporter.automation.playwright_runtime.sys.frozen",
            True,
            create=True,
        ), patch(
            "maple_reporter.automation.playwright_runtime.sys._MEIPASS",
            "C:/Apps/MapleClassicReporter/_internal",
            create=True,
        ):
            self.assertEqual(
                get_bundled_browser_dir(),
                Path("C:/Apps/MapleClassicReporter/_internal/ms-playwright"),
            )
            self.assertEqual(
                get_bundled_driver_path(),
                Path(
                    "C:/Apps/MapleClassicReporter/_internal/"
                    "playwright/driver/node.exe"
                ),
            )


if __name__ == "__main__":
    unittest.main()
