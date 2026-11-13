"""File manager for one server folder. Every path is checked so nothing outside the folder can be touched."""
from __future__ import annotations

import os
import re
import shutil
import time
from pathlib import Path

MAX_EDIT = 2 * 1024 * 1024
MAX_UPLOAD = 512 * 1024 * 1024
EDITABLE = {".properties", ".yml", ".yaml", ".json", ".json5", ".txt", ".toml", ".cfg", ".conf", ".ini", ".log",
            ".md", ".mcmeta", ".xml", ".csv", ".lang", ".sk", ".js", ".mcfunction", ".secret", ""}
PROTECTED_TOP = {"server.jar"}
BAD_NAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
WIN_RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}


class FsError(Exception):
    pass


def resolve(root: Path, rel: str) -> Path:
    rel = (rel or "").replace("\\", "/")
    if "\x00" in rel:
        raise FsError("That path is not allowed.")
    parts = [p for p in rel.split("/") if p not in ("", ".")]
    for p in parts:
        if p == ".." or ":" in p or len(p) > 150:
            raise FsError("That path is not allowed.")
    rr = root.resolve()
    tr = rr.joinpath(*parts).resolve()
    if tr != rr and rr not in tr.parents:
        raise FsError("That path is not allowed.")
    return tr


def clean_name(name: str) -> str:
    name = (name or "").strip()
    if not name or name in (".", "..") or BAD_NAME.search(name) or len(name) > 120 or name.endswith((".", " ")):
        raise FsError("That name is not allowed. Avoid the characters < > : \" / \\ | ? *")
    if name.split(".")[0].lower() in WIN_RESERVED:
        raise FsError("That name is reserved by Windows.")
    return name


def rel_of(root: Path, p: Path) -> str:
    return p.resolve().relative_to(root.resolve()).as_posix() if p.resolve() != root.resolve() else ""


def is_editable(p: Path, size: int) -> bool:
    return size <= MAX_EDIT and p.suffix.lower() in EDITABLE


def listdir(root: Path, rel: str) -> dict:
    d = resolve(root, rel)
    if not d.is_dir():
        raise FsError("That folder does not exist.")
    entries = []
    try:
        items = list(os.scandir(d))
    except OSError:
        raise FsError("Could not open that folder.") from None
    for e in items[:2000]:
        try:
            st = e.stat()
        except OSError:
            continue
        isdir = e.is_dir()
        entries.append({"name": e.name, "dir": isdir, "size": 0 if isdir else st.st_size,
                        "modified": int(st.st_mtime), "editable": (not isdir) and is_editable(Path(e.name), st.st_size)})
    entries.sort(key=lambda x: (not x["dir"], x["name"].lower()))
    return {"path": rel_of(root, d), "entries": entries, "truncated": len(items) > 2000}


def read_text(root: Path, rel: str) -> dict:
    p = resolve(root, rel)
    if not p.is_file():
        raise FsError("That file does not exist.")
    size = p.stat().st_size
    if size > MAX_EDIT:
        raise FsError("This file is too large to edit here. Download it instead.")
    data = p.read_bytes()
    if b"\x00" in data[:8192]:
        raise FsError("This is not a text file, so it cannot be edited here.")
    try:
        return {"path": rel_of(root, p), "content": data.decode("utf-8"), "size": size}
    except UnicodeDecodeError:
        raise FsError("This file is not UTF-8 text, so editing it here could damage it.") from None


def write_text(root: Path, rel: str, content: str) -> None:
    p = resolve(root, rel)
    if p.is_dir():
        raise FsError("That is a folder.")
    if not p.parent.is_dir():
        raise FsError("The folder does not exist.")
    data = content.encode("utf-8")
    if len(data) > MAX_EDIT:
        raise FsError("The file is too large to save here.")
    if p.parent == root.resolve() and p.name in PROTECTED_TOP:
        raise FsError("server.jar cannot be edited.")
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, p)


def mkdir(root: Path, rel_dir: str, name: str) -> None:
    d = resolve(root, rel_dir)
    if not d.is_dir():
        raise FsError("The folder does not exist.")
    new = d / clean_name(name)
    if new.exists():
        raise FsError("Something with that name already exists.")
    new.mkdir()


def delete(root: Path, rel: str, running: bool) -> None:
    p = resolve(root, rel)
    if p == root.resolve():
        raise FsError("The server folder itself cannot be deleted here.")
    if not p.exists():
        raise FsError("That does not exist.")
    if p.parent == root.resolve() and p.name in PROTECTED_TOP:
        raise FsError("server.jar is needed to run the server. Delete the whole server on the Servers page instead.")
    if p.is_dir():
        if running:
            raise FsError("Stop the server before deleting folders.")
        shutil.rmtree(p)
    else:
        p.unlink()


def rename(root: Path, rel: str, new_name: str, running: bool) -> None:
    p = resolve(root, rel)
    if p == root.resolve() or not p.exists():
        raise FsError("That does not exist.")
    if p.parent == root.resolve() and p.name in PROTECTED_TOP:
        raise FsError("server.jar cannot be renamed.")
    if p.is_dir() and running:
        raise FsError("Stop the server before renaming folders.")
    dest = p.with_name(clean_name(new_name))
    if dest.exists():
        raise FsError("Something with that name already exists.")
    p.rename(dest)


def upload_target(root: Path, rel_dir: str, name: str) -> Path:
    d = resolve(root, rel_dir)
    if not d.is_dir():
        raise FsError("The folder does not exist.")
    dest = d / clean_name(name)
    if dest.is_dir():
        raise FsError("A folder with that name already exists.")
    if dest.parent == root.resolve() and dest.name in PROTECTED_TOP:
        raise FsError("server.jar cannot be replaced here.")
    return dest


def dir_size(p: Path) -> int:
    total = 0
    for dp, _, files in os.walk(p):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(dp, f))
            except OSError:
                pass
    return total


def fmt_time(ts: float) -> str:
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))
