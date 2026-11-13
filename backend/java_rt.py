"""Find a suitable Java, or download one (Eclipse Temurin) into data/runtime."""
from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path
from typing import Callable

import requests

from . import brand
from .store import RUNTIME_DIR, get_settings

IS_WIN = sys.platform.startswith("win")
EXE = "java.exe" if IS_WIN else "java"
NOWINDOW = 0x08000000 if IS_WIN else 0  # CREATE_NO_WINDOW


class JavaError(Exception):
    pass


def java_major(java: str) -> int | None:
    try:
        r = subprocess.run([java, "-version"], capture_output=True, text=True, timeout=15, creationflags=NOWINDOW)
    except (OSError, subprocess.SubprocessError):
        return None
    m = re.search(r'version "(\d+)(?:\.(\d+))?', r.stderr + r.stdout)
    if not m:
        return None
    major = int(m.group(1))
    return int(m.group(2) or 0) if major == 1 else major  # "1.8.0" -> 8


def _has_javac(java: str) -> bool:
    return (Path(java).parent / ("javac.exe" if IS_WIN else "javac")).exists()


def _candidates() -> list[str]:
    out: list[str] = []
    s = get_settings().get("java_path", "").strip()
    if s:
        out.append(s)
    if RUNTIME_DIR.exists():
        for p in sorted(RUNTIME_DIR.glob(f"java-*/**/bin/{EXE}")):
            out.append(str(p))
    home = os.environ.get("JAVA_HOME")
    if home:
        out.append(str(Path(home) / "bin" / EXE))
    w = shutil.which("java")
    if w:
        out.append(w)
    seen, uniq = set(), []
    for c in out:
        if c not in seen and Path(c).exists():
            seen.add(c)
            uniq.append(c)
    return uniq


def find_java(required: int = 8, need_jdk: bool = False) -> tuple[str, int] | None:
    """Best Java with major >= required. Prefers the closest version."""
    found: list[tuple[int, str]] = []
    for c in _candidates():
        major = java_major(c)
        if major and major >= required and (not need_jdk or _has_javac(c)):
            found.append((major, c))
    if not found:
        return None
    found.sort()
    return found[0][1], found[0][0]


def install_java(major: int, jdk: bool, progress: Callable[[str, int], None]) -> str:
    """Download Temurin `major` into data/runtime. Returns path to java."""
    os_name = "windows" if IS_WIN else ("mac" if sys.platform == "darwin" else "linux")
    machine = platform.machine().lower()
    arch = "aarch64" if machine in ("arm64", "aarch64") else "x64"
    image = "jdk" if jdk else "jre"
    url = f"https://api.adoptium.net/v3/binary/latest/{major}/ga/{os_name}/{arch}/{image}/hotspot/normal/eclipse"
    dest = RUNTIME_DIR / f"java-{major}-{image}"
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    archive = RUNTIME_DIR / f"java-{major}-{image}.download"
    progress(f"Downloading Java {major}", 0)
    try:
        with requests.get(url, stream=True, timeout=30, allow_redirects=True,
                          headers={"User-Agent": brand.USER_AGENT}) as r:
            if r.status_code != 200:
                raise JavaError(f"Java download failed (error {r.status_code}). Install Java {major} yourself and set its path in Settings.")
            total = int(r.headers.get("content-length") or 0)
            got = 0
            with open(archive, "wb") as f:
                for chunk in r.iter_content(1 << 16):
                    f.write(chunk)
                    got += len(chunk)
                    if total:
                        progress(f"Downloading Java {major}", int(got * 100 / total))
    except requests.RequestException as e:
        raise JavaError("Could not download Java. Check your internet connection.") from e
    progress(f"Unpacking Java {major}", 100)
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    try:
        if zipfile.is_zipfile(archive):
            with zipfile.ZipFile(archive) as z:
                _safe_extract_zip(z, dest)
        else:
            with tarfile.open(archive) as t:
                t.extractall(dest, filter="data")
    finally:
        archive.unlink(missing_ok=True)
    for p in dest.glob(f"**/bin/{EXE}"):
        if not IS_WIN:
            p.chmod(0o755)
        return str(p)
    raise JavaError("Java was downloaded but java was not found inside it.")


def _safe_extract_zip(z: zipfile.ZipFile, dest: Path) -> None:
    root = dest.resolve()
    for info in z.infolist():
        target = (dest / info.filename).resolve()
        if root not in target.parents and target != root:
            raise JavaError("Unsafe path in downloaded archive.")
    z.extractall(dest)
