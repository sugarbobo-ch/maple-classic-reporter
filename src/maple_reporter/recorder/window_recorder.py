import os
import re
import time
import logging
from typing import List, Optional, Tuple, Callable
import cv2
import numpy as np
import mss
import pygetwindow as gw
from PIL import Image

import ctypes
from ctypes import wintypes

from maple_reporter.recorder.audio_capture import (
    DEFAULT_SAMPLE_RATE,
    LoopbackAudioRecorder,
    merge_audio_into_mp4,
)


LOGGER = logging.getLogger(__name__)

PRIMARY_GAME_WINDOW_TITLE = "新楓之谷：經典版"
RELATED_GAME_WINDOW_TITLE_KEYWORD = "新楓之谷"
_WINDOW_DIMENSION_SUFFIX = re.compile(
    r"\s+\(\s*\d+\s*[x×]\s*\d+\s*\)\s*$", re.IGNORECASE
)


def _enable_per_monitor_dpi_awareness() -> None:
    """Make Windows client coordinates line up with MSS physical pixels."""
    if os.name != "nt":
        return

    try:
        set_context = ctypes.windll.user32.SetProcessDpiAwarenessContext
        set_context.argtypes = [ctypes.c_void_p]
        set_context.restype = wintypes.BOOL
        if set_context(ctypes.c_void_p(-3)):  # PER_MONITOR_AWARE
            return
    except (AttributeError, OSError, OverflowError, TypeError, ValueError):
        pass

    try:
        current_awareness = ctypes.c_int()
        get_awareness = ctypes.windll.shcore.GetProcessDpiAwareness
        if (
            get_awareness(0, ctypes.byref(current_awareness)) == 0
            and current_awareness.value == 2
        ):
            return
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PER_MONITOR_DPI_AWARE
    except (AttributeError, OSError, OverflowError, TypeError, ValueError) as error:
        LOGGER.debug("無法設定 Windows DPI awareness (%s)", type(error).__name__)


_enable_per_monitor_dpi_awareness()


def normalize_window_title_keyword(window_title_keyword: str) -> str:
    """Remove the UI-only ``(widthxheight)`` suffix from saved titles."""
    return _WINDOW_DIMENSION_SUFFIX.sub("", (window_title_keyword or "").strip()).strip()

def get_accurate_window_bounds(hwnd) -> Optional[Tuple[int, int, int, int]]:
    """Get exact window bounds excluding DWM drop shadow padding."""
    rect = wintypes.RECT()
    DWMWA_EXTENDED_FRAME_BOUNDS = 9
    try:
        res = ctypes.windll.dwmapi.DwmGetWindowAttribute(
            wintypes.HWND(hwnd),
            wintypes.DWORD(DWMWA_EXTENDED_FRAME_BOUNDS),
            ctypes.byref(rect),
            ctypes.sizeof(rect)
        )
        if res == 0:
            return (rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top)
    except Exception as error:
        LOGGER.debug("讀取 DWM 視窗邊界失敗 (%s)", type(error).__name__)

    try:
        ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
        return (rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top)
    except Exception as error:
        LOGGER.debug("讀取 Windows 視窗矩形失敗 (%s)", type(error).__name__)
        return None

def get_client_area_bounds(hwnd) -> Optional[Tuple[int, int, int, int]]:
    """
    Get inner client area bounds (excluding window titlebar and borders) mapped to screen coordinates.
    Returns (left, top, width, height).
    """
    rect = wintypes.RECT()
    pt = wintypes.POINT()
    try:
        res1 = ctypes.windll.user32.GetClientRect(hwnd, ctypes.byref(rect))
        res2 = ctypes.windll.user32.ClientToScreen(hwnd, ctypes.byref(pt))
        if res1 and res2 and rect.right > 50 and rect.bottom > 50:
            return (pt.x, pt.y, rect.right, rect.bottom)
    except Exception as error:
        LOGGER.debug("讀取 Windows client area 失敗 (%s)", type(error).__name__)
    return get_accurate_window_bounds(hwnd)

def _window_title_priority(title: str) -> int:
    normalized = normalize_window_title_keyword(title).casefold()
    if normalized == PRIMARY_GAME_WINDOW_TITLE.casefold():
        return 0
    if RELATED_GAME_WINDOW_TITLE_KEYWORD.casefold() in normalized:
        return 1
    if "maple" in normalized:
        return 2
    return 3


def order_window_candidates(windows: List[dict]) -> List[dict]:
    """Order windows with the exact Classic title first, then related titles."""
    return sorted(
        windows,
        key=lambda window: (
            _window_title_priority(str(window.get("title", ""))),
            str(window.get("title", "")).casefold(),
        ),
    )


def select_preferred_window_title(windows: List[dict], saved_title: str = "") -> str:
    """Choose the exact Classic title before other MapleStory windows."""
    if not windows:
        return ""

    for window in windows:
        title = str(window.get("title", ""))
        if normalize_window_title_keyword(title).casefold() == PRIMARY_GAME_WINDOW_TITLE.casefold():
            return title

    for window in windows:
        title = str(window.get("title", ""))
        if RELATED_GAME_WINDOW_TITLE_KEYWORD.casefold() in title.casefold():
            return title

    normalized_saved_title = normalize_window_title_keyword(saved_title).casefold()
    if normalized_saved_title:
        for window in windows:
            title = str(window.get("title", ""))
            if normalize_window_title_keyword(title).casefold() == normalized_saved_title:
                return title

    return str(windows[0].get("title", ""))


def get_active_windows() -> List[dict]:
    """Return visible windows with their actual client-area dimensions."""
    windows: List[dict] = []
    seen_titles: set[str] = set()

    for window in gw.getAllWindows():
        title = str(getattr(window, "title", "") or "").strip()
        if not title or not getattr(window, "visible", False):
            continue
        if getattr(window, "isMinimized", False):
            continue

        hwnd = getattr(window, "_hWnd", None)
        bounds = get_client_area_bounds(hwnd) if hwnd else None
        if bounds and bounds[2] > 100 and bounds[3] > 100:
            width, height = int(bounds[2]), int(bounds[3])
        else:
            try:
                width, height = int(window.width), int(window.height)
            except (AttributeError, TypeError, ValueError):
                continue

        if width <= 100 or height <= 100:
            continue

        title_key = title.casefold()
        if title_key in seen_titles:
            continue
        seen_titles.add(title_key)
        windows.append({"title": title, "width": width, "height": height})

    return order_window_candidates(windows)


def get_active_window_titles() -> List[str]:
    """Return a priority-ordered list of visible window titles."""
    return [window["title"] for window in get_active_windows()]

def focus_window(window_title_keyword: str) -> bool:
    """Bring the target window to the foreground."""
    window_title_keyword = normalize_window_title_keyword(window_title_keyword)
    if not window_title_keyword:
        return False
    visible_windows = [
        w for w in gw.getAllWindows()
        if w.title and w.visible and not getattr(w, 'isMinimized', False)
    ]
    target_window = None
    for w in visible_windows:
        if w.title == window_title_keyword:
            target_window = w
            break
    if not target_window:
        for w in visible_windows:
            if w.title.strip().lower() == window_title_keyword.strip().lower():
                target_window = w
                break
    if not target_window:
        for w in visible_windows:
            if "maplestory classic auto reporter" in w.title.lower():
                continue
            if window_title_keyword.lower() in w.title.lower():
                target_window = w
                break

    if target_window:
        hwnd = getattr(target_window, '_hWnd', None)
        if hwnd:
            try:
                ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                ctypes.windll.user32.SetForegroundWindow(hwnd)
                return True
            except Exception as error:
                LOGGER.debug("設定目標視窗為前景失敗 (%s)", type(error).__name__)
        try:
            target_window.activate()
            return True
        except Exception as error:
            LOGGER.debug("啟用目標視窗失敗 (%s)", type(error).__name__)
    return False

def find_window_bounds(window_title_keyword: str) -> Optional[Tuple[int, int, int, int]]:
    """
    Find accurate window bounding box (left, top, width, height) by exact title or keyword.
    Prioritizes exact title match over substring match to avoid selecting browser/IDE windows.
    """
    window_title_keyword = normalize_window_title_keyword(window_title_keyword)
    if not window_title_keyword:
        return None

    visible_windows = [
        w for w in gw.getAllWindows()
        if w.title and w.visible and not getattr(w, 'isMinimized', False) and w.width > 50 and w.height > 50
    ]

    target_window = None

    # Pass 1: Exact Title Match
    for w in visible_windows:
        if w.title == window_title_keyword:
            target_window = w
            break

    # Pass 2: Case-insensitive Exact Match
    if not target_window:
        for w in visible_windows:
            if w.title.strip().lower() == window_title_keyword.strip().lower():
                target_window = w
                break

    # Pass 3: Substring Match (excluding current app title)
    if not target_window:
        for w in visible_windows:
            if "maplestory classic auto reporter" in w.title.lower():
                continue
            if window_title_keyword.lower() in w.title.lower():
                target_window = w
                break

    if target_window:
        hwnd = getattr(target_window, '_hWnd', None)
        if hwnd:
            bounds = get_client_area_bounds(hwnd)
            if bounds and bounds[2] > 50 and bounds[3] > 50:
                return bounds
        return (target_window.left, target_window.top, target_window.width, target_window.height)

    return None

from maple_reporter.utils.config import get_recordings_dir

def capture_screenshot(region: Optional[Tuple[int, int, int, int]] = None) -> Tuple[Image.Image, str]:
    """
    Capture screenshot of an explicit region (left, top, width, height).
    Returns (PIL Image, filepath to saved png inside recordings folder).
    """
    if region is None:
        raise ValueError("An explicit capture region is required.")
    with mss.MSS() as sct:
        left, top, width, height = region
        if width <= 0 or height <= 0:
            raise ValueError("Capture region dimensions must be positive.")
        monitor = {"left": left, "top": top, "width": width, "height": height}

        sct_img = sct.grab(monitor)
        img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")

        rec_dir = str(get_recordings_dir())
        file_path = os.path.join(rec_dir, f"maple_evidence_{int(time.time())}.png")
        img.save(file_path)
        return img, file_path


class AudioRecorderThread(LoopbackAudioRecorder):
    """Compatibility wrapper for short recordings using the shared capture."""

    def __init__(
        self,
        sample_rate: int = DEFAULT_SAMPLE_RATE,
        device_id: Optional[str] = None,
    ):
        # Short recordings do not need the full replay window, but keeping a
        # small margin covers the audio recorder opening slightly before video.
        super().__init__(
            buffer_seconds=3_600,
            sample_rate=sample_rate,
            device_id=device_id,
            error_callback=self._on_capture_error,
        )

    def _on_capture_error(self, message: str) -> None:
        LOGGER.warning("短片音訊擷取失敗：%s", message)


def record_short_video(
    window_title_keyword: str,
    duration_sec: int = 8,
    fps: int = 20,
    progress_callback=None,
    cancel_checker: Optional[Callable[[], bool]] = None,
    record_audio: bool = True,
    audio_device_id: Optional[str] = None,
) -> Tuple[Optional[str], List[Image.Image]]:
    """
    Record a short MP4 video of the target window for `duration_sec` seconds with specified `fps`.
    Extracts keyframe PIL images every 2 seconds for OCR. Optionally records system audio.
    Returns (file_path, keyframes_list). If canceled, returns (None, []).
    """
    bounds = find_window_bounds(window_title_keyword)
    keyframes: List[Image.Image] = []

    # Never fall back to recording the whole desktop. A stale/closed window
    # title must fail closed because the resulting evidence may be uploaded.
    if not bounds:
        return None, []

    left, top, width, height = bounds
    width = width if width % 2 == 0 else width - 1
    height = height if height % 2 == 0 else height - 1
    if width < 2 or height < 2:
        return None, []

    audio_thread: Optional[AudioRecorderThread] = None
    if record_audio:
        try:
            audio_thread = AudioRecorderThread(
                sample_rate=DEFAULT_SAMPLE_RATE, device_id=audio_device_id
            )
            audio_thread.start()
        except Exception as error:
            LOGGER.warning("無法啟動短片音訊擷取 (%s)", type(error).__name__)
            audio_thread = None

    monitor = {"left": left, "top": top, "width": width, "height": height}
    rec_dir = str(get_recordings_dir())
    file_path = os.path.join(
        rec_dir, f"maple_evidence_{time.time_ns() // 1_000_000}.mp4"
    )
    capture_start = time.monotonic()
    out = None
    cancelled = False

    try:
        with mss.MSS() as screen:
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            out = cv2.VideoWriter(file_path, fourcc, fps, (width, height))
            if not out.isOpened():
                raise RuntimeError("無法建立 MP4 影片檔案。")

            last_keyframe_time = -2.0
            written_frames = 0
            while True:
                elapsed = time.monotonic() - capture_start
                if elapsed >= duration_sec:
                    break

                if cancel_checker and cancel_checker():
                    cancelled = True
                    break

                try:
                    sct_img = screen.grab(monitor)
                    frame = np.asarray(sct_img)
                    frame_bgr = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                except Exception as error:
                    LOGGER.debug("螢幕影格擷取失敗，使用黑畫面 (%s)", type(error).__name__)
                    frame_bgr = np.zeros((height, width, 3), dtype=np.uint8)

                if frame_bgr.shape[:2] != (height, width):
                    frame_bgr = cv2.resize(
                        frame_bgr, (width, height), interpolation=cv2.INTER_AREA
                    )

                target_frame_count = int(elapsed * fps) + 1
                frames_to_write = max(1, target_frame_count - written_frames)
                for _ in range(frames_to_write):
                    out.write(frame_bgr)
                written_frames += frames_to_write

                if elapsed - last_keyframe_time >= 2.0:
                    last_keyframe_time = elapsed
                    frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
                    keyframes.append(Image.fromarray(frame_rgb))

                if progress_callback:
                    progress_callback(min(1.0, elapsed / max(1, duration_sec)))

                next_target_time = capture_start + (written_frames / fps)
                sleep_time = max(0.0, next_target_time - time.monotonic())
                if sleep_time > 0:
                    time.sleep(sleep_time)
    except Exception as error:
        LOGGER.warning("短片錄製失敗 (%s)", type(error).__name__)
        if audio_thread:
            audio_thread.stop_and_get_data()
        try:
            os.remove(file_path)
        except OSError as error:
            LOGGER.debug("清理錄影取消檔案失敗 (%s)", type(error).__name__)
        return None, []
    finally:
        if out is not None:
            out.release()

    if cancelled:
        try:
            os.remove(file_path)
        except OSError as error:
            LOGGER.debug("清理取消的短片失敗 (%s)", type(error).__name__)
        if audio_thread:
            audio_thread.stop_and_get_data()
        return None, []

    if audio_thread:
        audio_data = audio_thread.stop_and_get_data(
            start_time=capture_start, end_time=time.monotonic()
        )
        if audio_data is not None and len(audio_data) > 0:
            if not merge_audio_into_mp4(
                file_path, audio_data, sample_rate=DEFAULT_SAMPLE_RATE
            ):
                LOGGER.warning("短片已儲存，但 AAC 音訊軌合併失敗")

    return file_path, keyframes
