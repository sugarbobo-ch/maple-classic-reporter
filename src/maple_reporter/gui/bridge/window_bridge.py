"""Frameless window controls and native drag/resize integration."""

from __future__ import annotations

import logging
import os
import webview

LOGGER = logging.getLogger(__name__)


def _bridge_mod():
    import maple_reporter.gui.pywebview_bridge as bridge_mod

    return bridge_mod


class WindowBridgeMixin:
    """Methods for controlling desktop window state and handling drag/resize operations."""

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
        if previous is None or not getattr(self, "_window", None):
            return
        mod = _bridge_mod()
        hwnd = mod._window_handle(self._window)
        if hwnd:
            mod.move_window_by_drag_delta(hwnd, point[0] - previous[0], point[1] - previous[1])

    def _set_window_maximized_state(self, maximized: bool) -> None:
        self._window_maximized = maximized
        self._emit_event("WINDOW_MAXIMIZED" if maximized else "WINDOW_RESTORED")

    def handle_window_maximized(self) -> None:
        """Keep the React title-bar state in sync with native maximize events."""
        self._set_window_maximized_state(True)

    def handle_window_restored(self) -> None:
        """Keep the React title-bar state in sync with native restore events."""
        self._set_window_maximized_state(False)

    def minimize_window(self) -> bool:
        """Minimize the desktop window."""
        if not getattr(self, "_window", None):
            return False
        try:
            self._window.minimize()
            return True
        except Exception as err:
            LOGGER.warning("Failed to minimize window: %s", err)
            return False

    def toggle_window_maximized(self) -> bool:
        """Toggle between maximized and restored window state."""
        if not getattr(self, "_window", None):
            return getattr(self, "_window_maximized", False)
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
        if not getattr(self, "_window", None):
            return False
        try:
            self._window.destroy()
            return True
        except Exception as err:
            LOGGER.warning("Failed to close window: %s", err)
            return False

    def drag_window(self, anchor_mode: str = "proportional") -> bool:
        """Prepare the cursor anchor before pywebview moves its drag region."""
        mod = _bridge_mod()
        if not getattr(self, "_window", None) or mod.os.name != "nt":
            return False
        try:
            self._drag_move_baseline = None
            hwnd = mod._window_handle(self._window)
            return bool(hwnd and mod.prepare_native_drag(hwnd, anchor_mode))
        except Exception as err:
            LOGGER.debug("Native window drag failed: %s", err)
        return False

    def resize_window(self, direction: str) -> bool:
        """Initiate native Windows window resizing in the specified direction on mousedown."""
        mod = _bridge_mod()
        if not getattr(self, "_window", None) or mod.os.name != "nt":
            return False

        try:
            hwnd = mod._window_handle(self._window)
            return mod.begin_native_resize(hwnd, direction) if hwnd else False
        except Exception as err:
            LOGGER.debug("Native window resize failed: %s", err)
        return False
