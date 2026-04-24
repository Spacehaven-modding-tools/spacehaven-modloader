import os
import sys

import version


class Logger:
    """Logger that writes to the modloader diagnostics folder once the game is located."""

    def __init__(self):
        self.gameLog = None
        self.localLog = None
        self.localPath = None
        self.bufferedMessages = []

        print("Buffering logs until the Space Haven folder is detected...")

        self.logInitialInfo()

    def setGameModPath(self, path):
        dataDir = os.path.join(path, "modloader")
        os.makedirs(dataDir, exist_ok=True)
        newPath = os.path.join(dataDir, "logs.txt")

        if self.localPath is None or os.path.abspath(newPath) != os.path.abspath(self.localPath):
            try:
                if self.localLog:
                    self.localLog.close()
            except Exception:
                pass
            self.localPath = newPath
            self.localLog = open(self.localPath, "w")
            for message in self.bufferedMessages:
                self.localLog.write(message + "\n")
            self.localLog.flush()
            self.bufferedMessages = []
            print("Started logging to {}...".format(self.localPath))

        if self.gameLog:
            try:
                self.gameLog.close()
            except Exception:
                pass
            self.gameLog = None

        self.logInitialInfo()
        self.log("Logging to {}".format(self.localPath))

    def logInitialInfo(self):
        self.log("Space Haven Modloader v{}".format(version.version))
        self.log(f"version defined by {version.source}")
        self.log(f"Python: {sys.implementation.name} {sys.version}")

    def log(self, message=""):
        print("[LOG] {}".format(message))
        if self.localLog:
            self.localLog.write(message + "\n")
            self.localLog.flush()
        else:
            self.bufferedMessages.append(message)

        if self.gameLog:
            self.gameLog.write(message + "\n")
            self.gameLog.flush()

    def updateBackgroundState(self, message):
        self.backgroundState = message


logger = Logger()
log = logger.log
updateBackgroundState = updateLaunchState = logger.updateBackgroundState
setGameModPath = logger.setGameModPath
