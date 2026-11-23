"""The native splash is drawn by the packaged exe. Closing it must never fail, with or without a splash."""
import os, sys, unittest
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend import shell


class Splash(unittest.TestCase):
    def test_closing_a_missing_native_splash_is_harmless(self):
        shell.close_native_splash()
        fake = SimpleNamespace(close=mock.Mock())
        with mock.patch.dict(sys.modules, {"pyi_splash": fake}):
            shell.close_native_splash()
        fake.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
