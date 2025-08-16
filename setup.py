import sys
from cx_Freeze import setup, Executable
import version

build_exe_options = {
    "build_exe": "build/spacehaven-modloader",
    "packages": ["lxml", "png", "rectpack", "zipfile39"],
    "includes": ["vdf"],
    "include_files": [
        "spacehaven-modloader.png",
        "textures_annotations.xml",
        "aspectj-1.9.19.jar",
        "aspectjweaver-1.9.19.jar",
    ],
}

# Windows GUI app: use Win32GUI base
base = "Win32GUI" if sys.platform == "win32" else None

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
    description="Space Haven Mod Loader",
    options={"build_exe": build_exe_options},
    executables=[Executable("spacehaven-modloader.py", base=base)],
)
