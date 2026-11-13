# Zighost

Host Minecraft servers on your own Windows PC. Local dashboard, native window, tray icon, public address through playit.gg.

## Run from source (Windows)
    start.bat            # opens in the browser
    start-window.bat     # native window + tray

## Build the installer (Windows)
    python -m pip install -r requirements.txt pyinstaller
    python tools/build_windows.py     # needs Inno Setup 6 (winget install JRSoftware.InnoSetup)

Output goes to `dist-installer/`: `Zighost-Setup-<version>.exe`, a portable zip and `SHA256SUMS.txt`.
Or push a tag (`git tag v0.1.0 && git push origin v0.1.0`) and GitHub Actions builds it and attaches it to a draft Release.

Name, version and publisher are set only in `backend/brand.py`. Never change `DATA_KEY` or `APP_ID` there.
Plan and decisions: `PLAN.md`.
