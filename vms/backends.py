"""StrataView VMS camera sources: DVRIP (XMeye) + generic RTSP + P2P cloud bridge."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import cv2
import numpy as np

# Prefer TCP for RTSP (more reliable than UDP through routers/firewalls).
os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")

BRIDGE_SCRIPT = Path(__file__).resolve().parent.parent / "cloud_bridge" / "xmeye_cloud_to_rtsp.py"
BRIDGE_BASE_PORT = 8090
_bridge_ports_in_use: set[int] = set()
_bridge_ports_lock = threading.Lock()


def alloc_bridge_port() -> int:
    with _bridge_ports_lock:
        port = BRIDGE_BASE_PORT
        while port in _bridge_ports_in_use:
            port += 1
        _bridge_ports_in_use.add(port)
        return port


def free_bridge_port(port: int) -> None:
    with _bridge_ports_lock:
        _bridge_ports_in_use.discard(port)


class BaseSource:
    """Polling frame source running its own thread.

    Subclasses implement `_next_frame()` which returns a BGR ndarray
    or None, and may block briefly. The latest good frame is kept in
    a buffer for the GUI / recorder to pull via `latest()`.
    """

    poll_interval = 0.05

    def __init__(self, name: str):
        self.name = name
        self._frame: np.ndarray | None = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._status = "stopped"
        self._status_lock = threading.Lock()
        self.frame_count = 0
        self.last_frame_time = 0.0

    # -- lifecycle -----------------------------------------------------
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._set_status("Connecting…")
        self._thread = threading.Thread(
            target=self._loop, name=f"src-{self.name}", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        try:
            self._close()
        except Exception:
            pass
        self._set_status("stopped")

    # -- consumer API ---------------------------------------------------
    def latest(self) -> np.ndarray | None:
        with self._lock:
            return None if self._frame is None else self._frame.copy()

    @property
    def status(self) -> str:
        with self._status_lock:
            return self._status

    # -- internals ------------------------------------------------------
    def _set_status(self, text: str) -> None:
        with self._status_lock:
            self._status = text

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                frame = self._next_frame()
            except Exception as exc:  # never let the thread die
                self._set_status(f"error: {exc}")
                frame = None
            if frame is not None:
                with self._lock:
                    self._frame = frame
                self.frame_count += 1
                self.last_frame_time = time.time()
                self._set_status("live")
            self._stop.wait(self.poll_interval)

    def _next_frame(self) -> np.ndarray | None:
        raise NotImplementedError

    def _close(self) -> None:
        pass


class RtspSource(BaseSource):
    """Generic RTSP/HTTP/USB source via OpenCV (FFmpeg backend)."""

    poll_interval = 0.03

    def __init__(self, name: str, url: str):
        super().__init__(name)
        self.url = url
        self._cap: cv2.VideoCapture | None = None
        self._fail_count = 0

    def _open(self) -> None:
        self._close()
        cap = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 2)
        if cap.isOpened():
            self._cap = cap
            self._fail_count = 0
        else:
            cap.release()
            self._cap = None

    def _next_frame(self) -> np.ndarray | None:
        if self._cap is None:
            self._set_status("Connecting…")
            self._open()
            # Back off so a dead camera doesn't spin the CPU.
            self._fail_count += 1
            time.sleep(min(2 + self._fail_count, 10))
            return None
        ok, frame = self._cap.read()
        if not ok or frame is None:
            self._set_status("Reconnecting…")
            self._close()
            return None
        return frame

    def _close(self) -> None:
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None


class DvripSource(BaseSource):
    """XMeye / DVRIP (Sofia) camera via snapshot polling.

    `dvrip` cannot do raw-stream decode without extra plumbing, but its
    JPEG snapshot endpoint decodes reliably with OpenCV. Polls a few
    times per second — fine for a grid view; use RTSP for full fps.
    NOTE: needs a direct TCP route to the camera (no P2P cloud relay).
    """

    poll_interval = 0.2

    def __init__(
        self,
        name: str,
        host: str,
        user: str = "admin",
        password: str = "",
        port: int = 34567,
        channel: int = 0,
    ):
        super().__init__(name)
        self.host = host
        self.user = user
        self.password = password
        self.port = port
        self.channel = channel
        self._cam = None
        self._fail_count = 0

    def _open(self) -> bool:
        from dvrip import DVRIPCam

        self._close()
        cam = DVRIPCam(
            self.host, port=self.port, user=self.user, password=self.password
        )
        if cam.login():
            self._cam = cam
            self._fail_count = 0
            return True
        try:
            cam.close()
        except Exception:
            pass
        return False

    def _next_frame(self) -> np.ndarray | None:
        if self._cam is None:
            self._set_status("Connecting…")
            if not self._open():
                self._fail_count += 1
                time.sleep(min(2 + self._fail_count, 10))
                return None
        try:
            img_bytes = self._cam.snapshot(channel=self.channel)
        except Exception:
            self._set_status("Reconnecting…")
            self._close()
            return None
        if not img_bytes:
            return None
        frame = cv2.imdecode(
            np.frombuffer(img_bytes, dtype=np.uint8), cv2.IMREAD_COLOR
        )
        return frame

    def _close(self) -> None:
        if self._cam is not None:
            try:
                self._cam.close()
            except Exception:
                pass
            self._cam = None


class CloudBridgeSource(BaseSource):
    """XMeye CloudID (P2P) camera via the bundled cloud bridge.

    Spawns ``cloud_bridge/xmeye_cloud_to_rtsp.py`` (vendor NetSdk cloud
    login, same as the VMS app) which serves the camera as MPEG-TS over
    local HTTP; this source then reads that URL with OpenCV. Works from
    any network (PLDT LAN, Starlink, …) with zero router configuration.
    First connect takes ~15-30s (P2P login + stream analysis).
    """

    poll_interval = 0.03

    def __init__(self, name: str, cloud_id: str, user: str = "admin",
                 password: str = "", channel: int = 0, stream: int = 0):
        super().__init__(name)
        self.cloud_id = cloud_id
        self.user = user
        self.password = password
        self.channel = channel
        self.stream = stream
        self.port = alloc_bridge_port()
        self.url = f"http://127.0.0.1:{self.port}/live"
        self._proc: subprocess.Popen | None = None
        self._reader: threading.Thread | None = None
        self._serving = False
        self._serve_warmed_up = False
        self._cap: cv2.VideoCapture | None = None
        self._spawn_fail_count = 0

    # -- lifecycle ------------------------------------------------------
    def stop(self) -> None:
        super().stop()
        self._kill_bridge()
        free_bridge_port(self.port)

    def _bridge_cmd(self) -> list[str]:
        # NOTE: the password travels via environment, not the command line —
        # CLI args are visible system-wide (Task Manager / ps).
        common = [
            "--cloud-id", self.cloud_id,
            "--user", self.user, "--password", "",
            "--channel", str(self.channel),
            "--stream", str(self.stream),
            "--port", str(self.port),
        ]
        if getattr(sys, "frozen", False):
            # Portable .exe: frozen bridge runner + shared SDK DLLs folder.
            exe_dir = Path(sys.executable).resolve().parent
            return [str(exe_dir / "cloudbridge" / "cloudbridge.exe"),
                    "--vms-dir", str(exe_dir / "cloud_bridge")] + common
        return [sys.executable, str(BRIDGE_SCRIPT)] + common

    # -- internals ------------------------------------------------------
    def _debug_log(self, msg: str) -> None:
        try:
            path = os.path.join(tempfile.gettempdir(), "strataview_bridge.log")
            alive = self._proc.poll() if self._proc is not None else "none"
            with open(path, "a") as f:
                f.write(f"{time.strftime('%H:%M:%S')} [{self.name}] {msg} "
                        f"(proc_alive={alive})\n")
        except Exception:
            pass

    def _spawn(self) -> None:
        if not getattr(sys, "frozen", False) and not BRIDGE_SCRIPT.exists():
            self._set_status("Video bridge files missing. Reinstall the application.")
            return
        self._kill_bridge()
        self._serving = False
        self._serve_warmed_up = False
        self._debug_log(f"spawn attempt (prev_failures={self._spawn_fail_count})")
        try:
            env = dict(os.environ)
            env["XMEYE_CAM_PASSWORD"] = self.password
            self._proc = subprocess.Popen(
                self._bridge_cmd(),
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1,
                # NOTE: no cwd override — in portable builds the dev bridge
                # folder does not exist next to the bundle.
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                env=env,
            )
            self._debug_log(f"spawned pid={self._proc.pid}")
        except Exception as exc:
            self._set_status(f"Could not start the video bridge ({exc})")
            self._debug_log(f"spawn FAILED: {exc}")
            self._proc = None
            return
        except Exception as exc:
            self._set_status(f"error: cannot start bridge ({exc})")
            self._proc = None
            return
        self._reader = threading.Thread(target=self._watch_stdout, daemon=True)
        self._reader.start()

    def _watch_stdout(self) -> None:
        # Drain the bridge's stdout for the whole life of the process.
        # The SDK's native layer is VERY chatty; if the pipe fills up,
        # its logging thread blocks and the login stalls. So: never stop
        # reading, just flip flags when the ready/failure lines appear.
        proc = self._proc
        try:
            for line in proc.stdout:  # type: ignore[union-attr]
                if "Open this in VLC now" in line:
                    self._serving = True
                    self._set_status("Preparing video…")
                elif "Cloud login failed" in line:
                    self._set_status("Sign-in failed. Check the username and password.")
        except Exception:
            pass

    def _kill_bridge(self) -> None:
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None
        if self._proc is not None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=8)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            self._proc = None
        self._serving = False

    def _next_frame(self) -> np.ndarray | None:
        if self._proc is None or self._proc.poll() is not None:
            if self._proc is not None:  # exited unexpectedly
                self._debug_log(f"proc exited (code={self._proc.poll()}), respawning")
                self._kill_bridge()
            self._spawn_fail_count += 1
            self._set_status("Connecting…")
            self._spawn()
            time.sleep(min(2 + self._spawn_fail_count, 10))
            return None
        if not self._serving:
            self._set_status("Connecting…")
            return None
        if not self._serve_warmed_up:
            # ffmpeg needs an analysis window before frames flow.
            time.sleep(6)
            self._serve_warmed_up = True
        if self._cap is None:
            cap = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 2)
            if cap.isOpened():
                self._cap = cap
            else:
                cap.release()
                time.sleep(3)
                return None
        ok, frame = self._cap.read()
        if not ok or frame is None:
            self._set_status("Reconnecting…")
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None
            return None
        return frame


def make_source(cfg: dict) -> BaseSource:
    """Build a source from a cameras.json entry.

    Understands both the old shape ({"type": "rtsp"/"dvrip", ...}) and the
    vendor-style shape ({"login_type": "CloudID"/"IP Address"/"RTSP URL", ...}).
    """
    login = cfg.get("login_type", "")
    ctype = cfg.get("type", "").lower()
    name = cfg.get("name", "Camera")

    wants_rtsp = ctype == "rtsp" or login == "RTSP URL" or (not ctype and cfg.get("url"))
    if wants_rtsp:
        url = cfg.get("url", "")
        if not url:
            raise ValueError(f"{name}: the RTSP address is empty")
        return RtspSource(name, url)

    if login == "CloudID" or (ctype == "cloud"):
        cloud_id = cfg.get("cloud_id") or cfg.get("host") or ""
        if not cloud_id:
            raise ValueError(f"{name}: no CloudID set")
        if not getattr(sys, "frozen", False) and not BRIDGE_SCRIPT.exists():
            raise RuntimeError(
                f"{name}: video bridge files missing. Reinstall the application."
            )
        return CloudBridgeSource(
            name,
            cloud_id=cloud_id,
            user=cfg.get("user", "admin"),
            password=cfg.get("password", ""),
            channel=int(cfg.get("channel", 0)),
            stream=int(cfg.get("stream", 0)),
        )

    wants_dvrip = (
        ctype == "dvrip"
        or login in ("CloudID", "IP Address")
        or cfg.get("host")
        or cfg.get("cloud_id")
    )
    if wants_dvrip:
        try:
            import dvrip  # noqa: F401
        except ImportError as exc:
            raise RuntimeError(
                "DVRIP camera needs the 'python-dvr' package: "
                "pip install git+https://github.com/OpenIPC/python-dvr.git"
            ) from exc
        host = cfg.get("host") or cfg.get("cloud_id") or ""
        if not host:
            raise ValueError(f"{name}: no address set")
        return DvripSource(
            name,
            host=host,
            user=cfg.get("user", "admin"),
            password=cfg.get("password", ""),
            port=int(cfg.get("port", 34567)),
            channel=int(cfg.get("channel", 0)),
        )
    raise ValueError(f"Unknown camera type: {ctype!r} (use 'rtsp' or 'dvrip')")
