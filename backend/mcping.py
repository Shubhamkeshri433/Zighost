"""Minecraft Java "server list ping": asks a server who it is, like the in-game multiplayer screen.

Used to check that friends can really reach an address (for example a playit.gg tunnel).
Protocol: handshake packet, status request, read the JSON answer. No extra packages.
"""
from __future__ import annotations

import json
import re
import socket
import struct
import time

SECTION_RE = re.compile("§[0-9a-fk-or]", re.I)
HOST_RE = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9.-]{0,251}[A-Za-z0-9])?$")


class PingError(Exception):
    """Message is written for the user."""


def parse_address(text: str, default_port: int = 25565) -> tuple[str, int]:
    t = (text or "").strip()
    for prefix in ("minecraft://", "http://", "https://"):
        if t.lower().startswith(prefix):
            t = t[len(prefix):]
    t = t.rstrip("/")
    if not t:
        raise PingError("Enter an address first, like name.at.ply.gg:12345.")
    host, port = t, default_port
    if t.count(":") == 1:
        host, p = t.split(":")
        if not p.isdigit() or not (1 <= int(p) <= 65535):
            raise PingError("The port after the colon must be a number from 1 to 65535.")
        port = int(p)
    if not HOST_RE.match(host):
        raise PingError("That does not look like a server address. Use letters, numbers, dots and dashes only.")
    return host, port


def _varint(n: int) -> bytes:
    n &= 0xFFFFFFFF
    out = b""
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out += bytes([b | 0x80])
        else:
            return out + bytes([b])


def _recv_exact(s: socket.socket, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = s.recv(n - len(buf))
        if not chunk:
            raise PingError("The connection closed before the server answered.")
        buf += chunk
    return buf


def _read_varint(s: socket.socket) -> int:
    num = 0
    for i in range(5):
        b = _recv_exact(s, 1)[0]
        num |= (b & 0x7F) << (7 * i)
        if not b & 0x80:
            return num
    raise PingError("The answer was not a Minecraft status reply.")


def _varint_from(buf: bytes, pos: int) -> tuple[int, int]:
    num = 0
    for i in range(5):
        if pos >= len(buf):
            raise PingError("The answer was cut short.")
        b = buf[pos]
        pos += 1
        num |= (b & 0x7F) << (7 * i)
        if not b & 0x80:
            return num, pos
    raise PingError("The answer was not a Minecraft status reply.")


def _flat(d) -> str:
    if isinstance(d, str):
        return d
    if isinstance(d, dict):
        return str(d.get("text", "")) + "".join(_flat(e) for e in d.get("extra", []))
    if isinstance(d, list):
        return "".join(_flat(e) for e in d)
    return ""


def ping(host: str, port: int = 25565, timeout: float = 6.0) -> dict:
    try:
        s = socket.create_connection((host, port), timeout=timeout)
    except socket.gaierror:
        raise PingError("That address does not exist. Check the spelling.") from None
    except socket.timeout:
        raise PingError("No answer in time. The server may be off, or the tunnel is not running.") from None
    except ConnectionRefusedError:
        raise PingError("Connection refused. Nothing is listening on that address and port.") from None
    except OSError as e:
        raise PingError(f"Could not connect ({e.strerror or e.__class__.__name__}).") from None
    try:
        s.settimeout(timeout)
        hb = host.encode("utf-8")
        hs = b"\x00" + _varint(765) + _varint(len(hb)) + hb + struct.pack(">H", port) + _varint(1)
        s.sendall(_varint(len(hs)) + hs)
        t0 = time.time()
        s.sendall(b"\x01\x00")
        length = _read_varint(s)
        if not 1 <= length <= 1_000_000:
            raise PingError("It answered, but not like a Minecraft server.")
        latency = int((time.time() - t0) * 1000)
        buf = _recv_exact(s, length)
        pid, pos = _varint_from(buf, 0)
        if pid != 0:
            raise PingError("It answered, but not like a Minecraft server.")
        n, pos = _varint_from(buf, pos)
        try:
            data = json.loads(buf[pos:pos + n].decode("utf-8", "replace"))
        except ValueError:
            raise PingError("It answered, but not like a Minecraft server.") from None
    except socket.timeout:
        raise PingError("Connected, but the server did not answer in time. It may still be starting.") from None
    except OSError as e:
        raise PingError(f"The connection broke ({e.strerror or e.__class__.__name__}).") from None
    finally:
        s.close()
    players = data.get("players") or {}
    ver = data.get("version") or {}
    return {"ok": True, "latency_ms": latency, "version": str(ver.get("name", "")),
            "players_online": int(players.get("online", 0) or 0), "players_max": int(players.get("max", 0) or 0),
            "motd": SECTION_RE.sub("", _flat(data.get("description", ""))).strip()[:200]}
