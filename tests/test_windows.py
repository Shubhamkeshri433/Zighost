import json, os, sys, tempfile, unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

TMP = tempfile.mkdtemp()
os.environ["ZIGHOST_DATA"] = TMP
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend import winos, winmon, store, shell, brand


class Sealing(unittest.TestCase):
    def test_off_windows_plain(self):
        with mock.patch.object(winos, "IS_WINDOWS", False):
            self.assertEqual(winos.seal("abc"), "abc")
            self.assertEqual(winos.unseal("abc"), "abc")

    def test_prefix_not_double_sealed_and_bad_blob(self):
        with mock.patch.object(winos, "IS_WINDOWS", True):
            self.assertEqual(winos.seal("dpapi:xyz"), "dpapi:xyz")
        self.assertEqual(winos.unseal("dpapi:!!notbase64"), "")

    def test_roundtrip_with_fake_dpapi(self):
        fake = lambda data, enc: data[::-1] if enc else data[::-1]
        with mock.patch.object(winos, "IS_WINDOWS", True), mock.patch.object(winos, "_dpapi", fake):
            s = winos.seal("secret")
            self.assertTrue(s.startswith("dpapi:"))
            self.assertNotIn("secret", s)
            self.assertEqual(winos.unseal(s), "secret")

    def test_store_encrypts_plain_file_on_windows(self):
        fake = lambda data, enc: data[::-1]
        p = Path(store.DATA) / "settings.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"playit_secret": "abc123"}))
        with mock.patch.object(winos, "IS_WINDOWS", True), mock.patch.object(winos, "_dpapi", fake):
            self.assertEqual(store.get_settings()["playit_secret"], "abc123")
            self.assertTrue(json.loads(p.read_text())["playit_secret"].startswith("dpapi:"))
            store.update_settings({"discord_webhook": "https://x/y"})
            self.assertTrue(json.loads(p.read_text())["discord_webhook"].startswith("dpapi:"))
            self.assertEqual(store.get_settings()["discord_webhook"], "https://x/y")
        p.unlink()


class Mon(unittest.TestCase):
    def test_keep_awake_follows_server(self):
        awake = winos.KeepAwake()
        calls = []
        awake.set = lambda on: calls.append(on)
        mgr = SimpleNamespace(busy=lambda: True, proc=None)
        m = winmon.Monitor(mgr, awake)
        m.tick()
        mgr.busy = lambda: False
        m.tick()
        store.update_settings({"keep_awake": False})
        mgr.busy = lambda: True
        m.tick()
        store.update_settings({"keep_awake": True})
        self.assertEqual(calls, [True, False, False])

    def test_notices(self):
        got = []
        m = winmon.Monitor(SimpleNamespace(busy=lambda: False, proc=None), winos.KeepAwake())
        m.notifier = lambda t, x: got.append((t, x))
        m.event("player", "Steve joined")
        m.event("start", "Server is online")
        store.update_settings({"toasts": False})
        m.event("crash", "Server crashed")
        store.update_settings({"toasts": True})
        self.assertEqual(got, [(brand.NAME, "Server is online")])

    def test_throttle_new_pid_once(self):
        proc = SimpleNamespace(pid=77, poll=lambda: None)
        m = winmon.Monitor(SimpleNamespace(busy=lambda: True, proc=proc), winos.KeepAwake())
        m.awake.set = lambda on: None
        with mock.patch.object(winos, "disable_throttling") as d:
            m.tick(); m.tick()
        d.assert_called_once_with(77)


class FakeEvents(list):
    def __iadd__(self, f):
        self.append(f); return self


class FakeWindow:
    def __init__(self):
        self.events = SimpleNamespace(closing=FakeEvents())
        self.hidden = 0; self.destroyed = 0
    def hide(self): self.hidden += 1
    def show(self): pass
    def restore(self): pass
    def destroy(self): self.destroyed += 1


class Sh(unittest.TestCase):
    def make(self, icon=True):
        s = shell.Shell("http://127.0.0.1:1", lambda: self.quit.append(1), lambda: "ok", lambda: None, webview=SimpleNamespace(), pystray=None)
        s.window = FakeWindow()
        if icon:
            s.icon = mock.Mock()
        return s

    def setUp(self):
        self.quit = []

    def test_close_hides_to_tray_with_one_hint(self):
        s = self.make()
        self.assertFalse(s._closing())
        self.assertFalse(s._closing())
        self.assertEqual(s.window.hidden, 2)
        self.assertEqual(s.icon.notify.call_count, 1)

    def test_close_without_tray_really_closes(self):
        self.assertTrue(self.make(icon=False)._closing())

    def test_quit_once_and_allows_close(self):
        s = self.make()
        s.quit(); s.quit()
        self.assertEqual(self.quit, [1])
        self.assertTrue(s._closing())
        self.assertEqual(s.window.destroyed, 1)

    def test_run_without_anything_returns_false(self):
        s = shell.Shell("http://x", lambda: None, lambda: "", lambda: None, webview=None, pystray=None)
        s.webview = None; s.pystray = None
        self.assertFalse(s.run())


class WindowsApi(unittest.TestCase):
    def test_put_and_get(self):
        from starlette.testclient import TestClient
        from backend.app import app
        c = TestClient(app, base_url="http://127.0.0.1", headers={"X-MCPanel": "1"})
        r = c.get("/api/windows").json()
        self.assertEqual(set(r), {"available", "autostart", "keep_awake", "toasts"})
        r = c.put("/api/windows", json={"keep_awake": False, "toasts": False}).json()
        self.assertFalse(r["keep_awake"]); self.assertFalse(r["toasts"])
        with mock.patch.object(winos, "IS_WINDOWS", False):
            self.assertEqual(c.put("/api/windows", json={"autostart": True}).status_code, 400)
        with mock.patch("backend.app.winos.autostart_set") as a, mock.patch.object(winos, "IS_WINDOWS", True), \
             mock.patch("backend.app.winos.IS_WINDOWS", True), mock.patch("backend.app.winos.autostart_get", return_value=True):
            r = c.put("/api/windows", json={"autostart": True}).json()
            a.assert_called_once_with(True); self.assertTrue(r["autostart"])


if __name__ == "__main__":
    unittest.main()
