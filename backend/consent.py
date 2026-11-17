"""What the person has agreed to. Kept in DATA/consent.json, separate from settings, so it is easy to show and to reset.

- accepted: the privacy policy (needed to use the app)
- heads:    player head pictures from another website (off until switched on)
- updates:  look for a newer version on GitHub (covered by the policy the person accepts)
The "updates" switch exists in the backend, with no screen for it: the policy text is what the person agrees to.
There is no usage counting: older consent files may still hold a usage number, and it is deleted the first time it is read."""
from __future__ import annotations

import time

from . import brand
from .store import DATA, _read, _write_atomic

FILE = DATA / "consent.json"
OPTIONS = ("heads", "updates")
DEFAULTS = {"heads": False, "updates": True}
LEFTOVER = ("stats", "install_id", "_forget_id", "last_ping")      # kept by versions that counted usage; removed on read


def _read_clean() -> dict:
    raw = _read(FILE, {})
    if any(k in raw for k in LEFTOVER):
        for k in LEFTOVER:
            raw.pop(k, None)
        _write_atomic(FILE, raw)
    return raw


def get() -> dict:
    raw = _read_clean()
    version = int(raw.get("version") or 0)
    out = {"accepted": version >= brand.POLICY_VERSION, "version": version, "current": brand.POLICY_VERSION,
           "accepted_at": int(raw.get("accepted_at") or 0)}
    for k in OPTIONS:
        out[k] = bool(raw.get(k, DEFAULTS[k]))
    return out


def accept(heads: bool = False, updates: bool = True) -> dict:
    raw = _read_clean()
    raw.update({"version": brand.POLICY_VERSION, "accepted_at": int(time.time()),
                "first_accepted_at": int(raw.get("first_accepted_at") or time.time())})
    _write_atomic(FILE, raw)
    set_option("heads", heads)
    set_option("updates", updates)
    return get()


def set_option(name: str, on: bool) -> dict:
    if name not in OPTIONS:
        raise ValueError(name)
    raw = _read_clean()
    raw[name] = bool(on)
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
