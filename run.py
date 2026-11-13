"""Start the app: python run.py   (the packaged Windows app starts here too)."""
import os
import signal
import sys
import threading
import time
import webbrowser


def _hide_console() -> None:
    """The packaged exe is a console program (it starts reliably); its black window is hidden at once."""
    if getattr(sys, "frozen", False) and os.name == "nt" and "--console" not in sys.argv:
        try:
            import ctypes
            hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, 0)
        except Exception:  # noqa: BLE001
            pass


_hide_console()

import uvicorn

from backend import brand, instance, logsetup

HOST = instance.HOST


def _install_shutdown_hooks(server: uvicorn.Server, done: threading.Event) -> None:
    """Closing the window, logging off or Ctrl+Break must stop Minecraft servers safely (worlds saved)."""
    def stop(*_):
        server.should_exit = True

    for name in ("SIGTERM", "SIGBREAK"):
        if hasattr(signal, name):
            try:
                signal.signal(getattr(signal, name), stop)
            except (ValueError, OSError):
                pass
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        handler_t = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.DWORD)

        def handler(ctrl):
            if ctrl in (2, 5, 6):             # close, log off, shut down
                server.should_exit = True
                done.wait(4.5)                # Windows gives a console about 5 seconds
                return True
            return False

        global _keep
        _keep = handler_t(handler)
        ctypes.windll.kernel32.SetConsoleCtrlHandler(_keep, True)


def _wait_ready(url: str, timeout: float = 30.0) -> bool:
    port = int(url.rsplit(":", 1)[1])
    end = time.time() + timeout
    while time.time() < end:
        if instance._ping(port):
            return True
        time.sleep(0.2)
    return False


def main() -> int:
    log = logsetup.setup()
    args = sys.argv[1:]
    preferred = int(os.environ.get("ZIGHOST_PORT") or os.environ.get("MCPANEL_PORT") or "8765")
    window = ("--window" in args or getattr(sys, "frozen", False)) and "--browser" not in args and "--no-browser" not in args
    other = instance.claim(preferred)
    if other:
        print(f"{brand.NAME} is already open.")
        log.info("already running at %s", other)
        if not instance.request_show(other) and "--no-browser" not in args:
            webbrowser.open(other)
        return 0
    port = instance.choose_port(preferred)
    if port != preferred:
        log.info("port %s was busy, using %s", preferred, port)
    from backend import app as backend_app          # imported here so a second copy never starts the backend
    server = uvicorn.Server(uvicorn.Config(backend_app.app, host=HOST, port=port, log_level="warning", log_config=None))
    done = threading.Event()
    _install_shutdown_hooks(server, done)
    instance.publish(port)
    url = f"http://localhost:{port}"
    try:
        if window:
            return _run_window(server, url, backend_app, "--background" in args, log)
        if "--no-browser" not in args:
            threading.Thread(target=lambda: (time.sleep(1.2), webbrowser.open(url)), daemon=True).start()
        print(f"{brand.NAME} {brand.VERSION} is running at {url}  (press Ctrl+C to quit, servers are stopped safely)")
        server.run()
    finally:
        done.set()
        log.info("stopped")
    return 0


def _run_window(server, url, backend_app, background, log) -> int:
    """Native window + tray. The server runs in a thread; this (main) thread belongs to the window."""
    from backend.shell import Shell
    t = threading.Thread(target=server.run, name="server")
    t.start()
    mgr = backend_app.manager

    def status() -> str:
        sid = mgr.active_id
        meta = backend_app.get_server(sid) if sid else None
        return f"{meta['name']}: {mgr.state}" if meta and mgr.state != "offline" else "No server running"

    def stop_servers() -> None:
        try:
            mgr.stop()
        except Exception:  # noqa: BLE001
            log.exception("stop from the tray failed")

    shell = Shell(url, on_quit=lambda: setattr(server, "should_exit", True), status=status, stop_servers=stop_servers,
                  background=background, wait_ready=lambda: _wait_ready(url))
    instance.show_callback = shell.show
    backend_app.monitor.notifier = shell.notify
    ran = shell.run()
    if shell.failed:
        server.should_exit = True
        t.join(10)
        return 1
    if not ran:                                     # neither window nor tray library: plain browser mode
        if not _wait_ready(url):
            server.should_exit = True
            t.join(10)
            return 1
        print(f"{brand.NAME} is running at {url}  (press Ctrl+C to quit)")
        webbrowser.open(url)
        try:
            while t.is_alive():
                t.join(0.5)
        except KeyboardInterrupt:
            server.should_exit = True
    server.should_exit = True
    t.join(180)                                     # servers are stopped safely before the process ends
    return 0


if __name__ == "__main__":
    sys.exit(main())
