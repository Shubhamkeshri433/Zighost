"""Optional Discord webhook messages (server online/stopped/crashed, players joining)."""
from __future__ import annotations

import logging
import re
import threading

import requests

from . import brand
from .store import get_settings

log = logging.getLogger("mcpanel")
WEBHOOK_RE = re.compile(r"^https://(?:discord\.com|discordapp\.com|ptb\.discord\.com|canary\.discord\.com)/api/webhooks/\d+/[\w-]+/?$")


def valid_webhook(url: str) -> bool:
    return bool(WEBHOOK_RE.match(url or ""))


def send(text: str, timeout: int = 8) -> str | None:
    """Returns an error message for the user, or None when sent."""
    url = get_settings().get("discord_webhook", "")
    if not valid_webhook(url):
        return "No valid Discord webhook is saved."
    try:
        r = requests.post(url, json={"content": text[:1900], "username": brand.NAME}, timeout=timeout)
    except requests.RequestException:
        return "Could not reach Discord. Check your internet connection."
    if r.status_code not in (200, 204):
        return f"Discord refused the message (error {r.status_code}). Check the webhook link."
    return None


def event(kind: str, text: str) -> None:
    """Called by the process manager. Never raises; runs in the background."""
    s = get_settings()
    if not valid_webhook(s.get("discord_webhook", "")):
        return
    if kind == "player" and not s.get("notify_players"):
        return
    if kind != "player" and not s.get("notify_server"):
        return

    def run():
        err = send(text)
        if err:
            log.warning("Discord notice failed: %s", err)
    threading.Thread(target=run, daemon=True).start()
