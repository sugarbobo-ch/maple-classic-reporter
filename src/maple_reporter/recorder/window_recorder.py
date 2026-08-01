import os
import time
import tempfile
from typing import List, Optional, Tuple
import cv2
import numpy as np
import mss
import pygetwindow as gw
from PIL import Image

import ctypes
from ctypes import wintypes

# Enable Per-Monitor DPI Awareness safely if not already set by Qt
try:
    # 0 = Unaware, 1 = System Aware, 2 = Per Monitor Aware
    res = ctypes.windll.shcore.GetProcessDpiAwareness(0, ctypes.byref(ctypes.c_int()))
except Exception:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass

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
    except Exception:
        pass

    try:
        ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
        return (rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top)
    except Exception:
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
    except Exception:
        pass
    return get_accurate_window_bounds(hwnd)

def get_active_window_titles() -> List[str]:
    """Return a list of visible window titles."""
    titles = []
    for w in gw.getAllWindows():
        if w.title and w.visible and w.width > 100 and w.height > 100:
            titles.append(w.title)
    return sorted(list(set(titles)))

def focus_window(window_title_keyword: str) -> bool:
    """Bring the target window to the foreground."""
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
            except Exception:
                pass
        try:
            target_window.activate()
            return True
        except Exception:
            pass
    return False

def find_window_bounds(window_title_keyword: str) -> Optional[Tuple[int, int, int, int]]:
    """
    Find accurate window bounding box (left, top, width, height) by exact title or keyword.
    Prioritizes exact title match over substring match to avoid selecting browser/IDE windows.
    """
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
    Capture screenshot of a region (left, top, width, height) or full screen.
    Returns (PIL Image, filepath to saved png inside recordings folder).
    """
    with mss.mss() as sct:
        if region:
            left, top, width, height = region
            monitor = {"left": left, "top": top, "width": width, "height": height}
        else:
            monitor = sct.monitors[0]

        sct_img = sct.grab(monitor)
        img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")

        rec_dir = str(get_recordings_dir())
        file_path = os.path.join(rec_dir, f"maple_evidence_{int(time.time())}.png")
        img.save(file_path)
        return img, file_path

def record_short_video(
    window_title_keyword: str,
    duration_sec: int = 8,
    fps: int = 20,
    progress_callback=None
) -> Tuple[Optional[str], List[Image.Image]]:
    """
    Record a short MP4 video of the target window for `duration_sec` seconds with specified `fps`.
    Extracts keyframe PIL images every 2 seconds for OCR.
    Returns (file_path, keyframes_list).
    """
    bounds = find_window_bounds(window_title_keyword)
    keyframes: List[Image.Image] = []

    with mss.mss() as sct:
        if bounds:
            left, top, width, height = bounds
            # Make sure width and height are even numbers for H264/XVID encoding
            width = width if width % 2 == 0 else width - 1
            height = height if height % 2 == 0 else height - 1
            monitor = {"left": left, "top": top, "width": width, "height": height}
        else:
            monitor = sct.monitors[0]
            width, height = monitor["width"], monitor["height"]
            width = width if width % 2 == 0 else width - 1
            height = height if height % 2 == 0 else height - 1
            monitor["width"] = width
            monitor["height"] = height

        rec_dir = str(get_recordings_dir())
        file_path = os.path.join(rec_dir, f"maple_evidence_{int(time.time())}.mp4")

        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(file_path, fourcc, fps, (width, height))

        start_time = time.time()
        frame_delay = 1.0 / fps
        last_keyframe_time = 0.0

        while (time.time() - start_time) < duration_sec:
            loop_start = time.time()
            sct_img = sct.grab(monitor)
            frame = np.array(sct_img)
            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
            out.write(frame_bgr)

            elapsed = time.time() - start_time
            # Grab keyframe every 2 seconds
            if elapsed - last_keyframe_time >= 2.0 or last_keyframe_time == 0.0:
                last_keyframe_time = elapsed
                frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
                keyframes.append(Image.fromarray(frame_rgb))

            if progress_callback:
                progress_callback(min(1.0, elapsed / duration_sec))

            time_spent = time.time() - loop_start
            sleep_time = max(0, frame_delay - time_spent)
            time.sleep(sleep_time)

        out.release()
        return file_path, keyframes
