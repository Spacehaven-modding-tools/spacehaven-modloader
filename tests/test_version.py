import version
import tomllib
import unittest


class VersionTest(unittest.TestCase):
    def setUp(self):
        path = "pyproject.toml"
        with open(path, "rb") as f:
            self.toml = tomllib.load(f)

    def test_version(self):
        assert version.version == self.toml.get("project", {}).get("version")
