"""HTTP API + static frontend. Local only: 127.0.0.1, Host check, header check on writes."""
from __future__ import annotations

import asyncio
import contextlib
import functools
import json
import logging
import shutil
import sys
import time
from pathlib import Path

import psutil
from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.responses import FileResponse, HTMLResponse, JSONResponse, Response, StreamingResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from . import brand, consent, instance, support, paths, winmon, winos, backups, fsops, heads, java_rt, mcping, notify, openfolder, players, plugins, providers, servericon
from .manager import ManagerError, manager
from .playit import PlayitError, playit
from .props import clean_props, read_props, write_props
from .scheduler import ScheduleError, Scheduler, clean_schedules
from .store import (DATA, ensure_dirs, get_server, get_settings, list_servers, server_dir,
                    update_server, update_settings, valid_id)

VERSION = brand.VERSION
FRONTEND = paths.FRONTEND
log = logging.getLogger("mcpanel")
USER_ERRORS = (openfolder.OpenError, ManagerError, providers.ProviderError, backups.BackupError, java_rt.JavaError, PlayitError,
               players.PlayerError, fsops.FsError, plugins.PluginError, ScheduleError, mcping.PingError)


class NoCacheStatic(StaticFiles):
    """Page files are always re-checked, so an update never shows a stale screen."""

    async def get_response(self, path, scope):
        r = await super().get_response(path, scope)
        r.headers["Cache-Control"] = "no-cache"
        return r


# ---- plumbing ---------------------------------------------------------------

class Guard:
    """Stops other websites and other computers from using the local API."""

    def __init__(self, app, allowed_hosts=("127.0.0.1", "localhost")):
        self.app = app
        self.allowed = allowed_hosts

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            h = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope["headers"]}
            host = h.get("host", "").rsplit(":", 1)[0] if not h.get("host", "").startswith("[") else ""
            if host not in self.allowed:
                return await JSONResponse({"error": "Not allowed."}, status_code=403)(scope, receive, send)
            if scope["method"] not in ("GET", "HEAD", "OPTIONS") and h.get("x-mcpanel") != "1":
                return await JSONResponse({"error": "Not allowed."}, status_code=403)(scope, receive, send)
        await self.app(scope, receive, send)


def api(fn):
    @functools.wraps(fn)
    async def wrapper(request):
        try:
            res = await fn(request)
            return res if isinstance(res, Response) else JSONResponse(res)
        except USER_ERRORS as e:
            return JSONResponse({"error": str(e)}, status_code=400)
        except Exception:  # noqa: BLE001
            log.exception("API error on %s", request.url.path)
            return JSONResponse({"error": "Something went wrong inside the panel. Check the panel window for details."},
                                status_code=500)
    return wrapper


async def body(request) -> dict:
    try:
        data = await request.json()
    except Exception:  # noqa: BLE001
        raise ManagerError("The request was not understood.") from None
    if not isinstance(data, dict):
        raise ManagerError("The request was not understood.")
    return data


def need_server(sid: str) -> dict:
    meta = get_server(sid) if valid_id(sid) else None
    if not meta:
        raise ManagerError("That server was not found.")
    return meta


def sid_of(request) -> str:
    return need_server(request.path_params["sid"])["id"]


def is_running(sid: str) -> bool:
    return manager.active_id == sid and manager.busy()


def public_settings() -> dict:
    s = get_settings()
    s["playit_secret_set"] = bool(s.pop("playit_secret", ""))
    s["discord_webhook_set"] = bool(s.pop("discord_webhook", ""))   # the link lets anyone post, so it is never sent back
    return s


# ---- Windows settings ---------------------------------------------------------------------------------------------

def windows_state() -> dict:
    s = get_settings()
    return {"available": winos.IS_WINDOWS, "autostart": winos.autostart_get(), "keep_awake": s["keep_awake"], "toasts": s["toasts"]}


@api
async def show_window(request):
    fn = instance.show_callback
    return {"shown": bool(fn and await run_in_threadpool(fn))}


@api
async def get_windows(request):
    return windows_state()


@api
async def put_windows(request):
    d = await body(request)
    if "autostart" in d:
        if not winos.IS_WINDOWS:
            raise ManagerError("Start with Windows only works on Windows.")
        await run_in_threadpool(winos.autostart_set, bool(d["autostart"]))
    patch = {k: bool(d[k]) for k in ("keep_awake", "toasts") if k in d}
    if patch:
        update_settings(patch)
    return windows_state()


# ---- privacy, support, first-run setup ----------------------------------------------------------------------------

@api
async def get_consent(request):
    return consent.get()


@api
async def put_consent(request):
    d = await body(request)
    if d.get("accept"):
        return consent.accept(bool(d.get("heads")))
    if "heads" in d:
        if not consent.get()["accepted"]:
            raise ManagerError("Accept the privacy policy first.")
        return consent.set_heads(bool(d["heads"]))
    raise ManagerError("Nothing to change.")


@api
async def get_support_report(request):
    return {"text": await run_in_threadpool(support.report)}


@api
async def get_components(request):
    return await run_in_threadpool(support.components.status)


@api
async def post_components(request):
    return await run_in_threadpool(support.components.prepare)


# ---- routes: general ----------------------------------------------------------

async def index(request):
    html = (FRONTEND / "index.html").read_text(encoding="utf-8").replace("__NAME__", brand.NAME)
    return HTMLResponse(html, headers={"Cache-Control": "no-cache"})


async def brand_js(request):
    return Response(brand.js(), media_type="text/javascript", headers={"Cache-Control": "no-cache"})


async def ping(request):
    """Lets a second start find the copy that is already running (see run.py)."""
    return JSONResponse({"app": brand.DATA_KEY, "version": brand.VERSION})


@api
async def status(request):
    st = manager.status()
    return {"version": VERSION, **st, "servers": [{**s, "icon": servericon.version(s["id"])} for s in list_servers()], "playit": playit.status(),
            "settings": public_settings(), "now": int(time.time())}


@api
async def system(request):
    vm = psutil.virtual_memory()
    d = DATA if DATA.exists() else Path.home()
    return {"platform": sys.platform, "ram_total_mb": vm.total // (1024 * 1024),
            "disk_free_gb": round(shutil.disk_usage(d).free / 1e9, 1), "cpus": psutil.cpu_count() or 1,
            "git": bool(shutil.which("git")),
            "types": {k: {**v, "extends": (plugins.kind_for(k) or [None])[0]} for k, v in providers.TYPES.items()}, "version": VERSION, "data_dir": str(DATA), "app": brand.public()}


@api
async def versions(request):
    stype = request.query_params.get("type", "")
    if stype not in providers.TYPES:
        raise ManagerError("Choose a server type.")
    return {"versions": await run_in_threadpool(providers.list_versions, stype)}


# ---- servers ------------------------------------------------------------------

@api
async def create_server(request):
    d = await body(request)
    icon = None
    if d.get("icon"):
        try:
            icon = servericon.decode(str(d["icon"]))
        except servericon.IconError as e:
            raise ManagerError(str(e)) from None
    try:
        meta = await run_in_threadpool(
            manager.create_server, str(d.get("name", "")), str(d.get("type", "")), str(d.get("version", "")),
            int(d.get("ram_mb", get_settings()["default_ram_mb"])), int(d.get("port", 25565)),
            bool(d.get("eula")), str(d.get("motd", "")), d.get("properties"), str(d.get("jvm_args", "")),
            icon, d.get("starter") if isinstance(d.get("starter"), list) else None)
    except (TypeError, ValueError):
        raise ManagerError("RAM and port must be numbers.") from None
    return {"server": meta}


async def get_icon(request):
    try:
        sid = sid_of(request)
    except ManagerError:
        return Response(status_code=404)
    data = await run_in_threadpool(servericon.read, sid)
    if data is None:
        return Response(status_code=404)
    return Response(data, media_type="image/png", headers={"Cache-Control": "no-cache"})


@api
async def put_icon(request):
    sid = sid_of(request)
    need_server(sid)
    try:
        await run_in_threadpool(servericon.save, sid, await request.body())
    except servericon.IconError as e:
        raise ManagerError(str(e)) from None
    return {"icon": servericon.version(sid)}


@api
async def delete_icon(request):
    sid = sid_of(request)
    need_server(sid)
    await run_in_threadpool(servericon.remove, sid)
    return {"icon": 0}


@api
async def patch_server(request):
    sid = sid_of(request)
    return {"server": await run_in_threadpool(manager.update_config, sid, await body(request))}


@api
async def delete_server(request):
    await run_in_threadpool(manager.delete_server, sid_of(request))
    return {"ok": True}


@api
async def start_server(request):
    await run_in_threadpool(manager.start, sid_of(request))
    return {"ok": True}


@api
async def stop_server(request):
    await run_in_threadpool(manager.stop)
    return {"ok": True}


@api
async def restart_server(request):
    await run_in_threadpool(manager.restart)
    return {"ok": True}


@api
async def kill_server(request):
    await run_in_threadpool(manager.kill)
    return {"ok": True}


@api
async def command(request):
    d = await body(request)
    manager.send_command(str(d.get("command", "")))
    return {"ok": True}


@api
async def console_since(request):
    try:
        after = int(request.query_params.get("after", "0"))
    except ValueError:
        after = 0
    rows = manager.console.since(after)
    return {"lines": [{"seq": s, "text": t} for s, t in rows], "last": manager.console.last_seq}


async def console_stream(request):
    try:
        after = int(request.query_params.get("after") or request.headers.get("last-event-id") or 0)
    except ValueError:
        after = 0

    async def gen():
        nonlocal after
        last_ping = time.time()
        yield "retry: 1500\n\n"
        while not await request.is_disconnected():
            rows = manager.console.since(after)
            for seq, text in rows:
                after = seq
                yield f"id: {seq}\ndata: {json.dumps(text)}\n\n"
            if rows:
                last_ping = time.time()
            elif time.time() - last_ping > 15:
                last_ping = time.time()
                yield ": ping\n\n"
            await asyncio.sleep(0.3)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ---- properties ---------------------------------------------------------------

@api
async def get_props(request):
    sid = sid_of(request)
    return {"properties": read_props(server_dir(sid) / "server.properties"),
            "running": manager.active_id == sid and manager.state in ("starting", "online")}


@api
async def put_props(request):
    sid = sid_of(request)
    d = await body(request)
    try:
        clean = clean_props(d.get("properties"))
    except ValueError as e:
        raise ManagerError(str(e)) from None
    if not clean:
        raise ManagerError("Nothing to save.")
    if "server-port" in clean:
        try:
            if not 1024 <= int(clean["server-port"]) <= 65535:
                raise ValueError
        except ValueError:
            raise ManagerError("Port must be a number between 1024 and 65535.") from None
        update_server(sid, {"port": int(clean["server-port"])})
    await run_in_threadpool(write_props, server_dir(sid) / "server.properties", clean)
    live = manager.active_id == sid and manager.state in ("starting", "online", "stopping")
    meta = get_server(sid) or {}
    pend = dict(meta.get("pending_props") or {})
    if live:
        pend.update(clean)                       # kept and put back after the server stops (see manager.reapply_pending)
    else:
        for k in clean:
            pend.pop(k, None)
    if pend != (meta.get("pending_props") or {}):
        update_server(sid, {"pending_props": pend})
    if "motd" in clean:
        update_server(sid, {"motd": clean["motd"][:120]})
    return {"ok": True}


# ---- backups ------------------------------------------------------------------

@api
async def get_backups(request):
    return {"backups": backups.list_backups(sid_of(request))}


def _backup_now(sid: str, label: str = "manual") -> dict:
    running = manager.active_id == sid and manager.state == "online"
    if running:
        try:
            manager.send_command("save-off")
            manager.send_command("save-all flush")
            time.sleep(3)
        except ManagerError:
            running = False
    try:
        return backups.create_backup(sid, label)
    finally:
        if running:
            with contextlib.suppress(ManagerError):
                manager.send_command("save-on")


async def get_head(request):
    if not consent.heads_allowed():                      # contacts another website, so only after the person said yes
        return Response(status_code=404)
    data = await run_in_threadpool(heads.get, request.path_params["name"])
    if not data:
        return Response(status_code=404)
    return Response(data, media_type="image/png", headers={"Cache-Control": "max-age=86400"})


@api
async def post_open_folder(request):
    d = await body(request)
    path = await run_in_threadpool(openfolder.open_folder, str(d.get("which", "")), d.get("sid"))
    return {"ok": True, "path": path}


@api
async def post_backup(request):
    return {"backup": await run_in_threadpool(_backup_now, sid_of(request))}


@api
async def delete_backup(request):
    backups.delete_backup(sid_of(request), request.path_params["name"])
    return {"ok": True}


@api
async def restore_backup(request):
    sid = sid_of(request)
    if is_running(sid):
        raise ManagerError("Stop the server before restoring a backup.")
    await run_in_threadpool(backups.restore_backup, sid, request.path_params["name"])
    return {"ok": True}


@api
async def download_backup(request):
    sid = sid_of(request)
    name = backups.safe_name(request.path_params["name"])
    p = backups.backup_dir(sid) / name
    if not p.exists():
        raise ManagerError("Backup not found.")
    return FileResponse(p, filename=name, media_type="application/zip")


# ---- players ------------------------------------------------------------------

@api
async def get_players(request):
    sid = sid_of(request)
    data = await run_in_threadpool(players.overview, sid)
    online = sorted(manager.players) if manager.active_id == sid and manager.state == "online" else []
    return {**data, "online": online, "running": manager.active_id == sid and manager.state == "online"}


@api
async def player_action(request):
    sid = sid_of(request)
    d = await body(request)
    running = manager.active_id == sid and manager.state == "online"
    msg = await run_in_threadpool(players.apply, sid, str(d.get("action", "")), str(d.get("name", "")),
                                  str(d.get("value", "")), running, manager.send_command)
    return {"message": msg}


# ---- files --------------------------------------------------------------------

@api
async def files_list(request):
    return await run_in_threadpool(fsops.listdir, server_dir(sid_of(request)), request.query_params.get("path", ""))


@api
async def file_read(request):
    return await run_in_threadpool(fsops.read_text, server_dir(sid_of(request)), request.query_params.get("path", ""))


@api
async def file_write(request):
    sid = sid_of(request)
    d = await body(request)
    content = d.get("content")
    if not isinstance(content, str):
        raise ManagerError("Nothing to save.")
    await run_in_threadpool(fsops.write_text, server_dir(sid), str(d.get("path", "")), content)
    return {"ok": True}


@api
async def file_mkdir(request):
    sid = sid_of(request)
    d = await body(request)
    await run_in_threadpool(fsops.mkdir, server_dir(sid), str(d.get("path", "")), str(d.get("name", "")))
    return {"ok": True}


@api
async def file_delete(request):
    sid = sid_of(request)
    d = await body(request)
    await run_in_threadpool(fsops.delete, server_dir(sid), str(d.get("path", "")), is_running(sid))
    return {"ok": True}


@api
async def file_rename(request):
    sid = sid_of(request)
    d = await body(request)
    await run_in_threadpool(fsops.rename, server_dir(sid), str(d.get("path", "")), str(d.get("name", "")), is_running(sid))
    return {"ok": True}


@api
async def file_upload(request):
    sid = sid_of(request)
    root = server_dir(sid)
    dest = fsops.upload_target(root, request.query_params.get("path", ""), request.query_params.get("name", ""))
    part = dest.with_name(dest.name + ".part")
    size = 0
    try:
        with open(part, "wb") as f:
            async for chunk in request.stream():
                size += len(chunk)
                if size > fsops.MAX_UPLOAD:
                    raise fsops.FsError("That file is larger than 512 MB.")
                await run_in_threadpool(f.write, chunk)
        part.replace(dest)
    except BaseException:
        part.unlink(missing_ok=True)
        raise
    return {"ok": True, "size": size}


@api
async def file_download(request):
    sid = sid_of(request)
    p = fsops.resolve(server_dir(sid), request.query_params.get("path", ""))
    if not p.is_file():
        raise ManagerError("That file does not exist.")
    return FileResponse(p, filename=p.name)


# ---- plugins / mods -------------------------------------------------------------

@api
async def plugins_list(request):
    return await run_in_threadpool(plugins.list_installed, sid_of(request))


@api
async def plugins_toggle(request):
    sid = sid_of(request)
    d = await body(request)
    plugins.set_enabled(sid, str(d.get("file", "")), bool(d.get("enabled")))
    return {"ok": True}


@api
async def plugins_remove(request):
    sid = sid_of(request)
    plugins.remove(sid, str((await body(request)).get("file", "")))
    return {"ok": True}


@api
async def plugins_search(request):
    sid = sid_of(request)
    try:
        offset = int(request.query_params.get("offset", "0"))
    except ValueError:
        offset = 0
    return await run_in_threadpool(plugins.search, sid, request.query_params.get("q", ""), offset)


@api
async def plugins_install(request):
    sid = sid_of(request)
    d = await body(request)
    return await run_in_threadpool(plugins.install, sid, str(d.get("project_id", "")))


# ---- schedule / worlds ----------------------------------------------------------

@api
async def get_schedules(request):
    return {"schedules": need_server(request.path_params["sid"]).get("schedules", [])}


@api
async def put_schedules(request):
    sid = sid_of(request)
    jobs = clean_schedules((await body(request)).get("schedules"))
    update_server(sid, {"schedules": jobs})
    return {"schedules": jobs}


def _level_dirs(sid: str) -> list[str]:
    level = Path(read_props(server_dir(sid) / "server.properties").get("level-name", "world")).name or "world"
    return [level, level + "_nether", level + "_the_end"]


@api
async def worlds_list(request):
    sid = sid_of(request)
    root = server_dir(sid)

    def scan():
        out = []
        for n in _level_dirs(sid):
            p = root / n
            if p.is_dir():
                out.append({"name": n, "size": fsops.dir_size(p), "main": n == _level_dirs(sid)[0]})
        return out
    return {"worlds": await run_in_threadpool(scan), "running": is_running(sid)}


@api
async def worlds_reset(request):
    sid = sid_of(request)
    d = await body(request)
    if not d.get("confirm"):
        raise ManagerError("Confirm the reset first.")
    if is_running(sid):
        raise ManagerError("Stop the server before resetting the world.")

    def work():
        info = backups.create_backup(sid, "before-reset")
        for n in _level_dirs(sid):
            shutil.rmtree(server_dir(sid) / n, ignore_errors=True)
        return info
    return {"backup": await run_in_threadpool(work)}


# ---- settings / network ---------------------------------------------------------

@api
async def get_settings_route(request):
    return public_settings()


@api
async def put_settings(request):
    d = await body(request)
    if d.pop("clear_playit_secret", False):
        d["playit_secret"] = ""
    elif not str(d.get("playit_secret", "")).strip():
        d.pop("playit_secret", None)   # blank box means "keep the saved key"
    if d.pop("clear_discord_webhook", False):
        d["discord_webhook"] = ""
    elif not str(d.get("discord_webhook", "")).strip():
        d.pop("discord_webhook", None)   # blank box means "keep the saved link"
    elif not notify.valid_webhook(str(d["discord_webhook"]).strip()):
        raise ManagerError("That is not a Discord webhook link. It starts with https://discord.com/api/webhooks/")
    if "jvm_args" in d:
        from .manager import parse_jvm_args
        parse_jvm_args(str(d["jvm_args"]))
    try:
        update_settings(d)
    except (TypeError, ValueError):
        raise ManagerError("One of the settings has an invalid value.") from None
    return public_settings()


@api
async def network_start(request):
    if get_settings().get("playit_mode") == "external":
        raise PlayitError("You chose 'Use my own playit app'. Start that app yourself and paste its address below.")
    try:
        d = await body(request)
    except Exception:  # noqa: BLE001  (an empty body is fine)
        d = {}
    sid = str(d.get("sid") or manager.active_id or get_settings().get("last_active") or "")
    meta = get_server(sid) if sid and valid_id(sid) else None
    playit.start(local_port=meta["port"] if meta else None, tag=meta["id"] if meta else None)
    return playit.status()


@api
async def network_stop(request):
    await run_in_threadpool(playit.stop)
    return playit.status()


@api
async def network_unlink(request):
    await run_in_threadpool(playit.unlink)
    return playit.status()


@api
async def network_diagnostics(request):
    return {"text": playit.diagnostics()}


@api
async def network_address(request):
    d = await body(request)
    addr = str(d.get("address", "")).strip()
    if len(addr) > 120 or any(c in addr for c in " \r\n/\\"):
        raise ManagerError("That does not look like a server address. Paste it like name.ply.gg:12345.")
    update_settings({"playit_address": addr})
    return playit.status()


@api
async def network_test(request):
    """Ask a server the way the in-game server list does: this PC, or the public address friends use."""
    d = await body(request)
    if d.get("target") == "local":
        meta = need_server(str(d.get("sid", "")))
        port = read_props(server_dir(meta["id"]) / "server.properties").get("server-port", "")
        host, port = "127.0.0.1", int(port) if port.isdigit() else int(meta["port"])
    else:
        addr = playit.status()["address"]
        if not addr:
            raise ManagerError("There is no public address yet. Start the server and the network helper first.")
        host, port = mcping.parse_address(addr)
    return await run_in_threadpool(mcping.ping, host, port)


@api
async def notify_test(request):
    err = await run_in_threadpool(notify.send, f"Test message from {brand.NAME}. Discord notices work.")
    if err:
        raise ManagerError(err)
    return {"ok": True}


def _before_start(meta: dict):
    if get_settings().get("playit_auto", True):
        port = read_props(server_dir(meta["id"]) / "server.properties").get("server-port", "")
        playit.start(local_port=int(port) if port.isdigit() else meta["port"], tag=meta["id"])


def _job_restart(sid: str, job: dict) -> None:
    for secs in (60, 30, 10):
        if manager.state != "online":
            return
        with contextlib.suppress(ManagerError):
            manager.send_command(f"say Scheduled restart in {secs} seconds.")
        time.sleep(30 if secs == 60 else 20 if secs == 30 else 10)
    if manager.state == "online":
        manager.restart()


def _job_backup(sid: str, job: dict) -> None:
    _backup_now(sid, "scheduled")
    backups.prune(sid, "scheduled", int(job.get("keep", 5)))


scheduler = Scheduler(manager, {"restart": _job_restart, "backup": _job_backup,
                                "command": lambda sid, job: manager.send_command(job["command"])})


monitor = winmon.Monitor(manager)


def _fanout(kind, text):
    notify.event(kind, text)
    monitor.event(kind, text)


@contextlib.asynccontextmanager
async def lifespan(app):
    ensure_dirs()
    manager.on_before_start = _before_start
    manager.on_event = _fanout
    scheduler.start()
    monitor.start()
    yield
    monitor.stop()
    scheduler.stop()
    await run_in_threadpool(manager.shutdown)
    await run_in_threadpool(playit.stop)


S = "/api/servers/{sid}"
routes = [
    Route("/", index),
    Route("/brand.js", brand_js),
    Route("/api/ping", ping),
    Route("/api/show-window", show_window, methods=["POST"]),
    Route("/api/consent", get_consent, methods=["GET"]),
    Route("/api/consent", put_consent, methods=["PUT"]),
    Route("/api/support/report", get_support_report, methods=["GET"]),
    Route("/api/components", get_components, methods=["GET"]),
    Route("/api/components/prepare", post_components, methods=["POST"]),
    Route("/api/windows", get_windows, methods=["GET"]),
    Route("/api/windows", put_windows, methods=["PUT"]),
    Route("/api/status", status),
    Route("/api/system", system),
    Route("/api/versions", versions),
    Route("/api/servers", create_server, methods=["POST"]),
    Route("/api/servers/{sid}/icon", get_icon, methods=["GET"]),
    Route("/api/servers/{sid}/icon", put_icon, methods=["PUT"]),
    Route("/api/servers/{sid}/icon", delete_icon, methods=["DELETE"]),
    Route(S, patch_server, methods=["PATCH"]),
    Route(S, delete_server, methods=["DELETE"]),
    Route(S + "/start", start_server, methods=["POST"]),
    Route("/api/stop", stop_server, methods=["POST"]),
    Route("/api/restart", restart_server, methods=["POST"]),
    Route("/api/kill", kill_server, methods=["POST"]),
    Route("/api/command", command, methods=["POST"]),
    Route("/api/console", console_since),
    Route("/api/console/stream", console_stream),
    Route(S + "/properties", get_props, methods=["GET"]),
    Route(S + "/properties", put_props, methods=["PUT"]),
    Route("/api/open-folder", post_open_folder, methods=["POST"]),
    Route("/api/head/{name}", get_head, methods=["GET"]),
    Route(S + "/backups", get_backups, methods=["GET"]),
    Route(S + "/backups", post_backup, methods=["POST"]),
    Route(S + "/backups/{name}", delete_backup, methods=["DELETE"]),
    Route(S + "/backups/{name}/restore", restore_backup, methods=["POST"]),
    Route(S + "/backups/{name}/download", download_backup, methods=["GET"]),
    Route(S + "/players", get_players, methods=["GET"]),
    Route(S + "/players/action", player_action, methods=["POST"]),
    Route(S + "/files", files_list, methods=["GET"]),
    Route(S + "/file", file_read, methods=["GET"]),
    Route(S + "/file", file_write, methods=["PUT"]),
    Route(S + "/files/mkdir", file_mkdir, methods=["POST"]),
    Route(S + "/files/delete", file_delete, methods=["POST"]),
    Route(S + "/files/rename", file_rename, methods=["POST"]),
    Route(S + "/files/upload", file_upload, methods=["POST"]),
    Route(S + "/download", file_download, methods=["GET"]),
    Route(S + "/plugins", plugins_list, methods=["GET"]),
    Route(S + "/plugins/toggle", plugins_toggle, methods=["POST"]),
    Route(S + "/plugins/remove", plugins_remove, methods=["POST"]),
    Route(S + "/plugins/search", plugins_search, methods=["GET"]),
    Route(S + "/plugins/install", plugins_install, methods=["POST"]),
    Route(S + "/schedules", get_schedules, methods=["GET"]),
    Route(S + "/schedules", put_schedules, methods=["PUT"]),
    Route(S + "/worlds", worlds_list, methods=["GET"]),
    Route(S + "/worlds/reset", worlds_reset, methods=["POST"]),
    Route("/api/settings", get_settings_route, methods=["GET"]),
    Route("/api/settings", put_settings, methods=["PUT"]),
    Route("/api/network/start", network_start, methods=["POST"]),
    Route("/api/network/stop", network_stop, methods=["POST"]),
    Route("/api/network/unlink", network_unlink, methods=["POST"]),
    Route("/api/network/diagnostics", network_diagnostics, methods=["GET"]),
    Route("/api/network/address", network_address, methods=["POST"]),
    Route("/api/network/test", network_test, methods=["POST"]),
    Route("/api/notify/test", notify_test, methods=["POST"]),
    Mount("/static", NoCacheStatic(directory=FRONTEND, check_dir=False)),
]

app = Guard(Starlette(routes=routes, lifespan=lifespan))
