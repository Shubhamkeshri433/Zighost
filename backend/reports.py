"""Sending a support report. The only thing this app can send to the developer, and only when the person presses Send in Support.
The exact text shown in the box is what is sent, scrubbed once more. Nothing is counted, pinged or sent in the background.

With brand.REPORTS_URL empty nothing can be sent."""
from __future__ import annotations

import logging
import platform

import requests

from . import brand, support

log = logging.getLogger(brand.DATA_KEY)


def configured() -> bool:
    return bool(brand.REPORTS_URL)


def _post(path: str, payload: dict) -> bool:
    r = requests.post(brand.REPORTS_URL.rstrip("/") + path, json=payload, timeout=10, headers={"User-Agent": brand.USER_AGENT})
    return r.status_code == 200


def windows_text() -> str:
    if platform.system() != "Windows":
        return platform.system()
    version = platform.version()
    try:
        build = int(version.split(".")[-1])
    except ValueError:
        build = 0
    # Python reports Windows 11 24H2 as "2025Server", so name it from the build number instead.
    name = "11" if build >= 22000 else "10" if build >= 10240 else platform.release()
    return f"Windows {name} ({version})"


def send_report(text: str, note: str = "", contact: str = "") -> None:
    """Explicit send. `text` is what the person saw in the box; it is scrubbed again and cut to a safe size."""
    if not configured():
        raise RuntimeError("Sending is not set up. Copy the report and email it instead.")
    payload = {"v": brand.VERSION, "os": windows_text(), "text": support._scrub(text)[:20000],
               "note": support._scrub(note)[:1500], "contact": contact.strip()[:120]}
    if not _post("/report", payload):
        raise RuntimeError("The report could not be sent. Copy it and email it instead.")
