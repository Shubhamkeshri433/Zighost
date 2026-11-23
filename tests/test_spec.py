"""The PyInstaller recipe can be read here without PyInstaller: a fake PyInstaller records how the recipe calls it.
This catches mistakes in zighost.spec (like passing the splash files the wrong way) before a Windows build does."""
import os, sys, types, unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


class Toc(list):
    """Like PyInstaller's file lists: a list of (name, path, kind) entries, which COLLECT takes as ONE argument."""


def run_spec(splash_fails: bool):
    calls = {}
    ns = {"__file__": os.path.join(ROOT, "zighost.spec")}
    fake_hooks = types.ModuleType("PyInstaller.utils.hooks"); fake_hooks.collect_submodules = lambda name: []
    mods = {"PyInstaller": types.ModuleType("PyInstaller"), "PyInstaller.utils": types.ModuleType("PyInstaller.utils"),
            "PyInstaller.utils.hooks": fake_hooks}

    class Analysis:
        def __init__(self, *a, **k): self.pure, self.scripts = [], ["script"]; self.binaries, self.datas = Toc([("a", "b", "BINARY")]), Toc([("c", "d", "DATA")])

    class Splash:
        def __init__(self, image, **k):
            if splash_fails:
                raise SystemExit("no Tcl/Tk")
            calls["splash_image"] = image
            self.binaries = Toc([("tcl", "tcl.dll", "BINARY")])

    def record(name):
        def f(*a, **k): calls[name] = (a, k); return mock.Mock(name=name)
        return f

    ns.update(Analysis=Analysis, Splash=Splash, PYZ=record("PYZ"), EXE=record("EXE"), COLLECT=record("COLLECT"))
    with mock.patch.dict(sys.modules, mods), mock.patch("os.makedirs"):
        cwd = os.getcwd(); os.chdir(ROOT)
        try:
            exec(compile(open(os.path.join(ROOT, "zighost.spec"), encoding="utf-8").read(), "zighost.spec", "exec"), ns)
        finally:
            os.chdir(cwd)
    return ns, calls


class Spec(unittest.TestCase):
    def test_splash_files_are_passed_whole(self):
        ns, calls = run_spec(False)
        args = calls["COLLECT"][0]
        self.assertIn(ns["splash"].binaries, args, "COLLECT must get the splash file list as one argument")
        for a in args[1:]:
            self.assertIsInstance(a, (Toc, type(ns["a"].binaries)), "every list given to COLLECT must be a whole list, not single entries")
        self.assertIn(ns["splash"], calls["EXE"][0])
        self.assertTrue(os.path.exists(os.path.join(ROOT, calls["splash_image"])))

    def test_without_splash_the_build_still_works(self):
        ns, calls = run_spec(True)
        self.assertNotIn(ns.get("splash"), calls["EXE"][0])
        self.assertEqual(len(calls["COLLECT"][0]), 3)


if __name__ == "__main__":
    unittest.main()
