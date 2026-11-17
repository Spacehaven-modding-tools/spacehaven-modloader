"""Coordinate loader launches for one Space Haven installation."""
from contextlib import contextmanager
import os
import subprocess

from ui import runtime_manager


def _process_exists(pid):
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        process = kernel.OpenProcess(0x00100000, False, pid)
        if not process:
            return ctypes.get_last_error() != 87  # ERROR_INVALID_PARAMETER (PID absent)
        try:
            return kernel.WaitForSingleObject(process, 0) != 0  # WAIT_OBJECT_0 (exited)
        finally:
            kernel.CloseHandle(process)
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


@contextmanager
def installation_lock(game_executable):
    directory = runtime_manager.state_dir(game_executable)
    directory.mkdir(parents=True, exist_ok=True)
    lock = directory / "launch.lock"
    with lock.open("a+b") as handle:
        if not handle.tell():
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise RuntimeError("Another Mod Loader instance is using this installation.") from exc
        # Closing the handle releases the lock even after an unexpected exit.
        process_file = directory / "game.pid"
        if process_file.exists():
            try:
                pid = int(process_file.read_text(encoding="ascii"))
                if not 0 < pid <= 0xFFFFFFFF:
                    raise ValueError("invalid PID")
            except (OSError, ValueError) as exc:
                raise RuntimeError(f"Cannot verify the previous game process: {process_file}") from exc
            if _process_exists(pid):
                raise RuntimeError(f"A previous loader game process may still be running (PID {pid}).")
            process_file.unlink()
        yield process_file


def run(command, process_file, **kwargs):
    # A loader crash leaves the PID and its immutable classpath in place.
    with subprocess.Popen(command, **kwargs) as child:
        try:
            process_file.write_text(str(child.pid), encoding="ascii")
        except OSError:
            # The current instance still holds the lock. Let the game exit
            # normally, especially if the player has already started a save.
            child.wait()
            raise
        code = child.wait()
        process_file.unlink(missing_ok=True)
        return code
