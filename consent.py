"""What the person has agreed to. Kept in DATA/consent.json, separate from settings, so it is easy to show and to reset.

- accepted: the privacy policy (needed to use the app)
- heads:    player head pictures from another website (off until switched on)
- updates:  look for a newer version on GitHub (covered by the policy the person accepts)
- stats:    one anonymous "I am using version X" message a day (covered by the policy the person accepts)
The two switches exist in the backend, with no screen for them: the policy text is what the person agrees to."""
from __future__ import annotations

import time
import uuid

from . import brand
from .store import DATA, _read, _write_atomic

FILE = DATA / "consent.json"
OPTIONS = ("heads", "updates", "stats")
DEFAULTS = {"heads": False, "updates": True, "stats": True}


def get() -> dict:
    raw = _read(FILE, {})
    version = int(raw.get("version") or 0)
    out = {"accepted": version >= brand.POLICY_VERSION, "version": version, "current": brand.POLICY_VERSION,
           "accepted_at": int(raw.get("accepted_at") or 0)}
    for k in OPTIONS:
        out[k] = bool(raw.get(k, DEFAULTS[k]))
    out["usage_id"] = raw.get("install_id") or ""
    return out


def accept(heads: bool = False, updates: bool = True, stats: bool = True) -> dict:
    raw = _read(FILE, {})
    raw.update({"version": brand.POLICY_VERSION, "accepted_at": int(time.time()),
                "first_accepted_at": int(raw.get("first_accepted_at") or time.time())})
    _write_atomic(FILE, raw)
    set_option("heads", heads)
    set_option("updates", updates)
    set_option("stats", stats)
    return get()


def set_option(name: str, on: bool) -> dict:
    if name not in OPTIONS:
        raise ValueError(name)
    raw = _read(FILE, {})
    raw[name] = bool(on)
    if name == "stats":
        if on and not raw.get("install_id"):
            raw["install_id"] = str(uuid.uuid4())          # random, made only when stats are switched on
        if not on:
            raw["_forget_id"] = raw.pop("install_id", None) or raw.get("_forget_id")   # told to the server once, then dropped
            raw.pop("last_ping", None)
    _write_atomic(FILE, raw)
    return get()


def set_heads(on: bool) -> dict:
    return set_option("heads", on)


def heads_allowed() -> bool:
    c = get()
    return c["accepted"] and c["heads"]


def updates_allowed() -> bool:
    c = get()
    return c["accepted"] and c["updates"]


def stats_allowed() -> bool:
    c = get()
    return c["accepted"] and c["stats"]


def install_id() -> str:
    """The random number for this PC. Made the first time it is needed while usage messages are allowed."""
    raw = _read(FILE, {})
    if not raw.get("install_id") and bool(raw.get("stats", DEFAULTS["stats"])) and int(raw.get("version") or 0) >= brand.POLICY_VERSION:
        raw["install_id"] = str(uuid.uuid4())
        _write_atomic(FILE, raw)
    return raw.get("install_id") or ""


def pending_forget() -> str:
    return _read(FILE, {}).get("_forget_id") or ""


def clear_forget() -> None:
    raw = _read(FILE, {})
    raw.pop("_forget_id", None)
    _write_atomic(FILE, raw)


def last_ping() -> int:
    return int(_read(FILE, {}).get("last_ping") or 0)


def mark_ping() -> None:
    raw = _read(FILE, {})
    raw["last_ping"] = int(time.time())
    _write_atomic(FILE, raw)
