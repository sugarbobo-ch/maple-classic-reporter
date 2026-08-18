"""PyWebView JS Bridge connecting React UI with Python backend services."""

from __future__ import annotations

import base64
import concurrent.futures
import ctypes
from ctypes import wintypes
from functools import wraps
import io
import json
import logging
import math
import mimetypes
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time
from typing import Any
import urllib.parse
import webbrowser

import numpy as np
from PIL import Image
import webview

from maple_reporter.automation.form_filler import submit_gamania_report
from maple_reporter.automation.playwright_runtime import PlaywrightBrowserError
from maple_reporter.discord.webhook_service import (
    is_valid_discord_webhook_url,
    upload_evidence_to_discord,
)
from maple_reporter.gdrive.drive_service import GoogleDriveManager
from maple_reporter.gui.bridge import (
    BaseBridgeMixin,
    ConfigBridgeMixin,
    IntegrationBridgeMixin,
    MediaBridgeMixin,
    PyWebViewBridge,
    RecordingBridgeMixin,
    ReplayBridgeMixin,
    SubmissionBridgeMixin,
    _choose_preferred_window,
    _submission_guard,
)
from maple_reporter.gui.bridge_hotkeys import (
    CF_UNICODETEXT,
    HOTKEY_ACTIONS,
    MOD_ALT,
    MOD_CONTROL,
    MOD_NOREPEAT,
    MOD_SHIFT,
    MOD_WIN,
    VK_MAP,
    WM_HOTKEY,
    BackgroundHotkeyListener,
    read_system_clipboard_text,
    write_system_clipboard_text,
)
from maple_reporter.gui.evidence_capture_controller import EvidenceCaptureController
from maple_reporter.gui.history_controller import HistoryController
from maple_reporter.gui.media_server import LocalMediaServer, _RangeMediaRequestHandler
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

__all__ = [
    "PyWebViewBridge",
    "BaseBridgeMixin",
    "WindowBridgeMixin",
    "RecordingBridgeMixin",
    "ReplayBridgeMixin",
    "MediaBridgeMixin",
    "SubmissionBridgeMixin",
    "ConfigBridgeMixin",
    "IntegrationBridgeMixin",
    "_choose_preferred_window",
    "_submission_guard",
    "load_config",
    "save_config",
    "get_recordings_dir",
    "get_user_app_data_dir",
    "is_owned_recording_path",
    "add_history_entry",
    "LocalMediaServer",
    "BackgroundHotkeyListener",
    "GoogleDriveManager",
    "ReplayBufferRecorder",
    "SanctionRepository",
    "SanctionSyncCoordinator",
    "HistoryController",
    "EvidenceCaptureController",
    "read_system_clipboard_text",
    "write_system_clipboard_text",
    "record_capture_screenshot",
    "capture_window_screenshot",
    "find_window_bounds",
    "focus_window",
    "get_active_windows",
    "is_window_minimized",
    "order_window_candidates",
    "record_short_video",
    "select_preferred_window_title",
    "begin_native_resize",
    "_window_handle",
    "prepare_native_drag",
    "move_window_by_drag_delta",
    "submit_gamania_report",
    "recognize_candidates_from_image_list",
    "recognize_map_name_from_image_list",
]
