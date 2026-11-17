"""Local diagnostic ZIP export. Never uploads telemetry or includes savegames."""
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import zipfile

from ui.runtime_manager import state_dir

LOG_NAMES = ("logs.txt", "java8-game.log", "java25-game.log", "java27-game.log")
MAX_LOG_BYTES = 5 * 1024 * 1024


def export_logs(game_executable, destination):
    """Export bounded logs on explicit request; user should inspect before sharing."""
    destination = Path(destination).expanduser().resolve()
    directory = state_dir(game_executable)
    found = []
    for name in LOG_NAMES:
        path = directory / name
        if path.is_file() and not path.is_symlink():
            found.append((name, path))
    report = {
        "export_time_utc": datetime.now(timezone.utc).isoformat(),
        "modloader": "Space Haven Mod Loader Java 25/27 fork",
        "platform": platform.system(),
        "architecture": platform.machine(),
        "logs_collected": [name for name, _ in found],
        "privacy_warning": "Logs may contain Steam paths, Windows username, mod names or other private information. Review before sharing.",
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("diagnostics.json", json.dumps(report, indent=2))
        for name, path in found:
            with open(path, "rb") as handle:
                data = handle.read(MAX_LOG_BYTES + 1)
            if len(data) > MAX_LOG_BYTES:
                data = data[:MAX_LOG_BYTES] + b"\n[TRUNCATED: log exceeds 5 MiB]\n"
            archive.writestr(name, data)
    return len(found)
