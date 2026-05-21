import os
import glob
import sys
import tempfile

import ui.log

import loader.assets.library
import loader.assets.merge


MODLOADER_DATA_DIR = "modloader"
QUICK_LAUNCH_PREFIX = "quicklaunch_"
QUICK_LAUNCH_SUFFIX = ".jar"
PREVIOUS_GAME_PATH_FILENAME = "previous_spacehaven_path.txt"
EXTRA_MODS_PATH_FILENAME = "extra_mods_path.txt"


def modloader_data_dir(jarPath):
    gameDir = os.path.dirname(os.path.abspath(jarPath))
    dataDir = os.path.join(gameDir, "mods", MODLOADER_DATA_DIR)
    os.makedirs(dataDir, exist_ok=True)
    return dataDir


def modloader_state_file(jarPath, filename):
    return os.path.join(modloader_data_dir(jarPath), filename)


def quick_launch_basename(mods_cache_signature):
    return QUICK_LAUNCH_PREFIX + mods_cache_signature + QUICK_LAUNCH_SUFFIX


def quick_launch_filename(mods_cache_signature, jarPath=None):
    filename = quick_launch_basename(mods_cache_signature)
    if jarPath:
        return os.path.join(modloader_data_dir(jarPath), filename)
    return filename


def quick_launch_files(jarPath):
    cacheDir = modloader_data_dir(jarPath)
    return sorted(glob.glob(os.path.join(cacheDir, QUICK_LAUNCH_PREFIX + "*" + QUICK_LAUNCH_SUFFIX)))


def legacy_quick_launch_files(jarPath):
    cacheDir = os.path.normcase(os.path.normpath(os.path.abspath(modloader_data_dir(jarPath))))
    candidates = []
    for path in {os.getcwd(), os.path.dirname(sys.argv[0])}:
        if not path:
            continue
        path = os.path.abspath(path)
        if os.path.normcase(os.path.normpath(path)) == cacheDir:
            continue
        candidates.extend(glob.glob(os.path.join(path, QUICK_LAUNCH_PREFIX + "*" + QUICK_LAUNCH_SUFFIX)))
    return sorted(set(candidates))


def has_quick_launch_cache(jarPath):
    return bool(quick_launch_files(jarPath) or legacy_quick_launch_files(jarPath))


def clear_quick_launch_cache(jarPath):
    removed = 0
    for path in quick_launch_files(jarPath) + legacy_quick_launch_files(jarPath):
        try:
            os.unlink(path)
            removed += 1
            ui.log.log("Removed QuickLaunch cache file: {}".format(path))
        except FileNotFoundError:
            pass
        except Exception as ex:
            ui.log.log("Failed to remove QuickLaunch cache file {}: {}".format(path, ex))
    return removed


def prune_quick_launch_cache(jarPath, keep_signature=None, max_files=10):
    files = quick_launch_files(jarPath)
    if len(files) <= max_files:
        return 0

    keepFile = quick_launch_filename(keep_signature, jarPath) if keep_signature else None
    deleteCandidates = [path for path in files if os.path.abspath(path) != os.path.abspath(keepFile or "")]
    deleteCandidates.sort(key=lambda path: os.path.getmtime(path))
    deleteCount = max(0, len(files) - max_files)

    removed = 0
    for path in deleteCandidates[:deleteCount]:
        try:
            os.unlink(path)
            removed += 1
            ui.log.log("Pruned old QuickLaunch cache file: {}".format(path))
        except FileNotFoundError:
            pass
        except Exception as ex:
            ui.log.log("Failed to prune QuickLaunch cache file {}: {}".format(path, ex))
    return removed


def load(jarPath, activeMods, mods_cache_signature=None):
    """Load mods into spacehaven.jar"""

    modPaths = [mod.path for mod in activeMods]

    unload(jarPath, message=False)

    coreDirectory = tempfile.TemporaryDirectory()
    corePath = coreDirectory.name

    ui.log.log("Loading mods...")
    ui.log.log("  jarPath: {}".format(jarPath))
    ui.log.log("  corePath: {}".format(corePath))
    ui.log.log("  modPaths:\n  {}".format("\n  ".join(modPaths)))

    loader.assets.library.extract(jarPath, corePath)
    ui.log.updateBackgroundState("Installing Mods")
    extra_assets = loader.assets.merge.mods(corePath, activeMods, modPaths)

    os.rename(jarPath, jarPath + ".vanilla")
    loader.assets.library.patch(jarPath + ".vanilla", corePath, jarPath, extra_assets=extra_assets)

    coreDirectory.cleanup()

    if mods_cache_signature:
        import shutil

        quicklaunchfilename = quick_launch_filename(mods_cache_signature, jarPath)
        ui.log.updateBackgroundState("Saving QuickLaunch file")
        ui.log.log("Writing to quickLaunch file: {}".format(quicklaunchfilename))
        shutil.copyfile(jarPath, quicklaunchfilename)
        prune_quick_launch_cache(jarPath, keep_signature=mods_cache_signature)


def quickload(jarPath, mods_cache_signature):
    import shutil

    unload(jarPath, message=False)
    os.rename(jarPath, jarPath + ".vanilla")
    quicklaunchfilename = quick_launch_filename(mods_cache_signature, jarPath)
    ui.log.updateBackgroundState("Loading QuickLaunch file")
    ui.log.log("Reusing quickLaunch file: {}".format(quicklaunchfilename))
    shutil.copyfile(quicklaunchfilename, jarPath)


def unload(jarPath, message=True):
    """Unload mods from spacehaven.jar"""

    if message:
        ui.log.updateBackgroundState("Unloading mods")

    vanillaPath = jarPath + ".vanilla"
    if not os.path.exists(vanillaPath):
        if message:
            ui.log.log("  No active mods")
        return

    ui.log.log("  Restoring original {} from {}".format(jarPath, vanillaPath))
    # FIXME check if the game is running again if that fails ? Restarting from ingame after a language change does that
    os.remove(jarPath)
    os.rename(vanillaPath, jarPath)
