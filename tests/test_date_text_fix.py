import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from ui import date_text_fix, launch_config


class DatePatchTests(unittest.TestCase):
    def test_frozen_bundle_resolves_jar_beside_executable(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp).resolve() / "spacehaven-modloader.exe"
            with patch("sys.frozen", True, create=True), patch("sys.executable", str(exe)):
                self.assertEqual((exe.with_name(date_text_fix.JAR_NAME),), date_text_fix.bundled_candidates())

    def test_bundled_hash_and_jar_verified(self):
        with ZipFile(date_text_fix.verified_patch_path()) as jar:
            code = jar.read("shl/locale/SaveDateTextNormalizer.class")
            self.assertNotRegex(code, rb"(?i)[a-z]:[/\\]|/(?:users|home|private/var)/")

    def test_missing_and_modified_patch_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / date_text_fix.JAR_NAME
            with patch.object(date_text_fix, "bundled_candidates", return_value=[path]):
                with self.assertRaises(date_text_fix.DateTextFixError):
                    date_text_fix.verified_patch_path()
                path.write_bytes(b"modified")
                with self.assertRaises(date_text_fix.DateTextFixError):
                    date_text_fix.verified_patch_path()

    def test_modern_classpath_contains_one_agent_and_datefix(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp).resolve() / "spacehaven.exe"
            jar_path = exe.with_suffix(".jar")
            with ZipFile(jar_path, "w") as jar:
                jar.writestr("META-INF/MANIFEST.MF", "Main-Class: game.Main\n")
                jar.writestr("game/Main.class", b"test")
            weaver = Path(tmp) / "aspectjweaver-1.9.27.jar"
            config = exe.with_name("config.json")
            config.write_text('{"classPath":["spacehaven.jar","aspectjweaver-1.9.19.jar"],"vmArgs":["-javaagent:aspectjweaver-1.9.19.jar","--add-opens","java.base/java.lang=ALL-UNNAMED"]}')
            before = config.read_bytes()
            with patch.object(launch_config.aspectj_runtime, "installed_aspectj", return_value=weaver):
                command, _ = launch_config.build(exe, jar_path, [], "java", 25)
                self.assertIn("--add-opens=java.base/java.lang=ALL-UNNAMED", command)
                self.assertTrue(any(date_text_fix.TYPE_FILTER in arg for arg in command))
                self.assertEqual([arg for arg in command if arg.startswith("-javaagent:")], ["-javaagent:" + str(weaver)])
                self.assertEqual(command[-2].split(os.pathsep), [str(weaver), str(date_text_fix.verified_patch_path()), str(jar_path)])
            with patch.object(date_text_fix, "verified_patch_path", side_effect=AssertionError("Java 8 loaded DateFix")):
                command, _ = launch_config.build(exe, jar_path, [], "java", 8)
                self.assertEqual(command[-2], str(jar_path))
            self.assertEqual(before, config.read_bytes())

    def test_date_filter_preserves_weaving_for_unrestricted_mod(self):
        with tempfile.TemporaryDirectory() as tmp:
            mod = Path(tmp) / "mod.jar"
            with ZipFile(mod, "w") as jar:
                jar.writestr("META-INF/aop.xml", "<aspectj><aspects><aspect name='mod.Example'/></aspects></aspectj>")
            self.assertFalse(launch_config._can_add_date_type_filter([mod]))
            with ZipFile(mod, "w") as jar:
                jar.writestr("META-INF/aop.xml", "<aspectj><weaver><include within='mod..*'/></weaver></aspectj>")
            self.assertTrue(launch_config._can_add_date_type_filter([mod]))
