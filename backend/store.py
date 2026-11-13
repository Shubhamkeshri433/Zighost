"""Local JSON storage: settings and the server list. No database, no cloud."""
from __future__ import annotations

import json
import os
import re
import threading
import uuid
from pathlib import Path

from . import paths, winos

ROOT = paths.BASE
DATA = paths.default_data_dir()
SERVERS_DIR = DATA / "servers"
BACKUPS_DIR = DATA / "backups"
RUNTIME_DIR = DATA / "runtime"

ID_RE = re.compile(r"^[a-f0-9]{8}$")
THEMES = ("deepslate", "nether", "daylight")

DEFAULT_SETTINGS = {
    "java_path": "",
    "playit_path": "",
    "playit_address": "",       # manual override if detection fails
    "playit_secret": "",        # optional playit secret key (passed as SECRET_KEY)
    "contact": "",              # shown to download APIs (Paper asks for it)
    "playit_auto": True,        # start the playit agent together with the server
    "playit_mode": "managed",   # managed = panel runs its own helper; external = you run playit yourself
    "theme": "deepslate",
    "discord_webhook": "",      # optional Discord webhook link for notices
    "notify_server": False,     # tell Discord when a server starts, stops or crashes
    "notify_players": False,    # tell Discord when a player joins or leaves
    "jvm_args": "",             # extra Java arguments for every server
    "auto_restart": True,
    "tuned_flags": True,
    "default_ram_mb": 2048,
    "last_active": "",
    "keep_awake": True,         # Windows: do not let the PC sleep while a server runs
    "toasts": True,             # Windows: tray notices when a server starts, stops or crashes
}
SECRET_KEYS = ("playit_secret", "discord_webhook")      # encrypted on disk (Windows DPAPI)

_lock = threading.RLock()


def ensure_dirs() -> None:
    for d in (DATA, SERVERS_DIR, BACKUPS_DIR, RUNTIME_DIR):
        d.mkdir(parents=True, exist_ok=True)


def _read(path: Path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _write_atomic(path: Path, data) -> None:
    ensure_dirs()
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


# ---- settings -------------------------------------------------------------

def _sealed(s: dict) -> dict:
    out = dict(s)
    for k in SECRET_KEYS:
        out[k] = winos.seal(str(out.get(k, "")))
    return out


def get_settings() -> dict:
    with _lock:
        raw = _read(DATA / "settings.json", {})
        s = dict(DEFAULT_SETTINGS)
        s.update(raw)
        if winos.IS_WINDOWS and any(raw.get(k) and not str(raw[k]).startswith(winos.PREFIX) for k in SECRET_KEYS):
            _write_atomic(DATA / "settings.json", _sealed(s))      # older plain-text file: encrypt it now
        for k in SECRET_KEYS:
            s[k] = winos.unseal(str(s.get(k, "")))
        return s


def update_settings(changes: dict) -> dict:
    with _lock:
        s = get_settings()
        for k, v in changes.items():
            if k not in DEFAULT_SETTINGS:
                continue
            default = DEFAULT_SETTINGS[k]
            if isinstance(default, bool):
                s[k] = bool(v)
            elif isinstance(default, int):
                s[k] = max(512, min(int(v), 1024 * 128)) if k == "default_ram_mb" else int(v)
            else:
                s[k] = str(v).strip()[:500]
        if s["theme"] not in THEMES:
            s["theme"] = "deepslate"
        if s["playit_mode"] not in ("managed", "external"):
            s["playit_mode"] = "managed"
        _write_atomic(DATA / "settings.json", _sealed(s))
        return s


# ---- servers --------------------------------------------------------------

def list_servers() -> list[dict]:
    with _lock:
        return list(_read(DATA / "servers.json", []))


def get_server(sid: str) -> dict | None:
    for s in list_servers():
        if s["id"] == sid:
            return s
    return None


def save_server(meta: dict) -> None:
    with _lock:
        servers = list_servers()
        for i, s in enumerate(servers):
            if s["id"] == meta["id"]:
                servers[i] = meta
                break
        else:
            servers.append(meta)
        _write_atomic(DATA / "servers.json", servers)


def update_server(sid: str, changes: dict) -> dict:
    """Change fields of one server record. Only the listed keys can be changed this way."""
    allowed = {"name", "ram_mb", "port", "motd", "jvm_args", "notes", "schedules", "pending_props"}
    with _lock:
        meta = get_server(sid)
        if not meta:
            raise KeyError(sid)
        meta.update({k: v for k, v in changes.items() if k in allowed})
        save_server(meta)
        return meta


def remove_server(sid: str) -> None:
    with _lock:
        servers = [s for s in list_servers() if s["id"] != sid]
        _write_atomic(DATA / "servers.json", servers)


def new_server_id() -> str:
    return uuid.uuid4().hex[:8]


def valid_id(sid: str) -> bool:
    return bool(ID_RE.match(sid or ""))


def server_dir(sid: str) -> Path:
    if not valid_id(sid):
        raise ValueError("Invalid server id")
    return SERVERS_DIR / sid


def backup_dir(sid: str) -> Path:
    if not valid_id(sid):
        raise ValueError("Invalid server id")
    return BACKUPS_DIR / sid
