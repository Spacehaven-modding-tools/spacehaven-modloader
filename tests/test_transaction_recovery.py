"""Test the production lock, cache publication and legacy recovery."""
import hashlib
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
from zipfile import ZipFile

from loader import load
from loader.assets.library import PATCHABLE_XML_FILES
from ui.launch_session import installation_lock


def write_jar(path, version="1.0.4"):
    with ZipFile(path, "w") as jar:
        jar.writestr("version.txt", version)
        jar.writestr("META-INF/MANIFEST.MF", "Main-Class: game.Main\n")
        for name in PATCHABLE_XML_FILES:
            jar.writestr(name, "<data/>")


class RecoveryTests(TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.jar = Path(scratch.name) / "spacehaven.jar"
        self.exe = self.jar.with_suffix(".exe")
        self.backup = self.jar.with_suffix(".jar.vanilla")
        self.mods = [SimpleNamespace(path=scratch.name)]
        (self.jar.parent / "library").mkdir()

    def test_restore_valid_missing_jar_keeps_backup(self):
        write_jar(self.backup)
        load.restore_missing_legacy_jar(self.jar)
        self.assertEqual(self.jar.read_bytes(), self.backup.read_bytes())

    def test_recovery_never_replaces_existing_jar(self):
        write_jar(self.backup, "1.0.3")
        write_jar(self.jar)
        original = self.jar.read_bytes()
        with self.assertRaises(RuntimeError):
            load.restore_missing_legacy_jar(self.jar)
        self.assertEqual(original, self.jar.read_bytes())

    def test_corrupt_backup_rejected_without_writes(self):
        self.backup.write_bytes(b"invalid")
        with self.assertRaises(RuntimeError):
            load.restore_missing_legacy_jar(self.jar)
        self.assertFalse(self.jar.exists())
        self.assertEqual(self.backup.read_bytes(), b"invalid")

    def test_publish_race_preserves_new_vendor_file(self):
        write_jar(self.backup)
        original_link = os.link
        def steam_update(source, target):
            write_jar(target, "fresh Steam build")
            original_link(source, target)
        with patch("loader.load.os.link", side_effect=steam_update), self.assertRaises(FileExistsError):
            load.restore_missing_legacy_jar(self.jar)
        with ZipFile(self.jar) as jar:
            self.assertEqual(b"fresh Steam build", jar.read("version.txt"))

    def test_corrupt_cache_rebuilds_and_vendor_stays_identical(self):
        write_jar(self.jar)
        original = self.jar.read_bytes()
        with patch("loader.assets.library.extract"), patch("loader.assets.merge.mods"), \
                patch("loader.assets.library.patch", side_effect=lambda _jar, _core, path, **_: write_jar(path)) as pack:
            path = load.prepare_game_jar(self.jar, self.mods, "cache1")
            path.write_bytes(b"bad cache")
            self.assertEqual(load.prepare_game_jar(self.jar, self.mods, "cache1"), path)
            self.assertEqual(load.prepare_game_jar(self.jar, self.mods, "cache1"), path)
            self.assertEqual(2, pack.call_count)
        self.assertEqual(self.jar.read_bytes(), original)
        self.assertFalse(self.backup.exists())
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertEqual(digest, Path(str(path) + ".sha256").read_text().strip())

    def test_patch_failure_and_concurrent_input_change_leave_vendor_intact(self):
        write_jar(self.jar)
        original = self.jar.read_bytes()
        with patch("loader.assets.library.extract"), patch("loader.assets.merge.mods"), \
                patch("loader.assets.library.patch", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(OSError, "disk full"):
                load.prepare_game_jar(self.jar, self.mods, "cache1")
        with patch("loader.assets.library.extract"), patch("loader.assets.merge.mods"), \
                patch("loader.assets.library.patch", side_effect=lambda _jar, _core, path, **_: write_jar(path)):
            with self.assertRaisesRegex(RuntimeError, "changed during preparation"):
                load.prepare_game_jar(self.jar, self.mods, "cache1", lambda: "new")
        self.assertFalse(load.quick_launch_files(self.jar))
        self.assertEqual(self.jar.read_bytes(), original)

    def test_parallel_loader_and_live_orphan_are_blocked(self):
        with installation_lock(self.exe) as pid:
            with self.assertRaisesRegex(RuntimeError, "Another Mod Loader"):
                with installation_lock(self.exe):
                    self.fail("lock acquired twice")
            pid.write_text(str(os.getpid()))
        with self.assertRaisesRegex(RuntimeError, "still be running"):
            with installation_lock(self.exe):
                self.fail("orphan was ignored")
