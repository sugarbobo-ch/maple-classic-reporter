"""Base bridge mixin and lifecycle management."""

from __future__ import annotations

import concurrent.futures
import ctypes
from ctypes import wintypes
import json
import logging
import os
import sys
import threading
from typing import Any

import numpy as np
import webview
from PIL import Image
from maple_reporter.update.service import UpdateService

LOGGER = logging.getLogger(__name__)


def _bridge_mod():
    import maple_reporter.gui.pywebview_bridge as bridge_mod

    return bridge_mod


class BaseBridgeMixin:
    """Core state, lifecycle, event dispatcher and OCR engine for the PyWebView bridge."""

    def __init__(self, window: webview.Window | None = None, **kwargs):
        super().__init__(**kwargs)
        mod = _bridge_mod()
        self._window = window
        self.config = mod.load_config()
        self.history_controller = mod.HistoryController()
        self.capture_controller = mod.EvidenceCaptureController()
        self.drive_mgr = mod.GoogleDriveManager()
        self.replay_recorder = mod.ReplayBufferRecorder(
            state_callback=self._on_replay_state_changed,
            replay_saved_callback=self._on_replay_saved,
            error_callback=self._on_replay_error,
        )
        self.sanction_repo = mod.SanctionRepository()
        self.sanction_coordinator = mod.SanctionSyncCoordinator(
            repository=self.sanction_repo,
            event_emitter=self._emit_event,
        )

        # Recording state tracking
        self._recording_active = False
        self._cancel_requested = False
        self._recording_thread: threading.Thread | None = None
        self._submission_lock = threading.Lock()
        self._config_lock = threading.RLock()

        self.update_service = UpdateService(
            emit_event=self._emit_event,
            get_config=lambda: self.config,
            is_busy=lambda: bool(
                self._recording_active
                or self._replay_state not in {"idle", "stopped"}
                or self._submission_lock.locked()
            ),
            close_app=self._close_for_update,
        )

        # Replay status
        self._replay_state = "idle"
        self._replay_duration = 0.0
        self._window_maximized = False
        self._drag_move_baseline: tuple[float, float] | None = None

        # Media streaming server
        self.media_server = mod.LocalMediaServer()
        self.media_server.start()

        # Global hotkey listener
        self.hotkey_listener = mod.BackgroundHotkeyListener(self._handle_global_hotkey)
        self._init_hotkeys()

    @property
    def _safe_config_lock(self) -> threading.RLock:
        if not hasattr(self, "_config_lock") or self._config_lock is None:
            self._config_lock = threading.RLock()
        return self._config_lock

    def _close_for_update(self) -> None:
        try:
            if self._window:
                self._window.destroy()
        except Exception:
            pass
        threading.Timer(0.3, lambda: os._exit(0)).start()

    def _init_hotkeys(self) -> None:
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
            self._window.evaluate_js(
                f"if(window.__MAPLE_REPORTER_EVENT__)window.__MAPLE_REPORTER_EVENT__({payload});"
            )
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

    def _perform_ocr(self, keyframes: list[Image.Image]) -> dict[str, Any]:
        """Run rapid OCR in stages with event callbacks and timeout safeguards."""
        mod = _bridge_mod()
        default_map = str(self.config.get("default_map", "") or "").strip()
        if not keyframes:
            return {
                "suspect_ids": [],
                "map_name": default_map,
                "ocr_map_name": "",
                "map_name_source": "default",
            }

        try:
            # Subsample keyframes if there are too many (cap at 12 frames for thorough coverage and fast OCR)
            if len(keyframes) > 12:
                indices = np.linspace(0, len(keyframes) - 1, num=12, dtype=int)
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
                            mod.recognize_map_name_from_image_list,
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
                            mod.recognize_candidates_from_image_list,
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

    def _restore_gui_window(self) -> None:
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

    def shutdown(self) -> None:
        """Clean shutdown of background threads."""
        if hasattr(self, "hotkey_listener") and self.hotkey_listener:
            self.hotkey_listener.stop()
        if hasattr(self, "replay_recorder") and self.replay_recorder:
            self.replay_recorder.stop()
        if hasattr(self, "sanction_coordinator") and self.sanction_coordinator:
            self.sanction_coordinator.cancel(timeout=1.0)
        if hasattr(self, "update_service") and self.update_service:
            self.update_service.shutdown()
        if hasattr(self, "media_server") and self.media_server:
            self.media_server.stop()
