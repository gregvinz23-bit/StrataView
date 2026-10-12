@echo off
REM StrataView store pack - start sharing automatically when this user logs on.
REM Windowless: registers autostart.vbs (no console windows, ever).
REM No administrator rights needed. Run once.
set SHORTCUT=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\StrataView-Sharing.lnk
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%SHORTCUT%'); $s.TargetPath='wscript.exe'; $s.Arguments='\"%~dp0autostart.vbs\"'; $s.WorkingDirectory='%~dp0'; $s.Save()"
echo Done. Sharing now starts silently on every logon - no windows pop up.
echo (Windows must log on by itself after a reboot; otherwise sharing
echo  waits for somebody to log on first.)
pause
