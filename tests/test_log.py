from contextlib import redirect_stdout
import io
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
from zipfile import ZipFile

from lxml import etree

from loader.assets.patch import doPatchType
from ui.diagnostics import export_logs
from ui.log import Logger


class LogTests(TestCase):
    def test_multilingual_text_patch_with_legacy_console(self):
        text = "日本語 简体中文 한국어 Русский"
        location = "library/texts"
        library = {location: etree.XML(b"<data><texts/></data>")}
        operation = etree.XML(
            (
                '<Operation Class="Add"><xpath>/data/texts</xpath>'
                f'<value><t id="1"><JP>{text}</JP></t></value></Operation>'
            ).encode("utf-8")
        )

        with TemporaryDirectory() as folder, io.TextIOWrapper(io.BytesIO(), encoding="cp1252") as console, redirect_stdout(console):
            logger = Logger()
            logger.setGameModPath(folder)
            with logger.localLog, patch("ui.log.log", logger.log):
                doPatchType(library, SimpleNamespace(variables=[]), operation, location)

            self.assertEqual(library[location].findtext("./texts/t/JP"), text)
            self.assertIn(text, (Path(folder) / "modloader" / "logs.txt").read_text(encoding="utf-8"))
            console.flush()
            self.assertIn(rb"\u65e5", console.buffer.getvalue())

    def test_startup_failure_is_logged_and_exported_without_game_path(self):
        with TemporaryDirectory() as folder, redirect_stdout(None):
            startup = Path(folder) / "state" / "startup.log"
            logger = Logger()
            with patch("ui.log.startup_log_path", return_value=startup), self.assertRaisesRegex(RuntimeError, "failed to open"):
                with logger.startup_logging():
                    logger.log("Initialising the window")
                    raise RuntimeError("failed to open")

            self.assertEqual(logger.startupPath, startup)
            self.assertIsNone(logger.startupLog)
            text = startup.read_text(encoding="utf-8")
            self.assertIn("Initialising the window", text)
            self.assertIn("RuntimeError: failed to open", text)

            bundle = Path(folder) / "logs.zip"
            self.assertEqual(export_logs(None, bundle, startup_log=startup), 1)
            with ZipFile(bundle) as archive:
                self.assertEqual(set(archive.namelist()), {"diagnostics.json", "startup.log"})
                self.assertEqual(archive.read("startup.log").decode("utf-8").replace("\r\n", "\n"), text)
