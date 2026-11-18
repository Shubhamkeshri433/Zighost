"""Is there a newer version? Reads the latest GitHub Release of the public repo.
"Update now" (install_start / install_apply) downloads the installer from that release, checks it against the release's
SHA256SUMS.txt, stops running servers safely, closes the app, runs the installer silently and opens the new version.
Nothing is installed unless the checksum matches. Servers, worlds and settings live in the data folder and are never touched."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

import requests

from . import brand, consent, paths, verify
from .store import DATA

CACHE_SECONDS = 6 * 3600
_lock = threading.Lock()
_cache: dict = {"at": 0.0, "data": None}


def parse(v: str) -> tuple:
    """"v0.2.1" -> (0, 2, 1). Anything that is not numbers is ignored."""
    nums = [int(x) for x in re.findall(r"\d+", v.split("-")[0])[:4]]
    return tuple(nums + [0] * (3 - len(nums)))


UPDATE_DIR = DATA / "updates"
PENDING = DATA / "update_pending.json"
NOWINDOW = 0x08000000 if os.name == "nt" else 0
DETACHED = 0x00000008 if os.name == "nt" else 0
ALLOWED_PREFIX = f"https://github.com/{brand.REPO}/releases/download/"
NAME_RE = re.compile(r"^[A-Za-z0-9._-]{1,100}$")
request_exit = None            # set by run.py: closes the app the same safe way as Quit (servers are stopped first)


def _fetch() -> dict:
    r = requests.get(f"https://api.github.com/repos/{brand.REPO}/releases/latest", timeout=8,
                     headers={"User-Agent": brand.USER_AGENT, "Accept": "application/vnd.github+json"})
    if r.status_code == 404:
        return {"latest": brand.VERSION, "url": "", "notes": "", "none": True}
    r.raise_for_status()
    j = r.json()
    exe = next((a for a in j.get("assets", []) if a.get("name", "").lower().endswith("-setup-" + (j.get("tag_name", "").lstrip("v")) + ".exe")), None) \
        or next((a for a in j.get("assets", []) if a.get("name", "").lower().endswith(".exe")), None)
    sums = next((a for a in j.get("assets", []) if a.get("name", "") == "SHA256SUMS.txt"), None)
    return {"latest": j.get("tag_name", "").lstrip("v"), "url": j.get("html_url", ""), "notes": (j.get("body") or "")[:800],
            "file": (exe or {}).get("browser_download_url", ""), "file_name": (exe or {}).get("name", ""),
            "sums": (sums or {}).get("browser_download_url", ""), "none": False}


def check(force: bool = False) -> dict:
    """Never raises. enabled=False when the person turned update checks off."""
    base = {"enabled": consent.updates_allowed(), "current": brand.VERSION, "latest": brand.VERSION, "available": False,
            "url": "", "file": "", "notes": "", "error": "", "checked_at": 0, "can_install": False, "just_updated": just_updated}
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
    base["can_install"] = bool(base["available"] and can_install() and _release_ok(data))
    return base


# ---- Update now ---------------------------------------------------------------------------------------------------

def can_install() -> bool:
    """Only the installed Windows app updates itself. The portable zip, a source checkout and other systems link to the download."""
    return bool(sys.platform == "win32" and paths.FROZEN and Path(sys.executable).parent.joinpath("unins000.exe").exists())


def _release_ok(data: dict) -> bool:
    name = data.get("file_name", "")
    return bool(data.get("file", "").startswith(ALLOWED_PREFIX) and data.get("sums", "").startswith(ALLOWED_PREFIX)
                and NAME_RE.match(name) and name.lower().endswith(".exe") and "setup" in name.lower()
                and data.get("latest", "") != "" and data["latest"] in name)         # the installer must carry the release's own version


_job_lock = threading.Lock()
_want: dict = {}                                 # the checksum the downloaded installer must have
_job: dict = {"state": "idle", "progress": 0, "error": "", "version": ""}      # idle | downloading | ready | installing | error


def job() -> dict:
    with _job_lock:
        return dict(_job)


def _set(**kw) -> None:
    with _job_lock:
        _job.update(kw)


def install_start() -> dict:
    """Begin downloading and checking the installer in the background. Returns the job state."""
    info = check()
    with _job_lock:
        if _job["state"] in ("downloading", "installing"):
            return dict(_job)
    if not (info["available"] and info["can_install"]):
        raise UpdateError("This copy of Zighost cannot update itself. Use the Download button instead.")
    data = _cache["data"]
    _set(state="downloading", progress=0, error="", version=info["latest"])
    threading.Thread(target=_download_and_verify, args=(data,), daemon=True, name="update-download").start()
    return job()


class UpdateError(Exception):
    pass


def _fail(msg: str) -> None:
    _set(state="error", error=msg, progress=0)


def _get(url: str, **kw):
    if not url.startswith("https://"):
        raise UpdateError("Unsafe download address.")
    return requests.get(url, timeout=30, headers={"User-Agent": brand.USER_AGENT}, **kw)


def _download_and_verify(data: dict) -> None:
    final = UPDATE_DIR / data["file_name"]
    part = final.with_suffix(".part")
    try:
        UPDATE_DIR.mkdir(parents=True, exist_ok=True)
        for old in UPDATE_DIR.glob("*"):
            old.unlink(missing_ok=True)
        with _get(data["sums"], stream=True) as r:
            if r.status_code != 200:
                raise UpdateError("The checksum list for this release could not be downloaded, so nothing was installed.")
            text = r.raw.read(1 << 20, decode_content=True).decode("utf-8", "replace")
        want = verify.parse_sums(text).get(data["file_name"])
        if not want:
            raise UpdateError("This release does not list a checksum for its installer, so it was not installed.")
        with _get(data["file"], stream=True) as r:
            if r.status_code != 200:
                raise UpdateError(f"The update could not be downloaded (error {r.status_code}).")
            total = int(r.headers.get("content-length") or 0)
            got = 0
            with open(part, "wb") as f:
                for chunk in r.iter_content(1 << 16):
                    f.write(chunk)
                    got += len(chunk)
                    if total:
                        _set(progress=min(99, int(got * 100 / total)))
        try:
            verify.check(part, ("sha256", want), "The update")
        except verify.VerifyError as e:
            raise UpdateError(str(e)) from e
        part.replace(final)
        _want["sha256"] = want
        _set(state="ready", progress=100)
    except UpdateError as e:
        part.unlink(missing_ok=True)
        _fail(str(e))
    except (requests.RequestException, OSError):
        part.unlink(missing_ok=True)
        _fail("The update could not be downloaded. Check your internet connection and try again.")


def _batch(installer: Path, pid: int) -> Path:
    """A tiny script that waits for this app to exit, runs the installer silently and removes itself.
    The installer then starts the new version (see [Run] in installer/zighost.iss, switched on by /UPDATING=1)."""
    bat = UPDATE_DIR / "apply.cmd"
    bat.write_text("\r\n".join([
        "@echo off",
        "set /a n=0",
        ":wait",
        f'tasklist /FI "PID eq {int(pid)}" 2>nul | find "{int(pid)}" >nul',
        "if errorlevel 1 goto go",
        "set /a n+=1",
        "if %n% GEQ 90 goto go",
        "ping -n 2 127.0.0.1 >nul",
        "goto wait",
        ":go",
        f'"{installer}" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /CLOSEAPPLICATIONS /UPDATING=1',
        'del "%~f0"',
        ""]), encoding="ascii")
    return bat


def install_apply() -> dict:
    """Run the downloaded, verified installer. The caller has already dealt with running servers."""
    st = job()
    if st["state"] != "ready":
        raise UpdateError("The update is not ready yet.")
    data = _cache["data"] or {}
    installer = UPDATE_DIR / data.get("file_name", "")
    if not installer.exists() or not NAME_RE.match(installer.name):
        _fail("The downloaded update is missing. Press Update now again.")
        raise UpdateError("The downloaded update is missing. Press Update now again.")
    try:                                   # checked once more right before running: the file sat on disk for a while
        verify.check(installer, ("sha256", _want.get("sha256", "")), "The update")
    except verify.VerifyError as e:
        _fail(str(e))
        raise UpdateError(str(e)) from e
    PENDING.write_text(json.dumps({"to": st["version"]}), encoding="utf-8")
    bat = _batch(installer, os.getpid())
    _set(state="installing")
    subprocess.Popen(["cmd.exe", "/c", str(bat)], creationflags=NOWINDOW | DETACHED, close_fds=True,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if request_exit:
        threading.Thread(target=request_exit, daemon=True, name="update-exit").start()
    return job()


def startup_cleanup() -> str:
    """Called once when the app starts: removes what an earlier update left behind and tells whether this start follows an update."""
    just = ""
    try:
        if PENDING.exists():
            to = json.loads(PENDING.read_text(encoding="utf-8")).get("to", "")
            if to and parse(brand.VERSION) >= parse(to):
                just = brand.VERSION
            PENDING.unlink(missing_ok=True)
        if UPDATE_DIR.exists():
            for old in UPDATE_DIR.glob("*"):
                old.unlink(missing_ok=True)
    except (OSError, ValueError):
        pass
    return just


just_updated = ""
