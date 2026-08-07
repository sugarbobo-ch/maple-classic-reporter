import os
import time
import tempfile
import threading
import warnings
from typing import List, Optional, Tuple, Callable
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


class AudioRecorderThread(threading.Thread):
    """Background thread to capture WASAPI system loopback audio samples."""
    def __init__(self, sample_rate: int = 44100):
        super().__init__(daemon=True)
        self.sample_rate = sample_rate
        self.chunks = []
        self.stop_event = threading.Event()

    def run(self):
        try:
            import soundcard as sc
            warnings.filterwarnings("ignore", category=getattr(sc, "SoundcardRuntimeWarning", Warning))
            spk = sc.default_speaker()
            mic = sc.get_microphone(spk.id, include_loopback=True)
            with mic.recorder(samplerate=self.sample_rate) as recorder:
                while not self.stop_event.is_set():
                    data = recorder.record(numframes=int(self.sample_rate * 0.1))
                    if len(data) > 0:
                        self.chunks.append(data)
        except Exception:
            pass

    def stop_and_get_data(self) -> Optional[np.ndarray]:
        self.stop_event.set()
        self.join(timeout=1.5)
        if self.chunks:
            try:
                return np.vstack(self.chunks)
            except Exception:
                return None
        return None


def merge_audio_into_mp4(video_path: str, audio_data: np.ndarray, sample_rate: int = 44100) -> bool:
    """
    Merge numpy float32 PCM audio data into an existing MP4 video file using PyAV (av).
    Encodes video frames as H.264 and audio frames as AAC.
    """
    if audio_data is None or len(audio_data) == 0 or not os.path.exists(video_path):
        return False

    temp_out_path = video_path.replace(".mp4", "_audio_temp.mp4")
    try:
        import av
        in_c = av.open(video_path)
        if not in_c.streams.video:
            in_c.close()
            return False

        in_v = in_c.streams.video[0]
        out_c = av.open(temp_out_path, mode="w")

        fps_val = int(round(float(in_v.average_rate or in_v.rate or 20)))
        out_v = out_c.add_stream("h264", rate=fps_val)
        out_v.width = in_v.width
        out_v.height = in_v.height
        out_v.pix_fmt = "yuv420p"

        channels = audio_data.shape[1] if audio_data.ndim > 1 else 1
        layout = "stereo" if channels == 2 else "mono"
        out_a = out_c.add_stream("aac", rate=sample_rate)
        out_a.layout = layout

        # Decode & re-encode video frames to align timestamps
        for packet in in_c.demux(in_v):
            for frame in packet.decode():
                for p in out_v.encode(frame):
                    out_c.mux(p)

        for p in out_v.encode():
            out_c.mux(p)
        in_c.close()

        # Encode AAC audio frames (1024 samples per frame)
        arr = np.ascontiguousarray(audio_data.T, dtype=np.float32)
        samples_per_frame = 1024
        total_samples = arr.shape[1]
        pts = 0

        for i in range(0, total_samples, samples_per_frame):
            chunk = arr[:, i:i + samples_per_frame]
            if chunk.shape[1] < samples_per_frame:
                pad = np.zeros((channels, samples_per_frame - chunk.shape[1]), dtype=np.float32)
                chunk = np.hstack([chunk, pad])
            frame = av.AudioFrame.from_ndarray(chunk, format="fltp", layout=layout)
            frame.rate = sample_rate
            frame.pts = pts
            pts += samples_per_frame
            for pkt in out_a.encode(frame):
                out_c.mux(pkt)

        for pkt in out_a.encode():
            out_c.mux(pkt)

        out_c.close()

        if os.path.exists(temp_out_path) and os.path.getsize(temp_out_path) > 0:
            os.replace(temp_out_path, video_path)
            return True
    except Exception:
        if os.path.exists(temp_out_path):
            try:
                os.remove(temp_out_path)
            except Exception:
                pass
    return False


def record_short_video(
    window_title_keyword: str,
    duration_sec: int = 8,
    fps: int = 20,
    progress_callback=None,
    cancel_checker: Optional[Callable[[], bool]] = None,
    record_audio: bool = True
) -> Tuple[Optional[str], List[Image.Image]]:
    """
    Record a short MP4 video of the target window for `duration_sec` seconds with specified `fps`.
    Extracts keyframe PIL images every 2 seconds for OCR. Optionally records system audio.
    Returns (file_path, keyframes_list). If canceled, returns (None, []).
    """
    bounds = find_window_bounds(window_title_keyword)
    keyframes: List[Image.Image] = []

    audio_thread = None
    if record_audio:
        try:
            audio_thread = AudioRecorderThread(sample_rate=44100)
            audio_thread.start()
        except Exception:
            audio_thread = None

    with mss.mss() as sct:
        if bounds:
            left, top, width, height = bounds
            # Make sure width and height are even numbers for H264/XVID encoding
            width = width if width % 2 == 0 else width - 1
            height = height if height % 2 == 0 else height - 1
            monitor = {"left": left, "top": top, "width": width, "height": height}
        else:
            mon = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
            width, height = mon["width"], mon["height"]
            width = width if width % 2 == 0 else width - 1
            height = height if height % 2 == 0 else height - 1
            monitor = {"left": mon["left"], "top": mon["top"], "width": width, "height": height}

        rec_dir = str(get_recordings_dir())
        file_path = os.path.join(rec_dir, f"maple_evidence_{int(time.time())}.mp4")

        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(file_path, fourcc, fps, (width, height))

        start_time = time.time()
        frame_delay = 1.0 / fps
        last_keyframe_time = 0.0
        written_frames = 0

        while True:
            current_time = time.time()
            elapsed = current_time - start_time
            if elapsed >= duration_sec:
                break

            if cancel_checker and cancel_checker():
                if audio_thread:
                    audio_thread.stop_and_get_data()
                out.release()
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except Exception:
                        pass
                return None, []

            try:
                sct_img = sct.grab(monitor)
                frame = np.array(sct_img)
                frame_bgr = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
            except Exception:
                frame_bgr = np.zeros((height, width, 3), dtype=np.uint8)

            # Calculate target number of video frames corresponding to elapsed time
            target_frame_count = int(elapsed * fps) + 1
            frames_to_write = max(1, target_frame_count - written_frames)
            for _ in range(frames_to_write):
                out.write(frame_bgr)
            written_frames += frames_to_write

            # Grab keyframe every 2 seconds
            if elapsed - last_keyframe_time >= 2.0 or last_keyframe_time == 0.0:
                last_keyframe_time = elapsed
                frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
                keyframes.append(Image.fromarray(frame_rgb))

            if progress_callback:
                progress_callback(min(1.0, elapsed / duration_sec))

            # Sleep to match next frame interval target time
            next_target_time = start_time + (written_frames / fps)
            sleep_time = max(0, next_target_time - time.time())
            if sleep_time > 0:
                time.sleep(sleep_time)

        out.release()

        if audio_thread:
            audio_data = audio_thread.stop_and_get_data()
            if audio_data is not None and len(audio_data) > 0:
                merge_audio_into_mp4(file_path, audio_data, sample_rate=44100)

        return file_path, keyframes
