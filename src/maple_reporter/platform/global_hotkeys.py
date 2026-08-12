"""Windows global hotkeys bridged into the Qt event loop.

The application uses ``RegisterHotKey`` instead of a regular Qt shortcut so
the hotkeys continue to work while a game window owns the foreground focus.
This module deliberately does not install a low-level keyboard hook: the
registered combination is observed by Windows, but keyboard input is not
swallowed from the foreground application.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import logging
import os
import re
from dataclasses import dataclass
from typing import Mapping

from PySide6.QtCore import QAbstractNativeEventFilter, QCoreApplication, QObject, Signal


LOGGER = logging.getLogger(__name__)

WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

ACTION_SAVE_REPLAY = "save_replay"
ACTION_RECORD_VIDEO = "record_video"
DEFAULT_SAVE_REPLAY_KEY = "F9"
DEFAULT_RECORD_VIDEO_KEY = "F10"
DEFAULT_SAVE_REPLAY_HOTKEY = f"Ctrl+Shift+{DEFAULT_SAVE_REPLAY_KEY}"
DEFAULT_RECORD_VIDEO_HOTKEY = f"Ctrl+Shift+{DEFAULT_RECORD_VIDEO_KEY}"
HOTKEY_ACTIONS = (ACTION_SAVE_REPLAY, ACTION_RECORD_VIDEO)
HOTKEY_IDS = {
    ACTION_SAVE_REPLAY: 1,
    ACTION_RECORD_VIDEO: 2,
}

_MODIFIER_ALIASES = {
    "CTRL": ("Ctrl", MOD_CONTROL),
    "CONTROL": ("Ctrl", MOD_CONTROL),
    "ALT": ("Alt", MOD_ALT),
    "SHIFT": ("Shift", MOD_SHIFT),
    "WIN": ("Win", MOD_WIN),
    "WINDOWS": ("Win", MOD_WIN),
}

_SPECIAL_KEYS = {
    "SPACE": ("Space", 0x20),
    "TAB": ("Tab", 0x09),
    "ENTER": ("Enter", 0x0D),
    "RETURN": ("Enter", 0x0D),
    "ESC": ("Esc", 0x1B),
    "ESCAPE": ("Esc", 0x1B),
    "INSERT": ("Insert", 0x2D),
    "DELETE": ("Delete", 0x2E),
    "HOME": ("Home", 0x24),
    "END": ("End", 0x23),
    "PAGEUP": ("PageUp", 0x21),
    "PAGEDOWN": ("PageDown", 0x22),
    "UP": ("Up", 0x26),
    "DOWN": ("Down", 0x28),
    "LEFT": ("Left", 0x25),
    "RIGHT": ("Right", 0x27),
}

# The UI exposes only this final key.  Ctrl and Shift are intentionally fixed
# so users cannot accidentally choose a single-key shortcut or a combination
# that is likely to overlap with the game's own controls.
HOTKEY_KEY_OPTIONS = tuple(
    [f"F{number}" for number in range(1, 12)]
    + [f"F{number}" for number in range(13, 25)]
    + list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    + list("0123456789")
)


class HotkeyParseError(ValueError):
    """Raised when a configured shortcut cannot be represented by Win32."""


@dataclass(frozen=True)
class ParsedHotkey:
    """A canonical shortcut and the values required by ``RegisterHotKey``."""

    shortcut: str
    modifiers: int
    virtual_key: int


def _parse_key(token: str) -> tuple[str, int]:
    normalized = token.strip().upper()
    if normalized in _SPECIAL_KEYS:
        return _SPECIAL_KEYS[normalized]

    function_match = re.fullmatch(r"F([1-9]|1[0-9]|2[0-4])", normalized)
    if function_match:
        number = int(function_match.group(1))
        return f"F{number}", 0x6F + number

    if len(normalized) == 1 and "A" <= normalized <= "Z":
        return normalized, ord(normalized)
    if len(normalized) == 1 and "0" <= normalized <= "9":
        return normalized, ord(normalized)

    raise HotkeyParseError(f"不支援的快捷鍵：{token.strip()}")


def parse_hotkey(shortcut: str) -> ParsedHotkey:
    """Parse a user-facing shortcut such as ``Ctrl+Shift+F9``.

    At least one modifier is required.  Requiring a modifier prevents an
    accidental single key from becoming unavailable to the game and makes
    the setting safer to change in a text field.
    """

    if not isinstance(shortcut, str):
        raise HotkeyParseError("快捷鍵必須是文字，例如 Ctrl+Shift+F9。")

    parts = [part.strip() for part in shortcut.split("+") if part.strip()]
    if len(parts) < 2:
        raise HotkeyParseError("請使用至少一個修飾鍵，例如 Ctrl+Shift+F9。")

    modifier_names: list[str] = []
    modifiers = 0
    for token in parts[:-1]:
        modifier = _MODIFIER_ALIASES.get(token.upper())
        if modifier is None:
            raise HotkeyParseError(f"不支援的修飾鍵：{token}")
        display_name, modifier_value = modifier
        if modifiers & modifier_value:
            raise HotkeyParseError(f"修飾鍵重複：{display_name}")
        modifier_names.append(display_name)
        modifiers |= modifier_value

    key_name, virtual_key = _parse_key(parts[-1])
    if key_name == "F12":
        raise HotkeyParseError("F12 保留給 Windows 除錯器，請改用其他按鍵。")

    # Keep the display stable even when users type e.g. alt+control+r.
    modifier_order = {"Ctrl": 0, "Alt": 1, "Shift": 2, "Win": 3}
    modifier_names.sort(key=lambda name: modifier_order[name])
    canonical = "+".join((*modifier_names, key_name))
    return ParsedHotkey(canonical, modifiers, virtual_key)


def fixed_hotkey_for_key(key: str) -> str:
    """Return the configured shortcut for a UI-selected final key."""

    return parse_hotkey(f"Ctrl+Shift+{str(key).strip()}").shortcut


def hotkey_key_from_shortcut(shortcut: str, fallback: str) -> str:
    """Extract a supported final key from a legacy full shortcut setting."""

    try:
        key = parse_hotkey(shortcut).shortcut.rsplit("+", 1)[-1]
    except HotkeyParseError:
        return fallback
    return key if key in HOTKEY_KEY_OPTIONS else fallback


class _NativeHotkeyEventFilter(QAbstractNativeEventFilter):
    """Convert Windows ``WM_HOTKEY`` messages into manager callbacks."""

    def __init__(self, manager: "GlobalHotkeyManager") -> None:
        super().__init__()
        self._manager = manager

    def nativeEventFilter(self, event_type, message):  # noqa: N802 - Qt API
        return self._manager._handle_native_event(event_type, message)


@dataclass(frozen=True)
class _Configuration:
    hwnd: int
    enabled: bool
    bindings: dict[str, str]


class GlobalHotkeyManager(QObject):
    """Register and dispatch application-wide Windows hotkeys."""

    activated = Signal(str)
    registration_changed = Signal(str, bool, str, str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._hwnd = 0
        self._enabled = False
        self._registered: dict[str, int] = {}
        self._active_bindings: dict[str, str] = {}
        self._last_error = ""
        self._event_filter = _NativeHotkeyEventFilter(self)
        self._application = QCoreApplication.instance()
        if self._application is not None:
            self._application.installNativeEventFilter(self._event_filter)

        self._user32 = None
        if os.name == "nt":
            self._user32 = ctypes.WinDLL("user32", use_last_error=True)
            self._user32.RegisterHotKey.argtypes = [
                ctypes.wintypes.HWND,
                ctypes.c_int,
                ctypes.wintypes.UINT,
                ctypes.wintypes.UINT,
            ]
            self._user32.RegisterHotKey.restype = ctypes.wintypes.BOOL
            self._user32.UnregisterHotKey.argtypes = [
                ctypes.wintypes.HWND,
                ctypes.c_int,
            ]
            self._user32.UnregisterHotKey.restype = ctypes.wintypes.BOOL

    @property
    def active_bindings(self) -> dict[str, str]:
        """Return the shortcuts currently registered with Windows."""

        return dict(self._active_bindings)

    @property
    def last_error(self) -> str:
        return self._last_error

    @property
    def is_enabled(self) -> bool:
        return self._enabled and bool(self._registered)

    def configure(
        self,
        hwnd: int,
        *,
        enabled: bool,
        bindings: Mapping[str, str],
    ) -> bool:
        """Apply a complete binding set transactionally.

        If a new shortcut is invalid or already in use, the previous set is
        restored.  This keeps a typo in settings from leaving the application
        without its previously working global shortcuts.
        """

        requested = {
            action: str(bindings.get(action, "") or "").strip()
            for action in HOTKEY_ACTIONS
        }
        previous = _Configuration(
            self._hwnd,
            self._enabled,
            dict(self._active_bindings),
        )
        self._last_error = ""

        if not enabled:
            self._unregister_all()
            self._hwnd = int(hwnd)
            self._enabled = False
            self._active_bindings = {}
            for action in HOTKEY_ACTIONS:
                self.registration_changed.emit(
                    action,
                    False,
                    requested[action],
                    "全域快捷鍵已停用",
                )
            return True

        try:
            parsed = self._parse_bindings(requested)
        except HotkeyParseError as error:
            self._last_error = str(error)
            self.registration_changed.emit("", False, "", self._last_error)
            return False

        self._unregister_all()
        self._hwnd = int(hwnd)
        self._enabled = True
        if self._register_bindings(parsed):
            self._active_bindings = {
                action: definition.shortcut
                for action, definition in parsed.items()
            }
            return True

        failure = self._last_error or "Windows 無法註冊快捷鍵。"
        self._unregister_all()
        self._enabled = False
        self._active_bindings = {}
        self._restore(previous)
        self._last_error = failure
        return False

    def shutdown(self) -> None:
        """Unregister all hotkeys and detach the native event filter."""

        self._unregister_all()
        self._enabled = False
        self._active_bindings = {}
        if self._application is not None:
            self._application.removeNativeEventFilter(self._event_filter)
            self._application = None

    def _parse_bindings(
        self, bindings: Mapping[str, str]
    ) -> dict[str, ParsedHotkey]:
        parsed: dict[str, ParsedHotkey] = {}
        seen: dict[str, str] = {}
        for action in HOTKEY_ACTIONS:
            shortcut = bindings.get(action, "")
            if not shortcut:
                continue
            definition = parse_hotkey(shortcut)
            previous_action = seen.get(definition.shortcut.upper())
            if previous_action is not None:
                raise HotkeyParseError(
                    f"{definition.shortcut} 同時指定給兩個功能，請改用不同快捷鍵。"
                )
            seen[definition.shortcut.upper()] = action
            parsed[action] = definition
        if not parsed:
            raise HotkeyParseError("請至少設定一組全域快捷鍵。")
        return parsed

    def _register_bindings(self, bindings: Mapping[str, ParsedHotkey]) -> bool:
        if os.name != "nt" or self._user32 is None:
            self._last_error = "全域快捷鍵目前只支援 Windows。"
            self.registration_changed.emit("", False, "", self._last_error)
            return False

        for action, definition in bindings.items():
            hotkey_id = HOTKEY_IDS[action]
            ok = bool(
                self._user32.RegisterHotKey(
                    ctypes.wintypes.HWND(self._hwnd),
                    hotkey_id,
                    definition.modifiers | MOD_NOREPEAT,
                    definition.virtual_key,
                )
            )
            if not ok:
                error_code = ctypes.get_last_error()
                if error_code == 1409:
                    reason = "快捷鍵已被其他程式使用。"
                else:
                    reason = f"Windows 無法註冊此快捷鍵（錯誤碼 {error_code}）。"
                self._last_error = f"{definition.shortcut}：{reason}"
                self.registration_changed.emit(
                    action,
                    False,
                    definition.shortcut,
                    self._last_error,
                )
                return False

            self._registered[action] = hotkey_id
            self.registration_changed.emit(
                action,
                True,
                definition.shortcut,
                "已註冊",
            )
        return True

    def _restore(self, previous: _Configuration) -> None:
        self._hwnd = previous.hwnd
        self._enabled = previous.enabled
        if not previous.enabled or not previous.bindings:
            self._active_bindings = {}
            return
        try:
            parsed = self._parse_bindings(previous.bindings)
        except HotkeyParseError:
            LOGGER.exception("無法解析先前的全域快捷鍵設定")
            self._enabled = False
            self._active_bindings = {}
            return
        if self._register_bindings(parsed):
            self._active_bindings = {
                action: definition.shortcut
                for action, definition in parsed.items()
            }
        else:
            LOGGER.warning("無法恢復先前的全域快捷鍵設定：%s", self._last_error)
            self._enabled = False
            self._active_bindings = {}

    def _unregister_all(self) -> None:
        if self._user32 is not None and self._hwnd:
            for hotkey_id in tuple(self._registered.values()):
                try:
                    self._user32.UnregisterHotKey(
                        ctypes.wintypes.HWND(self._hwnd), hotkey_id
                    )
                except OSError:
                    LOGGER.debug("解除全域快捷鍵失敗", exc_info=True)
        self._registered.clear()

    def _handle_native_event(self, _event_type, message):
        if os.name != "nt":
            return False, 0
        try:
            address = int(message)
            if not address:
                return False, 0
            native_message = ctypes.wintypes.MSG.from_address(address)
            if int(native_message.message) != WM_HOTKEY:
                return False, 0
            hotkey_id = int(native_message.wParam)
        except (TypeError, ValueError, OSError):
            return False, 0

        for action, registered_id in self._registered.items():
            if hotkey_id == registered_id:
                self.activated.emit(action)
                return True, 0
        return False, 0


__all__ = [
    "ACTION_RECORD_VIDEO",
    "ACTION_SAVE_REPLAY",
    "DEFAULT_RECORD_VIDEO_HOTKEY",
    "DEFAULT_RECORD_VIDEO_KEY",
    "DEFAULT_SAVE_REPLAY_HOTKEY",
    "DEFAULT_SAVE_REPLAY_KEY",
    "GlobalHotkeyManager",
    "HOTKEY_ACTIONS",
    "HOTKEY_KEY_OPTIONS",
    "HOTKEY_IDS",
    "HotkeyParseError",
    "MOD_NOREPEAT",
    "ParsedHotkey",
    "fixed_hotkey_for_key",
    "hotkey_key_from_shortcut",
    "parse_hotkey",
]
