"""Checking a downloaded file against the checksum its publisher lists, before the file is used or run.
A mismatch always deletes the file and raises VerifyError. There is no switch to skip a check that has an expected value."""
from __future__ import annotations

import hashlib
import hmac
from pathlib import Path

ALGOS = ("sha256", "sha1")


class VerifyError(Exception):
    pass


def digest_of(path: Path, algo: str) -> str:
    h = hashlib.new(algo)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def split_digest(text: str) -> tuple[str, str] | None:
    """"sha256:ab12.." (the form GitHub uses for release files) -> ("sha256", "ab12..")."""
    if not isinstance(text, str) or ":" not in text:
        return None
    algo, _, hexa = text.partition(":")
    algo, hexa = algo.strip().lower(), hexa.strip().lower()
    if algo in ALGOS and hexa and all(c in "0123456789abcdef" for c in hexa):
        return algo, hexa
    return None


def check(path: Path, expected: tuple[str, str] | None, what: str) -> None:
    """expected = (algo, hex). Deletes the file and raises when it does not match."""
    if not expected:
        raise VerifyError(f"{what}: no checksum to compare with.")
    algo, want = expected
    if algo not in ALGOS or not want:
        path.unlink(missing_ok=True)
        raise VerifyError(f"{what}: unsupported checksum.")
    got = digest_of(path, algo)
    if not hmac.compare_digest(got, want.strip().lower()):
        path.unlink(missing_ok=True)
        raise VerifyError(f"{what} did not match its published checksum, so it was deleted and not used. Try again; if it keeps happening, do not use this download.")


def parse_sums(text: str) -> dict[str, str]:
    """Lines of a SHA256SUMS.txt file ("<hex>  <name>") -> {name: hex}."""
    out = {}
    for line in text.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) == 2 and len(parts[0]) == 64 and all(c in "0123456789abcdefABCDEF" for c in parts[0]):
            out[parts[1].lstrip("*").strip()] = parts[0].lower()
    return out
