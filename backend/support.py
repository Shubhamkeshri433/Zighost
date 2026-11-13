"""Support report (copied by the person, never sent by the app) and the "get ready" downloads (Java, playit helper)."""
from __future__ import annotations

import logging
import platform
import re
import sys
import threading
from pathlib import Path

import psutil

from . import brand, java_rt
from .logsetup import LOG_FILE
from .playit import playit
from .store import DATA, list_servers

MAIN_JAVA = 21


def _scrub(text: str) -> str:
    """Remove the Windows user name, home folder and anything that looks like a secret or a webhook."""
    home = str(Path.home())
    for h in {home, home.replace("\\", "/")}:
        text = text.replace(h, "~")
    text = re.sub(r"https://(?:discord(?:app)?\.com)/api/webhooks/\S+", "<discord webhook removed>", text)
    text = re.sub(r"(?i)(secret|token|key)([\"'=: ]+)[A-Za-z0-9_\-]{12,}", r"\1\2<removed>", text)
    return text


def report(tail: int = 80) -> str:
    vm = psutil.virtual_memory()
    servers = list_servers()
    kinds = ", ".join(sorted({f"{s.get('type')} {s.get('version')}" for s in servers})) or "none"
    lines = [f"{brand.NAME} {brand.VERSION}", f"Windows/OS: {platform.platform()}", f"Python: {sys.version.split()[0]}",
             f"RAM: {vm.total // 2**20} MB, CPUs: {psutil.cpu_count() or 1}",
             f"Servers: {len(servers)} ({kinds})", f"Java: {_java_text()}", f"playit helper: {'present' if playit.binary_exists() else 'not downloaded'}",
             "", "--- last log lines ---"]
    try:
        lines += LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()[-tail:]
    except OSError:
        lines.append("(no log yet)")
    return _scrub("\n".join(lines))


def _java_text() -> str:
    found = java_rt.find_java(MAIN_JAVA)
    return f"Java {found[1]}" if found else "not found"


class Components:
    """Downloads what a server needs before the first one is created, so creating it is fast."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.running = False
        self.java = {"state": "unknown", "percent": 0, "text": ""}
        self.playit = {"state": "unknown", "percent": 0, "text": ""}

    def status(self) -> dict:
        with self._lock:
            if not self.running:
                self.java.update(state="ready" if java_rt.find_java(MAIN_JAVA) else "missing")
                self.playit.update(state="ready" if playit.binary_exists() else "missing")
            return {"running": self.running, "java": dict(self.java), "playit": dict(self.playit)}

    def prepare(self) -> dict:
        with self._lock:
            if self.running:
                return self.status()
            self.running = True
            self.java.update(state="missing", percent=0, text="")
            self.playit.update(state="missing", percent=0, text="")
        threading.Thread(target=self._run, daemon=True, name="prepare").start()
        return self.status()

    def _run(self) -> None:
        log = logging.getLogger(brand.DATA_KEY)
        try:
            if java_rt.find_java(MAIN_JAVA):
                self.java.update(state="ready", percent=100)
            else:
                self.java.update(state="installing")

                def prog(text: str, pct: int) -> None:
                    self.java.update(text=text, percent=pct)
                try:
                    java_rt.install_java(MAIN_JAVA, False, prog)
                    self.java.update(state="ready", percent=100, text="")
                except Exception as e:  # noqa: BLE001
                    log.warning("java prepare failed: %s", e)
                    self.java.update(state="error", text=str(e))
            if playit.binary_exists():
                self.playit.update(state="ready", percent=100)
            else:
                self.playit.update(state="installing")
                try:
                    playit.fetch_binary()
                    self.playit.update(state="ready", percent=100, text="")
                except Exception as e:  # noqa: BLE001
                    log.warning("playit prepare failed: %s", e)
                    self.playit.update(state="error", text=str(e))
        finally:
            self.running = False


components = Components()
