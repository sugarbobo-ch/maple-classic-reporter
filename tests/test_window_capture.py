import unittest
from unittest.mock import MagicMock, patch
import numpy as np

from maple_reporter.recorder.window_capture import (
    UnifiedWindowCapture,
    find_target_hwnd,
    get_client_relative_crop,
    restore_and_focus_window,
)


class TestWindowCapture(unittest.TestCase):
    def test_find_target_hwnd_empty(self):
        self.assertIsNone(find_target_hwnd(""))
        self.assertIsNone(find_target_hwnd("   "))

    def test_restore_and_focus_window_invalid(self):
        self.assertFalse(restore_and_focus_window(0))
        self.assertFalse(restore_and_focus_window(-1))

    @patch("ctypes.windll.user32.IsWindow", return_value=True)
    @patch("ctypes.windll.user32.IsIconic", return_value=True)
    @patch("ctypes.windll.user32.ShowWindow")
    @patch("time.sleep")
    def test_restore_and_focus_window_iconic(
        self, mock_sleep, mock_show, mock_iconic, mock_is_win
    ):
        res = restore_and_focus_window(99999)
        self.assertTrue(res)
        mock_show.assert_called_with(99999, 9)

    @patch("ctypes.windll.user32.IsWindow", return_value=True)
    @patch("ctypes.windll.user32.IsIconic", return_value=False)
    def test_restore_and_focus_window_already_restored(
        self, mock_iconic, mock_is_win
    ):
        res = restore_and_focus_window(99999)
        self.assertTrue(res)

    @patch("pygetwindow.getAllWindows")
    def test_find_target_hwnd_exact_and_fuzzy(self, mock_get_all):
        win1 = MagicMock()
        win1.title = "新楓之谷：經典版"
        win1._hWnd = 12345

        win2 = MagicMock()
        win2.title = "Google Chrome"
        win2._hWnd = 67890

        mock_get_all.return_value = [win2, win1]

        self.assertEqual(find_target_hwnd("新楓之谷：經典版"), 12345)
        self.assertEqual(find_target_hwnd("新楓之谷"), 12345)
        self.assertIsNone(find_target_hwnd("NonExistentWindow"))

    def test_get_client_relative_crop_fallback(self):
        # When HWND is invalid/0, should return full frame dimensions
        crop = get_client_relative_crop(0, 800, 600)
        self.assertEqual(crop, (0, 0, 800, 600))

    def test_unified_window_capture_fallback_when_wgc_fails(self):
        capture = UnifiedWindowCapture()
        
        # Test grab_single_frame with non-existent window
        frame, is_wgc = capture.grab_single_frame("NonExistentTitle_12345")
        self.assertIsNone(frame)
        self.assertFalse(is_wgc)

    @patch("maple_reporter.recorder.window_capture.find_window_bounds")
    @patch("mss.MSS")
    def test_unified_window_capture_mss_fallback(self, mock_mss_cls, mock_bounds):
        mock_bounds.return_value = (100, 100, 640, 480)
        mock_screen = MagicMock()
        mock_mss_cls.return_value.__enter__.return_value = mock_screen
        
        dummy_bgra = np.zeros((480, 640, 4), dtype=np.uint8)
        mock_screen.grab.return_value = dummy_bgra

        fallback_called = []
        capture = UnifiedWindowCapture(fallback_callback=lambda msg: fallback_called.append(msg))
        
        frame, is_wgc = capture.grab_single_frame("MockGameWindow")
        self.assertIsNotNone(frame)
        self.assertFalse(is_wgc)
        self.assertEqual(frame.shape, (480, 640, 3))
        self.assertTrue(len(fallback_called) > 0)


if __name__ == "__main__":
    unittest.main()
