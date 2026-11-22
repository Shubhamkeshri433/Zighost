"""Backups: folder choice, zip contents, info file, verify, restore kinds, clean-up rules, import. No internet.
Run: python -I tests/test_backups_adv.py"""
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TMP = tempfile.mkdtemp(prefix="mcpanel-bk-")
os.environ["MCPANEL_DATA"] = TMP
sys.path.insert(0, str(ROOT))

from backend import backups  # noqa: E402
from backend.manager import Manager, ManagerError  # noqa: E402
from backend.props import write_props  # noqa: E402
from backend.store import (BACKUPS_DIR, SERVERS_DIR, backup_dir, ensure_dirs, get_server, list_servers, remove_server,  # noqa: E402
                           save_server, server_dir, update_settings, update_server)

SID = "dddd4444"


def wait_for(cond, secs=10):
    end = time.time() + secs
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.05)
    return False


class BackupTest(unittest.TestCase):
    def setUp(self):
        for s in list_servers():
            remove_server(s["id"])
        shutil.rmtree(SERVERS_DIR, ignore_errors=True)
        shutil.rmtree(BACKUPS_DIR, ignore_errors=True)
        update_settings({"backup_dir": ""})
        ensure_dirs()
        self.extra = Path(tempfile.mkdtemp(prefix="mcpanel-bk-extra-"))
        d = server_dir(SID)
        for sub in ("world/region", "world_nether", "plugins/Essentials", "logs", "libraries"):
            (d / sub).mkdir(parents=True, exist_ok=True)
        (d / "world" / "level.dat").write_bytes(b"WORLD")
        (d / "world" / "region" / "r.0.0.mca").write_bytes(b"R")
        (d / "world_nether" / "level.dat").write_bytes(b"NETHER")
        (d / "plugins" / "Essentials.jar").write_bytes(b"PLUGIN")
        (d / "plugins" / "Essentials" / "config.yml").write_text("a: 1")
        (d / "logs" / "latest.log").write_text("log")
        (d / "libraries" / "x.jar").write_bytes(b"L")
        (d / "server.jar").write_bytes(b"JAR")
        (d / "ops.json").write_text("[]")
        write_props(d / "server.properties", {"level-name": "world", "server-port": "25565"})
        save_server({"id": SID, "name": "Home", "type": "paper", "version": "1.21.4", "ram_mb": 1024, "port": 25565,
                     "eula": True, "motd": "", "jvm_args": "", "notes": "", "schedules": [], "installed": True, "created": 1})

    def names(self, b):
        with zipfile.ZipFile(backup_dir(SID) / b["name"]) as z:
            return set(z.namelist())

    def test_kinds_and_info_file(self):
        std = backups.create_backup(SID, "manual")
        n = self.names(std)
        self.assertIn("world/level.dat", n); self.assertIn("plugins/Essentials/config.yml", n)
        self.assertNotIn("server.jar", n); self.assertNotIn("logs/latest.log", n); self.assertNotIn("libraries/x.jar", n)
        self.assertEqual((std["scope"], std["version"], std["type"], std["server"]), ("standard", "1.21.4", "paper", "Home"))
        time.sleep(1.1)
        w = backups.create_backup(SID, "manual", "world")
        nw = self.names(w)
        self.assertIn("world/level.dat", nw); self.assertIn("world_nether/level.dat", nw)
        self.assertFalse([x for x in nw if x.startswith("plugins/")])
        time.sleep(1.1)
        f = backups.create_backup(SID, "manual", "full")
        self.assertIn("server.jar", self.names(f)); self.assertIn("libraries/x.jar", self.names(f))
        self.assertTrue(backups.verify(SID, f["name"])["ok"])
        self.assertFalse(any(b["damaged"] for b in backups.list_backups(SID)))
        self.assertFalse(backups.progress(SID)["active"])

    def test_default_scope_comes_from_the_server(self):
        update_server(SID, {"backup_scope": "world"})
        b = backups.create_backup(SID)
        self.assertEqual(b["scope"], "world")

    def test_folder_choice(self):
        shared = self.extra / "all"
        update_settings({"backup_dir": str(shared)})
        b = backups.create_backup(SID)
        self.assertTrue((shared / SID / b["name"]).exists())
        own = self.extra / "mine"
        update_server(SID, {"backup_dir": str(own)})
        time.sleep(1.1)
        b2 = backups.create_backup(SID)
        self.assertTrue((own / b2["name"]).exists())
        self.assertEqual(backup_dir(SID), own)
        update_server(SID, {"backup_dir": ""})
        self.assertEqual(backup_dir(SID), shared / SID)
        update_settings({"backup_dir": ""})
        self.assertEqual(backup_dir(SID), BACKUPS_DIR / SID)

    def test_folder_checks(self):
        ok = backups.check_folder(str(self.extra / "new" / "sub"))
        self.assertTrue(Path(ok["path"]).is_dir() and ok["free"] > 0)
        for bad in ("", "relative/path", str(server_dir(SID)), str(server_dir(SID) / "world")):
            with self.assertRaises(backups.BackupError, msg=bad):
                backups.check_folder(bad)
        f = self.extra / "afile"; f.write_text("x")
        with self.assertRaises(backups.BackupError):
            backups.check_folder(str(f / "inside"))

    def test_move_backups(self):
        a = backups.create_backup(SID)
        new = self.extra / "moved"
        old = backup_dir(SID)
        update_server(SID, {"backup_dir": str(new)})
        self.assertEqual(backups.move_backups(old, new), 1)
        self.assertTrue((new / a["name"]).exists() and not (old / a["name"]).exists())
        self.assertEqual(backups.move_backups(new, new), 0)
        (old.mkdir(parents=True, exist_ok=True))
        shutil.copy2(new / a["name"], old / a["name"])
        with self.assertRaises(backups.BackupError):
            backups.move_backups(old, new)                      # same name already there: nothing is overwritten

    def test_restore_kinds(self):
        b = backups.create_backup(SID, "manual")
        d = server_dir(SID)
        (d / "world" / "level.dat").write_bytes(b"CHANGED")
        (d / "plugins" / "Essentials" / "config.yml").write_text("a: 2")
        (d / "plugins" / "New.jar").write_bytes(b"N")
        backups.restore_backup(SID, b["name"], "world", safety=False)
        self.assertEqual((d / "world" / "level.dat").read_bytes(), b"WORLD")
        self.assertEqual((d / "plugins" / "Essentials" / "config.yml").read_text(), "a: 2")   # config untouched
        (d / "world" / "level.dat").write_bytes(b"CHANGED2")
        backups.restore_backup(SID, b["name"], "config", safety=False)
        self.assertEqual((d / "plugins" / "Essentials" / "config.yml").read_text(), "a: 1")
        self.assertFalse((d / "plugins" / "New.jar").exists())
        self.assertEqual((d / "world" / "level.dat").read_bytes(), b"CHANGED2")               # world untouched
        self.assertEqual((d / "server.jar").read_bytes(), b"JAR")
        backups.restore_backup(SID, b["name"], "all", safety=False)
        self.assertEqual((d / "world" / "level.dat").read_bytes(), b"WORLD")
        self.assertFalse((d / backups.MANIFEST).exists())                                      # info file is not copied in
        self.assertEqual(len([x for x in backups.list_backups(SID) if "before-restore" in x["name"]]), 0)

    def test_safety_backup_by_default(self):
        b = backups.create_backup(SID, "manual")
        time.sleep(1.1)
        backups.restore_backup(SID, b["name"])
        self.assertEqual(len([x for x in backups.list_backups(SID) if "before-restore" in x["name"]]), 1)

    def test_world_only_backup_cannot_restore_config(self):
        b = backups.create_backup(SID, "manual", "world")
        with self.assertRaises(backups.BackupError):
            backups.restore_backup(SID, b["name"], "config", safety=False)
        std = backups.create_backup(SID, "x", "standard")
        self.assertTrue(std)

    def test_unsafe_zip_is_refused_before_anything_changes(self):
        evil = backup_dir(SID); evil.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(evil / "20240101-000000_evil.zip", "w") as z:
            z.writestr("../escape.txt", "x")
        before = (server_dir(SID) / "ops.json").read_text()
        with self.assertRaises(backups.BackupError):
            backups.restore_backup(SID, "20240101-000000_evil.zip")
        self.assertEqual((server_dir(SID) / "ops.json").read_text(), before)
        self.assertFalse((server_dir(SID).parent / "escape.txt").exists())
        with self.assertRaises(backups.BackupError):
            backups.safe_name("../x.zip")

    def test_clean_up_rules_keep_newest(self):
        d = backup_dir(SID); d.mkdir(parents=True, exist_ok=True)
        now = time.time()
        for i in range(5):
            p = d / f"2024010{i + 1}-000000_manual.zip"
            with zipfile.ZipFile(p, "w") as z:
                z.writestr("a", "x" * 1000)
            os.utime(p, (now - (5 - i) * 86400 * 10, now - (5 - i) * 86400 * 10))
        update_server(SID, {"backup_rules": {"count": 2, "days": 0, "gb": 0}})
        self.assertEqual(len(backups.apply_rules(SID)), 3)
        update_server(SID, {"backup_rules": {"count": 0, "days": 1, "gb": 0}})
        self.assertEqual(len(backups.apply_rules(SID)), 1)      # the oldest left is old; the newest is never removed
        self.assertEqual(len(list(d.glob("*.zip"))), 1)
        update_server(SID, {"backup_rules": {"count": 0, "days": 0, "gb": 0}})
        self.assertEqual(backups.apply_rules(SID), [])

    def test_rules_run_after_a_new_backup_but_not_after_safety_ones(self):
        update_server(SID, {"backup_rules": {"count": 1, "days": 0, "gb": 0}})
        backups.create_backup(SID, "manual"); time.sleep(1.1)
        b2 = backups.create_backup(SID, "manual")
        self.assertEqual([b["name"] for b in backups.list_backups(SID)], [b2["name"]])
        time.sleep(1.1)
        backups.create_backup(SID, "before-restore")
        self.assertEqual(len(backups.list_backups(SID)), 2)

    def test_import(self):
        good = self.extra / "mine.zip"
        with zipfile.ZipFile(good, "w") as z:
            z.writestr("world/level.dat", "W")
        info = backups.import_backup(SID, str(good))
        self.assertTrue(info["name"].endswith("_imported.zip"))
        self.assertTrue(backups.NAME_RE.match(info["name"]))
        for bad in ("relative.zip", str(self.extra / "missing.zip"), str(self.extra)):
            with self.assertRaises(backups.BackupError):
                backups.import_backup(SID, bad)
        notzip = self.extra / "no.zip"; notzip.write_text("hello")
        with self.assertRaises(backups.BackupError):
            backups.import_backup(SID, str(notzip))
        evil = self.extra / "evil.zip"
        with zipfile.ZipFile(evil, "w") as z:
            z.writestr("../../x", "x")
        with self.assertRaises(backups.BackupError):
            backups.import_backup(SID, str(evil))

    def test_damaged_zip_is_flagged_and_purge_leaves_other_files(self):
        d = backup_dir(SID); d.mkdir(parents=True, exist_ok=True)
        (d / "20240101-000000_manual.zip").write_bytes(b"not a zip")
        (d / "my-holiday.zip").write_bytes(b"keep me")
        (d / "notes.txt").write_text("keep me too")
        self.assertTrue([b for b in backups.list_backups(SID) if b["damaged"]])
        self.assertFalse(backups.verify(SID, "20240101-000000_manual.zip")["ok"])
        backups.purge(SID)
        self.assertFalse((d / "20240101-000000_manual.zip").exists())
        self.assertTrue((d / "my-holiday.zip").exists() and (d / "notes.txt").exists())

    def test_restore_as_new_server(self):
        b = backups.create_backup(SID, "manual")
        d = server_dir(SID)
        (d / "world" / "level.dat").write_bytes(b"NEWER-WORLD")
        m = Manager()
        meta = m.duplicate_server(SID, "From backup", (b["name"], "all"))
        self.assertTrue(wait_for(lambda: not m.install_job["active"]))
        self.assertEqual(m.install_job["error"], "")
        nd = server_dir(meta["id"])
        self.assertEqual((nd / "world" / "level.dat").read_bytes(), b"WORLD")          # backup content
        self.assertEqual((d / "world" / "level.dat").read_bytes(), b"NEWER-WORLD")     # original untouched
        self.assertTrue((nd / "server.jar").exists())
        self.assertNotEqual(get_server(meta["id"])["port"], 25565)
        self.assertEqual(get_server(meta["id"])["backup_dir"], "")
        with self.assertRaises(ManagerError):
            m.duplicate_server(SID, "x", ("20990101-000000_nope.zip", "all"))


if __name__ == "__main__":
    unittest.main()
