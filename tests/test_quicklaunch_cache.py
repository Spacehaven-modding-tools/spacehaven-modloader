import os
import sys
import tempfile
import unittest
from unittest.mock import patch

import loader.load


class QuickLaunchCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = self.temp_dir.name
        self.game_dir = os.path.join(self.root, "SpaceHaven")
        os.makedirs(self.game_dir, exist_ok=True)
        self.jar_path = os.path.join(self.game_dir, "spacehaven.jar")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_quicklaunch_filename_uses_modloader_data_dir_when_jar_path_is_available(self):
        path = loader.load.quick_launch_filename("abc123", self.jar_path)

        self.assertEqual(path, os.path.join(self.game_dir, "mods", "modloader", "quicklaunch_abc123.jar"))
        self.assertTrue(os.path.isdir(os.path.join(self.game_dir, "mods", "modloader")))

    def test_modloader_state_file_uses_modloader_data_dir(self):
        path = loader.load.modloader_state_file(self.jar_path, loader.load.EXTRA_MODS_PATH_FILENAME)

        self.assertEqual(path, os.path.join(self.game_dir, "mods", "modloader", "extra_mods_path.txt"))

    def test_clear_quicklaunch_cache_removes_new_and_legacy_files(self):
        new_file = loader.load.quick_launch_filename("new", self.jar_path)
        os.makedirs(os.path.dirname(new_file), exist_ok=True)
        with open(new_file, "w", encoding="utf-8") as cache_file:
            cache_file.write("new")

        legacy_dir = os.path.join(self.root, "workshop", "content", "979110", "3703674043")
        os.makedirs(legacy_dir, exist_ok=True)
        legacy_file = os.path.join(legacy_dir, "quicklaunch_old.jar")
        with open(legacy_file, "w", encoding="utf-8") as cache_file:
            cache_file.write("old")

        with patch("loader.load.os.getcwd", return_value=legacy_dir), patch.object(sys, "argv", [os.path.join(legacy_dir, "spacehaven-modloader.exe")]):
            removed = loader.load.clear_quick_launch_cache(self.jar_path)

        self.assertEqual(removed, 2)
        self.assertFalse(os.path.exists(new_file))
        self.assertFalse(os.path.exists(legacy_file))

    def test_prune_quicklaunch_cache_keeps_current_file(self):
        for index in range(12):
            path = loader.load.quick_launch_filename(str(index), self.jar_path)
            with open(path, "w", encoding="utf-8") as cache_file:
                cache_file.write(str(index))
            os.utime(path, (index, index))

        current_file = loader.load.quick_launch_filename("11", self.jar_path)
        removed = loader.load.prune_quick_launch_cache(self.jar_path, keep_signature="11", max_files=10)

        self.assertEqual(removed, 2)
        self.assertTrue(os.path.exists(current_file))
        self.assertEqual(len(loader.load.quick_launch_files(self.jar_path)), 10)


if __name__ == "__main__":
    unittest.main()
