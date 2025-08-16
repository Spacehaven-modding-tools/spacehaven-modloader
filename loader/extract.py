import ui.log

import loader.assets.explode
import loader.assets.library


def extract(jarPath, corePath):
    """Extract and annotate game assets"""

    ui.log.log("Running extract & annotate")

    ui.log.updateBackgroundState("Extracting game files")
    loader.assets.library.extract(jarPath, corePath)

    ui.log.updateBackgroundState("Unpacking textures")
    loader.assets.explode.explode(corePath)
