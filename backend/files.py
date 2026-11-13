"""Safe file browser for one server folder: list, read, edit, upload, rename, delete."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

MAX_TEXT = 1_000_000            # editable text files up to 1 MB
MAX_UPLOAD = 512 * 1024 * 1024
BLOCKED_UPLOAD = {".exe", ".bat", ".cmd", ".ps1", ".sh", ".com", ".scr", ".msi", ".vbs", ".lnk"}
PROTECTED = {"server.jar", "eula.txt"}   # cannot be deleted or renamed from the panel


class FileError(Exception):
    """Message is written for the user."""


def resolve(root: Path, rel: str) -> Path:
    """Path inside root, or FileError. Symlinks that point outside are refused."""
    rel = (rel or "").replace("\\", "/").strip("/")
    if "\x00" in rel:
        raise FileError("Invalid path.")
    base = root.resolve()
    target = (base / rel).resolve() if rel else base
    if target != base and base not in target.parents:
        raise FileError("That path is outside the server folder.")
    return target


def rel_of(root: Path, p: Path) -> str:
    r = p.resolve().relative_to(root.resolve()).as_posix()
    return "" if r == "." else r


def listing(root: Path, rel: str) -> dict:
    d = resolve(root, rel)
    if not d.is_dir():
        raise FileError("That folder does not exist.")
    entries = []
    for p in d.iterdir():
        try:
            st = p.stat()
        except OSError:
            continue
        entries.append({"name": p.name, "dir": p.is_dir(), "size": 0 if p.is_dir() else st.st_size,
                        "modified": int(st.st_mtime)})
    entries.sort(key=lambda e: (not e["dir"], e["name"].lower()))
    return {"path": rel_of(root, d), "entries": entries}


def read_text(root: Path, rel: str) -> dict:
    p = resolve(root, rel)
    if not p.is_file():
        raise FileError("That file does not exist.")
    size = p.stat().st_size
    if size > MAX_TEXT:
        raise FileError(f"This file is {size // 1024} KB. The editor opens text files up to {MAX_TEXT // 1024} KB. Download it instead.")
    raw = p.read_bytes()
    if b"\x00" in raw[:4096]:
        raise FileError("This looks like a binary file, not text. You can download it.")
    return {"path": rel_of(root, p), "content": raw.decode("utf-8", errors="replace"), "size": size}


def write_text(root: Path, rel: str, content: str) -> None:
    p = resolve(root, rel)
    if p.is_dir():
        raise FileError("That is a folder.")
    if len(content.encode("utf-8")) > MAX_TEXT:
        raise FileError("The text is too long for the editor (over 1 MB).")
    if not p.parent.exists():
        raise FileError("The folder does not exist.")
    tmp = p.with_name(p.name + ".panel-tmp")
    tmp.write_text(content, encoding="utf-8", newline="")
    os.replace(tmp, p)


def mkdir(root: Path, rel: str) -> None:
    p = resolve(root, rel)
    if p.exists():
        raise FileError("Something with that name already exists.")
    p.mkdir(parents=True)


def _guard_root(root: Path, p: Path) -> None:
    if p == root.resolve():
        raise FileError("The server folder itself cannot be changed here.")
    if p.parent == root.resolve() and p.name in PROTECTED:
        raise FileError(f"{p.name} is needed by the server and cannot be changed here.")


def delete(root: Path, rel: str) -> None:
    p = resolve(root, rel)
    _guard_root(root, p)
    if not p.exists():
        raise FileError("That file does not exist.")
    shutil.rmtree(p) if p.is_dir() else p.unlink()


def rename(root: Path, src: str, dst: str) -> None:
    a, b = resolve(root, src), resolve(root, dst)
    _guard_root(root, a)
    if not a.exists():
        raise FileError("That file does not exist.")
    if b.exists():
        raise FileError("Something with that name already exists.")
    if not b.parent.exists():
        raise FileError("The target folder does not exist.")
    a.rename(b)


def upload_target(root: Path, rel_dir: str, name: str) -> Path:
    name = (name or "").strip()
    if not name or "/" in name or "\\" in name or name in (".", "..") or ":" in name or "\x00" in name:
        raise FileError("Invalid file name.")
    if Path(name).suffix.lower() in BLOCKED_UPLOAD:
        raise FileError(f"Files ending in {Path(name).suffix} cannot be uploaded to a server folder.")
    d = resolve(root, rel_dir)
    if not d.is_dir():
        raise FileError("The target folder does not exist.")
    return resolve(root, (rel_of(root, d) + "/" + name).strip("/"))


def download_path(root: Path, rel: str) -> Path:
    p = resolve(root, rel)
    if not p.is_file():
        raise FileError("That file does not exist.")
    return p
