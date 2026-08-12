import json
import logging
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict

from maple_reporter.gdrive.token_store import (
    ProtectedSecretStore,
    ProtectedTokenStoreError,
)


LOGGER = logging.getLogger(__name__)


def get_base_dir() -> Path:
    """Use the executable folder for frozen builds so data survives restarts."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent.parent.parent


def get_user_app_data_dir() -> Path:
    """Return the per-user directory for local application secrets."""

    local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
    if local_app_data:
        return Path(local_app_data) / "MapleClassicReporter"
    if os.name == "nt":
        return Path.home() / "AppData" / "Local" / "MapleClassicReporter"
    return Path.home() / ".maple_reporter"


def get_default_token_path() -> Path:
    """Return the protected per-user OAuth token path."""

    return get_user_app_data_dir() / "oauth_token.dpapi"


_SECRET_CONFIG_KEYS = ("gemini_api_key", "discord_webhook_url")


def get_default_secret_path(name: str) -> Path:
    """Return the protected path for one supported application secret."""

    if name not in _SECRET_CONFIG_KEYS:
        raise ValueError(f"Unsupported application secret: {name}")
    return get_user_app_data_dir() / f"{name}.dpapi"


BASE_DIR = get_base_dir()
DATA_DIR = BASE_DIR / "data"
# Settings belong to the per-user application-data directory, not next to the
# executable where another local user may be able to modify the install tree.
CONFIG_DIR = get_user_app_data_dir() / "config"
LEGACY_CONFIG_DIR = DATA_DIR / "config"
RECORDINGS_DIR = get_user_app_data_dir() / "recordings"
LEGACY_RECORDINGS_DIR = DATA_DIR / "recordings"

CONFIG_FILE = CONFIG_DIR / "config.json"
HISTORY_FILE = CONFIG_DIR / "history.json"
LEGACY_CONFIG_FILE = LEGACY_CONFIG_DIR / "config.json"
LEGACY_HISTORY_FILE = LEGACY_CONFIG_DIR / "history.json"

DEFAULT_CONFIG: Dict[str, Any] = {
    "default_server": "雪吉拉",
    "default_map": "維多利亞島",
    "default_note": "自動打怪/外掛行為",
    "record_duration_sec": 8,
    "record_fps": 20,
    "record_countdown_sec": 3,
    "replay_buffer_sec": 30,
    "selected_window_title": "新楓之谷",
    "gdrive_token_file": str(get_default_token_path()),
    "gdrive_folder_name": "MapleClassic_Reports",
    "gemini_api_key": "",
    "discord_webhook_url": "",
    "upload_destination": "gdrive",
    "violation_templates": [{"name": "自動打怪／外掛行為", "content": "自動打怪/外掛行為"}],
    "onboarding_completed": False,
    "whitelist": [],
    "auto_submit_without_preview": False,
    "auto_delete_after_upload": False,
    "record_audio": True,
    "audio_output_device_id": "",
}

def ensure_config_dir() -> Path:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    return CONFIG_DIR

def get_recordings_dir() -> Path:
    RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    return RECORDINGS_DIR


def is_owned_recording_path(file_path: str | os.PathLike[str]) -> bool:
    """Return whether a path is an app-generated recording we may delete."""

    candidate = Path(file_path).expanduser()
    recordings_dir = get_recordings_dir().resolve()
    try:
        resolved = candidate.resolve(strict=False)
    except OSError:
        return False
    if candidate.is_symlink() or resolved.parent != recordings_dir:
        return False
    return resolved.name.startswith("maple_evidence_")


def _write_json_atomic(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
        # Directory fsync is useful on POSIX. Opening a directory handle on
        # Windows can keep a temporary test/application directory undeletable,
        # while the completed file fsync above already protects the payload.
        if os.name != "nt":
            try:
                directory_fd = os.open(str(path.parent), os.O_RDONLY)
            except OSError:
                directory_fd = None
            if directory_fd is not None:
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
    finally:
        if temporary_path.exists():
            try:
                temporary_path.unlink()
            except OSError as error:
                LOGGER.warning(
                    "清理 JSON 暫存檔失敗 (%s: %s)",
                    temporary_path.name,
                    type(error).__name__,
                )


def _load_secret(name: str) -> str | None:
    try:
        return ProtectedSecretStore(get_default_secret_path(name)).load()
    except (OSError, ProtectedTokenStoreError) as error:
        LOGGER.warning("讀取受保護設定失敗 (%s: %s)", name, type(error).__name__)
        return None


def _save_secret(name: str, value: str) -> bool:
    try:
        ProtectedSecretStore(get_default_secret_path(name)).save(value)
        return True
    except (OSError, ProtectedTokenStoreError) as error:
        LOGGER.warning("儲存受保護設定失敗 (%s: %s)", name, type(error).__name__)
        return False


def _delete_secret(name: str) -> None:
    try:
        ProtectedSecretStore(get_default_secret_path(name)).delete()
    except OSError as error:
        LOGGER.warning("刪除受保護設定失敗 (%s: %s)", name, type(error).__name__)

def load_config() -> Dict[str, Any]:
    ensure_config_dir()
    source_path = CONFIG_FILE if CONFIG_FILE.exists() else LEGACY_CONFIG_FILE
    if not source_path.exists():
        save_config(DEFAULT_CONFIG)
        source_path = CONFIG_FILE
    try:
        with open(source_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            if not isinstance(cfg, dict):
                raise TypeError("config root must be an object")
            merged = DEFAULT_CONFIG.copy()
            merged.update(cfg)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError):
        return DEFAULT_CONFIG.copy()

    # Secrets are migrated out of the legacy JSON file on first read. They are
    # still returned to the UI in memory, but are never written back to JSON.
    sanitized = dict(cfg) if isinstance(cfg, dict) else {}
    changed = False
    for name in _SECRET_CONFIG_KEYS:
        legacy_value = sanitized.get(name, "")
        stored_value = _load_secret(name)
        if stored_value is None and isinstance(legacy_value, str) and legacy_value:
            if _save_secret(name, legacy_value):
                stored_value = legacy_value
        if stored_value is None:
            merged[name] = ""
        else:
            merged[name] = stored_value
        if name in sanitized and (stored_value is not None or not legacy_value):
            sanitized.pop(name, None)
            changed = True

    migration_blocked = any(
        name in sanitized and bool(sanitized.get(name))
        for name in _SECRET_CONFIG_KEYS
    )
    if changed and source_path == CONFIG_FILE and not migration_blocked:
        # Only remove plaintext values after the protected copy succeeded.
        _write_json_atomic(CONFIG_FILE, sanitized)
    elif source_path == LEGACY_CONFIG_FILE:
        # Copy ordinary settings into the protected per-user location. Remove
        # migrated secrets from the legacy file only after DPAPI persistence.
        if not migration_blocked:
            _write_json_atomic(CONFIG_FILE, sanitized)
            if changed:
                _write_json_atomic(LEGACY_CONFIG_FILE, sanitized)
    return merged

def save_config(cfg: Dict[str, Any]) -> None:
    ensure_config_dir()
    serializable = dict(cfg)
    for name in _SECRET_CONFIG_KEYS:
        if name not in serializable:
            continue
        value = serializable.pop(name)
        if value:
            if not isinstance(value, str) or not _save_secret(name, value.strip()):
                raise ProtectedTokenStoreError(
                    f"Could not securely store application secret: {name}"
                )
        else:
            _delete_secret(name)
    _write_json_atomic(CONFIG_FILE, serializable)

def load_history() -> list:
    ensure_config_dir()
    history_path = HISTORY_FILE if HISTORY_FILE.exists() else LEGACY_HISTORY_FILE
    if not history_path.exists():
        return []
    try:
        with open(history_path, "r", encoding="utf-8") as f:
            history = json.load(f)
            if not isinstance(history, list):
                raise TypeError("history root must be an array")
            return history
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError) as error:
        LOGGER.warning("讀取歷史紀錄失敗 (%s)", type(error).__name__)
        return []

def add_history_entry(entry: dict) -> None:
    history = load_history()
    history.insert(0, entry)
    _write_json_atomic(HISTORY_FILE, history[:100])
