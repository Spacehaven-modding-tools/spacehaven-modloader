"""Exercise game crash reporting independently of the process exit code."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from ui import launcher, runtime_manager


class GameExitTests(TestCase):
    def setUp(self):
        scratch = TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.game_dir = Path(scratch.name)
        self.exe = self.game_dir / "spacehaven.exe"
        self.state = runtime_manager.state_dir(self.exe)
        self.state.mkdir(parents=True)
        self.crash_path = self.game_dir / "crash.txt"

    def launch(self):
        launcher.run(self.exe, self.exe.with_suffix(".jar"), [], "java", 27, "Java 27", self.state / "game.pid")

    @patch.object(launcher.launch_config, "build", return_value=(["java"], {}))
    def test_report_written_during_exit_zero_is_a_crash(self, _build):
        self.crash_path.write_text("old report", encoding="utf-8")

        def exit_after_crash(*_args, **_kwargs):
            self.crash_path.write_text("new crash report", encoding="utf-8")
            return 0

        with patch.object(launcher.launch_session, "run", side_effect=exit_after_crash):
            with self.assertRaisesRegex(RuntimeError, "crash report .*exit code 0"):
                self.launch()

    @patch.object(launcher.launch_config, "build", return_value=(["java"], {}))
    @patch.object(launcher.launch_session, "run", return_value=0)
    def test_old_report_is_ignored_and_preserved_on_normal_exit(self, _run, _build):
        self.crash_path.write_text("old report", encoding="utf-8")
        self.launch()
        self.assertEqual("old report", self.crash_path.read_text(encoding="utf-8"))
