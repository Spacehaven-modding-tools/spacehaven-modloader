from collections import deque
from contextlib import contextmanager, suppress
import os
from pathlib import Path
import sys
import traceback

import version


def startup_log_path():
    if sys.platform == "win32":
        directory = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        directory = Path.home() / "Library" / "Logs"
    else:
        directory = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state")
    return directory / "spacehaven-modloader" / "startup.log"


def _console(message):
    stream = sys.stdout
    if stream is None:
        return
    try:
        print(message, file=stream)
    except UnicodeEncodeError:
        encoding = getattr(stream, "encoding", None) or "ascii"
        try:
            print(message.encode(encoding, errors="backslashreplace").decode(encoding), file=stream)
        except (OSError, ValueError):
            pass
    except (OSError, ValueError):
        pass


def _write_log(stream, message):
    try:
        stream.write(message + "\n")
        stream.flush()
    except (OSError, ValueError) as error:
        _console(f"[LOG] Could not write log: {error}")


class Logger:
    """Write UTF-8 startup and game logs independently of the console."""

    def __init__(self):
        self.localLog = None
        self.localPath = None
        self.startupLog = None
        self.startupPath = None
        self.bufferedMessages = deque(maxlen=200)
        self.logInitialInfo()

    @contextmanager
    def startup_logging(self):
        path = startup_log_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            self.startupLog = path.open("w", encoding="utf-8", errors="replace")
        except OSError as error:
            self.log(f"Could not open startup log {path}: {error}")
        else:
            self.startupPath = path
            for message in self.bufferedMessages:
                _write_log(self.startupLog, message)
        try:
            yield
        except Exception:
            self.log("Mod Loader startup failed:\n" + traceback.format_exc())
            raise
        finally:
            if self.startupLog:
                with suppress(OSError):
                    self.startupLog.close()
                self.startupLog = None

    def setGameModPath(self, path):
        dataDir = os.path.join(path, "modloader")
        newPath = os.path.abspath(os.path.join(dataDir, "logs.txt"))
        if self.localPath == newPath:
            return
        if self.localLog:
            with suppress(OSError):
                self.localLog.close()
        self.localLog = self.localPath = None
        try:
            os.makedirs(dataDir, exist_ok=True)
            self.localLog = open(newPath, "a", encoding="utf-8", errors="replace")
        except OSError as error:
            self.log(f"Could not open game log {newPath}: {error}")
            return
        self.localPath = newPath
        for message in self.bufferedMessages:
            _write_log(self.localLog, message)
        self.bufferedMessages.clear()

        self.logInitialInfo()
        self.log("Logging to {}".format(self.localPath))

    def logInitialInfo(self):
        self.log("Space Haven Modloader v{}".format(version.version))
        self.log(f"version defined by {version.source}")
        self.log(f"Python: {sys.implementation.name} {sys.version}")

    def log(self, message=""):
        if self.startupLog:
            _write_log(self.startupLog, message)
        if self.localLog:
            _write_log(self.localLog, message)
        else:
            self.bufferedMessages.append(message)
        _console(f"[LOG] {message}")

    def updateBackgroundState(self, message):
        self.backgroundState = message


logger = Logger()
log = logger.log
updateBackgroundState = updateLaunchState = logger.updateBackgroundState
setGameModPath = logger.setGameModPath
