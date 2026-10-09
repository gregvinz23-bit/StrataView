"""Version history shown in About."""

CHANGELOG: list[tuple[str, list[str]]] = [
    (
        "1.2.0",
        [
            "Recording modes per camera: always, scheduled hours, motion only, off.",
            "Per-weekday recording schedules with retention (days + disk cap).",
            "Motion detection with event feed, snapshots, click-to-playback.",
            "Camera health watchdog: stall restarts, backoff, health dialog.",
        ],
    ),
    (
        "1.1.0",
        [
            "Event log with export (View menu).",
            "Retry button on tiles that fail to connect.",
            "Clearer error messages with next steps.",
            "Version history in About.",
        ],
    ),
    (
        "1.0.0",
        [
            "Live grid (1, 2×2, 3×3) for CloudID, RTSP and DVRIP cameras.",
            "Recording with configurable segment length.",
            "Recording playback with seek.",
            "Snapshots, camera list, dark theme.",
            "Setup wizard, splash screen, settings.",
            " Portable Windows build.",
        ],
    ),
]


def notes_text() -> str:
    parts = []
    for version, items in CHANGELOG:
        parts.append(f"Version {version}")
        parts.extend(f"  • {item}" for item in items)
        parts.append("")
    return "\n".join(parts).strip()
