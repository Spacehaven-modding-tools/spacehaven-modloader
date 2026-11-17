"""Build a frozen Mod Loader with checkout-relative traceback paths."""
import os
from pathlib import Path
import sys

from cx_Freeze import setup


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    sys.path.insert(0, str(root))
    setup(
        options={"build_exe": {"replace_paths": [(str(root), "."), ("*", ".")]}},
        script_args=["build_exe", *sys.argv[1:]],
    )
