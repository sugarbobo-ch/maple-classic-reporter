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
    
    mock_history = temp_path / "test_history.json"
    mock_config = temp_path / "test_config.json"
    mock_cache = temp_path / "test_sanction_cache.json"
    mock_db = temp_path / "test_sanctions.db"

    with (
        mock.patch.object(cfg, "HISTORY_FILE", mock_history),
        mock.patch.object(cfg, "LEGACY_HISTORY_FILE", mock_history),
        mock.patch.object(repo_module, "HISTORY_FILE", mock_history),
        mock.patch.object(repo_module, "LEGACY_HISTORY_FILE", mock_history),
        mock.patch("maple_reporter.sanctions.repository.get_sanction_cache_path", return_value=mock_cache),
        mock.patch("maple_reporter.sanctions.database.get_default_db_path", return_value=mock_db),
    ):
        yield
    
    temp_dir.cleanup()
