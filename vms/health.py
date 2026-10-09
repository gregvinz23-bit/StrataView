"""Camera health tracking: uptime, reconnects, frame rate, stall logic.

- HealthTracker accumulates per-source stats from status observations.
- check_source() decides stall restarts and unstable backoff.
- HealthDialog shows the live table (Tools menu).
"""

from __future__ import annotations

import time
from collections import deque

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QDialog,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from .resources import apply_icon

STALL_AFTER = 20.0          # no fresh frame for this long -> force restart
UNSTABLE_FAILURES = 5       # restarts inside the window below -> back off
UNSTABLE_WINDOW = 600.0     # seconds
UNSTABLE_PAUSE = 900.0      # seconds to wait while unstable

TRANSIENT = ("Connecting…", "Reconnecting…", "Preparing video…", "stopped", "")


class HealthTracker:
    def __init__(self):
        self.live_seconds = 0.0
        self.reconnects = 0
        self.last_error = ""
        self._last_status = ""
        self._last_seen = time.time()
        self._frames = 0
        self._fps_window: deque[tuple[float, int]] = deque(maxlen=12)
        self._restarts: deque[float] = deque()
        self.unstable_until = 0.0

    def observe(self, status: str, frame_count: int) -> None:
        now = time.time()
        if status == "live":
            self.live_seconds += max(0.0, now - self._last_seen)
            if self._last_status != "live" and self._last_status:
                self.reconnects += 1
        elif status not in TRANSIENT:
            self.last_error = status
        self._last_status = status
        self._last_seen = now
        self._frames = frame_count
        self._fps_window.append((now, frame_count))

    @property
    def fps(self) -> float:
        if len(self._fps_window) < 2:
            return 0.0
        (t0, f0), (t1, f1) = self._fps_window[0], self._fps_window[-1]
        dt = t1 - t0
        return (f1 - f0) / dt if dt > 0 else 0.0

    def note_restart(self) -> None:
        now = time.time()
        self._restarts.append(now)
        while self._restarts and now - self._restarts[0] > UNSTABLE_WINDOW:
            self._restarts.popleft()
        if len(self._restarts) >= UNSTABLE_FAILURES:
            self.unstable_until = now + UNSTABLE_PAUSE

    @property
    def unstable(self) -> bool:
        return time.time() < self.unstable_until

    @staticmethod
    def format_uptime(seconds: float) -> str:
        seconds = int(seconds)
        h, rem = divmod(seconds, 3600)
        m, s = divmod(rem, 60)
        if h:
            return f"{h}h {m}m"
        if m:
            return f"{m}m {s}s"
        return f"{s}s"


def check_source(name: str, source, tracker: HealthTracker) -> str:
    """Inspect one source. Returns an action: ok / restart / unstable / wait.

    - ok: healthy or still (re)connecting on its own.
    - restart: stream stalled (no fresh frame) — caller should stop/start it.
    - unstable: too many recent restarts — caller should stop it and wait.
    - wait: in an unstable pause, not yet time to retry.
    """
    if tracker.unstable:
        return "wait"
    last_frame = getattr(source, "last_frame_time", 0) or 0
    if not last_frame:
        return "ok"  # never delivered a frame; connection logic owns it
    last_frame_age = time.time() - last_frame
    if last_frame_age > STALL_AFTER:
        tracker.note_restart()
        if tracker.unstable:
            return "unstable"
        return "restart"
    return "ok"


class HealthDialog(QDialog):
    def __init__(self, get_rows, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Camera health")
        apply_icon(self)
        self.resize(640, 300)
        self._get_rows = get_rows
        layout = QVBoxLayout(self)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Camera", "Status", "Uptime", "Reconnects", "Rate", "Last error"]
        )
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(2000)
        self.refresh()

    def refresh(self) -> None:
        rows = self._get_rows()
        self.table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, value in enumerate(row):
                self.table.setItem(i, j, QTableWidgetItem(str(value)))
