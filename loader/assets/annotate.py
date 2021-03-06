
import os
import gc
from xml.etree import ElementTree
from lxml.etree import XMLParser
import xmltodict

import ui.log

import csv



# Different outputs are not supported yet.  They're here to remind me of what I'm doing next.
# The bOutputEarlyAndOften parameter save the XML immediately after loading it, for debugging.
# Verbose gives more status feedback.
def annotate(corePath:str, language:str="EN", bVerbose=False, bOutputEarlyAndOften:bool=False, bOutputXML:bool = True, bOutputCSV:bool=False, bOutputPythonTree:bool=False ):
    """Generate an annotated Space Haven library"""


    ##############################################################################################
    # Internal use function definitions.
    ##############################################################################################

    def Verbose(*args):
        if bVerbose:
            return ui.log.log(*args)

    # Parse a SpaceHaven XML file into an ElementTree
    def loadXML(filename:str):
        et = ElementTree.parse(os.path.join(corePath, "library", filename), parser=XMLParser(recover=True))
        return et

    def makeXmlElementFromThisThing(thing:any):
        e = 0-1j
        t = type(thing).__name__
        if t in ["_Element","Element","_RootElement","RootElement"]:
            e=thing
        if t in ["_ElementTree","ElementTree"]:
            e=thing.getroot()
        elif thing is str or t in ["_String" ,"String"]:
            e=ElementTree.fromstring(e).getroot()
        elif thing is dict or t in ["_Dictionary" ,"Dictionary"]:
            e=ElementTree.fromstring( xmltodict.unparse(thing) ).getroot()
        else:
            ui.log.log("ERROR: Cannot convert type '{}' to XML Element !",t)
            return None
        
        return e

    def makeXmlElementTreeFromThisThing(thing:any):
        t = type(thing).__name__
        et = 0-1j
        if t in ["_ElementTree","ElementTree"]:
            et=thing
        elif t in ["_Element","Element","_RootElement","RootElement"]:
            et=ElementTree.ElementTree(thing)
        elif thing is str or t in ["_String" ,"String"]:
            et=ElementTree.fromstring(e)
        elif thing is dict or t in ["_Dictionary" ,"Dictionary"]:
            et=ElementTree.fromstring( xmltodict.unparse(thing) )
        else:
            ui.log.log("ERROR: Cannot convert type '{}' to XML ElementTree !",t)
            return None
        
        return et


    # Output XML.
    def saveXML(element_or_tree:dict or ElementTree or Element or _Element or RootElement,name:str, suffix:str="",prefix:str=""):
        # path = os.path.join(corePath, "library", filename )
        name = os.path.join(corePath, prefix + name + suffix + ".xml")
        et = makeXmlElementTreeFromThisThing(element_or_tree)
        et.write(name)
        ui.log.log("  Wrote {}".format(name))

    # Save Python dictionary of the XML.
    def savePython(element_or_tree:dict or ElementTree or Element or _Element or RootElement, name:str, suffix:str="", prefix:str=""):
        t = type(element_or_tree).__name__
        root = makeXmlElementFromThisThing(element_or_tree)
        name = os.path.join(corePath, prefix + name + suffix + ".csv")
        d = xmltodict.parse( ElementTree.tostring(root) )

        # TODO: pretty printer.
        with open(name, 'w', encoding='UTF8' ) as f:
            f.write('{} = [{}]'.format(root.tag,d))

        ui.log.log("  Wrote {}".format(name))

    # TODO: I need to finish this and make it actually work!
    # Optionally save CSV.
    # Unlike the other functions, this only saves the direct children of the passed 
    def saveCSV(element_or_tree:dict or ElementTree or Element or _Element or RootElement, attribs:list):
        root=element_or_tree
        t = type(element_or_tree).__name__
        if t in ["ElementTree","_ElementTree"]:
            root = element_or_tree.getroot()
        name = os.path.join(corePath, prefix + root.tag + suffix + ".csv")
        with open(name, 'w', encoding='UTF8', newline='' ) as f:
            writer = csv.DictWriter(f, fieldnames=attribs, delimiter=';', quotechar='"', quoting=csv.QUOTE_ALL)
            writer.writeheader()
            for e in root:
                row = {}
                for field in attribs:
                    s:str
                    s = e.get(field) or ""
                    row[field] = s
                writer.writerow(row)
        ui.log.log("  Wrote {}".format(name))
        return name

    # Saves in every enabled format.
    def saveMulti(element_or_tree:dict or _ElementTree or ElementTree or Element or _Element or RootElement, name:str, suffix:str="", prefix:str=""):
        if bOutputXML:
            saveXML(element_or_tree, name, suffix, prefix)

    # Used for debugging.
    def maybeSaveAll(element_or_elementtree:dict or _ElementTree or ElementTree or Element or _Element or RootElement, name:str, suffix:str="", prefix:str=""):
        if bOutputEarlyAndOften: 
            return saveMulti(element_or_elementtree,name,suffix,prefix)


    ##############################################################################################
    # Load XML files, from quickest/smallest to slowest/largest.
    # All of them are kept in memory so that the relationships can be built later.
    ##############################################################################################


    # root 'f'.  Unique tags, key attrib 'id'
    ui.log.log("  Loading fonts XML...")
    fontsxml = loadXML("fonts")
    maybeSaveAll(fontsxml,"fonts")

    # root 'files'.  Unique tags, key attrib 'id'
    ui.log.log("  Loading gfiles XML...")
    gfilesxml = loadXML("gfiles")
    maybeSaveAll(gfilesxml,"gfiles")

    # root 'AllTexturesAndRegions'.  'textures' tag with 't' tag has key 'i' and 'regions' tag with 're' tag has key 'id' and foreign key '' to the 'textures' section.
    ui.log.log("  Loading texture regions and textures XML...")
    texturesxml = loadXML("textures")
    maybeSaveAll(fontsxml,"textures")

    # root 'AllAnimations'.  'ba' tag has keys string 'n' and int 'id', both unique.  Also has foreign key 'tid' references 're' in textures file.
    ui.log.log("  Loading animations XML...")
    animationsxml = loadXML("animations")
    maybeSaveAll(animationsxml,"animations")

    # root 'GenNParticles'.  Unique tags, key attrib 'id'
    ui.log.log("  Loading GenNParticles gp XML...")
    gpxml = loadXML("gp")
    maybeSaveAll(gpxml,"gp")

    # root 't'.  Unique tags, key on 
    ui.log.log("  Loading texts XML...")
    textsxml = loadXML("texts")
    maybeSaveAll(textsxml,"texts")

    # root 'data'.  Most of the game data.  Many sections, some with multiple possible child tags.
    ui.log.log("  Loading haven XML...")
    havenxml = loadXML("haven")
    maybeSaveAll(havenxml,"haven")

    ##############################################################################################
    # Process XML files
    ##############################################################################################

    ui.log.log("  Processing text...")

    # Create table of text IDs for rapid lookup later.
    tids = {}   # quick lookup dictionary.
    tname = {}  # detailed dictionary.
    tname["COLLISION"] = {"tag":"COLLISION", "text":"COLLISION"}
    for text in textsxml.getroot():
        id = text.get("id")
        tids[id] = text.find(language).text
        tname[id] = {}
        tname[id]["tag"] = text.tag             # Text entries have mostly (but not always) unique tags.
        tname[id]["text"] = tids[id]            # The text used above, based on settings.
        for child in text:
            tname[id][child.tag] = child.text   # All language text can be referenced explicitly.
        if tname.get(text.tag) is None:
            tname[text.tag] = tname[id]
        else:
            tname[text.tag] = tname["COLLISION"]


    # Try hard to find a name for typical elements that have a name.
    # The game always does this with a child tag instead of an attribute, for some reason.
    # More attempts are made later, depending on element type.
    def nameOf(element:ElementTree.Element or ElementTree._Element_Py):
        e = element
        name = element.find("name")
        if name is not None:
            e = name

        tid = e.get("tid")

        if tid is None:
            return ""

        if tids.get(tid) is None:
            return ""

        return tids[tid]


    # Recurse EVERY element in the entire haven file, trying to find the name and set the annotation where it's obvious.
    # This is only a first pass.
    ui.log.log("  Process haven data for names...")
    # Annotate every XML element where the name is obvious.
    for e in havenxml.iter():
        name = nameOf(e)
        if "" != name:
            e.set("_annotation", nameOf(e))

    # Annotate Textures.
    texture_names = {}
    ui.log.log("  Processing textures and animations...")
    for region in texturesxml.findall(".//re[@n]"):
        if not region.get("_annotation"):
            continue
        texture_names[region.get('n')] = region.get("_annotation")


    # Annotate Animations.
    for assetPos in animationsxml.findall('.//assetPos[@a]'):
        asset_id = assetPos.get('a')
        if not asset_id in texture_names:
            continue
        assetPos.set('_annotation', texture_names[asset_id])

    


    # Avoid fragmenting memory.
    # this probably isn't strictly needed.
    gc.collect()




    ElementRoot = havenxml.find("Element")
    ElementName = {}
    ElementLink = {}
    # Annotate Elements and create list of links.
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

    # Second pass, give linked-by reference list.
    for element in ElementRoot:
        mid = element.get("mid")
        if mid in ElementLink:
            s=""
            for link in ElementLink[mid]:
                s = s + link
                if link in ElementName:
                    s = s + " " + ElementName[link]
                s = s + ";"
            element.set("_linkedBy", s)


    # Annotate basic products
    # first pass also builds the names cache
    ui.log.log("  annotate Product...")
    elementNames = {}
    ProductRoot = havenxml.find("Product")
    for element in ProductRoot:
        name = nameOf(element) or element.get("elementType") or ""        
        if name:
            element.set("_annotation", name)
        elementNames[element.get("eid")] = name
    
    ItemRoot = havenxml.find("Item")
    for item in ItemRoot:
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
    for sub_element in havenxml.findall(".//*[@consumeEvery]"):
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
    
    for trade in havenxml.find('TradingValues').findall('.//t'):
        try:
            _annotate_elt(trade, attr = 'eid')
        except:
            pass
    


    ui.log.log("  annotate DifficultySettings...")
    DifficultySettings = havenxml.find('DifficultySettings')
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
    


    ui.log.log("  annotate Tech...")
    TechRoot = havenxml.find("Tech")
    TechName = {}
    for tech in TechRoot:
        id = tech.get("id")
        name = tech.find("name")
        if name is not None:
            tech.set("_annotation", nameOf(tech))
            TechName[id] = tech.get("_annotation")

    ui.log.log("  annotate TechTree...")
    TechTreeRoot = havenxml.find("TechTree")
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


    ui.log.log("  annotate MainCat...")
    MainCatRoot = havenxml.find("MainCat")
    MainCatName = {}
    for cat in MainCatRoot:
        id = cat.get("id")
        name = cat.find("name")
        if name is not None:
            cat.set("_annotation", nameOf(cat))
            MainCatName[id] = cat.get("_annotation")



    ui.log.log("  annotate DataLogFragment...")
    # First get gfile names.
    gfiles = ElementTree.parse(os.path.join(corePath, "library", "gfiles"), parser=XMLParser(recover=True))
    gfilename = {}
    for f in gfiles.getroot():
        id = f.get("id")
        path = f.get("path")
        if id is not None:
            gfilename[id] = path
    # now Annotate DataLogFragment with file paths and names.
    DataLogFragmentRoot = havenxml.find("DataLogFragment")
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


    ui.log.log("  annotate CharacterCondition...")
    CharacterConditionRoot = havenxml.find("CharacterCondition")
    CharacterConditionName = {}
    for tech in TechRoot:
        id = tech.get("id")
        name = tech.find("name")
        if name is not None:
            tech.set("_annotation", nameOf(tech))
            TechName[id] = tech.get("_annotation")



    ##############################################################################################
    # Finish, save annotated XML.
    ##############################################################################################
    ui.log.log("  Saving Annotated Files...")
    saveMulti(fontsxml,"fonts","_annotated" )
    saveMulti(gfilesxml,"gfiles","_annotated" )
    saveMulti(texturesxml,"textures","_annotated" )
    saveMulti(animationsxml,"animations","_annotated" )
    saveMulti(gpxml,"gp","_annotated" )
    saveMulti(textsxml,"texts","_annotated" )
    saveMulti(havenxml,"haven","_annotated" )

    #Every section of haven individually
    for section in havenxml.getroot():
        saveMulti(section,section.tag,"_annotated", "haven_" )

    ui.log.log("  Annotation Finished.")
