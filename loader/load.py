import os
import glob
import tempfile
import hashlib
import re
from pathlib import Path
from zipfile import ZipFile, BadZipFile

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
    if not re.fullmatch(r"[0-9a-zA-Z]{1,64}", mods_cache_signature):
        raise ValueError("Invalid QuickLaunch key")
    return QUICK_LAUNCH_PREFIX + mods_cache_signature + QUICK_LAUNCH_SUFFIX


def quick_launch_filename(mods_cache_signature, jarPath=None):
    filename = quick_launch_basename(mods_cache_signature)
    if jarPath:
        return os.path.join(modloader_data_dir(jarPath), filename)
    return filename


def quick_launch_files(jarPath):
    cacheDir = modloader_data_dir(jarPath)
    return sorted(glob.glob(os.path.join(cacheDir, QUICK_LAUNCH_PREFIX + "*" + QUICK_LAUNCH_SUFFIX)))


def has_quick_launch_cache(jarPath):
    return bool(quick_launch_files(jarPath))


def clear_quick_launch_cache(jarPath):
    removed = 0
    for path in quick_launch_files(jarPath):
        try:
            os.unlink(path)
            Path(path + '.sha256').unlink(missing_ok=True)
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
            Path(path + '.sha256').unlink(missing_ok=True)
            removed += 1
            ui.log.log("Pruned old QuickLaunch cache file: {}".format(path))
        except FileNotFoundError:
            pass
        except Exception as ex:
            ui.log.log("Failed to prune QuickLaunch cache file {}: {}".format(path, ex))
    return removed


def _validate_game_jar(path, full=False):
    try:
        with ZipFile(path) as jar:
            required = {"version.txt", "META-INF/MANIFEST.MF", *loader.assets.library.PATCHABLE_XML_FILES}
            members = loader.assets.library.game_members(jar)
            if not required.issubset(members) or not jar.read(members["version.txt"]).strip():
                raise ValueError("Required Space Haven entries are missing")
            if full:
                for member in members.values():
                    if not member.is_dir():
                        with jar.open(member) as stream:
                            while stream.read(1024 * 1024):
                                pass
    except (BadZipFile, OSError, ValueError, RuntimeError) as exc:
        raise RuntimeError(f"Invalid Space Haven JAR {path}: {exc}") from exc


def restore_missing_legacy_jar(jarPath):
    """Restore a structurally valid legacy backup without ever replacing an installed JAR.

    The caller supplies confirmation and holds the installation lock. Keep the
    source as a backup, including if copying or publishing the recovery fails.
    """
    jar = Path(jarPath)
    backup = Path(str(jar) + ".vanilla")
    if jar.exists() or backup.is_symlink():
        raise RuntimeError("Legacy recovery requires an absent game JAR and a regular backup")
    _validate_game_jar(backup, full=True)
    with tempfile.TemporaryDirectory(prefix=".shl-recovery-", dir=jar.parent) as scratch:
        stage = Path(scratch) / jar.name
        with backup.open("rb") as source, stage.open("xb") as target:
            while chunk := source.read(1024 * 1024):
                target.write(chunk)
            target.flush()
            os.fsync(target.fileno())
        _validate_game_jar(stage, full=True)
        # Same filesystem, atomic publication and no overwrite on Windows or POSIX.
        os.link(stage, jar)


def _reusable_cache(path):
    digest_path = Path(str(path) + ".sha256")
    try:
        if path.is_symlink() or digest_path.is_symlink() or digest_path.stat().st_size > 66:
            return False
        expected = digest_path.read_text(encoding="ascii").strip()
        if not re.fullmatch(r"[a-f0-9]{64}", expected):
            return False
        with path.open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != expected:
                return False
        _validate_game_jar(path)
        return True
    except (OSError, ValueError, RuntimeError):
        return False


def prepare_game_jar(jarPath, activeMods, mods_cache_signature, fingerprint=None):
    """Return the separate game JAR for this launch. The vendor JAR is read-only."""
    _validate_game_jar(jarPath)
    if not any((Path(mod.path) / folder).is_dir() for mod in activeMods for folder in ("library", "patches")):
        return Path(jarPath)
    path = Path(quick_launch_filename(mods_cache_signature, jarPath))
    if _reusable_cache(path):
        ui.log.log(f"Reusing verified QuickLaunch file: {path}")
        return path
    modPaths = [mod.path for mod in activeMods]
    with tempfile.TemporaryDirectory(prefix=".shl-quicklaunch-", dir=path.parent) as scratch:
        stage = Path(scratch) / path.name
        with tempfile.TemporaryDirectory(prefix="spacehaven-modloader-") as corePath:
            loader.assets.library.extract(jarPath, corePath)
            extra_assets = loader.assets.merge.mods(corePath, activeMods, modPaths)
            loader.assets.library.patch(jarPath, corePath, stage, extra_assets=extra_assets)
        _validate_game_jar(stage, full=True)
        if fingerprint is not None and fingerprint() != mods_cache_signature:
            raise RuntimeError("Game or mod files changed during preparation. Launch again to rebuild.")
        with stage.open("rb") as stream:
            sha256 = hashlib.file_digest(stream, "sha256").hexdigest()
        digest_path = Path(str(stage) + ".sha256")
        digest_path.write_bytes((sha256 + "\n").encode("ascii"))
        os.replace(stage, path)
        os.replace(digest_path, Path(str(path) + ".sha256"))
    prune_quick_launch_cache(jarPath, keep_signature=mods_cache_signature)
    return path
