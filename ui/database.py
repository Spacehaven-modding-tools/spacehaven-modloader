# Required to annotate ModDatabase.getInstance() with own type
from __future__ import annotations

import distutils.version
from operator import truediv
import os
from xml.etree import ElementTree
import json

import version

import ui.gameinfo
import ui.log
import shutil


import tkinter as tk

class ModDatabase:
    """Information about a collection of mods"""
    __lastInstance = None
    Prefixes = {}
    mods: list[Mod]

    def __init__(self, path_list, gameInfo):
        self.path_list = path_list
        self.gameInfo = gameInfo
        self.mods = []
        ModDatabase.__lastInstance = self

    def locateMods(self):

        self.mods = []
        ModDatabase.Prefixes = {}

        ui.log.log("Locating mods...")
        for path in self.path_list:
            for modFolder in os.listdir(path):
                if 'spacehaven' in modFolder:
                    continue  # don't need to load core game definitions
                modPath = os.path.join(path, modFolder)
                if os.path.isfile(modPath):
                    # TODO add support for zip files ? unzip them on the fly ?
                    #continue  # don't load logs, prefs, etc
                    pass
                
                # TODO Pass the mod path to Mod() instead of the info_file and let it handle
                # the info file check. It already does this! Let it do its job!
                info_file = os.path.join(modPath, "info")
                if not os.path.isfile(info_file):
                    info_file += '.xml'
                if not os.path.isfile(info_file):
                    # no info file, don't create a mod.
                    continue
                
                isJarMod = False
                jarModFileName = ""
                jarModDisabled = False
                for file in os.listdir(modPath):
                    if file.endswith(".jar"):
                        isJarMod = True
                        jarModFileName = file

                if isJarMod:
                    newMod = JarMod(info_file, self.gameInfo, jarModFileName)
                    if newMod.enabled:
                        newMod.enable() # this has to be called in order to update config.json
                else:
                    newMod = Mod(info_file, self.gameInfo)
                if newMod.prefix:
                    if newMod.prefix in ModDatabase.Prefixes and ModDatabase.Prefixes[newMod.prefix]:
                        ui.log.log(f"  Warning: Mod prefix {newMod.prefix} for mod {newMod.title()} is already in use.")
                    else:
                        ModDatabase.Prefixes[newMod.prefix] = newMod.enabled
                self.mods.append(newMod)
        
        self.mods.sort(key=lambda mod: mod.name)

    def isEmpty(self) -> bool:
        return not len(self.mods)

    @classmethod
    def getActiveMods(cls) -> list[Mod]:
        return [
            mod
            for mod in cls.getInstance().mods
            if mod.enabled
        ]

    @classmethod
    def getInactiveMods(cls) -> list[Mod]:
        return [
            mod
            for mod in cls.getInstance().mods
            if not mod.enabled
        ]

    @classmethod
    def getRegisteredMods(cls) -> list[Mod]:
        return cls.getInstance().mods

    @classmethod
    def getMod(cls, modPath) -> Mod:
        """Get a specific mod from its installation path."""
        for mod in cls.getInstance().mods:
            if mod.path == modPath:
                return mod

    @classmethod
    def getInstance(cls) -> ModDatabase:
        """Return the last generated instance of a mod database."""
        if cls.__lastInstance is None:
            raise Exception("Mod Database not ready.")
        return cls.__lastInstance


class ModConfigVar:
    """ An individual user configurable variable.  Presently a simple string search-replace. Designed to support more advanced features."""

    def __init__(self, XML:ElementTree.Element):
        self.loadXml(
                XML.get("name"),        # Internal Name, used in search-replace of the XML.
                XML.text,               # Description shown in UI to user.
                XML.get("type"),        # Optional Data type, as int, float, str, or bool. TODO:enforce.
                XML.get("size"),        # Optional Size. Number of characters permitted in string.  TODO:enforce.
                XML.get("min"),         # Optional minimum value. TODO:enforce.
                XML.get("max"),         # Optional maximum value. TODO:enforce.
                XML.get("default"),     # Optional default value. 
                XML.get("value")        # User set value, and optional initial value. Can be different than default.
        )

    # Clean entry for different value types.
    # TODO: fully implement and enforce.
    def _cleanValue(self, val:any):
        if not self.type:
            self.type="str"
        type_name = self.type.strip().lower()
        v:any = val
        try:
            # Be very generous on string type.
            if type_name is None or type_name == "" or type_name.startswith("str") or type_name.startswith("text") or type_name.startswith("txt"):
                self.type="str"
                v = val
            elif type_name.startswith("int"):
                self.type="int"
                v = int(val)
            elif type_name.startswith("float"):
                self.type="float"
                v = float(val)
            elif type_name.startswith("bool"):
                self.type="bool"
                # Be generous on boolean values.
                if str(val).strip().lower() in [1,-1,'1','-1','t','y','true','yes','on']:
                    v=True
                else:
                    v=False
            elif type_name.startswith("toggle"): 
                self.type="toggle"
                # Be generous on boolean values. 
                if str(val).strip().lower() in [1,-1,'1','-1','t','y','true','yes','on']:
                    v = var.max
                else:
                    v = var.min
        except:
            return None

        return v


    def loadXml(self, name:str, desc:str, data_type:str, size, min, max, default, value):
        self.name:str=name
        self.desc:str=desc
        self.type:str=data_type

        self.min:float=float(min) if min else None
        self.max:float=float(max) if max else None
        self.min:toggle=str(min) if min else None
        self.max:toggle=str(max) if max else None
        self.size:int=int(size) if size else None
        self.default:str=str(default) if default else None
        self.value:str=self._cleanValue(value)
        if self.value is None:
            self.value = value = self.default
        

DISABLED_MARKER = "disabled.txt"
class Mod:
    """Details about a specific mod (name, description)"""

    def __init__(self, info_file, gameInfo):
        self.path = os.path.normpath(os.path.dirname(info_file))
        ui.log.log("  Loading mod at {}...".format(self.path))
        
        # TODO add a flag to warn users about savegame compatibility ?
        self.name = os.path.basename(self.path)
        self.version = ""
        self.author = ""
        self.website = ""
        self.updates = ""
        self.prefix = ""
        self.gameInfo = gameInfo
        self._mappedIDs = []
        self.enabled = not os.path.isfile(os.path.join(self.path, DISABLED_MARKER))
        self.variables:dict = {}
        self.info_file = info_file
        self.loadInfo(info_file)
        self.known_issues = ""

    def loadInfo(self, infoFile):
        
        if not os.path.exists(infoFile):
            ui.log.log("    No info file present")
            self.name += " [!]"
            self.description = "Error loading mod: no info file present. Please create one."
            return
        
        def _sanitize(elt):
            return elt.text.strip("\r\n\t ")
        
        def _optional(tag):
            try:
                return _sanitize(mod.find(tag))
            except:
                return ""
        
        try:
            info = ElementTree.parse(infoFile)
            mod = info.getroot()

            self.info_xml = info
            self.name = _sanitize(mod.find("name"))
            self.description = _sanitize(mod.find("description"))
            
            self.known_issues = _optional("knownIssues")
            self.version = _optional("version")
            self.author = _optional("author")
            self.website = _optional("website")
            self.updates = _optional("updates")
            self.prefix = int(_optional("modid") or "0")

            # feature request #4, user configuration.
            self.config_xml = mod.find("config")
            if self.config_xml:
                all_var = self.config_xml.findall("var")
                if all_var and len(all_var)>0:
                    self.variables=[]
                    for var in all_var:
                        confVar = ModConfigVar(var)
                        if confVar:
                            self.variables.append(confVar)
                        confVar=None

            self.verifyLoaderVersion(mod)
            self.verifyGameVersion(mod, self.gameInfo)

        except AttributeError as ex:
            print(ex)
            self.name += " [!]"
            self.description = "Error loading mod: error parsing info file."
            ui.log.log("    Failed to parse info file")

        ui.log.log("    Finished loading {}".format(self.name))

    def saveConfig(self):         
        if self.config_xml:
            all_var = self.config_xml.findall("var")
            if all_var and len(all_var)>0:
                for var in self.variables:
                    v = self.config_xml.findall("./var[@name='" + var.name + "']")
                    if v :
                        v[0].set("value",str(var.value))

            # config_xml is a section of info_xml
            self.info_xml.write(self.info_file)


    def enable(self):
        try:
            os.unlink(os.path.join(self.path, DISABLED_MARKER))
            self.enabled = True
        except:
            pass
    
    def disable(self):
        with open(os.path.join(self.path, DISABLED_MARKER), "w") as marker:
            marker.write("this mod is disabled, remove this file to enable it again (or toggle it via the modloader UI)")
        self.enabled = False
    
    def title(self):
        title = self.name
        if self.version:
            title += " (%s)" % self.version
        return title
    
    def getDescription(self):
        """Build a description from the mod data"""
        description = ""
        if self.author:
            description += f"AUTHOR: {self.author}\n"
        description += self.description + "\n"
        if self.known_issues:
            description += "\n" + "KNOWN ISSUES: " + self.known_issues
        if self.prefix:
            description += f"\nPREFIX: {self.prefix}"
        if self.website:
            # FIXME make it a separate textfield, can't select from this one
            description += f"\nURL: {self.website}"
        return description

    def getAutomaticID(self, internalID):
        """Returns a new ID prefixed by the mod prefix."""
        autoIDAllocatedSize = 1000
        if internalID in self._mappedIDs:
            raise ValueError(f"{self.title()} tried to double-allocate internal ID {internalID}")
        self._mappedIDs.append(internalID)
        id = self.prefix * autoIDAllocatedSize + internalID
        if internalID > autoIDAllocatedSize:
            raise RuntimeError(f"{self.title()} requested an ID outside of the auto-ID allocation limit ({internalID} limit {autoIDAllocatedSize}). File a bug report.")
        return str(id)

    def verifyLoaderVersion(self, mod):
        self.minimumLoaderVersion = mod.find("minimumLoaderVersion").text
        if distutils.version.StrictVersion(self.minimumLoaderVersion) > distutils.version.StrictVersion(version.version):
            self.warn("Mod loader version {} is required".format(self.minimumLoaderVersion))

        ui.log.log("    Minimum Loader Version: {}".format(self.minimumLoaderVersion))

    def verifyGameVersion(self, mod, gameInfo):
        # FIXME disabled ATM as this check doesn't work
        return
        self.gameVersions = []

        gameVersionsTag = mod.find("gameVersions")
        if gameVersionsTag is None:
            self.warn("This mod does not declare what game version(s) it supports.")
            return

        for version in list(gameVersionsTag):
            self.gameVersions.append(version.text)

        ui.log.log("    Game Versions: {}".format(", ".join(self.gameVersions)))

        if not gameInfo.version:
            self.warn("Could not determine Space Haven version. You might need to update your loader.")
            return

        if not gameInfo.version in self.gameVersions:
            self.warn("This mod may not support Space Haven {}, it only supports {}.".format(
                self.gameInfo.version,
                ", ".join(self.gameVersions)
            ))

    def warn(self, message):
        ui.log.log("    Warning: {}".format(message))
        self.name += " [!]"
        self.description += "\nWARNING: {}!".format(message)

class JarMod(Mod):
    def __init__(self, info_file, gameInfo, jarModFileName):
        super().__init__(info_file, gameInfo)
        self.jarModFileName = jarModFileName
        self.classPathName = self.path + "/" + jarModFileName

    def enable(self):
        try:
            os.unlink(os.path.join(self.path, DISABLED_MARKER))
        except:
            pass

        shutil.copyfile("aspectj-1.9.19.jar", self.path + "/../../aspectj-1.9.19.jar")
        shutil.copyfile("aspectjweaver-1.9.19.jar", self.path + "/../../aspectjweaver-1.9.19.jar")

        try:
            f = open(self.path + "/../../config.json","r", encoding='utf-8')
            jsonObj = json.load(f)
            classPath = jsonObj["classPath"]
            vmArgs = jsonObj["vmArgs"]
            
            # aspectj is required for .jar mods
            if "aspectjweaver-1.9.19.jar" not in classPath:
                classPath.insert(0, "aspectjweaver-1.9.19.jar")
            if "aspectj-1.9.19.jar" not in classPath:
                classPath.insert(1, "aspectj-1.9.19.jar")

            if self.classPathName not in classPath:
                classPath.insert(2, self.classPathName)

            jsonObj["classPath"] = classPath
                
            if "-javaagent:./aspectjweaver-1.9.19.jar" not in vmArgs:
                    vmArgs.insert(0, "-javaagent:./aspectjweaver-1.9.19.jar")
            if "-XstartOnFirstThread" not in vmArgs:
                    vmArgs.insert(0, "-XstartOnFirstThread")
            if "--add-opens java.base/java.lang=ALL-UNNAMED" not in vmArgs:
                    vmArgs.insert(0, "--add-opens java.base/java.lang=ALL-UNNAMED")

            jsonObj["vmArgs"] = vmArgs

            f.close()
            open(self.path + "/../../config.json", 'w').close() # erase file
            f = open(self.path + "/../../config.json","w", encoding='utf-8')
            f.write(json.dumps(jsonObj, indent=4))
            print("Updated config.json")

            self.enabled = True
        except:
            pass
    
    def disable(self):
        with open(os.path.join(self.path, DISABLED_MARKER), "w") as marker:
            marker.write("this mod is disabled, remove this file to enable it again (or toggle it via the modloader UI)")
        self.enabled = False

        f = open(self.path + "/../../config.json","r", encoding='utf-8')
        jsonObj = json.load(f)
        classPath = jsonObj["classPath"]

        if self.classPathName in classPath:
            classPath.remove(self.classPathName)
            jsonObj["classPath"] = classPath
            f.close()
            open(self.path + "/../../config.json", 'w').close() # erase file
            f = open(self.path + "/../../config.json","w", encoding='utf-8')
            f.write(json.dumps(jsonObj, indent=4))
            print("Updated config.json")
        
    pass
