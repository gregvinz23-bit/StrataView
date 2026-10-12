@echo off
REM StrataView store pack - start sharing minimized. Usage: start-viewing.bat [/auto]
if "%1"=="/auto" goto run
if not defined MINIMIZED (set MINIMIZED=1 & start /min "" "%~f0" %* & exit /b)
:run
cd /d %~dp0\cloud_bridge
echo Starting camera bridge (login can take up to 30 seconds)...
start "Bridge" /min python xmeye_cloud_to_rtsp.py --port 8090
echo Starting phone stream (640 wide for smooth viewing)...
start "HLS" /min pythonw hlsserve.py --scale 640x360 --bitrate 0.8M
echo Waiting for video (60 seconds)...
timeout /t 60 /nobreak >nul
echo Opening public link...
"%ProgramFiles%\Tailscale\tailscale.exe" funnel --bg http://127.0.0.1:8091
echo.
echo Done. Open the https link above + /live.m3u8 on any phone browser.
echo Example: https://YOUR-PC-NAME.ts.net/live.m3u8
echo Keep this PC on while viewers watch.
if "%1"=="/auto" exit /b
pause
