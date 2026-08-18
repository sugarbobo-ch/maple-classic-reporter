import unittest
from pathlib import Path
from unittest.mock import patch

from maple_reporter import __version__
from maple_reporter.gui.webview_app import (
    APP_TITLE,
    APP_USER_MODEL_ID,
    DEFAULT_WINDOW_SIZE,
    MIN_WINDOW_SIZE,
    get_web_index_path,
    get_webview_icon_path,
    is_dev_server_running,
    set_windows_app_user_model_id,
)


class TestWebviewApp(unittest.TestCase):
    def test_native_title_uses_current_product_name_and_version(self):
        self.assertEqual(
            APP_TITLE,
            f"新楓之谷：經典版《自動外掛檢舉工具》｜v{__version__}",
        )

    def test_project_icon_is_available_to_pywebview(self):
        icon_path = get_webview_icon_path()

        self.assertIsNotNone(icon_path)
        self.assertEqual(Path(icon_path).name, "icon.ico")
        self.assertTrue(Path(icon_path).is_file())

    def test_app_user_model_id_is_windows_only(self):
        self.assertEqual(APP_USER_MODEL_ID, "MapleClassicReporter")
        with patch("maple_reporter.gui.webview_app.sys.platform", "linux"):
            self.assertFalse(set_windows_app_user_model_id())

    def test_default_window_size_leaves_room_for_the_main_ui(self):
        self.assertEqual(DEFAULT_WINDOW_SIZE, (1040, 860))
        self.assertEqual(MIN_WINDOW_SIZE, (880, 620))

    def test_is_dev_server_running_returns_boolean(self):
        self.assertIsInstance(is_dev_server_running(), bool)

    def test_get_web_index_path_returns_valid_target(self):
        target = get_web_index_path()
        self.assertTrue(target.startswith("http://") or target.startswith("file://"))


if __name__ == "__main__":
    unittest.main()
