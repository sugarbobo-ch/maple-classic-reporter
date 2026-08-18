import os
import tempfile
from pathlib import Path
import pytest
import unittest.mock as mock

import maple_reporter.utils.config as cfg
import maple_reporter.sanctions.repository as repo_module


@pytest.fixture(autouse=True, scope="session")
def isolate_test_persistence():
    """Ensure tests never write to production user AppData or repo data files."""
    temp_dir = tempfile.TemporaryDirectory()
    temp_path = Path(temp_dir.name)
    app_data_dir = temp_path / "MapleClassicReporter"
    config_dir = app_data_dir / "config"
    recordings_dir = app_data_dir / "recordings"
    config_dir.mkdir(parents=True, exist_ok=True)
    recordings_dir.mkdir(parents=True, exist_ok=True)

    mock_config = config_dir / "config.json"
    mock_history = config_dir / "history.json"
    mock_legacy_config = temp_path / "legacy_config.json"
    mock_legacy_history = temp_path / "legacy_history.json"
    mock_cache = app_data_dir / "test_sanction_cache.json"
    mock_db = app_data_dir / "test_sanctions.db"

    old_local_app_data = os.environ.get("LOCALAPPDATA")
    os.environ["LOCALAPPDATA"] = str(temp_path)

    with (
        mock.patch.object(cfg, "CONFIG_DIR", config_dir),
        mock.patch.object(cfg, "CONFIG_FILE", mock_config),
        mock.patch.object(cfg, "RECORDINGS_DIR", recordings_dir),
        mock.patch.object(cfg, "HISTORY_FILE", mock_history),
        mock.patch.object(cfg, "LEGACY_CONFIG_FILE", mock_legacy_config),
        mock.patch.object(cfg, "LEGACY_HISTORY_FILE", mock_legacy_history),
        mock.patch.object(repo_module, "HISTORY_FILE", mock_history),
        mock.patch.object(repo_module, "LEGACY_HISTORY_FILE", mock_legacy_history),
        mock.patch(
            "maple_reporter.sanctions.repository.get_sanction_cache_path",
            return_value=mock_cache,
        ),
        mock.patch(
            "maple_reporter.sanctions.database.get_default_db_path",
            return_value=mock_db,
        ),
    ):
        try:
            yield
        finally:
            if old_local_app_data is not None:
                os.environ["LOCALAPPDATA"] = old_local_app_data
            else:
                os.environ.pop("LOCALAPPDATA", None)
            temp_dir.cleanup()
