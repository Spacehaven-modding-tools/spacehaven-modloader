import os
import subprocess
import sys

import ui.log
from ui import launch_config, launch_session, runtime_manager


def _crash_report_stamp(path):
    try:
        stat = path.stat()
    except FileNotFoundError:
        return None
    return stat.st_ino, stat.st_mtime_ns, stat.st_size


def run(game_executable, game_jar, mods, java, major, version, process_file):
    """Launch with the prepared, installation-scoped classpath and bundled natives."""
    ui.log.updateBackgroundState("Running")
    command, env = launch_config.build(game_executable, game_jar, mods, java, major, report=ui.log.log)
    log_path = runtime_manager.state_dir(game_executable) / f"java{major}-game.log"
    game_dir = runtime_manager.game_directory(game_executable)
    crash_path = game_dir / "crash.txt"
    previous_crash = _crash_report_stamp(crash_path)
    ui.log.log(f"Java {major} | {version} | {java}")
    with log_path.open("w", encoding="utf-8", errors="replace") as game_log:
        game_log.write(f"{version}\nGame JAR: {game_jar}\n")
        game_log.flush()
        code = launch_session.run(
            command, process_file, cwd=game_dir,
            env=env, stdout=game_log, stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    ui.log.log(f"Space Haven Java {major} exited with code {code}. Game output: {log_path}")
    current_crash = _crash_report_stamp(crash_path)
    if current_crash is not None and current_crash != previous_crash:
        raise RuntimeError(f"Space Haven wrote a crash report (exit code {code}). See {crash_path} and {log_path}")
    if code:
        raise RuntimeError(f"Space Haven Java {major} exited with code {code}. See {log_path}")


def open(path):
    """Open a path in an OS-native way."""
    if path is None:
        return
    if sys.platform == "win32":
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.call(["open", "-R", path])
    else:
        subprocess.call(["xdg-open", path])
