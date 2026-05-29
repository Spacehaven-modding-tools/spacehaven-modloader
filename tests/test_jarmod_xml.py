import os
import tempfile
import unittest
from pathlib import Path

import lxml.etree

import loader.assets.merge as merge


# Minimal but valid core library files. merge.mods() requires every entry in
# PATCHABLE_XML_FILES to exist, library/textures to have at least one <re n>,
# and library/audio to have an <audio> root.
CORE_FILES = {
    "haven": "<data><Element><me mid=\"1\"/></Element></data>",
    "texts": "<t></t>",
    "animations": "<AllAnimations><animations></animations></AllAnimations>",
    "textures": (
        "<AllTexturesAndRegions><textures></textures>"
        "<regions><re n=\"100\" t=\"0\" x=\"0\" y=\"0\" w=\"1\" h=\"1\"/></regions>"
        "</AllTexturesAndRegions>"
    ),
    "audio": "<audio></audio>",
}


class FakeGameInfo:
    def __init__(self, jarPath):
        self.jarPath = str(jarPath)
        self.version = "1.0.0"


class JarModXmlMergeTests(unittest.TestCase):
    """A JAR mod can ship traditional XML modifications under library/.

    Regression guard for the bug where JAR mods were excluded from the XML
    merge pipeline and only had their .jar injected via the classPath.
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

        self.core_path = self.root / "core"
        core_library = self.core_path / "library"
        core_library.mkdir(parents=True)
        for name, content in CORE_FILES.items():
            (core_library / name).write_text(content, encoding="utf-8")

    def tearDown(self):
        self.temp_dir.cleanup()

    def _make_jar_mod(self, mod_name, element_mid):
        """Create a mod folder that contains BOTH a .jar and a library/ XML mod."""
        mod_path = self.root / "mods" / mod_name
        (mod_path / "library").mkdir(parents=True)
        # The presence of a .jar file is what classifies this as a JAR mod.
        (mod_path / f"{mod_name}.jar").write_text("", encoding="utf-8")
        (mod_path / "library" / "haven.xml").write_text(
            "<data><Element><me mid=\"{}\"/></Element></data>".format(element_mid),
            encoding="utf-8",
        )
        return mod_path

    def _read_core_haven(self):
        return lxml.etree.parse(self.core_path / "library" / "haven")

    def test_jar_mod_library_xml_is_merged(self):
        mod_path = self._make_jar_mod("XmlCarryingJarMod", element_mid="999")

        merge.mods(str(self.core_path), [], [str(mod_path)])

        merged = self._read_core_haven()
        self.assertTrue(
            merged.xpath("/data/Element/me[@mid='999']"),
            "JAR mod's library/haven.xml definition was not merged into the core library.",
        )
        # Core content must be preserved.
        self.assertTrue(merged.xpath("/data/Element/me[@mid='1']"))


if __name__ == "__main__":
    unittest.main()
