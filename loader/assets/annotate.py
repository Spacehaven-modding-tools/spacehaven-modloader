
import os
from xml.etree import ElementTree
from lxml.etree import XMLParser
import xmltodict

import ui.log

import csv


# Create the dictionary of tags and their keys.
# Creates the definition of the structure, doesn't read any files.
# Maybe this should be read from an XSD or other data file?
# This helps build a database-like view of XML later, and is very fast.
def __createDbKeyStructure():
    """Create the dictionary of tags and their keys.
    This builds a database-like view of SpaceHaven XML later, and is very fast.
    Some tags have multiple possible children, or children of children that have the real elements, which complicates matters.
    The ultimate structure will look something like:
        {
            __Filename__:"haven",
            __RootTag__:"data",
            Element:{me:"mid"},
            Product:{product:"eid"},
            Notes:{
                stuff:{
                    __id__:"id",
                    {notes:"id"}
                }
            }
            TechTree:[
                {items:{i:"tid"}},
                {
                    links:{
                        l:"",
                        __foreign__:{
                            fromId:["haven", "Tech"],
                            toId:["haven", "Tech"]
                        }
                    }
                }
            ]
        },
        {
            __Filename__:"texts",
            __RootTag__:"t",
            __all__:{EN:"__text__"}
        }
    """

    # Create the entry in a given dictionary.  Makes things easier to read.
    def __makeTagRef(container:dict,tag:str,child:any,attrib="",foreign={}):
        if container.get(tag) is None:
            container[tag] = {}
        container[tag][child] = attrib

    # Texts
    tagkeys={"__FileNameXml__":"texts"}
    __makeTagRef(tagkeys,"__all__","EN","__text__")


    # Textures
    tagkeys={"__FileNameXml__":"textures"}


    # Animations
    tagkeys={"__FileNameXml__":"animations"}



    # The Haven File, all nodes under root 'data'.
    tagkeys={"__FileNameXml__":"haven"}
    __makeTagRef(tagkeys,"Randomizer","randomizer","id")
    __makeTagRef(tagkeys,"GOAPAction","action","id")
    __makeTagRef(tagkeys,"BackPack","item","mid")
    __makeTagRef(tagkeys,"Element","me","mid")
    __makeTagRef(tagkeys,"Product","product","eid")
    __makeTagRef(tagkeys,"DataLogFragment","fragment","id")
    __makeTagRef(tagkeys,"RandomShip","ship","id")
    __makeTagRef(tagkeys,"FloorExpPackage","expPackage","id")
    __makeTagRef(tagkeys,"IsoFX","fx","id")
    __makeTagRef(tagkeys,"Item","item","mid")
    __makeTagRef(tagkeys,"Tech","tech","id")
    __makeTagRef(tagkeys,"GameScenario","game","id")
    __makeTagRef(tagkeys,"SubCat","cat","id")
    __makeTagRef(tagkeys,"Monster","monster","cid")
    __makeTagRef(tagkeys,"PersonalitySettings","settings","id")
    __makeTagRef(tagkeys,"Encounter","encounter","id")
    __makeTagRef(tagkeys,"CostGroup","group","id")
    __makeTagRef(tagkeys,"CharacterSet","characters","cid")
    __makeTagRef(tagkeys,"DifficultySettings","settings","id")
    __makeTagRef(tagkeys,"Room","data","rid")
    __makeTagRef(tagkeys,"ObjectiveCollection","collection","nid")

    # this one not very useful for two reasons:
    #   1) there are two id's, 'id' and 'idc'
    #   2) there is only one 'stuff' entry, which has many 'notes' children
    __makeTagRef(tagkeys,"Notes","stuff","id")

    __makeTagRef(tagkeys,"DialogChoice","choice","id")
    __makeTagRef(tagkeys,"Faction","faction","id")
    __makeTagRef(tagkeys,"CelestialObject","explosion","id")
    __makeTagRef(tagkeys,"Explosion","randomizer","id")
    __makeTagRef(tagkeys,"Character","character","cid")
    __makeTagRef(tagkeys,"Craft","craft","cid")
    __makeTagRef(tagkeys,"Sector","bg","id")
    __makeTagRef(tagkeys,"DataLog","dataLog","id")
    __makeTagRef(tagkeys,"Plan","plan","id")
    __makeTagRef(tagkeys,"BackStory","backstory","id")
    __makeTagRef(tagkeys,"DefaultStuff","stuff","id")

    # only has one 'trade' entry, which in turn has many 't' entries keyed 'eid'.
    __makeTagRef(tagkeys,"TradingValues","trade","id")

    __makeTagRef(tagkeys,"CharacterTrait","trait","id")
    __makeTagRef(tagkeys,"Effect","effect","id")
    __makeTagRef(tagkeys,"CharacterCondition","condition","id")
    __makeTagRef(tagkeys,"Ship","data","rid")
    __makeTagRef(tagkeys,"IdleAnim","an","id")
    __makeTagRef(tagkeys,"RoofExpPackage","expPackage","id")
    __makeTagRef(tagkeys,"MainCat","cat","id")

    # only has two entries, which have two children:
    #   1) 'items' with children 'i' with 'tid' as key
    #   2) 'links' with children 'l' with 'fromId' and 'toId' as keys
    __makeTagRef(tagkeys,"TechTree","tree","id")
    
    #Finally, have all root level keys for 'haven'.
    haven_keys = tagkeys

    print(haven_keys["__FileNameXml__"])

    return haven_keys

def annotate(corePath:str, language="EN", bOutputXML = True, bOutputCSV=True, bOutputDependencies=True, bOutputPythonTree=True, bOutputLuaTree=True, bOutputReports=True):
    """Generate an annotated Space Haven library"""

    # Root Key Lookup.
    keys = __createDbKeyStructure()

    # Parse a SpaceHaven XML file into an ElementTree
    def loadXML(filename):
        et = ElementTree.parse(os.path.join(corePath, "library", filename), parser=XMLParser(recover=True))
        return et

    # Save annotated XML at the end.
    def saveXML(e,filename,suffix="_annotated"):
        # path = os.path.join(corePath, "library", filename )
        name = os.path.join(corePath, filename + suffix + ".xml")
        t=type(e).__name__
        et = 0-1j

        if "_ElementTree" == t or "ElementTree" == t:
            et = e
        elif "_Element" == t or "Element" == t:
            et = ElementTree.ElementTree(e)
            #ElementTree.fromstring(ElementTree.tostring(e, 'utf-8')))
        elif "_String" == t or "String" == t:
            et = ElementTree.fromstring(e)
        else:
            ui.log.log("ERROR: Cannot write type '{}' as XML to '{}'.".format(t,name))
            return
        et.write(name)
        ui.log.log("  Wrote {}".format(name))

    # Optionally save CSV.
    def saveCSV(element_or_tree:ElementTree or Element or _Element or RootElement, filename:str, fieldnames:list,suffix="_annotated"):
        name = os.path.join(corePath, filename + suffix + ".csv")
        root=element_or_tree
        if type(element_or_tree).__name__ in ["ElementTree","_ElementTree"]:
            root = element_or_tree.getroot()
        with open(name, 'w', encoding='UTF8', newline='' ) as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';', quotechar='"', quoting=csv.QUOTE_ALL)
            writer.writeheader()
            for e in root:
                row = {}
                for field in fieldnames:
                    s:str
                    s = e.get(field) or ""
                    row[field] = s
                writer.writerow(row)
        ui.log.log("  Wrote {}".format(name))
        return name

    # Optionally save Python dictionary of the XML.
    def savePython(root, filename, suffix="_annotated" ):
        name = os.path.join(corePath, filename + suffix + ".py" )
        # e:ElementTree.Element
        #if type(root) in ["ElementTree","_ElementTree"]:
        #    e = root.getroot()
        d = xmltodict.parse( ElementTree.tostring(root) )

        with open(name, 'w', encoding='UTF8' ) as f:
            f.write('{} = [{}]'.format(e.tag,d))

        ui.log.log("  Wrote {}".format(name))


    # Optionally save runnable Lua of the XML.
    # This is done by making each tag a function call passed a list.
    # The named part of the Lua gets the attributes, the numeric part gets all children, including text, in order.
    def saveLua(root, filename, fieldnames ):
        print("foo")



    # Load XML files
    ui.log.log("  Loading haven XML...")
    havenxml = loadXML("haven")


    # 
    saveXML(havenxml,"haven")
    saveCSV(havenxml.find("GameScenario"),"haven_GameScenario")
    savePython(havenxml,"haven")


    ui.log.log("  Loading textures XML...")
    texturexml = loadXML("textures")

    ui.log.log("  Loading animations XML...")
    animationxml = loadXML("animations")

    ui.log.log("  Loading texts XML...")
    textsxml = loadXML("texts")


    ''' TODO:
    Maybe support the following for reporting:
        File            Root Element            Tag        
        gp              GenNParticles           (unique) have key 'id'
        gfiles          files                   (unique) have key 'id'
        textures        AllTexturesAndRegions   'textures' with 't' have key 'i'
                                                'regions' with 're' have key 'id'
        animations      AllAnimations           one 'animations' with 'ba' have keys string 'n' and int 'id'
        fonts           f                       (unique) have key 'id'
    '''


    # Annotate Textures.
    ui.log.log("  Processing textures and animations...")
    for region in texturexml.findall(".//re[@n]"):
        if not region.get("_annotation"):
            continue
        texture_names[region.get('n')] = region.get("_annotation")
    

    # Annotate Animations.
    for assetPos in animations.findall('.//assetPos[@a]'):
        asset_id = assetPos.get('a')
        if not asset_id in texture_names:
            continue
        assetPos.set('_annotation', texture_names[asset_id])

    
    # Create table of text IDs for rapid lookup later.
    tids = {}
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

        tid = e.get("tid")        

        # Make one last chance to search for name elsewhere
        if tid is None:
            tid = e.get("name")

        if tid is None:
            return ""

        if tids[tid] is None:
            return ""

        return tids[tid]


    # Avoid fragmenting memory.
    # this probably isn't strictly needed, but it reduces memory useage for me with no noticable lag.
    gc.collect()


    n=64
    v=2
    print(n)
    while n>0:
        v=v^2
        n=n-1
    print(n)
    print(v)


    ui.log.log("  Process haven data Element...")
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
