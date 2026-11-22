"""Change a server's Minecraft version: new jar in, old version files out, world and settings kept. No internet.
Run: python -I tests/test_version_change.py"""
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TMP = tempfile.mkdtemp(prefix="mcpanel-ver-")
os.environ["MCPANEL_DATA"] = TMP
sys.path.insert(0, str(ROOT))

from backend import backups, providers  # noqa: E402
from backend.manager import Manager, ManagerError  # noqa: E402
from backend.props import write_props  # noqa: E402
from backend.store import BACKUPS_DIR, SERVERS_DIR, ensure_dirs, get_server, list_servers, remove_server, save_server, server_dir  # noqa: E402

providers.list_versions = lambda t: ["1.21.4", "1.21.3", "1.20.6"]
providers.resolve = lambda t, v: {"url": "https://example.invalid/x.jar", "kind": "jar", "build": "1", "hash": ("sha256", "")}
providers.java_required = lambda v: 21


def wait_for(cond, secs=10):
    end = time.time() + secs
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.05)
    return False


class VersionChangeTest(unittest.TestCase):
    def setUp(self):
        for s in list_servers():
            remove_server(s["id"])
        shutil.rmtree(SERVERS_DIR, ignore_errors=True)
        shutil.rmtree(BACKUPS_DIR, ignore_errors=True)
        ensure_dirs()
        self.m = Manager()
        self.m.ensure_java = lambda major, jdk=False: "java"
        self.fail_download = False

        def fake_download(url, dest, label, expect=None):
            if self.fail_download:
                raise ManagerError("Download failed (error 500).")
            Path(dest).write_bytes(b"NEW-JAR")
        self.m._download = fake_download
        d = server_dir("bbbb2222")
        for sub in ("world", "plugins", "libraries", "versions/1.21.3", "cache", ".fabric", "plugins/.paper-remapped"):
            (d / sub).mkdir(parents=True, exist_ok=True)
        (d / "world" / "level.dat").write_bytes(b"WORLD")
        (d / "plugins" / "Essentials.jar").write_bytes(b"PLUGIN")
        (d / "plugins" / "Essentials").mkdir()
        (d / "plugins" / "Essentials" / "config.yml").write_text("keep: me")
        (d / "libraries" / "old.jar").write_bytes(b"x")
        (d / "versions" / "1.21.3" / "paper.jar").write_bytes(b"x")
        (d / "plugins" / ".paper-remapped" / "e.jar").write_bytes(b"x")
        (d / "server.jar").write_bytes(b"OLD-JAR")
        (d / "ops.json").write_text("[]")
        write_props(d / "server.properties", {"server-port": "25570", "motd": "mine"})
        save_server({"id": "bbbb2222", "name": "S", "type": "paper", "version": "1.21.3", "ram_mb": 1024, "port": 25570,
                     "eula": True, "motd": "mine", "jvm_args": "", "notes": "", "schedules": [], "installed": True, "created": 1})

    def test_upgrade_swaps_jar_removes_old_files_keeps_data(self):
        r = self.m.change_version("bbbb2222", "1.21.4")
        self.assertFalse(r["downgrade"])
        self.assertTrue(wait_for(lambda: not self.m.install_job["active"]))
        self.assertEqual(self.m.install_job["error"], "")
        d = server_dir("bbbb2222")
        self.assertEqual((d / "server.jar").read_bytes(), b"NEW-JAR")
        self.assertFalse((d / "server.jar.new").exists())
        for gone in ("libraries", "versions", "cache", ".fabric", "plugins/.paper-remapped"):
            self.assertFalse((d / gone).exists(), gone)
        self.assertEqual((d / "world" / "level.dat").read_bytes(), b"WORLD")
        self.assertEqual((d / "plugins" / "Essentials.jar").read_bytes(), b"PLUGIN")
        self.assertEqual((d / "plugins" / "Essentials" / "config.yml").read_text(), "keep: me")
        self.assertTrue((d / "ops.json").exists() and (d / "server.properties").exists())
        meta = get_server("bbbb2222")
        self.assertEqual(meta["version"], "1.21.4")
        self.assertEqual(meta["version_changed"]["from"], "1.21.3")
        self.assertEqual(len(backups.list_backups("bbbb2222")), 1)   # backup is on by default

    def test_backup_can_be_skipped_on_upgrade(self):
        self.m.change_version("bbbb2222", "1.21.4", backup=False)
        self.assertTrue(wait_for(lambda: not self.m.install_job["active"]))
        self.assertEqual(backups.list_backups("bbbb2222"), [])

    def test_downgrade_always_makes_a_backup(self):
        r = self.m.change_version("bbbb2222", "1.20.6", backup=False)
        self.assertTrue(r["downgrade"] and r["backup"])
        self.assertTrue(wait_for(lambda: not self.m.install_job["active"]))
        self.assertEqual(len(backups.list_backups("bbbb2222")), 1)
        self.assertEqual(get_server("bbbb2222")["version"], "1.20.6")

    def test_failed_download_changes_nothing(self):
        self.fail_download = True
        self.m.change_version("bbbb2222", "1.21.4")
        self.assertTrue(wait_for(lambda: not self.m.install_job["active"]))
        d = server_dir("bbbb2222")
        self.assertIn("Nothing was changed", self.m.install_job["error"])
        self.assertEqual((d / "server.jar").read_bytes(), b"OLD-JAR")
        self.assertTrue((d / "libraries" / "old.jar").exists())
        self.assertEqual(get_server("bbbb2222")["version"], "1.21.3")
        self.assertIsNotNone(get_server("bbbb2222"))

    def test_refusals(self):
        with self.assertRaises(ManagerError):
            self.m.change_version("bbbb2222", "1.21.3")       # same version
        with self.assertRaises(ManagerError):
            self.m.change_version("bbbb2222", "9.9.9")        # unknown version
        with self.assertRaises(ManagerError):
            self.m.change_version("nope", "1.21.4")
        self.m.active_id, self.m.state = "bbbb2222", "online"
        with self.assertRaises(ManagerError):
            self.m.change_version("bbbb2222", "1.21.4")       # running
        self.m.state = "offline"
        self.m.install_job["active"] = True
        with self.assertRaises(ManagerError):
            self.m.change_version("bbbb2222", "1.21.4")       # busy


if __name__ == "__main__":
    unittest.main()
