"""
XMeye CCTV live viewer using OpenIPC python-dvr (dvrip) + OpenCV.

Fill in your credentials below, then run:
    python app.py

Press 'q' in the video window to quit.

NOTE on P2P / CLOUD_ID:
  The `dvrip` / `DVRIPCam` library speaks the DVRIP (Sofia) protocol over
  a direct TCP connection (default port 34567). It does NOT implement
  XiongMai's proprietary P2P cloud relay (xmeye.net).
  So `CLOUD_ID` below only works if it resolves to a reachable host/IP,
  e.g. via port-forwarding, VPN, or same-LAN, or if your NVR exposes
  the DVRIP port publicly. For true P2P (serial-number relay without
  port forwarding) you need the vendor XMeye app/SDK or an RTSP relay -
  python-dvr cannot do that.
"""
import cv2
import numpy as np
from dvrip import DVRIPCam

# ---- Fill these in ----
CLOUD_ID = "YOUR_P2P_CLOUD_ID_OR_IP"  # e.g. "192.168.1.10" or DDNS hostname
USERNAME = "admin"
PASSWORD = "YOUR_PASSWORD"
# ------------------------

PORT = 34567  # default DVRIP TCP port


def main():
    print(f"Connecting to {CLOUD_ID}:{PORT} as '{USERNAME}' ...")
    cam = DVRIPCam(CLOUD_ID, port=PORT, user=USERNAME, password=PASSWORD)

    try:
        if not cam.login():
            print("Failure. Could not log in - check CLOUD_ID / USERNAME / PASSWORD and network.")
            return
        print("Success! Logged in.")
        print("Camera time:", cam.get_time())
    except Exception as e:
        print(f"Connection failed: {e}")
        print("Tip: dvrip needs a direct TCP route to the camera. "
              "Cloud P2P serial numbers alone won't route without port-forward/VPN.")
        return

    cv2.namedWindow("XMeye Live Stream", cv2.WINDOW_NORMAL)

    try:
        # Snapshot-polling loop: cam.snapshot() returns JPEG bytes,
        # which OpenCV can decode reliably without ffmpeg plumbing.
        # For raw H264/H265 recording see cam.start_monitor() example below.
        while True:
            try:
                img_bytes = cam.snapshot(channel=0)
            except Exception as e:
                print(f"Snapshot failed: {e}")
                break

            if not img_bytes:
                print("Empty frame received.")
                continue

            frame = cv2.imdecode(np.frombuffer(img_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
            if frame is None:
                print("Could not decode frame.")
                continue

            cv2.imshow("XMeye Live Stream", frame)

            # Quit on 'q'
            if cv2.waitKey(1) & 0xFF == ord('q'):
                print("'q' pressed - exiting.")
                break
    except KeyboardInterrupt:
        print("Interrupted by user.")
    finally:
        try:
            cam.close()
        except Exception:
            pass
        cv2.destroyAllWindows()
        print("Closed connection and windows.")

    # --- Alternative: raw H264/H265 stream to file ---
    # with open("datastream.h265", "wb") as f:
    #     cam2 = DVRIPCam(CLOUD_ID, port=PORT, user=USERNAME, password=PASSWORD)
    #     if cam2.login():
    #         cam2.start_monitor(lambda frame, meta, user: f.write(frame))
    #     cam2.close()


if __name__ == "__main__":
    main()
