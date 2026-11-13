"""Scheduled jobs per server: restart, backup, run a command. Only runs while the panel is open and the server is online."""
from __future__ import annotations

import logging
import re
import threading
import time
import uuid
from typing import Callable

from .store import get_server

log = logging.getLogger("mcpanel.scheduler")
KINDS = ("restart", "backup", "command")
AT_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class ScheduleError(Exception):
    pass


def clean_schedules(raw) -> list[dict]:
    if not isinstance(raw, list) or len(raw) > 20:
        raise ScheduleError("You can have up to 20 scheduled jobs.")
    out = []
    for j in raw:
        if not isinstance(j, dict):
            raise ScheduleError("A job was not understood.")
        kind = j.get("kind")
        if kind not in KINDS:
            raise ScheduleError("Choose what the job should do.")
        mode = j.get("mode", "every")
        job = {"id": str(j.get("id") or uuid.uuid4().hex[:8])[:12], "kind": kind, "mode": mode,
               "enabled": bool(j.get("enabled", True))}
        if mode == "every":
            try:
                n = int(j.get("every_min", 0))
            except (TypeError, ValueError):
                n = 0
            if not 5 <= n <= 10080:
                raise ScheduleError("Repeat every 5 minutes to 7 days.")
            job["every_min"] = n
        elif mode == "at":
            at = str(j.get("at", ""))
            if not AT_RE.match(at):
                raise ScheduleError("Use a time like 04:30.")
            job["at"] = at
        else:
            raise ScheduleError("Choose how often the job runs.")
        if kind == "command":
            cmd = str(j.get("command", "")).strip().lstrip("/")
            if not cmd or len(cmd) > 200 or "\n" in cmd or "\r" in cmd:
                raise ScheduleError("Type one command (up to 200 characters).")
            job["command"] = cmd
        if kind == "backup":
            try:
                job["keep"] = max(1, min(50, int(j.get("keep", 5))))
            except (TypeError, ValueError):
                raise ScheduleError("Keep between 1 and 50 backups.") from None
        out.append(job)
    return out


class Scheduler:
    def __init__(self, manager, actions: dict[str, Callable]):
        self.manager = manager
        self.actions = actions
        self._stop = threading.Event()
        self._last: dict[tuple, float] = {}
        self._day: dict[tuple, str] = {}
        self._seen: set[tuple] = set()
        self.running_jobs: set[tuple] = set()

    def start(self) -> None:
        self._stop.clear()
        threading.Thread(target=self._loop, daemon=True).start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        while not self._stop.wait(15):
            try:
                self.tick(time.time())
            except Exception:  # noqa: BLE001
                log.exception("scheduler tick failed")

    def tick(self, now: float) -> list[dict]:
        m = self.manager
        sid = m.active_id
        if not sid or m.state != "online":
            return []
        meta = get_server(sid) or {}
        fired = []
        for job in meta.get("schedules", []):
            if job.get("enabled") and self._due(sid, job, now):
                key = (sid, job["id"])
                if key in self.running_jobs:
                    continue
                fired.append(job)
                self.running_jobs.add(key)
                threading.Thread(target=self._run, args=(sid, job, key), daemon=True).start()
        return fired

    def _due(self, sid: str, job: dict, now: float) -> bool:
        key = (sid, job["id"])
        first = key not in self._seen
        self._seen.add(key)
        if job["mode"] == "every":
            if first:
                self._last[key] = now
                return False
            if now - self._last[key] >= job["every_min"] * 60:
                self._last[key] = now
                return True
            return False
        lt = time.localtime(now)
        today = time.strftime("%Y-%m-%d", lt)
        hh, mm = map(int, job["at"].split(":"))
        passed = (lt.tm_hour, lt.tm_min) >= (hh, mm)
        if first and passed:
            self._day[key] = today          # do not fire at panel start for a time that is already past
            return False
        if passed and self._day.get(key) != today:
            self._day[key] = today
            return True
        return False

    def _run(self, sid: str, job: dict, key: tuple) -> None:
        try:
            self.manager.log(f"Scheduled job: {job['kind']}")
            self.actions[job["kind"]](sid, job)
        except Exception as e:  # noqa: BLE001
            self.manager.log(f"Scheduled {job['kind']} failed: {e}")
        finally:
            self.running_jobs.discard(key)
