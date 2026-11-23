"""Backups as zip files: what is saved, where, how it is checked and how it is restored.

Every backup holds a small info file (zighost-backup.json) next to the server files, so the app can later show
what a backup is and warn before restoring it onto another Minecraft version."""
from __future__ import annotations

import json
import re
import shutil
import time
import zipfile
from pathlib import Path

from .props import read_props
from .store import SERVERS_DIR, backup_dir, get_server, server_dir

# Not worth backing up in the "standard" kind: can be downloaded again
SKIP_DIRS = {"logs", "cache", "libraries", "versions", ".fabric", "crash-reports"}
SKIP_TOP_SUFFIX = (".jar",)
SCOPES = ("world", "standard", "full")
MODES = ("all", "world", "config")
MANIFEST = "zighost-backup.json"
NAME_RE = re.compile(r"^\d{8}-\d{6}_[A-Za-z0-9_-]{1,24}\.zip$")
PROGRESS: dict[str, dict] = {}


class BackupError(Exception):
    pass


def _should_skip(rel: Path) -> bool:
    parts = rel.parts
    if parts[0] in SKIP_DIRS:
        return True
    if len(parts) == 1 and parts[0].lower().endswith(SKIP_TOP_SUFFIX):
        return True
    return False


def safe_name(name: str) -> str:
    if not name or "/" in name or "\\" in name or ".." in name or not name.endswith(".zip"):
        raise BackupError("Invalid backup name.")
    return name


def level_dirs(root: Path) -> list[str]:
    level = Path(read_props(root / "server.properties").get("level-name", "world")).name or "world"
    return [level, level + "_nether", level + "_the_end"]


def progress(sid: str) -> dict:
    return PROGRESS.get(sid) or {"active": False, "pct": 0, "step": ""}


# ---- where backups are kept ---------------------------------------------------------

def check_folder(raw: str) -> dict:
    """Check a folder the person chose for backups. Returns its full path and free space."""
    raw = str(raw or "").strip().strip('"')
    if not raw:
        raise BackupError("Choose a folder first.")
    p = Path(raw).expanduser()
    if not p.is_absolute():
        raise BackupError("Use the full folder path, for example D:\\Backups.")
    p = p.resolve()
    servers = SERVERS_DIR.resolve()
    if p == servers or servers in p.parents:
        raise BackupError("Pick a folder outside the servers folder. A backup stored inside a server would copy itself.")
    try:
        p.mkdir(parents=True, exist_ok=True)
        probe = p / ".write-test"
        probe.write_text("ok")
        probe.unlink()
    except OSError as e:
        raise BackupError(f"This folder cannot be used: {e.strerror or e}.") from None
    return {"path": str(p), "free": shutil.disk_usage(p).free}


def move_backups(old: Path, new: Path) -> int:
    """Move the backup files of one server from the old folder into the new one."""
    if not old.is_dir() or old.resolve() == new.resolve():
        return 0
    new.mkdir(parents=True, exist_ok=True)
    files = [p for p in old.glob("*.zip") if p.is_file()]
    clash = [p.name for p in files if (new / p.name).exists()]
    if clash:
        raise BackupError(f"The new folder already has a file named {clash[0]}. Nothing was moved.")
    for p in files:
        shutil.move(str(p), str(new / p.name))
    return len(files)


def purge(sid: str) -> None:
    """Delete the backup files this app made for a server (used when the server is deleted). The folder itself is
    only removed when it is empty, because the person may share it with other things."""
    d = backup_dir(sid)
    if not d.is_dir():
        return
    for p in d.glob("*.zip"):
        if NAME_RE.match(p.name):
            p.unlink(missing_ok=True)
    try:
        d.rmdir()
    except OSError:
        pass


# ---- listing and checking ------------------------------------------------------------

def _info(p: Path) -> dict:
    st = p.stat()
    out = {"name": p.name, "size": st.st_size, "created": int(st.st_mtime),
           "label": p.stem.split("_", 1)[1] if "_" in p.stem else "", "scope": "", "version": "", "type": "",
           "server": "", "damaged": False}
    try:
        with zipfile.ZipFile(p) as z:
            if MANIFEST in z.namelist():
                m = json.loads(z.read(MANIFEST).decode("utf-8"))
                out.update(scope=m.get("scope", ""), version=m.get("server", {}).get("version", ""),
                           type=m.get("server", {}).get("type", ""), server=m.get("server", {}).get("name", ""))
    except (zipfile.BadZipFile, OSError, ValueError, KeyError):
        out["damaged"] = True
    return out


def list_backups(sid: str) -> list[dict]:
    d = backup_dir(sid)
    if not d.exists():
        return []
    return [_info(p) for p in sorted(d.glob("*.zip"), reverse=True)]


def verify(sid: str, name: str) -> dict:
    p = backup_dir(sid) / safe_name(name)
    if not p.exists():
        raise BackupError("Backup not found.")
    try:
        with zipfile.ZipFile(p) as z:
            bad = z.testzip()
            return {"ok": bad is None, "files": len(z.namelist()), "bad": bad or ""}
    except (zipfile.BadZipFile, OSError):
        return {"ok": False, "files": 0, "bad": "the file is not a readable zip"}


def _safe_members(z: zipfile.ZipFile, root: Path) -> list[zipfile.ZipInfo]:
    members = []
    rr = root.resolve()
    for info in z.infolist():
        if info.filename == MANIFEST or info.is_dir():
            continue
        if ((info.external_attr >> 16) & 0o170000) == 0o120000:
            raise BackupError("This backup holds a link, so it was not used.")
        target = (root / info.filename).resolve()
        if rr not in target.parents:
            raise BackupError("This backup has an unsafe path inside and was not used.")
        members.append(info)
    return members


# ---- making a backup -----------------------------------------------------------------

def _files_for(src: Path, scope: str) -> list[Path]:
    out: list[Path] = []
    if scope == "world":
        for n in level_dirs(src):
            if (src / n).is_dir():
                out += [p for p in (src / n).rglob("*") if p.is_file() and p.name != "session.lock"]
        return out
    for p in src.rglob("*"):
        if not p.is_file() or p.name in ("session.lock",) or p.name.endswith(".part"):
            continue
        if scope == "standard" and _should_skip(p.relative_to(src)):
            continue
        out.append(p)
    return out


def create_backup(sid: str, label: str = "manual", scope: str | None = None) -> dict:
    src = server_dir(sid)
    if not src.exists():
        raise BackupError("Server folder not found.")
    meta = get_server(sid) or {}
    scope = scope if scope in SCOPES else (meta.get("backup_scope") if meta.get("backup_scope") in SCOPES else "standard")
    d = backup_dir(sid)
    try:
        d.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise BackupError(f"The backup folder cannot be used: {e.strerror or e}. Choose another one on the Backups page.") from None
    label = "".join(c for c in label if c.isalnum() or c in "-_")[:24] or "manual"
    name = f"{time.strftime('%Y%m%d-%H%M%S')}_{label}.zip"
    tmp = d / (name + ".part")
    PROGRESS[sid] = {"active": True, "pct": 0, "step": "Reading the server files"}
    try:
        files = _files_for(src, scope)
        total = max(1, len(files))
        need = sum(p.stat().st_size for p in files if p.exists())
        if shutil.disk_usage(d).free < need // 2 + 50 * 1024 * 1024:
            raise BackupError("There is not enough free space in the backup folder.")
        manifest = {"format": 1, "created": int(time.time()), "label": label, "scope": scope, "files": len(files),
                    "server": {"name": meta.get("name", ""), "type": meta.get("type", ""), "version": meta.get("version", "")}}
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr(MANIFEST, json.dumps(manifest, indent=1))
            for i, p in enumerate(files):
                try:
                    z.write(p, p.relative_to(src).as_posix())
                except OSError:
                    continue  # file locked or vanished: skip it, keep the backup
                if i % 20 == 0:
                    PROGRESS[sid] = {"active": True, "pct": int(90 * i / total), "step": "Saving files"}
        PROGRESS[sid] = {"active": True, "pct": 92, "step": "Checking the backup"}
        with zipfile.ZipFile(tmp) as z:
            if z.testzip() is not None:
                raise BackupError("The backup file could not be verified, so it was not kept. Try again.")
        tmp.replace(d / name)
    except (OSError, zipfile.BadZipFile) as e:
        tmp.unlink(missing_ok=True)
        raise BackupError(f"The backup failed: {getattr(e, 'strerror', None) or e}.") from None
    except BackupError:
        tmp.unlink(missing_ok=True)
        raise
    finally:
        PROGRESS[sid] = {"active": False, "pct": 100, "step": "Done"}
    info = _info(d / name)
    if not label.startswith("before"):
        info["removed"] = apply_rules(sid)
    return info


def apply_rules(sid: str) -> list[str]:
    """Delete old backups by the server's clean-up rules (keep at most N, keep at most D days, stay under G GB).
    The newest backup is never removed."""
    rules = (get_server(sid) or {}).get("backup_rules") or {}
    count, days, gb = (int(rules.get(k) or 0) for k in ("count", "days", "gb"))
    if not (count or days or gb):
        return []
    d = backup_dir(sid)
    files = sorted((p for p in d.glob("*.zip") if NAME_RE.match(p.name)), key=lambda p: p.stat().st_mtime, reverse=True)
    doomed: list[Path] = []
    if count:
        doomed += files[max(1, count):]
    if days:
        cut = time.time() - days * 86400
        doomed += [p for p in files[1:] if p.stat().st_mtime < cut]
    if gb:
        total, keep = 0, []
        for p in files:
            total += p.stat().st_size
            if total > gb * 1024 ** 3 and keep:
                doomed.append(p)
            else:
                keep.append(p)
    gone = []
    for p in dict.fromkeys(doomed):
        p.unlink(missing_ok=True)
        gone.append(p.name)
    return gone


def prune(sid: str, label: str, keep: int) -> int:
    """Keep only the newest `keep` backups made with this label. Returns how many were deleted."""
    d = backup_dir(sid)
    old = sorted(d.glob(f"*_{label}.zip"), reverse=True)[max(1, keep):]
    for p in old:
        p.unlink(missing_ok=True)
    return len(old)


def delete_backup(sid: str, name: str) -> None:
    (backup_dir(sid) / safe_name(name)).unlink(missing_ok=True)


def import_backup(sid: str, path: str) -> dict:
    """Copy a zip file the person has on this PC into the backup folder."""
    p = Path(str(path or "").strip().strip('"')).expanduser()
    if not p.is_absolute() or not p.is_file() or p.suffix.lower() != ".zip":
        raise BackupError("Choose a .zip file with its full path.")
    try:
        with zipfile.ZipFile(p) as z:
            if z.testzip() is not None:
                raise BackupError("That zip file is damaged.")
            _safe_members(z, server_dir(sid))
    except zipfile.BadZipFile:
        raise BackupError("That file is not a zip file.") from None
    d = backup_dir(sid)
    d.mkdir(parents=True, exist_ok=True)
    name = f"{time.strftime('%Y%m%d-%H%M%S')}_imported.zip"
    shutil.copy2(p, d / name)
    return _info(d / name)


# ---- restoring -----------------------------------------------------------------------

def zip_worlds(names: list[str]) -> set[str]:
    base = {n.split("/")[0] for n in names if n.endswith("/level.dat") and n.count("/") == 1}
    out = set(base)
    for b in base:
        out |= {b + "_nether", b + "_the_end"}
    return {w for w in out if any(n.startswith(w + "/") for n in names)}


def restore_into(dst: Path, zip_path: Path, mode: str = "all") -> int:
    """Put the content of a backup into a server folder. Returns the number of files restored."""
    if mode not in MODES:
        raise BackupError("Unknown restore kind.")
    with zipfile.ZipFile(zip_path) as z:
        members = _safe_members(z, dst)
        worlds = zip_worlds([m.filename for m in members])
        top = lambda m: m.filename.split("/")[0]  # noqa: E731
        if mode == "world":
            if not worlds:
                raise BackupError("This backup holds no world.")
            chosen = [m for m in members if top(m) in worlds]
        elif mode == "config":
            chosen = [m for m in members if top(m) not in worlds]
            if not chosen:
                raise BackupError("This backup holds only a world.")
        else:
            chosen = members
        keep_worlds = set(worlds) | set(level_dirs(dst))
        for p in list(dst.iterdir()):
            if _should_skip(Path(p.name)):
                continue
            if mode == "world" and p.name not in worlds:
                continue
            if mode == "config" and p.name in keep_worlds:
                continue
            if p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
            else:
                p.unlink(missing_ok=True)
        for m in chosen:
            z.extract(m, dst)
        return len(chosen)


def restore_backup(sid: str, name: str, mode: str = "all", safety: bool = True) -> int:
    """Server must be stopped. A safety backup is made first unless it is turned off."""
    src = backup_dir(sid) / safe_name(name)
    if not src.exists():
        raise BackupError("Backup not found.")
    dst = server_dir(sid)
    with zipfile.ZipFile(src) as z:               # check before anything is changed
        _safe_members(z, dst)
    if safety:
        create_backup(sid, "before-restore", "standard")
    try:
        return restore_into(dst, src, mode)
    except zipfile.BadZipFile:
        raise BackupError("This backup file is damaged.") from None
