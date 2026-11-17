import os
from pathlib import Path
import sys


SPACE_HAVEN_APP_ID = "979110"


def loader_directory():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def normalize_path(path):
    return os.path.normpath(os.path.abspath(path))


def resolve_steamapps(game_path):
    if not game_path:
        return None

    try:
        game_path = Path(game_path).resolve()
    except OSError:
        game_path = Path(game_path).absolute()

    for parent in [game_path] + list(game_path.parents):
        if parent.name.lower() == "steamapps":
            return parent

    return None


def resolve_workshop_path(game_path):
    steamapps = resolve_steamapps(game_path)
    if steamapps is None:
        return None
    workshop_path = steamapps / "workshop" / "content" / SPACE_HAVEN_APP_ID
    return str(workshop_path) if workshop_path.is_dir() else None

