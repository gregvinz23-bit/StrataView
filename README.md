# StrataView

Local + cloud video management for XMeye / DVRIP and RTSP cameras.
Live grid, snapshots, recording, playback — desktop app (Python + PyQt6),
plus a portable Windows build.

## Features

- Live grid (1, 2×2, 3×3) with camera list sidebar and status indicators
- CloudID (P2P) cameras via the bundled bridge (vendor NetSdk login),
  direct DVRIP over LAN, and generic RTSP
- Recording with configurable segments, playback with seek, snapshots
- Event log with export, per-tile Retry on failures, fullscreen camera view
- Setup wizard, splash screen, settings, update check, dark theme

## Run from source (Windows)

```bat
pip install -r requirements.txt
copy cameras.example.json cameras.json
copy cloud_bridge\SAMPLE_credentials.py cloud_bridge\_credentials.py
python vms_app.py
```

Edit `cameras.json` (or use Add Device in the app) with your cameras.

## CloudID setup

The file `cloud_bridge/xmeye_cloud_to_rtsp.py` logs in through the
vendor `NetSdk.dll` (same handshake as the vendor VMS) and serves the
camera locally. It needs, next to itself:

- `NetSdk.dll`, `StreamReader.dll`, `H264Play.dll`
  (2018-era pair; the 2024 DLL from newer VMS builds fails cloud login)
- `ffmpeg.exe` — use a full build (the one shipped with the vendor VMS
  works; minimal/editor-bundled builds may lack network serving)
- `_credentials.py` — copy of `SAMPLE_credentials.py` with your
  CloudID, username and password (never commit this file)

The small DLLs are included here. `ffmpeg.exe` / `mediamtx.exe` are not
(too large) — source them as described above. Bridge provenance and
protocol findings are documented in `cloud_bridge/README.md`.

## Portable build

Built with PyInstaller (see `build/` — not committed):

```bat
python -m PyInstaller --noconfirm --clean --noconsole --onedir ^
  --name StrataView --icon assets\ICON.ico --add-data assets;assets vms_app.py
```

The bridge runner is frozen separately from `cloud_bridge/` and both
are assembled with the SDK folder, `ffmpeg.exe`, and `cameras.json`
into a runnable folder. Details of the exact assembly/trim steps live
outside this repo for now — ask the maintainer.

## Notes

- A camera accepts one remote P2P session: close the vendor VMS (or any
  second copy of this app) before connecting to the same CloudID twice.
- Camera passwords live in `cameras.json` / `cloud_bridge/_credentials.py`
  on your machine. Never commit those files.
- Personal-use project by Mantraix Software Solution.
  Support: MantraixSoftwareSolutions@gmail.com
