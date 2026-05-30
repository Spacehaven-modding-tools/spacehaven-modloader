from zipfile import ZipFile

import ui.log


class GameInfo:
    def __init__(self, jarPath):
        self.jarPath = jarPath

        self.detectVersion()

    def detectVersion(self):
        ui.log.log("Loading game information...")
        self.version = ""
        try:
            with ZipFile(self.jarPath, "r") as spacehaven:
                self.version = spacehaven.read("version.txt").decode("utf-8").split("\n")[0].strip()
                # second line is "alpha 8, which is useless. Don't know where the "build 3" comes from
        except KeyError:
            ui.log.log("  Could not find version.txt inside {}".format(self.jarPath))
        except Exception as ex:
            ui.log.log("  Could not read game version from {}: {}".format(self.jarPath, ex))

        ui.log.log("  Version: {}".format(self.version))

    @staticmethod
    def jvm_has_module_system() -> bool:
        # JVM shipped with the game does not have the Java module system
        # TODO handle alternative JVM usage that may have the module system
        return False
