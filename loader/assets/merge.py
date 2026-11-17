import copy
import os
from pathlib import Path
import shutil

import lxml.etree
import png
import rectpack
import ui.database
import ui.log

from .explode import Texture
from .library import PATCHABLE_XML_FILES
from .patch import doPatches
from .utils import create_xml_parser


def _detect_textures(coreLibrary, modLibrary, mod):
    textures_path = (Path(mod) / "textures").resolve()
    if not textures_path.is_dir():
        return {}
    if not textures_path.is_relative_to(Path(mod).resolve()):
        raise ValueError(f"Texture directory leaves the mod: {textures_path}")
    animations = modLibrary.get("library/animations", [])
    texture_xml = modLibrary.get("library/textures", [])
    regions = [region for tree in texture_xml for region in tree.xpath("//re[@n]")]
    automatic = {}
    textures = {}
    references = {}

    def register(filename, required=False):
        if filename in references:
            return references[filename]
        path = (textures_path / filename).resolve()
        if not path.is_relative_to(textures_path):
            raise ValueError(f"Texture path leaves the mod: {filename}")
        if not path.is_file():
            if required:
                raise FileNotFoundError(path)
            return None
        stem = Path(filename).stem
        if stem.isdecimal() and 0 <= int(stem) <= coreLibrary["_last_core_region_id"]:
            region_id = str(int(stem))
        else:
            region_id = str(coreLibrary["_next_region_id"])
            coreLibrary["_next_region_id"] += 1
        references[filename] = region_id
        textures[region_id] = {"path": str(path)}
        return region_id

    for tree in texture_xml:
        for page in tree.xpath("//t[@i]"):
            page_id = str(int(page.get("i")))
            page.set("i", page_id)
            coreLibrary["_custom_textures_cim"][page_id] = dict(page.attrib)

    for region in regions:
        region_id = region.get("n")
        filename = region_id + ".png"
        mapped = register(filename)
        if mapped is not None:
            region.set("n", mapped)
        if region.get("t") is not None:
            region.set("t", str(int(region.get("t"))))

    for tree in animations:
        for asset in tree.xpath("//assetPos[@filename]"):
            filename = asset.get("filename").lstrip("/")
            if not filename.lower().endswith(".png"):
                filename += ".png"
            # A filename explicitly requests new atlas placement unless manually defined.
            region_id = register(filename, required=True)
            asset.set("a", region_id)
            if int(region_id) > coreLibrary["_last_core_region_id"] and not any(r.get("n") == region_id for r in regions):
                automatic[filename] = region_id
        for asset in tree.xpath("//assetPos[@a and not(@filename)]"):
            region = asset.get("a")
            if not region.isdecimal():
                raise ValueError(f"Non-numeric texture region ID: {region!r}")
            if mapped := references.get(region + ".png"):
                asset.set("a", mapped)

    if not automatic:
        return textures

    if not texture_xml:
        root = lxml.etree.Element("AllTexturesAndRegions")
        texture_xml = modLibrary["library/textures"] = [lxml.etree.ElementTree(root)]
    root = texture_xml[0].getroot()
    pages_node = root.find("textures")
    if pages_node is None:
        pages_node = lxml.etree.SubElement(root, "textures")
    regions_node = root.find("regions")
    if regions_node is None:
        regions_node = lxml.etree.SubElement(root, "regions")

    size = 2048
    packer = rectpack.newPacker(rotation=False)
    packer.add_bin(size, size, count=float("inf"))
    for filename, region_id in sorted(automatic.items()):
        with open(textures[region_id]["path"], "rb") as source:
            reader = png.Reader(file=source)
            reader.preamble()
            width, height = reader.width, reader.height
        if not (0 < width <= size and 0 < height <= size):
            raise ValueError(f"Texture {filename} is {width}x{height}, exceeding the {size}x{size} atlas")
        packer.add_rect(width, height, region_id)
    packer.pack()
    rectangles = packer.rect_list()
    if len(rectangles) != len(automatic):
        raise ValueError(f"Could not pack all textures for {mod}")
    ui.log.log(f"    Packed {len(rectangles)} texture(s) into {len(packer)} sprite sheet(s).")

    used = {int(page.get("i")) for page in coreLibrary["library/textures"].xpath("//t[@i]")}
    used.update(map(int, coreLibrary["_custom_textures_cim"]))
    reserved = set(ui.database.ModDatabase.Prefixes)
    registered_mod = ui.database.ModDatabase.getMod(mod)
    preferred = registered_mod.prefix if registered_mod else None
    next_page = max(used | {9998}) + 1
    page_ids = []
    for index in range(len(packer)):
        if index == 0 and preferred and preferred > 0 and preferred not in used:
            page_id = preferred
        else:
            while next_page in used or next_page in reserved:
                next_page += 1
            page_id = next_page
        used.add(page_id)
        page_ids.append(page_id)
        attributes = {"i": str(page_id), "w": str(size), "h": str(size)}
        lxml.etree.SubElement(pages_node, "t", **attributes)
        coreLibrary["_custom_textures_cim"][str(page_id)] = attributes

    for page, x, y, width, height, region_id in sorted(rectangles, key=lambda rect: int(rect[-1])):
        lxml.etree.SubElement(
            regions_node, "re", n=region_id, t=str(page_ids[page]),
            x=str(x), y=str(y), w=str(width), h=str(height), file=Path(textures[region_id]["path"]).name,
        )
    return textures


def buildLibrary(location: str, mod: str):
    """Build up a library dict of files in `location`"""

    def _mod_path(filename):
        return os.path.join(mod, filename.replace("/", os.sep))

    location_library = {}
    try:
        location_files = [location + "/" + mod_file for mod_file in sorted(os.listdir(_mod_path(location)), key=str.casefold)]
    except FileNotFoundError:
        location_files = []

    # we allow breaking down mod xml files into smaller pieces for readability
    for target in PATCHABLE_XML_FILES:
        targetInLocation = target.replace("library", location)
        for mod_file in location_files:
            if not mod_file.startswith(targetInLocation):
                continue
            if target not in location_library:
                location_library[target] = []

            ui.log.log("    {} <= {}".format(target, mod_file))
            path = Path(_mod_path(mod_file)).resolve()
            if not path.is_relative_to(Path(mod).resolve()) or not path.is_file():
                raise ValueError(f"Invalid mod input file: {path}")
            with path.open("rb") as f:
                location_library[target].append(lxml.etree.parse(f, parser=create_xml_parser()))

    return location_library


def mods(corePath, activeMods, modPaths):
    # Load the core library files
    coreLibrary = {}

    def _core_path(filename):
        return os.path.join(corePath, filename.replace("/", os.sep))

    for filename in PATCHABLE_XML_FILES:
        with open(_core_path(filename), "rb") as f:
            # Build 1.0.4 has malformed entity references in its shipped texts.
            coreLibrary[filename] = lxml.etree.parse(f, parser=create_xml_parser(recover=filename == "library/texts"))

    # find the last region in the texture file and remember its index
    # we will need this to add mod textures with consecutive indexes...
    coreLibrary["_last_core_region_id"] = max(int(node.get("n")) for node in coreLibrary["library/textures"].xpath("//re[@n]"))
    coreLibrary["_next_region_id"] = coreLibrary["_last_core_region_id"] + 1
    coreLibrary["_all_modded_textures"] = {}
    coreLibrary["_custom_textures_cim"] = {}

    # Merge in modded files
    for mod in modPaths:
        ui.log.updateLaunchState("Installing {}".format(os.path.basename(mod)))

        ui.log.log("  Loading mod {}...".format(mod))

        # Load the mod's library
        modLibrary = buildLibrary("library", mod)
        doMerges(coreLibrary, modLibrary, mod)

    # Do patches after merges to avoid clobbers
    for mod in activeMods:
        ui.log.updateLaunchState(f"Patching {os.path.basename(mod.path)}")
        ui.log.log(f"  Loading patches {mod.path}...")
        modPatchesLibrary = buildLibrary("patches", mod.path)
        doPatches(coreLibrary, modPatchesLibrary, mod)

    ui.log.updateLaunchState("Updating XML")

    # Write out the new base library
    for filename in PATCHABLE_XML_FILES:
        with open(_core_path(filename), "wb") as f:
            f.write(lxml.etree.tostring(coreLibrary[filename], pretty_print=True, encoding="UTF-8"))

    # EXTRA ASSETS ADDED BY MODS
    extra_assets = []

    # AUDIO
    ui.log.updateLaunchState("Packing audio")

    # First of all, the 'a' entries should be sorted by 'at' attribbute, then by 'id' attribute:
    baseRoot = coreLibrary["library/audio"].xpath("/audio")[0]
    baseRoot[:] = sorted(baseRoot, key=lambda e: (-ord(e.get("at")[0]), int(e.get("id"))))

    # get list of original audio files
    valid_audio_types = ["Sound", "Music"]
    valid_audio_extensions = ["ogg", "mp3"]

    # get the game's original audio file list
    original_audio_relative_paths = set()
    for valid_audio_type in valid_audio_types:
        original_audio_directory = os.path.join(corePath, "library", valid_audio_type.lower())
        for abs_dir, _, filenames in os.walk(original_audio_directory):
            for filename in filenames:
                rel_dir = os.path.relpath(abs_dir, corePath)
                rel_path = os.path.join(rel_dir, filename)
                original_audio_relative_paths.add(rel_path.replace(os.sep, "/"))

    # process each audio entry in 'audio' file
    for audio in coreLibrary["library/audio"].xpath("//a[@n and @at]"):

        audio_name = audio.get("n")

        # validate audio reference type
        audio_type = audio.get("at")
        if audio_type not in valid_audio_types:
            ui.log.log(f"  ERROR: The type of the audio reference '{audio_name}' must be one of these: {','.join(valid_audio_types)}")
            continue

        # get encoding and relative audio path
        audio_encoding = None
        audio_relative_path = None
        for ext in valid_audio_extensions:
            if ext in audio.attrib:
                audio_encoding = ext.lower()
                audio_relative_path = audio.get(ext)
                if not audio_relative_path.lower().endswith(audio_encoding):
                    ui.log.log(f"  ERROR: The encoding type '{audio_encoding}' of the audio reference '{audio_name}' must be the same as its file extension '{audio_relative_path}'")
                break
        if audio_encoding is None or audio_relative_path is None:
            ui.log.log(f"  ERROR: the audio reference '{audio_name}' is invalid: unable to determine the audio's encoding type and relative path")
            continue

        # get audio filename
        audio_filename = Path(audio_relative_path).name

        # check if the audio file exist in mods
        audio_path_list = []
        for mod in modPaths:
            audio_path = os.path.join(mod, "audio", audio_filename)
            if os.path.isfile(audio_path):
                audio_path_list.append((Path(mod).name, audio_path))

        # audio file not found in mods?
        if len(audio_path_list) <= 0:
            # is it an original game audio?
            if audio_relative_path in original_audio_relative_paths:
                continue
            # audio file also not found as original game audio => notify!
            ui.log.log(f"  ERROR: Unable to find referenced audio file: '{audio_filename}'")
            continue

        # found multiple audio files with same name => notify!
        if len(audio_path_list) > 1:
            ui.log.log(
                f"  ERROR: Duplicates of modded audio file '{audio_filename}' were found in the following mods, copying just the first one: {', '.join(sorted(set(mod for mod, _ in audio_path_list)))}"
            )

        audio_src_path = audio_path_list[0][1]

        # copy audio to library
        ui.log.log(f"  Copying {audio_relative_path}...")
        expected_root = f"library/{audio_type.lower()}/"
        audio_dst_path = (Path(corePath) / audio_relative_path).resolve()
        if (not audio_relative_path.startswith(expected_root)
                or not audio_dst_path.is_relative_to(Path(corePath).resolve() / "library" / audio_type.lower())
                or "\\" in audio_relative_path or ":" in audio_relative_path):
            raise ValueError(f"Invalid audio destination: {audio_relative_path}")
        audio_dst_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(audio_src_path, audio_dst_path)
        extra_assets.append(audio_relative_path)

    # TEXTURE
    ui.log.updateLaunchState("Packing textures")
    # add or overwrite textures from mods. This is done after all the XML has been merged into the core "textures" file
    cims = {}

    for region in coreLibrary["library/textures"].xpath("//re[@n]"):
        name = region.get("n")

        if name not in coreLibrary["_all_modded_textures"]:
            continue

        png_file = coreLibrary["_all_modded_textures"][name]["path"]

        page = str(int(region.get("t")))
        if page not in cims:
            cim_name = "{}.cim".format(page)
            page_path = Path(corePath) / "library" / cim_name
            if page_path.is_file():
                cims[page] = Texture(page_path)
            else:
                dimensions = coreLibrary["_custom_textures_cim"][page]
                cims[page] = Texture(page_path, create=True, width=dimensions["w"], height=dimensions["h"])
            extra_assets.append("library/" + cim_name)

        x = int(region.get("x"))
        y = int(region.get("y"))
        w = int(region.get("w"))
        h = int(region.get("h"))

        ui.log.log("  Patching {}.cim...".format(page))
        cims[page].pack_png(png_file, x, y, w, h)

    # cims contains only the textures files that have actually been modified
    for page in cims:
        ui.log.log("  Writing {}.cim...".format(page))
        cims[page].export_cim(os.path.join(corePath, "library", "{}.cim".format(page)))

    return extra_assets


def doMerges(coreLib, modLib, mod: str):
    """Do merge-based modding sequence"""

    def mergeShim(file: str, xpath: str, idAttribute: str):
        """Shim to reduce function call complexity"""
        mergeDefinitions(coreLib, modLib, file, xpath, idAttribute)

    def mergeAbortMessage(filename: str):
        """Shim to standardize error message"""
        ui.log.log(f"    No merges needed: {filename}")

    # Lookup table for all nodes in library/haven based on element and the expected ID format
    havenIDLookUpTable = {
        "/data/BackPack": "mid",
        "/data/BackStory": "id",
        "/data/CelestialObject": "id",
        "/data/Character": "cid",
        "/data/CharacterCondition": "id",
        "/data/CharacterSet": "cid",
        "/data/CharacterTrait": "id",
        "/data/CostGroup": "id",
        "/data/Craft": "cid",
        "/data/DataLog": "id",
        "/data/DataLogFragment": "id",
        "/data/DefaultStuff": "id",
        "/data/DialogChoice": "id",
        "/data/DifficultySettings": "id",
        "/data/Effect": "id",
        "/data/Element": "mid",
        "/data/Encounter": "id",
        "/data/Explosion": "id",  #
        "/data/Faction": "id",
        "/data/FloorExpPackage": "id",  #
        "/data/GameScenario": "id",  #
        "/data/GOAPAction": "id",
        "/data/IdleAnim": "id",
        "/data/IsoFX": "id",
        "/data/Item": "mid",
        "/data/MainCat": "id",
        "/data/Monster": "cid",
        "/data/Notes": "id",
        "/data/ObjectiveCollection": "nid",
        "/data/PersonalitySettings": "id",
        "/data/Plan": "id",
        "/data/Product": "eid",
        "/data/Randomizer": "id",
        "/data/RandomShip": "id",
        "/data/Robot": "cid",  #
        "/data/RoofExpPackage": "id",  #
        "/data/Room": "rid",
        "/data/Sector": "id",
        "/data/Ship": "rid",
        "/data/SubCat": "id",
        "/data/Tech": "id",  #
        "/data/TechTree": "id",  #
        "/data/TradingValues": "id",
    }

    # Do an element-wise merge (replacing conflicts)
    currentFile = "library/haven"
    if currentFile in modLib:
        for path, idText in havenIDLookUpTable.items():
            mergeShim(currentFile, path, idText)
    else:
        mergeAbortMessage(currentFile)

    currentFile = "library/texts"
    if currentFile in modLib:
        mergeShim(currentFile, "/t", idAttribute="id")
    else:
        mergeAbortMessage(currentFile)

    currentFile = "library/audio"
    if currentFile in modLib:
        mergeShim(currentFile, "/audio", idAttribute="id")
    else:
        mergeAbortMessage(currentFile)

    # Remap texture references before merging animations and textures.
    coreLib["_all_modded_textures"].update(_detect_textures(coreLib, modLib, mod))

    currentFile = "library/animations"
    if currentFile in modLib:
        mergeShim(currentFile, "/AllAnimations/animations", "n")
    else:
        mergeAbortMessage(currentFile)

    currentFile = "library/textures"
    if currentFile in modLib:
        mergeShim(currentFile, "/AllTexturesAndRegions/textures", "i")
        mergeShim(currentFile, "/AllTexturesAndRegions/regions", "n")
    else:
        mergeAbortMessage(currentFile)


def mergeDefinitions(baseLibrary, modLibrary, file, xpath, idAttribute):
    if file not in modLibrary:
        ui.log.log("    {}: Not present".format(file))
        return

    try:
        baseRoot = baseLibrary[file].xpath(xpath)[0]
    except IndexError:
        # that's a big error if we can't find it in the core!
        ui.log.log("    {}: ERROR CORE NOTHING AT {}".format(file, xpath))
        return

    for mod_xml in modLibrary[file]:
        try:
            modRoot = mod_xml.xpath(xpath)[0]
        except:
            continue

        merged = 0
        for element in list(modRoot):

            if isinstance(element, lxml.etree._Comment):
                ui.log.log("Skipping comment in merge")
                ui.log.log(lxml.etree.tostring(element, pretty_print=True).decode())
                continue

            # TODO auto-id algo: if element.get(idAttribute + "_auto") then
            # id = prefix * idSpaceSize + id
            conflicts = baseRoot.xpath("*[@*[name()=$attr] = $value]", attr=idAttribute, value=element.get(idAttribute, ""))

            for conflict in conflicts:
                baseRoot.remove(conflict)

            ui.log.log("Merging XML:")
            ui.log.log(lxml.etree.tostring(element, pretty_print=True).decode())
            baseRoot.append(copy.deepcopy(element))
            merged += 1

        if merged:
            # TODO add source filename
            ui.log.log("    {}: Merged {} elements into {}".format(file, merged, xpath))
