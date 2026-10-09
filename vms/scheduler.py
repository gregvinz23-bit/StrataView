"""Recording scheduler + retention sweeper.

Per-camera modes: always / scheduled / motion / off.
Scheduled windows are per weekday (Monday=0) as [start, end] "HH:MM"
pairs; overnight wraps (end <= start) are supported.
Retention: keep N days + never exceed X% of disk. Oldest whole clips
go first; the file currently recording is never touched.
"""

from __future__ import annotations

import shutil
import time
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QObject, QTimer

from . import events
from .storage import camera_dir, recordings_root

DEFAULT_WINDOWS = [["04:00", "22:00"]]
RECORD_MODES = ("always", "scheduled", "motion", "off")


def default_schedule() -> dict[str, list]:
    return {str(d): [list(w) for w in DEFAULT_WINDOWS] for d in range(7)}


def with_defaults(cfg: dict) -> dict:
    """Fill missing recording keys so old configs keep working."""
    cfg.setdefault("record_mode", "scheduled")
    cfg.setdefault("motion_sensitivity", "medium")
    cfg.setdefault("schedule", default_schedule())
    return cfg


def _to_minutes(hhmm: str) -> int | None:
    try:
        h, m = hhmm.split(":")
        return int(h) * 60 + int(m)
    except (ValueError, AttributeError):
        return None


def in_window(schedule: dict | None, now: datetime | None = None) -> bool:
    """True if `now` falls inside any window for its weekday."""
    now = now or datetime.now()
    if not isinstance(schedule, dict):
        return False
    windows = schedule.get(str(now.weekday()), [])
    if not isinstance(windows, list):
        return False
    current = now.hour * 60 + now.minute
    for window in windows:
        if not isinstance(window, (list, tuple)) or len(window) != 2:
            continue
        start = _to_minutes(window[0])
        end = _to_minutes(window[1])
        if start is None or end is None:
            continue
        if end <= start:  # overnight wrap
            if current >= start or current < end:
                return True
        elif start <= current < end:
            return True
    return False


def desired_state(cfg: dict, motion_active: bool = False,
                  now: datetime | None = None) -> bool:
    """Should this camera be recording right now?"""
    cfg = with_defaults(dict(cfg))
    mode = cfg.get("record_mode", "scheduled")
    if mode not in RECORD_MODES:
        mode = "scheduled"
    if mode == "always":
        return True
    if mode == "off":
        return False
    if mode == "motion":
        return motion_active
    return in_window(cfg.get("schedule"), now)


def disk_usage_percent(path: Path | None = None) -> float:
    root = path or recordings_root()
    try:
        usage = shutil.disk_usage(str(root))
        return usage.used / usage.total * 100.0
    except OSError:
        return 0.0


def _clip_time(path: Path) -> float:
    try:
        stamp = datetime.strptime(path.stem[:15], "%Y%m%d_%H%M%S")
        return stamp.timestamp()
    except ValueError:
        return path.stat().st_mtime


def sweep_retention(retention_days: int = 7, max_disk_percent: float = 80.0) -> dict:
    """Delete oldest clips past retention or over the disk cap.

    Returns {"deleted": n, "freed_mb": x}. Never touches a file that is
    growing (modified within the last 60 seconds).
    """
    now = time.time()
    cutoff = now - max(1, retention_days) * 86400
    deleted, freed = 0, 0

    clips: list[tuple[float, Path]] = []
    root = recordings_root()
    for clip in root.rglob("*.mp4"):
        try:
            clips.append((_clip_time(clip), clip))
        except OSError:
            continue
    clips.sort()

    for stamp, clip in clips:
        if stamp >= cutoff:
            break
        if now - clip.stat().st_mtime < 60:
            continue
        try:
            freed += clip.stat().st_size
            clip.unlink()
            deleted += 1
        except OSError:
            continue

    if disk_usage_percent(root) > max_disk_percent:
        remaining = [(s, c) for s, c in clips if c.exists()]
        for _stamp, clip in remaining:
            if disk_usage_percent(root) <= max_disk_percent:
                break
            if time.time() - clip.stat().st_mtime < 60:
                continue
            try:
                freed += clip.stat().st_size
                clip.unlink()
                deleted += 1
            except OSError:
                continue

    if deleted:
        events.log("recording",
                   f"Retention cleanup removed {deleted} clip(s), "
                   f"freed {freed / 1048576:.1f} MB.")
    return {"deleted": deleted, "freed_mb": freed / 1048576}


class Scheduler(QObject):
    """Evaluates recording modes on a timer and runs retention sweeps."""

    def __init__(self, get_sources, get_config, is_motion_active,
                 apply_state, parent=None):
        super().__init__(parent)
        self._get_sources = get_sources
        self._get_config = get_config
        self._is_motion_active = is_motion_active
        self._apply_state = apply_state
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.evaluate)
        self.timer.start(30_000)
        self.sweep_timer = QTimer(self)
        self.sweep_timer.timeout.connect(self.sweep)
        self.sweep_timer.start(15 * 60_000)

    def evaluate(self) -> None:
        now = datetime.now()
        for name in self._get_sources():
            cfg = self._get_config(name)
            want = desired_state(cfg, self._is_motion_active(name), now)
            self._apply_state(name, want, auto=True)

    def sweep(self) -> None:
        from .settings import load as load_settings

        cfg = load_settings()
        sweep_retention(
            retention_days=int(cfg.get("retention_days", 7)),
            max_disk_percent=float(cfg.get("max_disk_percent", 80.0)),
        )
