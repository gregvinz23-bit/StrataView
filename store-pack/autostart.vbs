' StrataView store pack - silent autostart (no windows at all).
' Run once via Install-Autostart.bat, or double-click to start sharing now.
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("Wscript.Shell")
packDir = fso.GetParentFolderName(WScript.ScriptFullName)
bridgeDir = fso.BuildPath(packDir, "cloud_bridge")

' 1. Camera bridge (windowless; output is discarded).
sh.Run "pythonw.exe """ & fso.BuildPath(bridgeDir, "xmeye_cloud_to_rtsp.py") & """ --port 8090", 0, False

' 2. Phone stream (windowless).
sh.Run "pythonw.exe """ & fso.BuildPath(bridgeDir, "hlsserve.py") & """ --scale 640x360 --bitrate 0.8M", 0, False

' 3. Give the camera ~60s to log in, then open the public link (hidden).
WScript.Sleep 60000
sh.Run """C:\Program Files\Tailscale\tailscale.exe"" funnel --bg http://127.0.0.1:8091", 0, False
