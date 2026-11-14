"""Is there a newer version? Reads the latest GitHub Release of the public repo. It only tells; it never installs.
The person opens the download page, runs the installer, and the installer closes the old copy first."""
from __future__ import annotations

import re
import threading
import time

import requests

from . import brand, consent

CACHE_SECONDS = 6 * 3600
_lock = threading.Lock()
_cache: dict = {"at": 0.0, "data": None}


def parse(v: str) -> tuple:
    """"v0.2.1" -> (0, 2, 1). Anything that is not numbers is ignored."""
    nums = [int(x) for x in re.findall(r"\d+", v.split("-")[0])[:4]]
    return tuple(nums + [0] * (3 - len(nums)))


def _fetch() -> dict:
    r = requests.get(f"https://api.github.com/repos/{brand.REPO}/releases/latest", timeout=8,
                     headers={"User-Agent": brand.USER_AGENT, "Accept": "application/vnd.github+json"})
    if r.status_code == 404:
        return {"latest": brand.VERSION, "url": "", "notes": "", "none": True}
    r.raise_for_status()
    j = r.json()
    exe = next((a for a in j.get("assets", []) if a.get("name", "").lower().endswith("-setup-" + (j.get("tag_name", "").lstrip("v")) + ".exe")), None) \
        or next((a for a in j.get("assets", []) if a.get("name", "").lower().endswith(".exe")), None)
    return {"latest": j.get("tag_name", "").lstrip("v"), "url": j.get("html_url", ""), "notes": (j.get("body") or "")[:800],
            "file": (exe or {}).get("browser_download_url", ""), "none": False}


def check(force: bool = False) -> dict:
    """Never raises. enabled=False when the person turned update checks off."""
    base = {"enabled": consent.updates_allowed(), "current": brand.VERSION, "latest": brand.VERSION, "available": False,
            "url": "", "file": "", "notes": "", "error": "", "checked_at": 0}
    if not base["enabled"]:
        return base
    with _lock:
        if not force and _cache["data"] is not None and time.time() - _cache["at"] < CACHE_SECONDS:
            data, at, err = _cache["data"], _cache["at"], ""
        else:
            try:
                data, at, err = _fetch(), time.time(), ""
                _cache.update(at=at, data=data)
            except Exception as e:  # noqa: BLE001 - offline, rate limited, anything
                data, at, err = _cache["data"], _cache["at"], "Could not reach GitHub. Try again later."
                if data is None:
                    return {**base, "error": err}
    base.update(latest=data["latest"] or brand.VERSION, url=data["url"], file=data.get("file", ""), notes=data["notes"],
                checked_at=int(at), error=err)
    base["available"] = (not data.get("none")) and parse(base["latest"]) > parse(brand.VERSION)
    return base
