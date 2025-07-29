
import os
import zipfile39
import ui.log

PATCHABLE_XML_FILES = [
    'library/haven',
    'library/texts',
    'library/animations',
    'library/textures',
]

PATCHABLE_CIM_FILES = ["library/%d.cim" % i for i in range(24)]

def extract(jarPath, corePath):
    """Extract library files from spacehaven.jar"""
    ui.log.updateBackgroundState("Extracting game files")

    if not os.path.exists(corePath):
        os.mkdir(corePath)

    ui.log.log("  Extracting library from {} to {}...".format(jarPath, corePath))
    with zipfile39.ZipFile(jarPath, "r") as spacehaven:
        for file in set(spacehaven.namelist()):
            if file.startswith("library/") and not file.endswith("/"):
#                ui.log.log("    {}".format(file))
                spacehaven.extract(file, corePath)


def patch(jarPath, corePath, resultPath, extra_assets = None):
    """Patch spacehaven.jar with custom library files"""

    ui.log.log("Patch spacehaven.jar with custom library files...")
    
    original = zipfile39.ZipFile(jarPath, "r")
    patched = zipfile39.ZipFile(resultPath, "w")

    ui.log.updateBackgroundState("Merging vanilla files")
    
    update_files = PATCHABLE_XML_FILES + PATCHABLE_CIM_FILES
    for file in set(original.namelist()):
        if not file.endswith("/") and not file in update_files:
            try:
                patched.writestr(file, original.read(file))
            except Exception as e:
                ui.log.log("ERROR: Unable to add {} to {}: {}".format(str(file), str(resultPath), str(e)))
                pass
   
    original.close()
    
    ui.log.updateBackgroundState("Merging modded files")
    
    if extra_assets:
        update_files += extra_assets
    for file in update_files:
        ui.log.log("  Merging modded {}...".format(file))
        patched.write(os.path.join(corePath, file.replace('/', os.sep)), file)

    patched.close()
