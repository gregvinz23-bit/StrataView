"""Timestamped event log: in-memory ring buffer + daily log files.

Logged: app start/stop, camera connect/disconnect/failures, recording
start/stop, snapshots, camera add/remove/edit, settings, update checks.
Status polling never logs directly — callers log on state *transitions*.
"""

from __future__ import annotations

import threading
from collections import deque
from datetime import datetime
from pathlib import Path

from . import storage

MAX_ENTRIES = 500

_lock = threading.Lock()
_entries: deque[tuple[str, str, str]] = deque(maxlen=MAX_ENTRIES)


def _log_file() -> Path:
    d = storage.BASE_DIR / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"strataview-{datetime.now():%Y%m%d}.log"


def log(category: str, message: str) -> None:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _lock:
        _entries.append((stamp, category, message))
        try:
            with open(_log_file(), "a", encoding="utf-8") as f:
                f.write(f"[{stamp}] [{category}] {message}\n")
        except OSError:
            pass


def get_all() -> list[tuple[str, str, str]]:
    with _lock:
        return list(_entries)


def clear() -> None:
    with _lock:
        _entries.clear()


def export_to(path: str | Path) -> Path:
    dest = Path(path)
    with _lock:
        lines = [f"[{s}] [{c}] {m}\n" for s, c, m in _entries]
    dest.write_text("".join(lines), encoding="utf-8")
    return dest


def format_entry(stamp: str, category: str, message: str) -> str:
    return f"{stamp[11:]}  [{category}]  {message}"
