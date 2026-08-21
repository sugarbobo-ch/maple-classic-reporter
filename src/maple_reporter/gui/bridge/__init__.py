"""PyWebView bridge module and components."""

from __future__ import annotations

import webview

from maple_reporter.gui.bridge.base import BaseBridgeMixin
from maple_reporter.gui.bridge.config_bridge import ConfigBridgeMixin, _choose_preferred_window
from maple_reporter.gui.bridge.integration_bridge import IntegrationBridgeMixin
from maple_reporter.gui.bridge.media_bridge import MediaBridgeMixin
from maple_reporter.gui.bridge.recording_bridge import RecordingBridgeMixin
from maple_reporter.gui.bridge.replay_bridge import ReplayBridgeMixin
from maple_reporter.gui.bridge.submission_bridge import SubmissionBridgeMixin, _submission_guard
from maple_reporter.gui.bridge.update_bridge import UpdateBridgeMixin
from maple_reporter.gui.bridge.window_bridge import WindowBridgeMixin


class PyWebViewBridge(
    WindowBridgeMixin,
    RecordingBridgeMixin,
    ReplayBridgeMixin,
    MediaBridgeMixin,
    SubmissionBridgeMixin,
    ConfigBridgeMixin,
    IntegrationBridgeMixin,
    UpdateBridgeMixin,
    BaseBridgeMixin,
):
    """API bridge exposed to JavaScript via window.pywebview.api."""

    def __init__(self, window: webview.Window | None = None):
        super().__init__(window=window)


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
    "UpdateBridgeMixin",
    "_choose_preferred_window",
    "_submission_guard",
]
