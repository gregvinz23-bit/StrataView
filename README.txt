StrataView - local and cloud video management
=============================================

WHAT THIS IS
  StrataView is a desktop app for viewing and recording IP cameras:
  XMeye / DVRIP cameras (by LAN address or CloudID) and generic
  RTSP cameras. Live grid, snapshots, recording and playback.

HOW TO RUN
  Double-click StrataView.exe. No installation is required.
  On first launch with no cameras, a setup wizard will guide you.
  The first connection to a cloud camera can take up to 30 seconds.

WHAT IS IN THIS FOLDER
  StrataView.exe      The application (double-click to start).
  cameras.json        Your camera list. You can also manage cameras
                      from the toolbar (Add Device / Edit / Remove).
  recordings/         Recorded clips, one folder per camera.
  snapshots/          Still images captured with the Snapshot button.
  cloudbridge/        Helper files for CloudID connections.
                      Do not move, rename or delete this folder.
  _internal/          Application files. Do not modify.

NOTES
  - Keep this folder together; the exe will not run if moved alone.
  - While StrataView is connected to a cloud camera, do not open
    the vendor VMS on the same camera at the same time. The camera
    accepts one remote session and the two will interfere.
  - Your camera passwords are stored in cameras.json on this machine.

SUPPORT
  Version and update check: toolbar -> About -> Check for updates.
