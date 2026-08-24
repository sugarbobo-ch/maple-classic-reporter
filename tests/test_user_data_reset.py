import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from maple_reporter import reset


class TestUserDataReset(unittest.TestCase):
    def test_delete_removes_only_exact_owned_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            local_root = Path(temp_dir) / "Local"
            target = local_root / "MapleClassicReporter"
            sibling = local_root / "KeepMe"
            target.mkdir(parents=True)
            sibling.mkdir()
            (target / "config.json").write_text("{}", encoding="utf-8")
            (sibling / "important.txt").write_text("keep", encoding="utf-8")

            reset.delete_user_data(target, local_app_data_root=local_root)

            self.assertFalse(target.exists())
            self.assertTrue((sibling / "important.txt").is_file())

    def test_validation_rejects_broad_and_unowned_paths(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            local_root = Path(temp_dir) / "Local"
            local_root.mkdir()

            for unsafe in (local_root, Path(temp_dir), local_root / "AnotherApp"):
                with self.subTest(path=unsafe), self.assertRaises(ValueError):
                    reset.validate_user_data_root(
                        unsafe,
                        local_app_data_root=local_root,
                    )

    def test_validation_rejects_symbolic_link(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            local_root = Path(temp_dir) / "Local"
            outside = Path(temp_dir) / "Outside"
            local_root.mkdir()
            outside.mkdir()
            link = local_root / "MapleClassicReporter"
            try:
                link.symlink_to(outside, target_is_directory=True)
            except OSError:
                self.skipTest("Symbolic links are unavailable in this environment")

            with self.assertRaises(ValueError):
                reset.validate_user_data_root(link, local_app_data_root=local_root)

    def test_delete_retries_transient_file_lock(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            local_root = Path(temp_dir) / "Local"
            target = local_root / "MapleClassicReporter"
            target.mkdir(parents=True)

            with patch.object(
                reset.shutil,
                "rmtree",
                side_effect=[PermissionError("locked"), None],
            ) as remove, patch.object(reset.time, "sleep"):
                reset.delete_user_data(
                    target,
                    local_app_data_root=local_root,
                    retry_delay=0,
                )

            self.assertEqual(remove.call_count, 2)

    def test_reset_helper_waits_before_deleting(self):
        with patch.object(reset, "wait_for_process_exit", return_value=True) as wait, patch.object(
            reset, "delete_user_data"
        ) as delete, patch.object(
            reset, "get_user_app_data_dir", return_value=Path("C:/Users/Test/AppData/Local/MapleClassicReporter")
        ):
            result = reset.run_reset_helper(1234)

        self.assertEqual(result, 0)
        wait.assert_called_once_with(1234)
        delete.assert_called_once()

    def test_source_helper_command_uses_module_entrypoint(self):
        with patch.object(reset.sys, "frozen", False, create=True):
            command = reset.build_reset_helper_command(1234)

        self.assertEqual(
            command,
            [reset.sys.executable, "-m", "maple_reporter.main", reset.RESET_ARGUMENT, "1234"],
        )


if __name__ == "__main__":
    unittest.main()
