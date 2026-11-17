"""Tests for QuickLaunch fingerprints, runtime settings, and log export."""
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

from ui.cache_fingerprint import mod_fingerprint
from ui import diagnostics
from ui import runtime_manager as rt


class CacheFingerprintTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.game = self.base / "spacehaven.jar"
        self.game.write_bytes(b"vanilla")
        self.dir1 = self.base / "mod_a"
        self.dir1.mkdir()
        self.file = self.dir1 / "info.xml"
        self.file.write_text("initial", encoding="utf-8")
        self.mod = SimpleNamespace(path=str(self.dir1), name="mod_a", version="0.1")

    def test_same_inputs_stable(self):
        value = mod_fingerprint([self.mod], "alpha", self.game)
        self.assertEqual(value, mod_fingerprint([self.mod], "alpha", self.game))
        self.assertEqual(len(value), 32)

    def test_edit_same_version_invalidates_cache(self):
        before = mod_fingerprint([self.mod], "alpha", self.game)
        before_stat = self.file.stat()
        self.file.write_text("updated", encoding="utf-8")
        os.utime(self.file, ns=(before_stat.st_atime_ns, before_stat.st_mtime_ns))
        self.assertNotEqual(before, mod_fingerprint([self.mod], "alpha", self.game))

    def test_new_file_invalidates_cache(self):
        before = mod_fingerprint([self.mod], "alpha", self.game)
        (self.dir1 / "custom.jar").write_bytes(b"123")
        self.assertNotEqual(before, mod_fingerprint([self.mod], "alpha", self.game))

    def test_generated_sprites_do_not_invalidate_cache(self):
        before = mod_fingerprint([self.mod], "alpha", self.game)
        (self.dir1 / "custom_texture_123.png").write_bytes(b"generated")
        self.assertEqual(before, mod_fingerprint([self.mod], "alpha", self.game))

    def test_game_update_invalidates_cache(self):
        before = mod_fingerprint([self.mod], "alpha", self.game)
        self.game.write_bytes(b"new vanilla build")
        self.assertNotEqual(before, mod_fingerprint([self.mod], "alpha", self.game))

    def test_mod_order_matters(self):
        dir2 = self.base / "mod_b"
        dir2.mkdir()
        another = SimpleNamespace(path=str(dir2), name="mod_b", version="0.1")
        self.assertNotEqual(mod_fingerprint([self.mod, another], "alpha", self.game), mod_fingerprint([another, self.mod], "alpha", self.game))


class RuntimeSelectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.game = self.base / "spacehaven.exe"
        self.game.touch()
        (self.base / "config.json").write_text(json.dumps({
            "classPath": ["spacehaven.jar"],
            "mainClass": "fi.bugbyte.spacehaven.steam.SpacehavenSteam",
            "vmArgs": ["-Xmx4G"]
        }), encoding="utf-8")

    def test_java_25_paths_are_isolated(self):
        self.assertNotEqual(rt.runtime_home(self.game, 25), rt.runtime_home(self.game, 27))
        self.assertTrue(str(rt.runtime_home(self.game, 25)).endswith("temurin-25"))

    def test_java_25_mode_persistence(self):
        rt.set_mode(self.game, rt.MODE_TEMURIN25)
        self.assertEqual(rt.get_mode(self.game), rt.MODE_TEMURIN25)

    def test_java_25_rejects_version_27(self):
        from subprocess import CompletedProcess
        with patch.object(rt.subprocess, "run", return_value=CompletedProcess([], 0, "", 'openjdk version "27.0.1"')):
            with self.assertRaises(rt.RuntimeErrorDetail):
                rt.verify_java(self.game, major=25)

    def test_java_25_official_metadata(self):
        correct = {"version": {"major": 25}, "binary": {"architecture": "x64", "os": "windows", "image_type": "jre", "jvm_impl": "hotspot", "package": {"link": "https://github.com/adoptium/temurin25-binaries/releases/download/v25/test.zip", "checksum": "a"*64}}}
        with patch.object(rt, "_request_json", return_value=[correct]), patch.object(rt, "platform_artifact", return_value=("windows", "x64")):
            link, digest, release = rt.release_package(major=25)
        self.assertIn("25", link)
        self.assertEqual(digest, "a" * 64)

    def test_missing_java25_fails_without_download(self):
        with patch.object(rt, "_request_json", side_effect=AssertionError("unexpected download")):
            with self.assertRaises(rt.RuntimeErrorDetail):
                rt.preflight(self.game, rt.MODE_TEMURIN25)

    def test_bad_runtime_mode_rejected(self):
        with self.assertRaises(rt.RuntimeErrorDetail):
            rt.preflight(self.game, "java999")


class DiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.game = self.base / "spacehaven.exe"
        self.game.touch()

    def test_export_only_logs_no_saves_or_config(self):
        folder = diagnostics.state_dir(self.game)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "logs.txt").write_text("this is a log", encoding="utf-8")
        (folder / "private-savegame.txt").write_text("SECRET", encoding="utf-8")
        (folder / "config.json").write_text("ANOTHER SECRET", encoding="utf-8")
        target = self.base / "diagnostics.zip"
        count = diagnostics.export_logs(self.game, target)
        self.assertEqual(count, 1)
        with zipfile.ZipFile(target) as output:
            self.assertEqual(set(output.namelist()), {"diagnostics.json", "logs.txt"})
            self.assertEqual(json.loads(output.read("diagnostics.json"))["version"], diagnostics.version)
            self.assertNotIn(b"SECRET", output.read("logs.txt"))

    def test_large_logs_are_bounded(self):
        folder = diagnostics.state_dir(self.game)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "java27-game.log").write_bytes(b"x" * (diagnostics.MAX_LOG_BYTES + 123))
        target = self.base / "diagnostics.zip"
        diagnostics.export_logs(self.game, target)
        with zipfile.ZipFile(target) as output:
            self.assertIn(b"TRUNCATED", output.read("java27-game.log")[-100:])


if __name__ == "__main__":
    unittest.main()
