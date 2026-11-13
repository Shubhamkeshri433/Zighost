"""Background watcher: keeps the PC awake while a server runs, switches off power throttling for Java,
and turns server events into tray notices."""
from __future__ import annotations

import logging
import threading
from typing import Callable

from . import brand, winos
from .store import get_settings

log = logging.getLogger(brand.DATA_KEY)


class Monitor:
    def __init__(self, manager, awake: winos.KeepAwake | None = None, interval: float = 5.0) -> None:
        self.manager = manager
        self.awake = awake or winos.KeepAwake()
        self.interval = interval
        self.notifier: Callable[[str, str], None] | None = None     # set by the tray: notifier(title, text)
        self._pid = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        winos.disable_throttling()                 # the panel itself
        self._thread = threading.Thread(target=self._loop, daemon=True, name="winmon")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self.awake.set(False)

    def _loop(self) -> None:
        while not self._stop.wait(self.interval):
            try:
                self.tick()
            except Exception:  # noqa: BLE001
                log.exception("monitor tick failed")

    def tick(self) -> None:
        busy = self.manager.busy()
        self.awake.set(bool(busy and get_settings().get("keep_awake", True)))
        proc = getattr(self.manager, "proc", None)
        pid = proc.pid if proc is not None and proc.poll() is None else None
        if pid and pid != self._pid:
            winos.disable_throttling(pid)           # Java for the server that just started
        self._pid = pid

    def event(self, kind: str, text: str) -> None:
        """Server events: Discord is handled elsewhere, this is the tray notice (never for player joins)."""
        if kind == "player" or not self.notifier or not get_settings().get("toasts", True):
            return
        try:
            self.notifier(brand.NAME, text)
        except Exception:  # noqa: BLE001
            log.exception("tray notice failed")
