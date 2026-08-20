"""Configuration, clipboard, system window & audio scanning bridge mixin."""

from __future__ import annotations

import logging
from typing import Any

LOGGER = logging.getLogger(__name__)


def _bridge_mod():
    import maple_reporter.gui.pywebview_bridge as bridge_mod

    return bridge_mod


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


class ConfigBridgeMixin:
    """Methods for retrieving initial setup, managing config, and scanning audio/windows."""

    def get_clipboard_text(self) -> str:
        """Return clipboard text through the native host instead of WebView Clipboard API."""
        return _bridge_mod().read_system_clipboard_text()

    def set_clipboard_text(self, text: str) -> bool:
        """Write clipboard text through the native host instead of WebView Clipboard API."""
        return _bridge_mod().write_system_clipboard_text(text)

    def _handle_global_hotkey(self, action: str) -> None:
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

    def get_initial_data(self) -> dict[str, Any]:
        """Fetch initial config, system windows, audio devices, history, and drive auth."""
        mod = _bridge_mod()
        self.config = mod.load_config()
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
                mod.save_config(self.config)
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
            "app_data_dir": str(mod.get_user_app_data_dir()),
            "sanction_sync_status": sync_status,
            "last_complete_sync_at": cache.last_complete_sync_at or None,
        }

    def save_config_key(self, key: str, value: Any) -> bool:
        """Update single config key and persist."""
        mod = _bridge_mod()
        with self._safe_config_lock:
            try:
                current_config = mod.load_config()
                # Validate hotkey conflicts
                if key == "save_replay_hotkey":
                    other_hk = str(current_config.get("record_video_hotkey", "")).strip().lower()
                    if other_hk and str(value).strip().lower() == other_hk:
                        LOGGER.warning("拒絕重複快捷鍵設定: %s 與 record_video_hotkey 衝突", value)
                        return False
                elif key == "record_video_hotkey":
                    other_hk = str(current_config.get("save_replay_hotkey", "")).strip().lower()
                    if other_hk and str(value).strip().lower() == other_hk:
                        LOGGER.warning("拒絕重複快捷鍵設定: %s 與 save_replay_hotkey 衝突", value)
                        return False

                candidate_config = dict(current_config)
                candidate_config[key] = value
                if key == "audio_capture_mode":
                    mode = str(value).casefold()
                    if mode not in {"process", "system", "off"}:
                        return False
                    candidate_config["record_audio"] = mode != "off"
                elif key == "record_audio":
                    candidate_config["audio_capture_mode"] = (
                        "system" if bool(value) else "off"
                    )
                mod.save_config(candidate_config)
                self.config = candidate_config

                if key in ("global_hotkeys_enabled", "save_replay_hotkey", "record_video_hotkey"):
                    self._init_hotkeys()
                elif key in (
                    "replay_buffer_sec",
                    "selected_window_title",
                    "record_fps",
                    "record_audio",
                    "audio_capture_mode",
                    "audio_output_device_id",
                ):
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
        mod = _bridge_mod()
        with self._safe_config_lock:
            try:
                current_config = mod.load_config()
                candidate_config = dict(current_config)
                candidate_config.update(new_config)
                if "audio_capture_mode" not in new_config and "record_audio" in new_config:
                    candidate_config["audio_capture_mode"] = (
                        "system" if bool(new_config["record_audio"]) else "off"
                    )
                mode = str(candidate_config.get("audio_capture_mode", "process")).casefold()
                if mode not in {"process", "system", "off"}:
                    return False
                candidate_config["audio_capture_mode"] = mode
                candidate_config["record_audio"] = mode != "off"

                # Validate hotkey conflicts
                save_hk = str(candidate_config.get("save_replay_hotkey", "")).strip().lower()
                rec_hk = str(candidate_config.get("record_video_hotkey", "")).strip().lower()
                if save_hk and rec_hk and save_hk == rec_hk:
                    LOGGER.warning("拒絕儲存設定: save_replay_hotkey 與 record_video_hotkey 重複衝突")
                    return False
                mod.save_config(candidate_config)
                self.config = candidate_config
                self._init_hotkeys()
                return True
            except Exception as err:
                LOGGER.error("Failed to save config: %s", err)
                return False

    def get_windows(self) -> list[dict[str, Any]]:
        """Return active desktop windows excluding reporter tool itself."""
        mod = _bridge_mod()
        try:
            raw_windows = mod.get_active_windows()
            filtered = mod.order_window_candidates(
                [
                    window
                    for window in raw_windows
                    if "maplestory classic auto reporter" not in window["title"].lower()
                    and "自動外掛檢舉工具" not in window["title"]
                    and "maple classic reporter" not in window["title"].lower()
                ]
            )
            selected_title = mod.select_preferred_window_title(
                filtered, str(self.config.get("selected_window_title", ""))
            )
            if selected_title and selected_title != self.config.get("selected_window_title"):
                self.config["selected_window_title"] = selected_title
                try:
                    mod.save_config(self.config)
                except Exception as err:
                    LOGGER.warning("Failed to persist preferred window: %s", err)
            return filtered
        except Exception as err:
            LOGGER.warning("Error getting window titles: %s", err)
            return []

    def get_audio_devices(self) -> list[dict[str, Any]]:
        """Return system audio output devices."""
        mod = _bridge_mod()
        try:
            default_name = mod.get_default_audio_output_name()
            devices = mod.get_audio_output_devices()
            result = [{"id": "", "name": f"系統預設（{default_name}）"}]
            for dev_id, name in devices:
                result.append({"id": dev_id, "name": name})
            return result
        except Exception as err:
            LOGGER.warning("Error getting audio devices: %s", err)
            return [{"id": "", "name": "系統預設 (Realtek Digital Output)"}]
