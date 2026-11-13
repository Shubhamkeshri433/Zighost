"""Install and run Minecraft servers. One server runs at a time."""
from __future__ import annotations

import collections
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable

import psutil

from . import brand
import requests

import shlex

from . import java_rt, plugins, providers, servericon
from .props import DEFAULTS, clean_props, read_props, write_props
from .store import (get_server, get_settings, remove_server, save_server,
                    server_dir, update_server, update_settings, new_server_id, backup_dir)

IS_WIN = sys.platform.startswith("win")
NOWINDOW = 0x08000000 if IS_WIN else 0
LOG_LIMIT = 3000

JOIN_RE = re.compile(r":\s(\w{3,16}) joined the game")
LEAVE_RE = re.compile(r":\s(\w{3,16}) left the game")
DONE_RE = re.compile(r'Done \([\d.,]+s\)!')


class ManagerError(Exception):
    """Error with a message that is safe and useful to show to the user."""


_JVM_BLOCK = ("-jar", "-cp", "-classpath", "--class-path", "-xmx", "-xms")


def parse_jvm_args(text: str) -> list[str]:
    """Extra Java arguments typed by the user. Memory is set by the RAM field, so -Xmx/-Xms are refused."""
    text = (text or "").strip()
    if not text:
        return []
    if len(text) > 400 or "\n" in text:
        raise ManagerError("Java arguments are too long. Keep them on one line, under 400 characters.")
    try:
        parts = shlex.split(text, posix=not IS_WIN)
    except ValueError:
        raise ManagerError("The Java arguments have an unclosed quote.") from None
    for p in parts:
        if not p.startswith("-"):
            raise ManagerError(f"Java arguments must start with a dash. Problem: {p[:30]}")
        if p.lower().split("=")[0] in _JVM_BLOCK or p.lower().startswith(("-xmx", "-xms")):
            raise ManagerError("Set memory with the Memory field, not with -Xmx or -Xms. "
                               "-jar and -cp are managed by the panel.")
    return parts


class Console:
    """Ring buffer of log lines with increasing sequence numbers."""

    def __init__(self, limit: int = LOG_LIMIT):
        self._lines: collections.deque[tuple[int, str]] = collections.deque(maxlen=limit)
        self._seq = 0
        self._lock = threading.Lock()

    def add(self, text: str) -> None:
        with self._lock:
            self._seq += 1
            self._lines.append((self._seq, text.rstrip("\r\n")))

    def since(self, after: int = 0) -> list[tuple[int, str]]:
        with self._lock:
            return [(s, t) for s, t in self._lines if s > after]

    def clear(self) -> None:
        with self._lock:
            self._lines.clear()

    @property
    def last_seq(self) -> int:
        return self._seq


class Manager:
    def __init__(self):
        self.console = Console()
        self.lock = threading.RLock()
        self.state = "offline"            # offline|installing|starting|online|stopping|crashed
        self.active_id: str | None = None
        self.proc: subprocess.Popen | None = None
        self.players: set[str] = set()
        self.started_at: float | None = None
        self.stop_requested = False
        self.crashes: list[float] = []
        self.install_job = {"active": False, "step": "", "percent": 0, "error": "", "server_id": ""}
        self._psproc: psutil.Process | None = None
        self.on_before_start: Callable[[dict], None] | None = None
        self.on_event: Callable[[str, str], None] | None = None   # (kind, text) for Discord notices
        self._initial_props: dict[str, dict] = {}
        self._initial_icons: dict[str, bytes] = {}
        self._starter: dict[str, list[str]] = {}

    # ---- helpers ----------------------------------------------------------
    def log(self, text: str) -> None:
        self.console.add(f"[panel] {text}")

    def _set_job(self, **kw) -> None:
        self.install_job.update(kw)

    def _emit(self, kind: str, text: str) -> None:
        """Tell the notice hook (Discord). A broken hook must never break the server."""
        cb = self.on_event
        if cb:
            try:
                cb(kind, text)
            except Exception:  # noqa: BLE001
                pass

    @staticmethod
    def _name(sid: str) -> str:
        return (get_server(sid) or {}).get("name", "Server")

    def busy(self) -> bool:
        return self.state in ("installing", "starting", "online", "stopping") or self.install_job["active"]

    # ---- create -----------------------------------------------------------
    def create_server(self, name: str, stype: str, version: str, ram_mb: int,
                      port: int, eula: bool, motd: str = "", props: dict | None = None,
                      jvm_args: str = "", icon: bytes | None = None, starter: list | None = None) -> dict:
        name = (name or "").strip()
        try:
            initial = clean_props(props or {})
        except ValueError as e:
            raise ManagerError(str(e)) from None
        parse_jvm_args(jvm_args)   # raises ManagerError if something is wrong
        if icon:
            try:
                servericon.validate(icon)
            except servericon.IconError as e:
                raise ManagerError(str(e)) from None
        starter = [str(x) for x in (starter or [])][:12]
        if any(not plugins.ID_RE.match(x) for x in starter):
            raise ManagerError("One of the chosen plugins has an invalid id.")
        if not name or len(name) > 40:
            raise ManagerError("Give the server a name (up to 40 characters).")
        if stype not in providers.TYPES:
            raise ManagerError("Choose a server type.")
        if not eula:
            raise ManagerError("You need to accept the Minecraft EULA to create a server.")
        if not (1024 <= int(port) <= 65535):
            raise ManagerError("Port must be between 1024 and 65535.")
        ram_mb = int(ram_mb)
        total_mb = psutil.virtual_memory().total // (1024 * 1024)
        if ram_mb < 512:
            raise ManagerError("RAM must be at least 512 MB.")
        if ram_mb > total_mb * 0.8:
            raise ManagerError(f"This PC has {total_mb} MB of RAM. Choose {int(total_mb * 0.6)} MB or less.")
        if self.install_job["active"]:
            raise ManagerError("Another server is still being installed. Wait for it to finish.")
        sid = new_server_id()
        meta = {"id": sid, "name": name, "type": stype, "version": version, "ram_mb": ram_mb,
                "port": int(port), "eula": True, "motd": (motd.strip() or initial.get("motd", "")).strip()[:120] or name,
                "jvm_args": jvm_args.strip(), "notes": "", "schedules": [],
                "installed": False, "created": int(time.time())}
        save_server(meta)
        self._initial_props[sid] = initial
        if icon:
            self._initial_icons[sid] = icon
        if starter and plugins.kind_for(stype):
            self._starter[sid] = starter
        self._set_job(active=True, step="Starting", percent=0, error="", server_id=sid)
        threading.Thread(target=self._install_thread, args=(sid,), daemon=True).start()
        return meta

    def update_config(self, sid: str, changes: dict) -> dict:
        """Name, memory, port, Java arguments, notes. Not while this server is running."""
        meta = get_server(sid)
        if not meta:
            raise ManagerError("That server was not found.")
        if self.active_id == sid and self.busy():
            raise ManagerError("Stop the server before changing its memory, port or Java settings.")
        out: dict = {}
        if "name" in changes:
            n = str(changes["name"]).strip()
            if not n or len(n) > 40:
                raise ManagerError("Give the server a name (up to 40 characters).")
            out["name"] = n
        if "ram_mb" in changes:
            try:
                ram = int(changes["ram_mb"])
            except (TypeError, ValueError):
                raise ManagerError("Memory must be a number.") from None
            total_mb = psutil.virtual_memory().total // (1024 * 1024)
            if ram < 512 or ram > total_mb * 0.8:
                raise ManagerError(f"Memory must be between 512 MB and {int(total_mb * 0.8)} MB on this PC.")
            out["ram_mb"] = ram
        if "port" in changes:
            try:
                port = int(changes["port"])
            except (TypeError, ValueError):
                raise ManagerError("Port must be a number.") from None
            if not 1024 <= port <= 65535:
                raise ManagerError("Port must be between 1024 and 65535.")
            out["port"] = port
        if "jvm_args" in changes:
            parse_jvm_args(str(changes["jvm_args"]))
            out["jvm_args"] = str(changes["jvm_args"]).strip()[:400]
        if "notes" in changes:
            out["notes"] = str(changes["notes"])[:2000]
        if "motd" in changes:
            out["motd"] = str(changes["motd"]).strip()[:120]
        meta = update_server(sid, out)
        if "port" in out:
            write_props(server_dir(sid) / "server.properties", {"server-port": str(out["port"])})
        return meta

    def _progress(self, step: str, pct: int) -> None:
        self._set_job(step=step, percent=max(0, min(100, int(pct))))

    def _install_thread(self, sid: str) -> None:
        meta = get_server(sid)
        try:
            self._install(meta)
            meta = get_server(sid) or meta          # the person may have edited name, port or notes while it installed
            meta["installed"] = True
            save_server(meta)
            self._set_job(active=False, step="Done", percent=100)
            self.log(f"{meta['name']} is ready. Press Start server.")
        except Exception as e:  # noqa: BLE001  (show any failure to the user, then clean up)
            msg = str(e) if isinstance(e, (ManagerError, providers.ProviderError, java_rt.JavaError)) \
                else f"Install failed: {e.__class__.__name__}: {e}"
            self._set_job(active=False, error=msg, step="Failed")
            self.log(msg)
            shutil.rmtree(server_dir(sid), ignore_errors=True)
            remove_server(sid)

    def _install(self, meta: dict) -> None:
        sid, stype, version = meta["id"], meta["type"], meta["version"]
        d = server_dir(sid)
        d.mkdir(parents=True, exist_ok=True)
        free_gb = shutil.disk_usage(d).free / 1e9
        if free_gb < 1.5:
            raise ManagerError(f"Only {free_gb:.1f} GB of disk space is free. Free up at least 2 GB.")
        self._progress("Looking up version", 2)
        info = providers.resolve(stype, version)
        need_java = providers.java_required(version)
        self.ensure_java(need_java, jdk=(info["kind"] == "buildtools"))
        if info["kind"] == "jar":
            self._download(info["url"], d / "server.jar", "Downloading server")
        else:
            self._build_spigot(info["url"], version, d, need_java)
        (d / "eula.txt").write_text(f"# Accepted in {brand.NAME} when the server was created\neula=true\n", encoding="utf-8")
        fresh = get_server(sid) or meta
        props = {"server-port": str(fresh["port"]), "motd": fresh["motd"]}
        extra = self._initial_props.pop(sid, {})
        want = {**{k: v for k, v in DEFAULTS.items() if k in ("server-port", "motd")}, **extra, **props}
        have = read_props(d / "server.properties")
        # keep anything the person already changed in Settings while this installed
        write_props(d / "server.properties", {k: v for k, v in want.items() if k not in have or k in ("server-port", "motd")})
        icon = self._initial_icons.pop(sid, None)
        if icon:
            servericon.save(sid, icon)
        starter = self._starter.pop(sid, [])
        for i, pid in enumerate(starter):
            self._progress(f"Adding {pid}", 90 + int(8 * i / max(1, len(starter))))
            try:
                plugins.install(sid, pid)
            except Exception as e:  # noqa: BLE001  (a missing plugin must not stop the server from being created)
                self.log(f"Could not add {pid}: {e}")
        self._progress("Finishing", 99)

    def ensure_java(self, major: int, jdk: bool = False) -> str:
        found = java_rt.find_java(major, need_jdk=jdk)
        if found:
            return found[0]
        self.log(f"Java {major} was not found. Downloading it (about 50 MB).")
        return java_rt.install_java(major, jdk, self._progress)

    def _download(self, url: str, dest: Path, label: str) -> None:
        part = dest.with_suffix(dest.suffix + ".part")
        try:
            with requests.get(url, stream=True, timeout=30, allow_redirects=True,
                              headers={"User-Agent": providers.user_agent()}) as r:
                if r.status_code != 200:
                    raise ManagerError(f"Download failed (error {r.status_code}).")
                total = int(r.headers.get("content-length") or 0)
                got = 0
                with open(part, "wb") as f:
                    for chunk in r.iter_content(1 << 16):
                        f.write(chunk)
                        got += len(chunk)
                        if total:
                            self._progress(label, 10 + int(got * 80 / total))
        except requests.RequestException as e:
            part.unlink(missing_ok=True)
            raise ManagerError("Download failed. Check your internet connection and try again.") from e
        if part.stat().st_size < 1000:
            part.unlink(missing_ok=True)
            raise ManagerError("The download was empty. Try again in a few minutes.")
        part.replace(dest)

    def _build_spigot(self, url: str, version: str, d: Path, java_major: int) -> None:
        work = d / "_build"
        work.mkdir(exist_ok=True)
        self._download(url, work / "BuildTools.jar", "Downloading BuildTools")
        if not shutil.which("git"):
            raise ManagerError("Spigot needs Git to build. Install Git for Windows from git-scm.com, then try again.")
        java = self.ensure_java(java_major, jdk=True)
        self._progress("Building Spigot (5-10 minutes)", 30)
        self.log("Building Spigot with BuildTools. This takes 5-10 minutes.")
        p = subprocess.Popen([java, "-jar", "BuildTools.jar", "--rev", version], cwd=work,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                             encoding="utf-8", errors="replace", creationflags=NOWINDOW)
        assert p.stdout
        n = 0
        for line in p.stdout:
            self.console.add(f"[buildtools] {line.rstrip()}")
            n += 1
            self._progress("Building Spigot (5-10 minutes)", min(90, 30 + n // 15))
        if p.wait() != 0:
            raise ManagerError("Spigot build failed. Open the console to see the BuildTools log.")
        jars = sorted(work.glob("spigot-*.jar"))
        if not jars:
            raise ManagerError("Spigot build finished but no jar was produced.")
        shutil.copy2(jars[-1], d / "server.jar")
        shutil.rmtree(work, ignore_errors=True)

    # ---- delete -----------------------------------------------------------
    def delete_server(self, sid: str) -> None:
        if self.active_id == sid and self.busy():
            raise ManagerError("Stop the server before deleting it.")
        if self.install_job["active"] and self.install_job["server_id"] == sid:
            raise ManagerError("This server is still installing.")
        shutil.rmtree(server_dir(sid), ignore_errors=True)
        shutil.rmtree(backup_dir(sid), ignore_errors=True)
        remove_server(sid)
        if self.active_id == sid:
            self.active_id = None
            self.state = "offline"

    # ---- start / stop -------------------------------------------------------
    def _build_command(self, meta: dict, java: str) -> list[str]:
        ram = int(meta["ram_mb"])
        cmd = [java, f"-Xms{ram}M", f"-Xmx{ram}M", "-Dfile.encoding=UTF-8"]
        if get_settings().get("tuned_flags", True):
            cmd += ["-XX:+UseG1GC", "-XX:+ParallelRefProcEnabled", "-XX:MaxGCPauseMillis=200",
                    "-XX:+DisableExplicitGC"]
        for text in (get_settings().get("jvm_args", ""), meta.get("jvm_args", "")):
            cmd += parse_jvm_args(text)
        cmd += ["-jar", "server.jar", "nogui"]
        return cmd

    def _port_busy_message(self, port: int) -> str:
        who = ""
        try:
            for c in psutil.net_connections(kind="tcp"):
                if c.status == psutil.CONN_LISTEN and c.laddr and c.laddr.port == port and c.pid:
                    who = f" by {psutil.Process(c.pid).name()} (process {c.pid})"
                    break
        except (psutil.Error, OSError):
            pass
        nxt = next((p for p in range(port + 1, port + 50) if self._port_free(p)), None)
        tip = f" Or give this server another port in Settings, for example {nxt}." if nxt else " Or give this server another port in Settings."
        return (f"Port {port} is already used{who}. It may be an older Minecraft server that is still running: "
                f"close it in Task Manager (java.exe).{tip}")

    @staticmethod
    def _port_free(port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0 if IS_WIN else 1)
            return s.connect_ex(("127.0.0.1", port)) != 0

    def start(self, sid: str) -> None:
        with self.lock:
            if self.busy():
                raise ManagerError("A server is already running or installing. Stop it first.")
            meta = get_server(sid)
            if not meta or not meta.get("installed"):
                raise ManagerError("This server is not installed yet.")
            d = server_dir(sid)
            if not (d / "server.jar").exists():
                raise ManagerError("server.jar is missing. Delete this server and create it again.")
            props = read_props(d / "server.properties")
            port = int(props.get("server-port", meta["port"]))
            if not self._port_free(port):
                raise ManagerError(self._port_busy_message(port))
            avail_mb = psutil.virtual_memory().available // (1024 * 1024)
            if avail_mb < meta["ram_mb"] * 0.9:
                raise ManagerError(f"Only {avail_mb} MB of RAM is free but this server is set to {meta['ram_mb']} MB. "
                                   "Close other apps or lower the RAM in Settings.")
            self.state = "starting"
            self.active_id = sid
            self.stop_requested = False
            self.players.clear()
            self.console.clear()
        threading.Thread(target=self._start_thread, args=(meta,), daemon=True).start()

    def _start_thread(self, meta: dict) -> None:
        sid = meta["id"]
        try:
            major = providers.java_required(meta["version"])
            java = self.ensure_java(major)
            d = server_dir(sid)
            self.reapply_pending(sid, clear=True)
            if self.on_before_start:
                try:
                    self.on_before_start(meta)
                except Exception as e:  # noqa: BLE001  (never block server start on the tunnel)
                    self.log(f"Network helper problem: {e}")
            self.log(f"Starting {meta['name']} ({meta['type']} {meta['version']}, {meta['ram_mb']} MB)")
            cmd = self._build_command(meta, java)
            self.proc = subprocess.Popen(cmd, cwd=d, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                         stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                                         errors="replace", bufsize=1, creationflags=NOWINDOW)
            self.started_at = time.time()
            try:
                self._psproc = psutil.Process(self.proc.pid)
            except psutil.Error:
                self._psproc = None
            update_settings({"last_active": sid})
            threading.Thread(target=self._reader, args=(self.proc, sid), daemon=True).start()
        except Exception as e:  # noqa: BLE001
            msg = str(e) if isinstance(e, (ManagerError, providers.ProviderError, java_rt.JavaError)) \
                else f"Could not start: {e.__class__.__name__}: {e}"
            self.log(msg)
            self.state = "offline"

    def _reader(self, proc: subprocess.Popen, sid: str) -> None:
        assert proc.stdout
        for line in proc.stdout:
            self.console.add(line)
            if DONE_RE.search(line):
                was_online = self.state == "online"
                self.state = "online"
                if not was_online:
                    self._emit("server", f"{self._name(sid)} is online.")
            m = JOIN_RE.search(line)
            if m:
                self.players.add(m.group(1))
                self._emit("player", f"{m.group(1)} joined {self._name(sid)}.")
            m = LEAVE_RE.search(line)
            if m:
                self.players.discard(m.group(1))
                self._emit("player", f"{m.group(1)} left {self._name(sid)}.")
        code = proc.wait()
        for pipe in (proc.stdout, proc.stdin):   # release the file handles of the finished process
            try:
                pipe and pipe.close()
            except (OSError, ValueError):
                pass
        self._on_exit(sid, code)

    def reapply_pending(self, sid: str, clear: bool = False) -> None:
        """Game settings saved while the server was running live only in the file. The Minecraft server can write its own
        (older) values back when it stops, so the panel puts the saved ones back after it stops and before it starts."""
        try:
            meta = get_server(sid)
            pend = (meta or {}).get("pending_props") or {}
            if pend:
                write_props(server_dir(sid) / "server.properties", pend)
                if clear:
                    update_server(sid, {"pending_props": {}})
        except (OSError, ValueError, KeyError) as e:
            self.log(f"Could not restore saved settings: {e}")

    def _on_exit(self, sid: str, code: int) -> None:
        self.reapply_pending(sid)
        with self.lock:
            self.players.clear()
            self.started_at = None
            self._psproc = None
            self.proc = None
            requested = self.stop_requested
            if requested or code == 0:
                self.state = "offline"
                self.log("Server stopped.")
                self._emit("server", f"{self._name(sid)} stopped.")
                return
            self.state = "crashed"
            self.log(f"Server stopped unexpectedly (exit code {code}).")
            self._emit("server", f"{self._name(sid)} crashed (exit code {code}).")
            now = time.time()
            self.crashes = [t for t in self.crashes if now - t < 600] + [now]
            if get_settings().get("auto_restart", True) and len(self.crashes) <= 3:
                self.log("Restarting in 5 seconds.")
                threading.Timer(5, self._auto_restart, args=(sid,)).start()
            elif len(self.crashes) > 3:
                self.log("Crashed 3 times in 10 minutes. Auto-restart is paused. Check the log above.")

    def _auto_restart(self, sid: str) -> None:
        if self.state != "crashed":
            return
        try:
            self.start(sid)
        except ManagerError as e:
            self.log(f"Could not restart: {e}")

    def stop(self) -> None:
        with self.lock:
            if self.state not in ("starting", "online") or not self.proc:
                if self.state == "starting" and not self.proc:
                    raise ManagerError("The server is still getting ready. Try again in a few seconds.")
                raise ManagerError("The server is not running.")
            self.state = "stopping"
            self.stop_requested = True
            proc = self.proc
        self.log("Stopping. Saving the world...")
        self._send_raw(proc, "stop")
        threading.Thread(target=self._kill_later, args=(proc,), daemon=True).start()

    def _kill_later(self, proc: subprocess.Popen, wait: int = 60) -> None:
        try:
            proc.wait(timeout=wait)
        except subprocess.TimeoutExpired:
            self.log(f"Server did not stop in {wait} seconds. Forcing it to close.")
            self._terminate(proc)

    def kill(self) -> None:
        proc = self.proc
        if not proc:
            raise ManagerError("The server is not running.")
        self.stop_requested = True
        self.state = "stopping"
        self.log("Force closing the server. The last few minutes of progress may be lost.")
        self._terminate(proc)

    @staticmethod
    def _terminate(proc: subprocess.Popen) -> None:
        try:
            parent = psutil.Process(proc.pid)
            for c in parent.children(recursive=True):
                c.kill()
            parent.kill()
        except psutil.Error:
            pass

    def restart(self) -> None:
        sid = self.active_id
        if not sid:
            raise ManagerError("No server selected.")
        self.stop()

        def later():
            for _ in range(130):
                if self.state in ("offline", "crashed") and not self.proc:
                    break
                time.sleep(1)
            try:
                self.start(sid)
            except ManagerError as e:
                self.log(f"Could not start again: {e}")
        threading.Thread(target=later, daemon=True).start()

    @staticmethod
    def _send_raw(proc: subprocess.Popen, text: str) -> None:
        try:
            assert proc.stdin
            proc.stdin.write(text + "\n")
            proc.stdin.flush()
        except (OSError, ValueError, AssertionError):
            pass

    def send_command(self, cmd: str) -> None:
        cmd = (cmd or "").strip().lstrip("/")
        if not cmd:
            return
        if "\n" in cmd or "\r" in cmd:
            raise ManagerError("Send one command at a time.")
        if self.state not in ("starting", "online") or not self.proc:
            raise ManagerError("Start the server first.")
        self.console.add(f"> {cmd}")
        self._send_raw(self.proc, cmd)

    # ---- status -------------------------------------------------------------
    def metrics(self) -> dict:
        vm = psutil.virtual_memory()
        out = {"sys_ram_total_mb": vm.total // (1024 * 1024), "sys_ram_used_pct": vm.percent,
               "sys_cpu_pct": psutil.cpu_percent(interval=None), "ram_mb": 0, "cpu_pct": 0.0}
        p = self._psproc
        if p and self.state in ("starting", "online", "stopping"):
            try:
                procs = [p] + p.children(recursive=True)
                out["ram_mb"] = sum(x.memory_info().rss for x in procs) // (1024 * 1024)
                out["cpu_pct"] = round(sum(x.cpu_percent(interval=None) for x in procs) / (psutil.cpu_count() or 1), 1)
            except psutil.Error:
                pass
        return out

    def status(self) -> dict:
        meta = get_server(self.active_id) if self.active_id else None
        uptime = int(time.time() - self.started_at) if self.started_at else 0
        state = self.state
        if self.install_job["active"] and state == "offline":
            state = "installing"
        return {"state": state, "server": meta, "players": sorted(self.players),
                "uptime": uptime, "install": dict(self.install_job), "metrics": self.metrics()}

    def shutdown(self) -> None:
        """Called when the panel exits: stop the server cleanly."""
        proc = self.proc
        if proc and proc.poll() is None:
            self.stop_requested = True
            self.state = "stopping"
            self._send_raw(proc, "stop")
            try:
                proc.wait(timeout=45)
            except subprocess.TimeoutExpired:
                self._terminate(proc)


manager = Manager()
