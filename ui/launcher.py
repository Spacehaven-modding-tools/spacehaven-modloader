import os
import subprocess
import sys

import ui.log


def launchAndWait(path):
    """Launch the game and wait for it to exit"""
    ui.log.updateBackgroundState("Running")

    # FIXME cloud credentials aren't found when launching from the modloader.
    # cwd issue ?? apparently not as the cwd doesnt change anything...
    from_dir = os.path.dirname(path)
    if sys.platform == "darwin":
        subprocess.call(["open", path, "-W"])
    else:
        subprocess.call([path], cwd=from_dir)


def open(path):
    """Open a path in an OS-native way"""

    if path is None:
        return

    if sys.platform == "win32":
        os.startfile(path)
    elif sys.platform == "darwin":
        # Can't use `open path` when path is inside a .app bundle — macOS
        # resolves up to the .app and launches the game instead of the folder.
        # AppleScript's `reveal` navigates inside bundles correctly.
        subprocess.call(["osascript", "-e", f'tell application "Finder" to reveal POSIX file "{path}"'])
        subprocess.call(["osascript", "-e", 'tell application "Finder" to activate'])
    else:
        subprocess.call(["xdg-open", path])
