"""One log file for the app: DATA/logs/<key>.log (1 MB x 3). Also makes a windowed exe (no console) safe."""
from __future__ import annotations

import logging
import logging.handlers
import os
import sys
import threading

from . import brand
from .store import DATA

LOG_DIR = DATA / "logs"
LOG_FILE = LOG_DIR / f"{brand.DATA_KEY}.log"


class _ToLog:
    """Stands in for stdout/stderr when there is no console, so print() never crashes the app."""

    def __init__(self, logger: logging.Logger, level: int) -> None:
        self.logger, self.level, self.buf = logger, level, ""

    def write(self, text: str) -> int:
        self.buf += text
        while "\n" in self.buf:
            line, self.buf = self.buf.split("\n", 1)
            if line.strip():
                self.logger.log(self.level, line.rstrip())
        return len(text)

    def flush(self) -> None:
        pass

    def isatty(self) -> bool:
        return False


def setup() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    if not any(isinstance(h, logging.handlers.RotatingFileHandler) for h in root.handlers):
        fh = logging.handlers.RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        root.addHandler(fh)
    log = logging.getLogger(brand.DATA_KEY)
    if sys.stdout is None:
        sys.stdout = _ToLog(log, logging.INFO)
    if sys.stderr is None:
        sys.stderr = _ToLog(log, logging.ERROR)

    def hook(exc_type, exc, tb):
        log.critical("Unhandled error", exc_info=(exc_type, exc, tb))

    sys.excepthook = hook
    threading.excepthook = lambda a: log.critical("Unhandled error in thread %s", getattr(a.thread, "name", "?"),
                                                  exc_info=(a.exc_type, a.exc_value, a.exc_traceback))
    log.info("%s %s starting (pid %s, data %s)", brand.NAME, brand.VERSION, os.getpid(), DATA)
    return log
