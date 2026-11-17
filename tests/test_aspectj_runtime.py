import hashlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from ui import aspectj_runtime as aj


class AspectJInstallationTests(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.exe = Path(scratch.name) / "spacehaven.exe"
        archive = io.BytesIO()
        with ZipFile(archive, "w") as jar:
            jar.writestr("META-INF/MANIFEST.MF", "Premain-Class: org.aspectj.weaver.loadtime.Agent\n")
            jar.writestr("org/aspectj/weaver/loadtime/Agent.class", b"a")
            jar.writestr("org/aspectj/lang/JoinPoint.class", b"b")
        self.data = archive.getvalue()
        patcher = patch.object(aj, "SHA256", hashlib.sha256(self.data).hexdigest())
        patcher.start()
        self.addCleanup(patcher.stop)

    def download(self, data, url=None):
        response = io.BytesIO(data)
        response.geturl = lambda: url or aj.MAVEN_BASE + aj.ARTIFACT
        return patch.object(aj.urllib.request, "urlopen", return_value=response)

    def test_installs_exact_artifact_and_detects_tampering(self):
        with self.download(self.data):
            installed = aj.install_aspectj(self.exe)
        self.assertEqual(aj.installed_aspectj(self.exe), installed)
        installed.write_bytes(self.data + b"tampered")
        self.assertIsNone(aj.installed_aspectj(self.exe))

    def test_repair_keeps_previous_agent(self):
        target = aj.installed_artifact_path(self.exe)
        target.parent.mkdir(parents=True)
        target.write_bytes(b"partial install")
        with self.download(self.data):
            self.assertEqual(aj.install_aspectj(self.exe), target)
        copies = list(target.parent.glob("previous-*/*.jar"))
        self.assertEqual([b"partial install"], [item.read_bytes() for item in copies])

    def test_wrong_pinned_hash_does_not_publish(self):
        with self.download(b"wrong release"):
            with self.assertRaisesRegex(aj.AspectJRuntimeError, "SHA-256"):
                aj.install_aspectj(self.exe)
        self.assertFalse(aj.installed_artifact_path(self.exe).exists())

    def test_redirect_to_other_url_rejected(self):
        with self.download(self.data, "https://example.test/agent.jar"):
            with self.assertRaisesRegex(aj.AspectJRuntimeError, "location"):
                aj.install_aspectj(self.exe)
