"""Open every page of the dashboard in preview (demo) mode and fail on stray 'null', 'undefined' or 'NaN' text
and on JavaScript errors. Needs playwright (pip install playwright). Run: python tools/ui_smoke.py [--shots DIR]"""
from __future__ import annotations

import argparse
import re
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backend import brand  # noqa: E402

FRONT = ROOT / "frontend"
BAD = re.compile(r"\b(null|undefined|NaN|\[object Object\])\b")


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/":
            data, ctype = (FRONT / "index.html").read_text(encoding="utf-8").replace("__NAME__", brand.NAME).encode(), "text/html"
        elif path == "/brand.js":
            data, ctype = brand.js().encode(), "text/javascript"
        elif path.startswith("/static/"):
            f = (FRONT / path[len("/static/"):]).resolve()
            if FRONT not in f.parents or not f.is_file():
                self.send_error(404); return
            data = f.read_bytes()
            ctype = {"js": "text/javascript", "css": "text/css", "png": "image/png", "svg": "image/svg+xml"}.get(f.suffix[1:], "application/octet-stream")
        else:
            self.send_error(404); return
        self.send_response(200); self.send_header("Content-Type", ctype); self.end_headers(); self.wfile.write(data)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots", default="")
    ap.add_argument("--width", type=int, default=1280)
    args = ap.parse_args()
    from playwright.sync_api import sync_playwright
    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_port}/?demo"
    problems: list[str] = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": args.width, "height": 900})
        errs: list[str] = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(base)
        pg.wait_for_selector("#nav button", timeout=8000)
        pg.locator("button:visible:has-text('Open')").first.click()   # pick a server so the server pages open
        pg.wait_for_timeout(500)
        ids = pg.evaluate("Object.keys(Pages)")
        for pid in ids:
            pg.evaluate(f"go('{pid}')")
            pg.wait_for_timeout(500)
            text = pg.inner_text("body")
            for m in BAD.finditer(text):
                ctx = text[max(0, m.start() - 30): m.end() + 30].replace("\n", " ")
                problems.append(f"{pid}: stray '{m.group(0)}' near: {ctx}")
            if args.shots:
                Path(args.shots).mkdir(parents=True, exist_ok=True)
                pg.screenshot(path=f"{args.shots}/{pid}.png", full_page=True)
        # deeper screens: the file editor and the plugin search results
        def check(label):
            text = pg.inner_text("body")
            for m in BAD.finditer(text):
                problems.append(f"{label}: stray '{m.group(0)}' near: " + text[max(0, m.start() - 30): m.end() + 30].replace("\n", " "))
        pg.evaluate("api('/api/stop', { method: 'POST' }).then(() => refresh())"); pg.wait_for_timeout(1500)   # server stopped: the case that used to print null
        pg.evaluate("go('files')"); pg.wait_for_timeout(400)
        btn = pg.locator("button:has-text('Edit')").first
        if btn.count():
            btn.click(); pg.wait_for_timeout(400); check("file editor")
            if args.shots:
                pg.screenshot(path=f"{args.shots}/files-editor.png", full_page=True)
        pg.evaluate("go('plugins')"); pg.wait_for_timeout(400)
        tab = pg.locator("button:has-text('Find new')").first
        if tab.count():
            tab.click(); pg.wait_for_timeout(600); check("plugin search")
        problems += [f"JS error: {e}" for e in errs]
        b.close()
    for x in problems:
        print("FAIL", x)
    print("pages checked:", len(ids), "problems:", len(problems))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
