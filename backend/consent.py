"""What the person has agreed to. Kept in DATA/consent.json, separate from settings, so it is easy to show and to reset.

Only two things exist: accepting the privacy policy (needed to use the app) and the optional switch for player head
pictures (off until the person turns it on, because it contacts another website)."""
from __future__ import annotations

import time

from . import brand
from .store import DATA, _read, _write_atomic

FILE = DATA / "consent.json"


def get() -> dict:
    raw = _read(FILE, {})
    version = int(raw.get("version") or 0)
    return {"accepted": version >= brand.POLICY_VERSION, "version": version, "current": brand.POLICY_VERSION,
            "accepted_at": int(raw.get("accepted_at") or 0), "heads": bool(raw.get("heads", False))}


def accept(heads: bool = False) -> dict:
    raw = _read(FILE, {})
    _write_atomic(FILE, {"version": brand.POLICY_VERSION, "accepted_at": int(time.time()), "heads": bool(heads),
                         "first_accepted_at": int(raw.get("first_accepted_at") or time.time())})
    return get()


def set_heads(on: bool) -> dict:
    raw = _read(FILE, {})
    raw["heads"] = bool(on)
    _write_atomic(FILE, raw)
    return get()


def heads_allowed() -> bool:
    c = get()
    return c["accepted"] and c["heads"]
