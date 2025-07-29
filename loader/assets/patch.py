import copy

import lxml.etree
import ui.log


def AttributeSet(patchArgs):
    """Set the attribute on the node, adding if not present"""
    elem : lxml.etree._Element
    currentCoreLibElems = patchArgs["coreLibElems"]
    attribute = patchArgs["attribute"].text
    value = patchArgs["value"]
    for elem in currentCoreLibElems: elem.set(attribute, value.text)


def AttributeAdd(patchArgs):
    """Adds the attribute to the node IFF the attribute name is not already present"""
    elem : lxml.etree._Element
    currentCoreLibElems = patchArgs["coreLibElems"]
    attribute = patchArgs["attribute"].text
    value = patchArgs["value"]

    for elem in currentCoreLibElems:
        if elem.get(attribute, None) is not None:
            raise KeyError(f"Attribute '{attribute}' already exists")
        elem.set(attribute, value.text)


def AttributeRemove(patchArgs):
    """Remove the attribute from the node"""
    ui.log.log(f"    WARNING: REMOVING ATTRIBUTES MAY BREAK THE GAME")
    elem : lxml.etree._Element
    currentCoreLibElems = patchArgs["coreLibElems"]
    attribute = patchArgs["attribute"].text
    for elem in currentCoreLibElems: elem.attrib.pop(attribute)


def AttributeMath(patchArgs):
    """Set the attribute on the node, via math"""
    elem : lxml.etree._Element
    currentCoreLibElems = patchArgs["coreLibElems"]
    attribute = patchArgs["attribute"].text
    value = patchArgs["value"]
    opType = value.get("opType", None)
    valueFloat = float(value.text)
    for elem in currentCoreLibElems:
        startVal = float(elem.get(attribute, 0))
        isFloat = "." in elem.get(attribute, 0)
        if opType == "add":
            newVal = startVal + valueFloat
        elif opType == "subtract":
            newVal = startVal - valueFloat
        elif opType == "multiply":
            newVal = startVal * valueFloat
        elif opType == "divide":
            newVal = startVal / valueFloat
        else:
            raise AttributeError("Unknown opType")

        if isFloat:
            elem.set(attribute, f"{newVal:.1f}")
        else:
            newVal = int(newVal)
            elem.set(attribute, f"{newVal}")


def NodeAdd(patchArgs):
    """Adds a provided child node to the selected node"""
    elem : lxml.etree._Element
    parent: lxml.etree._Element
    currentCoreLibElems = patchArgs["coreLibElems"]
    value = patchArgs["value"]
    for elem in currentCoreLibElems:
        lastElemIDX = len(elem.getchildren())
        for node in value:
            lastElemIDX += 1
            elem.insert(lastElemIDX, copy.deepcopy(node))


def NodeInsert(patchArgs):
    """Adds a provided sibling node to the selected node"""
    elem : lxml.etree._Element
    parent: lxml.etree._Element
    currentCoreLibElems = patchArgs["coreLibElems"]
    value = patchArgs["value"]
    for elem in currentCoreLibElems:
        parent = elem.find('./..')
        elemIDX = parent.index(elem)
        for node in value:
            elemIDX += 1
            parent.insert(elemIDX, copy.deepcopy(node))


def NodeRemove(patchArgs):
    """Deletes the selected node"""
    elem : lxml.etree._Element
    parent: lxml.etree._Element
    currentCoreLibElems = patchArgs["coreLibElems"]
    for elem in currentCoreLibElems:
        parent = elem.find('./..')
        parent.remove(elem)


def NodeReplace(patchArgs):
    """Replaces the selected node with the provided node"""
    elem : lxml.etree._Element
    parent: lxml.etree._Element
    currentCoreLibElems = patchArgs["coreLibElems"]
    value = patchArgs["value"]
    for elem in currentCoreLibElems:
        parent = elem.find('./..')
        parent.replace(elem, copy.deepcopy(value[0]))


# Default case function
def BadOp(patchArgs):
    raise SyntaxError(f"BAD PATCH OPERATION")


patchDispatcher = {
    "AttributeSet" :    AttributeSet,
    "AttributeAdd" :    AttributeAdd,
    "AttributeRemove" : AttributeRemove,
    "AttributeMath" :   AttributeMath,
    "Add":              NodeAdd,
    "Insert":           NodeInsert,
    "Remove":           NodeRemove,
    "Replace":          NodeReplace,
}
def PatchDispatch(pType):
    """Return the correct PatchOperation function"""
    return patchDispatcher.get(pType,BadOp)

def doPatches(coreLib, modLib, mod:dict):

    # Helper function
    def doPatchType(patch: lxml.etree._Element, location: str):
        """Execute a single patch. Provided to reduce indentation level"""
        pType =  patch.attrib["Class"]
        xpath = patch.find('xpath').text
        currentCoreLibElems = coreLib[location].xpath(xpath)

        ui.log.log(f"    XPATH => {location:>15}: {pType:18}{xpath}")
        if len(currentCoreLibElems) == 0:
            ui.log.log(f"    Unable to perform patch. XPath found no results {xpath}")
            return      # Don't perform patch if no matches

        patchArgs:dict = {
            "value":        patch.find('value'),
            "attribute":    patch.find("attribute"),     # Defer exception throw to later.
            "coreLibElems": currentCoreLibElems,
        }

        # Replace Config Variables with user chosen value.
        if mod.variables:
            for var in mod.variables:
                patchArgs["value"].text = patchArgs["value"].text.replace( str(var.name), str(var.value) )
            

        PatchDispatch(pType)(patchArgs)

    # Execution
    for location in modLib:
        for patchList in modLib[location]:
            patchList : lxml.etree._ElementTree
            if patchList.find("Noload") is not None:
                ui.log.log(f"    Skipping file {patchList.getroot().base} (Noload tag)")
                continue
            for patchOperation in patchList.getroot():
                patchOperation : lxml.etree._Element
                if isinstance(patchOperation, lxml.etree._Comment):
                    continue

                try:
                    doPatchType(patchOperation, location)
                except Exception as e:
                    uri = patchOperation.base
                    line = patchOperation.sourceline
                    ui.log.log(f"    Failed to apply patch operation {uri}:{line}")
                    ui.log.log(f"      Reason: {repr(e)}")
                    raise SyntaxError("Issue in patch operation. Check logs for info.") from None
