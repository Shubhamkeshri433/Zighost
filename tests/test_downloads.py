"""Downloads are checked against the publisher's checksum before use."""
import hashlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TMP = tempfile.mkdtemp()
os.environ.setdefault("ZIGHOST_DATA", TMP)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend import java_rt, manager, playit, providers, verify


class Resp:
    def __init__(self, data=b"", status=200, js=None):
        self.data, self.status_code, self._js, self.headers = data, status, js, {"content-length": str(len(data))}

    def __enter__(self): return self
    def __exit__(self, *a): return False
    def iter_content(self, n): yield self.data
    def json(self): return self._js
    def raise_for_status(self): pass


GOOD = b"x" * 5000
SHA = hashlib.sha256(GOOD).hexdigest()


class Verify(unittest.TestCase):
    def test_match_and_mismatch(self):
        f = Path(TMP) / "a.bin"; f.write_bytes(GOOD)
        verify.check(f, ("sha256", SHA), "x")
        self.assertTrue(f.exists())
        with self.assertRaises(verify.VerifyError):
            verify.check(f, ("sha256", "0" * 64), "x")
        self.assertFalse(f.exists(), "a file that does not match is deleted")

    def test_missing_expected_is_an_error(self):
        f = Path(TMP) / "b.bin"; f.write_bytes(GOOD)
        with self.assertRaises(verify.VerifyError):
            verify.check(f, None, "x")

    def test_digest_and_sums_parsing(self):
        self.assertEqual(verify.split_digest("sha256:ABC123"), ("sha256", "abc123"))
        self.assertIsNone(verify.split_digest("md5:abc"))
        self.assertIsNone(verify.split_digest(""))
        self.assertEqual(verify.parse_sums(f"{SHA}  Zighost-Setup-1.exe\n")["Zighost-Setup-1.exe"], SHA)


class Server(unittest.TestCase):
    def setUp(self):
        self.m = manager.Manager.__new__(manager.Manager)
        self.m._progress = lambda *a, **k: None
        self.lines = []
        self.m.log = self.lines.append

    def run_dl(self, data, expect):
        dest = Path(tempfile.mkdtemp()) / "server.jar"
        with mock.patch.object(manager.requests, "get", return_value=Resp(data)):
            self.m._download("https://x/server.jar", dest, "Downloading server", expect=expect)
        return dest

    def test_good_download_is_kept(self):
        d = self.run_dl(GOOD, ("sha256", SHA))
        self.assertTrue(d.exists())
        self.assertTrue(any("matches" in l for l in self.lines))

    def test_modified_download_is_rejected(self):
        dest = Path(tempfile.mkdtemp()) / "server.jar"
        with mock.patch.object(manager.requests, "get", return_value=Resp(GOOD + b"evil")):
            with self.assertRaises(manager.ManagerError):
                self.m._download("https://x/server.jar", dest, "Downloading server", expect=("sha256", SHA))
        self.assertFalse(dest.exists()); self.assertFalse(dest.with_suffix(".jar.part").exists())

    def test_no_published_checksum_is_said_out_loud(self):
        self.run_dl(GOOD, None)
        self.assertTrue(any("could not be verified" in l for l in self.lines))


class Java(unittest.TestCase):
    API = [{"binary": {"package": {"link": "https://github.com/adoptium/x.zip", "checksum": SHA, "name": "x.zip"}}}]

    def test_package_and_checksum_from_api(self):
        with mock.patch.object(java_rt.requests, "get", return_value=Resp(js=self.API)):
            link, exp = java_rt._temurin_package(21, "windows", "x64", "jre")
        self.assertEqual(exp, ("sha256", SHA)); self.assertTrue(link.startswith("https://"))

    def test_no_checksum_means_no_download(self):
        bad = [{"binary": {"package": {"link": "https://github.com/x.zip"}}}]
        with mock.patch.object(java_rt.requests, "get", return_value=Resp(js=bad)):
            with self.assertRaises(java_rt.JavaError):
                java_rt._temurin_package(21, "windows", "x64", "jre")

    def test_corrupt_java_is_rejected_before_unpacking(self):
        runtime = Path(tempfile.mkdtemp())
        with mock.patch.object(java_rt, "RUNTIME_DIR", runtime), \
             mock.patch.object(java_rt, "_temurin_package", return_value=("https://x/j.zip", ("sha256", "0" * 64))), \
             mock.patch.object(java_rt.requests, "get", return_value=Resp(GOOD)), \
             mock.patch.object(java_rt.zipfile, "ZipFile") as z:
            with self.assertRaises(java_rt.JavaError):
                java_rt.install_java(21, False, lambda *a: None)
            z.assert_not_called()
        self.assertEqual(list(runtime.glob("*.download")), [])


class Providers(unittest.TestCase):
    def test_vanilla_and_paper_carry_hashes(self):
        with mock.patch.object(providers, "list_versions", return_value=["1.21"]), \
             mock.patch.object(providers, "_mojang_releases", return_value=[{"id": "1.21", "url": "u"}]), \
             mock.patch.object(providers, "http_get_json", return_value={"downloads": {"server": {"url": "https://m/s.jar", "sha1": "AB12"}}}):
            self.assertEqual(providers.resolve("vanilla", "1.21")["hash"], ("sha1", "ab12"))
        builds = [{"id": 5, "channel": "STABLE", "downloads": {"server:default": {"url": "https://p/s.jar", "checksums": {"sha256": SHA.upper()}}}}]
        with mock.patch.object(providers, "list_versions", return_value=["1.21"]), mock.patch.object(providers, "http_get_json", return_value=builds):
            self.assertEqual(providers.resolve("paper", "1.21")["hash"], ("sha256", SHA))


class Playit(unittest.TestCase):
    BIG = b"p" * 200_000

    def _run(self, digest, data):
        asset = {"name": "playit-windows-x86_64-signed.exe", "browser_download_url": "https://github.com/p.exe"}
        if digest is not None:
            asset["digest"] = digest
        rels = [{"tag_name": "v0.16.0", "draft": False, "prerelease": False, "assets": [asset]}]
        d = Path(tempfile.mkdtemp())
        agent = playit.Playit()
        notes = []
        agent.note = notes.append
        with mock.patch.object(playit, "PLAYIT_DIR", d), mock.patch.object(playit, "BIN_NAME", "playit.exe"), \
             mock.patch.object(playit.requests, "get", side_effect=[Resp(js=rels), Resp(data)]), \
             mock.patch.object(playit, "IS_WIN", True), \
             mock.patch.object(playit, "_pick_asset", return_value=asset):
            try:
                agent._download()
            except playit.PlayitError as e:
                return d, notes, e
        return d, notes, None

    def test_matching_digest_installs(self):
        d, notes, err = self._run("sha256:" + hashlib.sha256(self.BIG).hexdigest(), self.BIG)
        self.assertIsNone(err); self.assertTrue((d / "playit.exe").exists())

    def test_modified_helper_is_rejected(self):
        d, notes, err = self._run("sha256:" + hashlib.sha256(self.BIG).hexdigest(), self.BIG + b"!")
        self.assertIsNotNone(err); self.assertFalse((d / "playit.exe").exists()); self.assertEqual(list(d.glob("*.part")), [])

    def test_no_digest_is_said_out_loud(self):
        d, notes, err = self._run(None, self.BIG)
        self.assertIsNone(err); self.assertTrue(any("could not be verified" in n for n in notes))


if __name__ == "__main__":
    unittest.main()
