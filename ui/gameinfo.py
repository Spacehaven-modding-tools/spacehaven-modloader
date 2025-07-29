from zipfile import ZipFile

import ui.log


class GameInfo:
    def __init__(self, jarPath):
        self.jarPath = jarPath

        self.detectVersion()

    def detectVersion(self):
        ui.log.log("Loading game information...")
        with ZipFile(self.jarPath, "r") as spacehaven:
            self.version = spacehaven.read("version.txt").decode("utf-8").split("\n")[0].strip()
            # second line is "alpha 8, which is useless. Don't know where the "build 3" comes from

        ui.log.log("  Version: {}".format(self.version))
