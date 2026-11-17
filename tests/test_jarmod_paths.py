from pathlib import Path
import json
import os
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from ui import launch_config, paths
from ui.database import ModDatabase
from ui.gameinfo import GameInfo


class LaunchClasspathTests(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = Path(scratch.name).resolve() / "steamapps/common/Space Haven"
        self.root.mkdir(parents=True)
        self.exe = self.root / "spacehaven.exe"
        self.jar = self.exe.with_suffix(".jar")
        self.main = "game.Main"
        with ZipFile(self.jar, "w") as jar:
            jar.writestr("version.txt", "1.0.4")
            jar.writestr("META-INF/MANIFEST.MF", f"Main-Class: {self.main}\n")
            jar.writestr("game/Main.class", b"test")
        self.local = self.root / "mods"
        self.workshop = self.root.parents[1] / "workshop/content/979110"
        self.local_jar = self.make_mod(self.local / "Local")
        self.workshop_jar = self.make_mod(self.workshop / "123")
        self.external_jar = self.make_mod(self.root.parent / "Other Space Haven/mods/Residual")
        self.config = self.root / "config.json"
        self.config.write_text(json.dumps({
            "mainClass": "foreign.HiddenMain",
            "classPath": [str(self.external_jar), str(self.local_jar), "spacehaven.jar"],
            "vmArgs": ["-Xmx4G", "--add-opens java.base/java.lang=ALL-UNNAMED",
                       "-XstartOnFirstThread", "-javaagent:external.jar", "@external.args"],
        }), encoding="utf-8")
        self.original_config = self.config.read_bytes()
        self.database = ModDatabase([str(self.local), paths.resolve_workshop_path(self.exe)], GameInfo(str(self.jar)))
        self.database.locateMods()

    def make_mod(self, root, manifest=None):
        root.mkdir(parents=True, exist_ok=True)
        (root / "info.xml").write_text("<mod><name>Audit</name><version>1</version></mod>", encoding="utf-8")
        path = root / "mod.jar"
        with ZipFile(path, "w") as jar:
            jar.writestr("test.class", b"fixture")
            if manifest:
                jar.writestr("META-INF/MANIFEST.MF", manifest)
        return path

    def build(self, mods, major=8):
        lines = []
        command, env = launch_config.build(self.exe, self.jar, mods, "java", major, lines.append)
        self.assertEqual(self.original_config, self.config.read_bytes())
        return command, command[-2].split(os.pathsep), env, lines

    def test_clean_drops_residual_game_and_environment_entries(self):
        with patch.dict(os.environ, {"JAVA_TOOL_OPTIONS": "-javaagent:unexpected.jar", "_JAVA_OPTIONS": "-Xmx1G"}):
            command, cp, env, lines = self.build([])
        self.assertEqual([str(self.jar)], cp)
        self.assertEqual(self.main, command[-1])
        self.assertIn("-Xmx4G", command)
        self.assertFalse(any(item.startswith(("-javaagent", "@", "--add-opens")) for item in command))
        self.assertNotIn("JAVA_TOOL_OPTIONS", env)
        self.assertNotIn("_JAVA_OPTIONS", env)
        self.assertTrue(any("Other Space Haven" in line for line in lines))

    def test_local_workshop_order_and_toggles_without_config_writes(self):
        mods = self.database.getActiveMods()
        self.assertEqual(len(mods), 2)
        command, cp, _, _ = self.build(mods)
        self.assertEqual([mod.jarPath for mod in mods], cp[2:-1])
        self.assertTrue(any(arg.startswith("-javaagent:") and "1.9.19" in arg for arg in command))
        mods[0].disable()
        self.database.locateMods()
        _, cp, _, _ = self.build(self.database.getActiveMods())
        self.assertNotIn(mods[0].jarPath, cp)

    def test_mod_manifest_external_dependency_rejected(self):
        self.make_mod(self.local_jar.parent, "Class-Path: https://example.test/hidden.jar\n")
        with self.assertRaisesRegex(RuntimeError, "External manifest dependency"):
            self.build(self.database.getActiveMods())

    def test_manifest_dependency_with_spaces_in_same_mod(self):
        self.make_mod(self.local_jar.parent, "Class-Path: libs/my%20library.jar\n")
        dependency = self.local_jar.parent / "libs/my library.jar"
        dependency.parent.mkdir()
        with ZipFile(dependency, "w") as jar:
            jar.writestr("helper.class", b"fixture")
        _, cp, _, _ = self.build(self.database.getActiveMods())
        self.assertIn(str(dependency), cp)
