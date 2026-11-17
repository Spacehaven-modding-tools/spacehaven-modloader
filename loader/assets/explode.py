import hashlib
import os
import struct
import zlib

import lxml.etree
import png
import ui.log

from loader.assets.utils import create_xml_parser

PIXEL_SIZE = 4
RGBA_FORMAT = 4
HEADER_SIZE = 12
MAX_CIM_DIMENSION = 8192

class Texture:
    def __init__(self, path, create=False, width=None, height=None):
        if create:
            return self._init_cim(width, height)
        else:
            return self._import_cim(path)

    def _init_cim(self, width, height):
        self.width = int(width)
        self.height = int(height)
        self._pixel_bytes()

        self.header = bytearray(HEADER_SIZE)
        struct.pack_into(">i", self.header, 0, self.width)
        struct.pack_into(">i", self.header, 4, self.height)
        struct.pack_into(">i", self.header, 8, RGBA_FORMAT)

        self.data = bytearray(self.width * self.height * PIXEL_SIZE)

    def _pixel_bytes(self):
        if not (0 < self.width <= MAX_CIM_DIMENSION and 0 < self.height <= MAX_CIM_DIMENSION):
            raise ValueError(f"Unsupported CIM dimensions: {self.width}x{self.height}")
        return self.width * self.height * PIXEL_SIZE

    def _import_cim(self, path):
        inflate = zlib.decompressobj()
        with open(path, "rb") as source:
            chunk = source.read(65536)
            self.header = inflate.decompress(chunk, HEADER_SIZE)
            if len(self.header) != HEADER_SIZE:
                raise ValueError(f"Missing CIM header: {path}")
            self.width, self.height, self.format = struct.unpack(">iii", self.header)
            if self.format != RGBA_FORMAT:
                raise ValueError(f"Unsupported CIM format {self.format}: {path}")
            self.mode = "RGBA"
            expected = self._pixel_bytes()
            self.data = bytearray()
            chunk = inflate.unconsumed_tail or source.read(65536)
            while chunk and not inflate.eof:
                self.data.extend(inflate.decompress(chunk, expected - len(self.data) + 1))
                if len(self.data) > expected:
                    raise ValueError(f"CIM pixels exceed declared size: {path}")
                chunk = inflate.unconsumed_tail or source.read(65536)
            if not inflate.eof or len(self.data) != expected:
                raise ValueError(f"CIM pixel data is incomplete: {path}")

    def pack_png(self, path, x=0, y=0, w=0, h=0):
        with open(path, "rb") as source:
            width, height, rows, _ = png.Reader(file=source).asRGBA8()
            if (w and w != width) or (h and h != height):
                raise ValueError(f"Texture {path} is {width}x{height}, expected {w}x{h}")
            if x < 0 or y < 0 or x + width > self.width or y + height > self.height:
                raise ValueError(f"Texture {path} exceeds CIM page bounds")

            for row_idx, row in enumerate(rows):
                start = (x + ((row_idx + y) * self.width)) * PIXEL_SIZE
                end = start + (width * PIXEL_SIZE)
                self.data[start:end] = row
        ui.log.log("  Repacked {}...".format(os.path.split(path)[1]))

    def export_cim(self, path):
        export = self.header + self.data
        md5 = hashlib.md5(export).hexdigest()
        ui.log.log("  %s MODDED md5 %s %d bytes" % (os.path.split(path)[1], md5, len(export)))
        with open(path, "wb") as cim:
            cim.write(zlib.compress(export))

    def export_png(self, path, x=0, y=0, width=None, height=None):
        if width is None:
            width = self.width
        if height is None:
            height = self.height
        if not (x >= 0 and y >= 0 and width > 0 and height > 0 and x + width <= self.width and y + height <= self.height):
            raise ValueError(f"Texture export {path} exceeds CIM page bounds")

        rows = []
        for row in range(height):
            start = (x + ((row + y) * self.width)) * PIXEL_SIZE
            end = start + (width * PIXEL_SIZE)

            rows.append(self.data[start:end])

        with open(path, "wb") as file:
            writer = png.Writer(width=width, height=height, greyscale=False, alpha=True)
            writer.write_packed(file, rows)


def explode(corePath):
    """Decode textures and write them out as individual regions"""

    textures = lxml.etree.parse(os.path.join(corePath, "library", "textures"), parser=create_xml_parser())
    cims = {}
    # export_cims = {}

    regions = textures.xpath("//re[@n]")

    ui.log.log("  Exploding textures at {}...".format(corePath))

    for region in regions:
        name = str(int(region.get("n")))

        x = int(region.get("x"))
        y = int(region.get("y"))
        w = int(region.get("w"))
        h = int(region.get("h"))

        page = str(int(region.get("t")))

        if page not in cims:
            cim_filename = "{}.cim".format(page)
            ui.log.updateBackgroundState("Unpacking textures ({})".format(cim_filename))
            cims[page] = Texture(os.path.join(corePath, "library", cim_filename))

        try:
            os.makedirs(os.path.join(corePath, "library", "textures.exploded", page))
        except FileExistsError:
            pass

        png_filename = os.path.join(corePath, "library", "textures.exploded", page, "{}.png".format(name))
        cims[page].export_png(png_filename, x, y, w, h)

    for page in cims:
        cims[page].export_png(os.path.join(corePath, "library", "textures.exploded", "{}.png".format(page)))

    ui.log.log("    Wrote {} texture regions".format(len(regions)))
