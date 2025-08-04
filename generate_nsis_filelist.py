import os
import importlib.util

# Load version from version.py
spec = importlib.util.spec_from_file_location("version", "version.py")
version_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(version_module)
VERSION = version_module.version

BUILD_DIR = "build/spacehaven-modloader"
OUT_FILE = "FILE_LIST.nsh"
INSTALLER_TEMPLATE = "installer_template.nsi"
INSTALLER_OUTPUT = "installer.nsi"

if not os.path.isdir(BUILD_DIR):
    raise SystemExit(f"Build directory not found: {BUILD_DIR}")

lines = []

for root, dirs, files in os.walk(BUILD_DIR):
    rel_dir = os.path.relpath(root, BUILD_DIR)
    if rel_dir != ".":
        lines.append(f'CreateDirectory "$INSTDIR\\{rel_dir}"')

    for fname in files:
        rel_path = os.path.relpath(os.path.join(root, fname), BUILD_DIR)
        # Just single backslashes — NSIS handles them fine
        lines.append(f'StrCpy $CurrentFile "{rel_path}"')
        lines.append(f'File "/oname={rel_path}" "{os.path.join(BUILD_DIR, rel_path)}"')

with open(OUT_FILE, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print(f"[NSIS] Wrote {len(lines)} entries to {OUT_FILE}")

# Inject version into installer.nsi
with open(INSTALLER_TEMPLATE, "r", encoding="utf-8") as f:
    template = f.read()

template = template.replace("{{VERSION}}", VERSION)

with open(INSTALLER_OUTPUT, "w", encoding="utf-8") as f:
    f.write(template)

print(f"[NSIS] Generated {INSTALLER_OUTPUT} with version {VERSION}")
