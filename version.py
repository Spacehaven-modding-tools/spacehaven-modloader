from importlib.metadata import version as metadata_version, PackageNotFoundError
import tomllib


def get_version():
    try:
        # Use the name defined in [project] name in pyproject.toml
        return metadata_version("spacehaven-modloader"), "metadata"
    except PackageNotFoundError:
        try:
            path = "pyproject.toml"
            with open(path, "rb") as f:
                return tomllib.load(f)["project"]["version"], "toml"
        except FileNotFoundError:
            pass
        return "0.0.0", "unknown"


version, source = get_version()
