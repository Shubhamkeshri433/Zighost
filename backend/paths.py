"""Where things live, for both a source checkout and a packaged (PyInstaller) Windows app."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from . import brand

FROZEN = bool(getattr(sys, "frozen", False))
# Read-only program files (frontend, assets). In a packaged app PyInstaller unpacks them next to the exe.
BASE = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
FRONTEND = BASE / "frontend"


def _is_windows() -> bool:
    return os.name == "nt"


def default_data_dir() -> Path:
    """Where servers, backups and settings are kept.

    ZIGHOST_DATA (or the older MCPANEL_DATA) wins. A packaged app uses %APPDATA%\\zighost, so updating or
    reinstalling never touches worlds. A source checkout keeps using ./data next to the code (start.bat)."""
    for var in ("ZIGHOST_DATA", "MCPANEL_DATA"):
        if os.environ.get(var):
            return Path(os.environ[var])
    if FROZEN:
        if _is_windows():
            return Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") / brand.DATA_KEY
        return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / brand.DATA_KEY
    return BASE / "data"
