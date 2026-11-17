"""Build the effective classpath from the selected installation and enabled mods."""
import json
import hashlib
import os
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

from ui import aspectj_runtime, date_text_fix, runtime_manager
from ui.database import ASPECTJ_WEAVER_JAR, ASPECTJ_JAR, JarMod, _resource_path

MAIN_CLASS = re.compile(r"[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*")
MODULE_FLAGS = ("--add-opens", "--add-exports", "--add-reads", "--add-modules")
MEMORY_FLAG = re.compile(r"-Xm[sx]\d+[kKmMgG]?")
# Preserve diagnostics and opt-in JVM tuning in regular launches.
JVM_TUNING = re.compile(
    r"-XX:(?:[+-]Use(?:G1|Serial|Parallel|Z|Shenandoah)GC|"
    r"(?:MaxGCPauseMillis|ActiveProcessorCount|ParallelGCThreads|ConcGCThreads|"
    r"InitialRAMPercentage|MaxRAMPercentage)=\d+(?:\.\d+)?)"
)
JVM_INJECTION_ENV = {"CLASSPATH", "JDK_JAVA_OPTIONS", "JAVA_TOOL_OPTIONS", "_JAVA_OPTIONS"}
LEGACY_ASPECTJ_HASHES = {
    ASPECTJ_WEAVER_JAR: "36d9a05d11ee431c00f20edd53a84f9f9771b6296af9c5c1e31f7e037c6ecc97",
    ASPECTJ_JAR: "3ae8f2834e72bed7327cb9aaa2773ef865fd03214ac1f2332133870f3d29c743",
}
AOP_DESCRIPTORS = ("META-INF/aop.xml", "META-INF/aop-ajc.xml", "org/aspectj/aop.xml")


def read_settings(game_executable):
    path = runtime_manager.game_directory(game_executable) / "config.json"
    try:
        settings = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"Invalid Space Haven config.json: {exc}") from exc
    if not isinstance(settings, dict):
        raise RuntimeError("Space Haven config.json must contain a JSON object.")
    for field in ("classPath", "vmArgs"):
        items = settings.get(field, [])
        if not isinstance(items, list) or not all(isinstance(item, str) and item.strip() for item in items):
            raise RuntimeError(f"Space Haven config.json contains an invalid {field}.")
    return settings


def _manifest_fields(jar):
    member = jar.getinfo("META-INF/MANIFEST.MF")
    if member.file_size > 1024 * 1024:
        raise RuntimeError(f"JAR manifest exceeds 1 MiB: {jar.filename}")
    manifest = jar.read(member).decode("utf-8")
    section = manifest.replace("\r\n", "\n").replace("\n ", "").split("\n\n", 1)[0]
    return {key.casefold(): value for key, value in (line.split(": ", 1) for line in section.splitlines() if ": " in line)}


def manifest_main(path):
    try:
        with ZipFile(path) as jar:
            fields = _manifest_fields(jar)
            if any(name in jar.namelist() for name in ("META-INF/aop.xml", "META-INF/aop-ajc.xml")):
                raise RuntimeError("The game JAR contains AspectJ mod metadata. Verify the installation.")
            main = fields.get("main-class", "")
            if not MAIN_CLASS.fullmatch(main) or main.replace(".", "/") + ".class" not in jar.namelist():
                raise RuntimeError("The game JAR manifest does not identify a valid entry point.")
            if fields.get("class-path") or fields.get("launcher-agent-class"):
                raise RuntimeError("The game JAR manifest unexpectedly references external code.")
            return main
    except (BadZipFile, KeyError, UnicodeError) as exc:
        raise RuntimeError(f"Unable to inspect game JAR manifest: {path}") from exc


def _mod_classpath(mods):
    result = {}
    for mod in mods:
        if not isinstance(mod, JarMod):
            continue
        root = Path(mod.path).resolve(strict=True)
        visited = set()
        pending = list(map(Path, mod.jarPaths))
        while pending:
            jar_path = pending.pop(0).resolve(strict=True)
            if jar_path in visited:
                continue
            if not jar_path.is_relative_to(root) or not jar_path.is_file():
                raise RuntimeError(f"Mod JAR or dependency leaves {root}: {jar_path}")
            visited.add(jar_path)
            result[jar_path] = None
            with ZipFile(jar_path) as jar:
                if "META-INF/MANIFEST.MF" not in jar.namelist():
                    continue
                for value in _manifest_fields(jar).get("class-path", "").split():
                    dependency = urlsplit(value)
                    relative = Path(unquote(dependency.path))
                    if dependency.scheme or dependency.netloc or dependency.query or dependency.fragment or relative.is_absolute():
                        raise RuntimeError(f"External manifest dependency in {jar_path}: {value}")
                    pending.append(jar_path.parent / relative)
    return list(result)


def _can_add_date_type_filter(mod_jars):
    has_configuration = False
    for path in mod_jars:
        with ZipFile(path) as jar:
            for name in AOP_DESCRIPTORS:
                try:
                    member = jar.getinfo(name)
                except KeyError:
                    continue
                has_configuration = True
                if member.file_size > 1024 * 1024:
                    raise RuntimeError(f"AspectJ configuration is too large: {path}!/{name}")
                if ElementTree.fromstring(jar.read(member)).find("./weaver/include") is not None:
                    return True  # extend an existing union of includes
    return not has_configuration


def _effective_vm_args(items, major):
    args, ignored = [], []
    iterator = iter(items)
    for item in iterator:
        flag, _, value = item.replace(" ", "=", 1).partition("=")
        if flag in MODULE_FLAGS:
            value = value or next(iterator, "")
            if major > 8 and re.fullmatch(r"[A-Za-z0-9_./=,$-]+", value):
                args.append(f"{flag}={value}")
            else:
                ignored.append(f"{flag} {value}")
        elif MEMORY_FLAG.fullmatch(item) or JVM_TUNING.fullmatch(item):
            args.append(item)
        else:
            ignored.append(item)
    if not any(arg.startswith("-Xmx") for arg in args):
        args.append("-Xmx4G")
    if os.sys.platform == "darwin":
        args.append("-XstartOnFirstThread")
    return args, ignored


def build(game_executable, game_jar, mods, java, major, report=lambda _message: None):
    game_dir = runtime_manager.game_directory(game_executable)
    settings = read_settings(game_executable)
    main = manifest_main(game_jar)
    if settings.get("mainClass", main) != main:
        report(f"Using game manifest main class {main}; configured entry point excluded: {settings['mainClass']!r}")

    mod_jars = _mod_classpath(mods)
    allowed = {os.path.normcase(str(path)) for path in (Path(game_jar).resolve(), game_dir / "spacehaven.jar", *mod_jars)}
    for entry in settings.get("classPath", []):
        candidate = os.path.normcase(os.path.abspath(game_dir / entry))
        if candidate not in allowed:
            report(f"Excluded configured classpath entry: {entry!r}")

    args, ignored = _effective_vm_args(settings.get("vmArgs", []), major)
    for item in ignored:
        if item != "-XstartOnFirstThread" and not aspectj_runtime.ASPECTJ_AGENT.fullmatch(item):
            # JVM arguments can contain secrets. Log the option name only.
            report("Excluded configured JVM option: " + item.split("=", 1)[0].split(" ", 1)[0])
    native_paths = [str(game_dir / p) for p in ("bin", "bins", ".")]
    args.append("-Djava.library.path=" + os.pathsep.join(native_paths))
    cp = []
    if major > 8:
        weaver = aspectj_runtime.installed_aspectj(game_executable)
        if weaver is None:
            raise RuntimeError(f"Verified AspectJ {aspectj_runtime.VERSION} required. Use Install Java + AspectJ.")
        cp.extend([weaver, date_text_fix.verified_patch_path()])
        args.append("-javaagent:" + str(weaver))
        if _can_add_date_type_filter(mod_jars):
            args.append("-Dorg.aspectj.weaver.loadtime.configuration=" + ";".join((*AOP_DESCRIPTORS, date_text_fix.TYPE_FILTER)))
    elif mod_jars:
        for name, expected in LEGACY_ASPECTJ_HASHES.items():
            path = Path(_resource_path(name)).resolve(strict=True)
            with path.open("rb") as stream:
                if hashlib.file_digest(stream, "sha256").hexdigest() != expected:
                    raise RuntimeError(f"Bundled AspectJ integrity check failed: {path}")
            cp.append(path)
        weaver = cp[0]
        args.append("-javaagent:" + str(weaver))
    cp.extend(mod_jars)
    cp.append(Path(game_jar).resolve())
    if any(os.pathsep in str(entry) or "*" in str(entry) for entry in cp):
        raise RuntimeError(f"A launch path contains a classpath separator ({os.pathsep}) or wildcard.")
    env = {key: value for key, value in os.environ.items() if key.upper() not in JVM_INJECTION_ENV}
    env["PATH"] = os.pathsep.join(native_paths + [env.get("PATH", "")])
    if Path(java).is_absolute():
        env["JAVA_HOME"] = str(Path(java).parent.parent)
    report("Effective classpath (in order):\n  " + "\n  ".join(map(str, cp)))
    return [str(java), *args, "-cp", os.pathsep.join(map(str, cp)), main], env
