"""Pure-Python regression checks for the optional Java 27 launcher.

These validate the command and protections, not compatibility of Space Haven
or any third-party Java agents with the Java 27 VM.
"""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from ui import runtime_manager as rt


class RuntimeManagerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name) / "Space Haven"
        self.base.mkdir()
        self.exe = self.base / "spacehaven.exe"
        self.exe.touch()
    def test_default_is_unmodified_game(self):
        self.assertEqual(rt.get_mode(self.exe), rt.MODE_ORIGINAL)
        self.assertFalse(rt.preferences_path(self.exe).exists())

    def test_store_runtime_preference(self):
        rt.set_mode(self.exe, rt.MODE_TEMURIN)
        self.assertEqual(rt.get_mode(self.exe), rt.MODE_TEMURIN)
        self.assertEqual(json.loads(rt.preferences_path(self.exe).read_text())["schema"], 1)
        rt.set_mode(self.exe, rt.MODE_ORIGINAL)
        self.assertEqual(rt.get_mode(self.exe), rt.MODE_ORIGINAL)

    def test_reject_bad_mode(self):
        with self.assertRaises(ValueError):
            rt.set_mode(self.exe, "garbage")

    def test_archive_rejects_traversal(self):
        f = Path(self.tmp.name) / "evil.zip"
        with ZipFile(f, "w") as z:
            z.writestr("../escape.txt", "escape")
        with self.assertRaises(rt.RuntimeErrorDetail):
            rt._unpack_safe(f, Path(self.tmp.name) / "unpacked")
        self.assertFalse((Path(self.tmp.name) / "escape.txt").exists())

    def test_archive_rejects_zip_symlink(self):
        from zipfile import ZipInfo
        f = Path(self.tmp.name) / "evil.zip"
        info = ZipInfo("some-link")
        info.create_system = 3
        info.external_attr = (0o120777 << 16)
        with ZipFile(f, "w") as z:
            z.writestr(info, "../../evil")
        with self.assertRaises(rt.RuntimeErrorDetail):
            rt._unpack_safe(f, Path(self.tmp.name) / "unpacked")

    def test_archive_rejects_windows_reserved_names_and_duplicate_paths(self):
        for index, entries in enumerate((("bin/java.exe:alias",), ("bin/NUL.dll",), ("bin/Java.exe", "bin/java.exe"))):
            with self.subTest(entries=entries):
                archive = Path(self.tmp.name) / f"invalid{index}.zip"
                with ZipFile(archive, "w") as output:
                    for entry in entries:
                        output.writestr(entry, "fixture")
                with self.assertRaises(rt.RuntimeErrorDetail):
                    rt._unpack_safe(archive, Path(self.tmp.name) / f"unpacked{index}")

    @patch.object(rt, "platform_artifact", return_value=("windows", "x64"))
    def test_verify_checks_major(self, _platform):
        from subprocess import CompletedProcess
        with patch.object(rt.subprocess, "run", return_value=CompletedProcess([], 0, "", 'openjdk version "25.0.5"')):
            with self.assertRaises(rt.RuntimeErrorDetail):
                rt.verify_java("/tmp/java")
        with patch.object(rt.subprocess, "run", return_value=CompletedProcess([], 0, "", '    os.arch = amd64\nopenjdk version "27.0.1"')):
            self.assertIn("27.0.1", rt.verify_java("/tmp/java"))

    def test_official_package_version_and_sha(self):
        correct = {"version": {"major": 27}, "binary": {"architecture": "x64", "os": "windows", "image_type": "jre", "jvm_impl": "hotspot", "package": {"link": "https://github.com/adoptium/temurin27-binaries/releases/download/latest/test.zip", "checksum": "d"*64}}}
        with patch.object(rt, "_request_json", return_value=[correct]), patch.object(rt, "platform_artifact", return_value=("windows", "x64")):
            link, digest, release = rt.release_package()
        self.assertTrue(link.startswith("https://github.com/"))
        self.assertEqual(digest, "d"*64)

    def test_installer_does_not_download_implicitly(self):
        with patch.object(rt, "release_package", side_effect=AssertionError("must not download")):
            self.assertIsNone(rt.installed_java(self.exe))
            self.assertEqual(rt.get_mode(self.exe), rt.MODE_ORIGINAL)

    def test_install_flow_uses_verified_staging_and_private_dir(self):
        archive_path = Path(self.tmp.name) / "mock-temurin.zip"
        with ZipFile(archive_path, "w") as archive:
            archive.writestr("jdk-27-jre/bin/java", "#!/bin/sh\nexit 0\n")
            archive.writestr("jdk-27-jre/lib/modules", "test libraries")
            archive.writestr("jdk-27-jre/release", 'JAVA_VERSION="27"')

        def mocked_download(_url, _sha, target):
            import shutil
            shutil.copyfile(archive_path, target)
            return archive_path.stat().st_size

        with patch.object(rt, "release_package", return_value=("https://github.com/adoptium/temurin27-binaries/test.zip", "0" * 64, "test release")), \
             patch.object(rt, "_download_verified", side_effect=mocked_download), \
             patch.object(rt, "verify_java", return_value='    os.arch = amd64\nopenjdk version "27.0.1"'), \
             patch.object(rt.platform, "system", return_value="Linux"):
            java = rt.install_temurin27(self.exe)
            self.assertTrue(java.is_file())
            self.assertEqual(java.parts[-4:], ("runtimes", "temurin-27", "bin", "java"))
            self.assertEqual(java.read_text().splitlines()[0], "#!/bin/sh")
            self.assertEqual(rt.installed_java(self.exe), java)
            (java.parent.parent / "lib" / "modules").write_bytes(b"tampered")
            self.assertIsNone(rt.installed_java(self.exe))

    def test_macos_directory(self):
        self.assertEqual(rt.game_directory(self.base / "spacehaven.app"), self.base / "spacehaven.app" / "Contents" / "Resources")


if __name__ == "__main__":
    unittest.main()
