"""Deterministic QuickLaunch fingerprints, including edited mod files.

The upstream version-only signature could reuse a stale cached game JAR when
local/Workshop mod contents changed without an info.xml version bump.
The launch worker computes the content hashes before using a cached JAR.
"""
import hashlib
import os
from pathlib import Path

SKIP_DIRS = {".git", ".svn", "__pycache__", ".venv", "node_modules"}
SKIP_FILES = {"disabled.txt", ".ds_store"}


def mod_fingerprint(mods, game_version, game_jar=None):
    h = hashlib.sha256()

    def update(*parts):
        for part in parts:
            data = str(part).encode("utf-8", "surrogateescape")
            h.update(len(data).to_bytes(8, "big"))
            h.update(data)

    def content(path):
        with open(path, "rb") as stream:
            return hashlib.file_digest(stream, "sha256").hexdigest()

    update("spacehaven", game_version, "cache_schema_3", os.environ.get("FORCE_PARSER_ENCODING", ""))
    if game_jar:
        update("game-jar", content(game_jar))
    from loader.assets import library, merge, patch, explode, utils
    for module in (library, merge, patch, explode, utils):
        # Frozen builds version their embedded code as a single release.
        source = Path(module.__file__)
        if source.is_file():
            update(source.name, content(source))
    from version import version
    update(version)

    for mod in mods:  # order must remain significant
        mod_path = Path(mod.path)
        update("mod", mod.name, mod.version or "VERSION_UNKNOWN", os.path.normcase(str(mod_path.absolute())))
        if not mod_path.is_dir():
            update("mod-directory-missing")
            continue
        for base, folders, filenames in os.walk(mod_path, followlinks=False):
            folders[:] = sorted(f for f in folders if f.lower() not in SKIP_DIRS and not (Path(base) / f).is_symlink())
            for name in sorted(filenames):
                if name.lower() in SKIP_FILES or (Path(base) == mod_path and name.startswith("custom_texture_") and name.endswith(".png")):
                    continue  # generated sprite pages are outputs, not mod inputs
                path = Path(base) / name
                if not path.resolve().is_relative_to(mod_path.resolve()):
                    raise ValueError(f"Mod input points outside the mod directory: {path}")
                relative = path.relative_to(mod_path).as_posix()
                if path.is_file():
                    update(relative, content(path))
    return h.hexdigest()[:32]
