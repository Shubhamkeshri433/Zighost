"""World and config backups as zip files."""
from __future__ import annotations

import shutil
import time
import zipfile
from pathlib import Path

from .store import backup_dir, server_dir

# Not worth backing up: can be downloaded again
SKIP_DIRS = {"logs", "cache", "libraries", "versions", ".fabric", "crash-reports"}
SKIP_TOP_SUFFIX = (".jar",)


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


def list_backups(sid: str) -> list[dict]:
    d = backup_dir(sid)
    if not d.exists():
        return []
    out = []
    for p in sorted(d.glob("*.zip"), reverse=True):
        st = p.stat()
        out.append({"name": p.name, "size": st.st_size, "created": int(st.st_mtime)})
    return out


def create_backup(sid: str, label: str = "manual") -> dict:
    src = server_dir(sid)
    if not src.exists():
        raise BackupError("Server folder not found.")
    d = backup_dir(sid)
    d.mkdir(parents=True, exist_ok=True)
    label = "".join(c for c in label if c.isalnum() or c in "-_")[:24] or "manual"
    name = f"{time.strftime('%Y%m%d-%H%M%S')}_{label}.zip"
    tmp = d / (name + ".part")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for p in src.rglob("*"):
            if not p.is_file():
                continue
            rel = p.relative_to(src)
            if _should_skip(rel):
                continue
            try:
                z.write(p, rel.as_posix())
            except OSError:
                continue  # file locked or vanished: skip it, keep the backup
    tmp.replace(d / name)
    st = (d / name).stat()
    return {"name": name, "size": st.st_size, "created": int(st.st_mtime)}


def prune(sid: str, label: str, keep: int) -> int:
    """Keep only the newest `keep` backups made with this label. Returns how many were deleted."""
    d = backup_dir(sid)
    old = sorted(d.glob(f"*_{label}.zip"), reverse=True)[max(1, keep):]
    for p in old:
        p.unlink(missing_ok=True)
    return len(old)


def delete_backup(sid: str, name: str) -> None:
    (backup_dir(sid) / safe_name(name)).unlink(missing_ok=True)


def restore_backup(sid: str, name: str) -> None:
    """Server must be stopped. Makes a safety backup first."""
    src = backup_dir(sid) / safe_name(name)
    if not src.exists():
        raise BackupError("Backup not found.")
    dst = server_dir(sid)
    create_backup(sid, "before-restore")
    with zipfile.ZipFile(src) as z:
        root = dst.resolve()
        for info in z.infolist():
            target = (dst / info.filename).resolve()
            if root not in target.parents and target != root:
                raise BackupError("This backup has an unsafe path inside and was not restored.")
        # remove what the backup covers, keep jars and skipped folders
        for p in list(dst.iterdir()):
            rel = Path(p.name)
            if _should_skip(rel):
                continue
            if p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
            else:
                p.unlink(missing_ok=True)
        z.extractall(dst)
