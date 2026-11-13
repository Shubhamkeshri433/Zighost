"""Player heads (the face only). The browser asks the panel; the panel asks a public skin service,
keeps the picture on disk for a week, and remembers misses for a day so nothing is asked twice."""
from __future__ import annotations

import re
import time

import requests

from . import brand, store

NAME_RE = re.compile(r"^[A-Za-z0-9_]{1,16}$")
TTL = 7 * 86400
MISS_TTL = 86400
MAX_BYTES = 64 * 1024
SOURCES = ("https://minotar.net/helm/{n}/64.png", "https://mc-heads.net/avatar/{n}/64")
PNG = b"\x89PNG\r\n\x1a\n"


def _dir():
    d = store.DATA / "cache" / "heads"
    d.mkdir(parents=True, exist_ok=True)
    return d


def valid(name: str) -> bool:
    return bool(NAME_RE.match(name or ""))


def get(name: str, fetch=None) -> bytes | None:
    """PNG bytes of the player's face, or None when unknown or offline."""
    if not valid(name):
        return None
    key = name.lower()
    f, miss = _dir() / f"{key}.png", _dir() / f"{key}.miss"
    now = time.time()
    if f.exists() and now - f.stat().st_mtime < TTL:
        return f.read_bytes()
    if miss.exists() and now - miss.stat().st_mtime < MISS_TTL:
        return f.read_bytes() if f.exists() else None
    fetch = fetch or _fetch
    for src in SOURCES:
        data = fetch(src.format(n=name))
        if data and data.startswith(PNG) and len(data) <= MAX_BYTES:
            f.write_bytes(data)
            miss.unlink(missing_ok=True)
            return data
    miss.write_bytes(b"")
    return f.read_bytes() if f.exists() else None


def _fetch(url: str) -> bytes | None:
    try:
        r = requests.get(url, timeout=5, headers={"User-Agent": brand.USER_AGENT}, stream=True)
        if r.status_code != 200:
            return None
        return r.raw.read(MAX_BYTES + 1, decode_content=True)
    except requests.RequestException:
        return None
