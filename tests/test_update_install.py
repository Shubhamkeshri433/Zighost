"""Update now: download, checksum, apply, cleanup."""
import hashlib
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

TMP = tempfile.mkdtemp()
os.environ.setdefault("ZIGHOST_DATA", TMP)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from starlette.testclient import TestClient

from backend import app as appmod, brand, updates

INSTALLER = b"MZ" + b"i" * 5000
SHA = hashlib.sha256(INSTALLER).hexdigest()
NAME = "Zighost-Setup-9.9.9.exe"
BASE = f"https://github.com/{brand.REPO}/releases/download/v9.9.9/"
DATA = {"latest": "9.9.9", "url": "https://github.com/x", "notes": "", "none": False,
        "file": BASE + NAME, "file_name": NAME, "sums": BASE + "SHA256SUMS.txt"}


class Raw:
    def __init__(self, data): self.data = data
    def read(self, n, decode_content=True): return self.data[:n]


class Resp:
    def __init__(self, data=b"", status=200):
        self.data, self.status_code, self.raw = data, status, Raw(data)
        self.headers = {"content-length": str(len(data))}
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def iter_content(self, n): yield self.data


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.patches = [mock.patch.object(updates, "UPDATE_DIR", self.dir / "updates"),
                        mock.patch.object(updates, "PENDING", self.dir / "pending.json"),
                        mock.patch.dict(updates._cache, {"at": time.time(), "data": dict(DATA)})]
        for p in self.patches: p.start()
        updates._set(state="idle", progress=0, error="", version="9.9.9")
        updates._want.clear()

    def tearDown(self):
        for p in self.patches: p.stop()

    def get_side(self, sums_text, file_data, sums_status=200):
        def get(url, **kw):
            return Resp(sums_text.encode(), sums_status) if url.endswith("SHA256SUMS.txt") else Resp(file_data)
        return mock.patch.object(updates.requests, "get", side_effect=get)


class Release(Base):
    def test_only_this_repos_installer_is_accepted(self):
        self.assertTrue(updates._release_ok(DATA))
        for bad in ({**DATA, "file": "https://evil.example/" + NAME}, {**DATA, "sums": "http://github.com/x"},
                    {**DATA, "file_name": "..\\evil.exe"}, {**DATA, "file_name": "portable.zip"}, {**DATA, "file_name": "tool.exe"},
                    {**DATA, "latest": "1.0.1"}):          # tag says 1.0.1 but the installer inside is 9.9.9: mis-tagged release
            self.assertFalse(updates._release_ok(bad), bad)

    def test_portable_and_source_copies_do_not_self_update(self):
        self.assertFalse(updates.can_install())


class Download(Base):
    def run_dl(self, sums, data):
        with self.get_side(sums, data):
            updates._download_and_verify(dict(DATA))
        return updates.job()

    def test_good_installer_becomes_ready(self):
        st = self.run_dl(f"{SHA}  {NAME}\n", INSTALLER)
        self.assertEqual(st["state"], "ready"); self.assertTrue((updates.UPDATE_DIR / NAME).exists())

    def test_modified_installer_is_rejected_and_deleted(self):
        st = self.run_dl(f"{SHA}  {NAME}\n", INSTALLER + b"evil")
        self.assertEqual(st["state"], "error"); self.assertIn("checksum", st["error"])
        self.assertEqual(list(updates.UPDATE_DIR.glob("*")), [])

    def test_release_without_a_checksum_for_the_installer_is_refused(self):
        st = self.run_dl(f"{SHA}  other.exe\n", INSTALLER)
        self.assertEqual(st["state"], "error"); self.assertEqual(list(updates.UPDATE_DIR.glob("*.exe")), [])

    def test_missing_checksum_file_is_refused(self):
        with self.get_side("", INSTALLER, sums_status=404):
            updates._download_and_verify(dict(DATA))
        self.assertEqual(updates.job()["state"], "error")

    def test_offline(self):
        with mock.patch.object(updates.requests, "get", side_effect=updates.requests.ConnectionError()):
            updates._download_and_verify(dict(DATA))
        self.assertEqual(updates.job()["state"], "error")


class Apply(Base):
    def ready(self):
        with self.get_side(f"{SHA}  {NAME}\n", INSTALLER):
            updates._download_and_verify(dict(DATA))
        self.assertEqual(updates.job()["state"], "ready")

    def test_not_ready_is_refused(self):
        with self.assertRaises(updates.UpdateError):
            updates.install_apply()

    def test_apply_runs_installer_waits_for_exit_and_closes_app(self):
        self.ready()
        exits = []
        with mock.patch.object(updates.subprocess, "Popen") as popen, mock.patch.object(updates, "request_exit", lambda: exits.append(1)):
            st = updates.install_apply(); time.sleep(0.1)
        self.assertEqual(st["state"], "installing")
        args = popen.call_args[0][0]
        self.assertEqual(args[:2], ["cmd.exe", "/c"])
        script = Path(args[2]).read_text()
        self.assertIn(f'PID eq {os.getpid()}', script)                 # waits for this app to exit first
        self.assertIn("/VERYSILENT", script); self.assertIn("/UPDATING=1", script)
        self.assertIn(str(updates.UPDATE_DIR / NAME), script)
        self.assertEqual(json.loads(updates.PENDING.read_text())["to"], "9.9.9")
        self.assertEqual(exits, [1])

    def test_installer_changed_after_download_is_not_run(self):
        self.ready()
        (updates.UPDATE_DIR / NAME).write_bytes(INSTALLER + b"tampered")
        with mock.patch.object(updates.subprocess, "Popen") as popen:
            with self.assertRaises(updates.UpdateError):
                updates.install_apply()
        popen.assert_not_called()
        self.assertEqual(updates.job()["state"], "error")


class Cleanup(Base):
    def test_leftovers_removed_and_update_reported_once(self):
        updates.UPDATE_DIR.mkdir(parents=True); (updates.UPDATE_DIR / NAME).write_bytes(b"x")
        updates.PENDING.write_text(json.dumps({"to": brand.VERSION}))
        self.assertEqual(updates.startup_cleanup(), brand.VERSION)
        self.assertEqual(list(updates.UPDATE_DIR.glob("*")), []); self.assertFalse(updates.PENDING.exists())
        self.assertEqual(updates.startup_cleanup(), "")

    def test_failed_update_is_not_reported_as_done(self):
        updates.PENDING.write_text(json.dumps({"to": "99.0.0"}))
        self.assertEqual(updates.startup_cleanup(), "")


class Api(Base):
    def setUp(self):
        super().setUp()
        self.c = TestClient(appmod.app, base_url="http://127.0.0.1")
        self.h = {brand.API_HEADER: "1"}

    def test_cannot_start_when_this_copy_cannot_self_update(self):
        r = self.c.post("/api/update/start", json={}, headers=self.h)
        self.assertEqual(r.status_code, 400)

    def test_apply_needs_a_header(self):
        self.assertEqual(self.c.post("/api/update/apply", json={}).status_code, 403)

    def test_running_server_needs_an_explicit_yes(self):
        updates._set(state="ready")
        with mock.patch.object(appmod.manager, "busy", return_value=True), mock.patch.object(updates, "install_apply") as ap:
            r = self.c.post("/api/update/apply", json={}, headers=self.h)
            self.assertEqual(r.status_code, 400); ap.assert_not_called()
            ap.return_value = {"state": "installing"}
            r = self.c.post("/api/update/apply", json={"stop_servers": True}, headers=self.h)
            self.assertEqual(r.status_code, 200)


if __name__ == "__main__":
    unittest.main()
