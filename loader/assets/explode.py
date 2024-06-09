
import hashlib
import io
import os
import struct
import zlib

import click
import lxml.etree
import png
import ui.log

from loader.assets.utils import create_xml_parser

PIXEL_SIZE = 4
RGBA_FORMAT = 4
HEADER_SIZE = 12

"""
alt code for png
        if 0:
            from PIL import Image
            reader = Image.open(path)
            print(reader.format, reader.size, reader.mode)
            width, height = reader.size
            img_data = reader.getdata()
            for row_idx in range(height):
                start = (x + ((row_idx + y) * width)) * PIXEL_SIZE + HEADER_SIZE
                end = start + (width * PIXEL_SIZE)
                # FIXME might be tricky to get the image in the correct format ...
        else:
"""
class Texture:
    def __init__(self, path, create = False, width = None, height = None):
        if create:
            return self._init_cim(width, height)
        else:
            return self._import_cim(path)
    
    def _init_cim(self, width, height):
        self.width = int(width)
        self.height = int(height)
        
        self.header = bytearray(HEADER_SIZE)
        struct.pack_into('>i', self.header, 0, self.width)
        struct.pack_into('>i', self.header, 4, self.height)
        struct.pack_into('>i', self.header, 8, RGBA_FORMAT)
        
        self.data = bytearray(self.width * self.height * PIXEL_SIZE)
    
    def _import_cim(self, path):
        data = io.BytesIO(zlib.decompress(open(path, "rb").read()))
        md5 = hashlib.md5(data.getbuffer()).hexdigest()
        ui.log.log("  %s vanilla md5 %s %d bytes" % (os.path.split(path)[1], md5, data.getbuffer().nbytes))
        
        self.header = data.read(HEADER_SIZE)
        self.width = struct.unpack_from('>i', self.header)[0]
        self.height = struct.unpack_from('>i', self.header, offset = 4)[0]
        self.format = struct.unpack_from('>i', self.header, offset = 8)[0]

        if self.format == RGBA_FORMAT:
            self.mode = "RGBA"
        else:
            ui.log.log("ERROR: Unknown CIM format: {}".format(self.format))
            return

        self.data = bytearray(data.read())
        expected_size = self.width * self.height * PIXEL_SIZE
        if len(self.data) != expected_size:
            ui.log.log("ERROR: Wrong size %s: %d vs %d" % (path, len(self.data), expected_size))
    
    def pack_png(self, path, x=0, y=0, w=0, h=0):
        reader = png.Reader(filename = path)
        (width, height, rows, info) = reader.asRGBA()
        if w and w != width:
            ui.log.log("ERROR: Wrong width in %s: %d vs %d" % (path, width, w))
            return
        if h and h != height:
            ui.log.log("ERROR: Wrong width in %s: %d vs %d" % (path, height, h))
            return
        
        row_idx = 0
        for row in rows:
            start = (x + ((row_idx + y) * self.width)) * PIXEL_SIZE
            end = start + (width * PIXEL_SIZE)
            
            self.data[start:end] = row
            row_idx += 1
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

        rows = []
        for row in range(height):
            start = (x + ((row + y) * self.width)) * PIXEL_SIZE
            end = start + (width * PIXEL_SIZE)

            rows.append(self.data[start:end])

        with open(path, 'wb') as file:
            writer = png.Writer(width=width, height=height, greyscale=False, alpha=True)
            writer.write_packed(file, rows)


def explode(corePath):
    """Decode textures and write them out as individual regions"""

    textures = lxml.etree.parse(os.path.join(corePath, "library", "textures"), parser=create_xml_parser())
    cims = {}
    export_cims = {}
    
    regions = textures.xpath("//re[@n]")

    ui.log.log("  Exploding textures at {}...".format(corePath))

    for region in regions:
        name = region.get("n")

        x = int(region.get("x"))
        y = int(region.get("y"))
        w = int(region.get("w"))
        h = int(region.get("h"))

        page = region.get("t")

        if not page in cims:
            cim_filename = '{}.cim'.format(page)
            ui.log.updateBackgroundState("Unpacking textures ({})".format(cim_filename))
            cims[page] = Texture(os.path.join(corePath, 'library', cim_filename))
        
        try:
            os.makedirs(os.path.join(corePath, 'library', 'textures.exploded', page))
        except FileExistsError:
            pass
        
        png_filename = os.path.join(corePath, 'library', 'textures.exploded', page, '{}.png'.format(name))
        cims[page].export_png(png_filename, x, y, w, h)

    for page in cims:
        cims[page].export_png(os.path.join(corePath, 'library', 'textures.exploded', '{}.png'.format(page)))
        

    ui.log.log("    Wrote {} texture regions".format(len(regions)))

