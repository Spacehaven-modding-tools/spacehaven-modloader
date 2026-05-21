import json
import os
import tempfile
import unittest
from unittest.mock import patch

from ui.database import (
    ASPECTJ_JAR,
    ASPECTJ_JAVAAGENT,
    ASPECTJ_WEAVER_JAR,
    DISABLED_MARKER,
    JarMod,
    normalize_classpath_entry,
    reconcile_jarmod_classpath,
    resolve_config_path,
)


TEST_MOD_NAME = "TestJarMod"
TEST_MOD_JAR = "{}.jar".format(TEST_MOD_NAME)
TEST_WORKSHOP_ITEM_ID = "1234567890"


class FakeGameInfo:
    def __init__(self, jarPath):
        self.jarPath = jarPath
        self.version = "1.0.0"


def write_mod_files(modPath):
    os.makedirs(modPath, exist_ok=True)
    infoPath = os.path.join(modPath, "info.xml")
    with open(infoPath, "w", encoding="utf-8") as infoFile:
        infoFile.write(
            """<mod>
    <name>TestJarMod</name>
    <description>Test JAR mod</description>
    <minimumLoaderVersion>0.12.2</minimumLoaderVersion>
</mod>"""
        )
    with open(os.path.join(modPath, TEST_MOD_JAR), "w", encoding="utf-8") as jarFile:
        jarFile.write("")
    return infoPath


def write_config(gameDir):
    os.makedirs(gameDir, exist_ok=True)
    configPath = os.path.join(gameDir, "config.json")
    with open(configPath, "w", encoding="utf-8") as configFile:
        json.dump({"classPath": ["spacehaven.jar"], "vmArgs": []}, configFile)
    return configPath


def load_config(configPath):
    with open(configPath, "r", encoding="utf-8") as configFile:
        return json.load(configFile)


class JarModPathTests(unittest.TestCase):
    def setUp(self):
        self.tempDir = tempfile.TemporaryDirectory()
        self.root = self.tempDir.name
        self.gameDir = os.path.join(self.root, "Steam", "steamapps", "common", "SpaceHaven")
        self.jarPath = os.path.join(self.gameDir, "spacehaven.jar")
        self.gameInfo = FakeGameInfo(self.jarPath)
        self.configPath = write_config(self.gameDir)

    def tearDown(self):
        self.tempDir.cleanup()

    def test_local_mod_uses_game_config(self):
        modPath = os.path.join(self.gameDir, "mods", TEST_MOD_NAME)
        infoPath = write_mod_files(modPath)

        mod = JarMod(infoPath, self.gameInfo, TEST_MOD_JAR)

        self.assertEqual(resolve_config_path(self.gameInfo), self.configPath)
        self.assertEqual(mod.configPath, self.configPath)

    def test_workshop_mod_uses_game_config(self):
        modPath = os.path.join(self.root, "Steam", "steamapps", "workshop", "content", "979110", TEST_WORKSHOP_ITEM_ID)
        infoPath = write_mod_files(modPath)

        mod = JarMod(infoPath, self.gameInfo, TEST_MOD_JAR)

        self.assertEqual(mod.configPath, self.configPath)

    def test_workshop_mod_adds_absolute_normalized_classpath(self):
        modPath = os.path.join(self.root, "Steam", "steamapps", "workshop", "content", "979110", TEST_WORKSHOP_ITEM_ID)
        infoPath = write_mod_files(modPath)
        mod = JarMod(infoPath, self.gameInfo, TEST_MOD_JAR)

        mod.enable()
        config = load_config(self.configPath)

        expectedJarPath = normalize_classpath_entry(os.path.join(modPath, TEST_MOD_JAR))
        self.assertIn(expectedJarPath, config["classPath"])
        self.assertNotIn(os.path.join(self.root, "Steam", "steamapps", "workshop", "content", "config.json"), mod.configPath)

    def test_enable_is_idempotent(self):
        modPath = os.path.join(self.gameDir, "mods", TEST_MOD_NAME)
        infoPath = write_mod_files(modPath)
        mod = JarMod(infoPath, self.gameInfo, TEST_MOD_JAR)

        mod.enable()
        mod.enable()
        config = load_config(self.configPath)

        expectedJarPath = normalize_classpath_entry(os.path.join(modPath, TEST_MOD_JAR))
        for entry in [ASPECTJ_WEAVER_JAR, ASPECTJ_JAR, expectedJarPath]:
            self.assertEqual(config["classPath"].count(entry), 1)
        self.assertEqual(config["vmArgs"].count(ASPECTJ_JAVAAGENT), 1)

    def test_enable_keeps_existing_jar_order_before_spacehaven(self):
        modPath = os.path.join(self.gameDir, "mods", TEST_MOD_NAME)
        infoPath = write_mod_files(modPath)
        mod = JarMod(infoPath, self.gameInfo, TEST_MOD_JAR)
        otherJar = normalize_classpath_entry(os.path.join(self.gameDir, "mods", "OtherMod", "OtherMod.jar"))
        with open(self.configPath, "w", encoding="utf-8") as configFile:
            json.dump({"classPath": ["spacehaven.jar"], "vmArgs": []}, configFile)

        config = load_config(self.configPath)
        config["classPath"].insert(0, otherJar)
        with open(self.configPath, "w", encoding="utf-8") as configFile:
            json.dump(config, configFile)

        mod.enable()
        config = load_config(self.configPath)

        self.assertLess(config["classPath"].index(otherJar), config["classPath"].index(mod.classPathName))
        self.assertLess(config["classPath"].index(mod.classPathName), config["classPath"].index("spacehaven.jar"))

    def test_disable_removes_only_this_mod_jar(self):
        modPath = os.path.join(self.gameDir, "mods", TEST_MOD_NAME)
        infoPath = write_mod_files(modPath)
        mod = JarMod(infoPath, self.gameInfo, TEST_MOD_JAR)

        mod.enable()
        config = load_config(self.configPath)
        otherJar = normalize_classpath_entry(os.path.join(self.gameDir, "mods", "OtherMod", "OtherMod.jar"))
        config["classPath"].append(otherJar)
        with open(self.configPath, "w", encoding="utf-8") as configFile:
            json.dump(config, configFile)

        mod.disable()
        config = load_config(self.configPath)

        self.assertNotIn(mod.classPathName, config["classPath"])
        self.assertIn(otherJar, config["classPath"])
        self.assertIn(ASPECTJ_WEAVER_JAR, config["classPath"])
        self.assertIn(ASPECTJ_JAR, config["classPath"])
        self.assertTrue(os.path.isfile(os.path.join(modPath, DISABLED_MARKER)))

    def test_disable_cleans_classpath_when_marker_write_fails(self):
        modPath = os.path.join(self.gameDir, "mods", TEST_MOD_NAME)
        infoPath = write_mod_files(modPath)
        mod = JarMod(infoPath, self.gameInfo, TEST_MOD_JAR)
        mod.enable()
        real_open = open

        def fail_marker_open(path, mode="r", *args, **kwargs):
            if os.path.basename(path) == DISABLED_MARKER and "w" in mode:
                raise PermissionError("marker is read-only")
            return real_open(path, mode, *args, **kwargs)

        with patch("builtins.open", side_effect=fail_marker_open):
            mod.disable()

        config = load_config(self.configPath)

        self.assertNotIn(mod.classPathName, config["classPath"])

    def test_disable_does_not_crash_without_config(self):
        modPath = os.path.join(self.root, "Steam", "steamapps", "workshop", "content", "979110", TEST_WORKSHOP_ITEM_ID)
        infoPath = write_mod_files(modPath)
        mod = JarMod(infoPath, self.gameInfo, TEST_MOD_JAR)
        os.remove(self.configPath)

        mod.disable()

        self.assertTrue(os.path.isfile(os.path.join(modPath, DISABLED_MARKER)))

    def test_reconcile_removes_stale_managed_jars_and_keeps_unknown_entries(self):
        modsRoot = os.path.join(self.gameDir, "mods")
        workshopRoot = os.path.join(self.root, "Steam", "steamapps", "workshop", "content", "979110")
        activePath = os.path.join(modsRoot, TEST_MOD_NAME)
        disabledPath = os.path.join(modsRoot, "DisabledJarMod")
        staleLocalJar = normalize_classpath_entry(os.path.join(modsRoot, "MissingJarMod", "MissingJarMod.jar"))
        staleWorkshopJar = normalize_classpath_entry(os.path.join(workshopRoot, "9999999999", "OldWorkshop.jar"))
        unknownJar = normalize_classpath_entry(os.path.join(self.root, "External", "ManualJar.jar"))
        disabledJar = normalize_classpath_entry(os.path.join(disabledPath, "DisabledJarMod.jar"))

        activeInfoPath = write_mod_files(activePath)
        activeMod = JarMod(activeInfoPath, self.gameInfo, TEST_MOD_JAR)

        disabledInfoPath = write_mod_files(disabledPath)
        disabledMod = JarMod(disabledInfoPath, self.gameInfo, "DisabledJarMod.jar")
        with open(os.path.join(disabledPath, "DisabledJarMod.jar"), "w", encoding="utf-8") as jarFile:
            jarFile.write("")
        with open(os.path.join(disabledPath, DISABLED_MARKER), "w", encoding="utf-8") as marker:
            marker.write("disabled")
        disabledMod.enabled = False

        os.makedirs(os.path.dirname(staleWorkshopJar.replace("/", os.sep)), exist_ok=True)
        os.makedirs(os.path.dirname(unknownJar.replace("/", os.sep)), exist_ok=True)
        with open(unknownJar.replace("/", os.sep), "w", encoding="utf-8") as jarFile:
            jarFile.write("")

        with open(self.configPath, "w", encoding="utf-8") as configFile:
            json.dump(
                {
                    "classPath": [
                        "aspectjweaver-1.9.19.jar",
                        "aspectjweaver-1.9.19.jar",
                        "aspectj-1.9.19.jar",
                        activeMod.classPathName,
                        disabledJar,
                        staleLocalJar,
                        staleWorkshopJar,
                        unknownJar,
                        "spacehaven.jar",
                    ],
                    "vmArgs": [],
                },
                configFile,
            )

        changed = reconcile_jarmod_classpath(self.gameInfo, [activeMod, disabledMod], [modsRoot, workshopRoot])
        config = load_config(self.configPath)

        self.assertTrue(changed)
        self.assertIn(activeMod.classPathName, config["classPath"])
        self.assertIn(unknownJar, config["classPath"])
        self.assertNotIn(disabledJar, config["classPath"])
        self.assertNotIn(staleLocalJar, config["classPath"])
        self.assertNotIn(staleWorkshopJar, config["classPath"])
        self.assertEqual(config["classPath"].count("aspectjweaver-1.9.19.jar"), 1)


if __name__ == "__main__":
    unittest.main()
