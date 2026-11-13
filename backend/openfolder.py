"""Open one of the panel's own folders in the system file manager.

The browser only sends a key ("backups", "server", "data"); the path is always built here
from store.DATA, never taken from the browser."""
import os
import subprocess
import sys

from . import store

KEYS = ("backups", "server", "data", "logs")


class OpenError(Exception):
    pass


def resolve(key: str, sid: str | None):
    if key not in KEYS:
        raise OpenError("Unknown folder.")
    if key == "data":
        path = store.DATA
    elif key == "logs":
        path = store.DATA / "logs"
    else:
        if not sid or not store.valid_id(sid):
            raise OpenError("Pick a server first.")
        path = store.backup_dir(sid) if key == "backups" else store.server_dir(sid)
    path.mkdir(parents=True, exist_ok=True)
    return path


def open_folder(key: str, sid: str | None = None) -> str:
    path = resolve(key, sid)
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(path))  # noqa: S606 (path built from store.DATA only)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (OSError, FileNotFoundError) as e:
        raise OpenError(f"Could not open the folder. It is here: {path}") from e
    return str(path)
