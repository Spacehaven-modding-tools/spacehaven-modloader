"""Opt-in AspectJ 1.9.27 for experimental Java runtimes only.

The original game and 1.9.19 loader support are untouched. This module never
writes config.json. It downloads a pinned artifact from Maven Central on the
user's explicit request, verifies the repository checksum, and persists a
SHA-256 digest for subsequent tamper checks. Java 8 still uses the original
launcher and bundled AspectJ.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import tempfile
import urllib.request
import zipfile

VERSION = "1.9.27"
ARTIFACT = f"aspectjweaver-{VERSION}.jar"
MAVEN_BASE = "https://repo.maven.apache.org/maven2/org/aspectj/aspectjweaver/" + VERSION + "/"
SHA256 = "d8f63b252500ba50ec201a2e9fd1de74603e46c9537896b9b0b4cf14b22dbfa5"
MAX_JAR_BYTES = 12 * 1024 * 1024
# Matches the original AspectJ *dependencies*, not unrelated mod jars.
ASPECTJ_AGENT = re.compile(r"^-javaagent:(?:.*[/\\])?aspectjweaver-\d+(?:\.\d+)+\.jar(?:=.*)?$", re.I)


class AspectJRuntimeError(RuntimeError):
    pass


def storage_directory(game_executable):
    from ui import runtime_manager
    return runtime_manager.state_dir(game_executable) / "aspectj" / VERSION


def installed_artifact_path(game_executable):
    return storage_directory(game_executable) / ARTIFACT


def _jar_manifest_ok(path):
    """Small integrity/identity check, not an authenticity or signing check."""
    try:
        with zipfile.ZipFile(path) as archive:
            if archive.testzip() is not None:
                return False
            manifest = archive.read("META-INF/MANIFEST.MF").decode("utf-8", errors="replace")
            return (
                "Premain-Class: org.aspectj.weaver.loadtime.Agent" in manifest
                and "org/aspectj/weaver/loadtime/Agent.class" in archive.namelist()
                and "org/aspectj/lang/JoinPoint.class" in archive.namelist()
            )
    except (OSError, zipfile.BadZipFile, KeyError, RuntimeError):
        return False


def _hash_file(path, kind="sha256"):
    h = hashlib.new(kind)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def installed_aspectj(game_executable):
    jar = installed_artifact_path(game_executable)
    try:
        if not jar.is_symlink() and 0 < jar.stat().st_size <= MAX_JAR_BYTES and _hash_file(jar) == SHA256 and _jar_manifest_ok(jar):
            return jar
    except OSError:
        pass
    return None


def install_aspectj(game_executable, log=None):
    """Verify the exact release with a pinned SHA-256 before publication."""
    log = log or (lambda _message: None)
    already = installed_aspectj(game_executable)
    if already:
        return already
    target = installed_artifact_path(game_executable)
    target.parent.mkdir(parents=True, exist_ok=True)
    url = MAVEN_BASE + ARTIFACT
    request = urllib.request.Request(url, headers={"User-Agent": "SpaceHaven-ModLoader-SH-AspectJ/1"})
    with tempfile.TemporaryDirectory(prefix="shl-aspectj-", dir=target.parent) as scratch:
        jar = Path(scratch) / ARTIFACT
        size = 0
        with urllib.request.urlopen(request, timeout=45) as response, jar.open("xb") as output:
            if response.geturl() != url:
                raise AspectJRuntimeError("Unexpected Maven artifact download location")
            while chunk := response.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_JAR_BYTES:
                    raise AspectJRuntimeError("AspectJ artifact is unexpectedly large")
                output.write(chunk)
        if _hash_file(jar) != SHA256 or not _jar_manifest_ok(jar):
            raise AspectJRuntimeError("AspectJ agent failed SHA-256 or JAR validation.")
        if target.exists():
            quarantine = Path(tempfile.mkdtemp(prefix="previous-", dir=target.parent))
            os.link(target, quarantine / target.name)
        os.replace(jar, target)
    log(f"Verified and installed AspectJ {VERSION} ({size} bytes, SHA-256 {SHA256})")
    return target
