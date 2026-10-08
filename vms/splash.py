"""Launch splash screen with connection progress."""

from __future__ import annotations

import time

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication, QSplashScreen

from vms import __app_name__, __version__
from vms.resources import APP_LOGO


def build_splash_pixmap(width: int = 480, height: int = 340) -> QPixmap:
    pix = QPixmap(width, height)
    pix.fill(QColor("#11151c"))
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

    logo = QPixmap(APP_LOGO).scaled(
        128, 128,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    painter.drawPixmap((width - logo.width()) // 2, 36, logo)

    painter.setPen(QColor("#ffffff"))
    font = QFont()
    font.setPointSize(22)
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(0, 190, width, 40, Qt.AlignmentFlag.AlignHCenter, __app_name__)

    painter.setPen(QColor("#8b96a5"))
    small = QFont()
    small.setPointSize(10)
    painter.setFont(small)
    painter.drawText(0, 228, width, 24, Qt.AlignmentFlag.AlignHCenter,
                     f"Version {__version__}")
    painter.end()
    return pix


def show_splash(app: QApplication) -> QSplashScreen:
    splash = QSplashScreen(build_splash_pixmap())
    splash.show()
    splash.showMessage(
        "Starting StrataView…",
        Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
        QColor("#8b96a5"),
    )
    app.processEvents()
    return splash


def wait_for_first_live(app: QApplication, window, splash: QSplashScreen,
                        timeout: int = 45) -> None:
    """Pump events until a camera is live or the timeout expires."""
    sources = getattr(window, "sources", {})
    if not sources:
        return
    deadline = time.time() + timeout
    while time.time() < deadline:
        live = [s for s in sources.values() if s.status == "live"]
        if live:
            splash.showMessage(
                f"Connected to {live[0].name}.",
                Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
                QColor("#8b96a5"),
            )
            app.processEvents()
            break
        names = ", ".join(s.name for s in sources.values())
        splash.showMessage(
            f"Connecting to {names}…",
            Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
            QColor("#8b96a5"),
        )
        app.processEvents()
        time.sleep(0.2)
