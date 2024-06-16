
import os
from xml.etree import ElementTree

import ui.log

from loader.assets.utils import create_xml_parser


def annotate(corePath):
    """Generate an annotated Space Haven library"""


    # NOTE: textures and animations do not seem to get annotated.  Should this be replaced?  WP would like to use these to make additional annotations in `haven`.
    texture_names = {}
    local_texture_names = ElementTree.parse("textures_annotations.xml", parser=create_xml_parser())
    for region in local_texture_names.findall(".//re[@n]"):
        if not region.get("_annotation"):
            continue
        texture_names[region.get('n')] = region.get("_annotation")
    
    animations = ElementTree.parse(os.path.join(corePath, "library", "animations"), parser=create_xml_parser())
    for assetPos in animations.findall('.//assetPos[@a]'):
        asset_id = assetPos.get('a')
        if not asset_id in texture_names:
            continue
        assetPos.set('_annotation', texture_names[asset_id])
    
    annotatedPath = os.path.join(corePath, "library", "animations_annotated.xml")
    animations.write(annotatedPath)
    ui.log.log("  Wrote annotated annimations to {}".format(annotatedPath))
    
    haven = ElementTree.parse(os.path.join(corePath, "library", "haven"), parser=create_xml_parser())
    texts = ElementTree.parse(os.path.join(corePath, "library", "texts"), parser=create_xml_parser())

    tids = {}
    # Load texts
    for text in texts.getroot():
        tids[text.get("id")] = text.find("EN").text
    
    def nameOf(element):
        name = element.find("name")
        if name is None:
            return ""

        tid = name.get("tid")
        if tid is None:
            return ""

        return tids[tid]


    ##############################################################################################
    # Recurse EVERY element in the entire haven file, trying to find the name and set the 
    # annotation where it's obvious.  This is only a first pass, but covers all of these tags:
	#	Product/product
	#	Item/item
	#	Tech/tech
	#	GameScenario/game
	#	SubCat/cat
	#	PersonalitySettings/attributes/l
	#	DifficultySettings/settings
	#	Faction/faction
	#	Craft/craft
	#	DataLog/dataLog
	#	BackStory/backstory
	#	CharacterTrait/trait
	#	CharacterCondition/condition
	#	MainCat/cat
    # Later, tags that need special treatment will get it.
    ui.log.log("  Process haven data for names...")
    # Annotate every XML element where the name is obvious.
    for e in haven.iter():
        # giving annotations to these tags would be redundant or spammy.
        if e.tag in ["name","desc","objectInfo","text"]:
            continue
        name = nameOf(e)
        if name:
            e.set("_annotation", name)

    # Write the partially annotated haven file, in case something goes wrong later.
    annotatedHavenPath = os.path.join(corePath, "library", "haven_annotated.xml")
    haven.write(annotatedHavenPath)


    ##############################################################################################
    # Special treatment begins here.
    # Annotate Elements and create list of links.
    ui.log.log("  annotate Element...")
    ElementRoot = haven.find("Element")
    ElementName = {}
    ElementLink = {}
    for element in ElementRoot:
        mid = element.get("mid")
        objectInfo = element.find("objectInfo")
        if objectInfo is not None:
            element.set("_annotation", nameOf(objectInfo))
            ElementName[mid] = element.get("_annotation")
        # Keep track of links, inverted.
        linked = element.find("linked")
        for link in linked.findall("l"):
            linkid = link.get("id")
            if linkid is not None and linkid not in ElementLink:
                ElementLink[linkid] = []
            if mid not in ElementLink[linkid]:
                ElementLink[linkid].append(mid)

    # Element Second pass, give linked-by reference list.
    for element in ElementRoot:
        mid = element.get("mid")
        if mid in ElementLink:
            links = (
                (link + " " + ElementName[link]) if link in ElementName else link
                for link in ElementLink[mid]
            )
            s = "; ".join(links)
            element.set("_linkedBy", s)

    # Annotate basic products
    # first pass also builds the names cache
    # NOTE: Maybe this can be refactored, since these already have _annotation.
    elementNames = {}
    ProductRoot = haven.find("Product")
    for element in ProductRoot:
        name = nameOf(element) or element.get("elementType") or ""
        
        if name:
            element.set("_annotation", name)
        elementNames[element.get("eid")] = name
    
    for item in haven.find("Item"):
        name = nameOf(item) or item.get("elementType") or ""
        
        if name:
            item.set("_annotation", name)
        elementNames[item.get("mid")] = name
    
    # small helper to annotate a node
    def _annotate_elt(element, attr = None):
        if attr:
            name = elementNames[element.get(attr)]
        else:
            name = elementNames[element.get("element", element.get("elementId"))]
        if name:
            element.set("_annotation", name)
        return name
    
    # construction blocks for the build menu
    for me in ElementRoot:
        for customPrice in me.findall(".//customPrice"):
            for sub_l in customPrice:
                _annotate_elt(sub_l)
    
    # Annotate facility processes, now that we know the names of all the products involved
    for element in ProductRoot:
        processName = []
        for need in element.xpath("needs/l"):
            name = _annotate_elt(need)
            processName.append(name)
        
        processName.append("to")
        
        for product in element.xpath("products/l"):
            name = _annotate_elt(product)
            processName.append(name)
        
        if len(processName) > 2 and not element.get("_annotation"):
            processName = " ".join(processName)
            elementNames[element.get("eid")] = processName
            element.set("_annotation", processName)
    
    #generic rule should work for all remaining nodes ?
    for sub_element in haven.findall(".//*[@consumeEvery]"):
        try:
            _annotate_elt(sub_element)
        except:
            pass
            # error on 446, weird stuff
            #print(sub_element.tag)
            #print(sub_element.attrib)
    
    # iterate again once we have built all the process names
    for process in ProductRoot.xpath('.//list/processes/l[@process]'):
        process.set("_annotation", elementNames[process.get("process")])
    
    for trade in haven.find('TradingValues').findall('.//t'):
        try:
            _annotate_elt(trade, attr = 'eid')
        except:
            pass
    
    # NOTE: Maybe this can be refactored
    # Annotations for other critial sections.
    ui.log.log("  annotate DifficultySettings...")
    DifficultySettings = haven.find('DifficultySettings')
    for settings in DifficultySettings:
        name = nameOf(settings)
        
        if name:
            settings.set("_annotation", name)
    
    for res in DifficultySettings.xpath('.//l'):
        try:
            _annotate_elt(res, attr = 'elementId')
        except:
            pass
        
    for res in DifficultySettings.xpath('.//rules/r'):
        try:
            _annotate_elt(res, attr = 'cat')
        except:
            pass
    


    # NOTE: Maybe this can be refactored, since these already have _annotation.
    ui.log.log("  annotate Tech...")
    TechRoot = haven.find("Tech")
    TechName = {}
    for tech in TechRoot:
        id = tech.get("id")
        name = tech.find("name")
        if name is not None:
            tech.set("_annotation", nameOf(tech))
            TechName[id] = tech.get("_annotation")

    ui.log.log("  annotate TechTree...")
    TechTreeRoot = haven.find("TechTree")
    for techtree in TechTreeRoot:
        techtreeid = techtree.get("id")
        for techitem in techtree.find("items"):
            id = techitem.get("tid")
            if TechName[id] is not None:
                techitem.set("_annotation", TechName[id])
        for techlink in techtree.find("links"):
            fromId = techlink.get("fromId")
            toId = techlink.get("toId")
            if TechName[fromId] is not None:
                techlink.set("_fromName", TechName[fromId])
            if TechName[toId] is not None:
                techlink.set("_toName", TechName[toId])


    # NOTE: Maybe this can be refactored or removed, since these already have _annotation.
    ui.log.log("  annotate MainCat...")
    MainCatRoot = haven.find("MainCat")
    MainCatName = {}
    for cat in MainCatRoot:
        id = cat.get("id")
        name = cat.find("name")
        if name is not None:
            cat.set("_annotation", nameOf(cat))
            MainCatName[id] = cat.get("_annotation")


    # NOTE: maybe refactor to only use the tags for the annotation, as the path is always the same and a bit verbose.
    ui.log.log("  annotate DataLogFragment...")
    # First get gfile names.
    gfiles = ElementTree.parse(os.path.join(corePath, "library", "gfiles"), parser=create_xml_parser())
    gfilename = {}
    for f in gfiles.getroot():
        id = f.get("id")
        path = f.get("path")
        if id is not None:
            gfilename[id] = path
    # now Annotate DataLogFragment with file paths and names.
    DataLogFragmentRoot = haven.find("DataLogFragment")
    for fragment in DataLogFragmentRoot:
        id = fragment.get("id")
        languages = fragment.find("languages")
        if languages is not None:
            for l in languages.findall('l'):
                lang = l.get("lang")
                f = l.find("file")
                if f is not None:
                    fid=f.get("fid")
                    if fid is not None and gfilename[fid] is not None:
                      l.set("_annotation", gfilename[fid])
                      if lang=="EN":
                          fragment.set("_annotation", gfilename[fid])


    annotatedHavenPath = os.path.join(corePath, "library", "haven_annotated.xml")
    haven.write(annotatedHavenPath)
    ui.log.log("  Wrote annotated spacehaven library to {}".format(annotatedHavenPath))
