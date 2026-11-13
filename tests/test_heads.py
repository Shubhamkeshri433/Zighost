import os, sys, tempfile, unittest
from pathlib import Path
os.environ["MCPANEL_DATA"] = tempfile.mkdtemp()
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend import heads

PNG = heads.PNG + b"x" * 20


class T(unittest.TestCase):
    def test_bad_names(self):
        for n in ("", "../x", "a b", "x" * 17, ".Bedrock"):
            self.assertIsNone(heads.get(n, fetch=lambda u: self.fail("fetched")))

    def test_cache_and_miss(self):
        calls = []
        def ok(u): calls.append(u); return PNG
        self.assertEqual(heads.get("Steve", fetch=ok), PNG)
        self.assertEqual(heads.get("steve", fetch=ok), PNG)
        self.assertEqual(len(calls), 1)
        n = []
        def none(u): n.append(u); return None
        self.assertIsNone(heads.get("Ghost", fetch=none))
        c = len(n)
        self.assertIsNone(heads.get("Ghost", fetch=none))
        self.assertEqual(len(n), c)

    def test_rejects_non_png(self):
        self.assertIsNone(heads.get("Alex", fetch=lambda u: b"<html>"))


if __name__ == "__main__":
    unittest.main()
