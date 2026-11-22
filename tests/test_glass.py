"""Frosted theme, see-through window and native splash: the parts that can be checked without Windows."""
import os, sys, tempfile, unittest
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend import shell, store, winos


class Glass(unittest.TestCase):
    def test_not_supported_off_windows_and_on_old_windows(self):
        with mock.patch.object(winos, "IS_WINDOWS", False):
            self.assertFalse(winos.glass_supported())
            self.assertFalse(winos.apply_backdrop("Zighost"))
        with mock.patch.object(winos, "IS_WINDOWS", True), mock.patch.object(sys, "getwindowsversion", create=True, return_value=SimpleNamespace(build=19045)):
            self.assertFalse(winos.glass_supported())
        with mock.patch.object(winos, "IS_WINDOWS", True), mock.patch.object(sys, "getwindowsversion", create=True, return_value=SimpleNamespace(build=22631)):
            self.assertTrue(winos.glass_supported())

    def test_frost_is_the_default_and_the_switch_is_saved(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(store, "DATA", __import__("pathlib").Path(d)):
            s = store.get_settings()
            self.assertEqual(s["theme"], "frost")
            self.assertTrue(s["transparent_window"])
            self.assertFalse(store.update_settings({"transparent_window": False})["transparent_window"])
            self.assertEqual(store.update_settings({"theme": "nope"})["theme"], "frost")
            self.assertEqual(store.update_settings({"theme": "nether"})["theme"], "nether")

    def test_page_class_follows_what_windows_accepted(self):
        calls = []
        win = SimpleNamespace(native=SimpleNamespace(Handle=SimpleNamespace(ToInt64=lambda: 77)), evaluate_js=calls.append)
        sh = shell.Shell("http://x", on_quit=lambda: None, status=lambda: "", stop_servers=lambda: None, webview=SimpleNamespace(), pystray=SimpleNamespace())
        sh.window, sh.glass_on = win, True
        with mock.patch.object(winos, "apply_backdrop", return_value=True) as ab:
            sh._glass()
            ab.assert_called_once_with(shell.brand.NAME, 77)
        self.assertIn("add('glass')", calls[-1])
        with mock.patch.object(winos, "apply_backdrop", return_value=False):
            sh._glass()
        self.assertIn("remove('glass')", calls[-1])
        calls.clear(); sh.glass_on = False
        sh._glass()
        self.assertEqual(calls, [])

    def test_closing_a_missing_native_splash_is_harmless(self):
        shell.close_native_splash()
        fake = SimpleNamespace(close=mock.Mock())
        with mock.patch.dict(sys.modules, {"pyi_splash": fake}):
            shell.close_native_splash()
        fake.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
