"""The two things that can reach the developer, both opt-in and both through the Worker address in brand.STATS_URL:

- ping:   once a day, only if the person switched "anonymous usage" on. Sends a random id, the app version and the Windows
          version. Nothing else: no names, no servers, no IP address stored by the Worker.
- report: only when the person presses Send in Support. The exact text shown in the box is what is sent.

With brand.STATS_URL empty (before the Worker exists) nothing is ever sent."""
from __future__ import annotations

import logging
import platform
import time

import requests

from . import brand, consent, support

log = logging.getLogger(brand.DATA_KEY)
DAY = 24 * 3600


def configured() -> bool:
    return bool(brand.STATS_URL)


def _post(path: str, payload: dict) -> bool:
    r = requests.post(brand.STATS_URL.rstrip("/") + path, json=payload, timeout=10, headers={"User-Agent": brand.USER_AGENT})
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


def tick() -> None:
    """Called every few hours by the background loop. Does nothing unless a message is due and allowed."""
    if not configured():
        return
    try:
        gone = consent.pending_forget()
        if gone:                                   # stats were switched off: ask the Worker to delete the old id
            if _post("/forget", {"id": gone}):
                consent.clear_forget()
        if consent.stats_allowed() and time.time() - consent.last_ping() >= DAY:
            if _post("/ping", {"id": consent.install_id(), "v": brand.VERSION, "os": windows_text()}):
                consent.mark_ping()
    except Exception as e:  # noqa: BLE001 - offline is normal
        log.info("stats tick skipped: %s", e)


def send_report(text: str, note: str = "", contact: str = "") -> None:
    """Explicit send. `text` is what the person saw in the box; it is scrubbed again and cut to a safe size."""
    if not configured():
        raise RuntimeError("Sending is not set up. Copy the report and email it instead.")
    payload = {"v": brand.VERSION, "os": windows_text(), "text": support._scrub(text)[:20000],
               "note": support._scrub(note)[:1500], "contact": contact.strip()[:120]}
    if not _post("/report", payload):
        raise RuntimeError("The report could not be sent. Copy it and email it instead.")
