@echo off
REM StrataView store pack - one-time setup. Right-click -> Run as administrator.
cd /d %~dp0
echo [1/3] Installing Python...
python-installer.exe /quiet InstallAllUsers=0 PrependPath=1 Include_pip=1 Include_test=0
echo [2/3] Installing Tailscale...
tailscale-setup.exe /S
echo [3/3] Preparing camera login file...
if not exist cloud_bridge\_credentials.py (
  copy cloud_bridge\_credentials_TEMPLATE.py cloud_bridge\_credentials.py >nul
  echo Created cloud_bridge\_credentials.py
)
echo.
echo Setup finished. Next steps:
echo   1. Open cloud_bridge\_credentials.py in Notepad and set DEVICE_PASS.
echo   2. In a terminal run:  tailscale up   (sign in in the browser once)
echo   3. Double-click start-viewing.bat and share the link it prints.
pause
