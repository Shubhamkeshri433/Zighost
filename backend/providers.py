"""Where server jars come from: version lists and download URLs.

Paper: fill.papermc.io/v3 (checked against the PaperMC docs).
Vanilla, Purpur, Fabric, Spigot: written from the vendors' public APIs, still to be
checked live on a real machine (see PLAN.md).
"""
from __future__ import annotations

import time

import requests

from . import brand
from .store import get_settings

TYPES = {
    "paper":   {"label": "Paper",   "speed": 5, "note": "Fast, plugin support. Best for most people."},
    "vanilla": {"label": "Vanilla", "speed": 3, "note": "Official Mojang server, no plugins."},
    "purpur":  {"label": "Purpur",  "speed": 5, "note": "Paper with extra settings."},
    "fabric":  {"label": "Fabric",  "speed": 5, "note": "Mods (lightweight)."},
    "spigot":  {"label": "Spigot",  "speed": 3, "note": "Plugins. Built on your PC, takes 5-10 minutes."},
}

MOJANG_MANIFEST = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
PAPER_API = "https://fill.papermc.io/v3/projects/paper"
PURPUR_API = "https://api.purpurmc.org/v2/purpur"
FABRIC_META = "https://meta.fabricmc.net/v2/versions"
BUILDTOOLS_URL = "https://hub.spigotmc.org/jenkins/job/BuildTools/lastSuccessfulBuild/artifact/target/BuildTools.jar"


class ProviderError(Exception):
    pass


_cache: dict[str, tuple[float, object]] = {}
CACHE_SECONDS = 600


def user_agent() -> str:
    contact = get_settings().get("contact", "").strip()
    base = brand.USER_AGENT
    return f"{base} ({contact})" if contact else f"{base} (self-hosted panel)"


def http_get_json(url: str):
    hit = _cache.get(url)
    if hit and time.time() - hit[0] < CACHE_SECONDS:
        return hit[1]
    try:
        r = requests.get(url, headers={"User-Agent": user_agent()}, timeout=20)
    except requests.RequestException as e:
        raise ProviderError(f"Could not reach {url.split('/')[2]}. Check your internet connection.") from e
    if r.status_code in (401, 403) and "papermc" in url:
        raise ProviderError("PaperMC rejected the request. Add your contact (email or website) in Settings, then try again.")
    if r.status_code != 200:
        raise ProviderError(f"{url.split('/')[2]} answered with error {r.status_code}.")
    data = r.json()
    _cache[url] = (time.time(), data)
    return data


def _vkey(v: str):
    parts = []
    for p in v.replace("-", ".").split("."):
        parts.append(int(p) if p.isdigit() else 0)
    return tuple(parts)


def _mojang_releases() -> list[dict]:
    data = http_get_json(MOJANG_MANIFEST)
    return [v for v in data["versions"] if v["type"] == "release"]


def list_versions(stype: str) -> list[str]:
    """Newest first."""
    if stype == "vanilla":
        return [v["id"] for v in _mojang_releases()]
    if stype == "spigot":
        return [v["id"] for v in _mojang_releases() if _vkey(v["id"]) >= (1, 8)]
    if stype == "paper":
        data = http_get_json(PAPER_API)
        groups = data.get("versions", {})
        out: list[str] = []
        for _, vs in groups.items():
            out.extend(vs)
        return sorted(set(out), key=_vkey, reverse=True)
    if stype == "purpur":
        data = http_get_json(PURPUR_API)
        return sorted(data.get("versions", []), key=_vkey, reverse=True)
    if stype == "fabric":
        data = http_get_json(f"{FABRIC_META}/game")
        return [g["version"] for g in data if g.get("stable")]
    raise ProviderError(f"Unknown server type: {stype}")


def resolve(stype: str, version: str) -> dict:
    """Return {'url': ..., 'kind': 'jar' | 'buildtools', 'build': ...}."""
    if version not in list_versions(stype):
        raise ProviderError(f"{TYPES.get(stype, {}).get('label', stype)} has no version {version}.")
    if stype == "vanilla":
        entry = next(v for v in _mojang_releases() if v["id"] == version)
        meta = http_get_json(entry["url"])
        return {"url": meta["downloads"]["server"]["url"], "kind": "jar", "build": ""}
    if stype == "paper":
        builds = http_get_json(f"{PAPER_API}/versions/{version}/builds")
        if not builds:
            raise ProviderError(f"No Paper build for {version} yet.")
        stable = [b for b in builds if b.get("channel") == "STABLE"] or builds
        b = stable[0]
        return {"url": b["downloads"]["server:default"]["url"], "kind": "jar", "build": str(b.get("id", ""))}
    if stype == "purpur":
        return {"url": f"{PURPUR_API}/{version}/latest/download", "kind": "jar", "build": "latest"}
    if stype == "fabric":
        loader = next(l for l in http_get_json(f"{FABRIC_META}/loader") if l.get("stable"))["version"]
        installer = next(i for i in http_get_json(f"{FABRIC_META}/installer") if i.get("stable"))["version"]
        return {"url": f"{FABRIC_META}/loader/{version}/{loader}/{installer}/server/jar", "kind": "jar", "build": loader}
    if stype == "spigot":
        return {"url": BUILDTOOLS_URL, "kind": "buildtools", "build": ""}
    raise ProviderError(f"Unknown server type: {stype}")


_FALLBACK_JAVA = [((26, 0), 25), ((1, 20, 5), 21), ((1, 18), 17), ((1, 17), 16)]


def java_required(version: str) -> int:
    """Java major version this Minecraft version needs.

    Reads Mojang's version JSON (authoritative); falls back to a table if offline."""
    try:
        for v in _mojang_releases():
            if v["id"] == version:
                meta = http_get_json(v["url"])
                return int(meta["javaVersion"]["majorVersion"])
    except Exception:
        pass
    key = _vkey(version)
    for floor, java in _FALLBACK_JAVA:
        if key >= floor:
            return java
    return 8
