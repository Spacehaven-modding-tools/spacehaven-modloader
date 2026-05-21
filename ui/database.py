# Required to annotate ModDatabase.getInstance() with own type
from __future__ import annotations

import os
import sys
from xml.etree import ElementTree
import json
from packaging.version import Version

import version
import ui.log
import shutil

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


def _classpath_entry_to_path(entry, game_dir):
    if not entry:
        return ""
    native_entry = entry.replace("/", os.sep)
    if not os.path.isabs(native_entry):
        native_entry = os.path.join(game_dir, native_entry)
    return os.path.normcase(os.path.normpath(os.path.abspath(native_entry)))


def _is_path_under(path, roots):
    for root in roots:
        try:
            if os.path.commonpath([path, root]) == root:
                return True
        except ValueError:
            continue
    return False


def _dedupe_preserving_order(values):
    seen = set()
    result = []
    for value in values:
        if value in seen:
            ui.log.log("    Removed duplicate classPath entry: {}".format(value))
            continue
        seen.add(value)
        result.append(value)
    return result


def reconcile_jarmod_classpath(gameInfo, jarMods, modRoots):
    configPath = resolve_config_path(gameInfo)
    if not os.path.isfile(configPath):
        ui.log.log("Skipping JAR classPath cleanup because config.json does not exist: {}".format(configPath))
        return False

    gameDir = resolve_game_dir(gameInfo)
    managedRoots = []
    for root in modRoots:
        if root and os.path.isdir(root):
            managedRoots.append(os.path.normcase(os.path.normpath(os.path.abspath(root))))

    if not managedRoots:
        ui.log.log("Skipping JAR classPath cleanup because no mod roots are available.")
        return False

    activeJarMods = [mod for mod in jarMods if isinstance(mod, JarMod) and mod.enabled]
    expectedEntries = [mod.classPathName for mod in activeJarMods]
    expectedEntrySet = set(expectedEntries)
    expectedPathSet = {_classpath_entry_to_path(entry, gameDir) for entry in expectedEntries}

    try:
        with open(configPath, "r", encoding="utf-8") as configFile:
            jsonObj = json.load(configFile)
    except Exception as ex:
        ui.log.log("Failed to read config.json for JAR classPath cleanup: {}".format(ex))
        return False

    classPath = jsonObj.get("classPath", [])
    if not isinstance(classPath, list):
        ui.log.log("Skipping JAR classPath cleanup because classPath is not a list.")
        return False

    keepAlways = {ASPECTJ_WEAVER_JAR, ASPECTJ_JAR, "spacehaven.jar"}
    newClassPath = []
    changed = False

    for entry in classPath:
        if entry in keepAlways:
            newClassPath.append(entry)
            continue

        entryPath = _classpath_entry_to_path(entry, gameDir)
        isJar = entry.lower().endswith(".jar")
        isManagedJar = isJar and _is_path_under(entryPath, managedRoots)

        if not isManagedJar:
            newClassPath.append(entry)
            continue

        if entry in expectedEntrySet or entryPath in expectedPathSet:
            newClassPath.append(entry)
            continue

        changed = True
        if os.path.isfile(entryPath):
            ui.log.log("    Removed disabled or inactive JAR classPath entry: {}".format(entry))
        else:
            ui.log.log("    Removed stale missing JAR classPath entry: {}".format(entry))

    dedupedClassPath = _dedupe_preserving_order(newClassPath)
    if len(dedupedClassPath) != len(newClassPath):
        changed = True
    newClassPath = dedupedClassPath

    for entry in [ASPECTJ_WEAVER_JAR, ASPECTJ_JAR]:
        if activeJarMods and entry not in newClassPath:
            newClassPath.insert(0 if entry == ASPECTJ_WEAVER_JAR else min(1, len(newClassPath)), entry)
            changed = True
            ui.log.log("    Restored required AspectJ classPath entry: {}".format(entry))

    for entry in expectedEntries:
        if entry not in newClassPath:
            _insert_before_spacehaven(newClassPath, entry)
            changed = True
            ui.log.log("    Restored enabled JAR classPath entry: {}".format(entry))

    if not changed:
        ui.log.log("JAR classPath cleanup: no stale entries found.")
        return False

    jsonObj["classPath"] = newClassPath
    try:
        _write_json_file(configPath, jsonObj)
        ui.log.log("JAR classPath cleanup updated config.json")
        return True
    except Exception as ex:
        ui.log.log("Failed to write config.json during JAR classPath cleanup: {}".format(ex))
        return False


def _resource_path(file_name):
    if getattr(sys, "frozen", False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.getcwd()

    candidates = [
        os.path.join(base_dir, file_name),
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), file_name),
        os.path.abspath(file_name),
    ]

    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate

    return candidates[0]


def _insert_once(values, value, index):
    if value not in values:
        values.insert(min(index, len(values)), value)


def _move_once_to_front(values, ordered_entries):
    remaining = [value for value in values if value not in ordered_entries]
    return list(ordered_entries) + remaining


def _insert_before_spacehaven(values, value):
    if value in values:
        return
    try:
        index = values.index("spacehaven.jar")
        values.insert(index, value)
    except ValueError:
        values.append(value)


def _write_json_file(path, jsonObj):
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as outFile:
        json.dump(jsonObj, outFile, indent=4)
    os.replace(tmp_path, path)


class ModDatabase:
    """Information about a collection of mods"""

    __lastInstance = None
    Prefixes = {}
    mods: list[Mod]

    def __init__(self, path_list, gameInfo):
        self.path_list = path_list
        self.gameInfo = gameInfo
        self.mods = []
        self.load_order_path = os.path.join(resolve_game_dir(gameInfo), "modloader_load_order.json")
        ModDatabase.__lastInstance = self

    def locateMods(self):

        self.mods = []
        ModDatabase.Prefixes = {}

        ui.log.log("Locating mods...")
        for path in self.path_list:
            if not os.path.isdir(path):
                ui.log.log("  Skipping missing mod path: {}".format(path))
                continue
            for modFolder in os.listdir(path):
                if "spacehaven" in modFolder:
                    continue  # don't need to load core game definitions
                modPath = os.path.join(path, modFolder)
                if os.path.isfile(modPath):
                    # TODO add support for zip files ? unzip them on the fly ?
                    # continue  # don't load logs, prefs, etc
                    pass

                # TODO Pass the mod path to Mod() instead of the info_file and let it handle
                # the info file check. It already does this! Let it do its job!
                info_file = os.path.join(modPath, "info")
                if not os.path.isfile(info_file):
                    info_file += ".xml"
                if not os.path.isfile(info_file):
                    # no info file, don't create a mod.
                    continue

                isJarMod = False
                jarModFileName = ""
                # jarModDisabled = False
                for file in os.listdir(modPath):
                    if file.endswith(".jar"):
                        isJarMod = True
                        jarModFileName = file

                if isJarMod:
                    newMod = JarMod(info_file, self.gameInfo, jarModFileName)
                else:
                    newMod = Mod(info_file, self.gameInfo)
                if newMod.prefix:
                    if newMod.prefix in ModDatabase.Prefixes and ModDatabase.Prefixes[newMod.prefix]:
                        ui.log.log(f"  Warning: Mod prefix {newMod.prefix} for mod {newMod.title()} is already in use.")
                    else:
                        ModDatabase.Prefixes[newMod.prefix] = newMod.enabled
                self.mods.append(newMod)

        self.apply_load_order()

        for mod in self.mods:
            if isinstance(mod, JarMod) and mod.enabled:
                mod.enable()  # this has to be called in order to update config.json

        self.reconcile_jarmod_classpath()

    def isEmpty(self) -> bool:
        return not len(self.mods)

    def load_order(self):
        try:
            with open(self.load_order_path, "r", encoding="utf-8") as orderFile:
                data = json.load(orderFile)
                if isinstance(data, dict):
                    return data.get("modPaths", [])
                if isinstance(data, list):
                    return data
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

    def reconcile_jarmod_classpath(self):
        return reconcile_jarmod_classpath(self.gameInfo, self.mods, self.path_list)

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
        self.gameInfo = gameInfo
        self._mappedIDs = []
        self.enabled = not os.path.isfile(os.path.join(self.path, DISABLED_MARKER))
        self.variables = []
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
                if all_var and len(all_var) > 0:
                    self.variables = []
                    for var in all_var:
                        confVar = ModConfigVar(var)
                        if confVar:
                            self.variables.append(confVar)
                        confVar = None

            self.verifyLoaderVersion(mod)
            self.verifyGameVersion(mod, self.gameInfo)

        except (AttributeError, ElementTree.ParseError) as ex:
            self.name += " [!]"
            self.description = "Error loading mod: error parsing info file."
            ui.log.log("    Failed to parse info file {}: {}".format(infoFile, ex))

        ui.log.log("    Finished loading {}".format(self.name))

    def saveConfig(self):
        if self.config_xml:
            all_var = self.config_xml.findall("var")
            if all_var and len(all_var) > 0:
                for var in self.variables:
                    v = self.config_xml.findall("./var[@name='" + var.name + "']")
                    if v:
                        v[0].set("value", str(var.value))

            # config_xml is a section of info_xml
            try:
                self.info_xml.write(self.info_file, encoding="unicode")
                for var in self.variables:
                    var.saved_value = var.value
                ui.log.log("    Saved config for {}".format(self.title()))
                return True
            except Exception as ex:
                ui.log.log("    Failed to save config for {}: {}".format(self.title(), ex))
                return False
        return True

    def enable(self):
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
        self.minimumLoaderVersion = mod.find("minimumLoaderVersion").text
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
        self.classPathName = normalize_classpath_entry(self.jarPath)
        self.gameDir = resolve_game_dir(gameInfo)
        self.configPath = resolve_config_path(gameInfo)

    def _copy_aspectj(self):
        for fileName in [ASPECTJ_JAR, ASPECTJ_WEAVER_JAR]:
            sourcePath = _resource_path(fileName)
            targetPath = os.path.join(self.gameDir, fileName)

            if not os.path.isfile(sourcePath):
                raise FileNotFoundError("Required AspectJ file not found: {}".format(sourcePath))

            if os.path.abspath(sourcePath) == os.path.abspath(targetPath):
                ui.log.log("    AspectJ file already in game directory: {}".format(targetPath))
            elif os.path.isfile(targetPath):
                ui.log.log("    AspectJ file already exists: {}".format(targetPath))
            else:
                shutil.copyfile(sourcePath, targetPath)
                ui.log.log("    Copied AspectJ file to: {}".format(targetPath))

    def _load_config(self):
        with open(self.configPath, "r", encoding="utf-8") as configFile:
            return json.load(configFile)

    def _save_config(self, jsonObj):
        _write_json_file(self.configPath, jsonObj)
        ui.log.log("    Updated config.json")

    def _log_paths(self, action):
        modSource = "Workshop" if "\\workshop\\content\\" in self.path.lower() or "/workshop/content/" in self.path.lower() else "local"
        ui.log.log("  JarMod {}: {}".format(action, self.title()))
        ui.log.log("    Mod source: {}".format(modSource))
        ui.log.log("    Mod path: {}".format(self.path))
        ui.log.log("    Game directory: {}".format(self.gameDir))
        ui.log.log("    Config path: {}".format(self.configPath))
        ui.log.log("    Mod JAR classPath entry: {}".format(self.classPathName))

    def _remove_disabled_marker(self):
        markerPath = os.path.join(self.path, DISABLED_MARKER)
        if os.path.isfile(markerPath):
            os.unlink(markerPath)

    def enable(self):
        self._log_paths("enable")

        try:
            self._copy_aspectj()

            jsonObj = self._load_config()
            classPath = jsonObj.setdefault("classPath", [])
            vmArgs = jsonObj.setdefault("vmArgs", [])
            legacyClassPathName = self.path + "/" + self.jarModFileName
            legacyEntries = {
                legacyClassPathName,
                normalize_classpath_entry(legacyClassPathName),
            }
            classPath[:] = [entry for entry in classPath if entry not in legacyEntries and entry not in [ASPECTJ_WEAVER_JAR, ASPECTJ_JAR]]
            classPath[:] = _move_once_to_front(classPath, [ASPECTJ_WEAVER_JAR, ASPECTJ_JAR])
            _insert_before_spacehaven(classPath, self.classPathName)

            _insert_once(vmArgs, ASPECTJ_JAVAAGENT, 0)
            _insert_once(vmArgs, "-XstartOnFirstThread", 0)
            _insert_once(vmArgs, "--add-opens java.base/java.lang=ALL-UNNAMED", 0)

            self._save_config(jsonObj)
            self._remove_disabled_marker()

            self.enabled = True
        except Exception as ex:
            self.enabled = False
            ui.log.log("    Failed to enable JAR mod: {}".format(ex))

    def disable(self):
        self.enabled = False

        self._log_paths("disable")

        try:
            with open(os.path.join(self.path, DISABLED_MARKER), "w") as marker:
                marker.write("this mod is disabled, remove this file to enable it again (or toggle it via the modloader UI)")
        except Exception as ex:
            ui.log.log("    Failed to write disabled marker: {}".format(ex))

        if not os.path.isfile(self.configPath):
            ui.log.log("    config.json does not exist; classPath cleanup skipped.")
            return

        try:
            jsonObj = self._load_config()
            classPath = jsonObj.get("classPath", [])
            legacyClassPathName = self.path + "/" + self.jarModFileName
            removeEntries = {
                self.classPathName,
                legacyClassPathName,
                normalize_classpath_entry(legacyClassPathName),
            }
            newClassPath = [entry for entry in classPath if entry not in removeEntries]

            if len(newClassPath) != len(classPath):
                jsonObj["classPath"] = newClassPath
                self._save_config(jsonObj)
                ui.log.log("    Removed JAR classPath entry: {}".format(self.classPathName))
            else:
                ui.log.log("    JAR classPath entry was not present.")
        except Exception as ex:
            ui.log.log("    Failed to disable JAR mod cleanly: {}".format(ex))

    pass
