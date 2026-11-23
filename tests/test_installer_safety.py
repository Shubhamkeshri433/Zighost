"""The uninstaller must not delete servers by one careless click. Inno Setup cannot run here, so this guards the script text."""
import os, re, unittest

ISS = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "installer", "zighost.iss"), encoding="utf-8").read()


class UninstallSafety(unittest.TestCase):
    def test_keep_is_the_default_and_delete_needs_a_second_yes(self):
        self.assertIn("MB_YESNO or MB_DEFBUTTON1", ISS)          # first question: Yes = keep, and it is the default
        self.assertIn("MB_YESNO or MB_DEFBUTTON2", ISS)          # second question: the default is No (keep)
        self.assertEqual(ISS.count("DelTree(dataDir"), 1)
        i = ISS.index("DelTree(dataDir")
        self.assertIn("= IDYES then", ISS[ISS.rindex("MB_DEFBUTTON2", 0, i):i])   # only an explicit Yes on the second question deletes

    def test_only_functions_that_exist_in_an_uninstaller(self):
        # Inno Setup's uninstaller has no input box: InputQuery and the wizard pages are installer-only (this broke a build).
        code = ISS[ISS.index("function CountServers"):]
        for name in ("InputQuery", "CreateInputQueryPage", "WizardForm", "CreateCustomPage"):
            self.assertNotIn(name, code)

    def test_silent_uninstall_never_deletes(self):
        self.assertIn("not UninstallSilent", ISS)

    def test_begin_end_balance(self):
        code = ISS[ISS.index("function CountServers"):]
        words = re.findall(r"\b(begin|end|try|case)\b", code, re.I)
        opens = sum(1 for w in words if w.lower() in ("begin", "try", "case"))
        self.assertEqual(opens, sum(1 for w in words if w.lower() == "end"))


if __name__ == "__main__":
    unittest.main()
