import sys
from cx_Freeze import setup, Executable

import version

# Dependencies are automatically detected, but it might need fine tuning.
build_exe_options = {
    "packages": ["six", "pkg_resources._vendor"],
    "includes": ["vdf"],
    "excludes": [],
    "include_files": ["textures_annotations.xml", "aspectj-1.9.19.jar", "aspectjweaver-1.9.19.jar"],
}

# GUI applications require a different base on Windows (the default is for a
# console application).
base = None
if sys.platform == "win32":
    base = "Win32GUI"

APP = ["spacehaven-modloader.py"]
DATA_FILES = [
    (
        "spacehaven-modloader",
        [
            "textures_annotations.xml",
        ],
    ),
]
OPTIONS = {}

setup(
    name="spacehaven-modloader",
    version=version.version,
    options={"build_exe": build_exe_options},
    executables=[Executable("spacehaven-modloader.py", base=base)],
)
