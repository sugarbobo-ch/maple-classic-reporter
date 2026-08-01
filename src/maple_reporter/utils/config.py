import json
import os
from pathlib import Path
from typing import Any, Dict

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR = BASE_DIR / "data"
CONFIG_DIR = DATA_DIR / "config"
RECORDINGS_DIR = DATA_DIR / "recordings"

CONFIG_FILE = CONFIG_DIR / "config.json"
HISTORY_FILE = CONFIG_DIR / "history.json"

DEFAULT_CONFIG: Dict[str, Any] = {
    "default_server": "雪吉拉",
    "default_map": "維多利亞島",
    "default_note": "自動打怪/外掛行為",
    "record_duration_sec": 8,
    "record_countdown_sec": 3,
    "selected_window_title": "新楓之谷",
    "gdrive_credentials_file": str(CONFIG_DIR / "client_secrets.json"),
    "gdrive_token_file": str(CONFIG_DIR / "token.json"),
    "gdrive_folder_name": "MapleClassic_Reports",
    "gemini_api_key": "",
    "discord_webhook_url": "",
    "upload_destination": "gdrive",
    "violation_templates": [{"name": "自動打怪／外掛行為", "content": "自動打怪/外掛行為"}],
    "onboarding_completed": False,
    "whitelist": [],
    "auto_submit_without_preview": False,
}

def ensure_config_dir() -> Path:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    return CONFIG_DIR

def get_recordings_dir() -> Path:
    RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    return RECORDINGS_DIR

def load_config() -> Dict[str, Any]:
    ensure_config_dir()
    if not CONFIG_FILE.exists():
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            merged = DEFAULT_CONFIG.copy()
            merged.update(cfg)
            return merged
    except Exception:
        return DEFAULT_CONFIG.copy()

def save_config(cfg: Dict[str, Any]) -> None:
    ensure_config_dir()
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

def load_history() -> list:
    ensure_config_dir()
    if not HISTORY_FILE.exists():
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def add_history_entry(entry: dict) -> None:
    history = load_history()
    history.insert(0, entry)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history[:100], f, ensure_ascii=False, indent=2)
