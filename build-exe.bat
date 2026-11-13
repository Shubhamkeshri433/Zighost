@echo off
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo Python is not installed. Get it from python.org, tick "Add Python to PATH", then run this again.
  pause
  exit /b 1
)
python --version
echo Building Zighost.exe. This takes a few minutes and needs internet the first time.
if not exist ".venv\Scripts\python.exe" python -m venv .venv
".venv\Scripts\python.exe" -m pip install -q -r requirements.txt pyinstaller
if errorlevel 1 goto fail
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean zighost.spec
if errorlevel 1 goto fail
echo.
echo Done. Your app is in dist\Zighost\Zighost.exe
start "" "dist\Zighost"
pause
exit /b 0
:fail
echo Build failed. Send me the text above.
pause
exit /b 1
