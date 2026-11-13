# PyInstaller recipe: one folder with Zighost.exe (no console window). Built by tools/build_windows.py or build-exe.bat.
import os, sys
sys.path.insert(0, os.path.abspath("."))
from PyInstaller.utils.hooks import collect_submodules
from backend import brand

hidden = collect_submodules("uvicorn") + collect_submodules("webview") + collect_submodules("pystray") + ["PIL.Image", "starlette.routing"]


def _version_file():
    """Name, publisher and version shown in the exe's Properties > Details. Optional: the build still works without it."""
    try:
        from PyInstaller.utils.win32.versioninfo import (FixedFileInfo, StringFileInfo, StringStruct, StringTable,
                                                         VarFileInfo, VarStruct, VSVersionInfo)
        v = tuple(int(x) for x in brand.VERSION.split(".")[:3]) + (0,) * (4 - len(brand.VERSION.split(".")[:3]))
        info = VSVersionInfo(
            ffi=FixedFileInfo(filevers=v, prodvers=v, mask=0x3F, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0),
            kids=[StringFileInfo([StringTable("040904B0", [
                StringStruct("CompanyName", brand.PUBLISHER), StringStruct("FileDescription", brand.NAME),
                StringStruct("FileVersion", brand.VERSION), StringStruct("InternalName", brand.DATA_KEY),
                StringStruct("LegalCopyright", brand.COPYRIGHT), StringStruct("OriginalFilename", brand.NAME + ".exe"),
                StringStruct("ProductName", brand.NAME), StringStruct("ProductVersion", brand.VERSION)])]),
                VarFileInfo([VarStruct("Translation", [1033, 1200])])])
        os.makedirs("build", exist_ok=True)
        path = os.path.join("build", "version_info.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(str(info))
        return path
    except Exception as e:  # noqa: BLE001
        print("version info skipped:", e)
        return None


a = Analysis(["run.py"], pathex=["."], datas=[("frontend", "frontend")], hiddenimports=hidden, excludes=["tkinter", "unittest", "pytest"])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name=brand.NAME, console=False, icon="assets/brand/zighost.ico",
          version=_version_file())
coll = COLLECT(exe, a.binaries, a.datas, name=brand.NAME)
