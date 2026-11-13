"""playit.gg helper.

Why the panel does NOT run the playit that is installed on the PC (v2): that program opens its own window
and talks to a Windows service. If the service is not installed it just shows "service isn't running".
Instead the panel downloads its own small command-line agent (the 0.15-0.17 series, no service, no window)
into data/runtime/playit and runs that.

Checked online: Windows release files are named playit-windows-x86_64-signed.exe, Linux playit-linux-amd64.
NOT checked on a real PC: what that agent prints. So the module
  - asks the agent for --help and only uses flags it lists (--stdout, --secret),
  - parses output with loose patterns,
  - also asks the playit web API for the tunnel address (best effort, result is written to the helper log),
  - has an "external" mode (use your own playit app, paste the address), and a manual address box.
"""
from __future__ import annotations

import collections
import os
import platform
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

import requests

from . import brand
from .store import RUNTIME_DIR, get_settings, update_settings

IS_WIN = sys.platform.startswith("win")
NOWINDOW = 0x08000000 if IS_WIN else 0
RELEASES_API = "https://api.github.com/repos/playit-cloud/playit-agent/releases?per_page=50"
API_BASE = "https://api.playit.gg"
CLAIM_PAGE = "https://playit.gg/claim/"
HEX_RE = re.compile(r"[0-9a-fA-F]{32,}")
BAD_ACCOUNT = {"banned": "This playit account is banned.", "agent-disabled": "This playit agent was disabled on playit.gg. Open playit.gg, enable it, or press Unlink and link again.", "account-delete-scheduled": "This playit account is being deleted.", "agent-over-limit": "This playit account has too many agents. Delete an old agent on playit.gg, or press Unlink and use another account."}
NOISE = ("local timestamp if over", "tunnel running,", "udp channel requires auth", "udp session details", "send KeepAlive")
ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b\][^\x07]*\x07")
CLAIM_RE = re.compile(r"https?://[^\s\"'<>]*playit\.gg/claim/[^\s\"'<>]+", re.I)
ADDR_RE = re.compile(r"\b((?:[a-z0-9-]+\.)+(?:ply\.gg|playit\.gg|joinmc\.link|playit\.plus)(?::\d{2,5})?)\b", re.I)
SECRET_RE = re.compile(r"""secret_key\s*=\s*["']?([0-9a-fA-F]{16,})["']?""")
LEGACY_TAG_RE = re.compile(r"^v?0\.(\d+)\.(\d+)$")
PLAYIT_DIR = RUNTIME_DIR / "playit"
BIN_NAME = "playit.exe" if IS_WIN else "playit"
ACTIVE = ("downloading", "starting", "needs_claim", "online")


class PlayitError(Exception):
    pass


def api(path: str, body: dict | None = None, secret: str = "", timeout: float = 12.0) -> tuple[int, bool, object, str]:
    """POST to the playit.gg API. Returns (http status, ok, data, raw text). Raises requests.RequestException."""
    schemes = ("Agent-Key", "agent-key") if secret else ("",)
    r = None
    for scheme in schemes:
        headers = {"User-Agent": brand.USER_AGENT}
        if scheme:
            headers["Authorization"] = f"{scheme} {secret}"
        r = requests.post(API_BASE + path, json=body if body is not None else {}, headers=headers, timeout=timeout)
        if r.status_code not in (401, 403):
            break
    assert r is not None
    try:
        j = r.json()
    except ValueError:
        j = None
    if isinstance(j, dict) and "status" in j:
        return r.status_code, bool(r.ok and j.get("status") == "success"), j.get("data"), r.text
    return r.status_code, bool(r.ok and j is not None), j, r.text


def redact(text: str, secret: str = "") -> str:
    if secret:
        text = text.replace(secret, "***")
    return HEX_RE.sub("***", text)


def _pick_asset(assets: list[dict]) -> dict | None:
    machine = platform.machine().lower()
    arm = machine in ("arm64", "aarch64")
    if IS_WIN:
        os_words = ("windows",)
    elif sys.platform == "darwin":
        os_words = ("darwin", "macos", "mac")
    else:
        os_words = ("linux",)
    arch_words = ("aarch64", "arm64") if arm else ("amd64", "x86_64", "x64")
    bad = (".msi", ".deb", ".rpm", ".sha", ".sig", ".txt", ".zip", ".tar", ".gz")
    scored = []
    for a in assets:
        n = a.get("name", "").lower()
        if n.endswith(bad) or not any(w in n for w in os_words):
            continue
        score = 0
        if any(w in n for w in arch_words):
            score += 2
        elif any(w in n for w in ("aarch64", "arm64", "amd64", "x86_64", "x64", "arm", "x86", "i686")):
            continue  # a different CPU type
        if "signed" in n:
            score += 1
        scored.append((score, a))
    scored.sort(key=lambda t: -t[0])
    return scored[0][1] if scored else None


def pick_release(releases: list[dict]) -> tuple[dict, dict] | None:
    """Newest 0.x release (command-line agent) that has a file for this computer."""
    legacy = []
    for r in releases:
        m = LEGACY_TAG_RE.match(r.get("tag_name", ""))
        if m and not r.get("draft") and not r.get("prerelease") and int(m.group(1)) >= 15:
            legacy.append(((int(m.group(1)), int(m.group(2))), r))
    for _, r in sorted(legacy, key=lambda t: t[0], reverse=True):
        a = _pick_asset(r.get("assets", []))
        if a:
            return r, a
    return None


def find_secret() -> str:
    s = get_settings().get("playit_secret", "").strip()
    if s:
        return s
    # Only the panel's own folder. The key of an installed playit app must not be shared with a second agent.
    for p in (PLAYIT_DIR / "playit.toml",):
        try:
            m = SECRET_RE.search(p.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        if m:
            return m.group(1)
    return ""


TUNNEL_PREFIXES = brand.TUNNEL_PREFIXES


def tunnel_name(tag: str | None, port: int | None) -> str:
    """Each server gets a tunnel of its own, named after its id, so two servers never share one address."""
    return f"{TUNNEL_PREFIXES[0]}{tag}" if tag else f"{TUNNEL_PREFIXES[0]}{port}"


def tunnel_names(tag: str | None, port: int | None) -> tuple:
    """Every name this server's tunnel may carry (an older app name still counts)."""
    return tuple(f"{p}{tag}" if tag else f"{p}{port}" for p in TUNNEL_PREFIXES)


def parse_rundata(data: dict, local_port: int | None = None, tag: str | None = None) -> str:
    """Pull a public address out of the playit API answer. Tolerant: the exact shape is not verified.
    With a tag (server id) only that server's tunnel counts; tunnels named for other servers are skipped."""
    payload = data.get("data", data) if isinstance(data, dict) else {}
    tunnels = payload.get("tunnels") or [] if isinstance(payload, dict) else []
    best = ""
    for t in tunnels:
        if not isinstance(t, dict) or t.get("disabled"):
            continue
        dom = t.get("assigned_domain") or t.get("custom_domain") or ""
        if not dom:
            continue
        port = (t.get("port") or {}).get("from") if isinstance(t.get("port"), dict) else None
        addr = dom if not port or int(port) == 25565 else f"{dom}:{int(port)}"
        is_mc = "minecraft" in str(t.get("tunnel_type", "")).lower()
        name = str(t.get("name") or "")
        if tag:
            if name in tunnel_names(tag, None):
                return addr
            if name.startswith(TUNNEL_PREFIXES):
                continue          # made by the panel for another server (or an older panel version)
        if local_port and t.get("local_port") == local_port:
            return addr
        if is_mc and not best:
            best = addr
        elif not best:
            best = addr
    return best


class Playit:
    def __init__(self):
        self.lock = threading.RLock()
        self.state = "stopped"   # stopped|downloading|starting|needs_claim|online|error|external
        self.claim_url = ""
        self.address = ""
        self.error = ""
        self.version = ""
        self.cmdline = ""
        self.since = 0.0
        self.log: collections.deque[str] = collections.deque(maxlen=80)
        self.notes: collections.deque[str] = collections.deque(maxlen=40)   # the panel's own messages; helper chatter never pushes these out
        self.proc: subprocess.Popen | None = None
        self.local_port: int | None = None
        self.tag: str | None = None
        self._stop = False
        self._gen = 0
        self._api_note = ""
        self.account = ""        # guest | ready | email-not-verified ...
        self.tunnel_note = ""

    def note(self, text: str) -> None:
        self.log.append(f"[panel] {text}")
        self.notes.append(text)

    # ---- find / download ----------------------------------------------------
    def binary(self) -> str | None:
        s = get_settings().get("playit_path", "").strip()
        if s:
            if Path(s).exists():
                return s
            raise PlayitError("The playit path in Settings does not exist. Fix it or clear it.")
        mine = PLAYIT_DIR / BIN_NAME
        return str(mine) if mine.exists() else None

    def binary_exists(self) -> bool:
        try:
            return bool(self.binary())
        except PlayitError:
            return False

    def fetch_binary(self) -> str:
        """Download the helper now (used by the first-run "get ready" step) without starting anything."""
        before = self.state
        try:
            return self.binary() or self._download()
        finally:
            self.state = before

    def _download(self) -> str:
        self.state = "downloading"
        part = None
        try:
            r = requests.get(RELEASES_API, timeout=20, headers={"User-Agent": brand.USER_AGENT, "Accept": "application/vnd.github+json"})
            if r.status_code != 200:
                raise PlayitError(f"The panel could not look up the playit helper (error {r.status_code}). "
                                  "Check your internet connection, or choose 'Use my own playit app' on this page.")
            found = pick_release(r.json())
            if not found:
                raise PlayitError("No playit helper download matches this computer. Choose 'Use my own playit app' "
                                  "on this page, or set a playit path in Settings.")
            rel, asset = found
            self.version = rel["tag_name"]
            self.note(f"Downloading playit {rel['tag_name']} ({asset['name']})")
            PLAYIT_DIR.mkdir(parents=True, exist_ok=True)
            dest = PLAYIT_DIR / BIN_NAME
            part = dest.with_suffix(dest.suffix + ".part")
            with requests.get(asset["browser_download_url"], stream=True, timeout=30,
                              headers={"User-Agent": brand.USER_AGENT}) as d:
                if d.status_code != 200:
                    raise PlayitError(f"playit helper download failed (error {d.status_code}).")
                with open(part, "wb") as f:
                    for chunk in d.iter_content(1 << 16):
                        f.write(chunk)
        except requests.RequestException as e:
            raise PlayitError("Could not download the playit helper. Check your internet connection.") from e
        if part.stat().st_size < 100_000:
            part.unlink(missing_ok=True)
            raise PlayitError("The playit helper download was incomplete. Try again.")
        part.replace(dest)
        if not IS_WIN:
            dest.chmod(0o755)
        return str(dest)

    def _help_flags(self, exe: str) -> set[str]:
        """Ask the agent which flags it knows. Never start it without arguments blindly."""
        try:
            out = subprocess.run([exe, "--help"], capture_output=True, text=True, timeout=10, encoding="utf-8",
                                 errors="replace", creationflags=NOWINDOW, stdin=subprocess.DEVNULL)
            text = ANSI_RE.sub("", (out.stdout or "") + (out.stderr or ""))
        except (OSError, subprocess.SubprocessError) as e:
            self.note(f"Could not read --help from the helper ({e.__class__.__name__}). Starting without extra flags.")
            return set()
        flags = set(re.findall(r"--[a-z][a-z0-9_-]*", text))
        self.note("Helper flags: " + (", ".join(sorted(flags)) or "none found"))
        return flags

    # ---- run ----------------------------------------------------------------
    def start(self, local_port: int | None = None, tag: str | None = None) -> None:
        if get_settings().get("playit_mode") == "external":
            self.state = "external"
            return
        if self.state in ACTIVE and tag and self.tag and tag != self.tag:
            self.stop()                      # another server is starting: its own tunnel, its own address
            self.address = ""
        with self.lock:
            if self.state in ACTIVE:
                return
            self.state = "starting"
            self.claim_url = ""
            self.address = ""
            self.error = ""
            self.since = time.time()
            self.local_port = local_port
            self.tag = tag
            self._stop = False
            self._gen += 1
            gen = self._gen
            self.log.clear()
        threading.Thread(target=self._run, args=(gen,), daemon=True).start()

    def _run(self, gen: int) -> None:
        try:
            exe = self.binary() or self._download()
            secret = find_secret()
            if not secret:
                secret = self._claim(gen)
                if not secret:
                    return
            self.state = "starting"
            self._tunnel_setup(secret)
            if self._stop or gen != self._gen:
                return
            flags = self._help_flags(exe)
            args = [exe]
            env = dict(os.environ)
            env["SECRET_KEY"] = secret
            PLAYIT_DIR.mkdir(parents=True, exist_ok=True)
            toml = PLAYIT_DIR / "playit.toml"
            toml.write_text(f'secret_key = "{secret}"\n', encoding="utf-8")
            if "--stdout" in flags:
                args.append("--stdout")
            if "--secret" in flags:
                args += ["--secret", secret]
            elif "--secret_path" in flags:
                args += ["--secret_path", str(toml)]
            self.cmdline = " ".join(Path(args[0]).name if i == 0 else ("--secret ***" if a == secret else a)
                                    for i, a in enumerate(args) if a != "--secret").strip()
            self.note("Running: " + self.cmdline)
            PLAYIT_DIR.mkdir(parents=True, exist_ok=True)
            self.proc = subprocess.Popen(args, cwd=PLAYIT_DIR, env=env, stdin=subprocess.DEVNULL,
                                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                         encoding="utf-8", errors="replace", creationflags=NOWINDOW)
            threading.Thread(target=self._api_poll, args=(gen,), daemon=True).start()
            assert self.proc.stdout
            for raw in self.proc.stdout:
                self._parse(raw)
            code = self.proc.wait()
            if not self._stop and gen == self._gen:
                tail = " | ".join(list(self.log)[-2:])
                self.error = f"The playit helper closed (exit code {code}). {tail[:200]}"
                self.state = "error"
        except Exception as e:  # noqa: BLE001  (show any failure in the Network page)
            self.error = str(e) if isinstance(e, PlayitError) else f"{e.__class__.__name__}: {e}"
            self.state = "error"
        finally:
            self.proc = None
            if self._stop and gen == self._gen:
                self.state = "stopped"

    def _api_poll(self, gen: int) -> None:
        """Ask playit.gg for the tunnel address until it shows up."""
        deadline = time.time() + 20 * 60
        wait = 3
        tries = 0
        while time.time() < deadline and gen == self._gen and not self._stop and self.proc:
            time.sleep(wait)
            wait = 6
            if self.address:
                return
            secret = find_secret()
            if not secret:
                continue
            data = self._rundata(secret)
            if data is None:
                continue
            addr = parse_rundata(data, self.local_port, self.tag)
            if addr:
                self.address, self.claim_url, self.state = addr, "", "online"
                self.tunnel_note = ""
                self.note(f"Found address through the playit.gg API: {addr}")
                return
            self._api_log("playit.gg knows this agent but no tunnel with an address exists yet.")
            tries += 1
            if self.tunnel_note and tries % 8 == 0:      # about once a minute: the person may have verified the email or freed a slot
                try:
                    self._tunnel_setup(secret)
                except PlayitError as e:
                    self.error = str(e)

    def _rundata(self, secret: str) -> dict | None:
        try:
            st, ok, data, text = api("/agents/rundata", {}, secret)
        except requests.RequestException as e:
            self._api_log(f"playit.gg API not reachable ({e.__class__.__name__})")
            return None
        if not ok or not isinstance(data, dict):
            self._api_log(f"playit.gg API answered {st}: {redact(text, secret)[:160]}")
            return None
        acct = str(data.get("account_status") or "")
        if acct and acct != self.account:
            self.account = acct
            self.note(f"Account type: {acct}")
        return data

    # ---- link this PC to a playit account (guest or signed in) ---------------
    def _claim(self, gen: int) -> str:
        """The panel asks playit for a claim link, opens it, and waits until the person accepts it."""
        code = secrets.token_hex(8)
        url = f"{CLAIM_PAGE}{code}?name=MC+Panel&type=self-managed"
        body = {"code": code, "agent_type": "self-managed", "version": brand.CLAIM_NAME}
        self.claim_url, self.state = url, "needs_claim"
        self.note("Waiting for you to accept the link on playit.gg (guest or account).")
        opened, fails, deadline = False, 0, time.time() + 10 * 60
        while time.time() < deadline and gen == self._gen and not self._stop:
            try:
                st, ok, data, text = api("/claim/setup", body)
                fails = 0 if ok else fails + 1
            except requests.RequestException as e:
                self._api_log(f"playit.gg is not reachable ({e.__class__.__name__}). Check the internet connection.")
                fails += 1
                if fails > 20:
                    raise PlayitError("playit.gg cannot be reached. Check your internet connection and try again.") from e
                time.sleep(3)
                continue
            if not ok:
                self._api_log(f"claim answered {st}: {redact(text)[:160]}")
                if fails > 8:
                    raise PlayitError(f"playit.gg refused the link request (error {st}). Press Copy diagnostics and send it to the developer.")
            word = str(data)
            if "UserRejected" in word:
                raise PlayitError("You pressed Reject on the playit page. Start the helper again and press Accept.")
            if "UserAccepted" in word:
                try:
                    st, ok, data, text = api("/claim/exchange", {"code": code})
                except requests.RequestException:
                    ok, data, text = False, None, ""
                key = data.get("secret_key") if isinstance(data, dict) else ""
                if ok and key:
                    update_settings({"playit_secret": str(key)})
                    self.claim_url = ""
                    self.note("Linked to playit.gg.")
                    return str(key)
                self._api_log(f"claim exchange answered {st}: {redact(text)[:160]}")
            if ok and not opened:
                opened = True
                try:
                    webbrowser.open(url)
                except Exception:  # noqa: BLE001  (the button on the page still works)
                    pass
            time.sleep(3)
        if not self._stop and gen == self._gen:
            raise PlayitError("The link was not accepted in 10 minutes. Press Start helper to get a new link.")
        return ""

    def _tunnel_setup(self, secret: str) -> None:
        """Make sure a Minecraft Java tunnel exists for the server port. Best effort: failure only leaves a note."""
        data = self._rundata(secret)
        if data is None:
            return
        bad = BAD_ACCOUNT.get(self.account)
        if bad:
            raise PlayitError(bad)
        port = self.local_port
        if not port:
            return
        for t in data.get("tunnels") or []:
            if not isinstance(t, dict) or t.get("disabled"):
                continue
            mine = t.get("name") in tunnel_names(self.tag, port)
            legacy = not self.tag and t.get("local_port") == port
            if mine or legacy:
                self.note(f"Tunnel for this server already exists.")
                return
        agent_id = data.get("agent_id")
        base = {"name": tunnel_name(self.tag, port), "tunnel_type": "minecraft-java", "port_type": "tcp", "port_count": 1,
                "origin": {"type": "agent", "data": {"agent_id": agent_id, "local_ip": "127.0.0.1", "local_port": port}},
                "enabled": True}
        variants = [dict(base), {**base, "alloc": {"type": "region", "details": {"region": "global"}}},
                    {**base, "tunnel_type": None}]
        last = ""
        for body in variants:
            try:
                st, ok, resp, text = api("/tunnels/create", body, secret)
            except requests.RequestException as e:
                last = e.__class__.__name__
                break
            if ok:
                self.note(f"Created a Minecraft Java tunnel for port {port}.")
                self.tunnel_note = ""
                return
            last = f"{st}: {redact(text, secret)[:160]}"
            self.note(f"Tunnel create answered {last}")
            if "limit" in text.lower():
                self.tunnel_note = ("Your playit account has reached its tunnel limit. Delete an old tunnel on playit.gg, "
                                    "or press Unlink and link a different account.")
                return
        if self.account.startswith("email-not"):
            self.tunnel_note = ("Your playit.gg email is not verified yet, and playit only allows tunnels after that. "
                                "Open the verification email from playit.gg and press the link. The panel tries again by itself every minute.")
        else:
            self.tunnel_note = (f"The panel could not create the tunnel by itself. On playit.gg, open your agent and add a "
                                f"Minecraft Java tunnel with local port {port}. The address will then appear here.")

    def unlink(self) -> None:
        self.stop()
        update_settings({"playit_secret": ""})
        (PLAYIT_DIR / "playit.toml").unlink(missing_ok=True)
        with self.lock:
            self.account, self.address, self.claim_url, self.error, self.tunnel_note = "", "", "", "", ""
            self.state = "stopped"

    def diagnostics(self) -> str:
        s = get_settings()
        secret = find_secret()
        lines = [f"{brand.NAME} {brand.VERSION} playit report", f"OS: {platform.platform()}", f"mode: {s.get('playit_mode')}",
                 f"state: {self.state}", f"account: {self.account or '-'}", f"linked: {bool(secret)}",
                 f"helper: {self.version or '-'} | {self.cmdline or '-'}", f"error: {self.error or '-'}",
                 f"tunnel note: {self.tunnel_note or '-'}", f"address: {self.address or '-'}", "--- panel messages ---",
                 *(self.notes or ["none"]), "--- helper log ---", *self.log]
        return redact("\n".join(lines), secret)

    def _api_log(self, text: str) -> None:
        if text != self._api_note:
            self._api_note = text
            self.note(text)

    def _parse(self, raw: str) -> None:
        line = ANSI_RE.sub("", raw).strip()
        if not line or any(n in line for n in NOISE):
            return
        self.log.append(line[:300])
        m = CLAIM_RE.search(line)
        if m:
            self.claim_url = m.group(0)
            if not self.address:
                self.state = "needs_claim"
            return
        m = ADDR_RE.search(line)
        if m:
            self.address = m.group(1)
            self.claim_url = ""
            self.state = "online"

    def stop(self) -> None:
        self._stop = True
        p = self.proc
        if p and p.poll() is None:
            try:
                p.terminate()
                p.wait(timeout=5)
            except (OSError, subprocess.SubprocessError):
                try:
                    p.kill()
                except OSError:
                    pass
        with self.lock:
            if self.state != "error":
                self.state = "stopped"

    def status(self) -> dict:
        s = get_settings()
        manual = s.get("playit_address", "").strip()
        mode = s.get("playit_mode", "managed")
        state = "external" if mode == "external" else self.state
        return {"state": state, "mode": mode, "claim_url": self.claim_url, "detected_address": self.address,
                "address": manual or self.address, "manual": bool(manual), "error": self.error,
                "log": list(self.log)[-40:], "has_binary": self._has_binary(), "version": self.version,
                "cmdline": self.cmdline, "account": self.account, "tunnel_note": self.tunnel_note, "linked": bool(find_secret()),
                "other_app_installed": bool(shutil.which("playit") or shutil.which("playit-cli"))}

    def _has_binary(self) -> bool:
        try:
            return bool(self.binary())
        except PlayitError:
            return False


playit = Playit()
