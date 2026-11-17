"""Locate and verify the DateFix aspect bundled with the Mod Loader."""

from __future__ import annotations

import hashlib
import sys
import zipfile

from ui.paths import loader_directory

JAR_NAME = "shl-locale-datefix.jar"
SHA256 = "2329161394bcad5c2ed800c89433f2a9ac846e9f707353cb40591f85507eb4cb"
TYPE_FILTER = "META-INF/shl-date-types.xml"
REQUIRED = frozenset({"META-INF/aop.xml", TYPE_FILTER, "shl/locale/SaveDateTextNormalizer.class"})


class DateTextFixError(RuntimeError):
    pass


def bundled_candidates():
    directory = loader_directory()
    if not getattr(sys, "frozen", False):
        directory = directory / "tools" / "date_text_fix"
    return (directory / JAR_NAME,)


def verified_patch_path():
    """Return the bundled aspect JAR after checking its digest and entries."""
    for path in dict.fromkeys(bundled_candidates()):
        if not path.is_file():
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != SHA256:
            raise DateTextFixError("Date UI patch integrity mismatch: " + str(path))
        try:
            with zipfile.ZipFile(path) as archive:
                if not REQUIRED.issubset(archive.namelist()) or archive.testzip() is not None:
                    raise DateTextFixError("Invalid date UI patch JAR: " + str(path))
        except (OSError, zipfile.BadZipFile) as exc:
            raise DateTextFixError("Cannot read date UI patch JAR: " + str(path)) from exc
        return path
    raise DateTextFixError("Missing shl-locale-datefix.jar. Reinstall the Mod Loader or restore the file from the source checkout.")
