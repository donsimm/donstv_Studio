"""Schlichte, einfarbige Symbole für die Schaltflächenleisten der Docks (wie bei OBS), gezeichnet in der Textfarbe
des Themes. Keine Logos und keine Marken; alles wird mit QPainter aus Linien gezeichnet.
"""

from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, QSize, Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap, QPolygonF

ICON_SIZE = 16
RATIO = 2  # doppelt gross vorbereitet: scharf auch bei hoher Auflösung

KINDS = (
    "plus", "trash", "duplicate", "up", "down", "eye", "eye_off", "copy",
    "align_left", "align_center", "align_right", "align_top", "align_middle", "align_bottom",
)  # fmt: skip


def _poly(*pts: tuple[float, float]) -> QPolygonF:
    return QPolygonF([QPointF(x, y) for x, y in pts])


def draw_icon(kind: str, color: str, size: int = ICON_SIZE) -> QPixmap:
    pm = QPixmap(size * RATIO, size * RATIO)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    col = QColor(color)
    pen = QPen(col)
    pen.setWidthF(1.5 * RATIO)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    u = size * RATIO / 16  # Einheit: 1/16 der Symbolgrösse

    def r(x: float, y: float, w: float, h: float) -> QRectF:
        return QRectF(x * u, y * u, w * u, h * u)

    def line(x1: float, y1: float, x2: float, y2: float) -> None:
        p.drawLine(QPointF(x1 * u, y1 * u), QPointF(x2 * u, y2 * u))

    def scaled(*pts: tuple[float, float]) -> QPolygonF:
        return _poly(*[(x * u, y * u) for x, y in pts])

    if kind == "plus":
        line(8, 3, 8, 13)
        line(3, 8, 13, 8)
    elif kind == "trash":
        line(3, 4.5, 13, 4.5)
        line(6.5, 4.5, 6.5, 3)
        line(6.5, 3, 9.5, 3)
        line(9.5, 3, 9.5, 4.5)
        p.drawPolyline(scaled((4.5, 4.5), (5.2, 13), (10.8, 13), (11.5, 4.5)))
        line(7, 6.5, 7, 11)
        line(9, 6.5, 9, 11)
    elif kind in ("duplicate", "copy"):
        p.drawRect(r(3, 5, 7, 8))
        p.drawPolyline(scaled((6, 5), (6, 3), (13, 3), (13, 10), (10, 10)))
    elif kind == "up":
        p.drawPolyline(scaled((3.5, 10), (8, 5.5), (12.5, 10)))
    elif kind == "down":
        p.drawPolyline(scaled((3.5, 6), (8, 10.5), (12.5, 6)))
    elif kind in ("eye", "eye_off"):
        p.drawPolyline(scaled((1.5, 8), (4.5, 4.8), (8, 3.8), (11.5, 4.8), (14.5, 8),
                              (11.5, 11.2), (8, 12.2), (4.5, 11.2), (1.5, 8)))  # fmt: skip
        p.drawEllipse(r(6, 6, 4, 4))
        if kind == "eye_off":
            line(3, 13, 13, 3)
    elif kind.startswith("align_"):
        how = kind[6:]
        p.setBrush(col)
        p.setPen(Qt.PenStyle.NoPen)
        if how in ("left", "center", "right"):
            x = {"left": 2.5, "center": 7.5, "right": 12.5}[how]
            p.drawRect(r(x, 2, 1, 12))
            # zwei Balken, an der Linie ausgerichtet
            if how == "left":
                p.drawRect(r(4, 4, 8, 3))
                p.drawRect(r(4, 9, 5, 3))
            elif how == "center":
                p.drawRect(r(4, 4, 8, 3))
                p.drawRect(r(5.5, 9, 5, 3))
            else:
                p.drawRect(r(4, 4, 8, 3))
                p.drawRect(r(7, 9, 5, 3))
        else:
            y = {"top": 2.5, "middle": 7.5, "bottom": 12.5}[how]
            p.drawRect(r(2, y, 12, 1))
            if how == "top":
                p.drawRect(r(4, 4, 3, 8))
                p.drawRect(r(9, 4, 3, 5))
            elif how == "middle":
                p.drawRect(r(4, 4, 3, 8))
                p.drawRect(r(9, 5.5, 3, 5))
            else:
                p.drawRect(r(4, 4, 3, 8))
                p.drawRect(r(9, 7, 3, 5))
    p.end()
    pm.setDevicePixelRatio(RATIO)
    return pm


def make_icon(kind: str, color: str, size: int = ICON_SIZE) -> QIcon:
    return QIcon(draw_icon(kind, color, size))


def icon_size() -> QSize:
    return QSize(ICON_SIZE, ICON_SIZE)
