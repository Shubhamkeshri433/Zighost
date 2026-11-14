import os, sys, tempfile, unittest
from pathlib import Path
from unittest import mock

TMP = tempfile.mkdtemp()
os.environ["ZIGHOST_DATA"] = TMP
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend import brand, consent, stats, updates


class Resp:
    def __init__(self, status=200, data=None):
        self.status_code, self._d = status, data or {}
    def json(self): return self._d
    def raise_for_status(self):
        if self.status_code >= 400: raise RuntimeError(self.status_code)


def release(tag="v0.2.0"):
    return {"tag_name": tag, "html_url": "https://github.com/x/releases/tag/" + tag, "body": "notes",
            "assets": [{"name": f"Zighost-{tag.lstrip('v')}-portable.zip", "browser_download_url": "https://dl/portable.zip"},
                       {"name": f"Zighost-Setup-{tag.lstrip('v')}.exe", "browser_download_url": "https://dl/setup.exe"}]}


class Base(unittest.TestCase):
    def setUp(self):
        (Path(TMP) / "consent.json").unlink(missing_ok=True)
        updates._cache.update(at=0.0, data=None)
        consent.accept(heads=False, updates=True, stats=False)


class Defaults(Base):
    def test_accepting_policy_covers_update_check_and_daily_message(self):
        (Path(TMP) / "consent.json").unlink(missing_ok=True)
        consent.accept()
        c = consent.get()
        self.assertTrue(c["updates"]); self.assertTrue(c["stats"])
        self.assertEqual(len(consent.install_id()), 36); self.assertEqual(consent.install_id(), consent.get()["usage_id"])

    def test_no_id_before_accepting(self):
        (Path(TMP) / "consent.json").unlink(missing_ok=True)
        self.assertEqual(consent.install_id(), "")


class Options(Base):
    def test_defaults_after_accept(self):
        c = consent.get()
        self.assertTrue(c["updates"]); self.assertFalse(c["stats"]); self.assertFalse(c["heads"])
        self.assertEqual(consent.install_id(), "")

    def test_stats_id_made_only_when_on_and_forgotten_when_off(self):
        consent.set_option("stats", True)
        iid = consent.install_id()
        self.assertEqual(len(iid), 36)
        consent.set_option("stats", False)
        self.assertEqual(consent.install_id(), ""); self.assertEqual(consent.pending_forget(), iid)
        consent.clear_forget(); self.assertEqual(consent.pending_forget(), "")

    def test_unknown_option(self):
        with self.assertRaises(ValueError): consent.set_option("nope", True)

    def test_policy_bump_needs_new_accept(self):
        with mock.patch.object(brand, "POLICY_VERSION", brand.POLICY_VERSION + 1):
            self.assertFalse(consent.get()["accepted"]); self.assertFalse(consent.updates_allowed())


class Updates(Base):
    def test_parse_and_compare(self):
        self.assertTrue(updates.parse("v0.10.0") > updates.parse("0.9.9"))
        self.assertEqual(updates.parse("1.0"), (1, 0, 0))

    def test_newer_available_with_installer_link(self):
        with mock.patch.object(updates.requests, "get", return_value=Resp(200, release("v0.2.0"))):
            r = updates.check(force=True)
        self.assertTrue(r["available"]); self.assertEqual(r["latest"], "0.2.0"); self.assertEqual(r["file"], "https://dl/setup.exe")

    def test_same_or_older_not_available(self):
        with mock.patch.object(updates.requests, "get", return_value=Resp(200, release("v" + brand.VERSION))):
            self.assertFalse(updates.check(force=True)["available"])

    def test_no_release_yet_is_quiet(self):
        with mock.patch.object(updates.requests, "get", return_value=Resp(404)):
            r = updates.check(force=True)
        self.assertFalse(r["available"]); self.assertEqual(r["error"], "")

    def test_offline_never_raises_and_uses_cache(self):
        with mock.patch.object(updates.requests, "get", return_value=Resp(200, release("v0.2.0"))):
            updates.check(force=True)
        with mock.patch.object(updates.requests, "get", side_effect=OSError("offline")):
            r = updates.check(force=True)
        self.assertTrue(r["available"]); self.assertTrue(r["error"])
        updates._cache.update(at=0.0, data=None)
        with mock.patch.object(updates.requests, "get", side_effect=OSError("offline")):
            self.assertTrue(updates.check(force=True)["error"])

    def test_off_means_no_request(self):
        consent.set_option("updates", False)
        with mock.patch.object(updates.requests, "get") as g:
            r = updates.check(force=True)
        g.assert_not_called(); self.assertFalse(r["enabled"])

    def test_cache_used(self):
        with mock.patch.object(updates.requests, "get", return_value=Resp(200, release())) as g:
            updates.check(); updates.check()
        self.assertEqual(g.call_count, 1)


class Stats(Base):
    def test_nothing_sent_without_worker_address(self):
        consent.set_option("stats", True)
        with mock.patch.object(brand, "STATS_URL", ""), mock.patch.object(stats.requests, "post") as p:
            stats.tick()
        p.assert_not_called()

    def test_ping_once_a_day_and_only_with_consent(self):
        with mock.patch.object(brand, "STATS_URL", "https://w.test"), mock.patch.object(stats.requests, "post", return_value=Resp(200)) as p:
            stats.tick(); p.assert_not_called()                      # stats off
            consent.set_option("stats", True)
            stats.tick(); stats.tick()
        self.assertEqual(p.call_count, 1)
        url, kw = p.call_args[0][0], p.call_args[1]
        self.assertEqual(url, "https://w.test/ping")
        self.assertEqual(set(kw["json"]), {"id", "v", "os"})

    def test_switching_off_tells_server_to_forget(self):
        consent.set_option("stats", True); iid = consent.install_id()
        consent.set_option("stats", False)
        with mock.patch.object(brand, "STATS_URL", "https://w.test"), mock.patch.object(stats.requests, "post", return_value=Resp(200)) as p:
            stats.tick()
        self.assertEqual(p.call_args[0][0], "https://w.test/forget"); self.assertEqual(p.call_args[1]["json"], {"id": iid})
        self.assertEqual(consent.pending_forget(), "")

    def test_failed_ping_is_retried_later(self):
        consent.set_option("stats", True)
        with mock.patch.object(brand, "STATS_URL", "https://w.test"), mock.patch.object(stats.requests, "post", side_effect=OSError("offline")):
            stats.tick()
        self.assertEqual(consent.last_ping(), 0)

    def test_report_is_scrubbed_and_needs_worker(self):
        with mock.patch.object(brand, "STATS_URL", ""):
            with self.assertRaises(RuntimeError): stats.send_report("x")
        home = str(Path.home())
        with mock.patch.object(brand, "STATS_URL", "https://w.test"), mock.patch.object(stats.requests, "post", return_value=Resp(200)) as p:
            stats.send_report(f"log {home}/a secret=ABCDEFGHIJKLMNOP1234", note="n", contact="a@b.c")
        sent = p.call_args[1]["json"]
        self.assertNotIn(home, sent["text"]); self.assertNotIn("ABCDEFGHIJKLMNOP1234", sent["text"])
        self.assertEqual(sent["contact"], "a@b.c")


class Api(Base):
    def setUp(self):
        super().setUp()
        from starlette.testclient import TestClient
        from backend.app import app
        self.c = TestClient(app, base_url="http://127.0.0.1", headers={"X-MCPanel": "1"})

    def test_consent_options_and_update_endpoint(self):
        r = self.c.put("/api/consent", json={"stats": True, "updates": False}).json()
        self.assertTrue(r["stats"]); self.assertFalse(r["updates"])
        self.assertFalse(self.c.get("/api/update?force=1").json()["enabled"])

    def test_send_report_validation(self):
        self.assertEqual(self.c.post("/api/support/send", json={"text": "  "}).status_code, 400)
        with mock.patch.object(brand, "STATS_URL", ""):
            self.assertEqual(self.c.post("/api/support/send", json={"text": "hi"}).status_code, 400)
        with mock.patch.object(brand, "STATS_URL", "https://w.test"), mock.patch.object(stats.requests, "post", return_value=Resp(200)):
            self.assertEqual(self.c.post("/api/support/send", json={"text": "hi"}).json(), {"ok": True})
        self.assertIn("can_send", self.c.get("/api/support/report").json())


if __name__ == "__main__":
    unittest.main()
