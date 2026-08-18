"""Unified window capture engine for Maple Classic Reporter.

Provides occlusion-free window recording using Windows Graphics Capture (WGC)
with automatic fallback to MSS screen-coordinate capture when WGC is unavailable.
"""

import ctypes
from ctypes import wintypes
import logging
import threading
import time
from typing import Callable, Optional, Tuple

import cv2
import mss
import numpy as np
import pygetwindow as gw

from maple_reporter.recorder.window_recorder import (
    find_window_bounds,
    normalize_window_title_keyword,
)

LOGGER = logging.getLogger(__name__)


def find_target_hwnd(window_title_keyword: str) -> Optional[int]:
    """Find the Win32 window HWND matching the specified keyword or title."""
    keyword = normalize_window_title_keyword(window_title_keyword).strip()
    if not keyword:
        return None

    # Priority 1: pygetwindow matching (identical to find_window_bounds)
    try:
        visible_windows = [
            w for w in gw.getAllWindows()
            if getattr(w, "title", "") and getattr(w, "_hWnd", None)
        ]
        # Pass 1: Exact title
        for w in visible_windows:
            if w.title == keyword:
                return getattr(w, "_hWnd", None)
        # Pass 2: Case-insensitive exact
        for w in visible_windows:
            if w.title.strip().lower() == keyword.lower():
                return getattr(w, "_hWnd", None)
        # Pass 3: Substring
        for w in visible_windows:
            if "maplestory classic auto reporter" in w.title.lower():
                continue
            if keyword.lower() in w.title.lower():
                return getattr(w, "_hWnd", None)
    except Exception as err:
        LOGGER.debug("pygetwindow search error: %s", err)

    # Priority 2: Native EnumWindows
    matched_windows: list[tuple[int, str]] = []

    def enum_window_callback(hwnd: int, lparam: int) -> bool:
        if not ctypes.windll.user32.IsWindow(hwnd):
            return True
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        if length > 0:
            buff = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buff, length + 1)
            title = buff.value.strip()
            if title and "maplestory classic auto reporter" not in title.casefold():
                matched_windows.append((hwnd, title))
        return True

    try:
        enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)(
            enum_window_callback
        )
        ctypes.windll.user32.EnumWindows(enum_proc, 0)

        # Pass 1: Exact title match
        for hwnd, title in matched_windows:
            if title == keyword:
                return hwnd

        # Pass 2: Case-insensitive exact match
        for hwnd, title in matched_windows:
            if title.casefold() == keyword.casefold():
                return hwnd

        # Pass 3: Substring match
        for hwnd, title in matched_windows:
            if keyword.casefold() in title.casefold():
                return hwnd
    except Exception as err:
        LOGGER.debug("EnumWindows search error: %s", err)

    return None


def restore_and_focus_window(hwnd: int) -> bool:
    """Ensure the target window is restored from minimized state and brought to front."""
    if not hwnd or not ctypes.windll.user32.IsWindow(hwnd):
        return False
    try:
        # Check if minimized (IsIconic)
        if ctypes.windll.user32.IsIconic(hwnd):
            ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            time.sleep(0.05)
        ctypes.windll.user32.SetForegroundWindow(hwnd)
        return True
    except Exception as error:
        LOGGER.debug("還原並置頂視窗失敗 (%s)", type(error).__name__)
        return False


def get_client_relative_crop(
    hwnd: int, captured_width: int, captured_height: int
) -> Tuple[int, int, int, int]:
    """Calculate (x, y, width, height) to crop client area from full-window WGC frame."""
    if not hwnd or captured_width <= 0 or captured_height <= 0:
        return (0, 0, captured_width, captured_height)

    try:
        # Window outer bounds (DWM or GetWindowRect)
        win_rect = wintypes.RECT()
        DWMWA_EXTENDED_FRAME_BOUNDS = 9
        res = ctypes.windll.dwmapi.DwmGetWindowAttribute(
            wintypes.HWND(hwnd),
            wintypes.DWORD(DWMWA_EXTENDED_FRAME_BOUNDS),
            ctypes.byref(win_rect),
            ctypes.sizeof(win_rect),
        )
        if res != 0:
            ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(win_rect))

        # Client screen origin and size
        client_rect = wintypes.RECT()
        client_pt = wintypes.POINT(0, 0)
        ctypes.windll.user32.GetClientRect(hwnd, ctypes.byref(client_rect))
        ctypes.windll.user32.ClientToScreen(hwnd, ctypes.byref(client_pt))

        client_w = client_rect.right - client_rect.left
        client_h = client_rect.bottom - client_rect.top

        if client_w <= 10 or client_h <= 10:
            return (0, 0, captured_width, captured_height)

        # Calculate offset relative to window top-left
        offset_x = max(0, client_pt.x - win_rect.left)
        offset_y = max(0, client_pt.y - win_rect.top)

        # Clamp within captured bounds
        crop_x = min(offset_x, max(0, captured_width - 1))
        crop_y = min(offset_y, max(0, captured_height - 1))
        crop_w = min(client_w, captured_width - crop_x)
        crop_h = min(client_h, captured_height - crop_y)

        # Make even dimensions for video codecs
        crop_w -= crop_w % 2
        crop_h -= crop_h % 2

        if crop_w >= 10 and crop_h >= 10:
            return (crop_x, crop_y, crop_w, crop_h)
    except Exception as error:
        LOGGER.debug("計算 Client Area 裁切邊界失敗 (%s)", type(error).__name__)

    return (0, 0, captured_width, captured_height)


class UnifiedWindowCapture:
    """Unified capture coordinator supporting WGC hardware capture and MSS fallback."""

    def __init__(
        self,
        fallback_callback: Optional[Callable[[str], None]] = None,
    ):
        self._fallback_callback = fallback_callback
        self._wgc_capture = None
        self._wgc_control = None
        self._latest_frame: Optional[np.ndarray] = None
        self._latest_timestamp: float = 0.0
        self._lock = threading.Lock()
        self._is_wgc_active = False
        self._is_running = False
        self._current_hwnd: Optional[int] = None
        self._window_title_keyword: str = ""
        self._stop_event = threading.Event()
        self._mss_thread: Optional[threading.Thread] = None

    @property
    def is_wgc_active(self) -> bool:
        return self._is_wgc_active

    def grab_single_frame(
        self, window_title_keyword: str
    ) -> Tuple[Optional[np.ndarray], bool]:
        """Capture a single frame of the target window.

        Returns (frame_bgr, is_wgc). If capture fails, returns (None, False).
        """
        hwnd = find_target_hwnd(window_title_keyword)
        if hwnd:
            restore_and_focus_window(hwnd)

        # Try WGC single-frame capture first
        if hwnd:
            frame = self._try_wgc_single_frame(hwnd)
            if frame is not None:
                return frame, True

        # Fallback to MSS screen capture
        frame = self._grab_mss_single_frame(window_title_keyword)
        if frame is not None and self._fallback_callback:
            try:
                self._fallback_callback("已切換為相容截圖模式")
            except Exception:
                pass
        return frame, False

    def _try_wgc_single_frame(self, hwnd: int) -> Optional[np.ndarray]:
        try:
            import windows_capture

            captured_frame = None
            frame_event = threading.Event()

            capture = windows_capture.WindowsCapture(
                cursor_capture=True,
                draw_border=False,
                window_hwnd=hwnd,
            )

            @capture.event
            def on_frame_arrived(frame, control):
                nonlocal captured_frame
                try:
                    bgr_frame = frame.convert_to_bgr()
                    bgr = getattr(bgr_frame, "frame_buffer", bgr_frame)
                    if isinstance(bgr, np.ndarray) and bgr.size > 0:
                        h, w = bgr.shape[:2]
                        cx, cy, cw, ch = get_client_relative_crop(hwnd, w, h)
                        if cw > 10 and ch > 10 and cx + cw <= w and cy + ch <= h:
                            captured_frame = np.ascontiguousarray(bgr[cy : cy + ch, cx : cx + cw])
                        else:
                            captured_frame = np.ascontiguousarray(bgr)
                except Exception as frame_err:
                    LOGGER.warning("WGC 單張影格處理異常: %s", frame_err)
                    captured_frame = None
                finally:
                    control.stop()
                    frame_event.set()

            @capture.event
            def on_closed():
                frame_event.set()

            control = capture.start_free_threaded()
            frame_event.wait(timeout=1.5)
            try:
                control.stop()
            except Exception:
                pass
            return captured_frame
        except Exception as error:
            LOGGER.warning("WGC 單張截圖未成功 (%s: %s)", type(error).__name__, error, exc_info=True)
            return None

    def _grab_mss_single_frame(
        self, window_title_keyword: str
    ) -> Optional[np.ndarray]:
        bounds = find_window_bounds(window_title_keyword)
        if not bounds:
            return None
        left, top, width, height = bounds
        width -= width % 2
        height -= height % 2
        if width < 2 or height < 2:
            return None

        try:
            with mss.MSS() as screen:
                monitor = {"left": left, "top": top, "width": width, "height": height}
                sct_img = screen.grab(monitor)
                raw = np.asarray(sct_img)
                return cv2.cvtColor(raw, cv2.COLOR_BGRA2BGR)
        except Exception as error:
            LOGGER.warning("MSS 截圖失敗 (%s)", type(error).__name__)
            return None

    def start_stream(
        self,
        window_title_keyword: str,
        fps: int = 20,
    ) -> bool:
        """Start continuous frame streaming for recording or replay buffer."""
        self.stop_stream()
        self._window_title_keyword = window_title_keyword
        self._stop_event.clear()
        self._is_running = True

        hwnd = find_target_hwnd(window_title_keyword)
        if hwnd:
            restore_and_focus_window(hwnd)

        # Attempt WGC stream by HWND
        if hwnd:
            if self._start_wgc_stream(hwnd=hwnd):
                self._is_wgc_active = True
                self._current_hwnd = hwnd
                LOGGER.info("WGC 獨立視窗錄影成功啟動 (HWND=%s)", hwnd)
                return True

        # Attempt WGC stream by window name keyword
        clean_title = normalize_window_title_keyword(window_title_keyword)
        if clean_title:
            if self._start_wgc_stream(window_name=clean_title, hwnd=hwnd):
                self._is_wgc_active = True
                LOGGER.info("WGC 獨立視窗錄影以視窗名稱成功啟動 (%s)", clean_title)
                return True

        # Fallback to MSS stream
        LOGGER.warning("WGC 初始化未果，以 MSS 相容模式啟動視窗錄製串流 (%s)", window_title_keyword)
        self._is_wgc_active = False
        if self._fallback_callback:
            try:
                self._fallback_callback("已切換為相容截圖模式")
            except Exception:
                pass
        self._start_mss_stream(window_title_keyword, fps)
        return True

    def _start_wgc_stream(
        self, hwnd: Optional[int] = None, window_name: Optional[str] = None
    ) -> bool:
        try:
            import windows_capture

            attempts = [
                {"draw_border": False, "cursor_capture": True},
                {"draw_border": None, "cursor_capture": True},
            ]

            last_error = None
            for opts in attempts:
                capture_kwargs = dict(opts)
                if hwnd:
                    capture_kwargs["window_hwnd"] = hwnd
                elif window_name:
                    capture_kwargs["window_name"] = window_name
                else:
                    return False

                try:
                    capture = windows_capture.WindowsCapture(**capture_kwargs)

                    first_frame_logged = False

                    @capture.event
                    def on_frame_arrived(frame, control):
                        nonlocal first_frame_logged
                        if self._stop_event.is_set():
                            control.stop()
                            return
                        try:
                            bgr_frame = frame.convert_to_bgr()
                            bgr = getattr(bgr_frame, "frame_buffer", bgr_frame)
                            if isinstance(bgr, np.ndarray) and bgr.size > 0:
                                h, w = bgr.shape[:2]
                                target_hwnd = hwnd or (self._current_hwnd if self._current_hwnd else 0)
                                cx, cy, cw, ch = get_client_relative_crop(target_hwnd, w, h)
                                if cw > 10 and ch > 10 and cx + cw <= w and cy + ch <= h:
                                    cropped = np.ascontiguousarray(bgr[cy : cy + ch, cx : cx + cw])
                                else:
                                    cropped = np.ascontiguousarray(bgr)

                                with self._lock:
                                    self._latest_frame = cropped
                                    self._latest_timestamp = time.monotonic()

                                if not first_frame_logged:
                                    first_frame_logged = True
                                    LOGGER.info("WGC 首幀接收成功 (shape=%s)", cropped.shape)
                        except Exception as frame_error:
                            LOGGER.warning("WGC frame 處理異常 (%s: %s)", type(frame_error).__name__, frame_error, exc_info=True)

                    @capture.event
                    def on_closed():
                        LOGGER.debug("WGC 視窗擷取連線關閉")

                    control = capture.start_free_threaded()
                    self._wgc_capture = capture
                    self._wgc_control = control

                    # Wait up to 2.0s to confirm first frame arrives
                    start_wait = time.time()
                    while time.time() - start_wait < 2.0:
                        with self._lock:
                            if self._latest_frame is not None:
                                return True
                        time.sleep(0.03)

                    with self._lock:
                        if self._latest_frame is not None:
                            return True

                    # Timeout on this attempt
                    self._cleanup_wgc()
                except Exception as attempt_error:
                    last_error = attempt_error
                    LOGGER.warning("WGC 嘗試失敗 (opts=%s): %s", opts, attempt_error)
                    self._cleanup_wgc()

            if last_error:
                LOGGER.warning("所有 WGC 啟動嘗試均未成功: %s", last_error, exc_info=True)
            return False
        except Exception as error:
            LOGGER.warning("啟動 WGC 串流總體失敗 (%s: %s)", type(error).__name__, error, exc_info=True)
            self._cleanup_wgc()
            return False

    def _start_mss_stream(self, window_title_keyword: str, fps: int) -> None:
        self._mss_thread = threading.Thread(
            target=self._mss_capture_loop,
            args=(window_title_keyword, fps),
            name="maple-mss-capture",
            daemon=True,
        )
        self._mss_thread.start()

    def _mss_capture_loop(self, window_title_keyword: str, fps: int) -> None:
        interval = 1.0 / max(1, fps)
        screen = None
        try:
            screen = mss.MSS()
            while not self._stop_event.is_set():
                loop_start = time.monotonic()
                bounds = find_window_bounds(window_title_keyword)
                if bounds:
                    left, top, width, height = bounds
                    width -= width % 2
                    height -= height % 2
                    if width >= 2 and height >= 2:
                        monitor = {
                            "left": left,
                            "top": top,
                            "width": width,
                            "height": height,
                        }
                        try:
                            sct_img = screen.grab(monitor)
                            raw = np.asarray(sct_img)
                            bgr = cv2.cvtColor(raw, cv2.COLOR_BGRA2BGR)
                            with self._lock:
                                self._latest_frame = bgr
                                self._latest_timestamp = loop_start
                        except Exception as grab_error:
                            LOGGER.debug("MSS grab error (%s)", type(grab_error).__name__)
                sleep_time = interval - (time.monotonic() - loop_start)
                if sleep_time > 0:
                    time.sleep(sleep_time)
        except Exception as error:
            LOGGER.warning("MSS 擷取迴圈終止 (%s)", type(error).__name__)
        finally:
            if screen is not None:
                try:
                    screen.close()
                except Exception:
                    pass

    def get_latest_frame(self) -> Tuple[Optional[np.ndarray], float]:
        """Return the most recently captured (frame_bgr, timestamp)."""
        with self._lock:
            if self._latest_frame is not None:
                return self._latest_frame.copy(), self._latest_timestamp
            return None, 0.0

    def _cleanup_wgc(self) -> None:
        if self._wgc_control is not None:
            try:
                self._wgc_control.stop()
            except Exception:
                pass
            self._wgc_control = None
        self._wgc_capture = None

    def stop_stream(self) -> None:
        """Stop running stream and release resources."""
        self._stop_event.set()
        self._is_running = False
        self._cleanup_wgc()
        if self._mss_thread and self._mss_thread.is_alive():
            if threading.current_thread() is not self._mss_thread:
                self._mss_thread.join(timeout=1.0)
        self._mss_thread = None
        with self._lock:
            self._latest_frame = None
            self._latest_timestamp = 0.0
            self._is_wgc_active = False


__all__ = [
    "UnifiedWindowCapture",
    "find_target_hwnd",
    "get_client_relative_crop",
    "restore_and_focus_window",
]
