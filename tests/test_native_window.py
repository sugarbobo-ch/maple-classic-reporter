import ctypes
import unittest
from unittest.mock import MagicMock, patch

from ctypes import wintypes

import maple_reporter.gui.native_window as native_window

from maple_reporter.gui.native_window import (
    begin_native_drag,
    begin_native_resize,
    calculate_maximized_work_area,
    calculate_restored_grab_offset,
    calculate_resize_hit_test,
    calculate_resize_metrics,
    calculate_window_hit_test,
    move_window_by_drag_delta,
    prepare_native_drag,
    preserve_window_size_on_dpi_change,
)


class TestNativeWindow(unittest.TestCase):
    def tearDown(self):
        native_window._SUBCLASSES.clear()
        native_window._WINDOW_DPI.clear()
        native_window._WINDOW_LOGICAL_SIZE.clear()
        native_window._RESIZE_OVERLAY_IN_SIZING.clear()
        native_window._ACTIVE_DPI_DRAG_GEOMETRY.clear()
        native_window._ACTIVE_DRAG_ANCHOR_RATIOS.clear()
        native_window._DPI_DRAG_RELEASE_DEADLINES.clear()
        native_window._WINDOW_ICON_HANDLES.clear()

    def test_resize_hit_test_covers_edges_and_all_corners(self):
        left, top, right, bottom = 100, 100, 900, 700
        expected_hit_tests = {
            (left, top): 13,
            (right - 1, top): 14,
            (left, bottom - 1): 16,
            (right - 1, bottom - 1): 17,
            (left, 400): 10,
            (right - 1, 400): 11,
            (500, top): 12,
            (500, bottom - 1): 15,
        }

        for (cursor_x, cursor_y), expected in expected_hit_tests.items():
            with self.subTest(cursor_x=cursor_x, cursor_y=cursor_y):
                self.assertEqual(
                    calculate_resize_hit_test(
                        left, top, right, bottom, cursor_x, cursor_y
                    ),
                    expected,
                )

    def test_resize_hit_test_ignores_center_and_maximized_window(self):
        bounds = (100, 100, 900, 700)

        self.assertIsNone(calculate_resize_hit_test(*bounds, 500, 400))
        self.assertIsNone(
            calculate_resize_hit_test(*bounds, 100, 100, maximized=True)
        )

    def test_resize_metrics_scale_once_for_the_current_monitor_dpi(self):
        self.assertEqual(calculate_resize_metrics(96), (8, 58, 280))
        self.assertEqual(calculate_resize_metrics(144), (12, 87, 420))

    def test_maximized_work_area_stays_monitor_relative_on_a_portrait_monitor(self):
        self.assertEqual(
            calculate_maximized_work_area(
                (1920, -1200, 3000, 720),
                (1920, -1180, 3000, 700),
            ),
            (0, 20, 1080, 1880),
        )

    def test_dpi_change_centers_around_current_window_center(self):
        suggested = (80, 80, 1120, 830)  # new_w=1040, new_h=750
        # current center = (500, 400) -> new_left = 500 - 520 = -20, new_top = 400 - 375 = 25
        self.assertEqual(
            preserve_window_size_on_dpi_change(
                (100, 100, 900, 700),
                suggested,
            ),
            (-20, 25, 1020, 775),
        )

    def test_dpi_change_keeps_the_suggested_rect_for_a_maximized_window(self):
        suggested = (0, 0, 2194, 1186)
        self.assertEqual(
            preserve_window_size_on_dpi_change(
                (100, 100, 900, 700),
                suggested,
                maximized=True,
            ),
            suggested,
        )

    def test_dpi_change_pins_cursor_offset_when_dragging(self):
        current_rect = (2940, 200, 4760, 1200)  # width=1820, height=1000
        suggested_rect = (3840, 200, 5140, 914)  # width=1300, height=714
        cursor_pos = (3850, 250)  # cursor grabbed at (3850-2940)=910 -> 50% of 1820
        result = preserve_window_size_on_dpi_change(
            current_rect,
            suggested_rect,
            cursor_pos=cursor_pos,
            is_dragging=True,
        )
        # scale_x = 1300/1820 = 0.7142857 -> grab_offset_x = round(910 * (1300/1820)) = 650
        # new_left must stay at 3850 - 650 = 3200. Any post-transition
        # displacement breaks the cursor anchor and lets a later WebView move
        # pull the window back in the opposite direction.
        self.assertEqual(cursor_pos[0] - result[0], 650)
        self.assertEqual(result[0], 3200)
        self.assertEqual(result[2] - result[0], 1300)
        self.assertEqual(result[3] - result[1], 714)

    def test_drag_to_restore_uses_piecewise_header_anchors(self):
        common = (2560, 1300, 714)

        self.assertEqual(
            calculate_restored_grab_offset(*common, 200, 36, "left"),
            (200, 36),
        )
        self.assertEqual(
            calculate_restored_grab_offset(*common, 2360, 36, "right"),
            (1100, 36),
        )
        self.assertEqual(
            calculate_restored_grab_offset(*common, 1280, 36, "proportional"),
            (650, 36),
        )

    @patch("maple_reporter.gui.native_window._get_window_dpi", return_value=120)
    @patch("maple_reporter.gui.native_window._user32")
    def test_drag_delta_is_converted_from_logical_to_physical(self, user32, _dpi):
        def get_window_rect(_hwnd, rect_pointer):
            rect = ctypes.cast(rect_pointer, ctypes.POINTER(wintypes.RECT)).contents
            rect.left, rect.top, rect.right, rect.bottom = (3840, 200, 5140, 914)
            return True

        user32.GetWindowRect.side_effect = get_window_rect
        self.assertTrue(move_window_by_drag_delta(1234, 10, -4))
        user32.SetWindowPos.assert_called_once_with(
            1234,
            None,
            3852,
            195,
            0,
            0,
            native_window.SWP_NOSIZE
            | native_window.SWP_NOZORDER
            | native_window.SWP_NOACTIVATE
            | native_window.SWP_SHOWWINDOW,
        )

    def test_window_hit_test_uses_caption_for_header_but_not_controls(self):
        bounds = (100, 100, 900, 700)

        self.assertEqual(
            calculate_window_hit_test(*bounds, 400, 120),
            2,  # HTCAPTION
        )
        self.assertIsNone(
            calculate_window_hit_test(*bounds, 850, 120)
        )
        self.assertEqual(
            calculate_window_hit_test(*bounds, 400, 100),
            12,  # HTTOP
        )

    @patch("maple_reporter.gui.native_window._user32")
    @patch("maple_reporter.gui.native_window._get_cursor_position", return_value=(321, 654))
    def test_begin_native_resize_starts_a_non_client_sizing_loop(
        self, cursor_position, user32
    ):
        self.assertTrue(begin_native_resize(1234, "bottom-right"))

        user32.ReleaseCapture.assert_called_once_with()
        user32.PostMessageW.assert_called_once_with(
            1234,
            0x00A1,
            17,
            (654 << 16) | 321,
        )
        cursor_position.assert_called_once_with(user32)

    @patch("maple_reporter.gui.native_window._user32")
    @patch("maple_reporter.gui.native_window._get_cursor_position", return_value=(321, 654))
    def test_begin_native_drag_starts_a_caption_loop_for_windows_snap(
        self, cursor_position, user32
    ):
        self.assertTrue(begin_native_drag(1234))

        user32.ReleaseCapture.assert_called_once_with()
        user32.PostMessageW.assert_called_once_with(
            1234,
            0x00A1,
            native_window.HTCAPTION,
            (654 << 16) | 321,
        )
        cursor_position.assert_called_once_with(user32)

    @patch("maple_reporter.gui.native_window._user32")
    def test_set_window_identity_sets_titlebar_and_taskbar_icons(self, user32):
        user32.SetWindowTextW.return_value = True
        user32.LoadImageW.side_effect = [111, 222]

        with patch("maple_reporter.gui.native_window.os.name", "nt"):
            self.assertTrue(
                native_window.set_window_identity(
                    1234,
                    "Maple Classic Reporter",
                    "D:/Projects/maple-classic-reporter/assets/icon.ico",
                )
            )

        user32.SetWindowTextW.assert_called_once_with(1234, "Maple Classic Reporter")
        self.assertEqual(user32.LoadImageW.call_count, 2)
        user32.SendMessageW.assert_any_call(1234, native_window.WM_SETICON, 1, 111)
        user32.SendMessageW.assert_any_call(1234, native_window.WM_SETICON, 0, 222)
        self.assertEqual(native_window._WINDOW_ICON_HANDLES[1234], (111, 222))

    @patch("maple_reporter.gui.native_window._user32")
    @patch(
        "maple_reporter.gui.native_window._get_cursor_position",
        return_value=(500, 150),
    )
    def test_prepare_native_drag_captures_the_original_grab_ratio(
        self, _cursor_position, user32
    ):
        def get_window_rect(_hwnd, rect_pointer):
            rect = ctypes.cast(rect_pointer, ctypes.POINTER(wintypes.RECT)).contents
            rect.left, rect.top, rect.right, rect.bottom = (100, 100, 900, 1100)
            return True

        user32.GetWindowRect.side_effect = get_window_rect
        self.assertTrue(prepare_native_drag(1234))

        self.assertEqual(
            native_window._ACTIVE_DRAG_ANCHOR_RATIOS[1234],
            (0.5, 0.05),
        )

    @patch("maple_reporter.gui.native_window._user32")
    @patch(
        "maple_reporter.gui.native_window._get_cursor_position",
        return_value=(6200, 36),
    )
    def test_prepare_native_drag_restores_maximized_window_around_cursor_anchor(
        self, _cursor_position, user32
    ):
        def get_window_rect(_hwnd, rect_pointer):
            rect = ctypes.cast(rect_pointer, ctypes.POINTER(wintypes.RECT)).contents
            rect.left, rect.top, rect.right, rect.bottom = (3840, 0, 6400, 1440)
            return True

        hwnd = 1234
        user32.GetWindowRect.side_effect = get_window_rect
        user32.GetDpiForWindow.return_value = 120
        user32.IsZoomed.return_value = True
        native_window._WINDOW_LOGICAL_SIZE[hwnd] = (1040.0, 571.2)

        self.assertTrue(prepare_native_drag(hwnd, "right"))

        self.assertEqual(
            native_window._ACTIVE_DRAG_ANCHOR_RATIOS[hwnd],
            (1100 / 1300, 36 / 714),
        )
        user32.ShowWindow.assert_called_once_with(hwnd, native_window.SW_RESTORE)
        user32.SetWindowPos.assert_called_once_with(
            hwnd,
            None,
            5100,
            0,
            1300,
            714,
            native_window.SWP_NOZORDER | native_window.SWP_NOACTIVATE,
        )
        self.assertEqual(
            native_window._ACTIVE_DPI_DRAG_GEOMETRY[hwnd],
            (1300, 714, 1100, 36),
        )
        user32.SetTimer.assert_called_once_with(
            hwnd,
            native_window._DPI_DRAG_TIMER_ID,
            16,
            None,
        )
    @patch("maple_reporter.gui.native_window._get_cursor_position", return_value=(3850, 250))
    @patch("maple_reporter.gui.native_window._user32")
    def test_dpi_change_has_one_geometry_owner_during_native_drag(
        self, user32, _cursor_position
    ):
        hwnd = 1234
        user32.GetDpiForWindow.return_value = 168
        user32.GetWindowLongPtrW.return_value = 5678
        user32.SetWindowLongPtrW.return_value = 5678
        user32.IsZoomed.return_value = False
        user32.GetAsyncKeyState.return_value = 0x8000

        # By the time WM_DPICHANGED arrives, queued WebView movement may have
        # displaced the current rect away from the cursor. The pre-drag
        # anchor below remains the authoritative grab point.
        current = [2940, 300, 4760, 1300]

        def get_window_rect(_hwnd, rect_pointer):
            rect = ctypes.cast(rect_pointer, ctypes.POINTER(wintypes.RECT)).contents
            rect.left, rect.top, rect.right, rect.bottom = current
            return True

        user32.GetWindowRect.side_effect = get_window_rect

        def winforms_wnd_proc(_previous, window_handle, message, _w_param, l_param):
            if message == native_window.WM_DPICHANGED:
                rect = ctypes.cast(
                    ctypes.c_void_p(l_param), ctypes.POINTER(wintypes.RECT)
                ).contents
                user32.SetWindowPos(
                    window_handle,
                    None,
                    rect.left,
                    rect.top,
                    rect.right - rect.left,
                    rect.bottom - rect.top,
                    native_window.SWP_NOZORDER | native_window.SWP_NOACTIVATE,
                )
                current[:] = [rect.left, rect.top, rect.right, rect.bottom]
            return 0

        user32.CallWindowProcW.side_effect = winforms_wnd_proc

        native_window._install_wnd_proc(hwnd)
        callback, _previous = native_window._SUBCLASSES[hwnd]
        suggested = wintypes.RECT(3840, 200, 5140, 914)
        new_dpi = 120 | (120 << 16)

        native_window._ACTIVE_DPI_DRAG_GEOMETRY[hwnd] = (999, 999, 999, 999)
        callback(hwnd, native_window.WM_ENTERSIZEMOVE, 0, 0)
        self.assertNotIn(hwnd, native_window._ACTIVE_DPI_DRAG_GEOMETRY)
        native_window._ACTIVE_DRAG_ANCHOR_RATIOS[hwnd] = (0.5, 0.05)
        user32.SetWindowPos.reset_mock()
        callback(
            hwnd,
            native_window.WM_DPICHANGED,
            new_dpi,
            ctypes.addressof(suggested),
        )

        self.assertEqual(user32.SetWindowPos.call_count, 1)

        # WebView movement emits WM_WINDOWPOSCHANGING before applying stale
        # pre-DPI geometry, so this is where accepted bounds are preserved.
        class WindowPos(ctypes.Structure):
            _fields_ = [
                ("hwnd", wintypes.HWND),
                ("hwnd_insert_after", wintypes.HWND),
                ("x", ctypes.c_int),
                ("y", ctypes.c_int),
                ("cx", ctypes.c_int),
                ("cy", ctypes.c_int),
                ("flags", wintypes.UINT),
            ]

        changing = WindowPos(
            hwnd,
            0,
            2288,
            343,
            1796,
            1441,
            native_window.SWP_NOMOVE | native_window.SWP_NOSIZE,
        )
        callback(hwnd, 0x0046, 0, ctypes.addressof(changing))

        self.assertEqual(
            (changing.x, changing.y, changing.cx, changing.cy),
            (3200, 214, 1300, 714),
        )

        # A transient physical-size error on the 125% monitor must not be
        # multiplied on the return trip. The original 168-DPI logical size is
        # the stable source of truth.
        current[:] = [3200, 214, 4505, 934]  # drifted to 1305 x 720
        suggested_back = wintypes.RECT(2940, 200, 4767, 1208)
        old_dpi = 168 | (168 << 16)
        callback(
            hwnd,
            native_window.WM_DPICHANGED,
            old_dpi,
            ctypes.addressof(suggested_back),
        )
        changing_back = WindowPos(hwnd, 0, 2940, 200, 1827, 1008, 0)
        callback(hwnd, 0x0046, 0, ctypes.addressof(changing_back))
        self.assertEqual((changing_back.cx, changing_back.cy), (1820, 1000))

        callback(hwnd, 0x0202, 0, 0)  # WM_LBUTTONUP
        user32.GetAsyncKeyState.return_value = 0
        late_move = WindowPos(hwnd, 0, -999, 200, 0, 0, 0)
        callback(hwnd, 0x0046, 0, ctypes.addressof(late_move))
        self.assertEqual(
            (late_move.x, late_move.y, late_move.cx, late_move.cy),
            (2940, 200, 1820, 1000),
        )

        native_window._DPI_DRAG_RELEASE_DEADLINES[hwnd] = 0
        callback(hwnd, native_window.WM_TIMER, native_window._DPI_DRAG_TIMER_ID, 0)
        self.assertNotIn(hwnd, native_window._ACTIVE_DPI_DRAG_GEOMETRY)
        self.assertNotIn(hwnd, native_window._ACTIVE_DRAG_ANCHOR_RATIOS)
        user32.KillTimer.assert_any_call(hwnd, native_window._DPI_DRAG_TIMER_ID)

        maximize = WindowPos(hwnd, 0, 3840, 0, 2560, 1440, 0)
        callback(hwnd, 0x0046, 0, ctypes.addressof(maximize))
        self.assertEqual(
            (maximize.x, maximize.y, maximize.cx, maximize.cy),
            (3840, 0, 2560, 1440),
        )


if __name__ == "__main__":
    unittest.main()
