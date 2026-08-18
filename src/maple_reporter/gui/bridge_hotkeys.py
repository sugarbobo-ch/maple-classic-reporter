"""Win32 global hotkey listener and clipboard helpers for PyWebView bridge."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import logging
import os
import threading
from typing import Any, Callable

LOGGER = logging.getLogger(__name__)

WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

HOTKEY_ACTIONS = {
    1: "save_replay",
    2: "record_video",
}

VK_MAP = {
    **{f"F{i}": 0x70 + (i - 1) for i in range(1, 25)},
    **{chr(c): c for c in range(ord("A"), ord("Z") + 1)},
    **{str(d): ord(str(d)) for d in range(10)},
    "SPACE": 0x20,
    "TAB": 0x09,
    "ENTER": 0x0D,
    "ESC": 0x1B,
    "ESCAPE": 0x1B,
    "INSERT": 0x2D,
    "DELETE": 0x2E,
    "HOME": 0x24,
    "END": 0x23,
    "PAGEUP": 0x21,
    "PAGEDOWN": 0x22,
    "UP": 0x26,
    "DOWN": 0x28,
    "LEFT": 0x25,
    "RIGHT": 0x27,
}

CF_UNICODETEXT = 13


def read_system_clipboard_text() -> str:
    """Read plain text from the native Windows clipboard without WebView permissions."""
    if os.name != "nt":
        return ""

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    user32.OpenClipboard.argtypes = [ctypes.wintypes.HWND]
    user32.OpenClipboard.restype = ctypes.wintypes.BOOL
    user32.GetClipboardData.argtypes = [ctypes.wintypes.UINT]
    user32.GetClipboardData.restype = ctypes.c_void_p
    user32.CloseClipboard.argtypes = []
    user32.CloseClipboard.restype = ctypes.wintypes.BOOL
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalUnlock.restype = ctypes.wintypes.BOOL

    if not user32.OpenClipboard(None):
        return ""

    try:
        clipboard_handle = user32.GetClipboardData(CF_UNICODETEXT)
        if not clipboard_handle:
            return ""

        text_pointer = kernel32.GlobalLock(clipboard_handle)
        if not text_pointer:
            return ""

        try:
            return ctypes.wstring_at(text_pointer)
        finally:
            kernel32.GlobalUnlock(clipboard_handle)
    except (OSError, ValueError):
        LOGGER.debug("Unable to read native clipboard text", exc_info=True)
        return ""
    finally:
        user32.CloseClipboard()


def write_system_clipboard_text(text: str) -> bool:
    """Write plain text to the native Windows clipboard."""
    if os.name != "nt" or not isinstance(text, str):
        return False

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    user32.OpenClipboard.argtypes = [ctypes.wintypes.HWND]
    user32.OpenClipboard.restype = ctypes.wintypes.BOOL
    user32.EmptyClipboard.argtypes = []
    user32.EmptyClipboard.restype = ctypes.wintypes.BOOL
    user32.SetClipboardData.argtypes = [ctypes.wintypes.UINT, ctypes.c_void_p]
    user32.SetClipboardData.restype = ctypes.c_void_p
    user32.CloseClipboard.argtypes = []
    user32.CloseClipboard.restype = ctypes.wintypes.BOOL
    kernel32.GlobalAlloc.argtypes = [ctypes.wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = ctypes.c_void_p
    kernel32.GlobalFree.argtypes = [ctypes.c_void_p]
    kernel32.GlobalFree.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalUnlock.restype = ctypes.wintypes.BOOL

    # CF_UNICODETEXT expects a UTF-16LE buffer with a terminating null.
    encoded_text = (text + "\0").encode("utf-16-le")
    global_handle = kernel32.GlobalAlloc(0x0002, len(encoded_text))  # GMEM_MOVEABLE
    if not global_handle:
        return False

    try:
        text_pointer = kernel32.GlobalLock(global_handle)
        if not text_pointer:
            return False

        try:
            ctypes.memmove(text_pointer, encoded_text, len(encoded_text))
        finally:
            kernel32.GlobalUnlock(global_handle)

        if not user32.OpenClipboard(None):
            return False

        try:
            if not user32.EmptyClipboard():
                return False
            if not user32.SetClipboardData(CF_UNICODETEXT, global_handle):
                return False

            # Ownership transfers to the clipboard after SetClipboardData.
            global_handle = None
            return True
        finally:
            user32.CloseClipboard()
    except (OSError, ValueError):
        LOGGER.debug("Unable to write native clipboard text", exc_info=True)
        return False
    finally:
        if global_handle:
            kernel32.GlobalFree(global_handle)


class BackgroundHotkeyListener:
    """Threaded Win32 RegisterHotKey message pump that runs in the background."""

    def __init__(self, on_hotkey_callback: Callable[[str], Any]):
        self.on_hotkey_callback = on_hotkey_callback
        self._thread: threading.Thread | None = None
        self._thread_id: int | None = None
        self._running = False
        self._bindings: dict[int, tuple[int, int]] = {}  # id -> (mod, vk)

    def update_bindings(self, save_key: str, record_key: str, enabled: bool):
        new_bindings = {}
        if enabled:
            clean_save = (save_key or "F9").split("+")[-1].strip().upper()
            clean_record = (record_key or "F10").split("+")[-1].strip().upper()
            save_vk = VK_MAP.get(clean_save, 0x78)  # F9
            record_vk = VK_MAP.get(clean_record, 0x79)  # F10
            # Default to Ctrl + Shift
            mod = MOD_CONTROL | MOD_SHIFT | MOD_NOREPEAT
            new_bindings[1] = (mod, save_vk)
            new_bindings[2] = (mod, record_vk)

        self._bindings = new_bindings
        if enabled and not self._running:
            self.start()
        elif not enabled and self._running:
            self.stop()
        elif self._running:
            # Restart thread to re-register
            self.stop()
            self.start()

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        if not self._running:
            return
        self._running = False
        if self._thread_id and os.name == "nt":
            user32 = ctypes.windll.user32
            WM_QUIT = 0x0012
            user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None

    def _run(self):
        if os.name != "nt":
            return
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        self._thread_id = kernel32.GetCurrentThreadId()

        # Register hotkeys
        registered_ids = []
        for hk_id, (mod, vk) in self._bindings.items():
            if user32.RegisterHotKey(0, hk_id, mod, vk):
                registered_ids.append(hk_id)
            else:
                LOGGER.warning("Failed to register hotkey %d (mod=%x, vk=%x)", hk_id, mod, vk)

        msg = ctypes.wintypes.MSG()
        while self._running:
            b_ret = user32.GetMessageW(ctypes.byref(msg), 0, 0, 0)
            if b_ret <= 0:
                break
            if msg.message == WM_HOTKEY:
                action = HOTKEY_ACTIONS.get(msg.wParam)
                if action and self.on_hotkey_callback:
                    try:
                        self.on_hotkey_callback(action)
                    except Exception as err:
                        LOGGER.error("Hotkey callback error: %s", err)
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        for hk_id in registered_ids:
            user32.UnregisterHotKey(0, hk_id)
        self._thread_id = None
