import os
import tempfile

import ui.log

import loader.assets.library
import loader.assets.merge


def quick_launch_filename(mods_cache_signature):
    return "quicklaunch_" + mods_cache_signature + ".jar"


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

        quicklaunchfilename = quick_launch_filename(mods_cache_signature)
        ui.log.updateBackgroundState("Saving QuickLaunch file")
        ui.log.log("Writing to quickLaunch file: {}".format(quicklaunchfilename))
        shutil.copyfile(jarPath, quicklaunchfilename)


def quickload(jarPath, mods_cache_signature):
    import shutil

    unload(jarPath, message=False)
    os.rename(jarPath, jarPath + ".vanilla")
    quicklaunchfilename = quick_launch_filename(mods_cache_signature)
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
