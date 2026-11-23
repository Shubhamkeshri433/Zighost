"""The uninstaller must not delete servers by one careless click. Inno Setup cannot run here, so this guards the script text."""
import os, re, unittest

ISS = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "installer", "zighost.iss"), encoding="utf-8").read()


class UninstallSafety(unittest.TestCase):
    def test_keep_is_the_default_and_delete_needs_typing(self):
        self.assertIn("MB_YESNO or MB_DEFBUTTON1", ISS)          # first button (Yes = keep) is the default
        self.assertIn("InputQuery(", ISS)
        self.assertIn("typed = 'DELETE'", ISS)
        self.assertEqual(ISS.count("DelTree(dataDir"), 1)

    def test_delete_only_after_the_typed_check(self):
        i = ISS.index("DelTree(dataDir")
        self.assertIn("typed = 'DELETE'", ISS[ISS.rindex("InputQuery(", 0, i):i])

    def test_silent_uninstall_never_deletes(self):
        self.assertIn("not UninstallSilent", ISS)

    def test_begin_end_balance(self):
        code = ISS[ISS.index("function CountServers"):]
        words = re.findall(r"\b(begin|end|try|case)\b", code, re.I)
        opens = sum(1 for w in words if w.lower() in ("begin", "try", "case"))
        self.assertEqual(opens, sum(1 for w in words if w.lower() == "end"))


if __name__ == "__main__":
    unittest.main()
