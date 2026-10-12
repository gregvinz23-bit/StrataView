StrataView store pack - view the shop camera from any phone
=============================================================

WHAT YOU NEED ON THIS PC
  - Windows 10 or 11, internet access, this PC stays ON while viewing.
  - Administrator rights for the one-time setup.

ONE-TIME SETUP (about 10 minutes)
  1. Right-click setup.bat -> "Run as administrator". Wait until it says
     "Setup finished."
  2. Open the folder cloud_bridge, open _credentials.py in Notepad.
     Set DEVICE_PASS to the camera admin password (same as the VMS app).
     Save and close. CLOUD_ID and user are already filled in.
  3. Open a terminal (press Win+R, type cmd, Enter) and run:
       tailscale up
     Sign in with the shop Tailscale account in the browser that opens.
     (One account for the shop; viewers do NOT need anything installed.)

EVERY DAY (when you want the camera viewable)
  1. Double-click start-viewing.bat.
  2. Wait about a minute. It prints an https link ending in .ts.net.
  3. Open https://THAT-ADDRESS/live.m3u8 on any phone browser.
     The picture is 640 wide so it stays smooth. There is about a
     10 second delay. That is normal.
  4. Keep this PC on. Close the black windows to stop sharing.

START AUTOMATICALLY (optional, recommended)
  1. Double-click Install-Autostart.bat once.
  2. From then on, sharing starts by itself on every logon with no
     windows popping up at all.
     (Set Windows to log on automatically after a reboot, otherwise it
     waits for somebody to log on first.)

IF IT DOES NOT WORK
  - "Login failed" in the Bridge window: wrong DEVICE_PASS in
    cloud_bridge\_credentials.py. Fix it and restart start-viewing.bat.
  - Phone says the site cannot be reached: wait 3 minutes and retry.
    If it still fails, the link changed - read the new one from the
    start-viewing window.
  - Only one viewer session at a time per camera: close the vendor VMS
    on this camera while sharing.

FILES IN THIS FOLDER - do not move or rename them.
