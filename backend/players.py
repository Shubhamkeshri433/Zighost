"""Players: whitelist, operators, bans, known players.

Server running  -> send the normal server commands (the server keeps its own files in sync).
Server stopped  -> edit the JSON files directly (whitelist.json, ops.json, banned-players.json, banned-ip.json).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import Callable

import requests

from . import brand
from .props import read_props, write_props
from .store import server_dir

NAME_RE = re.compile(r"^\.?[A-Za-z0-9_]{1,32}$")   # a leading dot is how Floodgate names Bedrock players
IP_RE = re.compile(r"^[0-9a-fA-F:.]{3,45}$")
MODES = ("survival", "creative", "adventure", "spectator")


class PlayerError(Exception):
    pass


def check_name(name: str) -> str:
    name = (name or "").strip()
    if not NAME_RE.match(name):
        raise PlayerError("Player names use letters, numbers and underscores (up to 16 characters).")
    return name


def clean_text(s: str, limit: int = 100) -> str:
    s = " ".join((s or "").split())[:limit]
    return s


def _read(path: Path) -> list:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def _write(path: Path, data: list) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def overview(sid: str) -> dict:
    d = server_dir(sid)
    props = read_props(d / "server.properties")
    wl = _read(d / "whitelist.json")
    ops = _read(d / "ops.json")
    bans = _read(d / "banned-players.json")
    ips = _read(d / "banned-ip.json")
    known = _read(d / "usercache.json")
    return {
        "whitelist": sorted(({"name": e.get("name", ""), "uuid": e.get("uuid", "")} for e in wl if e.get("name")),
                            key=lambda e: e["name"].lower()),
        "ops": sorted(({"name": e.get("name", ""), "level": e.get("level", 4)} for e in ops if e.get("name")),
                      key=lambda e: e["name"].lower()),
        "bans": sorted(({"name": e.get("name", ""), "reason": e.get("reason", ""), "created": e.get("created", ""),
                         "source": e.get("source", "")} for e in bans if e.get("name")),
                       key=lambda e: e["name"].lower()),
        "ipbans": [{"ip": e.get("ip", ""), "reason": e.get("reason", "")} for e in ips if e.get("ip")],
        "known": sorted({e.get("name", "") for e in known if e.get("name")}, key=str.lower),
        "whitelist_on": props.get("white-list", "false") == "true",
        "online_mode": props.get("online-mode", "true") == "true",
        "max_players": int(props.get("max-players", "20") or 20) if props.get("max-players", "20").isdigit() else 20,
    }


def offline_uuid(name: str) -> str:
    b = hashlib.md5(("OfflinePlayer:" + name).encode("utf-8")).digest()
    return str(uuid.UUID(bytes=b, version=3))


def lookup(name: str, online_mode: bool) -> tuple[str, str]:
    """Returns (uuid, correctly-cased name)."""
    if not online_mode:
        return offline_uuid(name), name
    if name.startswith("."):
        raise PlayerError("Bedrock players can only be added while the server is running.")
    try:
        r = requests.get(f"https://api.mojang.com/users/profiles/minecraft/{name}", timeout=10,
                         headers={"User-Agent": brand.USER_AGENT})
    except requests.RequestException:
        raise PlayerError("Could not reach Mojang to look up that player. Check your internet, "
                          "or start the server and try again.") from None
    if r.status_code in (204, 404):
        raise PlayerError(f"No Minecraft account named {name} was found.")
    if r.status_code != 200:
        raise PlayerError(f"Mojang answered with error {r.status_code}. Try again in a minute.")
    j = r.json()
    return str(uuid.UUID(j["id"])), j.get("name", name)


def _remove(path: Path, key: str, value: str) -> bool:
    data = _read(path)
    keep = [e for e in data if str(e.get(key, "")).lower() != value.lower()]
    if len(keep) == len(data):
        return False
    _write(path, keep)
    return True


def _upsert(path: Path, entry: dict, key: str = "name") -> None:
    data = [e for e in _read(path) if str(e.get(key, "")).lower() != str(entry[key]).lower()]
    data.append(entry)
    _write(path, data)


def apply(sid: str, action: str, name: str = "", value: str = "", running: bool = False,
          send: Callable[[str], None] | None = None) -> str:
    """Do one player action. Returns a short message for the toast."""
    d = server_dir(sid)
    value = clean_text(value)

    if action == "whitelist_toggle":
        on = value == "on"
        if running and send:
            send("whitelist on" if on else "whitelist off")
        else:
            write_props(d / "server.properties", {"white-list": "true" if on else "false"})
        return "Whitelist is now on." if on else "Whitelist is now off."

    if action == "ip_unban":
        if not IP_RE.match(value):
            raise PlayerError("That is not a valid IP address.")
        if running and send:
            send(f"pardon-ip {value}")
        else:
            _remove(d / "banned-ip.json", "ip", value)
        return f"{value} can join again."

    name = check_name(name)

    if running and send:
        cmds = {
            "kick": f"kick {name} {value}", "ban": f"ban {name} {value}", "pardon": f"pardon {name}",
            "op": f"op {name}", "deop": f"deop {name}",
            "whitelist_add": f"whitelist add {name}", "whitelist_remove": f"whitelist remove {name}",
            "message": f"tell {name} {value}",
        }
        if action == "gamemode":
            if value not in MODES:
                raise PlayerError("Choose survival, creative, adventure or spectator.")
            cmds["gamemode"] = f"gamemode {value} {name}"
        if action not in cmds:
            raise PlayerError("That action is not available.")
        if action == "message" and not value:
            raise PlayerError("Type a message first.")
        send(cmds[action].strip())
        return {"kick": f"Kicked {name}.", "ban": f"Banned {name}.", "pardon": f"Unbanned {name}.",
                "op": f"{name} is now an operator.", "deop": f"{name} is no longer an operator.",
                "whitelist_add": f"Added {name} to the whitelist.",
                "whitelist_remove": f"Removed {name} from the whitelist.",
                "message": f"Message sent to {name}.", "gamemode": f"{name} is now in {value} mode."}[action]

    # server is stopped: edit the files
    if action in ("kick", "message", "gamemode"):
        raise PlayerError("Start the server to do this. It needs the player to be online.")
    props = read_props(d / "server.properties")
    online_mode = props.get("online-mode", "true") == "true"
    if action == "whitelist_remove":
        _remove(d / "whitelist.json", "name", name)
        return f"Removed {name} from the whitelist."
    if action == "deop":
        _remove(d / "ops.json", "name", name)
        return f"{name} is no longer an operator."
    if action == "pardon":
        _remove(d / "banned-players.json", "name", name)
        return f"Unbanned {name}."
    uid, real = lookup(name, online_mode)
    if action == "whitelist_add":
        _upsert(d / "whitelist.json", {"uuid": uid, "name": real})
        return f"Added {real} to the whitelist."
    if action == "op":
        _upsert(d / "ops.json", {"uuid": uid, "name": real, "level": 4, "bypassesPlayerLimit": False})
        return f"{real} is now an operator."
    if action == "ban":
        _upsert(d / "banned-players.json", {
            "uuid": uid, "name": real, "created": time.strftime("%Y-%m-%d %H:%M:%S +0000", time.gmtime()),
            "source": brand.NAME, "expires": "forever", "reason": value or "Banned by an operator."})
        return f"Banned {real}."
    raise PlayerError("That action is not available.")
