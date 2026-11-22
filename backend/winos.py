"""Windows-only helpers (ctypes and the registry). Every function is safe to call anywhere: off Windows it does nothing."""
from __future__ import annotations

import base64
import logging
import os
import sys
import threading

from . import brand

log = logging.getLogger(brand.DATA_KEY)
IS_WINDOWS = os.name == "nt"


# ---- keep the PC awake while a server runs -----------------------------------------------------------------------
class KeepAwake:
    """SetThreadExecutionState works per thread, so one small thread holds the request until it is released."""
    ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001

    def __init__(self) -> None:
        self._on = False
        self._stop: threading.Event | None = None

    @property
    def active(self) -> bool:
        return self._on

    def set(self, on: bool) -> None:
        if on == self._on:
            return
        self._on = on
        if not IS_WINDOWS:
            return
        if on:
            self._stop = threading.Event()
            threading.Thread(target=self._hold, args=(self._stop,), daemon=True, name="keep-awake").start()
        elif self._stop:
            self._stop.set()

    def _hold(self, stop: threading.Event) -> None:
        import ctypes
        k = ctypes.windll.kernel32
        k.SetThreadExecutionState(self.ES_CONTINUOUS | self.ES_SYSTEM_REQUIRED)
        stop.wait()
        k.SetThreadExecutionState(self.ES_CONTINUOUS)


# ---- Windows 11 "efficiency mode" must not slow the panel or Java down -----------------------------------------------
def disable_throttling(pid: int | None = None) -> bool:
    """Ask Windows not to throttle this process (or pid) when the window is hidden or minimised."""
    if not IS_WINDOWS:
        return False
    try:
        import ctypes
        from ctypes import wintypes

        class STATE(ctypes.Structure):
            _fields_ = [("Version", wintypes.ULONG), ("ControlMask", wintypes.ULONG), ("StateMask", wintypes.ULONG)]

        k = ctypes.windll.kernel32
        k.OpenProcess.restype = wintypes.HANDLE
        h = k.GetCurrentProcess() if pid is None else k.OpenProcess(0x0200, False, int(pid))   # PROCESS_SET_INFORMATION
        if not h:
            return False
        try:
            st = STATE(1, 0x1, 0x0)          # version 1, control EXECUTION_SPEED, state 0 = throttling off
            return bool(k.SetProcessInformation(h, 4, ctypes.byref(st), ctypes.sizeof(st)))   # ProcessPowerThrottling
        finally:
            if pid is not None:
                k.CloseHandle(h)
    except Exception:  # noqa: BLE001 - never stop the app over an optimisation
        log.exception("could not switch off power throttling")
        return False


# ---- start with Windows (current user only, no admin) ---------------------------------------------------------------
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def autostart_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --background'
    exe = sys.executable.replace("python.exe", "pythonw.exe")
    return f'"{exe}" "{os.path.abspath(sys.argv[0])}" --window --background'


def autostart_get() -> bool:
    if not IS_WINDOWS:
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, brand.NAME)
            return True
    except OSError:
        return False


def autostart_set(on: bool) -> None:
    if not IS_WINDOWS:
        return
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, brand.NAME, 0, winreg.REG_SZ, autostart_command())
        else:
            try:
                winreg.DeleteValue(k, brand.NAME)
            except FileNotFoundError:
                pass


# ---- secrets at rest: Windows DPAPI, readable only by this Windows user -------------------------------------------------
PREFIX = "dpapi:"


def _blob(data: bytes):
    import ctypes
    from ctypes import wintypes

    class BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]
    buf = ctypes.create_string_buffer(data, len(data))
    return BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))), buf, BLOB


def _dpapi(data: bytes, protect: bool) -> bytes:
    import ctypes
    inp, keep, BLOB = _blob(data)
    out = BLOB()
    f = ctypes.windll.crypt32.CryptProtectData if protect else ctypes.windll.crypt32.CryptUnprotectData
    ok = f(ctypes.byref(inp), None, None, None, None, 0, ctypes.byref(out))
    if not ok:
        raise OSError("DPAPI failed")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(out.pbData)


class SealError(Exception):
    """A secret could not be encrypted. Callers must not store it in plain text."""


def seal(text: str) -> str:
    """Encrypt for storage. Off Windows nothing can be encrypted, so the text is returned as it is (development only).
    On Windows a failure raises SealError: a secret is never stored in plain text as a fallback."""
    if not text or text.startswith(PREFIX) or not IS_WINDOWS:
        return text
    try:
        return PREFIX + base64.b64encode(_dpapi(text.encode("utf-8"), True)).decode("ascii")
    except (OSError, ValueError) as e:
        log.error("could not encrypt a secret, it was not saved")
        raise SealError("The secret could not be encrypted, so it was not saved.") from e


def unseal(text: str) -> str:
    if not text or not text.startswith(PREFIX):
        return text              # plain text from an older version: accepted, encrypted on the next save
    try:
        return _dpapi(base64.b64decode(text[len(PREFIX):]), False).decode("utf-8")
    except (OSError, ValueError):
        log.warning("a saved secret could not be read (different Windows user?)")
        return ""


# ---- see-through window (Windows 11 22H2 or newer) ---------------------------------------------------------------
GLASS_BUILD = 22621       # first Windows 11 build with the system backdrop setting (Acrylic and Mica)


def glass_supported() -> bool:
    """True on a Windows that can blur the desktop behind a window. Everywhere else the plain dark look is used."""
    if not IS_WINDOWS:
        return False
    try:
        return sys.getwindowsversion().build >= GLASS_BUILD
    except Exception:  # noqa: BLE001
        return False


def apply_backdrop(title: str, hwnd: int = 0) -> bool:
    """Give the window (its handle, else the one with this title) the Acrylic backdrop and a dark frame. False if refused."""
    if not glass_supported():
        return False
    try:
        import ctypes
        from ctypes import wintypes
        user32, dwm = ctypes.windll.user32, ctypes.windll.dwmapi
        user32.FindWindowW.restype = wintypes.HWND
        hwnd = hwnd or user32.FindWindowW(None, title)
        if not hwnd:
            return False

        class MARGINS(ctypes.Structure):
            _fields_ = [("l", ctypes.c_int), ("r", ctypes.c_int), ("t", ctypes.c_int), ("b", ctypes.c_int)]

        def attr(code: int, value: int) -> int:
            v = ctypes.c_int(value)
            return dwm.DwmSetWindowAttribute(hwnd, code, ctypes.byref(v), ctypes.sizeof(v))

        attr(20, 1)                                   # DWMWA_USE_IMMERSIVE_DARK_MODE
        m = MARGINS(-1, -1, -1, -1)
        dwm.DwmExtendFrameIntoClientArea(hwnd, ctypes.byref(m))
        return attr(38, 3) == 0                       # DWMWA_SYSTEMBACKDROP_TYPE = transient window (Acrylic)
    except Exception:  # noqa: BLE001
        log.exception("could not turn on the window backdrop")
        return False
