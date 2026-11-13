"""Server icon: the 64x64 server-icon.png that Minecraft shows next to the server in the multiplayer list.

The pictures are made in the browser (item picker or upload with crop) and sent here as a PNG.
Only the PNG header is checked: PNG, exactly 64 by 64, small.
"""
from __future__ import annotations

import base64
import binascii
import struct

from .store import server_dir

NAME = "server-icon.png"
MAX_BYTES = 100 * 1024
SIGNATURE = b"\x89PNG\r\n\x1a\n"


class IconError(Exception):
    pass


def validate(data: bytes) -> bytes:
    if len(data) > MAX_BYTES:
        raise IconError("The icon file is too big. It should be a small 64 by 64 picture.")
    if len(data) < 33 or data[:8] != SIGNATURE or data[12:16] != b"IHDR":
        raise IconError("The icon must be a PNG picture.")
    width, height = struct.unpack(">II", data[16:24])
    if (width, height) != (64, 64):
        raise IconError("The icon must be exactly 64 by 64 pixels.")
    return data


def decode(text: str) -> bytes:
    """Accepts plain base64 or a data URL."""
    if "," in text[:64]:
        text = text.split(",", 1)[1]
    try:
        return validate(base64.b64decode(text, validate=True))
    except (binascii.Error, ValueError):
        raise IconError("The icon data is not valid.") from None


def path(sid: str):
    return server_dir(sid) / NAME


def version(sid: str) -> int:
    """Changes whenever the icon changes. 0 = no icon."""
    try:
        return int(path(sid).stat().st_mtime)
    except OSError:
        return 0


def read(sid: str) -> bytes | None:
    try:
        return path(sid).read_bytes()
    except OSError:
        return None


def save(sid: str, data: bytes) -> None:
    validate(data)
    p = path(sid)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_bytes(data)
    tmp.replace(p)


def remove(sid: str) -> None:
    path(sid).unlink(missing_ok=True)
