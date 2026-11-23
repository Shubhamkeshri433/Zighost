"""Find server folders that exist on disk but are missing from servers.json."""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

from . import store

_VER = re.compile(r"\d+\.\d+(?:\.\d+)?")


def _text(p: Path, limit: int = 200_000) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")[:limit]
    except OSError:
        return ""


def _props(d: Path) -> dict:
    out = {}
    for line in _text(d / "server.properties").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def guess_type(d: Path) -> str:
    if (d / "purpur.yml").exists():
        return "purpur"
    if (d / ".fabric").exists() or (d / "fabric-server-launch.jar").exists() \
            or (d / "fabric-server-launcher.properties").exists():
        return "fabric"
    if (d / ".paper").exists() or (d / "config" / "paper-global.yml").exists() \
            or (d / "paper.yml").exists() or (d / "versions").is_dir():
        return "paper"
    if (d / "spigot.yml").exists():
        return "spigot"
    return "vanilla"


def guess_version(d: Path) -> str:
    m = re.search(r"MC:\s*(" + _VER.pattern + ")", _text(d / "version_history.json"))
    if m:
        return m.group(1)
    vd = d / "versions"
    if vd.is_dir():
        for sub in sorted(vd.iterdir(), reverse=True):
            if sub.is_dir() and _VER.fullmatch(sub.name):
                return sub.name
    m = re.search(r"Starting minecraft server version (" + _VER.pattern + ")", _text(d / "logs" / "latest.log"))
    return m.group(1) if m else ""


def _clean_motd(m: str) -> str:
    m = re.sub(r"\\u00a7.|\u00a7.", "", m)           # colour codes
    m = re.sub(r"\\n.*", "", m).strip()
    return "" if m.lower() in ("", "a minecraft server") else m[:40]


def guess_name(d: Path, typ: str, ver: str, motd: str) -> str:
    """The old name if a backup remembers it, else the motd, else something readable."""
    try:
        from . import backups
        for b in backups.list_backups(d.name):          # newest first
            if b.get("server"):
                return b["server"]
    except Exception:  # noqa: BLE001 - a broken backup folder must not stop the recovery
        pass
    return _clean_motd(motd) or f"{typ.capitalize()} {ver}".strip() + " server"


def inspect(d: Path) -> dict:
    props = _props(d)
    eula = bool(re.search(r"eula\s*=\s*true", _text(d / "eula.txt"), re.I))
    try:
        port = int(props.get("server-port", "25565"))
    except ValueError:
        port = 25565
    motd = props.get("motd", "")
    try:
        created = int(d.stat().st_ctime)
    except OSError:
        created = int(time.time())
    typ, ver = guess_type(d), guess_version(d)
    return {
        "id": d.name,
        "name": guess_name(d, typ, ver, motd),
        "type": typ,
        "version": ver,
        "ram_mb": int(store.get_settings().get("default_ram_mb") or 2048),
        "port": port,
        "eula": eula,
        "motd": motd,
        "jvm_args": "",
        "notes": "Recovered from the server folder on disk.",
        "schedules": [],
        "installed": True,
        "created": created,
        "recovered": True,
    }


def orphans() -> list[Path]:
    known = {s["id"] for s in store.list_servers()}
    root = store.SERVERS_DIR
    if not root.is_dir():
        return []
    found = []
    for d in sorted(root.iterdir()):
        if d.is_dir() and store.ID_RE.match(d.name) and d.name not in known \
                and ((d / "server.properties").exists() or any(d.glob("*.jar"))):
            found.append(d)
    return found


def recover() -> list[dict]:
    """Register every orphan folder. Never touches the files inside them."""
    out = []
    for d in orphans():
        meta = inspect(d)
        store.save_server(meta)
        out.append(meta)
    return out
