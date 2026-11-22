"""Plugin and mod checks and updates with a pretend Modrinth. Run: python -I tests/test_plugin_updates.py"""
import hashlib
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

os.environ["MCPANEL_DATA"] = tempfile.mkdtemp(prefix="mcpanel-plug-")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import plugins as pl  # noqa: E402
from backend.store import ensure_dirs, save_server, server_dir  # noqa: E402


def make_jar(path: Path, name: str, version: str, api: str = "") -> str:
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("plugin.yml", f"name: {name}\nversion: {version}\n" + (f"api-version: {api}\n" if api else ""))
    return hashlib.sha1(path.read_bytes()).hexdigest()


class FakeResp:
    def __init__(self, data: bytes):
        self.status_code, self._d = 200, data

    def iter_content(self, n):
        yield self._d

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass


class PluginUpdateTest(unittest.TestCase):
    def setUp(self):
        import shutil
        from backend.store import SERVERS_DIR
        shutil.rmtree(SERVERS_DIR, ignore_errors=True)
        ensure_dirs()
        self.d = server_dir("cccc3333") / "plugins"
        self.d.mkdir(parents=True)
        save_server({"id": "cccc3333", "name": "P", "type": "paper", "version": "1.21.4", "ram_mb": 1024, "port": 25565,
                     "eula": True, "motd": "", "jvm_args": "", "notes": "", "schedules": [], "installed": True, "created": 1})
        self.h_ess = make_jar(self.d / "Essentials.jar", "Essentials", "1.0")
        self.h_old = make_jar(self.d / "OldThing.jar.disabled", "OldThing", "2.0")
        self.h_wild = make_jar(self.d / "Wild.jar", "Wild", "1", api="1.22")
        self.h_gone = make_jar(self.d / "Gone.jar", "Gone", "3")
        (self.d / "Essentials").mkdir()
        (self.d / "Essentials" / "config.yml").write_text("keep")
        self.new_bytes = b"PK-new-essentials"
        self.new_sha = hashlib.sha1(self.new_bytes).hexdigest()
        known = {self.h_ess: {"id": "v1", "project_id": "essx", "version_number": "1.0"},
                 self.h_old: {"id": "o1", "project_id": "oldp", "version_number": "2.0"},
                 self.h_gone: {"id": "g1", "project_id": "gonep", "version_number": "3"}}
        latest = {self.h_ess: {"id": "v2", "project_id": "essx", "version_number": "1.1", "version_type": "release",
                               "files": [{"filename": "Essentials-1.1.jar", "primary": True, "url": "https://cdn.modrinth.com/e.jar",
                                          "hashes": {"sha1": self.new_sha}}], "dependencies": []},
                  self.h_old: {"id": "o1", "project_id": "oldp", "version_number": "2.0"}}

        def post(path, payload):
            if path == "/version_files":
                return {h: known[h] for h in payload["hashes"] if h in known}
            return {h: latest[h] for h in payload["hashes"] if h in latest}
        self.patches = [mock.patch.object(pl, "_post", side_effect=post),
                        mock.patch.object(pl.requests, "get", side_effect=lambda *a, **k: FakeResp(self.new_bytes)),
                        mock.patch.object(pl, "_get", return_value=[])]
        for p in self.patches:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in self.patches])

    def test_check_statuses(self):
        r = pl.check("cccc3333")
        it = r["items"]
        self.assertEqual(it["Essentials.jar"]["status"], "update")
        self.assertEqual(it["Essentials.jar"]["latest"], "1.1")
        self.assertEqual(it["OldThing.jar.disabled"]["status"], "ok")
        self.assertEqual(it["Gone.jar"]["status"], "no_build")
        self.assertEqual(it["Wild.jar"]["status"], "no_build")          # not on Modrinth, but made for a newer Minecraft
        self.assertIn("1.22", it["Wild.jar"]["note"])
        self.assertEqual(r["counts"]["update"], 1)

    def test_update_replaces_jar_keeps_config_and_removes_old(self):
        r = pl.update("cccc3333", "Essentials.jar")
        self.assertTrue(r["changed"])
        self.assertFalse((self.d / "Essentials.jar").exists())
        self.assertEqual((self.d / "Essentials-1.1.jar").read_bytes(), self.new_bytes)
        self.assertEqual((self.d / "Essentials" / "config.yml").read_text(), "keep")
        self.assertFalse(list(self.d.glob("*.part")))

    def test_update_all_and_unchanged(self):
        r = pl.update_all("cccc3333")
        self.assertEqual([x["file"] for x in r["updated"]], ["Essentials.jar"])
        self.assertEqual(r["failed"], [])
        self.assertFalse(pl.update("cccc3333", "OldThing.jar.disabled")["changed"])

    def test_bad_checksum_keeps_old_file(self):
        with mock.patch.object(pl.requests, "get", side_effect=lambda *a, **k: FakeResp(b"tampered")):
            with self.assertRaises(pl.PluginError):
                pl.update("cccc3333", "Essentials.jar")
        self.assertTrue((self.d / "Essentials.jar").exists())
        self.assertFalse(list(self.d.glob("*.part")))

    def test_no_build_and_unknown_cannot_update(self):
        with self.assertRaises(pl.PluginError):
            pl.update("cccc3333", "Gone.jar")
        with self.assertRaises(pl.PluginError):
            pl.update("cccc3333", "Wild.jar")

    def test_project_page_and_specific_version_with_replace(self):
        pr = {"id": "essx", "slug": "essx", "title": "Essentials", "description": "x", "body": "# Hi", "icon_url": "https://evil.example/i.png",
              "downloads": 5, "followers": 1, "categories": ["utility"], "license": {"name": "GPL"},
              "gallery": [{"url": "https://cdn.modrinth.com/g.png", "title": "a"}, {"url": "https://evil.example/g.png"}],
              "source_url": "https://github.com/x/y", "issues_url": "javascript:alert(1)"}
        vers = [{"id": "v2", "version_number": "1.1", "game_versions": ["1.21.4"], "loaders": ["paper"], "version_type": "release",
                 "files": [{"filename": "E-1.1.jar", "primary": True}]},
                {"id": "v0", "version_number": "0.9", "game_versions": ["1.19"], "loaders": ["paper"], "version_type": "beta",
                 "files": [{"filename": "E-0.9.jar", "primary": True}]}]
        with mock.patch.object(pl, "_get", side_effect=lambda path, **k: pr if path == "/project/essx" else vers):
            page = pl.project_page("cccc3333", "essx")
        self.assertEqual(page["icon"], "")                                   # not from Modrinth's CDN: dropped
        self.assertEqual([g["url"] for g in page["gallery"]], ["https://cdn.modrinth.com/g.png"])
        self.assertEqual(list(page["links"]), ["source"])                    # javascript: link dropped
        self.assertEqual([(v["number"], v["compatible"]) for v in page["versions"]], [("1.1", True), ("0.9", False)])
        # install an older version over the installed one: old jar goes, config stays
        old_ver = {"id": "v0", "project_id": "essx", "version_number": "0.9", "game_versions": ["1.21.4"], "loaders": ["paper"],
                   "files": [{"filename": "E-0.9.jar", "primary": True, "url": "https://cdn.modrinth.com/o.jar",
                              "hashes": {"sha1": self.new_sha}}], "dependencies": []}
        with mock.patch.object(pl, "_get", return_value=old_ver):
            r = pl.install("cccc3333", "essx", "v0", replace_file="Essentials.jar")
        self.assertEqual(r["file"], "E-0.9.jar")
        self.assertFalse((self.d / "Essentials.jar").exists())
        self.assertTrue((self.d / "E-0.9.jar").exists())
        self.assertEqual((self.d / "Essentials" / "config.yml").read_text(), "keep")

    def test_incompatible_version_needs_permission(self):
        ver = {"id": "v9", "project_id": "essx", "version_number": "9", "game_versions": ["1.8"], "loaders": ["paper"],
               "files": [{"filename": "E-9.jar", "primary": True, "url": "https://cdn.modrinth.com/o.jar", "hashes": {"sha1": self.new_sha}}]}
        with mock.patch.object(pl, "_get", return_value=ver):
            with self.assertRaises(pl.PluginError):
                pl.install("cccc3333", "essx", "v9")
            self.assertEqual(pl.install("cccc3333", "essx", "v9", allow_other_version=True)["file"], "E-9.jar")
        with mock.patch.object(pl, "_get", return_value={**ver, "project_id": "other"}):
            with self.assertRaises(pl.PluginError):
                pl.install("cccc3333", "essx", "v9", allow_other_version=True)


if __name__ == "__main__":
    unittest.main()
