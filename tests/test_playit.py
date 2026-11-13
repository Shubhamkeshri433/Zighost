"""playit claim + tunnel flow against a fake playit.gg API. Run: python -I tests/test_playit.py"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
os.environ["MCPANEL_DATA"] = tempfile.mkdtemp(prefix="mcpanel-test3-")
sys.path.insert(0, str(ROOT))

from backend import playit as P   # noqa: E402
from backend.store import ensure_dirs, get_settings, update_settings   # noqa: E402

ensure_dirs()


class Resp:
    def __init__(self, status, data, kind="success"):
        self.status_code = status
        self.ok = status < 400
        self._j = {"status": kind, "data": data}
        self.text = json.dumps(self._j)

    def json(self):
        return self._j


def fake_api(script):
    """script: dict path -> list of Resp (last one repeats). Records calls."""
    calls = []

    def post(url, json=None, headers=None, timeout=None):
        path = url.replace(P.API_BASE, "")
        calls.append((path, json, headers))
        items = script[path]
        return items.pop(0) if len(items) > 1 else items[0]
    return post, calls


class ClaimTests(unittest.TestCase):
    def setUp(self):
        update_settings({"playit_secret": ""})
        self.pl = P.Playit()
        self.pl._gen = 1
        self.sleep = mock.patch.object(P.time, "sleep", lambda s: None)
        self.web = mock.patch.object(P.webbrowser, "open", lambda u: True)
        self.sleep.start(); self.web.start()

    def tearDown(self):
        self.sleep.stop(); self.web.stop()

    def test_claim_waits_then_saves_secret(self):
        post, calls = fake_api({"/claim/setup": [Resp(200, "WaitingForUserVisit"), Resp(200, "WaitingForUser"), Resp(200, "UserAccepted")],
                                "/claim/exchange": [Resp(200, {"secret_key": "ab" * 20})]})
        with mock.patch.object(P.requests, "post", post):
            key = self.pl._claim(1)
        self.assertEqual(key, "ab" * 20)
        self.assertEqual(get_settings()["playit_secret"], "ab" * 20)
        self.assertEqual(self.pl.claim_url, "")
        setup = [c for c in calls if c[0] == "/claim/setup"][0][1]
        self.assertEqual(setup["agent_type"], "self-managed")
        self.assertEqual(len(setup["code"]), 16)

    def test_claim_shows_link_while_waiting(self):
        post, _ = fake_api({"/claim/setup": [Resp(200, "WaitingForUserVisit")]})
        self.pl._gen = 1
        seen = []
        orig = P.time.sleep

        def spy(s):
            seen.append((self.pl.state, self.pl.claim_url))
            self.pl._stop = True
        with mock.patch.object(P.requests, "post", post), mock.patch.object(P.time, "sleep", spy):
            self.pl._claim(1)
        self.assertEqual(seen[0][0], "needs_claim")
        self.assertTrue(seen[0][1].startswith("https://playit.gg/claim/"))

    def test_reject_is_a_clear_error(self):
        post, _ = fake_api({"/claim/setup": [Resp(200, "UserRejected")]})
        with mock.patch.object(P.requests, "post", post):
            with self.assertRaises(P.PlayitError) as cm:
                self.pl._claim(1)
        self.assertIn("Reject", str(cm.exception))

    def test_unreachable_gives_up_with_plain_text(self):
        def boom(*a, **k):
            raise P.requests.ConnectionError("x")
        with mock.patch.object(P.requests, "post", boom):
            with self.assertRaises(P.PlayitError) as cm:
                self.pl._claim(1)
        self.assertIn("internet", str(cm.exception))


class TunnelTests(unittest.TestCase):
    def setUp(self):
        self.pl = P.Playit()
        self.pl.local_port = 25565

    def rundata(self, **kw):
        return Resp(200, {"agent_id": "ag1", "account_status": kw.get("acct", "guest"), "tunnels": kw.get("tunnels", [])})

    def test_creates_tunnel_when_missing(self):
        post, calls = fake_api({"/agents/rundata": [self.rundata()], "/tunnels/create": [Resp(200, {"id": "t1"})]})
        with mock.patch.object(P.requests, "post", post):
            self.pl._tunnel_setup("k" * 40)
        body = [c for c in calls if c[0] == "/tunnels/create"][0][1]
        self.assertEqual(body["origin"]["data"]["local_port"], 25565)
        self.assertEqual(body["origin"]["data"]["agent_id"], "ag1")
        self.assertEqual(self.pl.account, "guest")
        self.assertEqual(self.pl.tunnel_note, "")

    def test_existing_tunnel_is_left_alone(self):
        post, calls = fake_api({"/agents/rundata": [self.rundata(tunnels=[{"local_port": 25565, "assigned_domain": "a.ply.gg"}])]})
        with mock.patch.object(P.requests, "post", post):
            self.pl._tunnel_setup("k" * 40)
        self.assertFalse([c for c in calls if c[0] == "/tunnels/create"])

    def test_limit_gives_plain_message(self):
        post, _ = fake_api({"/agents/rundata": [self.rundata()], "/tunnels/create": [Resp(400, "TunnelLimit reached: limit", "fail")]})
        with mock.patch.object(P.requests, "post", post):
            self.pl._tunnel_setup("k" * 40)
        self.assertIn("limit", self.pl.tunnel_note.lower())

    def test_all_variants_fail_leaves_manual_steps(self):
        post, calls = fake_api({"/agents/rundata": [self.rundata()], "/tunnels/create": [Resp(400, "InvalidField", "fail")]})
        with mock.patch.object(P.requests, "post", post):
            self.pl._tunnel_setup("k" * 40)
        self.assertEqual(len([c for c in calls if c[0] == "/tunnels/create"]), 3)
        self.assertIn("25565", self.pl.tunnel_note)

    def test_bad_account_stops_with_message(self):
        post, _ = fake_api({"/agents/rundata": [self.rundata(acct="agent-over-limit")]})
        with mock.patch.object(P.requests, "post", post):
            with self.assertRaises(P.PlayitError):
                self.pl._tunnel_setup("k" * 40)

    def test_no_port_no_creation(self):
        self.pl.local_port = None
        post, calls = fake_api({"/agents/rundata": [self.rundata()]})
        with mock.patch.object(P.requests, "post", post):
            self.pl._tunnel_setup("k" * 40)
        self.assertFalse([c for c in calls if c[0] == "/tunnels/create"])


class MiscTests(unittest.TestCase):
    def test_diagnostics_hides_the_secret(self):
        key = "cd" * 20
        update_settings({"playit_secret": key})
        pl = P.Playit()
        pl.log.append(f"secret_key = {key}")
        pl.error = f"oops {key}"
        text = pl.diagnostics()
        self.assertNotIn(key, text)
        self.assertIn("state:", text)

    def test_unlink_forgets_key(self):
        update_settings({"playit_secret": "ef" * 20})
        (P.PLAYIT_DIR).mkdir(parents=True, exist_ok=True)
        (P.PLAYIT_DIR / "playit.toml").write_text('secret_key = "x"')
        pl = P.Playit()
        pl.unlink()
        self.assertEqual(get_settings()["playit_secret"], "")
        self.assertFalse((P.PLAYIT_DIR / "playit.toml").exists())

    def test_other_playit_app_key_is_never_used(self):
        update_settings({"playit_secret": ""})
        self.assertEqual(P.find_secret(), "")

    def test_parse_rundata_prefers_matching_port(self):
        d = {"tunnels": [{"assigned_domain": "a.ply.gg", "local_port": 1, "port": {"from": 100}},
                         {"assigned_domain": "b.ply.gg", "local_port": 25565, "port": {"from": 25565}}]}
        self.assertEqual(P.parse_rundata(d, 25565), "b.ply.gg")


class PerServerTunnel(unittest.TestCase):
    TUN = [{"name": "MC Panel aaaa1111", "local_port": 25565, "assigned_domain": "a.ply.gg", "port": {"from": 25565}},
           {"name": "MC Panel bbbb2222", "local_port": 25565, "assigned_domain": "b.ply.gg", "port": {"from": 25565}},
           {"name": "MC Panel 25565", "local_port": 25565, "assigned_domain": "old.ply.gg", "port": {"from": 25565}}]

    def test_each_server_gets_its_own_address(self):
        d = {"tunnels": self.TUN}
        self.assertEqual(P.parse_rundata(d, 25565, "aaaa1111"), "a.ply.gg")
        self.assertEqual(P.parse_rundata(d, 25565, "bbbb2222"), "b.ply.gg")

    def test_server_without_tunnel_never_borrows_another(self):
        self.assertEqual(P.parse_rundata({"tunnels": self.TUN}, 25565, "cccc3333"), "")

    def test_creates_own_tunnel_even_if_port_is_taken_by_another(self):
        pl = P.Playit(); pl.local_port = 25565; pl.tag = "cccc3333"
        data = Resp(200, {"agent_id": "ag1", "account_status": "ready", "tunnels": self.TUN})
        post, calls = fake_api({"/agents/rundata": [data], "/tunnels/create": [Resp(200, {"id": "t"})]})
        with mock.patch.object(P.requests, "post", post):
            pl._tunnel_setup("k" * 40)
        body = [c for c in calls if c[0] == "/tunnels/create"][0][1]
        self.assertEqual(body["name"], "Zighost cccc3333")

    def test_switching_server_restarts_helper(self):
        pl = P.Playit(); pl.state = "online"; pl.tag = "aaaa1111"; pl.address = "a.ply.gg"
        with mock.patch.object(pl, "stop", side_effect=lambda: setattr(pl, "state", "stopped")) as st, mock.patch.object(P.threading, "Thread"):
            pl.start(25565, "bbbb2222")
        st.assert_called_once()
        self.assertEqual(pl.tag, "bbbb2222")


class NoiseAndNotes(unittest.TestCase):
    def test_noise_dropped_and_notes_kept(self):
        from backend import playit as pl
        p = pl.Playit()
        for i in range(200):
            p._parse("WARN local timestamp if over 10 seconds off offset=-1")
        p.note("Tunnel create answered 400: email not verified")
        for i in range(200):
            p._parse(f"some other helper line {i}")
        self.assertIn("Tunnel create answered 400: email not verified", p.diagnostics())
        self.assertFalse(any("local timestamp" in l for l in p.log))


if __name__ == "__main__":
    unittest.main(verbosity=1)
