from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from lxml import etree
import png

from loader.assets.explode import Texture
from loader.assets.merge import _detect_textures
from ui.database import ModDatabase


class TexturePagesTests(TestCase):
    def test_multi_page_allocation_remaps_animations_and_writes_no_mod_outputs(self):
        with TemporaryDirectory() as scratch:
            path = Path(scratch) / "textures"
            path.mkdir()
            for name in ("sprite1.png", "sprite2.png"):
                with (path / name).open("wb") as output:
                    row = [0, 0, 0, 255] * 1025
                    png.Writer(1025, 1025, greyscale=False, alpha=True).write(output, [row] * 1025)
            src = etree.fromstring(b'<A><assetPos filename="sprite1"/><assetPos filename="sprite2"/></A>')
            base = etree.fromstring(b'<AllTexturesAndRegions><textures><t i="9999"/></textures></AllTexturesAndRegions>')
            core = {"_last_core_region_id": 9, "_next_region_id": 10, "_custom_textures_cim": {}, "library/textures": base}
            mod_lib = {"library/animations": [src]}
            with patch.object(ModDatabase, "getMod", return_value=None):
                textures = _detect_textures(core, mod_lib, scratch)
            self.assertEqual(set(textures), {"10", "11"})
            self.assertEqual(src.xpath("//assetPos/@a"), ["10", "11"])
            tree = mod_lib["library/textures"][0]
            self.assertEqual(2, len(set(tree.xpath("//re/@t"))))
            self.assertNotIn("9999", tree.xpath("//re/@t"))
            self.assertEqual({"textures"}, {p.name for p in Path(scratch).iterdir()})

    def test_cim_rejects_out_of_bounds_png_and_round_trips(self):
        with TemporaryDirectory() as scratch:
            src = Path(scratch) / "sprite.png"
            with src.open("wb") as output:
                png.Writer(1, 1, greyscale=False, alpha=True).write(output, [[255, 3, 2, 255]])
            texture = Texture(None, create=True, width=2, height=2)
            with self.assertRaisesRegex(ValueError, "bounds"):
                texture.pack_png(src, x=2)
            texture.pack_png(src)
            dest = Path(scratch) / "page.cim"
            texture.export_cim(dest)
            self.assertEqual(texture.data, Texture(dest).data)
