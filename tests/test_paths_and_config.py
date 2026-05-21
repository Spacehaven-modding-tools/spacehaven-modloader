import os
import tempfile
import unittest
from pathlib import Path

from ui.database import Mod, ModDatabase, normalize_classpath_entry
from ui.paths import resolve_workshop_path


class FakeGameInfo:
    def __init__(self, jarPath):
        self.jarPath = str(jarPath)
        self.version = "1.0.0"


def write_info_xml(mod_path, name, value="default"):
    mod_path = Path(mod_path)
    mod_path.mkdir(parents=True, exist_ok=True)
    info_path = mod_path / "info.xml"
    info_path.write_text(
        f"""<mod>
    <name>{name}</name>
    <description>{name} description</description>
    <minimumLoaderVersion>0.12.2</minimumLoaderVersion>
    <config>
        <var name="power" type="str" default="default" value="{value}">Power setting</var>
        <var name="crew" type="str" default="small" value="small">Crew setting</var>
    </config>
</mod>""",
        encoding="utf-8",
    )
    return str(info_path)


class PathAndConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_resolve_workshop_path_from_steam_install(self):
        steamapps = self.root / "Steam" / "steamapps"
        game_path = steamapps / "common" / "SpaceHaven" / "spacehaven.exe"
        workshop_path = steamapps / "workshop" / "content" / "979110"
        game_path.parent.mkdir(parents=True, exist_ok=True)
        workshop_path.mkdir(parents=True, exist_ok=True)

        resolved = resolve_workshop_path(str(game_path))
        # Compare via Path.resolve() on both sides so Windows short-name (8.3)
        # vs long-name normalization differences don't cause a false negative
        # on CI runners whose user name expands (e.g. RUNNER~1 -> runneradmin).
        self.assertEqual(Path(resolved).resolve(), workshop_path.resolve())

    def test_resolve_workshop_path_returns_none_for_non_steam_install(self):
        game_path = self.root / "GOG Games" / "SpaceHaven" / "spacehaven.exe"
        game_path.parent.mkdir(parents=True, exist_ok=True)

        self.assertIsNone(resolve_workshop_path(str(game_path)))

    def test_mod_config_save_persists_values(self):
        mod_path = self.root / "mods" / "ConfigMod"
        info_path = write_info_xml(mod_path, "ConfigMod")
        game_info = FakeGameInfo(self.root / "SpaceHaven" / "spacehaven.jar")

        mod = Mod(info_path, game_info)
        mod.variables[0].value = "high"

        self.assertTrue(mod.saveConfig())

        reloaded = Mod(info_path, game_info)
        values = {var.name: var.value for var in reloaded.variables}
        self.assertEqual(values["power"], "high")
        self.assertEqual(values["crew"], "small")

    def test_mod_load_order_persists(self):
        game_dir = self.root / "SpaceHaven"
        mods_dir = game_dir / "mods"
        game_dir.mkdir(parents=True, exist_ok=True)
        game_info = FakeGameInfo(game_dir / "spacehaven.jar")
        write_info_xml(mods_dir / "Beta", "Beta")
        write_info_xml(mods_dir / "Alpha", "Alpha")

        database = ModDatabase([str(mods_dir)], game_info)
        database.locateMods()
        database.mods = list(reversed(database.mods))
        self.assertTrue(database.save_load_order())

        reloaded = ModDatabase([str(mods_dir)], game_info)
        reloaded.locateMods()

        self.assertEqual([mod.name for mod in reloaded.mods], [mod.name for mod in database.mods])

    def test_normalize_classpath_entry_uses_absolute_forward_slashes(self):
        path = self.root / "mods" / "My Mod" / "MyMod.jar"
        normalized = normalize_classpath_entry(str(path))

        self.assertTrue(os.path.isabs(normalized))
        self.assertNotIn("\\", normalized)


if __name__ == "__main__":
    unittest.main()
