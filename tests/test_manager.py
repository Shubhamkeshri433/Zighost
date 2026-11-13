"""Tests with a fake Minecraft process (no Java, no internet). Run: python -I tests/test_manager.py
POSIX only (the fake java is a shell script)."""
import os
import sys
import tempfile
import time
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TMP = tempfile.mkdtemp(prefix="mcpanel-test-")
os.environ["MCPANEL_DATA"] = TMP
sys.path.insert(0, str(ROOT))

from backend import backups, providers          # noqa: E402
from backend.manager import Manager, ManagerError  # noqa: E402
from backend.props import read_props, write_props  # noqa: E402
from backend.store import (ensure_dirs, save_server, server_dir, update_settings)  # noqa: E402

providers.java_required = lambda v: 8   # no network in tests
FAKE_JAVA = str(ROOT / "tests" / "fake_java" / "java")


def wait_for(cond, secs=10):
    end = time.time() + secs
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.05)
    return False


def make_server(sid="aaaaaaaa", port=25999):
    ensure_dirs()
    d = server_dir(sid)
    d.mkdir(parents=True, exist_ok=True)
    (d / "server.jar").write_bytes(b"x" * 2048)
    (d / "world").mkdir(exist_ok=True)
    (d / "world" / "level.dat").write_text("level")
    write_props(d / "server.properties", {"server-port": str(port), "motd": "t"})
    save_server({"id": sid, "name": "T", "type": "paper", "version": "1.21.4", "ram_mb": 512,
                 "port": port, "installed": True, "motd": "t"})
    return sid


class ManagerTests(unittest.TestCase):
    def setUp(self):
        update_settings({"java_path": FAKE_JAVA, "auto_restart": True, "playit_auto": False})
        self.m = Manager()
        self.sid = make_server()

    def tearDown(self):
        self.m.stop_requested = True
        if self.m.proc:
            self.m._terminate(self.m.proc)
        wait_for(lambda: self.m.state in ("offline", "crashed"), 5)

    def test_start_players_command_stop(self):
        self.m.start(self.sid)
        self.assertTrue(wait_for(lambda: self.m.state == "online"), self.m.console.since(0))
        self.m.send_command("join Steve")
        self.assertTrue(wait_for(lambda: "Steve" in self.m.players))
        self.m.send_command("leave Steve")
        self.assertTrue(wait_for(lambda: "Steve" not in self.m.players))
        self.assertIn("> join Steve", [t for _, t in self.m.console.since(0)])
        self.m.stop()
        self.assertTrue(wait_for(lambda: self.m.state == "offline"))
        self.assertTrue(any("Server stopped." in t for _, t in self.m.console.since(0)))

    def test_settings_saved_while_running_survive_the_server_rewriting_its_file(self):
        from backend.store import update_server, get_server
        self.m.start(self.sid)
        self.assertTrue(wait_for(lambda: self.m.state == "online"))
        d = server_dir(self.sid)
        # what the panel's save does while the server runs: file changed and remembered
        write_props(d / "server.properties", {"online-mode": "false", "white-list": "false"})
        update_server(self.sid, {"pending_props": {"online-mode": "false", "white-list": "false"}})
        # the Minecraft server writes its older in-memory values back while stopping
        write_props(d / "server.properties", {"online-mode": "true", "white-list": "true"})
        self.m.reapply_pending(self.sid)          # what _on_exit does right after the process ends
        p = read_props(d / "server.properties")
        self.assertEqual((p["online-mode"], p["white-list"]), ("false", "false"))
        self.m.stop()
        self.assertTrue(wait_for(lambda: self.m.state == "offline", 10))
        # next start also puts them back, then forgets them
        write_props(d / "server.properties", {"online-mode": "true"})
        self.m.start(self.sid)
        self.assertTrue(wait_for(lambda: self.m.state == "online"))
        self.assertEqual(read_props(d / "server.properties")["online-mode"], "false")
        self.assertFalse(get_server(self.sid).get("pending_props"))

    def test_second_start_refused_and_bad_command(self):
        self.m.start(self.sid)
        with self.assertRaises(ManagerError):
            self.m.start(self.sid)
        wait_for(lambda: self.m.state == "online")
        with self.assertRaises(ManagerError):
            self.m.send_command("say hi\nop me")
        self.m.stop()
        wait_for(lambda: self.m.state == "offline")
        with self.assertRaises(ManagerError):
            self.m.send_command("list")

    def test_crash_then_auto_restart(self):
        self.m.start(self.sid)
        wait_for(lambda: self.m.state == "online")
        first = self.m.proc.pid
        self.m.send_command("crash")
        self.assertTrue(wait_for(lambda: self.m.state == "crashed", 5))
        self.assertTrue(wait_for(lambda: self.m.state == "online" and self.m.proc and self.m.proc.pid != first, 15),
                        [t for _, t in self.m.console.since(0)][-6:])

    def test_crash_loop_pauses_auto_restart(self):
        update_settings({"auto_restart": False})
        self.m.start(self.sid)
        wait_for(lambda: self.m.state == "online")
        self.m.send_command("crash")
        self.assertTrue(wait_for(lambda: self.m.state == "crashed", 5))
        time.sleep(6)
        self.assertEqual(self.m.state, "crashed")

    def test_port_in_use(self):
        import socket
        s = socket.socket(); s.bind(("127.0.0.1", 25998)); s.listen(1)
        try:
            sid = make_server("bbbbbbbb", 25998)
            with self.assertRaises(ManagerError) as cm:
                self.m.start(sid)
            self.assertIn("already used", str(cm.exception))
        finally:
            s.close()

    def test_delete_blocked_while_running(self):
        self.m.start(self.sid)
        wait_for(lambda: self.m.state == "online")
        with self.assertRaises(ManagerError):
            self.m.delete_server(self.sid)

    def test_create_validation(self):
        with self.assertRaises(ManagerError):
            self.m.create_server("", "paper", "1.21.4", 2048, 25565, True)
        with self.assertRaises(ManagerError):
            self.m.create_server("x", "paper", "1.21.4", 2048, 25565, False)
        with self.assertRaises(ManagerError):
            self.m.create_server("x", "nope", "1.21.4", 2048, 25565, True)
        with self.assertRaises(ManagerError):
            self.m.create_server("x", "paper", "1.21.4", 2048, 80, True)
        with self.assertRaises(ManagerError):
            self.m.create_server("x", "paper", "1.21.4", 10**7, 25565, True)


class BackupAndPropsTests(unittest.TestCase):
    def test_backup_restore_roundtrip(self):
        sid = make_server("cccccccc", 25997)
        info = backups.create_backup(sid)
        d = server_dir(sid)
        (d / "world" / "level.dat").write_text("changed")
        backups.restore_backup(sid, info["name"])
        self.assertEqual((d / "world" / "level.dat").read_text(), "level")
        self.assertTrue(any("before-restore" in b["name"] for b in backups.list_backups(sid)))
        self.assertTrue((d / "server.jar").exists())

    def test_zip_slip_rejected(self):
        sid = make_server("dddddddd", 25996)
        from backend.store import backup_dir
        bd = backup_dir(sid); bd.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(bd / "evil.zip", "w") as z:
            z.writestr("../../escape.txt", "bad")
        with self.assertRaises(backups.BackupError):
            backups.restore_backup(sid, "evil.zip")
        self.assertFalse((Path(TMP) / "escape.txt").exists())

    def test_backup_names_validated(self):
        for bad in ("../x.zip", "a/b.zip", "x.txt", ""):
            with self.assertRaises(backups.BackupError):
                backups.safe_name(bad)

    def test_props_keep_comments_and_reject_newlines(self):
        p = Path(TMP) / "p.properties"
        p.write_text("#hello\nmotd=a\nunknown=1\n")
        write_props(p, {"motd": "b", "pvp": "false"})
        text = p.read_text()
        self.assertIn("#hello", text)
        self.assertEqual(read_props(p), {"motd": "b", "unknown": "1", "pvp": "false"})
        with self.assertRaises(ValueError):
            write_props(p, {"motd": "x\nop=1"})


class ApiTests(unittest.TestCase):
    def test_guard_and_errors(self):
        from starlette.testclient import TestClient
        from backend.app import app
        with TestClient(app, base_url="http://127.0.0.1:8765") as c:
            self.assertEqual(c.post("/api/stop").status_code, 403)            # no header
            self.assertEqual(c.post("/api/stop", headers={"X-MCPanel": "1"}).status_code, 400)
            self.assertIn(c.get("/api/servers/..%2f..%2fx/backups").status_code, (400, 404))   # path tricks never work
            self.assertEqual(c.get("/api/servers/evil/backups").status_code, 400)             # unknown id
            self.assertNotIn("playit_secret", c.get("/api/settings").json())
            r = c.put("/api/settings", json={"playit_secret": "abc"}, headers={"X-MCPanel": "1"})
            self.assertTrue(r.json()["playit_secret_set"])
            self.assertNotIn("abc", r.text)
            r = c.put("/api/settings", json={"playit_secret": ""}, headers={"X-MCPanel": "1"})
            self.assertTrue(r.json()["playit_secret_set"])                      # blank keeps the key
            r = c.put("/api/settings", json={"clear_playit_secret": True}, headers={"X-MCPanel": "1"})
            self.assertFalse(r.json()["playit_secret_set"])
        with TestClient(app, base_url="http://evil.example") as c:
            self.assertEqual(c.get("/api/status").status_code, 403)


class PlayitParseTests(unittest.TestCase):
    def test_parse(self):
        from backend.playit import Playit, _pick_asset
        p = Playit()
        p._parse("\x1b[32mVisit https://playit.gg/claim/abc123 to link\x1b[0m\n")
        self.assertEqual(p.state, "needs_claim")
        self.assertTrue(p.claim_url.endswith("/claim/abc123"))
        p._parse("tunnel ready: cool-name.at.ply.gg:41872 => 127.0.0.1:25565")
        self.assertEqual((p.state, p.address, p.claim_url), ("online", "cool-name.at.ply.gg:41872", ""))
        assets = [{"name": "playit-linux-aarch64"}, {"name": "playit-linux-amd64"},
                  {"name": "playit-windows-x86_64-signed.exe"}, {"name": "playit.msi"}]
        got = _pick_asset(assets)
        self.assertIn(got["name"], ("playit-linux-amd64", "playit-linux-aarch64"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
