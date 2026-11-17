import os
from zipfile import ZipFile
from pathlib import PurePosixPath
import ui.log

PATCHABLE_XML_FILES = [
    "library/haven",
    "library/texts",
    "library/animations",
    "library/textures",
    "library/audio",
]

PATCHABLE_CIM_FILES = ["library/%d.cim" % i for i in range(24)]


def game_members(archive):
    """Resolve the identical central-directory aliases shipped by Space Haven."""
    by_offset = {}
    by_name = {}
    for item in archive.infolist():
        canonical = by_offset.setdefault(item.header_offset, item)
        if canonical is not item:
            fields = ("filename", "CRC", "flag_bits", "compress_type", "compress_size", "file_size")
            if any(getattr(canonical, field) != getattr(item, field) for field in fields):
                raise ValueError("Conflicting entries share a game JAR data offset: " + item.filename)
        by_name[item.filename] = canonical
    return by_name


def extract(jarPath, corePath):
    """Extract library files from spacehaven.jar"""
    ui.log.updateBackgroundState("Extracting game files")

    if not os.path.exists(corePath):
        os.mkdir(corePath)

    ui.log.log("  Extracting library from {} to {}...".format(jarPath, corePath))
    with ZipFile(jarPath) as spacehaven:
        for file, member in game_members(spacehaven).items():
            if file.startswith("library/") and not file.endswith("/"):
                _validate_library_path(file)
                spacehaven.extract(member, corePath)


def _validate_library_path(name):
    if (not name.startswith("library/") or len(PurePosixPath(name).parts) < 2
            or any(part in {"", ".", ".."} for part in name.split("/"))
            or any(char in name for char in ('\\', ':', '\x00'))):
        raise ValueError("Invalid library path: " + repr(name))


def patch(jarPath, corePath, resultPath, extra_assets=None):
    """Build a complete JAR or propagate the failing read/write to the caller."""
    import shutil

    update_files = list(dict.fromkeys(PATCHABLE_XML_FILES + (extra_assets or [])))
    for entry in update_files:
        _validate_library_path(entry)
    updated = set(update_files)
    ui.log.updateBackgroundState("Merging game files")
    with ZipFile(jarPath) as original, ZipFile(resultPath, "x") as patched:
        for name, member in game_members(original).items():
            if name.endswith("/") or name in updated:
                continue
            with original.open(member) as source, patched.open(name, "w", force_zip64=True) as output:
                shutil.copyfileobj(source, output, length=1024 * 1024)
        for name in update_files:
            patched.write(os.path.join(corePath, *name.split("/")), name)
