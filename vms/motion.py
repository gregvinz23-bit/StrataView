"""Software motion detection (works on any source type).

Downscaled MOG2 background subtraction at a few frames per second.
Emits events (log + snapshot) with a cooldown; exposes a motion-active
window with post-roll so motion-only recording outlasts the movement.
"""

from __future__ import annotations

import threading
import time

import cv2
import numpy as np

PRESETS = {
    "low": {"var_threshold": 50, "min_fraction": 0.020},
    "medium": {"var_threshold": 30, "min_fraction": 0.008},
    "high": {"var_threshold": 18, "min_fraction": 0.003},
}


def _preset(sensitivity: str) -> dict:
    return PRESETS.get(sensitivity, PRESETS["medium"])


class MotionDetector:
    """Analyses `source.latest()` in a background thread."""

    EVENT_COOLDOWN = 10.0   # seconds between logged events
    POST_ROLL = 30.0        # recording stays on this long after motion
    ANALYSE_WIDTH = 320
    ANALYSE_HZ = 3.0
    WARMUP_FRAMES = 30      # learn the background first; never fire during these

    def __init__(self, source, sensitivity: str = "medium", on_event=None):
        self.source = source
        self.sensitivity = sensitivity
        self.on_event = on_event  # called as on_event() on each new event
        self.motion_until = 0.0
        self.last_event_at = 0.0
        self._warmup = self.WARMUP_FRAMES
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._subtractor = cv2.createBackgroundSubtractorMOG2(
            history=100, detectShadows=False
        )

    @property
    def active(self) -> bool:
        return time.time() < self.motion_until

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._subtractor = cv2.createBackgroundSubtractorMOG2(
            history=100, detectShadows=False
        )
        self._subtractor.setVarThreshold(_preset(self.sensitivity)["var_threshold"])
        self._warmup = self.WARMUP_FRAMES
        self._thread = threading.Thread(
            target=self._loop, name=f"motion-{self.source.name}", daemon=True
        )
        self._thread.start()

    def set_sensitivity(self, sensitivity: str) -> None:
        self.sensitivity = sensitivity
        try:
            self._subtractor.setVarThreshold(_preset(sensitivity)["var_threshold"])
        except Exception:
            pass

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None

    # -- internals ------------------------------------------------------
    def _loop(self) -> None:
        interval = 1.0 / self.ANALYSE_HZ
        while not self._stop.is_set():
            try:
                frame = self.source.latest()
                if frame is not None:
                    self._analyse(frame)
            except Exception:
                pass
            self._stop.wait(interval)

    def _analyse(self, frame: np.ndarray) -> bool:
        preset = _preset(self.sensitivity)
        h, w = frame.shape[:2]
        small = cv2.resize(frame, (self.ANALYSE_WIDTH, max(1, int(h * self.ANALYSE_WIDTH / max(1, w)))))
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        mask = self._subtractor.apply(gray)
        if self._warmup > 0:
            # Background model is still learning; never fire during warmup.
            self._warmup -= 1
            return False
        fg = (mask == 255).mean()
        if fg >= float(preset["min_fraction"]):
            now = time.time()
            self.motion_until = now + self.POST_ROLL
            if now - self.last_event_at >= self.EVENT_COOLDOWN:
                self.last_event_at = now
                if self.on_event is not None:
                    try:
                        self.on_event()
                    except Exception:
                        pass
            return True
        return False
