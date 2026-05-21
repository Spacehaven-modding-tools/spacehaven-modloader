import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import loader.load


class QuickLaunchCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.game_dir = self.root / "SpaceHaven"
        self.game_dir.mkdir(parents=True, exist_ok=True)
        self.jar_path = self.game_dir / "spacehaven.jar"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_quicklaunch_filename_uses_modloader_data_dir_when_jar_path_is_available(self):
        path = loader.load.quick_launch_filename("abc123", str(self.jar_path))

        expected = self.game_dir / "mods" / "modloader" / "quicklaunch_abc123.jar"
        self.assertEqual(Path(path), expected)
        self.assertTrue((self.game_dir / "mods" / "modloader").is_dir())

    def test_modloader_state_file_uses_modloader_data_dir(self):
        path = loader.load.modloader_state_file(str(self.jar_path), loader.load.PREVIOUS_GAME_PATH_FILENAME)

        expected = self.game_dir / "mods" / "modloader" / "previous_spacehaven_path.txt"
        self.assertEqual(Path(path), expected)

    def test_clear_quicklaunch_cache_removes_new_and_legacy_files(self):
        new_file = Path(loader.load.quick_launch_filename("new", str(self.jar_path)))
        new_file.parent.mkdir(parents=True, exist_ok=True)
        new_file.write_text("new", encoding="utf-8")

        legacy_dir = self.root / "workshop" / "content" / "979110" / "3703674043"
        legacy_dir.mkdir(parents=True, exist_ok=True)
        legacy_file = legacy_dir / "quicklaunch_old.jar"
        legacy_file.write_text("old", encoding="utf-8")

        with patch("loader.load.os.getcwd", return_value=str(legacy_dir)), patch.object(
            sys, "argv", [str(legacy_dir / "spacehaven-modloader.exe")]
        ):
            removed = loader.load.clear_quick_launch_cache(str(self.jar_path))

        self.assertEqual(removed, 2)
        self.assertFalse(new_file.exists())
        self.assertFalse(legacy_file.exists())

    def test_prune_quicklaunch_cache_keeps_current_file(self):
        for index in range(12):
            path = Path(loader.load.quick_launch_filename(str(index), str(self.jar_path)))
            path.write_text(str(index), encoding="utf-8")
            os.utime(path, (index, index))

        current_file = Path(loader.load.quick_launch_filename("11", str(self.jar_path)))
        removed = loader.load.prune_quick_launch_cache(str(self.jar_path), keep_signature="11", max_files=10)

        self.assertEqual(removed, 2)
        self.assertTrue(current_file.exists())
        self.assertEqual(len(loader.load.quick_launch_files(str(self.jar_path))), 10)


if __name__ == "__main__":
    unittest.main()
