import os, sys, tempfile, unittest
from pathlib import Path
from unittest import mock
os.environ["MCPANEL_DATA"] = tempfile.mkdtemp()
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend import plugins as pl


class T(unittest.TestCase):
    def test_suggests_other_versions_when_none_match(self):
        hits = [{"versions": ["1.21.1", "1.21.4", "26.3", "1.20.1", "snapshot-x"]} for _ in range(10)]
        with mock.patch.object(pl, "_get", return_value={"hits": hits}):
            r = pl._other_versions("mods", ["fabric"], "26.3")
        self.assertEqual(r, ["1.21.4", "1.21.1", "1.20.1"])

    def test_network_failure_gives_empty(self):
        with mock.patch.object(pl, "_get", side_effect=pl.PluginError("x")):
            self.assertEqual(pl._other_versions("mods", ["fabric"], "1.21"), [])


if __name__ == "__main__":
    unittest.main()
