# Required to annotate ModDatabase.getInstance() with own type
from __future__ import annotations

import os
import sys
from xml.etree import ElementTree
import json
import tempfile
from pathlib import Path
from packaging.version import Version

import version
import ui.log

from ui.gameinfo import GameInfo

ASPECTJ_VERSION = "1.9.19"
ASPECTJ_JAR = "aspectj-{}.jar".format(ASPECTJ_VERSION)
ASPECTJ_WEAVER_JAR = "aspectjweaver-{}.jar".format(ASPECTJ_VERSION)
ASPECTJ_JAVAAGENT = "-javaagent:./{}".format(ASPECTJ_WEAVER_JAR)


def resolve_game_dir(gameInfo):
    if not getattr(gameInfo, "jarPath", None):
        raise ValueError("Could not resolve Space Haven directory because jarPath is empty.")
    return os.path.dirname(os.path.abspath(gameInfo.jarPath))


def resolve_config_path(gameInfo):
    return os.path.join(resolve_game_dir(gameInfo), "config.json")


def normalize_classpath_entry(path):
    return os.path.normpath(os.path.abspath(path)).replace("\\", "/")


def _resource_path(file_name):
    if getattr(sys, "frozen", False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    candidates = [
        os.path.join(base_dir, file_name),
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), file_name),
    ]

    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate

    return candidates[0]


def _write_json_file(path, jsonObj):
    with tempfile.TemporaryDirectory(dir=os.path.dirname(os.path.abspath(path))) as scratch:
        stage = os.path.join(scratch, "state.json")
        with open(stage, "w", encoding="utf-8") as outFile:
            json.dump(jsonObj, outFile, indent=4)
        os.replace(stage, path)


class ModDatabase:
    """Information about a collection of mods"""

    __lastInstance = None
    Prefixes = {}
    mods: list[Mod]

    def __init__(self, path_list, gameInfo):
        self.path_list = path_list
        self.gameInfo = gameInfo
        self.mods = []
        self.discovery = []
        self.load_order_path = os.path.join(resolve_game_dir(gameInfo), "modloader_load_order.json")
        ModDatabase.__lastInstance = self

    def locateMods(self):
        self.mods = []
        self.discovery = []
        ModDatabase.Prefixes = {}

        def report(message):
            self.discovery.append(message)
            ui.log.log(message)

        ui.log.log("Locating mods...")
        seen_mods = set()
        for path in self.path_list:
            report(f"Mod folder: {path}")
            try:
                folders = sorted(os.listdir(path), key=str.casefold)
                root = Path(path).resolve()
            except (OSError, RuntimeError) as error:
                report(f"  Could not scan folder: {error}")
                continue

            found = len(self.mods)
            for modFolder in folders:
                modPath = os.path.join(path, modFolder)
                if not os.path.isdir(modPath):
                    continue
                if modFolder.lower().startswith("spacehaven_"):
                    report(f"  Skipped {modFolder}: reserved prefix for extracted game assets.")
                    continue
                resolved = os.path.normcase(os.path.realpath(modPath))
                if not Path(resolved).is_relative_to(root):
                    report(f"  Skipped {modFolder}: directory resolves outside the mod folder.")
                    continue

                info_file = os.path.join(modPath, "info")
                if not os.path.isfile(info_file):
                    info_file += ".xml"
                if not os.path.isfile(info_file):
                    report(f"  Skipped {modFolder}: no info or info.xml in the item folder.")
                    continue
                if resolved in seen_mods:
                    report(f"  Skipped {modFolder}: already found in an earlier scan.")
                    continue
                try:
                    files = os.listdir(modPath)
                except OSError as error:
                    report(f"  Skipped {modFolder}: could not read the item folder ({error}).")
                    continue

                seen_mods.add(resolved)
                jars = sorted(
                    (file for file in files if file.lower().endswith(".jar")
                     and os.path.isfile(os.path.join(modPath, file))
                     and not file.lower().startswith(("aspectj-", "aspectjweaver-", "aspectjrt-", "aspectjtools-"))),
                    key=str.casefold,
                )
                if jars:
                    newMod = JarMod(info_file, self.gameInfo, jars[0])
                    newMod.jarPaths = [os.path.join(modPath, jar) for jar in jars]
                else:
                    newMod = Mod(info_file, self.gameInfo)
                if newMod.info_xml is None:
                    report(f"  {modFolder} is disabled because its metadata could not be read. See the game log for details.")
                if newMod.prefix:
                    if newMod.prefix in ModDatabase.Prefixes and ModDatabase.Prefixes[newMod.prefix]:
                        ui.log.log(f"  Warning: Mod prefix {newMod.prefix} for mod {newMod.title()} is already in use.")
                    else:
                        ModDatabase.Prefixes[newMod.prefix] = newMod.enabled
                self.mods.append(newMod)
            report(f"  Mods found: {len(self.mods) - found}")

        self.apply_load_order()
        ui.log.log(f"Discovery complete: {len(self.mods)} mod(s), {sum(mod.enabled for mod in self.mods)} enabled.")

    def isEmpty(self) -> bool:
        return not len(self.mods)

    def load_order(self):
        try:
            with open(self.load_order_path, "r", encoding="utf-8") as orderFile:
                data = json.load(orderFile)
                if isinstance(data, dict):
                    data = data.get("modPaths", [])
                if isinstance(data, list):
                    return [path for path in data if isinstance(path, str)]
        except FileNotFoundError:
            return []
        except Exception as ex:
            ui.log.log("  Failed to read mod load order: {}".format(ex))
        return []

    def save_load_order(self):
        try:
            _write_json_file(
                self.load_order_path,
                {
                    "version": 1,
                    "modPaths": [mod.path for mod in self.mods],
                },
            )
            ui.log.log("Saved mod load order to {}".format(self.load_order_path))
            return True
        except Exception as ex:
            ui.log.log("Failed to save mod load order: {}".format(ex))
            return False

    def apply_load_order(self):
        saved_order = self.load_order()
        order_index = {os.path.normcase(os.path.normpath(path)): index for index, path in enumerate(saved_order)}

        def sort_key(mod):
            path_key = os.path.normcase(os.path.normpath(mod.path))
            if path_key in order_index:
                return (0, order_index[path_key])
            return (1, mod.name.lower())

        self.mods.sort(key=sort_key)

    @classmethod
    def getActiveMods(cls) -> list[Mod]:
        return [mod for mod in cls.getInstance().mods if mod.enabled]

    @classmethod
    def getInactiveMods(cls) -> list[Mod]:
        return [mod for mod in cls.getInstance().mods if not mod.enabled]

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
    """An individual user configurable variable.  Presently a simple string search-replace. Designed to support more advanced features."""

    def __init__(self, XML: ElementTree.Element):
        self.loadXml(
            XML.get("name"),  # Internal Name, used in search-replace of the XML.
            XML.text,  # Description shown in UI to user.
            XML.get("type"),  # Optional Data type, as int, float, str, or bool. TODO:enforce.
            XML.get("size"),  # Optional Size. Number of characters permitted in string.  TODO:enforce.
            XML.get("min"),  # Optional minimum value. TODO:enforce.
            XML.get("max"),  # Optional maximum value. TODO:enforce.
            XML.get("default"),  # Optional default value.
            XML.get("value"),  # User set value, and optional initial value. Can be different than default.
        )

    # Clean entry for different value types.
    # TODO: fully implement and enforce.
    def _cleanValue(self, val: any):
        if not self.type:
            self.type = "str"
        type_name = self.type.strip().lower()
        v: any = val
        try:
            # Be very generous on string type.
            if type_name == "" or type_name.startswith("str") or type_name.startswith("text") or type_name.startswith("txt"):
                self.type = "str"
                v = val
            elif type_name.startswith("int"):
                self.type = "int"
                v = int(val)
            elif type_name.startswith("float"):
                self.type = "float"
                v = float(val)
            elif type_name.startswith("bool"):
                self.type = "bool"
                # Be generous on boolean values.
                if str(val).strip().lower() in ["1", "-1", "t", "y", "true", "yes", "on"]:
                    v = True
                else:
                    v = False
        except:
            return None

        return v

    def loadXml(self, name: str, desc: str, data_type: str, size, min, max, default, value):
        self.name: str = name
        self.desc: str = desc
        self.type: str = data_type

        self.min: float = float(min) if min else None
        self.max: float = float(max) if max else None
        self.size: int = int(size) if size else None
        self.default: str = str(default) if default else None
        self.value: str = self._cleanValue(value)
        if self.value is None:
            self.value = value = self.default
        self.saved_value = self.value


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
        self.gameInfo: GameInfo = gameInfo
        self._mappedIDs = []
        self.enabled = not os.path.isfile(os.path.join(self.path, DISABLED_MARKER))
        self.variables = []
        self.info_file = info_file
        self.info_xml = None
        self.config_xml = None
        self.known_issues = ""
        self.loadInfo(info_file)

    def loadInfo(self, infoFile):

        if not os.path.exists(infoFile):
            ui.log.log("    No info file present")
            self.name += " [!]"
            self.description = "Error loading mod: no info file present. Please create one."
            self.enabled = False
            return

        def _optional(tag):
            return (mod.findtext(tag) or "").strip()

        try:
            info = ElementTree.parse(infoFile)
            mod = info.getroot()

            self.info_xml = info
            self.name = _optional("name") or self.name
            self.description = _optional("description")

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
                if all_var and len(all_var) > 0:
                    self.variables = []
                    for var in all_var:
                        confVar = ModConfigVar(var)
                        if confVar:
                            self.variables.append(confVar)
                        confVar = None

            self.verifyLoaderVersion(mod)
            self.verifyGameVersion(mod, self.gameInfo)

        except (AttributeError, OSError, ValueError, ElementTree.ParseError) as ex:
            self.name += " [!]"
            self.description = "Error loading mod: error parsing info file."
            self.info_xml = self.config_xml = None
            self.enabled = False
            ui.log.log("    Failed to parse info file {}: {}".format(infoFile, ex))

        ui.log.log("    Finished loading {}".format(self.name))

    def saveConfig(self):
        if self.config_xml:
            all_var = self.config_xml.findall("var")
            if all_var and len(all_var) > 0:
                values = {var.name: var.value for var in self.variables}
                for var_xml in all_var:
                    if (name := var_xml.get("name")) in values:
                        var_xml.set("value", str(values[name]))

            # config_xml is a section of info_xml
            try:
                with tempfile.TemporaryDirectory(dir=self.path) as scratch:
                    stage = os.path.join(scratch, "info.xml")
                    self.info_xml.write(stage, encoding="utf-8")
                    os.replace(stage, self.info_file)
                for var in self.variables:
                    var.saved_value = var.value
                ui.log.log("    Saved config for {}".format(self.title()))
                return True
            except Exception as ex:
                ui.log.log("    Failed to save config for {}: {}".format(self.title(), ex))
                return False
        return True

    def enable(self):
        if self.info_xml is None:
            ui.log.log(f"    Cannot enable {self.title()}: fix its info.xml first.")
            return
        try:
            os.unlink(os.path.join(self.path, DISABLED_MARKER))
            self.enabled = True
        except FileNotFoundError:
            self.enabled = True
        except Exception as ex:
            ui.log.log("    Failed to enable mod {}: {}".format(self.title(), ex))

    def disable(self):
        try:
            with open(os.path.join(self.path, DISABLED_MARKER), "w") as marker:
                marker.write("this mod is disabled, remove this file to enable it again (or toggle it via the modloader UI)")
            self.enabled = False
        except Exception as ex:
            ui.log.log("    Failed to disable mod {}: {}".format(self.title(), ex))

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
        self.minimumLoaderVersion = mod.findtext("minimumLoaderVersion", "").strip()
        if not self.minimumLoaderVersion:
            return
        if Version(self.minimumLoaderVersion) > Version(version.version):
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

        for v in list(gameVersionsTag):
            self.gameVersions.append(v.text)

        ui.log.log("    Game Versions: {}".format(", ".join(self.gameVersions)))

        if not gameInfo.version:
            self.warn("Could not determine Space Haven version. You might need to update your loader.")
            return

        if gameInfo.version not in self.gameVersions:
            self.warn("This mod may not support Space Haven {}, it only supports {}.".format(self.gameInfo.version, ", ".join(self.gameVersions)))

    def warn(self, message):
        ui.log.log("    Warning: {}".format(message))
        self.name += " [!]"
        self.description += "\nWARNING: {}!".format(message)


class JarMod(Mod):
    def __init__(self, info_file, gameInfo, jarModFileName):
        super().__init__(info_file, gameInfo)
        self.jarModFileName = jarModFileName
        self.jarPath = os.path.join(self.path, jarModFileName)
        self.jarPaths = [self.jarPath]
        self.classPathName = normalize_classpath_entry(self.jarPath)
        self.gameDir = resolve_game_dir(gameInfo)
        self.configPath = resolve_config_path(gameInfo)
