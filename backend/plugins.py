"""Plugins and mods: list what is installed, switch on/off, remove, search and install from Modrinth.

Modrinth API facts checked online: base https://api.modrinth.com/v2, a unique User-Agent is required, search takes
query/facets/limit/offset/index, facets is a JSON array of arrays (inner = OR, outer = AND) and supports
categories/versions/project_type. Loaders are searched as categories. The project "version" call and the exact
answer fields are written from experience and read defensively.
"""
from __future__ import annotations

import hashlib
import json
import re
import zipfile
from pathlib import Path

import requests

from . import providers
from .fsops import clean_name
from .store import get_server, server_dir

API = "https://api.modrinth.com/v2"
MAX_JAR = 150 * 1024 * 1024
ID_RE = re.compile(r"^[A-Za-z0-9_-]{2,64}$")
KINDS = {
    "paper": ("plugins", ["paper", "spigot", "bukkit"]),
    "purpur": ("plugins", ["purpur", "paper", "spigot", "bukkit"]),
    "spigot": ("plugins", ["spigot", "bukkit"]),
    "fabric": ("mods", ["fabric"]),
}


class PluginError(Exception):
    pass


def kind_for(stype: str):
    return KINDS.get(stype)


def _folder(sid: str) -> tuple[Path, str, list[str], dict]:
    meta = get_server(sid)
    if not meta:
        raise PluginError("That server was not found.")
    k = kind_for(meta["type"])
    if not k:
        raise PluginError("Vanilla servers cannot use plugins or mods. Create a Paper or Fabric server for that.")
    d = server_dir(sid) / k[0]
    return d, k[0], k[1], meta


def _info(path: Path) -> dict:
    out = {"title": "", "version": "", "description": ""}
    try:
        with zipfile.ZipFile(path) as z:
            names = set(z.namelist())
            for yml in ("paper-plugin.yml", "plugin.yml"):
                if yml in names:
                    txt = z.read(yml).decode("utf-8", errors="replace")
                    for key in ("name", "version", "description"):
                        m = re.search(rf"^{key}:\s*['\"]?(.+?)['\"]?\s*$", txt, re.M)
                        if m:
                            out["title" if key == "name" else key] = m.group(1)[:200]
                    break
            else:
                if "fabric.mod.json" in names:
                    j = json.loads(z.read("fabric.mod.json").decode("utf-8", errors="replace"))
                    out.update(title=str(j.get("name", j.get("id", "")))[:200], version=str(j.get("version", ""))[:60],
                               description=str(j.get("description", ""))[:200])
    except (OSError, zipfile.BadZipFile, ValueError, KeyError):
        pass
    return out


def list_installed(sid: str) -> dict:
    meta = get_server(sid)
    if not meta:
        raise PluginError("That server was not found.")
    k = kind_for(meta["type"])
    if not k:
        return {"supported": False, "kind": "", "folder": "", "items": [], "type": meta["type"]}
    d = server_dir(sid) / k[0]
    items = []
    if d.is_dir():
        for p in sorted(d.iterdir(), key=lambda x: x.name.lower()):
            if not p.is_file() or not (p.name.endswith(".jar") or p.name.endswith(".jar.disabled")):
                continue
            info = _info(p)
            items.append({"file": p.name, "enabled": p.name.endswith(".jar"), "size": p.stat().st_size,
                          "title": info["title"] or p.name.split(".jar")[0], "version": info["version"],
                          "description": info["description"]})
    return {"supported": True, "kind": "plugin" if k[0] == "plugins" else "mod", "folder": k[0], "items": items,
            "type": meta["type"], "version": meta["version"]}


def _target(sid: str, filename: str) -> Path:
    d, _, _, _ = _folder(sid)
    name = clean_name(filename)
    if not (name.endswith(".jar") or name.endswith(".jar.disabled")):
        raise PluginError("That is not a plugin file.")
    p = d / name
    if not p.is_file():
        raise PluginError("That file was not found.")
    return p


def set_enabled(sid: str, filename: str, enabled: bool) -> None:
    p = _target(sid, filename)
    dest = p.with_name(p.name[:-len(".disabled")] if enabled and p.name.endswith(".disabled")
                       else (p.name + ".disabled" if not enabled and p.name.endswith(".jar") else p.name))
    if dest != p:
        if dest.exists():
            raise PluginError("A file with that name already exists.")
        p.rename(dest)


def remove(sid: str, filename: str) -> None:
    _target(sid, filename).unlink()


def _get(path: str, **params):
    try:
        r = requests.get(API + path, params=params, timeout=15, headers={"User-Agent": providers.user_agent()})
    except requests.RequestException:
        raise PluginError("Could not reach Modrinth. Check your internet connection.") from None
    if r.status_code != 200:
        raise PluginError(f"Modrinth answered with error {r.status_code}. Try again in a minute.")
    return r.json()


def search(sid: str, query: str, offset: int = 0) -> dict:
    _, folder, loaders, meta = _folder(sid)
    facets = [[f"categories:{x}" for x in loaders], [f"versions:{meta['version']}"]]
    if folder == "mods":
        facets.append(["project_type:mod"])
    query = (query or "").strip()[:80]
    data = _get("/search", query=query, facets=json.dumps(facets), limit=12, offset=max(0, int(offset)),
                index="relevance" if query else "downloads")
    hits = [{"id": h.get("project_id", ""), "slug": h.get("slug", ""), "title": h.get("title", ""),
             "description": h.get("description", ""), "icon": h.get("icon_url") or "",
             "downloads": h.get("downloads", 0), "author": h.get("author", "")} for h in data.get("hits", [])]
    out = {"hits": hits, "total": data.get("total_hits", len(hits)), "offset": offset, "suggest": []}
    if not hits and not offset:
        out["suggest"] = _other_versions(folder, loaders, meta["version"])
    return out


def _other_versions(folder: str, loaders: list[str], current: str) -> list[str]:
    """Nothing matches this Minecraft version: find the versions that the popular ones are made for."""
    facets = [[f"categories:{x}" for x in loaders]]
    if folder == "mods":
        facets.append(["project_type:mod"])
    try:
        data = _get("/search", query="", facets=json.dumps(facets), limit=30, index="downloads")
    except PluginError:
        return []
    count: dict[str, int] = {}
    for h in data.get("hits", []):
        for v in h.get("versions", []):
            if re.fullmatch(r"\d+\.\d+(\.\d+)?", str(v)) and v != current:
                count[v] = count.get(v, 0) + 1
    top = [v for v, n in count.items() if n >= max(3, len(data.get("hits", [])) // 3)]
    key = lambda v: tuple(int(x) for x in v.split("."))
    return [v for v in sorted(top, key=key, reverse=True)[:3]]


def install(sid: str, project_id: str) -> dict:
    d, folder, loaders, meta = _folder(sid)
    if not ID_RE.match(project_id or ""):
        raise PluginError("That project id is not valid.")
    versions = _get(f"/project/{project_id}/version", loaders=json.dumps(loaders),
                    game_versions=json.dumps([meta["version"]]))
    if not versions:
        raise PluginError(f"No version made for Minecraft {meta['version']} was found. "
                          "Try another plugin, or create a server on a version it supports.")
    versions.sort(key=lambda v: (v.get("version_type") != "release", ))   # stable: releases first, then API order
    ver = versions[0]
    files = [f for f in ver.get("files", []) if str(f.get("filename", "")).endswith(".jar")]
    if not files:
        raise PluginError("That version has no .jar file to download.")
    f = next((x for x in files if x.get("primary")), files[0])
    name = clean_name(f["filename"])
    url = f.get("url", "")
    if not url.startswith("https://cdn.modrinth.com/"):
        raise PluginError("The download address was not from Modrinth, so it was not used.")
    d.mkdir(exist_ok=True)
    dest = d / name
    part = d / (name + ".part")
    sha1 = hashlib.sha1()
    size = 0
    try:
        with requests.get(url, stream=True, timeout=30, headers={"User-Agent": providers.user_agent()}) as r:
            if r.status_code != 200:
                raise PluginError(f"Download failed (error {r.status_code}).")
            with open(part, "wb") as out:
                for chunk in r.iter_content(1 << 16):
                    size += len(chunk)
                    if size > MAX_JAR:
                        raise PluginError("The file is larger than 150 MB, so it was not installed.")
                    sha1.update(chunk)
                    out.write(chunk)
    except requests.RequestException:
        part.unlink(missing_ok=True)
        raise PluginError("Download failed. Check your internet connection.") from None
    except PluginError:
        part.unlink(missing_ok=True)
        raise
    expected = (f.get("hashes") or {}).get("sha1")
    if expected and expected.lower() != sha1.hexdigest():
        part.unlink(missing_ok=True)
        raise PluginError("The downloaded file did not match its checksum, so it was not installed.")
    part.replace(dest)
    deps = [x.get("project_id") for x in ver.get("dependencies", [])
            if x.get("dependency_type") == "required" and x.get("project_id")]
    dep_names: list[str] = []
    if deps:
        try:
            for p in _get("/projects", ids=json.dumps(deps[:10])):
                dep_names.append(p.get("title", ""))
        except PluginError:
            dep_names = ["(could not look up names)"]
    return {"file": name, "version": ver.get("version_number", ""), "requires": [n for n in dep_names if n]}
