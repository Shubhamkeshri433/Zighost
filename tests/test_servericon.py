"""Server icon + capability checks. Run: python -I tests/test_servericon.py"""
import base64
import os
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["MCPANEL_DATA"] = tempfile.mkdtemp(prefix="mcpanel-test4-")
sys.path.insert(0, str(ROOT))

from backend import plugins, servericon   # noqa: E402
from backend.manager import ManagerError, manager   # noqa: E402
from backend.store import ensure_dirs, save_server, server_dir   # noqa: E402

ensure_dirs()


def png(w=64, h=64):
    def chunk(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    raw = b"".join(b"\x00" + b"\xff\x00\x00\xff" * w for _ in range(h))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


class IconTests(unittest.TestCase):
    def test_good_png_passes(self):
        self.assertEqual(servericon.validate(png()), png())

    def test_wrong_size_rejected(self):
        with self.assertRaises(servericon.IconError):
            servericon.validate(png(32, 32))

    def test_not_a_png_rejected(self):
        with self.assertRaises(servericon.IconError):
            servericon.validate(b"GIF89a" + b"0" * 100)

    def test_too_big_rejected(self):
        with self.assertRaises(servericon.IconError):
            servericon.validate(png() + b"0" * servericon.MAX_BYTES)

    def test_data_url_and_plain_base64(self):
        b64 = base64.b64encode(png()).decode()
        self.assertEqual(servericon.decode("data:image/png;base64," + b64), png())
        self.assertEqual(servericon.decode(b64), png())
        with self.assertRaises(servericon.IconError):
            servericon.decode("not base64 !!!")

    def test_save_read_version_remove(self):
        sid = "aaaa1111"
        save_server({"id": sid, "name": "I", "type": "paper", "version": "1.21.4", "ram_mb": 512, "port": 25901, "installed": True})
        self.assertEqual(servericon.version(sid), 0)
        servericon.save(sid, png())
        self.assertEqual(servericon.read(sid), png())
        self.assertGreater(servericon.version(sid), 0)
        self.assertEqual((server_dir(sid) / "server-icon.png").read_bytes(), png())
        servericon.remove(sid)
        self.assertIsNone(servericon.read(sid))


class CreateValidationTests(unittest.TestCase):
    def call(self, **kw):
        args = dict(name="N", stype="paper", version="1.21.4", ram_mb=1024, port=25600, eula=True)
        args.update(kw)
        return manager.create_server(**args)

    def test_bad_icon_is_refused_before_anything_is_created(self):
        with self.assertRaises(ManagerError):
            self.call(icon=b"nope")

    def test_bad_starter_id_refused(self):
        with self.assertRaises(ManagerError):
            self.call(starter=["../etc/passwd"])


class CapabilityTests(unittest.TestCase):
    def test_table(self):
        self.assertIsNone(plugins.kind_for("vanilla"))
        self.assertEqual(plugins.kind_for("paper")[0], "plugins")
        self.assertEqual(plugins.kind_for("spigot")[0], "plugins")
        self.assertEqual(plugins.kind_for("purpur")[0], "plugins")
        self.assertEqual(plugins.kind_for("fabric")[0], "mods")
        self.assertEqual(plugins.kind_for("fabric")[1], ["fabric"])


if __name__ == "__main__":
    unittest.main(verbosity=1)
