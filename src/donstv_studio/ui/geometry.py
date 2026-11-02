"""Rechnen im Editor (F-13, F-65): Umrechnung Overlay-Pixel <-> Bildschirm, Verschieben, Skalieren,
Drehen, Einrasten, Ausrichten. Dieses Modul braucht kein Qt und ist deshalb ohne Oberfläche testbar.

Alle gespeicherten Werte sind ganze Pixel der Overlay-Auflösung (CLAUDE.md Regel 4). Fliesskommazahlen
gibt es nur auf dem Weg dorthin (Zeigerlage, Drehung um die Mitte) und werden am Ende gerundet.

Koordinaten: x nach rechts, y nach unten. Drehung in Grad im Uhrzeigersinn um die Mitte der Quelle, wie
CSS `rotate()` auf der Overlay-Seite (overlay.js).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from donstv_studio.ui import diagnose

ZOOM_STEPS = (0.25, 0.5, 1.0, 2.0, 4.0)  # Anzeige in Prozent: 25, 50, 100, 200, 400
FIT = "fit"  # Zoom-Modus «Einpassen»
HANDLES = ("nw", "n", "ne", "e", "se", "s", "sw", "w")
# Richtung je Griff: (sx, sy) mit -1 = links/oben, +1 = rechts/unten, 0 = Mitte
HANDLE_DIR = {
    "nw": (-1, -1), "n": (0, -1), "ne": (1, -1), "e": (1, 0),
    "se": (1, 1), "s": (0, 1), "sw": (-1, 1), "w": (-1, 0),
}  # fmt: skip
ROTATE = "rotate"
SNAP_PIXELS = 6  # Fangbereich in Bildschirmpixeln
ROTATE_STEP = 15  # Umschalttaste: Drehung rastet in 15°-Schritten
MIN_SIDE = 1


def rint(value: float) -> int:
    """Auf die nächste ganze Zahl runden, bei .5 nach oben (kein «Bankier-Runden»)."""
    return math.floor(value + 0.5)


def normalize_angle(deg: float) -> float:
    """Winkel in den Bereich (-180, 180]."""
    a = math.fmod(deg, 360.0)
    if a <= -180.0:
        a += 360.0
    elif a > 180.0:
        a -= 360.0
    return a


@dataclass(frozen=True)
class Box:
    """Lage und Grösse einer Quelle in ganzen Pixeln; Drehung um die Mitte in Grad."""

    x: int
    y: int
    w: int
    h: int
    rot: float = 0.0

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2

    def corners(self) -> list[tuple[float, float]]:
        pts = [
            (self.x, self.y),
            (self.x + self.w, self.y),
            (self.x + self.w, self.y + self.h),
            (self.x, self.y + self.h),
        ]
        return [rotate_point(px, py, self.cx, self.cy, self.rot) for px, py in pts]

    def bounds(self) -> tuple[float, float, float, float]:
        """Umschliessendes, achsenparalleles Rechteck (links, oben, rechts, unten)."""
        if not self.rot:
            return (float(self.x), float(self.y), float(self.x + self.w), float(self.y + self.h))
        xs, ys = zip(*self.corners(), strict=True)
        return (min(xs), min(ys), max(xs), max(ys))

    def contains(self, px: float, py: float) -> bool:
        """Liegt der Punkt in der (gedrehten) Quelle?"""
        lx, ly = rotate_point(px, py, self.cx, self.cy, -self.rot)
        return self.x <= lx <= self.x + self.w and self.y <= ly <= self.y + self.h


def rotate_point(px: float, py: float, cx: float, cy: float, deg: float) -> tuple[float, float]:
    if not deg:
        return (px, py)
    t = math.radians(deg)
    c, s = math.cos(t), math.sin(t)
    dx, dy = px - cx, py - cy
    return (cx + dx * c - dy * s, cy + dx * s + dy * c)


# --- Ansicht: Overlay-Pixel <-> Bildschirm ---------------------------------------------------------


@dataclass(frozen=True)
class ViewTransform:
    """Umrechnung zwischen Overlay-Pixeln und Qt-Koordinaten (logische Pixel) der Ansicht.

    `zoom` = Bildschirmpixel (physisch) je Overlay-Pixel; bei 1.0 ist ein Overlay-Pixel genau ein
    Bildschirmpixel, auch bei `dpr` 2 (dann sind es 0,5 logische Pixel). `origin` ist die Lage des
    Overlay-Punkts (0, 0) in der Ansicht.
    """

    zoom: float = 1.0
    dpr: float = 1.0
    origin: tuple[float, float] = (0.0, 0.0)

    @property
    def k(self) -> float:
        """Logische Qt-Pixel je Overlay-Pixel."""
        return self.zoom / self.dpr

    @property
    def web_zoom(self) -> float:
        """Zoomfaktor der Webansicht: Chromium rechnet selbst mit dem devicePixelRatio von Qt."""
        return self.k

    def to_view(self, x: float, y: float) -> tuple[float, float]:
        return (self.origin[0] + x * self.k, self.origin[1] + y * self.k)

    def to_overlay(self, vx: float, vy: float) -> tuple[float, float]:
        return ((vx - self.origin[0]) / self.k, (vy - self.origin[1]) / self.k)

    def pixel_at(self, vx: float, vy: float) -> tuple[int, int]:
        """Ganzzahlige Overlay-Pixelkoordinate unter dem Zeiger (das Pixel, in dem der Zeiger liegt)."""
        x, y = self.to_overlay(vx, vy)
        return (math.floor(x), math.floor(y))

    def stage_size(self, width: int, height: int) -> tuple[float, float]:
        """Grösse der Overlay-Fläche in logischen Pixeln (bei dpr 2 und Zoom 100 % also 960 × 540 für 1920 × 1080)."""
        return (width * self.k, height * self.k)


def fit_zoom(avail_w: float, avail_h: float, width: int, height: int, dpr: float) -> float:
    """Zoom für «Einpassen»: grösster Wert, bei dem das ganze Overlay in die Fläche passt."""
    if width <= 0 or height <= 0:
        return 1.0
    return max(0.01, min(avail_w * dpr / width, avail_h * dpr / height))


def next_zoom(current: float, direction: int) -> float:
    """Nächste feste Stufe über (direction > 0) oder unter (< 0) dem aktuellen Zoom."""
    eps = 1e-9
    if direction > 0:
        for z in ZOOM_STEPS:
            if z > current + eps:
                return z
        return ZOOM_STEPS[-1]
    for z in reversed(ZOOM_STEPS):
        if z < current - eps:
            return z
    return ZOOM_STEPS[0]


def zoom_label(zoom: float) -> str:
    return f"{round(zoom * 100)} %"


# --- Einrasten -------------------------------------------------------------------------------------


@dataclass
class SnapTargets:
    """Linien, an denen eingerastet wird (Overlay-Pixel). Leere Listen = nichts einrasten."""

    xs: list[float] = field(default_factory=list)
    ys: list[float] = field(default_factory=list)


@dataclass
class SnapHit:
    """Ergebnis des Einrastens: Verschiebung und die getroffenen Linien (für die Anzeige)."""

    dx: float = 0.0
    dy: float = 0.0
    xs: list[float] = field(default_factory=list)
    ys: list[float] = field(default_factory=list)


def snap_targets(
    width: int,
    height: int,
    guides_v: list[int],
    guides_h: list[int],
    others: list[Box],
    *,
    edges: bool = True,
    guides: bool = True,
    sources: bool = True,
) -> SnapTargets:
    """Sammelt die Fanglinien: Ränder und Mitte des Overlays, Hilfslinien, Kanten und Mitten anderer Quellen.

    Das Raster gehört nicht hierher: `snap_axis` berücksichtigt es je Bewegungskante (Argument `grid` dort).
    """
    t = SnapTargets()
    if edges:
        t.xs += [0.0, width / 2, float(width)]
        t.ys += [0.0, height / 2, float(height)]
    if guides:
        t.xs += [float(g) for g in guides_v]
        t.ys += [float(g) for g in guides_h]
    if sources:
        for b in others:
            left, top, right, bottom = b.bounds()
            t.xs += [left, (left + right) / 2, right]
            t.ys += [top, (top + bottom) / 2, bottom]
    return t


def snap_axis(
    moving: list[float], lines: list[float], threshold: float, grid: int = 0
) -> tuple[float, float | None]:
    """Kleinste Verschiebung, mit der eine der Kanten (`moving`) auf eine Linie oder ein Rasterkreuz rastet.

    Rückgabe: (Verschiebung, getroffene Linie) oder (0, None), wenn nichts näher als `threshold` liegt.
    """
    best: tuple[float, float] | None = None
    for m in moving:
        for line in lines:
            d = line - m
            if abs(d) <= threshold and (best is None or abs(d) < abs(best[0])):
                best = (d, line)
        if grid > 0:
            line = round(m / grid) * grid
            d = line - m
            if abs(d) <= threshold and (best is None or abs(d) < abs(best[0])):
                best = (d, line)
    return (best[0], best[1]) if best else (0.0, None)


# --- Verschieben, Skalieren, Drehen ----------------------------------------------------------------


def move_box(
    start: Box,
    dx: float,
    dy: float,
    snap: SnapTargets | None = None,
    threshold: float = 0.0,
    grid: int = 0,
) -> tuple[Box, SnapHit]:
    """Verschiebt um (dx, dy) Overlay-Pixel (Zeigerweg, gerundet), rastet auf Wunsch ein.

    Eingerastet werden linke Kante, Mitte und rechte Kante (oben, Mitte, unten) des umschliessenden Rechtecks.
    """
    hit = SnapHit()
    if snap is not None:
        left, top, right, bottom = start.bounds()
        sx, line_x = snap_axis(
            [left + dx, (left + right) / 2 + dx, right + dx], snap.xs, threshold, grid
        )
        sy, line_y = snap_axis(
            [top + dy, (top + bottom) / 2 + dy, bottom + dy], snap.ys, threshold, grid
        )
        if line_x is not None:
            dx += sx
            hit.dx, hit.xs = sx, [line_x]
        if line_y is not None:
            dy += sy
            hit.dy, hit.ys = sy, [line_y]
    return Box(start.x + rint(dx), start.y + rint(dy), start.w, start.h, start.rot), hit


def fit_inside(w: int, h: int, max_w: int, max_h: int) -> tuple[int, int]:
    """Grösse im Seitenverhältnis w:h, höchstens max_w × max_h (nur verkleinern), ganze Pixel, mindestens 1 (F-77)."""
    if diagnose.off("geometry_changes"):  # DIAGNOSE (P06d3): wie P08 nur begrenzt
        return min(w, max_w), min(h, max_h)
    s = min(1.0, max_w / w, max_h / h)
    return (max(MIN_SIDE, min(max_w, rint(w * s))), max(MIN_SIDE, min(max_h, rint(h * s))))


def is_corner(handle: str) -> bool:
    sx, sy = HANDLE_DIR[handle]
    return bool(sx and sy)


def resize_box(
    start: Box,
    handle: str,
    dx: float,
    dy: float,
    snap: SnapTargets | None = None,
    threshold: float = 0.0,
    grid: int = 0,
    keep_ratio: bool = False,
) -> tuple[Box, SnapHit]:
    """Ändert die Grösse über einen Eck- oder Seitengriff.

    (dx, dy) ist der Weg des Zeigers seit dem Anfassen in Overlay-Pixeln. Die gegenüberliegende Kante (Ecke)
    bleibt an ihrem Platz, auch bei gedrehter Quelle. Einrasten gibt es nur ohne Drehung. Mindestgrösse 1 Pixel.

    `keep_ratio` (nur Eckgriffe, F-77): Das Seitenverhältnis von `start` bleibt (bis auf Rundung auf ganze
    Pixel). Es gilt im Koordinatensystem der Quelle, also auch bei Drehung.
    """
    sx, sy = HANDLE_DIR[handle]
    if keep_ratio and sx and sy and not diagnose.off("geometry_changes"):  # DIAGNOSE (P06d3)
        return _resize_keep_ratio(start, sx, sy, dx, dy, snap, threshold, grid)
    hit = SnapHit()
    theta = start.rot
    # Lage des Griffs vor dem Ziehen, in der ungedrehten Quelle (Mitte als Ursprung)
    hx, hy = sx * start.w / 2, sy * start.h / 2
    # Ziel des Griffs in Welt-Koordinaten
    c0x, c0y = start.cx, start.cy
    wx, wy = rotate_point(c0x + hx, c0y + hy, c0x, c0y, theta)
    tx, ty = wx + dx, wy + dy
    if snap is not None and not theta:
        if sx:
            d, line = snap_axis([tx], snap.xs, threshold, grid)
            if line is not None:
                tx += d
                hit.dx, hit.xs = d, [line]
        if sy:
            d, line = snap_axis([ty], snap.ys, threshold, grid)
            if line is not None:
                ty += d
                hit.dy, hit.ys = d, [line]
    # Ziel im ungedrehten Rahmen der Quelle
    qx, qy = rotate_point(tx, ty, c0x, c0y, -theta)
    qx, qy = qx - c0x, qy - c0y
    new_w = max(MIN_SIDE, rint(sx * qx + start.w / 2)) if sx else start.w
    new_h = max(MIN_SIDE, rint(sy * qy + start.h / 2)) if sy else start.h
    return _anchored(start, sx, sy, new_w, new_h), hit


def _anchored(start: Box, sx: int, sy: int, new_w: int, new_h: int) -> Box:
    """Box mit neuer Grösse; die dem Griff gegenüberliegende Ecke (Kante) bleibt fest, auch gedreht."""
    c0x, c0y, theta = start.cx, start.cy, start.rot
    ax, ay = rotate_point(c0x - sx * start.w / 2, c0y - sy * start.h / 2, c0x, c0y, theta)
    ox, oy = rotate_point(sx * new_w / 2, sy * new_h / 2, 0.0, 0.0, theta)
    cx, cy = ax + ox, ay + oy
    return Box(rint(cx - new_w / 2), rint(cy - new_h / 2), new_w, new_h, start.rot)


def _resize_keep_ratio(
    start: Box,
    sx: int,
    sy: int,
    dx: float,
    dy: float,
    snap: SnapTargets | None,
    threshold: float,
    grid: int,
) -> tuple[Box, SnapHit]:
    hit = SnapHit()
    w0, h0, theta = start.w, start.h, start.rot
    c0x, c0y = start.cx, start.cy
    # Ziel des Griffs im ungedrehten Rahmen der Quelle (Mitte als Ursprung)
    gx, gy = rotate_point(c0x + sx * w0 / 2, c0y + sy * h0 / 2, c0x, c0y, theta)
    qx, qy = rotate_point(gx + dx, gy + dy, c0x, c0y, -theta)
    raw_w, raw_h = sx * (qx - c0x) + w0 / 2, sy * (qy - c0y) + h0 / 2
    # Faktor: Projektion des Zeigers auf die Diagonale (gleichmässig in beide Richtungen)
    f = (raw_w * w0 + raw_h * h0) / (w0 * w0 + h0 * h0)
    if snap is not None and not theta:
        # Ohne Drehung darf eine der beiden bewegten Kanten einrasten; die andere folgt dem Verhältnis.
        ax, ay = c0x - sx * w0 / 2, c0y - sy * h0 / 2
        best: tuple[float, str, float, float] | None = None
        ex, ey = ax + sx * w0 * f, ay + sy * h0 * f
        d, line = snap_axis([ex], snap.xs, threshold, grid)
        if line is not None:
            best = (abs(d), "x", line, sx * (ex + d - ax) / w0)
        d, line = snap_axis([ey], snap.ys, threshold, grid)
        if line is not None and (best is None or abs(d) < best[0]):
            best = (abs(d), "y", line, sy * (ey + d - ay) / h0)
        if best is not None:
            f = best[3]
            if best[1] == "x":
                hit.xs = [best[2]]
            else:
                hit.ys = [best[2]]
    f = max(f, MIN_SIDE / min(w0, h0))
    new_w, new_h = max(MIN_SIDE, rint(w0 * f)), max(MIN_SIDE, rint(h0 * f))
    return _anchored(start, sx, sy, new_w, new_h), hit


def rotation_from_pointer(
    start: Box, press: tuple[float, float], now: tuple[float, float], step: bool
) -> float:
    """Neue Drehung beim Ziehen des Drehgriffs: Startdrehung plus Winkeländerung des Zeigers um die Mitte.

    Ganze Grad; mit `step` (Umschalttaste) Vielfache von 15°.
    """
    a0 = math.degrees(math.atan2(press[1] - start.cy, press[0] - start.cx))
    a1 = math.degrees(math.atan2(now[1] - start.cy, now[0] - start.cx))
    deg = start.rot + (a1 - a0)
    deg = round(deg / ROTATE_STEP) * ROTATE_STEP if step else round(deg)
    return float(normalize_angle(deg))


# --- Ausrichten ------------------------------------------------------------------------------------

ALIGNMENTS = ("left", "center", "right", "top", "middle", "bottom")
ALIGN_LABELS = {
    "left": "Links ausrichten",
    "center": "Horizontal zentrieren",
    "right": "Rechts ausrichten",
    "top": "Oben ausrichten",
    "middle": "Vertikal zentrieren",
    "bottom": "Unten ausrichten",
}


def align_box(box: Box, how: str, width: int, height: int) -> Box:
    """Richtet das umschliessende Rechteck der Quelle am Overlay aus (nur Verschiebung, ganze Pixel)."""
    left, top, right, bottom = box.bounds()
    dx = dy = 0.0
    if how == "left":
        dx = -left
    elif how == "center":
        dx = width / 2 - (left + right) / 2
    elif how == "right":
        dx = width - right
    elif how == "top":
        dy = -top
    elif how == "middle":
        dy = height / 2 - (top + bottom) / 2
    elif how == "bottom":
        dy = height - bottom
    else:
        raise ValueError(f"Unbekannte Ausrichtung: {how}")
    return Box(box.x + rint(dx), box.y + rint(dy), box.w, box.h, box.rot)


def nudge_box(box: Box, dx: int, dy: int) -> Box:
    return Box(box.x + dx, box.y + dy, box.w, box.h, box.rot)
