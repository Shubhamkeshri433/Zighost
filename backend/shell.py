"""The Windows app shell: a native window (Edge WebView2 through pywebview) and a tray icon (pystray).

Both libraries are optional. Without pywebview the page opens in the default browser; without pystray there is no tray
and closing the window quits. run() returns False when neither exists so the caller can use plain browser mode."""
from __future__ import annotations

import logging
import threading
import webbrowser
from typing import Callable

from . import brand, paths

log = logging.getLogger(brand.DATA_KEY)


def _import(name: str):
    try:
        return __import__(name)
    except Exception:  # noqa: BLE001 - missing, or fails to load on this machine
        return None


class Api:
    """Small bridge the page may call (window.pywebview.api)."""

    def open_external(self, url: str) -> bool:
        if isinstance(url, str) and url.startswith(("https://", "http://")) and len(url) < 2000:
            webbrowser.open(url)
            return True
        return False


SPLASH = """<!doctype html><meta charset="utf-8"><title>%(name)s</title>
<style>html,body{margin:0;height:100%%;background:#10141d;color:#e8edf5;font:15px 'Segoe UI',system-ui,sans-serif;overflow:hidden}
body{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:14px;border:1px solid #2a3243;box-sizing:border-box}
svg{width:72px;height:72px}h1{margin:0;font-size:22px;font-weight:600;letter-spacing:.2px}
p{margin:0;color:#8c97ab;font-size:13px}.bar{width:150px;height:3px;background:#222a3a;border-radius:2px;overflow:hidden}
.bar i{display:block;width:40%%;height:100%%;background:#5ccf57;animation:m 1.1s ease-in-out infinite}
@keyframes m{0%%{margin-left:-40%%}100%%{margin-left:100%%}}</style>
<svg viewBox="0 0 100 100"><rect width="100" height="100" rx="22" fill="#10141d" stroke="#2a3243"/><g shape-rendering="crispEdges" transform="translate(20 17.5) scale(5)"><path fill="#5ccf57" d="M4 0h4v1h-4zM2 1h8v1h-8zM1 2h10v2h-10zM0 4h12v7h-12zM0 11h3v1h-3zM4 11h4v1h-4zM9 11h3v1h-3zM0 12h2v1h-2zM5 12h2v1h-2zM10 12h2v1h-2z"/><path fill="#10141d" d="M3 5h2v2h-2zM7 5h2v2h-2z"/></g></svg>
<h1>%(name)s</h1><div class="bar"><i></i></div><p>Starting...</p>"""


class Shell:
    def __init__(self, url: str, on_quit: Callable[[], None], status: Callable[[], str],
                 stop_servers: Callable[[], None], background: bool = False, webview=None, pystray=None,
                 wait_ready: Callable[[], bool] | None = None) -> None:
        self.wait_ready = wait_ready
        self.failed = False
        self.splash = None
        self._navigated = False
        self._loaded = threading.Event()
        self.url, self.on_quit, self.status, self.stop_servers = url, on_quit, status, stop_servers
        self.background = background
        self.webview = webview if webview is not None else _import("webview")
        self.pystray = pystray if pystray is not None else _import("pystray")
        self.window = None
        self.icon = None
        self.quitting = False
        self.hint_shown = False
        self._quit_evt = threading.Event()

    # ---- tray ---------------------------------------------------------------------------------------------------
    def _make_icon(self):
        if not self.pystray:
            return None
        try:
            from PIL import Image
            img = Image.open(paths.FRONTEND / "brand" / "icon-256.png")
            ps = self.pystray
            menu = ps.Menu(
                ps.MenuItem(f"Open {brand.NAME}", lambda *_: self.show(), default=True),
                ps.MenuItem(lambda item: self.status(), None, enabled=False),
                ps.Menu.SEPARATOR,
                ps.MenuItem("Stop all servers", lambda *_: threading.Thread(target=self.stop_servers, daemon=True).start()),
                ps.MenuItem(f"Quit {brand.NAME}", lambda *_: self.quit()))
            return ps.Icon(brand.DATA_KEY, img, brand.NAME, menu)
        except Exception:  # noqa: BLE001
            log.exception("tray icon could not start")
            return None

    def notify(self, title: str, text: str) -> None:
        if self.icon is not None:
            try:
                self.icon.notify(text[:250], title)
            except Exception:  # noqa: BLE001
                log.exception("tray notice failed")

    # ---- window -------------------------------------------------------------------------------------------------
    def show(self) -> bool:
        if self.window is None:
            webbrowser.open(self.url)
            return False
        try:
            self.window.show()
            self.window.restore()
            return True
        except Exception:  # noqa: BLE001
            log.exception("could not show the window")
            return False

    def _closing(self) -> bool:
        """pywebview calls this when the window is closed. False cancels the close: hide to the tray instead."""
        if self.quitting or self.icon is None:
            return True
        try:
            self.window.hide()
        except Exception:  # noqa: BLE001
            return True
        if not self.hint_shown:
            self.hint_shown = True
            self.notify(brand.NAME, "Still running in the tray. Servers keep running. Right-click the icon to quit.")
        return False

    def quit(self) -> None:
        if self.quitting:
            return
        self.quitting = True
        self.notify(brand.NAME, "Stopping servers safely, then closing.")
        self.on_quit()                      # starts the safe shutdown of servers (world saved)
        for w in (self.splash, self.window):
            try:
                if w is not None:
                    w.destroy()
            except Exception:  # noqa: BLE001
                pass
        self._quit_evt.set()

    def _boot(self) -> None:
        """Runs once the native loop is up: wait for the server, then swap the small splash for the full window."""
        ok = self.wait_ready() if self.wait_ready else True
        if not ok:
            log.error("the server did not start")
            self.failed = True
            self.quit()
            return
        try:
            self._navigated = True
            self.window.load_url(self.url)
            self._loaded.wait(20)
            if not self.background:
                self.window.maximize()
                self.window.show()
        except Exception:  # noqa: BLE001
            log.exception("could not open the window")
        finally:
            try:
                if self.splash is not None:
                    self.splash.destroy()
            except Exception:  # noqa: BLE001
                pass

    def run(self) -> bool:
        """Blocks until the app is quit. False: no window and no tray library, caller should use browser mode."""
        self.icon = self._make_icon()
        if self.icon is not None:
            self.icon.run_detached()
        if self.webview is not None:
            try:
                if hasattr(self.webview, "settings"):
                    self.webview.settings["ALLOW_DOWNLOADS"] = True
                if not self.background:
                    self.splash = self.webview.create_window(brand.NAME, html=SPLASH % {"name": brand.NAME}, width=380, height=250,
                                                             frameless=True, easy_drag=True, resizable=False, on_top=True)
                # The real window starts hidden and maximized (full screen area, not floating); people can restore it.
                self.window = self.webview.create_window(brand.NAME, html="<body style='background:#10141d'></body>", hidden=True,
                                                         maximized=True, min_size=(980, 640), js_api=Api(), text_select=True)
                self.window.events.closing += self._closing
                self.window.events.loaded += lambda *_: self._loaded.set() if self._navigated else None
                self.webview.start(self._boot)      # main thread; returns after destroy()
                if self.quitting or self.icon is None:
                    self._stop_icon()
                    return True
                self._quit_evt.wait()       # window ended some other way: stay in the tray
                self._stop_icon()
                return True
            except Exception:  # noqa: BLE001 - no WebView2 or it failed: use the browser, keep the tray
                log.exception("native window failed, using the browser")
                self.window = None
        if self.icon is None:
            return False
        if self.wait_ready and not self.wait_ready():
            self.failed = True
            self._stop_icon()
            return True
        if not self.background:
            webbrowser.open(self.url)
        self._quit_evt.wait()
        self._stop_icon()
        return True

    def _stop_icon(self) -> None:
        if self.icon is not None:
            try:
                self.icon.stop()
            except Exception:  # noqa: BLE001
                pass
