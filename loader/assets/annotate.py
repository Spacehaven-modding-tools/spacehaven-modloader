
import os
from xml.etree import ElementTree
from lxml.etree import XMLParser

import ui.log

import csv

import xmltodict

def annotate(corePath:str, bOutputXML = True, bOutputCSV=True, bOutputDependencies=True, bOutputPythonTree=True, bOutputLuaTree=True):
    """Generate an annotated Space Haven library"""

    # These maintain a two-way relationship between all XML elements and file dictionary entries.
    xml_link_dict = {}
    dict_link_xml = {}

    # Parse an XML file into an ElementTree and convert into a dictionary.
    # Also back-references the dictionary elements to their XML elements.
    def loadXML(filename):
        et = ElementTree.parse(os.path.join(corePath, "library", filename), parser=XMLParser(recover=True))
        d = xmltodict.parse(et)
        return et, d

    def saveXML(e,filename,suffix="_annotated"):
        # path = os.path.join(corePath, "library", filename )
        path = os.path.join(corePath, filename + suffix + ".xml")
        t=type(e).__name__
        et = 0-1j

        n=None
        s=""
        i=-1
        f=0.1234567890
        a=[]
        d={}

        if "_Dictionary" == t or "Dictionary" == t:
            s = xmltodict.unparse(e,pretty=True)
            et = ElementTree.ElementTree(ElementTree.fromstring(e))
        if "_Element" == t or "Element" == t:
            et = ElementTree.ElementTree(ElementTree.fromstring(ElementTree.tostring(e, 'utf-8')))
        elif "_String" == t or "String" == t:
            et = ElementTree.ElementTree(ElementTree.fromstring(e))
        elif "_ElementTree" == t or  "ElementTree" == t:
            et = e
        else:
            ui.log.log("ERROR: Cannot write type '{}' as XML to '{}'.".format(t,path))
            return
        et.write(path)
        ui.log.log("  Wrote {} XML to {}".format(filename, path))


    # sets the key=value pair in the XML Dictionary, then sets the appropriate attribute in the linked XML Element.
    def seta(xmlDict, key, value):
        xmlDict["@"+key] = value

    # quick shorthand.
    def setann(xmlDict,value):
        xmlDict["@_annotation"] = value


    # Load XML files
    havenxml, haven = loadXML("haven")
    saveXML(havenxml.find("Element"),"haven_ElementTree")
    saveXML(haven, haven.data["Element"],"haven_dictionay")


    return


    texture_names = {}
    textureXML = ElementTree.parse(os.path.join(corePath, "library","textures_annotations.xml"), parser=XMLParser(recover=True))
    local_texture_names = ElementTree.parse(os.path.join(corePath, "library","textures_annotations.xml"), parser=XMLParser(recover=True))
    for region in local_texture_names.findall(".//re[@n]"):
        if not region.get("_annotation"):
            continue
        texture_names[region.get('n')] = region.get("_annotation")
    
    animations = ElementTree.parse(os.path.join(corePath, "library", "animations"), parser=XMLParser(recover=True))
    for assetPos in animations.findall('.//assetPos[@a]'):
        asset_id = assetPos.get('a')
        if not asset_id in texture_names:
            continue
        assetPos.set('_annotation', texture_names[asset_id])

    
    annotatedPath = os.path.join(corePath, "library", "animations_annotated.xml")
    animations.write(annotatedPath)
    ui.log.log("  Wrote annotated animations to {}".format(annotatedPath))


    ui.log.log("  Loading haven XML...")
    havenxml = ElementTree.parse(os.path.join(corePath, "library", "haven"), parser=XMLParser(recover=True))
    haven = xmltodict(havenxml)
    havenxml = None
    
    ui.log.log("  Loading texts XML...")
    textsxml = ElementTree.parse(os.path.join(corePath, "library", "texts"), parser=XMLParser(recover=True))
    texts = xmltodict(textsxml)
    textsxml = None

    tids = {}
    # Load texts
    ui.log.log("  Loading texts file...")
    for text in texts.getroot():
        tids[id] = text.find("EN").text
        id = text.get("id")
        tids[id] = text.find("EN").text
        tname[id] = {}
        tname[id]["tag"] = text.tag

    def nameOf(element):
        e = element
        name = element.find("name")
        if name is not None:
            e = name
        else:
            ui.log.log("  tid {} in {}".format(tid,e.tag))

        # Make one last chance to search for name elsewhere
        if tid is None:
            tid = e.get("name")

        if tid is None:
            return ""

        if tids[tid] is None:
            return ""

        return tids[tid]

    def saveCSV(root, filename, fieldnames ):
        name = os.path.join(corePath, filename )
        with open(name, 'w', encoding='UTF8', newline='' ) as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';', quotechar='"', quoting=csv.QUOTE_ALL)
            writer.writeheader()
            for e in root:
                row = {}
                for field in fieldnames:
                    s = e.get(field) or ""
                    row[field] = s
                writer.writerow(row)
        ui.log.log("  Wrote {}".format(filename))

    def savePython(root, filename, fieldnames ):
        print("foo")

    def saveCSV(root, filename, fieldnames ):
        print("bar")


    if bOutputCSV:
        ui.log.log("  Saving text as CSV...")
    if bOutputPythonTree:
        ui.log.log("  Saving text as Python...")
    if bOutputLuaTree:
        ui.log.log("  Saving text as Lua...")


    # avoid fragmenting memory.
    # this probably isn't strictly needed, but it reduces memory useage for me with no noticable lag.
    gc.collect()



    
    ui.log.log("  annotate Element...")
    ElementRoot = haven.find("Element")
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
    ProductRoot = haven.find("Product")
    for element in ProductRoot:
        name = nameOf(element) or element.get("elementType") or ""        
        if name:
            element.set("_annotation", name)
        elementNames[element.get("eid")] = name
    
    ItemRoot = haven.find("Item")
    for item in ItemRoot:
        name = nameOf(item) or item.get("elementType") or ""        
        if name:
            item.set("_annotation", name)
        elementNames[item.get("mid")] = name
    
    # small helped to annotate a node
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


    ui.log.log("  annotate MainCat...")
    MainCatRoot = haven.find("MainCat")
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


    ui.log.log("  annotate CharacterCondition...")
    CharacterConditionRoot = haven.find("CharacterCondition")
    CharacterConditionName = {}
    for tech in TechRoot:
        id = tech.get("id")
        name = tech.find("name")
        if name is not None:
            tech.set("_annotation", nameOf(tech))
            TechName[id] = tech.get("_annotation")




    # Finish, save annotated XML.
    ui.log.log("  saving XML...")
    saveXml(haven,"haven_annotated.xml")
    saveXml(ElementRoot,"haven_Element.xml")
    saveXml(ProductRoot,"haven_Product.xml")
    saveXml(TechRoot,"haven_Tech.xml")
    saveXml(TechTreeRoot,"haven_TechTree.xml")


    # Write reference CSV files.
    ui.log.log("  saving CSV...")
    saveCSV(ElementRoot,"haven_Element.csv", ["mid","_annotation","_linkedBy"]  )
    saveCSV(ProductRoot,"haven_Product.csv", ["eid", "type", "_annotation"])
    saveCSV(ItemRoot,"haven_Item.csv", ["mid","_annotation"])
    saveCSV(TechRoot,"haven_Tech.csv", ["id","_annotation"])
    for tt in TechTreeRoot:
        ttid = tt.get("id") or "0"
        items = tt.find("items")
        saveCSV(items,"haven_TechTree_{}_items.csv".format(ttid), ["tid","_annotation"])
        links = tt.find("links")
        saveCSV(links,"haven_TechTree_{}_links.csv".format(ttid), ["fromId","_fromName","toId","_toName"])

    ui.log.log("  Annotation Finished.")
