import os
from pathlib import Path


SPACE_HAVEN_APP_ID = "979110"


def normalize_path(path):
    return os.path.normpath(os.path.abspath(path))


def resolve_workshop_path(game_path):
    if not game_path:
        return None

    try:
        game_path = Path(game_path).resolve()
    except OSError:
        game_path = Path(game_path).absolute()

    for parent in [game_path] + list(game_path.parents):
        if parent.name.lower() == "steamapps":
            workshop_path = parent / "workshop" / "content" / SPACE_HAVEN_APP_ID
            return str(workshop_path) if workshop_path.exists() else None

    return None

