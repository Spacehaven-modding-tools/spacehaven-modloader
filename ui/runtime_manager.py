"""Install and verify optional Temurin runtimes beside each game's mods."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import stat
import subprocess
import tarfile
import tempfile
import urllib.parse
import urllib.request
import zipfile

RUNTIME_MAJOR = 27
SUPPORTED_MAJORS = (25, 27)
MODE_ORIGINAL = "original"
MODE_TEMURIN25 = "temurin25"
MODE_TEMURIN = "temurin27"
VALID_MODES = (MODE_ORIGINAL, MODE_TEMURIN25, MODE_TEMURIN)
PREFERENCES_FILENAME = "experimental_runtime.json"
RUNTIME_NAME = "temurin-27"  # backwards-compatible default name
MAX_ARCHIVE_BYTES = 400 * 1024 * 1024
MAX_EXPANDED_BYTES = 1_100 * 1024 * 1024
MAX_ARCHIVE_ITEMS = 12_000
ADOPTIUM_API_TEMPLATE = "https://api.adoptium.net/v3/assets/latest/{major}/hotspot"
ADOPTIUM_API = ADOPTIUM_API_TEMPLATE.format(major=RUNTIME_MAJOR)


class RuntimeErrorDetail(RuntimeError):
    """Human-readable runtime preparation or launch error."""


def game_directory(game_executable):
    path = Path(game_executable).expanduser().resolve()
    # macOS .app bundle paths are normalised only for runtime-store layout
    if path.suffix.lower() == ".app":
        return path / "Contents" / "Resources"
    return path.parent


def state_dir(game_executable):
    return game_directory(game_executable) / "mods" / "modloader"


def preferences_path(game_executable):
    return state_dir(game_executable) / PREFERENCES_FILENAME


def get_mode(game_executable):
    try:
        data = json.loads(preferences_path(game_executable).read_text(encoding="utf-8"))
        mode = data.get("mode")
        return mode if mode in VALID_MODES else MODE_ORIGINAL
    except (OSError, ValueError, TypeError, AttributeError):
        return MODE_ORIGINAL


def set_mode(game_executable, mode):
    if mode not in VALID_MODES:
        raise ValueError("Unknown runtime mode: " + str(mode))
    target = preferences_path(game_executable)
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=target.parent) as scratch:
        tmp = Path(scratch) / target.name
        tmp.write_text(json.dumps({"mode": mode, "schema": 1}, indent=2), encoding="utf-8")
        os.replace(tmp, target)


def platform_artifact():
    system = platform.system().lower()
    architecture = platform.machine().lower()
    if system not in {"windows", "linux", "darwin"}:
        raise RuntimeErrorDetail("Unsupported operating system: " + system)
    if architecture in {"amd64", "x86_64", "x64"}:
        arch = "x64"
    elif architecture in {"arm64", "aarch64"}:
        arch = "aarch64"
    else:
        raise RuntimeErrorDetail("Unsupported architecture for Temurin 27: " + architecture)
    # Explicitly use the official Adoptium naming, not platform.system() values.
    os_name = {"windows": "windows", "linux": "linux", "darwin": "mac"}[system]
    if os_name == "windows" and arch != "x64":
        raise RuntimeErrorDetail("Space Haven Windows binaries require x64 Java.")
    return os_name, arch


def runtime_home(game_executable, major=RUNTIME_MAJOR):
    if major not in SUPPORTED_MAJORS:
        raise ValueError("Unsupported Java major: " + str(major))
    return state_dir(game_executable) / "runtimes" / f"temurin-{major}"


def java_binary(runtime_dir):
    exe = "java.exe" if platform.system() == "Windows" else "java"
    return Path(runtime_dir) / "bin" / exe


RUNTIME_MANIFEST = ".shl-runtime.json"


def _runtime_files(root):
    files = {}
    if root.is_symlink() or getattr(root.stat(), "st_file_attributes", 0) & 0x400:
        raise RuntimeErrorDetail("Runtime directory is a link or reparse point")

    def walk_error(exc):
        raise exc

    for base, folders, filenames in os.walk(root, followlinks=False, onerror=walk_error):
        for name in folders + filenames:
            path = Path(base) / name
            info = path.lstat()
            if path.is_symlink() or getattr(info, "st_file_attributes", 0) & 0x400:
                raise RuntimeErrorDetail(f"Runtime contains a link or reparse point: {name}")
            if not stat.S_ISDIR(info.st_mode) and not stat.S_ISREG(info.st_mode):
                raise RuntimeErrorDetail(f"Runtime contains an unsupported file: {name}")
            if stat.S_ISREG(info.st_mode) and path != root / RUNTIME_MANIFEST:
                with path.open("rb") as stream:
                    files[path.relative_to(root).as_posix()] = hashlib.file_digest(stream, "sha256").hexdigest()
    return files


def installed_java(game_executable, major=RUNTIME_MAJOR):
    root = runtime_home(game_executable, major)
    candidate = java_binary(root)
    if not candidate.is_file():
        return None
    manifest = root / RUNTIME_MANIFEST
    try:
        if manifest.is_symlink() or manifest.stat().st_size > 4 * 1024 * 1024:
            return None
        data = json.loads(manifest.read_text(encoding="utf-8"))
        if data["major"] == major and data["files"] == _runtime_files(root):
            return candidate
    except (OSError, TypeError, KeyError, ValueError, RuntimeErrorDetail):
        pass
    return None


def verify_java(java_path, major=RUNTIME_MAJOR):
    try:
        env = {key: value for key, value in os.environ.items()
               if key.upper() not in {"JDK_JAVA_OPTIONS", "JAVA_TOOL_OPTIONS", "_JAVA_OPTIONS"}}
        completed = subprocess.run([str(java_path), "-XshowSettings:properties", "-version"],
                                   text=True, errors="replace", capture_output=True, timeout=15, check=False, env=env)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeErrorDetail("Java runtime could not be executed: " + str(exc)) from exc
    message = (completed.stderr or "") + (completed.stdout or "")
    match = re.search(r'(?im)^(?:java|openjdk) version\s+"(?:1\.)?(\d+)[^"]*".*$', message)
    architecture = re.search(r"(?m)^\s*os\.arch\s*=\s*(\S+)", message)
    expected = platform_artifact()[1]
    accepted = {"x64": {"amd64", "x86_64", "x64"}, "aarch64": {"aarch64", "arm64"}}
    if completed.returncode != 0 or not match or int(match.group(1)) != major:
        raise RuntimeErrorDetail(f"Expected Java {major}, got: " + (match.group(0) if match else message.strip()[-240:]))
    if architecture is None or architecture.group(1).lower() not in accepted[expected]:
        raise RuntimeErrorDetail(f"Expected {expected} Java runtime")
    return match.group(0)


def _request_json(url):
    request = urllib.request.Request(url, headers={"User-Agent": "SpaceHaven-ModLoader-Experimental-Java27/1", "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=25) as response:
        if response.status != 200:
            raise RuntimeErrorDetail("Adoptium metadata request failed: HTTP " + str(response.status))
        body = response.read(2 * 1024 * 1024 + 1)
    if len(body) > 2 * 1024 * 1024:
        raise RuntimeErrorDetail("Adoptium metadata response unexpectedly large")
    return json.loads(body)


def release_package(major=RUNTIME_MAJOR):
    if major not in SUPPORTED_MAJORS:
        raise ValueError("Unsupported Java major: " + str(major))
    os_name, arch = platform_artifact()
    query = urllib.parse.urlencode({"architecture": arch, "image_type": "jre", "os": os_name, "vendor": "eclipse"})
    assets = _request_json(ADOPTIUM_API_TEMPLATE.format(major=major) + "?" + query)
    if not isinstance(assets, list) or not assets:
        raise RuntimeErrorDetail(f"Adoptium does not offer a Temurin {major} JRE for this OS/architecture. No files were changed.")
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        binary = asset.get("binary")
        release = asset.get("version")
        if not isinstance(binary, dict) or not isinstance(release, dict):
            continue
        if any(binary.get(key) != value for key, value in
               {"architecture": arch, "os": os_name, "image_type": "jre", "jvm_impl": "hotspot"}.items()):
            continue
        package = binary.get("package")
        if not isinstance(package, dict):
            continue
        asset_major = release.get("major")
        link, checksum = package.get("link", ""), package.get("checksum", "")
        if not isinstance(link, str) or not isinstance(checksum, str):
            continue
        parsed = urllib.parse.urlparse(link)
        official_prefix = f"/adoptium/temurin{major}-binaries/releases/download/"
        if (asset_major != major or parsed.scheme != "https" or parsed.netloc != "github.com"
                or not parsed.path.startswith(official_prefix)):
            continue
        if not re.fullmatch(r"[A-Fa-f0-9]{64}", checksum):
            continue
        return link, checksum.lower(), str(asset.get("release_name", f"Temurin {major}"))
    raise RuntimeErrorDetail(f"Adoptium returned no suitable, verified-metadata Java {major} package")


def _download_verified(url, checksum, target):
    request = urllib.request.Request(url, headers={"User-Agent": "SpaceHaven-ModLoader-Experimental-Java27/1"})
    sha = hashlib.sha256()
    size = 0
    with urllib.request.urlopen(request, timeout=90) as response, open(target, "wb") as output:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_ARCHIVE_BYTES:
                raise RuntimeErrorDetail("Runtime archive exceeded the safety size limit")
            sha.update(chunk)
            output.write(chunk)
    if not size or sha.hexdigest().lower() != checksum:
        raise RuntimeErrorDetail("SHA-256 mismatch: downloaded Java archive failed verification")
    return size


def _safe_target(root, member_name):
    name = member_name.replace("\\", "/")
    parts = name.rstrip("/").split("/")
    if any(part in {"..", ".", ""} or part.rstrip(" .") != part or
           any(char in part for char in ':\x00<>|?*"') or
           re.fullmatch(r"(?:CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³])(?:\..*)?", part, re.I)
           for part in parts):
        raise RuntimeErrorDetail("Archive contains unsafe path: " + member_name)
    target = root.joinpath(*parts)
    if not target.resolve().is_relative_to(root.resolve()):
        raise RuntimeErrorDetail("Archive extraction escaped the runtime directory")
    return target


def _unpack_safe(archive_path, output_dir):
    """Extract archives without symlinks, traversal or oversized content."""
    total = 0
    names = set()

    def register(name):
        target = _safe_target(output_dir, name)
        key = target.relative_to(output_dir).as_posix().casefold()
        if key in names:
            raise RuntimeErrorDetail(f"Archive contains duplicate path: {name}")
        names.add(key)
        return target

    output_dir.mkdir(parents=True, exist_ok=True)
    if zipfile.is_zipfile(archive_path):
        with zipfile.ZipFile(archive_path) as archive:
            items = archive.infolist()
            if len(items) > MAX_ARCHIVE_ITEMS:
                raise RuntimeErrorDetail("Runtime archive contains too many files")
            for item in items:
                target = register(item.filename)
                mode = (item.external_attr >> 16) & 0o170000
                if mode not in {0, stat.S_IFREG, stat.S_IFDIR}:
                    raise RuntimeErrorDetail("Runtime ZIP contains a link or special file")
                total += item.file_size
                if total > MAX_EXPANDED_BYTES:
                    raise RuntimeErrorDetail("Runtime expanded data exceeded safety limit")
                if item.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(item) as source, open(target, "xb") as dest:
                        shutil.copyfileobj(source, dest, 1024 * 1024)
                    if target.name == "java" and "/bin/" in item.filename.replace("\\", "/"):
                        target.chmod(target.stat().st_mode | stat.S_IXUSR)
    else:
        with tarfile.open(archive_path, "r|gz") as archive:
            for count, item in enumerate(archive, 1):
                if count > MAX_ARCHIVE_ITEMS:
                    raise RuntimeErrorDetail("Runtime archive contains too many files")
                target = register(item.name)
                if not (item.isfile() or item.isdir()):
                    raise RuntimeErrorDetail("Runtime archive contains non-regular files")
                total += item.size
                if total > MAX_EXPANDED_BYTES:
                    raise RuntimeErrorDetail("Runtime expanded data exceeded safety limit")
                if item.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    source = archive.extractfile(item)
                    if source is None:
                        raise RuntimeErrorDetail("Cannot read archive member")
                    with source, open(target, "xb") as dest:
                        shutil.copyfileobj(source, dest, 1024 * 1024)
                    if item.mode & stat.S_IXUSR:
                        target.chmod(target.stat().st_mode | stat.S_IXUSR)


def _discover_runtime_root(output_dir):
    exe = "java.exe" if platform.system() == "Windows" else "java"
    paths = [p.parent.parent for p in output_dir.rglob(exe) if p.parent.name == "bin" and p.is_file()]
    # Most Temurin distributions contain a single directory at archive root.
    if len(paths) != 1:
        raise RuntimeErrorDetail("Could not identify exactly one Java executable in archive")
    home = paths[0]
    if not home.resolve().is_relative_to(output_dir.resolve()):
        raise RuntimeErrorDetail("Invalid runtime directory")
    return home


def install_temurin(game_executable, major=RUNTIME_MAJOR, log=None):
    """Explicit install only; never download during automatic launch."""
    if major not in SUPPORTED_MAJORS:
        raise ValueError("Unsupported Java major: " + str(major))
    log = log or (lambda message: None)
    java = installed_java(game_executable, major)
    if java:
        verify_java(java, major)
        return java
    link, checksum, release = release_package(major)
    root = runtime_home(game_executable, major)
    root.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f"shl-java{major}-", dir=str(root.parent)) as temp:
        tmp = Path(temp)
        archive = tmp / "temurin-runtime.download"
        log("Downloading " + release + " from the official Adoptium release")
        size = _download_verified(link, checksum, archive)
        log("Verified Java {} archive ({} bytes, SHA-256 {}).".format(major, size, checksum))
        extracted = tmp / "unpacked"
        _unpack_safe(archive, extracted)
        home = _discover_runtime_root(extracted)
        files = _runtime_files(home)
        verify_java(java_binary(home), major)
        (home / RUNTIME_MANIFEST).write_text(
            json.dumps({"major": major, "archive_sha256": checksum, "release": release, "files": files}),
            encoding="utf-8",
        )
        existing = installed_java(game_executable, major)
        if existing:
            verify_java(existing, major)
            return existing
        quarantined = None
        if root.exists():
            # Keep the old installation available for diagnosis or manual rollback.
            quarantined = Path(tempfile.mkdtemp(prefix=root.name + "-previous-", dir=root.parent)) / root.name
            os.rename(root, quarantined)
        try:
            os.rename(home, root)
        except OSError:
            if quarantined and not root.exists():
                os.rename(quarantined, root)
            raise
        if quarantined:
            log("Previous unverified runtime retained at " + str(quarantined))
        log("Installed isolated runtime at " + str(root))
    return java_binary(root)


def install_temurin27(game_executable, log=None):
    return install_temurin(game_executable, major=27, log=log)


def install_temurin25(game_executable, log=None):
    return install_temurin(game_executable, major=25, log=log)


def selected_java(game_executable, mode):
    if mode == MODE_ORIGINAL:
        game_dir = game_directory(game_executable)
        candidates = [java_binary(game_dir / "jre")]
        if Path(game_executable).suffix.lower() == ".app":
            candidates += sorted(Path(game_executable).glob("Contents/PlugIns/*/Contents/Home/bin/java"))
        for java in candidates:
            if java.is_file():
                return java, 8
        raise RuntimeErrorDetail("Bundled Java 8 was not found. Use the game's native launcher or repair its JRE.")
    major = {MODE_TEMURIN25: 25, MODE_TEMURIN: 27}.get(mode)
    if major is None:
        raise RuntimeErrorDetail("Unsupported runtime selection")
    java = installed_java(game_executable, major)
    if java is None:
        raise RuntimeErrorDetail(f"Temurin {major} is missing or unverified. Run Install Java + AspectJ.")
    return java, major


def preflight(game_executable, mode):
    from ui import launch_config
    java, major = selected_java(game_executable, mode)
    version = verify_java(java, major)
    jar = game_directory(game_executable) / "spacehaven.jar"
    command, _ = launch_config.build(game_executable, jar, [], java, major)
    return f"{version} | mainClass={command[-1]}"
