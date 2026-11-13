"""One running copy, and a free port.

A second start finds the first one (instance file + /api/ping) and just opens it. A Windows named mutex covers the
short moment while the first copy is still starting."""
from __future__ import annotations

import atexit
import json
import os
import socket
import sys
import time
import urllib.request

from . import brand
from .store import RUNTIME_DIR

HOST = "127.0.0.1"
FILE = RUNTIME_DIR / "instance.json"
_mutex = None


def _ping(port: int, timeout: float = 0.7) -> bool:
    try:
        with urllib.request.urlopen(f"http://{HOST}:{port}/api/ping", timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8")).get("app") == brand.DATA_KEY
    except (OSError, ValueError):
        return False


def find_running(preferred: int = 8765) -> str | None:
    """URL of a copy of this app that already answers, else None."""
    ports = []
    try:
        ports.append(int(json.loads(FILE.read_text(encoding="utf-8")).get("port")))
    except (OSError, ValueError, TypeError):
        pass
    ports += [p for p in range(preferred, preferred + 10) if p not in ports]
    for p in ports:
        if _ping(p):
            return f"http://localhost:{p}"
    return None


def port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((HOST, port)) != 0


def choose_port(preferred: int = 8765) -> int:
    for p in range(preferred, preferred + 50):
        if port_free(p):
            return p
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, 0))
        return s.getsockname()[1]


def _take_mutex() -> bool:
    """True when this is the first copy. Windows only; elsewhere always True."""
    global _mutex
    if os.name != "nt":
        return True
    import ctypes
    k = ctypes.windll.kernel32
    _mutex = k.CreateMutexW(None, False, f"Local\\{brand.DATA_KEY}-single-instance")
    return k.GetLastError() != 183          # ERROR_ALREADY_EXISTS


def claim(preferred: int = 8765, wait: float = 6.0) -> str | None:
    """None: this copy may run. A URL: another copy already runs there."""
    url = find_running(preferred)
    if url:
        return url
    if not _take_mutex():
        end = time.time() + wait            # the other copy is still starting: give it a moment
        while time.time() < end:
            url = find_running(preferred)
            if url:
                return url
            time.sleep(0.4)
    return None


def publish(port: int) -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    FILE.write_text(json.dumps({"pid": os.getpid(), "port": port, "version": brand.VERSION}), encoding="utf-8")
    atexit.register(lambda: FILE.unlink(missing_ok=True))


show_callback = None          # set by the window shell: brings the existing window to the front


def request_show(url: str) -> bool:
    """Ask the copy that already runs to show its window. False: it has no window (browser mode)."""
    try:
        req = urllib.request.Request(url.replace("localhost", HOST) + "/api/show-window", data=b"{}", method="POST",
                                     headers={brand.API_HEADER: "1", "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=2) as r:
            return bool(json.loads(r.read().decode("utf-8")).get("shown"))
    except (OSError, ValueError):
        return False
