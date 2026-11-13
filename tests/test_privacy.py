import os, sys, tempfile, unittest
from pathlib import Path
from unittest import mock

TMP = tempfile.mkdtemp()
os.environ["ZIGHOST_DATA"] = TMP
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend import brand, consent, support


class Consent(unittest.TestCase):
    def setUp(self):
        (Path(TMP) / "consent.json").unlink(missing_ok=True)

    def test_default_not_accepted(self):
        c = consent.get()
        self.assertFalse(c["accepted"]); self.assertFalse(c["heads"]); self.assertFalse(consent.heads_allowed())

    def test_accept_and_heads(self):
        consent.accept(heads=False)
        self.assertTrue(consent.get()["accepted"]); self.assertFalse(consent.heads_allowed())
        consent.set_heads(True)
        self.assertTrue(consent.heads_allowed())
        consent.set_heads(False)

    def test_new_policy_version_asks_again(self):
        consent.accept()
        with mock.patch.object(brand, "POLICY_VERSION", 2):
            self.assertFalse(consent.get()["accepted"])


class Report(unittest.TestCase):
    def test_scrub(self):
        home = str(Path.home())
        t = support._scrub(f"open {home}/x https://discord.com/api/webhooks/123/abcDEF and secret=ABCDEFGHIJKLMNOP1234")
        self.assertNotIn(home, t); self.assertNotIn("abcDEF", t); self.assertNotIn("ABCDEFGHIJKLMNOP1234", t)

    def test_report_text(self):
        t = support.report()
        self.assertIn(brand.VERSION, t); self.assertIn("last log lines", t)


class Api(unittest.TestCase):
    def setUp(self):
        from starlette.testclient import TestClient
        from backend.app import app
        self.c = TestClient(app, base_url="http://127.0.0.1", headers={"X-MCPanel": "1"})
        (Path(TMP) / "consent.json").unlink(missing_ok=True)

    def test_flow_and_heads_gate(self):
        self.assertFalse(self.c.get("/api/consent").json()["accepted"])
        self.assertEqual(self.c.put("/api/consent", json={"heads": True}).status_code, 400)
        self.assertEqual(self.c.get("/api/head/Steve").status_code, 404)
        r = self.c.put("/api/consent", json={"accept": True, "heads": False}).json()
        self.assertTrue(r["accepted"]); self.assertFalse(r["heads"])
        with mock.patch("backend.heads.get", return_value=b"\x89PNG\r\n\x1a\nxx") as g:
            self.assertEqual(self.c.get("/api/head/Steve").status_code, 404); g.assert_not_called()
            self.c.put("/api/consent", json={"heads": True})
            self.assertEqual(self.c.get("/api/head/Steve").status_code, 200)

    def test_support_and_components(self):
        self.assertIn("text", self.c.get("/api/support/report").json())
        st = self.c.get("/api/components").json()
        self.assertEqual(set(st), {"running", "java", "playit"})
        self.assertEqual(self.c.post("/api/open-folder", json={"which": "logs"}).status_code in (200, 400), True)

    def test_brand_public(self):
        self.assertEqual(brand.public()["supportEmail"], "zighost.support@gmail.com")


class Prepare(unittest.TestCase):
    def test_prepare_downloads_missing(self):
        calls = []
        comp = support.Components()
        with mock.patch.object(support.java_rt, "find_java", return_value=None), \
             mock.patch.object(support.java_rt, "install_java", side_effect=lambda m, j, p: (p("x", 50), calls.append("java"))), \
             mock.patch.object(support.playit, "binary_exists", return_value=False), \
             mock.patch.object(support.playit, "fetch_binary", side_effect=lambda: calls.append("playit")):
            comp._run()
        self.assertEqual(calls, ["java", "playit"])
        self.assertEqual((comp.java["state"], comp.playit["state"]), ("ready", "ready"))

    def test_prepare_error_is_reported(self):
        comp = support.Components()
        with mock.patch.object(support.java_rt, "find_java", return_value=None), \
             mock.patch.object(support.java_rt, "install_java", side_effect=support.java_rt.JavaError("no internet")), \
             mock.patch.object(support.playit, "binary_exists", return_value=True):
            comp._run()
        self.assertEqual(comp.java["state"], "error"); self.assertEqual(comp.playit["state"], "ready")


if __name__ == "__main__":
    unittest.main()
