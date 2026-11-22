"""Duplicate a server: files copied, new name and port, original untouched. Run: python -I tests/test_duplicate.py"""
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TMP = tempfile.mkdtemp(prefix="mcpanel-dup-")
os.environ["MCPANEL_DATA"] = TMP
sys.path.insert(0, str(ROOT))

from backend.manager import Manager, ManagerError  # noqa: E402
from backend.props import read_props, write_props  # noqa: E402
from backend.store import ensure_dirs, get_server, list_servers, save_server, server_dir  # noqa: E402


def wait_for(cond, secs=10):
    end = time.time() + secs
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.05)
    return False


class DuplicateTest(unittest.TestCase):
    def setUp(self):
        ensure_dirs()
        import shutil
        from backend.store import SERVERS_DIR, remove_server
        for s in list_servers():
            remove_server(s["id"])
        shutil.rmtree(SERVERS_DIR, ignore_errors=True)
        ensure_dirs()
        self.m = Manager()
        d = server_dir("aaaa1111")
        (d / "world").mkdir(parents=True)
        (d / "plugins").mkdir()
        (d / "world" / "level.dat").write_bytes(b"world-data")
        (d / "plugins" / "Essentials.jar").write_bytes(b"jar")
        (d / "server.jar").write_bytes(b"server")
        (d / "session.lock").write_text("x")
        write_props(d / "server.properties", {"server-port": "25565", "motd": "hello"})
        save_server({"id": "aaaa1111", "name": "Friends", "type": "paper", "version": "1.21.4", "ram_mb": 1024,
                     "port": 25565, "eula": True, "motd": "hello", "jvm_args": "", "notes": "n", "schedules": [],
                     "installed": True, "created": 1})

    def test_copy_keeps_data_and_changes_name_and_port(self):
        meta = self.m.duplicate_server("aaaa1111")
        self.assertEqual(meta["name"], "Friends duplicate")
        self.assertNotEqual(meta["id"], "aaaa1111")
        self.assertNotEqual(meta["port"], 25565)
        self.assertTrue(wait_for(lambda: (get_server(meta["id"]) or {}).get("installed")))
        nd = server_dir(meta["id"])
        self.assertEqual((nd / "world" / "level.dat").read_bytes(), b"world-data")
        self.assertTrue((nd / "plugins" / "Essentials.jar").exists())
        self.assertFalse((nd / "session.lock").exists())
        self.assertEqual(read_props(nd / "server.properties")["server-port"], str(meta["port"]))
        self.assertEqual(read_props(server_dir("aaaa1111") / "server.properties")["server-port"], "25565")
        self.assertEqual(get_server("aaaa1111")["port"], 25565)
        self.assertFalse(self.m.install_job["active"])

    def test_custom_name_and_numbering(self):
        a = self.m.duplicate_server("aaaa1111", "My copy")
        self.assertEqual(a["name"], "My copy")
        self.assertTrue(wait_for(lambda: not self.m.install_job["active"]))
        b = self.m.duplicate_server("aaaa1111")
        self.assertTrue(wait_for(lambda: not self.m.install_job["active"]))
        c = self.m.duplicate_server("aaaa1111")
        self.assertEqual(b["name"], "Friends duplicate")
        self.assertEqual(c["name"], "Friends duplicate 2")
        self.assertEqual(len({a["port"], b["port"], c["port"]}), 3)

    def test_refuses_while_running_or_busy(self):
        self.m.active_id, self.m.state = "aaaa1111", "online"
        with self.assertRaises(ManagerError):
            self.m.duplicate_server("aaaa1111")
        self.m.state = "offline"
        self.m.install_job["active"] = True
        with self.assertRaises(ManagerError):
            self.m.duplicate_server("aaaa1111")
        self.m.install_job["active"] = False
        with self.assertRaises(ManagerError):
            self.m.duplicate_server("nope")
        with self.assertRaises(ManagerError):
            self.m.duplicate_server("aaaa1111", "x" * 41)

    def test_failed_copy_leaves_nothing(self):
        import shutil
        real = shutil.copy2
        shutil.copy2 = lambda *a, **k: (_ for _ in ()).throw(OSError("disk full"))
        try:
            meta = self.m.duplicate_server("aaaa1111")
            self.assertTrue(wait_for(lambda: not self.m.install_job["active"]))
        finally:
            shutil.copy2 = real
        self.assertIsNone(get_server(meta["id"]))
        self.assertFalse(server_dir(meta["id"]).exists())
        self.assertIn("Copy failed", self.m.install_job["error"])
        self.assertEqual(len(list_servers()), 1)


if __name__ == "__main__":
    unittest.main()
