import http.server, json, os, sys, tempfile, threading, unittest
from pathlib import Path
from unittest import mock

TMP = tempfile.mkdtemp()
os.environ["ZIGHOST_DATA"] = TMP
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend import brand, instance, logsetup, paths


class Ping(http.server.BaseHTTPRequestHandler):
    app = brand.DATA_KEY

    def do_GET(self):
        body = json.dumps({"app": self.app}).encode()
        self.send_response(200); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

    def log_message(self, *a):
        pass


def serve(app):
    h = type("H", (Ping,), {"app": app})
    srv = http.server.HTTPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1]


class Brand(unittest.TestCase):
    def test_public_and_js(self):
        self.assertEqual(brand.VERSION, "0.1.0")
        js = brand.js()
        self.assertTrue(js.startswith("window.BRAND = "))
        data = json.loads(js[len("window.BRAND = "):].rstrip(";\n"))
        self.assertEqual(data["publisher"], "shubverser")
        self.assertEqual(data["publisherName"], "Shubham Keshri")
        self.assertNotIn("appId", data)             # installer id is never sent to the page

    def test_rename_keeps_ids(self):
        self.assertEqual(brand.DATA_KEY, "zighost")
        self.assertTrue(brand.APP_ID.startswith("{") and brand.APP_ID.endswith("}"))
        self.assertIn("MC Panel ", brand.TUNNEL_PREFIXES)


class DataDir(unittest.TestCase):
    def test_env_wins(self):
        self.assertEqual(paths.default_data_dir(), Path(TMP))

    def test_packaged_app_uses_appdata(self):
        with mock.patch.dict(os.environ, {"ZIGHOST_DATA": "", "MCPANEL_DATA": "", "APPDATA": "/fake/AppData/Roaming"}), \
             mock.patch.object(paths, "FROZEN", True), mock.patch.object(paths, "_is_windows", lambda: True):
            d = paths.default_data_dir()
        self.assertTrue(str(d).endswith("zighost"))
        self.assertIn("AppData", str(d))

    def test_source_checkout_keeps_local_data_folder(self):
        with mock.patch.dict(os.environ, {"ZIGHOST_DATA": "", "MCPANEL_DATA": ""}), mock.patch.object(paths, "FROZEN", False):
            self.assertEqual(paths.default_data_dir(), paths.BASE / "data")


class Instance(unittest.TestCase):
    def test_finds_running_copy_and_ignores_strangers(self):
        srv, port = serve(brand.DATA_KEY)
        other, oport = serve("something-else")
        try:
            self.assertEqual(instance.find_running(port), f"http://localhost:{port}")
            self.assertIsNone(instance.find_running(oport))
            self.assertEqual(instance.claim(port), f"http://localhost:{port}")
        finally:
            srv.shutdown(); other.shutdown()

    def test_choose_port_skips_busy(self):
        srv, port = serve("x")
        try:
            p = instance.choose_port(port)
            self.assertNotEqual(p, port)
            self.assertTrue(instance.port_free(p))
        finally:
            srv.shutdown()

    def test_publish_writes_file(self):
        instance.publish(8123)
        self.assertEqual(json.loads(instance.FILE.read_text())["port"], 8123)
        instance.FILE.unlink()


class Logging(unittest.TestCase):
    def test_no_console_does_not_crash_and_logs(self):
        out, err = sys.stdout, sys.stderr
        try:
            sys.stdout = sys.stderr = None
            logsetup.setup()
            print("hello from a windowed app")
            for h in __import__("logging").getLogger().handlers:
                h.flush()
        finally:
            sys.stdout, sys.stderr = out, err
        self.assertIn("hello from a windowed app", logsetup.LOG_FILE.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
