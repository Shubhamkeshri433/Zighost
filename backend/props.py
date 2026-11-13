"""Read and write server.properties while keeping comments and order."""
from __future__ import annotations

import re
from pathlib import Path

DEFAULTS = {
    "server-port": "25565",
    "motd": "A Minecraft Server",
    "gamemode": "survival",
    "difficulty": "easy",
    "max-players": "20",
    "pvp": "true",
    "online-mode": "true",
    "white-list": "false",
    "view-distance": "10",
    "simulation-distance": "10",
    "allow-flight": "false",
    "spawn-protection": "16",
    "level-seed": "",
    "enable-command-block": "false",
}


KEY_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,59}$")


def clean_props(raw) -> dict[str, str]:
    """Check a dict that came from the browser. Returns strings only; raises ValueError with a readable message."""
    if not isinstance(raw, dict) or len(raw) > 150:
        raise ValueError("The settings were not understood.")
    out: dict[str, str] = {}
    for k, v in raw.items():
        k = str(k).strip()
        if not KEY_RE.match(k):
            raise ValueError(f"'{k}' is not a valid setting name.")
        if isinstance(v, bool):
            v = "true" if v else "false"
        if v is None:
            v = ""
        if not isinstance(v, (str, int, float)):
            raise ValueError(f"Setting {k} has an invalid value.")
        v = str(v)
        if "\n" in v or "\r" in v or len(v) > 600:
            raise ValueError(f"Setting {k} has an invalid value.")
        out[k] = v
    return out


def read_props(path: Path) -> dict[str, str]:
    props: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return props
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        props[k.strip()] = v.strip()
    return props


def _clean(s: str) -> str:
    s = str(s)
    if "\n" in s or "\r" in s:
        raise ValueError("Values cannot contain line breaks")
    return s


def write_props(path: Path, updates: dict[str, str]) -> None:
    """Update keys in place; keep comments, order and unknown keys."""
    updates = {_clean(k).strip(): _clean(v) for k, v in updates.items()}
    for k in updates:
        if not k or "=" in k or k.startswith("#"):
            raise ValueError(f"Invalid property name: {k!r}")
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except FileNotFoundError:
        lines = ["#Minecraft server properties"]
    done: set[str] = set()
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            k = stripped.split("=", 1)[0].strip()
            if k in updates:
                out.append(f"{k}={updates[k]}")
                done.add(k)
                continue
        out.append(line)
    for k, v in updates.items():
        if k not in done:
            out.append(f"{k}={v}")
    tmp = path.with_suffix(".properties.tmp")
    tmp.write_text("\n".join(out) + "\n", encoding="utf-8")
    tmp.replace(path)
