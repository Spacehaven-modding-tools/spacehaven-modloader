
import copy
import math
import os

import loader.assets.library
import lxml.etree
import png
import rectpack
import ui.database
import ui.log

from .explode import Texture
from .library import PATCHABLE_CIM_FILES, PATCHABLE_XML_FILES
from .patch import doPatches
from .utils import create_xml_parser


def _detect_textures(coreLibrary, modLibrary, mod):
    textures_path = os.path.join(mod, 'textures')
    if not os.path.isdir(textures_path):
        return {}

    mapping_n_region = {}
    modded_textures = {}
    seen_textures = set()

    def _add_texture(filename):
        region_id = str.join(".", filename.split('.')[:-1])
        isCoreRegion = region_id.isdecimal() and int(region_id) <= coreLibrary['_last_core_region_id']
        # Early exit if this texture exists
        if (region_id in modded_textures) or (region_id in mapping_n_region):
            return

        path = os.path.join(textures_path, filename)
        #core region file without an associated file, return early
        if isCoreRegion and not os.path.exists(path):
            return

        if not isCoreRegion:
            # adding a new texture, this gets tricky as they have to have consecutive numbers.
            core_region_id = str(coreLibrary['_next_region_id'])
            mapping_n_region[filename] = core_region_id
            coreLibrary['_next_region_id'] += 1
            ui.log.log(f"    Allocated new core region idx {core_region_id:>5} to file {filename}")
        else:
            core_region_id = region_id
            ui.log.log(f"    Mod updated texture region {core_region_id}")

        seen_textures.add(filename)
        modded_textures[core_region_id] = {
            'mapped_from_id' : region_id,
            'filename' : filename,
            'path' : path,
            }

    autoAnimations = False
    for animation_chunk in modLibrary['library/animations']:
        filenameAssetPos = animation_chunk.find("//assetPos[@filename]")
        if filenameAssetPos is not None:
            autoAnimations = True

    # no textures.xml file and no autoAnimations, we're done
    if 'library/textures' not in modLibrary and not autoAnimations:
        return modded_textures
    # Create a textures xml tree if there was no manually-defined file
    if 'library/textures' not in modLibrary and autoAnimations:
        texRoot = lxml.etree.Element("AllTexturesAndRegions")
        lxml.etree.SubElement(texRoot, "textures")
        lxml.etree.SubElement(texRoot, "regions")
        modLibrary['library/textures'] = [lxml.etree.ElementTree(texRoot)]

    #FIXME verify that there's only one file
    # TODO Maybe don't require only a single file?
    textures_count = len(modLibrary['library/textures'])
    if len(modLibrary['library/textures']) != 1:
        ui.log.log(f"    Expected 1 library/textures but found {textures_count}")

    textures_mod = modLibrary['library/textures'][0]

    # Allocate any manually defined texture regions into the CTC lib
    for texture_pack in textures_mod.xpath("//t[@i]"):
        cim_id = texture_pack.get('i')
        coreLibrary['_custom_textures_cim'][cim_id] = texture_pack.attrib

    # Map manually defined regions in textures file to autoIDs
    for region in textures_mod.xpath("//re[@n]"):
        region_id = region.get('n')
        _add_texture(region_id)

    # no custom mod textures, no need to remap ids
    if not mapping_n_region and not autoAnimations:
        return modded_textures

    ##########################################################################
    # Custom Mod Textures processing starts here
    ##########################################################################
    needs_autogeneration = set()
    for animation_chunk in modLibrary['library/animations']:
        # iterate on autogeneration nodes
        for asset in animation_chunk.xpath("//assetPos[@filename]"):
            # asset.get will never return null here
            mod_local_id = asset.get("filename").lstrip("/")
            if ".png" not in mod_local_id:
                mod_local_id += ".png"
            if mod_local_id not in needs_autogeneration:
                needs_autogeneration.add(mod_local_id)
                _add_texture(mod_local_id)
            if mod_local_id not in mapping_n_region:
                continue
            new_id = mapping_n_region[mod_local_id]
            asset.set('a', new_id)

        # iterate on manually defined nodes
        for asset in animation_chunk.xpath("//assetPos[@a and not(@filename)]"):
            mod_local_id = asset.get('a')
            if not str.isdecimal(mod_local_id):
                raise ValueError(f"Cannot specify a non-numerical 'a' attribute {mod_local_id}. " +
                                  "Specify in 'filename' attribute instead.")
            _add_texture(mod_local_id + ".png")
            if mod_local_id not in mapping_n_region:
                continue
            new_id = mapping_n_region[mod_local_id]
            asset.set('a', new_id)

    if len(needs_autogeneration):
        image_count = len(needs_autogeneration)

        regionsNode = textures_mod.find("//regions")
        texturesNode = textures_mod.find("//textures")
        textureID:int = ui.database.ModDatabase.getMod(mod).prefix

        # Catch missing Modder ID.  Still try to process and move forward.
        if not textureID or textureID <= 0:
            ui.log.log("ERROR: info.xml is missing <modid>.  Mod Author should set this to their Discord ID for all mods they make.")
            textureID = 9999

        packer = rectpack.newPacker(rotation=False)
        sumA:int = 0  # Total Area
        sumW:int = 0  # Total Width
        sumH:int = 0  # Total Height
        minRequiredDimension = 2048
        # First get all the files and pack them into a new texture square
        for regionName in needs_autogeneration:
            (w, h, rows, info) = png.Reader(textures_path + "/" + regionName).asRGBA()
            packer.add_rect(w, h, regionName)
            minRequiredDimension = max(minRequiredDimension, w, h)
            sumA += (w * h)
            sumW += w
            sumH += h

        # The absolute largest size that can be needed to fit everything.
        maxRequiredDimension = int(math.ceil(math.sqrt(sumH*sumW)))

        # Increase size estimate until it is large enough.
        size:int = 0
        sizeEstimate = 1.2
        basearea = max( int(math.sqrt(sumA)) , minRequiredDimension )
        while size < maxRequiredDimension and image_count != len( packer.rect_list() or [] ) :
            size = int(basearea * sizeEstimate)
            packer.reset()
            packer.add_bin(size, size)
            packer.pack()
            sizeEstimate += 0.1

        newTex = lxml.etree.SubElement(texturesNode, "t")
        newTex.set("i", str(textureID))
        newTex.set("w", str(size))
        newTex.set("h", str(size))
        coreLibrary['_custom_textures_cim'][str(textureID)] = newTex.attrib

        # prepare to export packed PNG to mod directory.
        kwargs = {}
        kwargs['create'] = True
        kwargs['width'] = size
        kwargs['height'] = size
        export_path = os.path.join(mod, f"custom_texture_{textureID}.png")
        custom_png:Texture = Texture( export_path, **kwargs )

        packedRectsSorted = {}
        for rect in packer.rect_list():
            b, x, y, w, h, rid = rect
            remappedID = mapping_n_region[rid]
            packedRectsSorted[remappedID] = (str(x), str(y), str(w), str(h), str(rid))
            custom_png.pack_png( os.path.join(textures_path,rid) , x,y,w,h )

        # write back the cim file as png for debugging
        # this only includes textures from this mod, not the final generated cim.
        custom_png.export_png(export_path)

        # NOT YET SORTED
        packedRectsSorted = {k: v for k,v in sorted(packedRectsSorted.items())}
        # NOW SORTED: We need this to make sure the IDs are added to the textures file in the correct order

        for remappedID, data in packedRectsSorted.items(): 
            x, y, w, h, regionFileName = data
            remapData = modded_textures[remappedID]
            newNode = lxml.etree.SubElement(regionsNode, "re")
            newNode.set("n", remappedID)
            newNode.set("t", str(textureID))
            newNode.set("x", x)
            newNode.set("y", y)
            newNode.set("w", w)
            newNode.set("h", h)
            newNode.set("file", regionFileName)


    for asset in textures_mod.xpath("//re[@n]"):
        mod_local_id = asset.get('n')
        if mod_local_id not in mapping_n_region:
            continue
        new_id = mapping_n_region[mod_local_id]
        ui.log.log("  Mapping texture 're' {} to {}...".format(mod_local_id, new_id))
        asset.set('n', new_id)

    # write the new textures XML if changed.
    if autoAnimations:
        modLibrary['library/textures'][0].write(
            os.path.join(mod, "library", "generated_textures.xml"),
            pretty_print=True
        )

    return modded_textures


def buildLibrary(location: str, mod: str):
    """Build up a library dict of files in `location`"""
    def _mod_path(filename):
        return os.path.join(mod, filename.replace('/', os.sep))
    location_library = {}
    try:
        location_files = [location + '/' + mod_file for mod_file in os.listdir(_mod_path(location))]
    except FileNotFoundError:
        location_files = []

    # we allow breaking down mod xml files into smaller pieces for readability
    for target in PATCHABLE_XML_FILES:
        targetInLocation = target.replace('library', location)
        for mod_file in location_files:
            if not mod_file.startswith(targetInLocation): continue
            if target not in location_library:  location_library[target] = []

            ui.log.log("    {} <= {}".format(target, mod_file))
            with open(_mod_path(mod_file)) as f:
                location_library[target].append(lxml.etree.parse(f, parser=create_xml_parser()))

        mod_file = _mod_path(target)
        # try again with the extension ?
        if not os.path.exists(mod_file):
            mod_file += '.xml'
            if not os.path.exists(mod_file):
                continue
    return location_library


def mods(corePath, activeMods, modPaths):
    # Load the core library files
    coreLibrary = {}
    def _core_path(filename):
        return os.path.join(corePath, filename.replace('/', os.sep))

    for filename in PATCHABLE_XML_FILES:
        with open(_core_path(filename), 'rb') as f:
            coreLibrary[filename] = lxml.etree.parse(f, parser=create_xml_parser())

    # find the last region in the texture file and remember its index
    # we will need this to add mod textures with consecutive indexes...
    coreLibrary['_last_core_region_id'] = int(coreLibrary['library/textures'].find("//re[@n][last()]").get('n'))
    coreLibrary['_next_region_id'] = coreLibrary['_last_core_region_id'] + 1
    coreLibrary['_all_modded_textures'] = {}
    coreLibrary['_custom_textures_cim'] = {}

    # Merge in modded files
    for mod in modPaths:
        ui.log.updateLaunchState("Installing {}".format(os.path.basename(mod)))

        ui.log.log("  Loading mod {}...".format(mod))

        # Load the mod's library
        modLibrary = buildLibrary('library', mod)
        doMerges(coreLibrary, modLibrary, mod)

    # Do patches after merges to avoid clobbers
    for mod in activeMods:
        ui.log.updateLaunchState(f"Patching {os.path.basename(mod.path)}")
        ui.log.log(f"  Loading patches {mod.path}...")
        modPatchesLibrary = buildLibrary('patches', mod.path)
        doPatches(coreLibrary, modPatchesLibrary, mod)

    ui.log.updateLaunchState("Updating XML")

    # Write out the new base library
    for filename in PATCHABLE_XML_FILES:
        with open(_core_path(filename), "wb") as f:
            f.write(lxml.etree.tostring(coreLibrary[filename], pretty_print=True, encoding="UTF-8"))

    ui.log.updateLaunchState("Packing textures")
    # add or overwrite textures from mods. This is done after all the XML has been merged into the core "textures" file
    cims = {}
    reexport_cims = {}
    extra_assets = []

    for region in coreLibrary['library/textures'].xpath("//re[@n]"):
        name = region.get("n")

        if name not in coreLibrary['_all_modded_textures']:
            continue

        png_file = coreLibrary['_all_modded_textures'][name]['path']

        page = region.get("t")
        if not page in cims:
            cim_name = '{}.cim'.format(page)
            kwargs = {'create': False}
            # TODO better cross checking of texture packs
            if 'library/' + cim_name not in PATCHABLE_CIM_FILES:
                kwargs['create'] = True
                kwargs['width'] = coreLibrary['_custom_textures_cim'][page]['w']
                kwargs['height'] = coreLibrary['_custom_textures_cim'][page]['h']
                extra_assets.append('library/' + cim_name)
                
            cims[page] = Texture(os.path.join(corePath, 'library', cim_name), **kwargs)

            reexport_cims[page] = set()

        # write back the cim file as png for debugging
        # reexport_cims[page].add(os.path.normpath(mod + "/textures"))

        x = int(region.get("x"))
        y = int(region.get("y"))
        w = int(region.get("w"))
        h = int(region.get("h"))

        ui.log.log("  Patching {}.cim...".format(page))
        cims[page].pack_png(png_file, x, y, w, h)

    # cims contains only the textures files that have actually been modified
    for page in cims:
        ui.log.log("  Writing {}.cim...".format(page))
        cims[page].export_cim(os.path.join(corePath, 'library', '{}.cim'.format(page)))

    return extra_assets


def doMerges(coreLib, modLib, mod: str):
    """Do merge-based modding sequence"""
    def mergeShim(file: str, xpath: str, idAttribute: str):
        '''Shim to reduce function call complexity'''
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
        "/data/Explosion": "id",               #
        "/data/Faction": "id",
        "/data/FloorExpPackage": "id",         #
        "/data/GameScenario": "id",            #
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
        "/data/Robot":"cid",                   #
        "/data/RoofExpPackage": "id",          #
        "/data/Room": "rid",
        "/data/Sector": "id",
        "/data/Ship": "rid",
        "/data/SubCat": "id",
        "/data/Tech": "id",                    #
        "/data/TechTree": "id",                #
        "/data/TradingValues": "id",
    }

    # Do an element-wise merge (replacing conflicts)
    currentFile = "library/haven"
    if currentFile in modLib:
        for path, idText in havenIDLookUpTable.items(): mergeShim(currentFile, path, idText)
    else: mergeAbortMessage(currentFile)

    currentFile = "library/texts"
    if currentFile in modLib:
        mergeShim(currentFile, "/t", idAttribute="id")
    else: mergeAbortMessage(currentFile)

    # do that before merging animations and textures because references might have to be remapped!
    coreLib['_all_modded_textures'].update(_detect_textures(coreLib, modLib, mod))

    # this way the last mod loaded will overwrite previous textures
    #FIXME reimplement this test
    #if region_id in all_modded_textures:
    #    ui.log.log("  ERROR CONFLICT {}...".format(filename))
    #    ui.log.log("  ERROR CONFLICT {}...".format(filename))
    #    ui.log.log("  ERROR CONFLICT {}...".format(filename))
    #    continue


    currentFile = "library/animations"
    if currentFile in modLib:
        mergeShim(currentFile, "/AllAnimations/animations", "n")
    else: mergeAbortMessage(currentFile)

    currentFile = "library/textures"
    if currentFile in modLib:
        mergeShim(currentFile, "/AllTexturesAndRegions/textures", "i")
        mergeShim(currentFile, "/AllTexturesAndRegions/regions", "n")
    else: mergeAbortMessage(currentFile)


def mergeDefinitions(baseLibrary, modLibrary, file, xpath, idAttribute):
    if not file in modLibrary:
        ui.log.log("    {}: Not present".format(file))
        return

    try:
        baseRoot = baseLibrary[file].xpath(xpath)[0]
    except IndexError:
        #that's a big error if we can't find it in the core!
        ui.log.log("    {}: ERROR CORE NOTHING AT {}".format(file, xpath))
        return

    for mod_xml in modLibrary[file]:
        try:
            modRoot = mod_xml.xpath(xpath)[0]
        except:
            continue

        merged = 0
        for element in list(modRoot):
            # TODO auto-id algo: if element.get(idAttribute + "_auto") then
            # id = prefix * idSpaceSize + id
            conflicts = baseRoot.xpath("*[@{}='{}']".format(idAttribute, element.get(idAttribute)))

            for conflict in conflicts:
                baseRoot.remove(conflict)

            baseRoot.append(copy.deepcopy(element))
            merged += 1

        if merged:
            # TODO add source filename
            ui.log.log("    {}: Merged {} elements into {}".format(file, merged, xpath))
