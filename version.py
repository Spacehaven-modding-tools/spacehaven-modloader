from importlib.metadata import version as metadata_version, PackageNotFoundError
from pathlib import Path
import sys
import tomllib


def get_version():
    if not getattr(sys, "frozen", False):
        try:
            with Path(__file__).with_name("pyproject.toml").open("rb") as source:
                return tomllib.load(source)["project"]["version"], "toml"
        except FileNotFoundError:
            pass
    try:
        return metadata_version("spacehaven-modloader"), "metadata"
    except PackageNotFoundError:
        return "0.0.0", "unknown"


version, source = get_version()
