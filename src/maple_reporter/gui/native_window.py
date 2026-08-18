"""Native Windows chrome helpers for the frameless PyWebView window."""

from __future__ import annotations

import ctypes
import logging
import os
import time
from ctypes import wintypes


LOGGER = logging.getLogger(__name__)

WM_NCHITTEST = 0x0084
WM_SETICON = 0x0080
WM_NCCALCSIZE = 0x0083
WM_GETMINMAXINFO = 0x0024
WM_NCDESTROY = 0x0082
WM_NCLBUTTONDOWN = 0x00A1
WM_WINDOWPOSCHANGING = 0x0046
WM_DPICHANGED = 0x02E0
WM_GETDPISCALEDSIZE = 0x02E4
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_NCLBUTTONUP = 0x00A2
WM_CAPTURECHANGED = 0x0215
WM_SETCURSOR = 0x0020
WM_MOUSEACTIVATE = 0x0021
WM_ERASEBKGND = 0x0014
WM_PAINT = 0x000F
WM_SIZE = 0x0005
WM_TIMER = 0x0113
WM_ENTERSIZEMOVE = 0x0231
WM_EXITSIZEMOVE = 0x0232
HTCAPTION = 2
HTCLIENT = 1
MA_NOACTIVATE = 3
GWL_WNDPROC = -4
GWL_STYLE = -16
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020
SWP_SHOWWINDOW = 0x0040
MONITOR_DEFAULTTONEAREST = 0x00000002
HWND_TOP = 0
WS_CHILD = 0x40000000
WS_VISIBLE = 0x10000000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_NOACTIVATE = 0x08000000
SW_HIDE = 0
SW_SHOWNA = 8
SW_RESTORE = 9
RGN_DIFF = 4

IDC_SIZEWE = 32644
IDC_SIZENS = 32645
IDC_SIZENWSE = 32642
IDC_SIZENESW = 32643

WS_MAXIMIZEBOX = 0x00010000
WS_MINIMIZEBOX = 0x00020000
WS_THICKFRAME = 0x00040000
WS_SYSMENU = 0x00080000

HTLEFT = 10
HTRIGHT = 11
HTTOP = 12
HTTOPLEFT = 13
HTTOPRIGHT = 14
HTBOTTOM = 15
HTBOTTOMLEFT = 16
HTBOTTOMRIGHT = 17

ICON_SMALL = 0
ICON_BIG = 1
IMAGE_ICON = 1
LR_LOADFROMFILE = 0x00000010
GCLP_HICON = -14
GCLP_HICONSM = -34

WINDOW_HEADER_HEIGHT = 58
WINDOW_ACTIONS_EXCLUSION_WIDTH = 280
WINDOW_MIN_TRACK_WIDTH = 880
WINDOW_MIN_TRACK_HEIGHT = 620

_RESIZE_HIT_TESTS = {
    "left": HTLEFT,
    "right": HTRIGHT,
    "top": HTTOP,
    "top-left": HTTOPLEFT,
    "top-right": HTTOPRIGHT,
    "bottom": HTBOTTOM,
    "bottom-left": HTBOTTOMLEFT,
    "bottom-right": HTBOTTOMRIGHT,
}

_user32 = ctypes.WinDLL("user32", use_last_error=True) if os.name == "nt" else None
_gdi32 = ctypes.WinDLL("gdi32", use_last_error=True) if os.name == "nt" else None


class _Point(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class _Size(ctypes.Structure):
    _fields_ = [("cx", wintypes.LONG), ("cy", wintypes.LONG)]


class _WindowPos(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("hwnd_insert_after", wintypes.HWND),
        ("x", ctypes.c_int),
        ("y", ctypes.c_int),
        ("cx", ctypes.c_int),
        ("cy", ctypes.c_int),
        ("flags", wintypes.UINT),
    ]


class _MinMaxInfo(ctypes.Structure):
    _fields_ = [
        ("ptReserved", _Point),
        ("ptMaxSize", _Point),
        ("ptMaxPosition", _Point),
        ("ptMinTrackSize", _Point),
        ("ptMaxTrackSize", _Point),
    ]


class _MonitorInfo(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", wintypes.RECT),
        ("rcWork", wintypes.RECT),
        ("dwFlags", wintypes.DWORD),
    ]


_SUBCLASSES: dict[int, tuple[object, int]] = {}
_WINDOW_DPI: dict[int, int] = {}
_WINDOW_LOGICAL_SIZE: dict[int, tuple[float, float]] = {}
_RESIZE_OVERLAYS: dict[int, int] = {}
_RESIZE_OVERLAY_CLASS_REGISTERED = False
_RESIZE_OVERLAY_WNDPROC = None
_RESIZE_OVERLAY_CLASS_NAME = "MapleClassicReporterResizeOverlay"
_RESIZE_OVERLAY_TIMER_ID = 0x4D52
_DPI_DRAG_TIMER_ID = 0x4D44
_RESIZE_OVERLAY_TIMER_ATTEMPTS: dict[int, int] = {}
_RESIZE_OVERLAY_IN_SIZING: set[int] = set()
_ACTIVE_DPI_DRAG_GEOMETRY: dict[int, tuple[int, int, int, int]] = {}
_ACTIVE_DRAG_ANCHOR_RATIOS: dict[int, tuple[float, float]] = {}
_DPI_DRAG_RELEASE_DEADLINES: dict[int, float] = {}
_WINDOW_ICON_HANDLES: dict[int, tuple[int, int]] = {}
_RESIZE_OVERLAY_API_CONFIGURED = False
_DPI_API_CONFIGURED = False
_CURSOR_API_CONFIGURED = False


def _clear_active_drag_state(hwnd: int) -> None:
    _ACTIVE_DPI_DRAG_GEOMETRY.pop(hwnd, None)
    _ACTIVE_DRAG_ANCHOR_RATIOS.pop(hwnd, None)
    _DPI_DRAG_RELEASE_DEADLINES.pop(hwnd, None)


def _schedule_drag_release(hwnd: int) -> None:
    if hwnd in _ACTIVE_DPI_DRAG_GEOMETRY:
        _DPI_DRAG_RELEASE_DEADLINES.setdefault(hwnd, time.monotonic() + 0.12)
    else:
        _clear_active_drag_state(hwnd)


def _end_active_drag(user32, hwnd: int) -> None:
    _clear_active_drag_state(hwnd)
    user32.KillTimer(hwnd, _DPI_DRAG_TIMER_ID)


def _physical_size_for_dpi(
    logical_size: tuple[float, float], dpi: int
) -> tuple[int, int]:
    scale = max(int(dpi or 96), 1) / 96.0
    return (
        max(1, round(logical_size[0] * scale)),
        max(1, round(logical_size[1] * scale)),
    )


def _remember_logical_window_size(user32, hwnd: int, dpi: int) -> None:
    rect = wintypes.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return
    width = rect.right - rect.left
    height = rect.bottom - rect.top
    if width <= 0 or height <= 0:
        return
    scale = max(int(dpi or 96), 1) / 96.0
    _WINDOW_LOGICAL_SIZE[hwnd] = (width / scale, height / scale)


class _ResizeOverlayClass(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", ctypes.c_void_p),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", ctypes.c_void_p),
        ("hIcon", ctypes.c_void_p),
        ("hCursor", ctypes.c_void_p),
        ("hbrBackground", ctypes.c_void_p),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


def calculate_resize_metrics(dpi: int) -> tuple[int, int, int]:
    """Return resize border, header, and control exclusion sizes for a DPI."""
    scale = max(int(dpi or 96), 1) / 96
    return (
        max(8, round(8 * scale)),
        max(8, round(WINDOW_HEADER_HEIGHT * scale)),
        max(8, round(WINDOW_ACTIONS_EXCLUSION_WIDTH * scale)),
    )


def _dpi_from_message(w_param: int, fallback: int = 96) -> int:
    """Read the X DPI from WM_DPICHANGED's packed wParam value."""
    dpi = int(w_param) & 0xFFFF
    return dpi or fallback


def _get_window_dpi(user32, hwnd: int) -> int:
    global _DPI_API_CONFIGURED
    cached = _WINDOW_DPI.get(hwnd)
    if cached:
        return cached

    if not _DPI_API_CONFIGURED:
        user32.GetDpiForWindow.argtypes = [wintypes.HWND]
        user32.GetDpiForWindow.restype = wintypes.UINT
        _DPI_API_CONFIGURED = True
    dpi = int(user32.GetDpiForWindow(hwnd) or 96)
    _WINDOW_DPI[hwnd] = dpi
    return dpi


def _get_cursor_position(user32) -> tuple[int, int] | None:
    """Return the current cursor position in screen coordinates."""
    global _CURSOR_API_CONFIGURED
    point = _Point()
    if not _CURSOR_API_CONFIGURED:
        user32.GetCursorPos.argtypes = [ctypes.POINTER(_Point)]
        user32.GetCursorPos.restype = wintypes.BOOL
        _CURSOR_API_CONFIGURED = True
    if not user32.GetCursorPos(ctypes.byref(point)):
        return None
    return int(point.x), int(point.y)


def _pack_screen_point(cursor_x: int, cursor_y: int) -> int:
    """Pack signed screen coordinates into the LPARAM used by mouse messages."""
    return (int(cursor_x) & 0xFFFF) | ((int(cursor_y) & 0xFFFF) << 16)


def calculate_maximized_work_area(
    monitor_rect: tuple[int, int, int, int],
    work_rect: tuple[int, int, int, int],
) -> tuple[int, int, int, int]:
    """Return monitor-relative max position plus work-area size."""
    monitor_left, monitor_top, _monitor_right, _monitor_bottom = monitor_rect
    work_left, work_top, work_right, work_bottom = work_rect
    return (
        work_left - monitor_left,
        work_top - monitor_top,
        max(0, work_right - work_left),
        max(0, work_bottom - work_top),
    )


def preserve_window_size_on_dpi_change(
    current_rect: tuple[int, int, int, int],
    suggested_rect: tuple[int, int, int, int],
    cursor_pos: tuple[int, int] | None = None,
    is_dragging: bool = False,
    maximized: bool = False,
    grab_ratio: tuple[float, float] | None = None,
) -> tuple[int, int, int, int]:
    """Calculate DPI-scaled bounds without changing the active cursor anchor."""
    if maximized:
        return suggested_rect

    new_width = max(0, suggested_rect[2] - suggested_rect[0])
    new_height = max(0, suggested_rect[3] - suggested_rect[1])
    if new_width <= 0 or new_height <= 0:
        return suggested_rect

    curr_left, curr_top, curr_right, curr_bottom = current_rect
    curr_width = curr_right - curr_left
    curr_height = curr_bottom - curr_top
    if curr_width <= 0 or curr_height <= 0:
        return suggested_rect

    scale_x = new_width / float(curr_width)
    scale_y = new_height / float(curr_height)

    if is_dragging and cursor_pos is not None:
        cursor_x, cursor_y = cursor_pos
        # Scale the grab offset from cursor to top-left corner
        # so the mouse cursor stays pinned to the exact same point in the title bar
        if grab_ratio is not None:
            grab_offset_x = round(new_width * grab_ratio[0])
            grab_offset_y = round(new_height * grab_ratio[1])
        else:
            grab_offset_x = round((cursor_x - curr_left) * scale_x)
            grab_offset_y = round((cursor_y - curr_top) * scale_y)
        new_left = cursor_x - grab_offset_x
        new_top = cursor_y - grab_offset_y
    else:
        # Static change: center around current window center
        center_x = (curr_left + curr_right) / 2.0
        center_y = (curr_top + curr_bottom) / 2.0
        new_left = round(center_x - new_width / 2.0)
        new_top = round(center_y - new_height / 2.0)

    return (new_left, new_top, new_left + new_width, new_top + new_height)


def calculate_restored_grab_offset(
    current_width: int,
    target_width: int,
    target_height: int,
    offset_x: int,
    offset_y: int,
    anchor_mode: str,
) -> tuple[int, int]:
    """Resolve a drag-to-restore anchor for fixed and fluid header regions."""
    mode = anchor_mode.strip().lower()
    if mode == "left":
        target_offset_x = offset_x
    elif mode == "right":
        target_offset_x = target_width - (current_width - offset_x)
    else:
        ratio_x = offset_x / current_width if current_width > 0 else 0.5
        target_offset_x = round(target_width * ratio_x)

    return (
        min(max(target_offset_x, 0), target_width),
        min(max(offset_y, 0), target_height),
    )




def calculate_resize_hit_test(
    left: int,
    top: int,
    right: int,
    bottom: int,
    cursor_x: int,
    cursor_y: int,
    border_size: int = 8,
    maximized: bool = False,
) -> int | None:
    """Return the Win32 resize hit-test code for a window edge or corner."""
    if maximized or right <= left or bottom <= top:
        return None

    on_left = left <= cursor_x < left + border_size
    on_right = right - border_size <= cursor_x < right
    on_top = top <= cursor_y < top + border_size
    on_bottom = bottom - border_size <= cursor_y < bottom

    if on_top and on_left:
        return HTTOPLEFT
    if on_top and on_right:
        return HTTOPRIGHT
    if on_bottom and on_left:
        return HTBOTTOMLEFT
    if on_bottom and on_right:
        return HTBOTTOMRIGHT
    if on_left:
        return HTLEFT
    if on_right:
        return HTRIGHT
    if on_top:
        return HTTOP
    if on_bottom:
        return HTBOTTOM
    return None


def calculate_window_hit_test(
    left: int,
    top: int,
    right: int,
    bottom: int,
    cursor_x: int,
    cursor_y: int,
    border_size: int = 8,
    header_height: int = WINDOW_HEADER_HEIGHT,
    right_exclusion_width: int = WINDOW_ACTIONS_EXCLUSION_WIDTH,
    maximized: bool = False,
) -> int | None:
    """Return resize or caption hit-testing for the frameless app window."""
    resize_hit_test = calculate_resize_hit_test(
        left,
        top,
        right,
        bottom,
        cursor_x,
        cursor_y,
        border_size,
        maximized,
    )
    if resize_hit_test is not None:
        return resize_hit_test

    header_bottom = top + max(header_height, border_size)
    drag_right = right - max(right_exclusion_width, border_size)
    if left <= cursor_x < drag_right and top + border_size <= cursor_y < header_bottom:
        return HTCAPTION

    return None


def _begin_native_resize(hwnd: int, hit_test: int) -> bool:
    """Start a native Windows sizing loop from a WebView event."""
    if not hwnd or not _user32:
        return False

    user32 = _user32
    try:
        user32.ReleaseCapture.argtypes = []
        user32.ReleaseCapture.restype = wintypes.BOOL
        user32.PostMessageW.argtypes = [
            wintypes.HWND,
            wintypes.UINT,
            wintypes.WPARAM,
            wintypes.LPARAM,
        ]
        user32.PostMessageW.restype = wintypes.BOOL
        cursor_position = _get_cursor_position(user32)
        if cursor_position is None:
            return False

        user32.ReleaseCapture()
        # Posting avoids blocking the WebView bridge while Win32 owns sizing.
        return bool(
            user32.PostMessageW(
                hwnd,
                WM_NCLBUTTONDOWN,
                hit_test,
                _pack_screen_point(*cursor_position),
            )
        )
    except (OSError, TypeError, ValueError):
        LOGGER.debug("Native window resize failed", exc_info=True)
        return False


def prepare_native_drag(hwnd: int, anchor_mode: str = "proportional") -> bool:
    """Capture the anchor and restore a maximized window before JS movement."""
    user32 = _user32
    if not hwnd or not user32:
        return False

    _end_active_drag(user32, hwnd)
    cursor_position = _get_cursor_position(user32)
    rect = wintypes.RECT()
    if cursor_position is not None and user32.GetWindowRect(
        hwnd, ctypes.byref(rect)
    ):
        width = rect.right - rect.left
        height = rect.bottom - rect.top
        offset_x = cursor_position[0] - rect.left
        offset_y = cursor_position[1] - rect.top
        if (
            width > 0
            and height > 0
            and 0 <= offset_x <= width
            and 0 <= offset_y <= height
        ):
            grab_ratio = (offset_x / width, offset_y / height)

            if user32.IsZoomed(hwnd):
                # A custom WebView title bar does not get Windows' normal
                # drag-to-restore positioning for free. Restore to the
                # canonical normal size and position that rect around the
                # exact point the user held in the maximized window.
                logical_size = _WINDOW_LOGICAL_SIZE.get(hwnd)
                user32.ShowWindow(hwnd, SW_RESTORE)
                if logical_size is not None:
                    target_width, target_height = _physical_size_for_dpi(
                        logical_size,
                        _get_window_dpi(user32, hwnd),
                    )
                else:
                    restored_rect = wintypes.RECT()
                    if user32.GetWindowRect(hwnd, ctypes.byref(restored_rect)):
                        target_width = restored_rect.right - restored_rect.left
                        target_height = restored_rect.bottom - restored_rect.top
                    else:
                        target_width, target_height = width, height

                target_offset_x, target_offset_y = calculate_restored_grab_offset(
                    width,
                    target_width,
                    target_height,
                    offset_x,
                    offset_y,
                    anchor_mode,
                )
                grab_ratio = (
                    target_offset_x / target_width,
                    target_offset_y / target_height,
                )
                target_left = cursor_position[0] - target_offset_x
                target_top = cursor_position[1] - target_offset_y
                user32.SetWindowPos(
                    hwnd,
                    None,
                    target_left,
                    target_top,
                    target_width,
                    target_height,
                    SWP_NOZORDER | SWP_NOACTIVATE,
                )
                _ACTIVE_DPI_DRAG_GEOMETRY[hwnd] = (
                    target_width,
                    target_height,
                    cursor_position[0] - target_left,
                    cursor_position[1] - target_top,
                )
                user32.SetTimer(hwnd, _DPI_DRAG_TIMER_ID, 16, None)
                if logical_size is not None:
                    _WINDOW_LOGICAL_SIZE[hwnd] = logical_size
            _ACTIVE_DRAG_ANCHOR_RATIOS[hwnd] = grab_ratio
            return True
    return False


def move_window_by_drag_delta(hwnd: int, delta_x: float, delta_y: float) -> bool:
    """Move a window by a WebView logical-pixel delta in physical pixels.

    pywebview's absolute logical desktop coordinates are not stable across
    mixed-DPI monitor origins. Applying only the per-event delta avoids
    converting a global logical origin with the wrong monitor scale.
    """
    user32 = _user32
    if not hwnd or not user32:
        return False

    try:
        rect = wintypes.RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return False
        scale = max(_get_window_dpi(user32, hwnd), 1) / 96.0
        target_left = rect.left + round(float(delta_x) * scale)
        target_top = rect.top + round(float(delta_y) * scale)
        user32.SetWindowPos(
            hwnd,
            None,
            target_left,
            target_top,
            0,
            0,
            SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_SHOWWINDOW,
        )
        return True
    except (OSError, TypeError, ValueError):
        LOGGER.debug("Native drag delta move failed", exc_info=True)
        return False


def begin_native_resize(hwnd: int, direction: str) -> bool:
    """Start the native Windows sizing loop for a resize direction."""
    hit_test = _RESIZE_HIT_TESTS.get(direction.strip().lower())
    if hit_test is None:
        return False
    return _begin_native_resize(hwnd, hit_test)


def begin_native_drag(hwnd: int) -> bool:
    """Start the native caption drag loop so Windows Snap can take over."""
    return _begin_native_resize(hwnd, HTCAPTION)


def _window_handle(window) -> int | None:
    native = getattr(window, "native", None)
    handle = getattr(native, "Handle", None)
    if handle is None:
        return None

    try:
        to_int64 = getattr(handle, "ToInt64", None)
        return int(to_int64() if to_int64 else handle)
    except (AttributeError, TypeError, ValueError):
        return None


def set_window_identity(hwnd: int, title: str, icon_path: str | None = None) -> bool:
    """Set the native title-bar/taskbar title and icon for the PyWebView window."""
    if os.name != "nt" or not hwnd or not _user32:
        return False

    user32 = _user32
    try:
        user32.SetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPCWSTR]
        user32.SetWindowTextW.restype = wintypes.BOOL
        user32.SendMessageW.argtypes = [
            wintypes.HWND,
            wintypes.UINT,
            wintypes.WPARAM,
            wintypes.LPARAM,
        ]
        user32.SendMessageW.restype = ctypes.c_ssize_t
        user32.SetClassLongPtrW.argtypes = [
            wintypes.HWND,
            ctypes.c_int,
            ctypes.c_void_p,
        ]
        user32.SetClassLongPtrW.restype = ctypes.c_void_p
        user32.LoadImageW.argtypes = [
            wintypes.HINSTANCE,
            wintypes.LPCWSTR,
            wintypes.UINT,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.UINT,
        ]
        user32.LoadImageW.restype = ctypes.c_void_p

        title_set = bool(user32.SetWindowTextW(hwnd, title or ""))
        if not icon_path:
            return title_set

        existing_icons = _WINDOW_ICON_HANDLES.get(hwnd)
        if existing_icons:
            big_icon, small_icon = existing_icons
            user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, big_icon)
            user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, small_icon)
            return title_set

        icon_handles = []
        for size in (32, 16):
            icon = user32.LoadImageW(
                None,
                str(icon_path),
                IMAGE_ICON,
                size,
                size,
                LR_LOADFROMFILE,
            )
            if icon:
                icon_handles.append(int(icon))

        if not icon_handles:
            return title_set

        big_icon = icon_handles[0]
        small_icon = icon_handles[-1]
        user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, big_icon)
        user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, small_icon)
        user32.SetClassLongPtrW(hwnd, GCLP_HICON, ctypes.c_void_p(big_icon))
        user32.SetClassLongPtrW(hwnd, GCLP_HICONSM, ctypes.c_void_p(small_icon))
        _WINDOW_ICON_HANDLES[hwnd] = (big_icon, small_icon)
        return title_set
    except (AttributeError, OSError, TypeError, ValueError):
        LOGGER.debug("Failed to set native window identity", exc_info=True)
        return False


def _install_resize_style(hwnd: int) -> None:
    user32 = _user32
    user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.GetWindowLongW.restype = wintypes.LONG
    user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.LONG]
    user32.SetWindowLongW.restype = wintypes.LONG
    user32.SetWindowPos.argtypes = [
        wintypes.HWND,
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    ]

    style = user32.GetWindowLongW(hwnd, GWL_STYLE)
    style |= WS_THICKFRAME | WS_MAXIMIZEBOX | WS_MINIMIZEBOX | WS_SYSMENU
    user32.SetWindowLongW(hwnd, GWL_STYLE, style)
    user32.SetWindowPos(
        hwnd,
        None,
        0,
        0,
        0,
        0,
        SWP_NOMOVE
        | SWP_NOSIZE
        | SWP_NOZORDER
        | SWP_NOACTIVATE
        | SWP_FRAMECHANGED,
    )


def _install_wnd_proc(hwnd: int) -> None:
    global _DPI_API_CONFIGURED
    if hwnd in _SUBCLASSES:
        return

    user32 = _user32
    wnd_proc_type = ctypes.WINFUNCTYPE(
        ctypes.c_ssize_t,
        wintypes.HWND,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
    )

    user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.GetWindowLongPtrW.restype = ctypes.c_void_p
    user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
    user32.SetWindowLongPtrW.restype = ctypes.c_void_p
    user32.CallWindowProcW.argtypes = [
        ctypes.c_void_p,
        wintypes.HWND,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
    ]
    user32.CallWindowProcW.restype = ctypes.c_ssize_t
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.GetWindowRect.restype = wintypes.BOOL
    user32.IsZoomed.argtypes = [wintypes.HWND]
    user32.IsZoomed.restype = wintypes.BOOL
    user32.SetWindowPos.argtypes = [
        wintypes.HWND,
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    ]
    user32.SetWindowPos.restype = wintypes.BOOL
    user32.GetDpiForWindow.argtypes = [wintypes.HWND]
    user32.GetDpiForWindow.restype = wintypes.UINT
    user32.SetTimer.argtypes = [
        wintypes.HWND,
        ctypes.c_void_p,
        wintypes.UINT,
        ctypes.c_void_p,
    ]
    user32.SetTimer.restype = ctypes.c_void_p
    user32.KillTimer.argtypes = [wintypes.HWND, ctypes.c_void_p]
    user32.KillTimer.restype = wintypes.BOOL
    _DPI_API_CONFIGURED = True

    _WINDOW_DPI[hwnd] = int(user32.GetDpiForWindow(hwnd) or 96)
    _remember_logical_window_size(user32, hwnd, _WINDOW_DPI[hwnd])
    previous = user32.GetWindowLongPtrW(hwnd, GWL_WNDPROC)
    previous_value = previous.value if isinstance(previous, ctypes.c_void_p) else int(previous)
    if not previous_value:
        raise OSError("could not read the native window procedure")

    def call_previous(window_handle, message, w_param, l_param):
        return user32.CallWindowProcW(
            ctypes.c_void_p(previous_value), window_handle, message, w_param, l_param
        )

    def window_proc(window_handle, message, w_param, l_param):
        try:
            dpi_change_rect = None
            previous_l_param = l_param
            if message == WM_GETDPISCALEDSIZE and l_param:
                new_dpi = int(w_param) & 0xFFFF
                current_dpi = _WINDOW_DPI.get(hwnd) or _get_window_dpi(user32, window_handle) or 96
                if new_dpi and current_dpi and not user32.IsZoomed(window_handle):
                    current_rect = wintypes.RECT()
                    if user32.GetWindowRect(window_handle, ctypes.byref(current_rect)):
                        curr_w = current_rect.right - current_rect.left
                        curr_h = current_rect.bottom - current_rect.top
                        size_ptr = ctypes.cast(ctypes.c_void_p(l_param), ctypes.POINTER(_Size))
                        logical_size = _WINDOW_LOGICAL_SIZE.get(hwnd)
                        if logical_size is not None:
                            target_width, target_height = _physical_size_for_dpi(
                                logical_size, new_dpi
                            )
                        else:
                            target_width = round(curr_w * (new_dpi / current_dpi))
                            target_height = round(curr_h * (new_dpi / current_dpi))
                        size_ptr.contents.cx = target_width
                        size_ptr.contents.cy = target_height
                        return 1

            if message == WM_DPICHANGED:
                # Keep the resize hit-test metrics aligned with the DPI that
                # Windows just assigned to this top-level window.  The
                # original WinForms procedure still owns child re-layout and
                # WebView scaling, but it must not scale a restored window's
                # outer bounds just because the monitor DPI changed.
                _WINDOW_DPI[hwnd] = _dpi_from_message(w_param, _WINDOW_DPI.get(hwnd, 96))
                if l_param and not user32.IsZoomed(window_handle):
                    current_rect = wintypes.RECT()
                    if user32.GetWindowRect(
                        window_handle, ctypes.byref(current_rect)
                    ):
                        suggested_rect = ctypes.cast(
                            ctypes.c_void_p(l_param),
                            ctypes.POINTER(wintypes.RECT),
                        ).contents
                        suggested_bounds = (
                            suggested_rect.left,
                            suggested_rect.top,
                            suggested_rect.right,
                            suggested_rect.bottom,
                        )
                        logical_size = _WINDOW_LOGICAL_SIZE.get(hwnd)
                        if logical_size is not None:
                            target_width, target_height = _physical_size_for_dpi(
                                logical_size, _WINDOW_DPI[hwnd]
                            )
                            suggested_bounds = (
                                suggested_rect.left,
                                suggested_rect.top,
                                suggested_rect.left + target_width,
                                suggested_rect.top + target_height,
                            )
                        cursor_pos = _get_cursor_position(user32)
                        user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
                        user32.GetAsyncKeyState.restype = wintypes.SHORT
                        is_dragging = (
                            hwnd in _RESIZE_OVERLAY_IN_SIZING
                            or bool(user32.GetAsyncKeyState(1) & 0x8000)
                        )
                        stable_bounds = preserve_window_size_on_dpi_change(
                            (
                                current_rect.left,
                                current_rect.top,
                                current_rect.right,
                                current_rect.bottom,
                            ),
                            suggested_bounds,
                            cursor_pos=cursor_pos,
                            is_dragging=is_dragging,
                            maximized=bool(user32.IsZoomed(window_handle)),
                            grab_ratio=_ACTIVE_DRAG_ANCHOR_RATIOS.get(hwnd),
                        )
                        if is_dragging and cursor_pos is not None:
                            _ACTIVE_DPI_DRAG_GEOMETRY[hwnd] = (
                                stable_bounds[2] - stable_bounds[0],
                                stable_bounds[3] - stable_bounds[1],
                                cursor_pos[0] - stable_bounds[0],
                                cursor_pos[1] - stable_bounds[1],
                            )
                            # WebView mouse-up is not reliably delivered to
                            # the top-level window. Poll until release so a
                            # stale drag lock cannot affect later operations.
                            user32.SetTimer(
                                hwnd,
                                _DPI_DRAG_TIMER_ID,
                                16,
                                None,
                            )
                        dpi_change_rect = wintypes.RECT(*stable_bounds)
                        previous_l_param = ctypes.addressof(dpi_change_rect)

            if message == WM_WINDOWPOSCHANGING and l_param:
                drag_geometry = _ACTIVE_DPI_DRAG_GEOMETRY.get(hwnd)
                if drag_geometry is not None:
                    user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
                    user32.GetAsyncKeyState.restype = wintypes.SHORT
                    button_down = bool(user32.GetAsyncKeyState(1) & 0x8000)
                    if button_down:
                        _DPI_DRAG_RELEASE_DEADLINES.pop(hwnd, None)
                    else:
                        _schedule_drag_release(hwnd)
                    cursor_pos = _get_cursor_position(user32)
                    if cursor_pos is not None:
                        width, height, grab_offset_x, grab_offset_y = drag_geometry
                        window_pos = ctypes.cast(
                            ctypes.c_void_p(l_param),
                            ctypes.POINTER(_WindowPos),
                        ).contents
                        window_pos.x = cursor_pos[0] - grab_offset_x
                        window_pos.y = cursor_pos[1] - grab_offset_y
                        window_pos.cx = width
                        window_pos.cy = height
                        window_pos.flags &= ~(SWP_NOMOVE | SWP_NOSIZE)
                        return 0

            if message in (WM_LBUTTONUP, WM_NCLBUTTONUP, WM_CAPTURECHANGED):
                _schedule_drag_release(hwnd)

            if message == WM_NCHITTEST:
                rect = wintypes.RECT()
                if user32.GetWindowRect(window_handle, ctypes.byref(rect)):
                    border_size, header_height, actions_exclusion_width = (
                        calculate_resize_metrics(_get_window_dpi(user32, window_handle))
                    )
                    cursor_x = ctypes.c_short(l_param & 0xFFFF).value
                    cursor_y = ctypes.c_short((l_param >> 16) & 0xFFFF).value
                    hit_test = calculate_window_hit_test(
                        rect.left,
                        rect.top,
                        rect.right,
                        rect.bottom,
                        cursor_x,
                        cursor_y,
                        border_size,
                        header_height,
                        actions_exclusion_width,
                        bool(user32.IsZoomed(window_handle)),
                    )
                    if hit_test is not None:
                        return hit_test

            if message == WM_NCCALCSIZE:
                # Keep the frameless client area edge-to-edge.  The dedicated
                # same-process resize overlay handles the border before the
                # out-of-process WebView child can consume the pointer.
                return 0

            if message == WM_GETMINMAXINFO:
                result = call_previous(window_handle, message, w_param, l_param)
                _set_maximized_work_area(window_handle, l_param)
                return result

            if message == WM_TIMER and w_param == _RESIZE_OVERLAY_TIMER_ID:
                _service_resize_overlay_timer(hwnd)
                return 0

            if message == WM_TIMER and w_param == _DPI_DRAG_TIMER_ID:
                user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
                user32.GetAsyncKeyState.restype = wintypes.SHORT
                if user32.GetAsyncKeyState(1) & 0x8000:
                    _DPI_DRAG_RELEASE_DEADLINES.pop(hwnd, None)
                else:
                    _schedule_drag_release(hwnd)
                    deadline = _DPI_DRAG_RELEASE_DEADLINES.get(hwnd)
                    if deadline is not None and time.monotonic() >= deadline:
                        _end_active_drag(user32, hwnd)
                return 0

            if message == WM_ENTERSIZEMOVE:
                _ACTIVE_DPI_DRAG_GEOMETRY.pop(hwnd, None)
                _RESIZE_OVERLAY_IN_SIZING.add(hwnd)

            result = call_previous(
                window_handle, message, w_param, previous_l_param
            )
            if message == WM_EXITSIZEMOVE:
                _RESIZE_OVERLAY_IN_SIZING.discard(hwnd)
                _end_active_drag(user32, hwnd)
                _sync_resize_overlay(hwnd)
            elif (
                message in (WM_SIZE, WM_DPICHANGED)
                and hwnd not in _RESIZE_OVERLAY_IN_SIZING
            ):
                if _RESIZE_OVERLAYS.get(hwnd):
                    _sync_resize_overlay(hwnd)
                else:
                    _schedule_resize_overlay(hwnd)
            if (
                message == WM_SIZE
                and int(w_param) == 0
                and hwnd not in _ACTIVE_DPI_DRAG_GEOMETRY
                and not user32.IsZoomed(window_handle)
            ):
                _remember_logical_window_size(
                    user32,
                    hwnd,
                    _get_window_dpi(user32, window_handle),
                )
            if message == WM_NCDESTROY:
                overlay_hwnd = _RESIZE_OVERLAYS.pop(hwnd, None)
                if overlay_hwnd:
                    user32.DestroyWindow(overlay_hwnd)
                user32.KillTimer(hwnd, _RESIZE_OVERLAY_TIMER_ID)
                user32.KillTimer(hwnd, _DPI_DRAG_TIMER_ID)
                _RESIZE_OVERLAY_TIMER_ATTEMPTS.pop(hwnd, None)
                _RESIZE_OVERLAY_IN_SIZING.discard(hwnd)
                _clear_active_drag_state(hwnd)
                _SUBCLASSES.pop(hwnd, None)
                _WINDOW_DPI.pop(hwnd, None)
                _WINDOW_LOGICAL_SIZE.pop(hwnd, None)
                _WINDOW_ICON_HANDLES.pop(hwnd, None)
            return result
        except Exception:
            LOGGER.debug("Native window hit-test failed", exc_info=True)
            return call_previous(window_handle, message, w_param, l_param)

    callback = wnd_proc_type(window_proc)
    previous_after_set = user32.SetWindowLongPtrW(
        hwnd, GWL_WNDPROC, ctypes.cast(callback, ctypes.c_void_p)
    )
    previous_after_set_value = (
        previous_after_set.value
        if isinstance(previous_after_set, ctypes.c_void_p)
        else int(previous_after_set)
    )
    if previous_after_set_value and previous_after_set_value != previous_value:
        LOGGER.debug("Native window procedure changed during installation")
    _SUBCLASSES[hwnd] = (callback, previous_value)


def _set_maximized_work_area(hwnd: int, l_param: int) -> None:
    user32 = _user32
    user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
    user32.MonitorFromWindow.restype = ctypes.c_void_p
    user32.GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.POINTER(_MonitorInfo)]
    user32.GetMonitorInfoW.restype = wintypes.BOOL

    monitor = user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
    if not monitor:
        return

    monitor_info = _MonitorInfo()
    monitor_info.cbSize = ctypes.sizeof(_MonitorInfo)
    if not user32.GetMonitorInfoW(monitor, ctypes.byref(monitor_info)):
        return

    min_max_info = ctypes.cast(
        ctypes.c_void_p(l_param), ctypes.POINTER(_MinMaxInfo)
    ).contents
    max_x, max_y, max_width, max_height = calculate_maximized_work_area(
        (
            monitor_info.rcMonitor.left,
            monitor_info.rcMonitor.top,
            monitor_info.rcMonitor.right,
            monitor_info.rcMonitor.bottom,
        ),
        (
            monitor_info.rcWork.left,
            monitor_info.rcWork.top,
            monitor_info.rcWork.right,
            monitor_info.rcWork.bottom,
        ),
    )
    min_max_info.ptMaxPosition.x = max_x
    min_max_info.ptMaxPosition.y = max_y
    min_max_info.ptMaxSize.x = max_width
    min_max_info.ptMaxSize.y = max_height
    min_max_info.ptMaxTrackSize.x = max_width
    min_max_info.ptMaxTrackSize.y = max_height

    # pywebview/WinForms reports ``min_size`` in logical pixels and scales it
    # on every monitor.  Keep the native tracking floor in physical pixels so
    # moving a restored window to a higher-DPI monitor does not resize it just
    # to satisfy a newly scaled minimum.
    min_max_info.ptMinTrackSize.x = min(WINDOW_MIN_TRACK_WIDTH, max_width)
    min_max_info.ptMinTrackSize.y = min(WINDOW_MIN_TRACK_HEIGHT, max_height)


class _Margins(ctypes.Structure):
    _fields_ = [
        ("cxLeftWidth", ctypes.c_int),
        ("cxRightWidth", ctypes.c_int),
        ("cyTopHeight", ctypes.c_int),
        ("cyBottomHeight", ctypes.c_int),
    ]


DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWCP_ROUND = 2


def _extend_frame_into_client_area(hwnd: int) -> None:
    try:
        dwmapi = ctypes.WinDLL("dwmapi", use_last_error=True)
        # Margin of 1 enables DWM composition, Windows 11 rounded corners and drop shadow
        margins = _Margins(1, 1, 1, 1)
        dwmapi.DwmExtendFrameIntoClientArea(hwnd, ctypes.byref(margins))

        # Explicitly request native Windows 11 rounded corners (Build 22000+)
        corner_pref = ctypes.c_int(DWMWCP_ROUND)
        dwmapi.DwmSetWindowAttribute(
            hwnd,
            DWMWA_WINDOW_CORNER_PREFERENCE,
            ctypes.byref(corner_pref),
            ctypes.sizeof(corner_pref),
        )
    except Exception as err:
        LOGGER.debug("DwmExtendFrameIntoClientArea failed: %s", err)


def _configure_resize_overlay_api(user32) -> None:
    global _CURSOR_API_CONFIGURED, _RESIZE_OVERLAY_API_CONFIGURED
    if _RESIZE_OVERLAY_API_CONFIGURED:
        return

    user32.GetParent.argtypes = [wintypes.HWND]
    user32.GetParent.restype = wintypes.HWND
    user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.GetClientRect.restype = wintypes.BOOL
    user32.GetCursorPos.argtypes = [ctypes.POINTER(_Point)]
    user32.GetCursorPos.restype = wintypes.BOOL
    _CURSOR_API_CONFIGURED = True
    user32.IsZoomed.argtypes = [wintypes.HWND]
    user32.IsZoomed.restype = wintypes.BOOL
    user32.IsWindow.argtypes = [wintypes.HWND]
    user32.IsWindow.restype = wintypes.BOOL
    user32.PostMessageW.argtypes = [
        wintypes.HWND,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
    ]
    user32.PostMessageW.restype = wintypes.BOOL
    user32.ReleaseCapture.argtypes = []
    user32.ReleaseCapture.restype = wintypes.BOOL
    user32.ScreenToClient.argtypes = [
        wintypes.HWND,
        ctypes.POINTER(_Point),
    ]
    user32.ScreenToClient.restype = wintypes.BOOL
    user32.SetWindowPos.argtypes = [
        wintypes.HWND,
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    ]
    user32.SetWindowPos.restype = wintypes.BOOL
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.ShowWindow.restype = wintypes.BOOL
    user32.SetTimer.argtypes = [
        wintypes.HWND,
        ctypes.c_void_p,
        wintypes.UINT,
        ctypes.c_void_p,
    ]
    user32.SetTimer.restype = ctypes.c_void_p
    user32.KillTimer.argtypes = [wintypes.HWND, ctypes.c_void_p]
    user32.KillTimer.restype = wintypes.BOOL
    user32.SetWindowRgn.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wintypes.BOOL]
    user32.SetWindowRgn.restype = ctypes.c_int
    user32.CreateWindowExW.argtypes = [
        wintypes.DWORD,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.DWORD,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.HWND,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
    ]
    user32.CreateWindowExW.restype = wintypes.HWND
    user32.DestroyWindow.argtypes = [wintypes.HWND]
    user32.DestroyWindow.restype = wintypes.BOOL
    user32.DefWindowProcW.argtypes = [
        wintypes.HWND,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
    ]
    user32.DefWindowProcW.restype = ctypes.c_ssize_t
    user32.LoadCursorW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    user32.LoadCursorW.restype = ctypes.c_void_p
    user32.SetCursor.argtypes = [ctypes.c_void_p]
    user32.SetCursor.restype = ctypes.c_void_p
    if _gdi32:
        _gdi32.CreateRectRgn.argtypes = [
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
        ]
        _gdi32.CreateRectRgn.restype = ctypes.c_void_p
        _gdi32.CombineRgn.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_int,
        ]
        _gdi32.CombineRgn.restype = ctypes.c_int
        _gdi32.DeleteObject.argtypes = [ctypes.c_void_p]
        _gdi32.DeleteObject.restype = wintypes.BOOL
    _RESIZE_OVERLAY_API_CONFIGURED = True


def _resize_overlay_dimensions(user32, parent_hwnd: int) -> tuple[int, int]:
    rect = wintypes.RECT()
    if not user32.GetClientRect(parent_hwnd, ctypes.byref(rect)):
        return 0, 0
    return max(0, int(rect.right - rect.left)), max(0, int(rect.bottom - rect.top))


def _resize_overlay_hit_test(user32, parent_hwnd: int, l_param: int) -> int | None:
    width, height = _resize_overlay_dimensions(user32, parent_hwnd)
    if not width or not height:
        return None

    border_size = calculate_resize_metrics(
        _get_window_dpi(user32, parent_hwnd)
    )[0]
    cursor_x = ctypes.c_short(l_param & 0xFFFF).value
    cursor_y = ctypes.c_short((l_param >> 16) & 0xFFFF).value
    return calculate_resize_hit_test(
        0,
        0,
        width,
        height,
        cursor_x,
        cursor_y,
        border_size,
        bool(user32.IsZoomed(parent_hwnd)),
    )


def _resize_cursor_id(hit_test: int) -> int | None:
    if hit_test in (HTLEFT, HTRIGHT):
        return IDC_SIZEWE
    if hit_test in (HTTOP, HTBOTTOM):
        return IDC_SIZENS
    if hit_test in (HTTOPLEFT, HTBOTTOMRIGHT):
        return IDC_SIZENWSE
    if hit_test in (HTTOPRIGHT, HTBOTTOMLEFT):
        return IDC_SIZENESW
    return None


def _set_resize_overlay_region(user32, parent_hwnd: int, overlay_hwnd: int) -> None:
    width, height = _resize_overlay_dimensions(user32, parent_hwnd)
    border_size = calculate_resize_metrics(
        _get_window_dpi(user32, parent_hwnd)
    )[0]
    if width <= border_size * 2 or height <= border_size * 2:
        user32.ShowWindow(overlay_hwnd, SW_HIDE)
        return

    gdi32 = _gdi32
    if not gdi32:
        return

    outer = gdi32.CreateRectRgn(0, 0, width, height)
    inner = gdi32.CreateRectRgn(
        border_size,
        border_size,
        width - border_size,
        height - border_size,
    )
    if not outer or not inner:
        if outer:
            gdi32.DeleteObject(outer)
        if inner:
            gdi32.DeleteObject(inner)
        return

    gdi32.CombineRgn(outer, outer, inner, RGN_DIFF)
    gdi32.DeleteObject(inner)
    if not user32.SetWindowRgn(overlay_hwnd, outer, True):
        gdi32.DeleteObject(outer)


def _sync_resize_overlay(parent_hwnd: int) -> None:
    overlay_hwnd = _RESIZE_OVERLAYS.get(parent_hwnd)
    if not overlay_hwnd or not _user32:
        return

    user32 = _user32
    try:
        _configure_resize_overlay_api(user32)
        if not user32.IsWindow(overlay_hwnd):
            _RESIZE_OVERLAYS.pop(parent_hwnd, None)
            _schedule_resize_overlay(parent_hwnd)
            return
        width, height = _resize_overlay_dimensions(user32, parent_hwnd)
        if not width or not height or user32.IsZoomed(parent_hwnd):
            user32.ShowWindow(overlay_hwnd, SW_HIDE)
            return

        user32.SetWindowPos(
            overlay_hwnd,
            HWND_TOP,
            0,
            0,
            width,
            height,
            SWP_NOACTIVATE | SWP_SHOWWINDOW,
        )
        _set_resize_overlay_region(user32, parent_hwnd, overlay_hwnd)
        user32.ShowWindow(overlay_hwnd, SW_SHOWNA)
    except (OSError, TypeError, ValueError):
        LOGGER.debug("Failed to sync native resize overlay", exc_info=True)


def _schedule_resize_overlay(parent_hwnd: int) -> None:
    if not _user32:
        return
    try:
        _configure_resize_overlay_api(_user32)
        _RESIZE_OVERLAY_TIMER_ATTEMPTS[parent_hwnd] = 0
        _user32.SetTimer(
            parent_hwnd,
            _RESIZE_OVERLAY_TIMER_ID,
            400,
            None,
        )
    except (OSError, TypeError, ValueError):
        LOGGER.debug("Failed to schedule native resize overlay", exc_info=True)


def _service_resize_overlay_timer(parent_hwnd: int) -> None:
    if not _user32:
        return

    attempts = _RESIZE_OVERLAY_TIMER_ATTEMPTS.get(parent_hwnd, 0) + 1
    _RESIZE_OVERLAY_TIMER_ATTEMPTS[parent_hwnd] = attempts
    overlay_hwnd = _RESIZE_OVERLAYS.get(parent_hwnd)
    if overlay_hwnd and _user32.IsWindow(overlay_hwnd):
        if attempts >= 20:
            _user32.KillTimer(parent_hwnd, _RESIZE_OVERLAY_TIMER_ID)
            _RESIZE_OVERLAY_TIMER_ATTEMPTS.pop(parent_hwnd, None)
        return
    if overlay_hwnd:
        _RESIZE_OVERLAYS.pop(parent_hwnd, None)

    _install_resize_overlay(parent_hwnd)
    if attempts >= 20:
        _user32.KillTimer(parent_hwnd, _RESIZE_OVERLAY_TIMER_ID)
        _RESIZE_OVERLAY_TIMER_ATTEMPTS.pop(parent_hwnd, None)


def _resize_overlay_window_proc(window_handle, message, w_param, l_param):
    user32 = _user32
    if not user32:
        return 0

    try:
        _configure_resize_overlay_api(user32)
        parent_hwnd = user32.GetParent(window_handle)
        if message == WM_LBUTTONDOWN and parent_hwnd:
            hit_test = _resize_overlay_hit_test(user32, parent_hwnd, l_param)
            if hit_test is not None:
                cursor_position = _get_cursor_position(user32)
                if cursor_position is not None:
                    user32.ReleaseCapture()
                    user32.PostMessageW(
                        parent_hwnd,
                        WM_NCLBUTTONDOWN,
                        hit_test,
                        _pack_screen_point(*cursor_position),
                    )
                    return 0

        if message == WM_SETCURSOR and parent_hwnd:
            cursor_position = _get_cursor_position(user32)
            if cursor_position is not None:
                point = _Point(*cursor_position)
                if user32.ScreenToClient(parent_hwnd, ctypes.byref(point)):
                    hit_test = _resize_overlay_hit_test(
                        user32,
                        parent_hwnd,
                        _pack_screen_point(point.x, point.y),
                    )
                    cursor_id = _resize_cursor_id(hit_test) if hit_test else None
                    if cursor_id is not None:
                        resource = ctypes.cast(
                            ctypes.c_void_p(cursor_id), wintypes.LPCWSTR
                        )
                        cursor = user32.LoadCursorW(None, resource)
                        if cursor:
                            user32.SetCursor(cursor)
                            return 1

        if message == WM_MOUSEACTIVATE:
            return MA_NOACTIVATE
        if message == WM_ERASEBKGND:
            return 1
        if message == WM_NCHITTEST:
            return HTCLIENT
        return user32.DefWindowProcW(window_handle, message, w_param, l_param)
    except Exception:
        LOGGER.debug("Native resize overlay message failed", exc_info=True)
        return user32.DefWindowProcW(window_handle, message, w_param, l_param)


def _ensure_resize_overlay_class() -> bool:
    global _RESIZE_OVERLAY_CLASS_REGISTERED, _RESIZE_OVERLAY_WNDPROC
    if _RESIZE_OVERLAY_CLASS_REGISTERED:
        return True

    user32 = _user32
    if not user32:
        return False

    user32.RegisterClassW.argtypes = [ctypes.POINTER(_ResizeOverlayClass)]
    user32.RegisterClassW.restype = wintypes.WORD
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
    kernel32.GetModuleHandleW.restype = ctypes.c_void_p
    instance = kernel32.GetModuleHandleW(None)

    wnd_proc_type = ctypes.WINFUNCTYPE(
        ctypes.c_ssize_t,
        wintypes.HWND,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
    )
    callback = wnd_proc_type(_resize_overlay_window_proc)
    class_info = _ResizeOverlayClass()
    class_info.lpfnWndProc = ctypes.cast(callback, ctypes.c_void_p)
    class_info.hInstance = instance
    class_info.lpszClassName = _RESIZE_OVERLAY_CLASS_NAME
    atom = user32.RegisterClassW(ctypes.byref(class_info))
    if not atom and ctypes.get_last_error() != 1410:
        return False

    _RESIZE_OVERLAY_WNDPROC = callback
    _RESIZE_OVERLAY_CLASS_REGISTERED = True
    return True


def _install_resize_overlay(parent_hwnd: int) -> bool:
    existing_overlay = _RESIZE_OVERLAYS.get(parent_hwnd)
    if existing_overlay:
        if _user32.IsWindow(existing_overlay):
            _sync_resize_overlay(parent_hwnd)
            return True
        _RESIZE_OVERLAYS.pop(parent_hwnd, None)
    if not _ensure_resize_overlay_class():
        return False

    user32 = _user32
    _configure_resize_overlay_api(user32)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
    kernel32.GetModuleHandleW.restype = ctypes.c_void_p
    overlay_hwnd = user32.CreateWindowExW(
        WS_EX_NOACTIVATE | WS_EX_TRANSPARENT,
        _RESIZE_OVERLAY_CLASS_NAME,
        None,
        WS_CHILD | WS_VISIBLE,
        0,
        0,
        0,
        0,
        parent_hwnd,
        None,
        kernel32.GetModuleHandleW(None),
        None,
    )
    if not overlay_hwnd:
        return False

    overlay_value = int(overlay_hwnd)
    _RESIZE_OVERLAYS[parent_hwnd] = overlay_value
    _sync_resize_overlay(parent_hwnd)
    return True


def install_native_resize_support(window) -> bool:
    """Enable native resize hit-testing and monitor-aware maximization."""
    if os.name != "nt":
        return False

    hwnd = _window_handle(window)
    if not hwnd:
        return False

    try:
        already_installed = hwnd in _SUBCLASSES
        _install_wnd_proc(hwnd)
        if not already_installed:
            _install_resize_style(hwnd)
            _extend_frame_into_client_area(hwnd)
        installed = _install_resize_overlay(hwnd)
        _schedule_resize_overlay(hwnd)
        return installed
    except (AttributeError, OSError, TypeError, ValueError) as error:
        LOGGER.warning("Failed to enable native window resize support: %s", error)
        return False


__all__ = [
    "begin_native_drag",
    "begin_native_resize",
    "calculate_restored_grab_offset",
    "calculate_maximized_work_area",
    "calculate_resize_metrics",
    "calculate_resize_hit_test",
    "calculate_window_hit_test",
    "prepare_native_drag",
    "move_window_by_drag_delta",
    "set_window_identity",
    "install_native_resize_support",
    "preserve_window_size_on_dpi_change",
]
