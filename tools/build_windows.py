"""Build the Windows app and installer:  python tools/build_windows.py   (run on Windows).

1. PyInstaller makes dist/<Name>/<Name>.exe from zighost.spec.
2. Inno Setup (iscc) makes dist-installer/<Name>-Setup-<version>.exe, using the values in backend/brand.py.
3. A portable zip and SHA256SUMS.txt are written next to the installer.
Name, version and publisher come from backend/brand.py only."""
import hashlib
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backend import brand  # noqa: E402

OUT = ROOT / "dist-installer"


def find_iscc() -> str:
    for c in (os.environ.get("ISCC"), shutil.which("iscc"),
              r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe", r"C:\Program Files\Inno Setup 6\ISCC.exe",
              str(Path.home() / "AppData/Local/Programs/Inno Setup 6/ISCC.exe")):
        if c and Path(c).exists():
            return c
    sys.exit("Inno Setup 6 was not found. Install it from https://jrsoftware.org/isdl.php (or: winget install JRSoftware.InnoSetup).")


def run(cmd: list[str]) -> None:
    print(">", " ".join(cmd), flush=True)
    r = subprocess.run(cmd, cwd=ROOT)
    if r.returncode:
        sys.exit(r.returncode)


def main() -> None:
    if sys.platform != "win32":
        sys.exit("Run this on Windows: the exe and the installer are Windows programs.")
    iscc = find_iscc()
    run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "zighost.spec"])
    app = ROOT / "dist" / brand.NAME
    if not (app / f"{brand.NAME}.exe").exists():
        sys.exit("PyInstaller did not produce the exe.")
    OUT.mkdir(exist_ok=True)
    for old in OUT.glob("*"):
        old.unlink()
    run([iscc, "/Qp", f"/DAppName={brand.NAME}", f"/DAppVersion={brand.VERSION}", f"/DPublisher={brand.PUBLISHER}",
         f"/DCopyright={brand.COPYRIGHT.replace('©', '(c)')}", f"/DAppGuid={brand.APP_ID}", f"/DDataKey={brand.DATA_KEY}",
         str(ROOT / "installer" / "zighost.iss")])
    portable = OUT / f"{brand.NAME}-{brand.VERSION}-portable.zip"
    with zipfile.ZipFile(portable, "w", zipfile.ZIP_DEFLATED) as z:
        for f in app.rglob("*"):
            if f.is_file():
                z.write(f, Path(brand.NAME) / f.relative_to(app))
    lines = []
    for f in sorted(OUT.glob("*")):
        if f.name != "SHA256SUMS.txt":
            lines.append(f"{hashlib.sha256(f.read_bytes()).hexdigest()}  {f.name}")
    (OUT / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\nDone:")
    for f in sorted(OUT.glob("*")):
        print(f"  {f.name}  ({f.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
