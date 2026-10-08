"""Application artwork (logo / window icon), dev- and frozen-aware."""

from __future__ import annotations

import sys
from pathlib import Path


def resource_path(relative: str) -> str:
    """Resolve a bundled resource in both dev runs and the frozen .exe."""
    base = getattr(sys, "_MEIPASS", None)
    if base is None:
        base = Path(__file__).resolve().parent.parent
    return str(Path(base) / relative)


APP_ICON = resource_path("assets/ICON.ico")
APP_LOGO = resource_path("assets/LOGO.png")


def app_icon():
    from PyQt6.QtGui import QIcon

    return QIcon(APP_ICON)


def app_logo_pixmap(size: int = 96):
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QPixmap

    return QPixmap(APP_LOGO).scaled(
        size, size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


def apply_icon(widget) -> None:
    """Set the StrataView window icon (title bar + taskbar)."""
    widget.setWindowIcon(app_icon())
