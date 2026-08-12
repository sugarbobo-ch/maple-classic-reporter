"""Application settings orchestration kept outside the main window."""

from __future__ import annotations

from typing import Any

from maple_reporter.utils.config import load_config, save_config


class SettingsController:
    """Load, apply, and persist settings for the existing UI controls."""

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config if config is not None else load_config()

    def reload(self) -> dict[str, Any]:
        self.config = load_config()
        return self.config

    def apply_to_window(self, window) -> None:
        """Populate controls without changing their layout or labels."""

        window.refresh_window_list()
        window.combo_server.setCurrentText(self.config.get("default_server", "雪吉拉"))
        window.txt_map.setText(self.config.get("default_map", "維多利亞島"))
        window.load_templates()
        window.spin_duration.setValue(self.config.get("record_duration_sec", 8))
        fps_index = window.combo_fps.findData(self.config.get("record_fps", 20))
        window.combo_fps.setCurrentIndex(max(0, fps_index))
        window.spin_countdown.setValue(self.config.get("record_countdown_sec", 3))
        window.txt_gdrive_folder.setText(
            self.config.get("gdrive_folder_name", "MapleClassic_Reports")
        )
        window.txt_gemini_key.setText(self.config.get("gemini_api_key", ""))
        window.txt_discord_webhook.setText(
            self.config.get("discord_webhook_url", "")
        )
        destination_index = window.combo_upload_destination.findData(
            self.config.get("upload_destination", "gdrive")
        )
        window.combo_upload_destination.setCurrentIndex(max(0, destination_index))
        whitelist = self.config.get("whitelist", [])
        window.txt_whitelist.setText(
            ", ".join(whitelist) if isinstance(whitelist, list) else str(whitelist)
        )
        window.chk_auto_delete.setChecked(
            self.config.get("auto_delete_after_upload", False)
        )
        window.chk_record_audio.setChecked(self.config.get("record_audio", True))
        window.refresh_audio_devices(self.config.get("audio_output_device_id", ""))
        window.spin_replay_seconds.setValue(self.config.get("replay_buffer_sec", 30))
        window.on_replay_state_changed("idle", 0.0)

    def load_templates(self, window) -> None:
        templates = self.config.get("violation_templates", [])
        if not templates:
            templates = [
                {
                    "name": "自動打怪／外掛行為",
                    "content": self.config.get("default_note", "自動打怪/外掛行為"),
                }
            ]
            self.config["violation_templates"] = templates
        window.combo_template.blockSignals(True)
        window.combo_template.clear()
        for item in templates:
            window.combo_template.addItem(
                item.get("name", "未命名範本"), item.get("content", "")
            )
        window.combo_template.blockSignals(False)
        self.apply_selected_template(window)

    def apply_selected_template(self, window) -> None:
        content = window.combo_template.currentData()
        if content is not None:
            window.txt_note.setText(str(content))

    def collect_from_window(self, window) -> dict[str, Any]:
        """Read current control values into the in-memory config model."""

        self.config["default_server"] = window.combo_server.currentText()
        self.config["default_map"] = window.txt_map.text().strip()
        self.config["default_note"] = window.txt_note.text().strip()
        self.config["selected_window_title"] = window.combo_windows.currentText()
        self.config["record_duration_sec"] = window.spin_duration.value()
        self.config["record_fps"] = int(window.combo_fps.currentData())
        self.config["record_countdown_sec"] = window.spin_countdown.value()
        self.config["replay_buffer_sec"] = window.spin_replay_seconds.value()
        self.config["gdrive_folder_name"] = (
            window.txt_gdrive_folder.text().strip() or "MapleClassic_Reports"
        )
        self.config["gemini_api_key"] = window.txt_gemini_key.text().strip()
        self.config["discord_webhook_url"] = window.txt_discord_webhook.text().strip()
        self.config["upload_destination"] = window.combo_upload_destination.currentData()
        self.config["whitelist"] = [
            value.strip()
            for value in window.txt_whitelist.text().split(",")
            if value.strip()
        ]
        self.config["auto_delete_after_upload"] = window.chk_auto_delete.isChecked()
        self.config["record_audio"] = window.chk_record_audio.isChecked()
        self.config["audio_output_device_id"] = (
            window.combo_audio_output.currentData() or ""
        )
        return self.config

    def save_from_window(self, window) -> dict[str, Any]:
        config = self.collect_from_window(window)
        save_config(config)
        return config

    def save_model(self) -> None:
        save_config(self.config)

    def mark_onboarding_completed(self) -> None:
        self.config["onboarding_completed"] = True
        save_config(self.config)


__all__ = ["SettingsController"]
