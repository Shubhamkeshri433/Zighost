"""Tests for players, files, plugins, scheduler, server config and playit helpers. Run: python -I tests/test_backend2.py"""
import json
import os
import sys
import tempfile
import time
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TMP = tempfile.mkdtemp(prefix="mcpanel-test2-")
os.environ["MCPANEL_DATA"] = TMP
sys.path.insert(0, str(ROOT))

from backend import fsops, players, plugins, providers   # noqa: E402
from backend.manager import Manager, ManagerError, parse_jvm_args   # noqa: E402
from backend.playit import parse_rundata, pick_release   # noqa: E402
from backend.props import clean_props, read_props, write_props   # noqa: E402
from backend.scheduler import ScheduleError, Scheduler, clean_schedules   # noqa: E402
from backend.store import ensure_dirs, get_server, save_server, server_dir, update_settings   # noqa: E402

providers.java_required = lambda v: 8
HDR = {"X-MCPanel": "1"}


def make_server(sid, stype="paper", port=25900, props=None):
    ensure_dirs()
    d = server_dir(sid)
    d.mkdir(parents=True, exist_ok=True)
    (d / "server.jar").write_bytes(b"x" * 2048)
    write_props(d / "server.properties", {"server-port": str(port), "online-mode": "false", **(props or {})})
    save_server({"id": sid, "name": "T", "type": stype, "version": "1.21.4", "ram_mb": 512, "port": port,
                 "installed": True, "motd": "t", "schedules": []})
    return d


class PlayersTests(unittest.TestCase):
    def test_offline_edits_all_lists(self):
        sid = "11111111"
        d = make_server(sid)
        self.assertIn("added", players.apply(sid, "whitelist_add", "Steve").lower())
        wl = json.loads((d / "whitelist.json").read_text())
        self.assertEqual(wl[0]["name"], "Steve")
        self.assertEqual(wl[0]["uuid"], players.offline_uuid("Steve"))
        players.apply(sid, "op", "Steve")
        players.apply(sid, "ban", "Alex", "griefing")
        ov = players.overview(sid)
        self.assertEqual([e["name"] for e in ov["ops"]], ["Steve"])
        self.assertEqual(ov["bans"][0]["reason"], "griefing")
        players.apply(sid, "pardon", "Alex")
        players.apply(sid, "deop", "Steve")
        players.apply(sid, "whitelist_remove", "steve")           # case-insensitive
        ov = players.overview(sid)
        self.assertEqual((ov["ops"], ov["bans"], ov["whitelist"]), ([], [], []))
        players.apply(sid, "whitelist_toggle", value="on")
        self.assertTrue(players.overview(sid)["whitelist_on"])

    def test_commands_when_running_and_validation(self):
        sid = "22222222"
        make_server(sid)
        sent = []
        players.apply(sid, "kick", "Steve", "be nice", running=True, send=sent.append)
        players.apply(sid, "gamemode", "Steve", "creative", running=True, send=sent.append)
        players.apply(sid, "whitelist_toggle", value="off", running=True, send=sent.append)
        self.assertEqual(sent, ["kick Steve be nice", "gamemode creative Steve", "whitelist off"])
        for bad in ("Steve\nop Evil", "a b", "", "x" * 40, "St;eve"):
            with self.assertRaises(players.PlayerError):
                players.apply(sid, "op", bad, running=True, send=sent.append)
        with self.assertRaises(players.PlayerError):
            players.apply(sid, "gamemode", "Steve", "god", running=True, send=sent.append)
        with self.assertRaises(players.PlayerError):
            players.apply(sid, "kick", "Steve")                    # offline: needs the server
        # a reason cannot smuggle a second command
        players.apply(sid, "ban", "Steve", "x\nop Evil", running=True, send=sent.append)
        self.assertNotIn("\n", sent[-1])


class FsTests(unittest.TestCase):
    def setUp(self):
        self.root = make_server("33333333")

    def test_traversal_blocked(self):
        for bad in ("../x", "a/../../x", "..\\x", "C:/Windows", "a\x00b"):
            with self.assertRaises(fsops.FsError, msg=bad):
                fsops.resolve(self.root, bad)
        # a leading slash is read as "inside the server folder", never as the real root of the disk
        inside = fsops.resolve(self.root, "/etc/passwd")
        self.assertEqual(inside, self.root.resolve() / "etc" / "passwd")

    def test_symlink_escape_blocked(self):
        outside = Path(tempfile.mkdtemp())
        (outside / "secret.txt").write_text("s")
        try:
            os.symlink(outside, self.root / "link")
        except (OSError, NotImplementedError):
            self.skipTest("symlinks not available")
        with self.assertRaises(fsops.FsError):
            fsops.read_text(self.root, "link/secret.txt")

    def test_edit_rename_delete_mkdir(self):
        fsops.mkdir(self.root, "", "plugins")
        fsops.write_text(self.root, "plugins/a.yml", "x: 1\n")
        self.assertEqual(fsops.read_text(self.root, "plugins/a.yml")["content"], "x: 1\n")
        fsops.rename(self.root, "plugins/a.yml", "b.yml", False)
        names = [e["name"] for e in fsops.listdir(self.root, "plugins")["entries"]]
        self.assertEqual(names, ["b.yml"])
        with self.assertRaises(fsops.FsError):
            fsops.rename(self.root, "plugins/b.yml", "../evil.yml", False)
        with self.assertRaises(fsops.FsError):
            fsops.delete(self.root, "plugins", running=True)       # folders: not while running
        fsops.delete(self.root, "plugins", running=False)
        with self.assertRaises(fsops.FsError):
            fsops.delete(self.root, "server.jar", False)
        with self.assertRaises(fsops.FsError):
            fsops.delete(self.root, "", False)

    def test_binary_and_names(self):
        (self.root / "bin.dat").write_bytes(b"\x00\x01\x02")
        with self.assertRaises(fsops.FsError):
            fsops.read_text(self.root, "bin.dat")
        for bad in ("a:b", "con", "x/y", "", "..", "a|b"):
            with self.assertRaises(fsops.FsError, msg=bad):
                fsops.clean_name(bad)


class PluginTests(unittest.TestCase):
    def test_list_toggle_remove(self):
        sid = "44444444"
        d = make_server(sid)
        (d / "plugins").mkdir()
        with zipfile.ZipFile(d / "plugins" / "Cool.jar", "w") as z:
            z.writestr("plugin.yml", "name: CoolPlugin\nversion: '2.1'\ndescription: Does cool things\n")
        got = plugins.list_installed(sid)
        self.assertTrue(got["supported"])
        self.assertEqual((got["items"][0]["title"], got["items"][0]["version"]), ("CoolPlugin", "2.1"))
        plugins.set_enabled(sid, "Cool.jar", False)
        self.assertTrue((d / "plugins" / "Cool.jar.disabled").exists())
        self.assertFalse(plugins.list_installed(sid)["items"][0]["enabled"])
        plugins.set_enabled(sid, "Cool.jar.disabled", True)
        self.assertTrue((d / "plugins" / "Cool.jar").exists())
        with self.assertRaises((plugins.PluginError, fsops.FsError)):   # the API turns both into a 400
            plugins.set_enabled(sid, "../server.jar", False)
        with self.assertRaises(plugins.PluginError):
            plugins.set_enabled(sid, "server.properties", False)
        plugins.remove(sid, "Cool.jar")
        self.assertEqual(plugins.list_installed(sid)["items"], [])

    def test_vanilla_unsupported_and_fabric_info(self):
        make_server("55555555", "vanilla")
        self.assertFalse(plugins.list_installed("55555555")["supported"])
        d = make_server("66666666", "fabric")
        (d / "mods").mkdir()
        with zipfile.ZipFile(d / "mods" / "m.jar", "w") as z:
            z.writestr("fabric.mod.json", json.dumps({"id": "m", "name": "Mod M", "version": "1.0"}))
        self.assertEqual(plugins.list_installed("66666666")["items"][0]["title"], "Mod M")


class SchedulerTests(unittest.TestCase):
    def test_validation(self):
        ok = clean_schedules([{"kind": "backup", "mode": "every", "every_min": 30, "keep": 3},
                              {"kind": "restart", "mode": "at", "at": "04:30"},
                              {"kind": "command", "mode": "every", "every_min": 10, "command": "/say hi"}])
        self.assertEqual(ok[2]["command"], "say hi")
        for bad in ([{"kind": "x"}], [{"kind": "restart", "mode": "every", "every_min": 1}],
                    [{"kind": "restart", "mode": "at", "at": "25:00"}],
                    [{"kind": "command", "mode": "every", "every_min": 10, "command": "a\nb"}], "nope"):
            with self.assertRaises(ScheduleError, msg=str(bad)):
                clean_schedules(bad)

    def test_due_logic(self):
        s = Scheduler(Manager(), {})
        job = {"id": "j1", "mode": "every", "every_min": 10}
        t0 = 1_000_000.0
        self.assertFalse(s._due("a", job, t0))                     # first sight never fires
        self.assertFalse(s._due("a", job, t0 + 599))
        self.assertTrue(s._due("a", job, t0 + 601))
        self.assertFalse(s._due("a", job, t0 + 700))
        at = {"id": "j2", "mode": "at", "at": "04:30"}
        base = time.mktime((2026, 11, 10, 3, 0, 0, 0, 0, -1))
        self.assertFalse(s._due("a", at, base))
        self.assertTrue(s._due("a", at, base + 3600 * 2))          # 05:00 passed 04:30
        self.assertFalse(s._due("a", at, base + 3600 * 3))         # once per day
        self.assertTrue(s._due("a", at, base + 86400 + 3600 * 2))  # next day
        late = {"id": "j3", "mode": "at", "at": "01:00"}
        self.assertFalse(s._due("b", late, base))                  # already past when first seen: skip today


class ConfigTests(unittest.TestCase):
    def test_jvm_args(self):
        self.assertEqual(parse_jvm_args("-Dfoo=bar -XX:+UseZGC"), ["-Dfoo=bar", "-XX:+UseZGC"])
        for bad in ("-Xmx4G", "-xms1G", "-jar evil.jar", "-cp x", "notaflag", "-Dx='unclosed"):
            with self.assertRaises(ManagerError, msg=bad):
                parse_jvm_args(bad)

    def test_clean_props(self):
        self.assertEqual(clean_props({"pvp": False, "max-players": 10, "motd": "hi"}),
                         {"pvp": "false", "max-players": "10", "motd": "hi"})
        for bad in ({"Bad Key": "x"}, {"a": "x\ny"}, {"a=b": "x"}, {"a": [1]}, "str"):
            with self.assertRaises(ValueError, msg=str(bad)):
                clean_props(bad)

    def test_initial_props_written_and_update_config(self):
        update_settings({"java_path": str(ROOT / "tests" / "fake_java" / "java")})
        m = Manager()
        d = make_server("77777777", port=25901)
        m._initial_props["77777777"] = {"difficulty": "hard", "pvp": "false"}
        meta = get_server("77777777")
        with self.assertRaises(ManagerError):
            m.update_config("77777777", {"ram_mb": 100})
        out = m.update_config("77777777", {"name": "Renamed", "port": 25999, "jvm_args": "-Dx=1", "notes": "hello"})
        self.assertEqual((out["name"], out["port"], out["jvm_args"]), ("Renamed", 25999, "-Dx=1"))
        self.assertEqual(read_props(d / "server.properties")["server-port"], "25999")
        cmd = m._build_command(out, "java")
        self.assertIn("-Dx=1", cmd)
        self.assertEqual(cmd[-3:], ["-jar", "server.jar", "nogui"])


class PlayitHelperTests(unittest.TestCase):
    def test_pick_release_prefers_command_line_agent(self):
        rels = [
            {"tag_name": "v2.0.2", "assets": [{"name": "playit-windows-x86_64-signed.exe"}, {"name": "playit-linux-amd64"}]},
            {"tag_name": "v1.0.10", "assets": [{"name": "playit-windows-x86_64-signed.exe"}, {"name": "playit-linux-amd64"}]},
            {"tag_name": "v0.17.1", "assets": [{"name": "playit-windows-x86_64-signed.exe"}, {"name": "playit-windows-x86_64-signed.msi"},
                                              {"name": "playit-linux-amd64"}, {"name": "playit-linux-aarch64"}]},
            {"tag_name": "v0.16.5", "assets": [{"name": "playit-linux-amd64"}]},
            {"tag_name": "v0.14.0", "assets": [{"name": "playit-linux-amd64"}]},
        ]
        rel, asset = pick_release(rels)
        self.assertEqual(rel["tag_name"], "v0.17.1")
        self.assertNotIn(".msi", asset["name"])
        self.assertIsNone(pick_release(rels[:2]))

    def test_parse_rundata(self):
        data = {"tunnels": [{"assigned_domain": "a.joinmc.link", "tunnel_type": "minecraft-java", "port": {"from": 25565}},
                            {"assigned_domain": "b.gl.at.ply.gg", "tunnel_type": "tcp", "port": {"from": 41872}, "local_port": 25565}]}
        self.assertEqual(parse_rundata(data, 25565), "b.gl.at.ply.gg:41872")
        self.assertEqual(parse_rundata(data, None), "a.joinmc.link")
        self.assertEqual(parse_rundata({"data": data}, None), "a.joinmc.link")
        self.assertEqual(parse_rundata({"tunnels": [{"disabled": True, "assigned_domain": "x.joinmc.link"}]}), "")
        self.assertEqual(parse_rundata("garbage"), "")


class ApiTests(unittest.TestCase):
    def setUp(self):
        from starlette.testclient import TestClient
        from backend.app import app
        self.c = TestClient(app, base_url="http://127.0.0.1:8765")
        self.c.__enter__()
        self.sid = "88888888"
        self.root = make_server(self.sid, port=25902)

    def tearDown(self):
        self.c.__exit__(None, None, None)

    def test_files_roundtrip(self):
        c, s = self.c, self.sid
        r = c.post(f"/api/servers/{s}/files/upload?path=&name=hello.txt", content=b"hi there", headers=HDR)
        self.assertEqual(r.json()["size"], 8)
        self.assertEqual(c.get(f"/api/servers/{s}/file?path=hello.txt").json()["content"], "hi there")
        self.assertEqual(c.get(f"/api/servers/{s}/download?path=hello.txt").content, b"hi there")
        r = c.put(f"/api/servers/{s}/file", json={"path": "hello.txt", "content": "changed"}, headers=HDR)
        self.assertTrue(r.json()["ok"])
        self.assertEqual((self.root / "hello.txt").read_text(), "changed")
        bad = c.post(f"/api/servers/{s}/files/upload?path=&name=../evil.txt", content=b"x", headers=HDR)
        self.assertEqual(bad.status_code, 400)
        bad = c.get(f"/api/servers/{s}/file?path=../../etc/passwd")
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(c.post(f"/api/servers/{s}/files/delete", json={"path": "hello.txt"}, headers=HDR).status_code, 200)
        self.assertFalse((self.root / "hello.txt").exists())
        self.assertFalse(list(self.root.glob("*.part")))

    def test_players_schedules_worlds_config(self):
        c, s = self.c, self.sid
        r = c.post(f"/api/servers/{s}/players/action", json={"action": "whitelist_add", "name": "Steve"}, headers=HDR)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(c.get(f"/api/servers/{s}/players").json()["whitelist"][0]["name"], "Steve")
        r = c.post(f"/api/servers/{s}/players/action", json={"action": "op", "name": "bad name"}, headers=HDR)
        self.assertEqual(r.status_code, 400)
        r = c.put(f"/api/servers/{s}/schedules", json={"schedules": [{"kind": "backup", "mode": "every", "every_min": 60}]}, headers=HDR)
        self.assertEqual(r.json()["schedules"][0]["keep"], 5)
        self.assertEqual(c.get(f"/api/servers/{s}/schedules").json()["schedules"][0]["kind"], "backup")
        self.assertEqual(c.put(f"/api/servers/{s}/schedules", json={"schedules": [{"kind": "x"}]}, headers=HDR).status_code, 400)
        (self.root / "world").mkdir(exist_ok=True)
        (self.root / "world" / "level.dat").write_text("w")
        self.assertEqual(c.get(f"/api/servers/{s}/worlds").json()["worlds"][0]["name"], "world")
        self.assertEqual(c.post(f"/api/servers/{s}/worlds/reset", json={}, headers=HDR).status_code, 400)
        r = c.post(f"/api/servers/{s}/worlds/reset", json={"confirm": True}, headers=HDR)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertFalse((self.root / "world").exists())
        self.assertTrue(any("before-reset" in b["name"] for b in c.get(f"/api/servers/{s}/backups").json()["backups"]))
        r = c.patch(f"/api/servers/{s}", json={"name": "New name", "ram_mb": 1024, "jvm_args": "-Xmx9G"}, headers=HDR)
        self.assertEqual(r.status_code, 400)
        r = c.patch(f"/api/servers/{s}", json={"name": "New name", "ram_mb": 1024}, headers=HDR)
        self.assertEqual(r.json()["server"]["name"], "New name")

    def test_settings_theme_and_mode(self):
        r = self.c.put("/api/settings", json={"theme": "nether", "playit_mode": "external"}, headers=HDR).json()
        self.assertEqual((r["theme"], r["playit_mode"]), ("nether", "external"))
        r = self.c.put("/api/settings", json={"theme": "hacked", "playit_mode": "bogus"}, headers=HDR).json()
        self.assertEqual((r["theme"], r["playit_mode"]), ("deepslate", "managed"))
        self.assertEqual(self.c.get("/api/status").json()["playit"]["mode"], "managed")

    def test_create_server_rejects_bad_props(self):
        r = self.c.post("/api/servers", headers=HDR, json={"name": "x", "type": "paper", "version": "1.21.4", "ram_mb": 1024,
                                                           "port": 25911, "eula": True, "properties": {"bad key": "1"}})
        self.assertEqual(r.status_code, 400)
        self.assertIn("not a valid setting name", r.json()["error"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
