import json
import os
import tempfile
import unittest

from ui.database import Mod, ModDatabase, normalize_classpath_entry
from ui.paths import resolve_workshop_path


class FakeGameInfo:
    def __init__(self, jarPath):
        self.jarPath = jarPath
        self.version = "1.0.0"


def write_info_xml(mod_path, name, value="default"):
    os.makedirs(mod_path, exist_ok=True)
    info_path = os.path.join(mod_path, "info.xml")
    with open(info_path, "w", encoding="utf-8") as info_file:
        info_file.write(
            f"""<mod>
    <name>{name}</name>
    <description>{name} description</description>
    <minimumLoaderVersion>0.12.2</minimumLoaderVersion>
    <config>
        <var name="power" type="str" default="default" value="{value}">Power setting</var>
        <var name="crew" type="str" default="small" value="small">Crew setting</var>
    </config>
</mod>"""
        )
    return info_path


class PathAndConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = self.temp_dir.name

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_resolve_workshop_path_from_steam_install(self):
        steamapps = os.path.join(self.root, "Steam", "steamapps")
        game_path = os.path.join(steamapps, "common", "SpaceHaven", "spacehaven.exe")
        workshop_path = os.path.join(steamapps, "workshop", "content", "979110")
        os.makedirs(os.path.dirname(game_path), exist_ok=True)
        os.makedirs(workshop_path, exist_ok=True)

        self.assertEqual(os.path.normcase(resolve_workshop_path(game_path)), os.path.normcase(workshop_path))

    def test_resolve_workshop_path_returns_none_for_non_steam_install(self):
        game_path = os.path.join(self.root, "GOG Games", "SpaceHaven", "spacehaven.exe")
        os.makedirs(os.path.dirname(game_path), exist_ok=True)

        self.assertIsNone(resolve_workshop_path(game_path))

    def test_mod_config_save_persists_values(self):
        mod_path = os.path.join(self.root, "mods", "ConfigMod")
        info_path = write_info_xml(mod_path, "ConfigMod")
        game_info = FakeGameInfo(os.path.join(self.root, "SpaceHaven", "spacehaven.jar"))

        mod = Mod(info_path, game_info)
        mod.variables[0].value = "high"

        self.assertTrue(mod.saveConfig())

        reloaded = Mod(info_path, game_info)
        values = {var.name: var.value for var in reloaded.variables}
        self.assertEqual(values["power"], "high")
        self.assertEqual(values["crew"], "small")

    def test_mod_load_order_persists(self):
        game_dir = os.path.join(self.root, "SpaceHaven")
        mods_dir = os.path.join(game_dir, "mods")
        os.makedirs(game_dir, exist_ok=True)
        game_info = FakeGameInfo(os.path.join(game_dir, "spacehaven.jar"))
        write_info_xml(os.path.join(mods_dir, "Beta"), "Beta")
        write_info_xml(os.path.join(mods_dir, "Alpha"), "Alpha")

        database = ModDatabase([mods_dir], game_info)
        database.locateMods()
        database.mods = list(reversed(database.mods))
        self.assertTrue(database.save_load_order())

        reloaded = ModDatabase([mods_dir], game_info)
        reloaded.locateMods()

        self.assertEqual([mod.name for mod in reloaded.mods], [mod.name for mod in database.mods])

    def test_normalize_classpath_entry_uses_absolute_forward_slashes(self):
        path = os.path.join(self.root, "mods", "My Mod", "MyMod.jar")
        normalized = normalize_classpath_entry(path)

        self.assertTrue(os.path.isabs(normalized))
        self.assertNotIn("\\", normalized)


if __name__ == "__main__":
    unittest.main()

