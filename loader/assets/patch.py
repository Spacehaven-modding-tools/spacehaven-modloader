import copy

import lxml.etree
import ui.log
import re


def AttributeSet(patchArgs):
    """Set the attribute on the node, adding if not present"""
    element: lxml.etree._Element
    matchingElements = patchArgs["coreLibElems"]

    attribute = patchArgs["attribute"]
    if attribute is None:
        raise SyntaxError("Invalid patch operation, <attribute> is not defined.")
    attribute = attribute.text

    value = patchArgs["value"]
    if value is None:
        raise SyntaxError("Invalid patch operation, <value> is not defined.")

    for element in matchingElements:
        element.set(attribute, value.text)


def AttributeAdd(patchArgs):
    """Adds the attribute to the node IFF the attribute name is not already present"""
    element: lxml.etree._Element
    matchingElements = patchArgs["coreLibElems"]

    attribute = patchArgs["attribute"]
    if attribute is None:
        raise SyntaxError("Invalid patch operation, <attribute> is not defined.")
    attribute = attribute.text

    value = patchArgs["value"]
    if value is None:
        raise SyntaxError("Invalid patch operation, <value> is not defined.")

    for element in matchingElements:
        if element.get(attribute, None) is not None:
            raise KeyError(f"Attribute '{attribute}' already exists")
        element.set(attribute, value.text)


def AttributeRemove(patchArgs):
    """Remove the attribute from the node"""
    element: lxml.etree._Element
    matchingElements = patchArgs["coreLibElems"]

    attribute = patchArgs["attribute"]
    if attribute is None:
        raise SyntaxError("Invalid patch operation, <attribute> is not defined.")
    attribute = attribute.text

    for element in matchingElements:
        element.attrib.pop(attribute)


def AttributeMath(patchArgs):
    """Set the attribute on the node, via math"""
    element: lxml.etree._Element
    matchingElements = patchArgs["coreLibElems"]

    attribute = patchArgs["attribute"]
    if attribute is None:
        raise SyntaxError("Invalid patch operation, <attribute> is not defined.")
    attribute = attribute.text

    value = patchArgs["value"]
    if value is None:
        raise SyntaxError("Invalid patch operation, <value> is not defined.")

    opType = value.get("opType", None)
    valueFloat = float(value.text)
    for element in matchingElements:
        startVal = float(element.get(attribute, 0))
        isFloat = "." in element.get(attribute, 0)
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
            element.set(attribute, f"{newVal:.1f}")
        else:
            newVal = int(newVal)
            element.set(attribute, f"{newVal}")


def NodeAdd(patchArgs):
    """Adds the provided node(s) as last child to the selected node"""
    parent: lxml.etree._Element
    matchingElements = patchArgs["coreLibElems"]

    value = patchArgs["value"]
    if value is None:
        raise SyntaxError("Invalid patch operation, <value> is not defined.")

    for parent in matchingElements:
        index = len(parent.getchildren())
        for node in value:
            index += 1
            parent.insert(index, copy.deepcopy(node))


def NodeAddFirst(patchArgs):
    """Adds the provided node(s) as first child to the selected node"""
    parent: lxml.etree._Element
    matchingElements = patchArgs["coreLibElems"]

    value = patchArgs["value"]
    if value is None:
        raise SyntaxError("Invalid patch operation, <value> is not defined.")

    for parent in matchingElements:
        for node in reversed(value):
            parent.insert(1, copy.deepcopy(node))


def NodeInsert(patchArgs):
    """Adds the provided node(s) as sibling(s) to the selected node, after the selected node"""
    sibling: lxml.etree._Element
    matchingElements = patchArgs["coreLibElems"]

    value = patchArgs["value"]
    if value is None:
        raise SyntaxError("Invalid patch operation, <value> is not defined.")

    for sibling in matchingElements:
        parent = sibling.find("./..")
        index = parent.index(sibling)
        for node in value:
            index += 1
            parent.insert(index, copy.deepcopy(node))


def NodeInsertBefore(patchArgs):
    """Adds a provided node as sibling to the selected node, before the selected node"""
    sibling: lxml.etree._Element
    matchingElements = patchArgs["coreLibElems"]

    value = patchArgs["value"]
    if value is None:
        raise SyntaxError("Invalid patch operation, <value> is not defined.")

    for sibling in matchingElements:
        parent = sibling.find("./..")
        index = parent.index(sibling)
        for node in reversed(value):
            parent.insert(index, copy.deepcopy(node))


def NodeRemove(patchArgs):
    """Deletes the selected node"""
    node: lxml.etree._Element
    matchingElements = patchArgs["coreLibElems"]

    for node in matchingElements:
        parent = node.find("./..")
        parent.remove(node)


def NodeReplace(patchArgs):
    """Replaces the selected node with a single provided node"""
    target: lxml.etree._Element
    matchingElements = patchArgs["coreLibElems"]

    value = patchArgs["value"]
    if value is None:
        raise SyntaxError("Invalid patch operation, <value> is not defined.")
    if len(value.getchildren()) <= 0:
        raise SyntaxError("Invalid patch operation, <value> must contain a node.")

    for target in matchingElements:
        parent = target.find("./..")
        parent.replace(target, copy.deepcopy(value[0]))


# Default case function
def BadOp(patchArgs):
    raise SyntaxError("Invalid patch operation type.")


patchDispatcher = {
    "SetAttribute": AttributeSet,
    "AttributeSet": AttributeSet,

    "AddAttribute": AttributeAdd,
    "AttributeAdd": AttributeAdd,

    "RemoveAttribute": AttributeRemove,
    "AttributeRemove": AttributeRemove,

    "MathAttribute": AttributeMath,
    "AttributeMath": AttributeMath,


    "Add": NodeAdd,  # this was kept because of retrocompatibility
    "AddNode": NodeAdd,  # this was kept because of retrocompatibility
    "NodeAdd": NodeAdd,  # this was kept because of retrocompatibility
    
    "AddFirst": NodeAddFirst,
    "AddNodeFirst": NodeAddFirst,
    "NodeAddFirst": NodeAddFirst,
    
    "AddLast": NodeAdd,
    "AddNodeLast": NodeAdd,
    "NodeAddLast": NodeAdd,

    "Insert": NodeInsert,  # this was kept because of retrocompatibility
    "InsertNode": NodeInsert,  # this was kept because of retrocompatibility
    "NodeInsert": NodeInsert,  # this was kept because of retrocompatibility

    "InsertBefore": NodeInsertBefore,
    "InsertNodeBefore": NodeInsertBefore,
    "NodeInsertBefore": NodeInsertBefore,

    "InsertAfter": NodeInsert,
    "InsertNodeAfter": NodeInsert,
    "NodeInsertAfter": NodeInsert,

    "Remove": NodeRemove,
    "RemoveNode": NodeRemove,
    "NodeRemove": NodeRemove,

    "Replace": NodeReplace,
    "ReplaceNode": NodeReplace,
    "NodeReplace": NodeReplace,
}


def PatchDispatch(patchType):
    """Return the correct PatchOperation function"""
    return patchDispatcher.get(patchType, BadOp)


def doPatchType(coreLib, mod: dict, patch: lxml.etree._Element, location: str):
    """Execute a single patch. Provided to reduce indentation level"""

    patchType = patch.attrib["Class"]
    xpath = patch.find("xpath").text
    matchingElements = coreLib[location].xpath(xpath)
    count = len(matchingElements)
    value = patch.find("value")
    attribute = patch.find("attribute")

    # Log
    log = [""]
    log.append(f"    {patchType.upper():15}")
    log.append(f"      xpath:      {xpath}")
    log.append(f"      matches:    {count:<3}")
    if attribute is not None:
        log.append(f"      attribute:  {attribute.text if attribute is not None else ''}")
    if value is not None:
        if len(value.getchildren()) > 0:
            strValue = "".join("".join(lxml.etree.tostring(child, encoding="unicode")) for child in value)
        else:
            strValue = value.text
        strValue = strValue.replace("\n", "").replace("\t", " ")
        strValue = re.sub(r"\s+", " ", strValue)
        strValue = (strValue[:150] + "...") if len(strValue) > 150 else strValue
        log.append(f"      value:      {strValue}")

    try:
        # Check patch type
        if patchType not in patchDispatcher:
            raise SyntaxError(f"Invalid patch operation type '{patchType}'.")

        # Don't perform patch if no matches are found
        if count <= 0:
            log.append("      result:      not performed: no xpath matches")
            return

        patchEnable = patch.find("enable")
        if patchEnable is not None:
            patchEnable = patchEnable.text

        patchDisable = patch.find("disable")
        if patchDisable is not None:
            patchDisable = patchDisable.text

        # Replace variables defined in config section of 'info.xml' file with its corresponding value
        if mod.variables:
            if value is not None:
                for var in mod.variables:
                    value.text = value.text.replace(str(var.name), str(var.value))

            if patchEnable is not None:
                for var in mod.variables:
                    patchEnable = patchEnable.replace(str(var.name), str(var.value))

            if patchDisable is not None:
                for var in mod.variables:
                    patchDisable = patchDisable.replace(str(var.name), str(var.value))

        # Skip if disabled
        if patchEnable is not None and patchEnable in [0, "0", "f", "n", "false", "no", "off"]:
            log.append(f"      result:      skipped (enable = {patchEnable})")
            return

        if patchDisable is not None and patchDisable in [1, "1", "t", "y", "true", "yes", "on"]:
            log.append(f"      result:      skipped (disable = {patchDisable})")
            return

        # Execute patch
        patchArgs: dict = {
            "value": value,
            "attribute": attribute,
            "coreLibElems": matchingElements,
        }

        PatchDispatch(patchType)(patchArgs)
        log.append("      result:     OK")

    except:
        log.append("      result:     ERROR <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<")
        raise

    finally:
        for line in log:
            ui.log.log(line)


def doPatches(coreLib, modLib, mod: dict):

    # Execution
    for location in modLib:
        for patchList in modLib[location]:
            patchList: lxml.etree._ElementTree

            if patchList is None or patchList.getroot() is None:
                ui.log.log(f"    Skipping location {location} (no XML root node)")
                continue

            # Is this even useful? TODO: Remove?
            if patchList.find("Noload") is not None:
                ui.log.log(f"    Skipping file {patchList.getroot().base} (contains Noload XML tag)")
                continue

            ui.log.log("")
            ui.log.log(f"    Executing Patch Operations: mod='{mod.name}', file='{location}'...")

            # Run patch operations
            for patchOperation in patchList.getroot():
                patchOperation: lxml.etree._Element

                # Skip XML comments
                if isinstance(patchOperation, lxml.etree._Comment):
                    continue

                try:
                    doPatchType(coreLib, mod, patchOperation, location)

                except Exception as e:
                    uri = patchOperation.base
                    line = patchOperation.sourceline
                    ui.log.log(f"      Failed to apply patch operation {uri}:{line}")
                    ui.log.log(f"      Reason: {repr(e)}")
                    raise SyntaxError("Patch operation failed, see logs.txt for more details.") from None
