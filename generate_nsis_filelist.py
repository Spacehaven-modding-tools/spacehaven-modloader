import os
import importlib.util
import argparse

# Load version from version.py
spec = importlib.util.spec_from_file_location("version", "version.py")
version_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(version_module)
VERSION = version_module.version

parser = argparse.ArgumentParser(description="Generate NSIS lists for a frozen Mod Loader build.")
parser.add_argument("--build-dir", default="build/spacehaven-modloader")
BUILD_DIR = parser.parse_args().build_dir
OUT_FILE = "FILE_LIST.nsh"
UNINSTALL_FILE = "UNINSTALL_FILE_LIST.nsh"
INSTALLER_TEMPLATE = "installer_template.nsi"
INSTALLER_OUTPUT = "installer.nsi"
LOCAL_PREFERENCES = {"previous_spacehaven_path.txt", "extra_mods_path.txt"}

if not os.path.isdir(BUILD_DIR):
    raise SystemExit(f"Build directory not found: {BUILD_DIR}")

lines = []
uninstall_files = []
uninstall_dirs = []

for root, dirs, files in os.walk(BUILD_DIR):
    dirs.sort()
    files.sort()
    rel_dir = os.path.relpath(root, BUILD_DIR)
    destination = "$INSTDIR" if rel_dir == "." else f"$INSTDIR\\{rel_dir}"
    lines.append(f'SetOutPath "{destination}"')
    if rel_dir != ".":
        uninstall_dirs.append(f'RMDir "{destination}"')

    for fname in files:
        if fname in LOCAL_PREFERENCES:
            continue
        rel_path = os.path.relpath(os.path.join(root, fname), BUILD_DIR)
        if "$" in rel_path or '"' in rel_path:
            raise SystemExit(f"Unsafe NSIS build filename: {rel_path}")
        lines.append(f'File "{os.path.join(BUILD_DIR, rel_path)}"')
        uninstall_files.append(f'Delete "{destination}\\{fname}"')

with open(OUT_FILE, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
with open(UNINSTALL_FILE, "w", encoding="utf-8") as f:
    f.write("\n".join(uninstall_files + list(reversed(uninstall_dirs))))

print(f"[NSIS] Wrote {len(lines)} entries to {OUT_FILE}")

# Inject version into installer.nsi
with open(INSTALLER_TEMPLATE, "r", encoding="utf-8") as f:
    template = f.read()

template = template.replace("{{VERSION}}", VERSION)

with open(INSTALLER_OUTPUT, "w", encoding="utf-8") as f:
    f.write(template)

print(f"[NSIS] Generated {INSTALLER_OUTPUT} with version {VERSION}")
