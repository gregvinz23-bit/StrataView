"""Config + recording-file helpers for StrataView VMS."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

if getattr(sys, "frozen", False):
    # Portable .exe: keep user data next to the executable, not in the
    # read-only bundle dir.
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent.parent
CAMERAS_FILE = BASE_DIR / "cameras.json"
RECORDINGS_DIR = BASE_DIR / "recordings"
SNAPSHOTS_DIR = BASE_DIR / "snapshots"

_recordings_override: Path | None = None
_snapshots_override: Path | None = None


def apply_directory_overrides(
    recordings: str | None = None, snapshots: str | None = None
) -> None:
    """Point recordings/snapshots at custom folders (from Settings)."""
    global _recordings_override, _snapshots_override
    _recordings_override = Path(recordings) if recordings else None
    _snapshots_override = Path(snapshots) if snapshots else None


def recordings_root() -> Path:
    root = _recordings_override or RECORDINGS_DIR
    root.mkdir(parents=True, exist_ok=True)
    return root


def snapshots_root() -> Path:
    root = _snapshots_override or SNAPSHOTS_DIR
    root.mkdir(parents=True, exist_ok=True)
    return root

EXAMPLE_CAMERAS = [    {
        "name": "Front Door",
        "type": "rtsp",
        "url": "rtsp://user:pass@192.168.1.20:554/stream1",
        "enabled": False,
    },
    {
        "name": "NVR Ch1",
        "type": "dvrip",
        "host": "192.168.1.10",
        "port": 34567,
        "user": "admin",
        "password": "",
        "channel": 0,
        "enabled": False,
    },
]


def ensure_dirs() -> None:
    recordings_root()
    snapshots_root()
    if not CAMERAS_FILE.exists():
        CAMERAS_FILE.write_text(json.dumps(EXAMPLE_CAMERAS, indent=2), encoding="utf-8")


def load_cameras() -> list[dict]:
    ensure_dirs()
    try:
        data = json.loads(CAMERAS_FILE.read_text(encoding="utf-8"))
        return [c for c in data if isinstance(c, dict)]
    except (json.JSONDecodeError, OSError):
        return []


def save_cameras(cameras: list[dict]) -> None:
    ensure_dirs()
    CAMERAS_FILE.write_text(json.dumps(cameras, indent=2), encoding="utf-8")


def camera_dir(name: str) -> Path:
    safe = "".join(ch if ch.isalnum() or ch in ("-", "_", " ") else "_" for ch in name).strip()
    path = recordings_root() / (safe or "camera")
    path.mkdir(parents=True, exist_ok=True)
    return path


def clips_for(name: str) -> list[Path]:
    d = camera_dir(name)
    return sorted(d.glob("*.mp4"))


def snapshot_path(name: str) -> Path:
    ensure_dirs()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in name).strip() or "camera"
    return snapshots_root() / f"{safe}_{stamp}.jpg"
