"""Crisp hand-drawn toolbar icons (QPainter vectors, theme-matched).

No external assets: every icon is drawn at runtime so it stays sharp at
any DPI and always matches the StrataView palette.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

ACCENT = QColor("#2dd4bf")
LIGHT = QColor("#dbe2ec")
MUTED = QColor("#8b96a5")
RED = QColor("#f87171")
SIZE = 24


def _canvas() -> tuple[QPixmap, QPainter]:
    pix = QPixmap(SIZE, SIZE)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    return pix, painter


def _pen(color: QColor, width: float = 2.0) -> QPen:
    pen = QPen(color)
    pen.setWidthF(width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return pen


def _icon(pix: QPixmap) -> QIcon:
    return QIcon(pix)


def add_device() -> QIcon:
    pix, p = _canvas()
    p.setPen(_pen(ACCENT))
    p.drawRoundedRect(3, 6, 18, 13, 2, 2)          # monitor
    p.drawLine(9, 21, 15, 21)                       # stand
    p.setPen(_pen(LIGHT))
    p.drawLine(12, 9, 12, 15)                       # plus vertical
    p.drawLine(9, 12, 15, 12)                       # plus horizontal
    p.end()
    return _icon(pix)


def edit() -> QIcon:
    pix, p = _canvas()
    p.setPen(_pen(LIGHT))
    path = QPainterPath()
    path.moveTo(6, 18)
    path.lineTo(8, 14)
    path.lineTo(14, 6)
    path.lineTo(18, 10)
    path.lineTo(12, 18)
    path.closeSubpath()
    p.drawPath(path)
    p.setPen(_pen(ACCENT))
    p.drawLine(14, 6, 18, 10)
    p.end()
    return _icon(pix)


def remove() -> QIcon:
    pix, p = _canvas()
    p.setPen(_pen(LIGHT))
    p.drawLine(7, 9, 17, 9)                         # lid
    p.drawLine(10, 9, 10, 7)
    p.drawLine(14, 9, 14, 7)
    p.drawLine(10, 7, 14, 7)
    p.drawRoundedRect(8, 9, 8, 11, 1, 1)            # bin
    p.setPen(_pen(RED))
    p.drawLine(11, 12, 11, 17)
    p.drawLine(13, 12, 13, 17)
    p.end()
    return _icon(pix)


def snapshot() -> QIcon:
    pix, p = _canvas()
    p.setPen(_pen(LIGHT))
    p.drawRoundedRect(3, 8, 18, 12, 2, 2)           # body
    p.drawLine(9, 8, 10, 5)
    p.drawLine(10, 5, 14, 5)
    p.drawLine(14, 5, 15, 8)                        # viewfinder hump
    p.setPen(_pen(ACCENT))
    p.drawEllipse(9, 11, 6, 6)                      # lens
    p.setPen(_pen(ACCENT))
    p.drawPoint(19, 11)
    p.end()
    return _icon(pix)


def record() -> QIcon:
    pix, p = _canvas()
    p.setBrush(RED)
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(7, 7, 10, 10)                     # red dot
    p.end()
    return _icon(pix)


def playback() -> QIcon:
    pix, p = _canvas()
    p.setBrush(ACCENT)
    p.setPen(Qt.PenStyle.NoPen)
    path = QPainterPath()
    path.moveTo(8, 5)
    path.lineTo(18, 12)
    path.lineTo(8, 19)
    path.closeSubpath()
    p.drawPath(path)                                # play triangle
    p.end()
    return _icon(pix)


def about() -> QIcon:
    pix, p = _canvas()
    p.setPen(_pen(LIGHT))
    p.drawEllipse(4, 4, 16, 16)
    p.setPen(_pen(ACCENT))
    p.drawLine(12, 11, 12, 16)
    p.drawPoint(12, 8)
    p.end()
    return _icon(pix)


def folder() -> QIcon:
    pix, p = _canvas()
    p.setPen(_pen(LIGHT))
    path = QPainterPath()
    path.moveTo(3, 8)
    path.lineTo(3, 18)
    path.lineTo(21, 18)
    path.lineTo(21, 8)
    path.closeSubpath()
    p.drawPath(path)
    p.drawLine(3, 8, 9, 8)
    p.drawLine(9, 8, 11, 10)
    p.drawLine(11, 10, 21, 10)
    p.end()
    return _icon(pix)


def settings() -> QIcon:
    pix, p = _canvas()
    p.setPen(_pen(MUTED))
    p.drawEllipse(9, 9, 6, 6)
    for cx, cy in ((12, 3), (12, 21), (3, 12), (21, 12),
                   (6, 6), (18, 6), (6, 18), (18, 18)):
        p.drawLine(12, 12, cx, cy)
    p.end()
    return _icon(pix)
