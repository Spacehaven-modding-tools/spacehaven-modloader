#!/usr/bin/env python3
"""Rebuild the DateFix aspect with javac and the bundled AspectJ 1.9.19 API."""
import argparse
from hashlib import sha256
import os
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory
from zipfile import ZipFile, ZipInfo

TOOL_DIR = Path(__file__).resolve().parent
ROOT = TOOL_DIR.parents[1]
SOURCE = TOOL_DIR / "src"
JAR = TOOL_DIR / "shl-locale-datefix.jar"
PIN = ROOT / "ui" / "date_text_fix.py"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--update-hash", action="store_true")
    args = parser.parse_args()
    with TemporaryDirectory(prefix=".shl-datefix-", dir=ROOT) as scratch:
        temp = Path(scratch)
        api = temp / "aspectjrt.jar"
        with ZipFile(ROOT / "aspectj-1.9.19.jar") as installer:
            api.write_bytes(installer.read("files/lib/aspectjrt.jar"))
        classes = temp / "classes"
        subprocess.run([
            "javac", "--release", "8", "-g", "-encoding", "UTF-8", "-Xlint:-options",
            "-classpath", str(api), "-d", str(classes),
            str(SOURCE / "shl/locale/SaveDateTextNormalizer.java"),
        ], check=True, timeout=60)
        entries = [(path.relative_to(classes).as_posix(), path) for path in classes.rglob("*.class")]
        entries.extend((path.relative_to(SOURCE).as_posix(), path) for path in (SOURCE / "META-INF").glob("*.xml"))
        stage = temp / JAR.name
        with ZipFile(stage, "w") as output:
            for name, path in sorted(entries):
                entry = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                entry.external_attr = 0o644 << 16
                data = path.read_bytes()
                if path.suffix == ".xml":
                    data = data.replace(b"\r\n", b"\n")
                output.writestr(entry, data)
        digest = sha256(stage.read_bytes()).hexdigest()
        source = PIN.read_text(encoding="utf-8")
        updated, count = re.subn(r'(?m)^SHA256 = "[a-f0-9]{64}"$', f'SHA256 = "{digest}"', source)
        if count != 1:
            sys.exit("Could not locate the DateFix SHA-256 pin")
        if updated != source and not args.update_hash:
            sys.exit(f"SHA-256 differs from pinned digest: {digest}")
        if args.update_hash and updated != source:
            staged_pin = temp / PIN.name
            staged_pin.write_text(updated, encoding="utf-8")
            os.replace(staged_pin, PIN)
        os.replace(stage, JAR)
    print(f"Built {JAR.name} with SHA-256 {digest}")


if __name__ == "__main__":
    main()
