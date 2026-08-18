"""PyWebView JS Bridge connecting React UI with Python backend services."""

from __future__ import annotations

import base64
import concurrent.futures
import ctypes
from ctypes import wintypes
import io
import json
import logging
import math
import os
import subprocess
import threading
import time
import webbrowser
from functools import wraps
from http.server import HTTPServer, BaseHTTPRequestHandler
import mimetypes
from pathlib import Path
import shutil
from typing import Any
import urllib.parse

import numpy as np
import webview
from PIL import Image

from maple_reporter.automation.form_filler import submit_gamania_report
from maple_reporter.automation.playwright_runtime import PlaywrightBrowserError
from maple_reporter.discord.webhook_service import (
    is_valid_discord_webhook_url,
    upload_evidence_to_discord,
)
from maple_reporter.gdrive.drive_service import GoogleDriveManager
from maple_reporter.gui.evidence_capture_controller import EvidenceCaptureController
from maple_reporter.gui.history_controller import HistoryController
from maple_reporter.gui.native_window import (
    _window_handle,
    begin_native_resize,
    move_window_by_drag_delta,
    prepare_native_drag,
)
from maple_reporter.ocr.win_ocr import (
    recognize_candidates_from_image_list,
    recognize_map_name_from_image_list,
)
from maple_reporter.recorder.audio_capture import (
    get_audio_output_devices,
    get_default_audio_output_name,
)
from maple_reporter.recorder.replay_buffer import ReplayBufferRecorder
from maple_reporter.recorder.video_editor import cut_video_segment, get_video_duration
from maple_reporter.recorder.window_recorder import (
    capture_screenshot as record_capture_screenshot,
    capture_window_screenshot,
    find_window_bounds,
    focus_window,
    get_active_windows,
    is_window_minimized,
    order_window_candidates,
    record_short_video,
    select_preferred_window_title,
)
from maple_reporter.sanctions.coordinator import SanctionSyncCoordinator
from maple_reporter.sanctions.repository import SanctionRepository
from maple_reporter.utils.config import (
    add_history_entry,
    get_recordings_dir,
    get_user_app_data_dir,
    is_owned_recording_path,
    load_config,
    save_config,
)

LOGGER = logging.getLogger(__name__)


def _submission_guard(method):
    """Reject overlapping submissions before they can upload duplicate evidence."""

    @wraps(method)
    def guarded(self, form_data):
        if not self._submission_lock.acquire(blocking=False):
            message = "已有檢舉正在送出，請稍候完成後再試。"
            self._emit_submission_status("busy", message, "error")
            return {"status": "error", "message": message}
        try:
            return method(self, form_data)
        finally:
            self._submission_lock.release()

    return guarded


from maple_reporter.gui.media_server import LocalMediaServer, _RangeMediaRequestHandler
from maple_reporter.gui.bridge_hotkeys import (
    BackgroundHotkeyListener,
    read_system_clipboard_text,
    write_system_clipboard_text,
    WM_HOTKEY,
    MOD_ALT,
    MOD_CONTROL,
    MOD_SHIFT,
    MOD_WIN,
    MOD_NOREPEAT,
    HOTKEY_ACTIONS,
    VK_MAP,
    CF_UNICODETEXT,
)



def _choose_preferred_window(windows: list[dict[str, Any]], saved_title: str = "") -> str:
    if not windows:
        return "新楓之谷：經典版"
    # 1. Exact match "新楓之谷：經典版"
    for w in windows:
        if w.get("title", "").strip() == "新楓之谷：經典版":
            return w["title"]
    # 2. Contains "新楓之谷：經典版"
    for w in windows:
        if "新楓之谷：經典版" in w.get("title", ""):
            return w["title"]
    # 3. Contains "新楓之谷"
    for w in windows:
        if "新楓之谷" in w.get("title", ""):
            return w["title"]
    # 4. Contains "maple" (case-insensitive)
    for w in windows:
        if "maple" in w.get("title", "").lower():
            return w["title"]
    # 5. Saved title if exists in scanned windows
    if saved_title:
        for w in windows:
            if w.get("title") == saved_title:
                return saved_title
    # 6. First scanned window
    return windows[0]["title"]


class PyWebViewBridge:
    """API bridge exposed to JavaScript via window.pywebview.api."""

    def __init__(self, window: webview.Window | None = None):
        self._window = window
        self.config = load_config()
        self.history_controller = HistoryController()
        self.capture_controller = EvidenceCaptureController()
        self.drive_mgr = GoogleDriveManager()
        self.replay_recorder = ReplayBufferRecorder(
            state_callback=self._on_replay_state_changed,
            replay_saved_callback=self._on_replay_saved,
            error_callback=self._on_replay_error,
        )
        self.sanction_repo = SanctionRepository()
        self.sanction_coordinator = SanctionSyncCoordinator(
            repository=self.sanction_repo,
            event_emitter=self._emit_event,
        )

        # Recording state tracking
        self._recording_active = False
        self._cancel_requested = False
        self._recording_thread: threading.Thread | None = None
        self._submission_lock = threading.Lock()
        self._config_lock = threading.RLock()

        # Replay status
        self._replay_state = "idle"
        self._replay_duration = 0.0
        self._window_maximized = False
        self._drag_move_baseline: tuple[float, float] | None = None

        # Media streaming server
        self.media_server = LocalMediaServer()
        self.media_server.start()

        # Global hotkey listener
        self.hotkey_listener = BackgroundHotkeyListener(self._handle_global_hotkey)
        self._init_hotkeys()

    def set_window(self, window: webview.Window, maximized: bool = False) -> None:
        self._window = window
        self._window_maximized = maximized
        # pywebview's built-in drag region calls window.move(x, y) with an
        # absolute logical desktop position. Convert only successive deltas
        # so mixed-DPI monitor origins cannot move the window to an edge.
        try:
            window.move = self._move_window_from_drag_delta
        except (AttributeError, TypeError):
            LOGGER.debug("Could not install the native drag movement adapter", exc_info=True)

    def _move_window_from_drag_delta(self, x: float, y: float) -> None:
        point = (float(x), float(y))
        previous = self._drag_move_baseline
        self._drag_move_baseline = point
        if previous is None or not self._window:
            return
        hwnd = _window_handle(self._window)
        if hwnd:
            move_window_by_drag_delta(hwnd, point[0] - previous[0], point[1] - previous[1])

    def _set_window_maximized_state(self, maximized: bool) -> None:
        self._window_maximized = maximized
        self._emit_event("WINDOW_MAXIMIZED" if maximized else "WINDOW_RESTORED")

    def handle_window_maximized(self) -> None:
        """Keep the React title-bar state in sync with native maximize events."""
        self._set_window_maximized_state(True)

    def handle_window_restored(self) -> None:
        """Keep the React title-bar state in sync with native restore events."""
        self._set_window_maximized_state(False)

    def _init_hotkeys(self):
        enabled = bool(self.config.get("global_hotkeys_enabled", True))
        save_key = self.config.get("save_replay_hotkey", "F9").split("+")[-1]
        record_key = self.config.get("record_video_hotkey", "F10").split("+")[-1]
        self.hotkey_listener.update_bindings(save_key, record_key, enabled)

    def _emit_event(self, event_type: str, data: Any = None) -> None:
        """Push an asynchronous event to the React frontend."""
        if not self._window:
            return
        payload = json.dumps({"type": event_type, "data": data or {}})
        try:
            self._window.evaluate_js(f"if(window.__MAPLE_REPORTER_EVENT__)window.__MAPLE_REPORTER_EVENT__({payload});")
        except Exception as err:
            LOGGER.debug("Failed to evaluate js event: %s", err)

    def _emit_submission_status(
        self,
        step: str,
        message: str,
        status: str = "progress",
    ) -> None:
        """Publish a consistent submission lifecycle event to the React UI."""
        self._emit_event(
            "SUBMISSION_STATUS",
            {"step": step, "status": status, "message": message},
        )

    def _handle_global_hotkey(self, action: str):
        LOGGER.info("Global hotkey triggered: %s", action)
        self._emit_event("GLOBAL_HOTKEY_TRIGGERED", {"action": action})

        if action == "save_replay":
            if self.replay_recorder.is_running:
                self.save_replay()
            else:
                self.start_replay()
        elif action == "record_video":
            if self._recording_active:
                self.cancel_recording()
            else:
                self.start_recording()

    # --- Initial Data & Config ---

    def get_clipboard_text(self) -> str:
        """Return clipboard text through the native host instead of WebView Clipboard API."""
        return read_system_clipboard_text()

    def set_clipboard_text(self, text: str) -> bool:
        """Write clipboard text through the native host instead of WebView Clipboard API."""
        return write_system_clipboard_text(text)

    # --- Frameless Window Controls ---

    def minimize_window(self) -> bool:
        """Minimize the desktop window."""
        if not self._window:
            return False
        try:
            self._window.minimize()
            return True
        except Exception as err:
            LOGGER.warning("Failed to minimize window: %s", err)
            return False

    def toggle_window_maximized(self) -> bool:
        """Toggle between maximized and restored window state."""
        if not self._window:
            return self._window_maximized
        try:
            should_maximize = not self._window_maximized
            if should_maximize:
                self._window.maximize()
            else:
                self._window.restore()
            self._window_maximized = should_maximize
        except Exception as err:
            LOGGER.warning("Failed to toggle window maximized state: %s", err)
        return self._window_maximized

    def close_window(self) -> bool:
        """Close the desktop window."""
        if not self._window:
            return False
        try:
            self._window.destroy()
            return True
        except Exception as err:
            LOGGER.warning("Failed to close window: %s", err)
            return False

    def drag_window(self, anchor_mode: str = "proportional") -> bool:
        """Prepare the cursor anchor before pywebview moves its drag region."""
        if not self._window or os.name != "nt":
            return False
        try:
            self._drag_move_baseline = None
            hwnd = _window_handle(self._window)
            return bool(hwnd and prepare_native_drag(hwnd, anchor_mode))
        except Exception as err:
            LOGGER.debug("Native window drag failed: %s", err)
        return False

    def resize_window(self, direction: str) -> bool:
        """Initiate native Windows window resizing in the specified direction on mousedown."""
        if not self._window or os.name != "nt":
            return False

        try:
            hwnd = _window_handle(self._window)
            return begin_native_resize(hwnd, direction) if hwnd else False
        except Exception as err:
            LOGGER.debug("Native window resize failed: %s", err)
        return False

    def get_initial_data(self) -> dict[str, Any]:
        """Fetch initial config, system windows, audio devices, history, and drive auth."""
        self.config = load_config()
        windows = self.get_windows()
        audio_devices = self.get_audio_devices()
        history = self.sanction_repo.load_history()
        gdrive_auth = self.drive_mgr.is_authenticated()
        sync_status = self.sanction_coordinator.get_status().to_dict()
        cache = self.sanction_repo.load_cache()

        preferred_window = _choose_preferred_window(
            windows, self.config.get("selected_window_title", "")
        )
        self.config["selected_window_title"] = preferred_window

        if not self.config.get("has_initialized_defaults", False):
            self.config["has_initialized_defaults"] = True
            if "recording_preset" not in self.config:
                self.config["recording_preset"] = "balanced"
            try:
                save_config(self.config)
            except Exception as err:
                LOGGER.warning("Failed to save initial default config: %s", err)

        return {
            "config": self.config,
            "windows": windows,
            "audio_devices": audio_devices,
            "history": history,
            "gdrive_authenticated": gdrive_auth,
            "replay_state": self._replay_state,
            "replay_duration": self._replay_duration,
            "app_data_dir": str(get_user_app_data_dir()),
            "sanction_sync_status": sync_status,
            "last_complete_sync_at": cache.last_complete_sync_at or None,
        }

    def start_sanction_sync(self, trigger: str = "manual") -> dict[str, Any]:
        """Start sanction synchronization worker."""
        trig = "startup" if trigger == "startup" else "manual"
        result = self.sanction_coordinator.start(trigger=trig)
        return result.to_dict()

    def get_sanction_sync_status(self) -> dict[str, Any]:
        """Return current sanction synchronization status."""
        return self.sanction_coordinator.get_status().to_dict()

    def get_history(self) -> list[dict[str, Any]]:
        """Return the latest history records."""
        return self.sanction_repo.load_history()

    def rebuild_sanction_cache_for_development(self) -> bool:
        """Reset sanction cache if developer mode is enabled."""
        if not self.config.get("dev_mode", False):
            return False
        return self.sanction_coordinator.rebuild_cache_for_development()

    def clear_history(self) -> bool:
        """Delete all locally persisted report history entries."""
        try:
            self.sanction_repo.clear_history()
            return True
        except OSError as err:
            LOGGER.warning("Failed to clear report history: %s", err)
            return False

    @property
    def _safe_config_lock(self) -> threading.RLock:
        if not hasattr(self, "_config_lock") or self._config_lock is None:
            self._config_lock = threading.RLock()
        return self._config_lock

    def save_config_key(self, key: str, value: Any) -> bool:
        """Update single config key and persist."""
        with self._safe_config_lock:
            try:
                current_config = load_config()
                candidate_config = dict(current_config)
                candidate_config[key] = value
                save_config(candidate_config)
                self.config = candidate_config

                if key in ("global_hotkeys_enabled", "save_replay_hotkey", "record_video_hotkey"):
                    self._init_hotkeys()
                elif key in ("replay_buffer_sec", "selected_window_title", "record_fps", "record_audio", "audio_output_device_id"):
                    if self.replay_recorder.is_running:
                        LOGGER.info("Restarting replay buffer to apply updated setting: %s", key)
                        self.start_replay()
                LOGGER.info("Config key saved: %s = %s", key, value)
                return True
            except Exception as err:
                LOGGER.error("Failed to save config key %s: %s", key, err)
                return False

    def save_config_all(self, new_config: dict[str, Any]) -> bool:
        """Save entire updated config dict."""
        with self._safe_config_lock:
            try:
                current_config = load_config()
                candidate_config = dict(current_config)
                candidate_config.update(new_config)
                save_config(candidate_config)
                self.config = candidate_config
                self._init_hotkeys()
                return True
            except Exception as err:
                LOGGER.error("Failed to save config: %s", err)
                return False

    def get_windows(self) -> list[dict[str, Any]]:
        """Return active desktop windows excluding reporter tool itself."""
        try:
            raw_windows = get_active_windows()
            filtered = order_window_candidates(
                [
                    window
                    for window in raw_windows
                    if "maplestory classic auto reporter" not in window["title"].lower()
                    and "自動外掛檢舉工具" not in window["title"]
                    and "maple classic reporter" not in window["title"].lower()
                ]
            )
            selected_title = select_preferred_window_title(
                filtered, str(self.config.get("selected_window_title", ""))
            )
            if selected_title and selected_title != self.config.get("selected_window_title"):
                self.config["selected_window_title"] = selected_title
                try:
                    save_config(self.config)
                except Exception as err:
                    LOGGER.warning("Failed to persist preferred window: %s", err)
            return filtered
        except Exception as err:
            LOGGER.warning("Error getting window titles: %s", err)
            return []

    def get_audio_devices(self) -> list[dict[str, Any]]:
        """Return system audio output devices."""
        try:
            default_name = get_default_audio_output_name()
            devices = get_audio_output_devices()
            result = [{"id": "", "name": f"系統預設（{default_name}）"}]
            for dev_id, name in devices:
                result.append({"id": dev_id, "name": name})
            return result
        except Exception as err:
            LOGGER.warning("Error getting audio devices: %s", err)
            return [{"id": "", "name": "系統預設 (Realtek Digital Output)"}]

    # --- OCR Execution Helper ---

    def _perform_ocr(self, keyframes: list[Image.Image]) -> dict[str, Any]:
        """Run rapid OCR in stages with event callbacks and timeout safeguards."""
        default_map = str(self.config.get("default_map", "維多利亞島") or "").strip()
        if not keyframes:
            return {
                "suspect_ids": [],
                "map_name": default_map,
                "ocr_map_name": "",
                "map_name_source": "default",
            }

        try:
            # Subsample keyframes if there are too many (cap at 4 evenly spaced frames for speed)
            if len(keyframes) > 4:
                indices = np.linspace(0, len(keyframes) - 1, num=4, dtype=int)
                sampled_keyframes = [keyframes[int(i)] for i in indices]
            else:
                sampled_keyframes = keyframes

            whitelist = [w.strip() for w in self.config.get("whitelist", []) if w.strip()]
            recognize_id = bool(self.config.get("ocr_autofill_id", True))
            recognize_map = bool(self.config.get("ocr_autofill_map", True))

            detected_map = ""
            candidates = []

            def on_map_progress(curr: int, tot: int):
                pct = 45 + int(20 * curr / max(1, tot))
                self._emit_event(
                    "OCR_STATUS",
                    {
                        "step": "map",
                        "status": f"正在辨識地圖名稱 (第 {curr}/{tot} 張)...",
                        "percent": pct,
                        "current": curr,
                        "total": tot,
                    },
                )

            def on_id_progress(curr: int, tot: int):
                pct = 65 + int(30 * curr / max(1, tot))
                self._emit_event(
                    "OCR_STATUS",
                    {
                        "step": "id",
                        "status": f"正在辨識角色 ID (第 {curr}/{tot} 張)...",
                        "percent": pct,
                        "current": curr,
                        "total": tot,
                    },
                )

            self._emit_event(
                "OCR_STATUS",
                {
                    "step": "map",
                    "status": f"正在辨識地圖名稱 (共 {len(sampled_keyframes)} 張)...",
                    "percent": 45,
                    "current": 1,
                    "total": len(sampled_keyframes),
                },
            )
            if recognize_map:
                try:
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                        future = executor.submit(
                            recognize_map_name_from_image_list,
                            sampled_keyframes,
                            on_progress=on_map_progress,
                        )
                        detected_map = future.result(timeout=6.0) or ""
                except concurrent.futures.TimeoutError:
                    LOGGER.warning("Map name recognition timed out (6s limit reached)")
                except Exception as err:
                    LOGGER.warning("Map name recognition failed: %s", err)

            self._emit_event(
                "OCR_STATUS",
                {
                    "step": "id",
                    "status": f"正在辨識可疑 ID (共 {len(sampled_keyframes)} 張)...",
                    "percent": 65,
                    "current": 1,
                    "total": len(sampled_keyframes),
                },
            )
            if recognize_id:
                try:
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                        future = executor.submit(
                            recognize_candidates_from_image_list,
                            sampled_keyframes,
                            detected_map_name=detected_map,
                            on_progress=on_id_progress,
                        )
                        raw_candidates = future.result(timeout=8.0) or []
                    seen = set()
                    for cand in raw_candidates:
                        if cand not in seen and cand not in whitelist:
                            seen.add(cand)
                            candidates.append(cand)
                except concurrent.futures.TimeoutError:
                    LOGGER.warning("Candidate recognition timed out (8s limit reached)")
                except Exception as err:
                    LOGGER.warning("Candidate recognition failed: %s", err)

            self._emit_event(
                "OCR_STATUS",
                {"step": "done", "status": "整理資料完成", "percent": 100},
            )
            return {
                "suspect_ids": candidates,
                "map_name": detected_map or default_map,
                "ocr_map_name": detected_map,
                "map_name_source": "ocr" if detected_map else "default",
            }
        except Exception as err:
            LOGGER.error("OCR execution exception: %s", err)
            self._emit_event(
                "OCR_STATUS",
                {"step": "error", "status": f"辨識完成 (發生部分異常: {err})", "percent": 100},
            )
            return {
                "suspect_ids": [],
                "map_name": default_map,
                "ocr_map_name": "",
                "map_name_source": "default",
            }

    # --- Screenshot Capture ---

    def capture_screenshot(self, mode: str = "window") -> dict[str, Any]:
        """Capture screenshot from the selected target game window and perform OCR."""
        win_title = self.config.get("selected_window_title", "新楓之谷：經典版")
        try:
            if is_window_minimized(win_title):
                return {
                    "status": "error",
                    "message": "目標遊戲視窗處於最小化狀態，請先展開遊戲視窗後再進行截圖。",
                }

            focus_window(win_title)
            time.sleep(0.15)
            bounds = find_window_bounds(win_title)
            if not bounds:
                raise RuntimeError("找不到選取的遊戲視窗，請重新整理視窗清單。")

            img, file_path = capture_window_screenshot(win_title)
            if img is None or not file_path:
                img, file_path = record_capture_screenshot(bounds)

            ocr_res = self._perform_ocr([img])

            return {
                "status": "success",
                "suspect_ids": ocr_res["suspect_ids"],
                "map_name": ocr_res["map_name"],
                "ocr_map_name": ocr_res.get("ocr_map_name", ""),
                "map_name_source": ocr_res.get("map_name_source", "default"),
                "media_path": file_path,
                "media_type": "image",
            }
        except Exception as err:
            LOGGER.error("Screenshot capture failed: %s", err)
            return {
                "status": "error",
                "message": f"截圖失敗: {str(err)}",
                "suspect_ids": [],
                "map_name": "",
                "media_path": "",
                "media_type": "image",
            }

    def _restore_gui_window(self):
        """Restore and bring PyWebView GUI window forcefully to foreground."""
        try:
            if self._window:
                self._window.restore()
                self._window.show()
        except Exception:
            pass

        if os.name == "nt":
            try:
                pid = os.getpid()
                found_hwnd = None

                def _enum_proc(hwnd, lparam):
                    nonlocal found_hwnd
                    if ctypes.windll.user32.IsWindow(hwnd):
                        window_pid = wintypes.DWORD()
                        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(window_pid))
                        if window_pid.value == pid:
                            rect = wintypes.RECT()
                            ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
                            if (rect.right - rect.left) > 200 and (rect.bottom - rect.top) > 200:
                                found_hwnd = hwnd
                                return False
                    return True

                WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
                ctypes.windll.user32.EnumWindows(WNDENUMPROC(_enum_proc), 0)

                if not found_hwnd:
                    for w in gw.getAllWindows():
                        t = str(getattr(w, "title", "")).strip().casefold()
                        if "新楓之谷經典版 自動檢舉小幫手".casefold() in t or "maplestory classic auto reporter".casefold() in t:
                            found_hwnd = getattr(w, "_hWnd", None)
                            if found_hwnd:
                                break

                if found_hwnd and ctypes.windll.user32.IsWindow(found_hwnd):
                    try:
                        ctypes.windll.user32.OpenIcon(found_hwnd)
                    except Exception:
                        pass

                    # Bypass Windows SetForegroundWindow lock via ALT key simulation
                    ctypes.windll.user32.keybd_event(0x12, 0, 0, 0)
                    ctypes.windll.user32.keybd_event(0x12, 0, 2, 0)

                    ctypes.windll.user32.ShowWindow(found_hwnd, 9)  # SW_RESTORE
                    ctypes.windll.user32.SetWindowPos(found_hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002)  # HWND_TOPMOST
                    ctypes.windll.user32.SetWindowPos(found_hwnd, -2, 0, 0, 0, 0, 0x0001 | 0x0002)  # HWND_NOTOPMOST
                    ctypes.windll.user32.BringWindowToTop(found_hwnd)
                    ctypes.windll.user32.SetForegroundWindow(found_hwnd)
            except Exception as err:
                LOGGER.debug("無法強制喚醒主視窗: %s", err)

    # --- Video Recording ---

    def start_recording(
        self,
        duration_sec: int | None = None,
        fps: int | None = None,
        countdown_sec: int | None = None,
        record_audio: bool | None = None,
        audio_device_id: str | None = None,
    ) -> bool:
        """Start a short video recording in a background thread with real-time events."""
        if self._recording_active or (self._recording_thread and self._recording_thread.is_alive()):
            # Wait briefly if previous thread is finishing cleanup
            if self._recording_thread and self._recording_thread.is_alive():
                self._recording_thread.join(timeout=0.5)
            if self._recording_active:
                LOGGER.warning("start_recording rejected: previous recording still active.")
                return False

        duration = duration_sec or int(self.config.get("record_duration_sec", 8))
        rec_fps = fps or int(self.config.get("record_fps", 30))
        countdown = countdown_sec if countdown_sec is not None else int(self.config.get("record_countdown_sec", 0))
        rec_audio = record_audio if record_audio is not None else bool(self.config.get("record_audio", True))
        audio_dev = audio_device_id or self.config.get("audio_output_device_id") or None
        win_title = self.config.get("selected_window_title", "新楓之谷：經典版")

        # Reject if target window is minimized
        if is_window_minimized(win_title):
            LOGGER.warning("start_recording rejected: target window '%s' is minimized.", win_title)
            self._emit_event("RECORDING_ERROR", {"message": "目標遊戲視窗處於最小化狀態，請先展開遊戲視窗後再開始錄影。"})
            raise RuntimeError("目標遊戲視窗處於最小化狀態，請先展開遊戲視窗後再開始錄影。")

        focus_window(win_title)

        self._recording_active = True
        self._cancel_requested = False

        def _worker():
            try:
                focus_window(win_title)
                # Countdown phase
                if countdown > 0:
                    for remaining in range(countdown, 0, -1):
                        if self._cancel_requested:
                            self._emit_event("RECORDING_CANCELED")
                            return
                        percent = int((remaining / countdown) * 100)
                        self._emit_event("RECORDING_COUNTDOWN", {"remaining": remaining, "percent": percent, "total": countdown})
                        time.sleep(1.0)

                if self._cancel_requested:
                    self._emit_event("RECORDING_CANCELED")
                    return

                self._emit_event("RECORDING_PROGRESS", {"elapsed": 0, "total": duration, "percent": 0, "fraction": 0.0})

                last_progress_time = 0.0
                def _progress_cb(val: float):
                    nonlocal last_progress_time
                    now = time.monotonic()
                    if now - last_progress_time < 0.04 and val < 0.99:
                        return
                    last_progress_time = now
                    frac = max(0.0, min(1.0, float(val)))
                    elapsed = min(duration, int(frac * duration))
                    percent = int(frac * 100)
                    self._emit_event(
                        "RECORDING_PROGRESS",
                        {"elapsed": elapsed, "total": duration, "percent": percent, "fraction": frac},
                    )

                file_path, keyframes = record_short_video(
                    win_title,
                    duration_sec=duration,
                    fps=rec_fps,
                    progress_callback=_progress_cb,
                    cancel_checker=lambda: self._cancel_requested,
                    record_audio=rec_audio,
                    audio_device_id=audio_dev,
                )

                if self._cancel_requested or not file_path:
                    if self._cancel_requested:
                        self._emit_event("RECORDING_CANCELED")
                    else:
                        self._emit_event("RECORDING_ERROR", {"message": "無法擷取目標遊戲視窗，請確認遊戲未關閉"})
                    return

                # Emit final 100% progress so the circle fills completely
                self._emit_event("RECORDING_PROGRESS", {"elapsed": duration, "total": duration, "percent": 100, "fraction": 1.0})
                time.sleep(0.15)

                self._emit_event("RECORDING_FINISHED", {"file_path": file_path})
                ocr_res = self._perform_ocr(keyframes)

                self._emit_event(
                    "OCR_RESULT",
                    {
                        "status": "success",
                        "suspect_ids": ocr_res["suspect_ids"],
                        "map_name": ocr_res["map_name"],
                        "ocr_map_name": ocr_res.get("ocr_map_name", ""),
                        "map_name_source": ocr_res.get("map_name_source", "default"),
                        "media_path": file_path,
                        "media_type": "video",
                    },
                )
            except Exception as err:
                LOGGER.error("Recording worker exception: %s", err)
                self._emit_event("RECORDING_ERROR", {"message": str(err)})
            finally:
                self._recording_active = False
                self._cancel_requested = False

        self._recording_thread = threading.Thread(target=_worker, daemon=True)
        self._recording_thread.start()
        return True

    def cancel_recording(self) -> bool:
        """Request cancellation of active recording and wait for cleanup."""
        if not self._recording_active and (not self._recording_thread or not self._recording_thread.is_alive()):
            return True
        self._cancel_requested = True
        if self._recording_thread and self._recording_thread.is_alive():
            self._recording_thread.join(timeout=1.5)
        self._recording_active = False
        self._cancel_requested = False
        return True

    # --- Replay Buffer ---

    def start_replay(
        self,
        window_title: str | None = None,
        fps: int | None = None,
        buffer_seconds: int | None = None,
        record_audio: bool | None = None,
        audio_device_id: str | None = None,
    ) -> bool:
        """Start the background sliding replay buffer."""
        title = window_title or self.config.get("selected_window_title", "新楓之谷：經典版")
        rec_fps = fps or int(self.config.get("record_fps", 30))
        sec = buffer_seconds or int(self.config.get("replay_buffer_sec", 30))
        rec_audio = record_audio if record_audio is not None else bool(self.config.get("record_audio", True))
        audio_dev = audio_device_id or self.config.get("audio_output_device_id") or None

        return self.replay_recorder.start(
            title,
            fps=rec_fps,
            buffer_seconds=sec,
            record_audio=rec_audio,
            audio_device_id=audio_dev,
        )

    def stop_replay(self) -> bool:
        """Stop background replay buffer."""
        self.replay_recorder.stop()
        return True

    def save_replay(self) -> bool:
        """Save the current buffer segment to mp4 file."""
        return self.replay_recorder.save_replay()

    def get_replay_status(self) -> dict[str, Any]:
        """Return current replay buffer state and duration."""
        return {
            "state": self._replay_state,
            "duration": self._replay_duration,
            "is_running": self.replay_recorder.is_running,
        }

    def _on_replay_state_changed(self, state: str, duration: float):
        self._replay_state = state
        self._replay_duration = duration
        self._emit_event(
            "REPLAY_STATE_CHANGED",
            {
                "state": state,
                "duration": duration,
                "total": int(self.config.get("replay_buffer_sec", 30)),
            },
        )

    def _on_replay_saved(self, file_path: str, keyframes: list[Image.Image]):
        LOGGER.info("Replay saved to %s (%d keyframes)", file_path, len(keyframes))
        self._emit_event("REPLAY_SAVED", {"file_path": file_path})
        try:
            ocr_res = self._perform_ocr(keyframes)
        except Exception as err:
            LOGGER.error("Failed to perform OCR on replay: %s", err)
            ocr_res = {
                "suspect_ids": [],
                "map_name": self.config.get("default_map", "維多利亞島"),
                "ocr_map_name": "",
                "map_name_source": "default",
            }
        self._emit_event(
            "OCR_RESULT",
            {
                "status": "success",
                "suspect_ids": ocr_res.get("suspect_ids", []),
                "map_name": ocr_res.get("map_name", ""),
                "ocr_map_name": ocr_res.get("ocr_map_name", ""),
                "map_name_source": ocr_res.get("map_name_source", "default"),
                "media_path": file_path,
                "media_type": "video",
            },
        )

    def _on_replay_error(self, message: str):
        LOGGER.warning("Replay error: %s", message)
        self._emit_event("REPLAY_ERROR", {"message": message})

    # --- File Import & OCR ---

    def select_local_file(self) -> str | None:
        """Open native file dialog to select image or video file."""
        if not self._window:
            return None
        file_types = ("Evidence files (*.mp4;*.png;*.jpg;*.jpeg;*.mkv;*.avi;*.mov)", "All files (*.*)")
        result = self._window.create_file_dialog(
            getattr(webview.FileDialog, "OPEN", webview.OPEN_DIALOG),
            allow_multiple=False,
            file_types=file_types,
            directory=str(get_recordings_dir()),
        )
        if result and len(result) > 0:
            return result[0]
        return None

    def process_imported_file(self, file_path: str) -> dict[str, Any]:
        """Decode keyframes from an imported file and run OCR."""
        if not file_path or not os.path.exists(file_path):
            return {"status": "error", "message": "檔案不存在"}

        try:
            keyframes = self.capture_controller.load_keyframes(file_path)
            if not keyframes:
                return {"status": "error", "message": "無法解析媒體影格"}

            ext = Path(file_path).suffix.lower()
            media_type = "video" if ext in {".mp4", ".mkv", ".avi", ".mov"} else "image"
            ocr_res = self._perform_ocr(keyframes)

            return {
                "status": "success",
                "suspect_ids": ocr_res.get("suspect_ids", []),
                "map_name": ocr_res.get("map_name", ""),
                "ocr_map_name": ocr_res.get("ocr_map_name", ""),
                "map_name_source": ocr_res.get("map_name_source", "default"),
                "media_path": file_path,
                "media_type": media_type,
            }
        except Exception as err:
            LOGGER.error("process_imported_file error: %s", err)
            return {
                "status": "success",
                "suspect_ids": [],
                "map_name": self.config.get("default_map", "維多利亞島"),
                "ocr_map_name": "",
                "map_name_source": "default",
                "media_path": file_path,
                "media_type": "video",
            }

    # --- Report Submission Pipeline ---

    @_submission_guard
    def submit_report(self, form_data: dict[str, Any]) -> dict[str, Any]:
        """Upload evidence to GDrive/Discord and submit report via Playwright."""
        LOGGER.info("PyWebViewBridge: Submitting report form: %s", form_data)
        raw_file_path = form_data.get("file_path", "")
        file_path = (
            os.fspath(raw_file_path)
            if isinstance(raw_file_path, os.PathLike)
            else raw_file_path
            if isinstance(raw_file_path, str)
            else ""
        )
        dest = form_data.get("upload_destination") or self.config.get("upload_destination", "gdrive")
        evidence_url = form_data.get("evidence_url", "")

        # 1. Upload evidence if URL not yet provided
        if not evidence_url:
            if not file_path:
                message = "找不到事證檔案，請重新選取或錄製影片後再試。"
                self._emit_submission_status("uploading", message, "error")
                return {"status": "error", "message": message}
            if not os.path.isfile(file_path):
                message = "事證檔案不存在或無法讀取，請重新選取後再試。"
                self._emit_submission_status("uploading", message, "error")
                return {"status": "error", "message": message}

            self._emit_submission_status("uploading", "正在上傳事證檔案...")
            if dest == "gdrive":
                folder_name = self.config.get("gdrive_folder_name", "MapleClassic_Reports")
                ok, res_url = self.drive_mgr.upload_file_and_make_public(file_path, folder_name)
                if not ok:
                    message = f"Google Drive 上傳失敗: {res_url}"
                    self._emit_submission_status("uploading", message, "error")
                    return {"status": "error", "message": message}
                evidence_url = res_url
            else:
                webhook_url = self.config.get("discord_webhook_url", "")
                if not webhook_url:
                    message = "尚未設定 Discord Webhook URL"
                    self._emit_submission_status("uploading", message, "error")
                    return {"status": "error", "message": message}
                if not is_valid_discord_webhook_url(webhook_url):
                    message = "請先設定有效的 Discord HTTPS Webhook URL"
                    self._emit_submission_status("uploading", message, "error")
                    return {"status": "error", "message": message}
                desc = f"檢舉事證 - 玩家: {form_data.get('suspect_id')}, 地圖: {form_data.get('map_name')}"
                ok, res_msg = upload_evidence_to_discord(webhook_url, file_path, desc)
                if not ok:
                    message = f"Discord 上傳失敗: {res_msg}"
                    self._emit_submission_status("uploading", message, "error")
                    return {"status": "error", "message": message}
                evidence_url = res_msg

        # 2. Automated form submission via Playwright (or Dev Mode Dry-Run)
        dev_mode = form_data.get("dev_mode", self.config.get("dev_mode", False))
        if dev_mode:
            LOGGER.info("PyWebViewBridge: Developer mode enabled. Skipping actual Gamania submission.")
            self._emit_submission_status("dev_mode", "開發者模式：已略過實際提交")
            report_url = "https://forms.gamania.com/s/eLGg4"
            try:
                self.open_external_url(report_url)
            except Exception as e:
                LOGGER.warning("Could not open external url: %s", e)

            # Record in local history with dev mode note
            repo = getattr(self, "sanction_repo", None)
            if repo:
                repo.add_history_entry({
                    "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "suspect_id": form_data.get("suspect_id", ""),
                    "server": form_data.get("server_name") or form_data.get("server", "雪吉拉"),
                    "map": form_data.get("map_name", ""),
                    "url": evidence_url,
                    "status": "模擬成功",
                    "note": f"[開發者模式] {form_data.get('note', '')}".strip(),
                })
            else:
                add_history_entry({
                    "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "suspect_id": form_data.get("suspect_id", ""),
                    "server": form_data.get("server_name") or form_data.get("server", "雪吉拉"),
                    "map": form_data.get("map_name", ""),
                    "url": evidence_url,
                    "status": "模擬成功",
                    "note": f"[開發者模式] {form_data.get('note', '')}".strip(),
                })

            success_message = "開發者模式：已模擬檢舉成功（未實際送出），已在系統瀏覽器開啟檢舉頁面"
            self._emit_submission_status("completed", success_message, "success")
            return {
                "status": "success",
                "message": success_message,
                "evidence_url": evidence_url,
                "dev_mode": True,
            }

        self._emit_submission_status("filling", "正在自動填寫並送出官方檢舉表單...")
        headless_submit = form_data.get(
            "form_submit_headless",
            self.config.get("form_submit_headless", True),
        )
        if headless_submit is None:
            headless_submit = True
        try:
            ok, msg = submit_gamania_report(
                suspect_id=form_data.get("suspect_id", ""),
                server_name=form_data.get("server_name") or form_data.get("server", "雪吉拉"),
                map_name=form_data.get("map_name", ""),
                note=form_data.get("note", "自動打怪/外掛行為"),
                evidence_url=evidence_url,
                headless=bool(headless_submit),
            )
        except PlaywrightBrowserError as err:
            LOGGER.warning("Playwright submission error: %s", err)
            message = f"Playwright 錯誤: {err.details.summary}"
            self._emit_submission_status("filling", message, "error")
            return {"status": "error", "message": message}
        except Exception as err:
            LOGGER.error("Form filler unhandled error: %s", err)
            message = f"表單送出異常: {str(err)}"
            self._emit_submission_status("filling", message, "error")
            return {"status": "error", "message": message}

        # 3. Add to local history
        repo = getattr(self, "sanction_repo", None)
        if repo:
            repo.add_history_entry({
                "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                "suspect_id": form_data.get("suspect_id", ""),
                "server": form_data.get("server_name") or form_data.get("server", "雪吉拉"),
                "map": form_data.get("map_name", ""),
                "url": evidence_url,
                "status": "成功" if ok else "失敗",
                "note": form_data.get("note", ""),
            })
        else:
            add_history_entry({
                "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                "suspect_id": form_data.get("suspect_id", ""),
                "server": form_data.get("server_name") or form_data.get("server", "雪吉拉"),
                "map": form_data.get("map_name", ""),
                "url": evidence_url,
                "status": "成功" if ok else "失敗",
                "note": form_data.get("note", ""),
            })

        # 4. Auto-delete local recording if enabled
        if ok and bool(self.config.get("auto_delete_after_upload", False)):
            if file_path and is_owned_recording_path(file_path):
                try:
                    os.remove(file_path)
                    LOGGER.info("Auto-deleted confirmed evidence: %s", file_path)
                except OSError as err:
                    LOGGER.warning("Failed to auto-delete file: %s", err)

        self._emit_submission_status(
            "completed" if ok else "failed",
            msg,
            "success" if ok else "error",
        )
        return {
            "status": "success" if ok else "error",
            "message": msg,
            "evidence_url": evidence_url,
        }

    # --- Google Drive & Discord Integration ---

    def check_gdrive_auth(self) -> bool:
        """Check if Google Drive is authorized."""
        return self.drive_mgr.is_authenticated()

    def authenticate_gdrive(self) -> dict[str, Any]:
        """Trigger interactive Google Drive OAuth login in default browser."""
        ok, msg = self.drive_mgr.authenticate_interactive()
        is_auth = self.drive_mgr.is_authenticated()
        return {"success": ok, "message": msg, "is_authenticated": is_auth}

    def get_gdrive_folder_url(self, folder_name: str | None = None) -> str:
        """Return URL to the user's GDrive reports folder."""
        name = folder_name or self.config.get("gdrive_folder_name", "MapleClassic_Reports")
        if self.drive_mgr.is_authenticated():
            url = self.drive_mgr.get_folder_url(name)
            if url:
                return url
        return "https://drive.google.com/drive/my-drive"

    def test_discord_webhook(self, webhook_url: str) -> dict[str, Any]:
        """Test sending a test message to the Discord Webhook URL."""
        if not webhook_url:
            return {"success": False, "message": "請先輸入 Webhook URL"}
        if not is_valid_discord_webhook_url(webhook_url):
            return {"success": False, "message": "請輸入有效的 Discord HTTPS Webhook URL"}
        try:
            import requests
            res = requests.post(
                webhook_url,
                json={"content": " Maple Classic Reporter: Webhook 連線測試成功！"},
                timeout=8,
            )
            if res.status_code in (200, 204):
                return {"success": True, "message": "Discord Webhook 測試連線成功！"}
            return {"success": False, "message": f"Webhook 回傳錯誤碼: {res.status_code}"}
        except Exception as err:
            return {"success": False, "message": f"連線失敗: {str(err)}"}

    # --- System & Utilities ---

    def open_external_url(self, url: str) -> bool:
        """Open URL in system default browser."""
        from maple_reporter.utils.urls import is_safe_https_url

        if not is_safe_https_url(url):
            LOGGER.warning("Blocked unsafe external URL: %r", url)
            return False
        return bool(webbrowser.open(url))

    def open_file_location(self, file_path: str) -> None:
        """Open File Explorer highlighting the specified file."""
        if file_path and os.path.exists(file_path):
            subprocess.Popen(["explorer", "/select,", os.path.normpath(file_path)])

    def open_media_file(self, file_path: str) -> None:
        """Open image or video in system default viewer."""
        if file_path and os.path.exists(file_path):
            os.startfile(os.path.normpath(file_path))

    def get_media_preview(self, file_path: str) -> str:
        """Return base64 data URL for an image or video thumbnail."""
        if not file_path or not os.path.exists(file_path):
            return ""
        try:
            ext = Path(file_path).suffix.lower()
            if ext in {".png", ".jpg", ".jpeg", ".bmp", ".webp"}:
                with open(file_path, "rb") as f:
                    data = f.read()
                mime = "image/png" if ext == ".png" else "image/jpeg"
                b64 = base64.b64encode(data).decode("utf-8")
                return f"data:{mime};base64,{b64}"
            elif ext in {".mp4", ".mkv", ".avi", ".mov"}:
                keyframes = self.capture_controller.load_keyframes(file_path)
                if keyframes and len(keyframes) > 0:
                    buffered = io.BytesIO()
                    keyframes[0].save(buffered, format="JPEG", quality=85)
                    b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
                    return f"data:image/jpeg;base64,{b64}"
        except Exception as err:
            LOGGER.warning("Failed to generate media preview for %s: %s", file_path, err)
        return ""

    def get_media_stream_url(self, file_path: str) -> str:
        """Return streaming HTTP URL for local media file to support HTML5 video playback."""
        if not file_path or not os.path.exists(file_path):
            return ""
        if not self.media_server or not self.media_server.port:
            self.media_server.start()
        encoded = base64.urlsafe_b64encode(file_path.encode("utf-8")).decode("utf-8")
        return f"http://127.0.0.1:{self.media_server.port}/media?path={encoded}"

    def trim_video_segment(
        self,
        file_path: str,
        cut_start: float,
        cut_end: float,
        original_backup_path: str | None = None,
    ) -> dict[str, Any]:
        """
        Cut out a segment [cut_start, cut_end] from the video file.
        Preserves original backup and outputs standard cleanly named video.
        """
        if not file_path or not os.path.exists(file_path):
            return {"success": False, "error": "檔案不存在"}

        try:
            # 1. Determine backup path
            rec_dir = get_recordings_dir()
            backup_file = original_backup_path
            if not backup_file or not os.path.exists(backup_file):
                # Create original backup
                backup_name = f".backup_{Path(file_path).name}"
                backup_file = str(rec_dir / backup_name)
                shutil.copy2(file_path, backup_file)
                LOGGER.info("Created original backup at %s", backup_file)

            # 2. Prepare target output path with clean name
            timestamp = time.time_ns() // 1_000_000
            target_path = str(rec_dir / f"maple_evidence_replay_{timestamp}.mp4")

            # 3. Perform cut
            ok = cut_video_segment(file_path, cut_start, cut_end, target_path)
            if not ok or not os.path.exists(target_path):
                return {"success": False, "error": "影片區段剪輯失敗"}

            new_duration = get_video_duration(target_path)
            stream_url = self.get_media_stream_url(target_path)

            return {
                "success": True,
                "new_path": target_path,
                "duration": new_duration,
                "stream_url": stream_url,
                "original_backup_path": backup_file,
            }
        except Exception as err:
            LOGGER.error("trim_video_segment failed: %s", err, exc_info=True)
            return {"success": False, "error": str(err)}

    def restore_original_video(self, current_path: str, backup_path: str) -> dict[str, Any]:
        """Restore edited video back to original backup."""
        if not backup_path or not os.path.exists(backup_path):
            return {"success": False, "error": "找不到原始備份影片"}

        try:
            rec_dir = get_recordings_dir()
            timestamp = time.time_ns() // 1_000_000
            restored_path = str(rec_dir / f"maple_evidence_replay_{timestamp}.mp4")
            shutil.copy2(backup_path, restored_path)

            new_duration = get_video_duration(restored_path)
            stream_url = self.get_media_stream_url(restored_path)

            return {
                "success": True,
                "restored_path": restored_path,
                "duration": new_duration,
                "stream_url": stream_url,
            }
        except Exception as err:
            LOGGER.error("restore_original_video failed: %s", err)
            return {"success": False, "error": str(err)}

    def clear_all_recordings(self) -> dict[str, Any]:
        """Delete all media files in recordings directory and return count and freed bytes."""
        rec_dir = get_recordings_dir()
        files = [f for f in rec_dir.iterdir() if f.is_file()]
        deleted = 0
        total_bytes = 0
        for f in files:
            try:
                size = f.stat().st_size
                f.unlink()
                deleted += 1
                total_bytes += size
            except OSError as err:
                LOGGER.warning("Failed to delete %s: %s", f.name, err)

        if total_bytes < 1024:
            size_str = f"{total_bytes} B"
        elif total_bytes < 1024 * 1024:
            size_str = f"{total_bytes / 1024:.1f} KB"
        else:
            size_str = f"{total_bytes / (1024 * 1024):.1f} MB"

        return {
            "success": True,
            "count": deleted,
            "total_bytes": total_bytes,
            "size_str": size_str,
        }

    def open_app_data_folder(self) -> None:
        """Open the local AppData folder in Explorer."""
        folder = get_user_app_data_dir()
        folder.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            os.startfile(str(folder))
        else:
            subprocess.Popen(["explorer", str(folder)])

    def open_log_file(self) -> bool:
        """Open the reporter.log file in default text editor."""
        log_file = get_user_app_data_dir() / "logs" / "reporter.log"
        if not log_file.exists():
            log_file.parent.mkdir(parents=True, exist_ok=True)
            log_file.write_text("", encoding="utf-8")
        try:
            if os.name == "nt":
                os.startfile(str(log_file))
            else:
                subprocess.Popen(["notepad", str(log_file)])
            return True
        except Exception as err:
            LOGGER.warning("Failed to open log file: %s", err)
            return False

    def open_log_folder(self) -> None:
        """Open the logs folder in File Explorer."""
        folder = get_user_app_data_dir() / "logs"
        folder.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            os.startfile(str(folder))
        else:
            subprocess.Popen(["explorer", str(folder)])

    def shutdown(self) -> None:
        """Clean shutdown of background threads."""
        self.hotkey_listener.stop()
        self.replay_recorder.stop()
        self.sanction_coordinator.cancel(timeout=1.0)
        if self.media_server:
            self.media_server.stop()
