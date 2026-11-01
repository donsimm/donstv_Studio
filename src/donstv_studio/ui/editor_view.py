"""Editor mit Vorschau (F-13, F-14, F-65): Lineale, Karo-Bühne, Webansicht und Bedienebene.

Aufbau von unten nach oben:
  1. `Stage`: Karo-Hintergrund (Qt).
  2. `WebPreview`: dieselbe Overlay-Seite wie die Browserquelle (durchsichtig, QtWebEngine).
  3. `InteractionLayer`: Qt zeichnet Auswahlrahmen, Griffe, Hilfslinien und Raster **über** der Webansicht und nimmt
     Maus und Tastatur an. Nichts davon liegt innerhalb der Overlay-Seite.

Alle Werte sind ganze Pixel der Overlay-Auflösung (CLAUDE.md Regel 4, F-65). Umrechnung: `geometry.ViewTransform`.
"""

from __future__ import annotations

import math

from PyQt6.QtCore import QPoint, QPointF, QRect, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFontMetrics, QPainter, QPen
from PyQt6.QtWidgets import QScrollBar, QWidget

from donstv_studio.ui import diagnose, preview_web, theme
from donstv_studio.ui import geometry as geo
from donstv_studio.ui.editor_model import EditorModel, box_of
from donstv_studio.ui.editor_prefs import EditorPrefs
from donstv_studio.ui.geometry import FIT, Box

RULER = 20  # Breite der Lineale in Pixeln
MARGIN = 24  # Rand um die Fläche, wenn sie grösser ist als die Ansicht (zum Verschieben)
FIT_MARGIN = 8  # Rand um die Fläche bei «Einpassen»
HANDLE = 8  # Seitenlänge der Griffe
HANDLE_HIT = 7  # Trefferradius der Griffe
ROTATE_OFFSET = 26  # Abstand des Drehgriffs über der oberen Kante (Bildschirmpixel)
GUIDE_HIT = 4
SHRUNK_ZOOM = 0.5  # «Vorschau verkleinern»: «Einpassen» wird nie grösser als 50 %
RULER_STEPS = (1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000)
PAN_STEP = 40
BADGE_MARGIN = 6  # Abstand der Zeigeranzeige zum linken und unteren Rand der Vorschaufläche
BADGE_PAD = (6, 2)  # Innenabstand der Zeigeranzeige (waagrecht, senkrecht)
BADGE_ALPHA = (
    200  # Deckkraft des Grundes der Zeigeranzeige (0 bis 255): lesbar auf hellem und dunklem Bild
)
NO_POINTER = "X: –   Y: –"
WIDEST_POINTER = "X: -99999   Y: -99999"  # für die feste Breite der Zeigeranzeige


def pointer_text(inside: bool, x: int, y: int) -> str:
    """Text der Zeigeranzeige (F-75): ganze Overlay-Pixel, ausserhalb der Fläche «–»."""
    return f"X: {x}   Y: {y}" if inside else NO_POINTER


def ruler_step(k: float, min_px: float = 64.0) -> int:
    """Abstand der beschrifteten Striche in Overlay-Pixeln: der kleinste Schritt mit mindestens `min_px` Bildschirmpixeln."""
    for s in RULER_STEPS:
        if s * k >= min_px:
            return s
    return RULER_STEPS[-1]


class Stage(QWidget):
    """Karo-Hintergrund hinter dem durchsichtigen Overlay. Die Karos haben feste Bildschirmgrösse (nicht zoomabhängig)."""

    CELL = 8

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("editor_stage")
        self.palette_ = theme.palette(theme.DEFAULT_THEME)
        self.solid: str | None = None  # nur für Vergleichstests: einfarbig statt Karo

    def paintEvent(self, e) -> None:
        p = QPainter(self)
        r = e.rect()
        if self.solid:
            p.fillRect(r, QColor(self.solid))
            return
        a, b = QColor(self.palette_["checker_a"]), QColor(self.palette_["checker_b"])
        c = self.CELL
        p.fillRect(r, a)
        for y in range(r.top() // c * c, r.bottom() + 1, c):
            for x in range(r.left() // c * c, r.right() + 1, c):
                if (x // c + y // c) % 2:
                    p.fillRect(x, y, c, c, b)


class Ruler(QWidget):
    """Lineal oben (waagerecht) oder links (senkrecht) mit Strichen in Overlay-Pixeln; Ziehen erzeugt eine Hilfslinie."""

    def __init__(self, view: EditorView, horizontal: bool) -> None:
        super().__init__(view)
        self.view, self.horizontal = view, horizontal
        self.setObjectName("ruler_top" if horizontal else "ruler_left")
        self.pointer: float | None = (
            None  # Lage des Zeigers entlang des Lineals (Ansichtskoordinate)
        )
        self.setCursor(Qt.CursorShape.SplitVCursor if horizontal else Qt.CursorShape.SplitHCursor)
        self.setToolTip("Ziehen erzeugt eine Hilfslinie")

    def paintEvent(self, _e) -> None:
        pal = theme.palette(self.view.theme_name)
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(pal["title_bg"]))
        t = self.view.transform()
        k = t.k
        length = self.width() if self.horizontal else self.height()
        origin = t.origin[0] if self.horizontal else t.origin[1]
        major = ruler_step(k)
        minor = max(1, major // (5 if major in (1, 2, 5) or major % 10 else 10))
        if minor * k < 4:
            minor = major
        first = math.floor((0 - origin) / k / minor) * minor
        last = math.ceil((length - origin) / k)
        size = self.view.model.size()
        limit = size[0] if self.horizontal else size[1]
        p.setPen(QColor(pal["text_muted"]))
        font = p.font()
        font.setPointSizeF(max(6.5, font.pointSizeF() - 2.5))
        p.setFont(font)
        v = first
        while v <= last:
            if 0 <= v <= limit:
                pos = origin + v * k
                is_major = v % major == 0
                depth = RULER if is_major else RULER // 3
                if self.horizontal:
                    p.drawLine(QPointF(pos, RULER - depth), QPointF(pos, RULER))
                    if is_major:
                        p.drawText(QPointF(pos + 3, RULER - 9), str(v))
                else:
                    p.drawLine(QPointF(RULER - depth, pos), QPointF(RULER, pos))
                    if is_major:
                        p.save()
                        p.translate(RULER - 9, pos + 3)
                        p.rotate(-90)
                        p.drawText(QPointF(0, 0), str(v))
                        p.restore()
            v += minor
        if self.pointer is not None:
            p.setPen(QPen(QColor(pal["accent"]), 1))
            if self.horizontal:
                p.drawLine(QPointF(self.pointer, 0), QPointF(self.pointer, RULER))
            else:
                p.drawLine(QPointF(0, self.pointer), QPointF(RULER, self.pointer))
        p.setPen(QColor(pal["border"]))
        p.drawRect(self.rect().adjusted(0, 0, -1, -1))

    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton and self.view.model.current() is not None:
            self.view.layer.begin_guide("h" if self.horizontal else "v", None)
            self.view.layer.update_guide(
                self.view.layer.mapFromGlobal(e.globalPosition().toPoint())
            )

    def mouseMoveEvent(self, e) -> None:
        if e.buttons() & Qt.MouseButton.LeftButton:
            self.view.layer.update_guide(
                self.view.layer.mapFromGlobal(e.globalPosition().toPoint())
            )

    def mouseReleaseEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self.view.layer.end_guide(self.view.layer.mapFromGlobal(e.globalPosition().toPoint()))


class PointerBadge(QWidget):
    """Zeigerposition links unten in der Vorschaufläche (F-75), von Qt über der Webansicht gezeichnet.

    Nicht Teil der Overlay-Seite: die Ausgabe in OBS bleibt gleich. Halbtransparenter Grund in der Farbe der Fläche,
    Text in der Textfarbe; Mausereignisse gehen durch auf die Bedienebene. Feste Breite: der Text springt nicht.
    """

    def __init__(self, view: EditorView) -> None:
        super().__init__(view.viewport)
        self.view = view
        self.setObjectName("pointer_badge")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAccessibleName("Pixelposition unter dem Zeiger")
        self._text = NO_POINTER

    def text(self) -> str:
        return self._text

    def set_pointer(self, inside: bool, x: int, y: int) -> None:
        text = pointer_text(inside, x, y)
        if text != self._text:
            self._text = text
            self.update()

    def sizeHint(self) -> QSize:
        fm = QFontMetrics(self.font())
        return QSize(
            fm.horizontalAdvance(WIDEST_POINTER) + 2 * BADGE_PAD[0], fm.height() + 2 * BADGE_PAD[1]
        )

    def place(self) -> None:
        """Links unten in die Vorschaufläche, über die Bedienebene. Setzt die Lage nur, wenn sie sich ändert (P06d2)."""
        size = self.sizeHint()
        parent = self.parentWidget()
        rect = QRect(
            BADGE_MARGIN,
            parent.height() - size.height() - BADGE_MARGIN,
            size.width(),
            size.height(),
        )
        if self.geometry() != rect:
            self.setGeometry(rect)
        self.raise_()

    def colors(self) -> tuple[QColor, QColor]:
        pal = theme.palette(self.view.theme_name)
        back = QColor(pal["surface"])
        back.setAlpha(BADGE_ALPHA)
        return back, QColor(pal["text"])

    def paintEvent(self, _e) -> None:
        back, fore = self.colors()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(back)
        p.drawRoundedRect(QRectF(self.rect()), 3, 3)
        p.setPen(fore)
        p.drawText(
            QRectF(self.rect()).adjusted(BADGE_PAD[0], 0, -BADGE_PAD[0], 0),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            self._text,
        )
        p.end()


class InteractionLayer(QWidget):
    """Liegt über der Webansicht: zeichnet Raster, Hilfslinien, Auswahlrahmen und Griffe; nimmt Maus und Tasten an."""

    pointer_pixel = pyqtSignal(
        bool, int, int
    )  # Zeiger über der Fläche?, x, y in Overlay-Pixeln (Regel 12)

    def __init__(self, view: EditorView) -> None:
        super().__init__(view.viewport)
        self.view = view
        self.setObjectName("editor_layer")
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._drag: dict | None = None
        self._snap_lines: tuple[list[float], list[float]] = ([], [])
        self._live_guide: dict | None = (
            None  # {"axis": "h"|"v", "index": int|None, "pos": int|None}
        )

    # --- Hilfen -------------------------------------------------------------------------------------
    @property
    def model(self) -> EditorModel:
        return self.view.model

    def _selected_box(self) -> Box | None:
        s = self.model.selected()
        return box_of(s) if s and s.get("visible", True) else None

    def handle_points(self, box: Box | None = None) -> dict[str, QPointF]:
        """Lage der Griffe in Ansichtskoordinaten (für die Anzeige und für Tests)."""
        b = box or self._selected_box()
        if b is None:
            return {}
        t = self.view.transform()
        pts: dict[str, QPointF] = {}
        for name, (sx, sy) in geo.HANDLE_DIR.items():
            wx, wy = geo.rotate_point(b.cx + sx * b.w / 2, b.cy + sy * b.h / 2, b.cx, b.cy, b.rot)
            pts[name] = QPointF(*t.to_view(wx, wy))
        wx, wy = geo.rotate_point(b.cx, b.y - ROTATE_OFFSET / t.k, b.cx, b.cy, b.rot)
        pts[geo.ROTATE] = QPointF(*t.to_view(wx, wy))
        return pts

    def _hit_handle(self, pos: QPointF) -> str | None:
        for name, pt in self.handle_points().items():
            if abs(pt.x() - pos.x()) <= HANDLE_HIT and abs(pt.y() - pos.y()) <= HANDLE_HIT:
                return name
        return None

    def _hit_source(self, ox: float, oy: float) -> str | None:
        for s in reversed(self.model.sources()):  # oberste zuerst
            if s.get("visible", True) and box_of(s).contains(ox, oy):
                return s["id"]
        return None

    def _guides(self) -> tuple[list[int], list[int]]:
        v, h = self.model.guides()
        live = self._live_guide
        if live and live["pos"] is not None:
            lst = v if live["axis"] == "v" else h
            if live["index"] is not None and live["index"] < len(lst):
                lst = list(lst)
                lst[live["index"]] = live["pos"]
            else:
                lst = [*lst, live["pos"]]
            return (lst, h) if live["axis"] == "v" else (v, lst)
        return v, h

    def _hit_guide(self, pos: QPointF) -> tuple[str, int] | None:
        t = self.view.transform()
        v, h = self.model.guides()
        for i, x in enumerate(v):
            if abs(t.to_view(x, 0)[0] - pos.x()) <= GUIDE_HIT:
                return ("v", i)
        for i, y in enumerate(h):
            if abs(t.to_view(0, y)[1] - pos.y()) <= GUIDE_HIT:
                return ("h", i)
        return None

    def _targets(self) -> geo.SnapTargets | None:
        if not self.view.prefs.snap:
            return None
        w, h = self.model.size()
        v, hh = self.model.guides()
        return geo.snap_targets(w, h, v, hh, self.model.others())

    def _grid(self) -> int:
        p = self.view.prefs
        return p.grid_size if p.grid and p.snap else 0

    # --- Zeichnen -----------------------------------------------------------------------------------
    def paintEvent(self, _e) -> None:
        if self.model.current() is None:
            return
        pal = theme.palette(self.view.theme_name)
        t = self.view.transform()
        w, h = self.model.size()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        x0, y0 = t.to_view(0, 0)
        x1, y1 = t.to_view(w, h)
        # Raster
        prefs = self.view.prefs
        if prefs.grid and prefs.grid_size * t.k >= 4:
            gc = QColor(pal["text"])
            gc.setAlpha(45)
            p.setPen(QPen(gc, 1))
            for gx in range(0, w + 1, prefs.grid_size):
                vx = round(t.to_view(gx, 0)[0])
                p.drawLine(vx, round(y0), vx, round(y1))
            for gy in range(0, h + 1, prefs.grid_size):
                vy = round(t.to_view(0, gy)[1])
                p.drawLine(round(x0), vy, round(x1), vy)
        # Rand des Overlays
        p.setPen(QPen(QColor(pal["border"]), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(QRectF(x0 - 0.5, y0 - 0.5, x1 - x0 + 1, y1 - y0 + 1))
        # Hilfslinien
        gv, gh = self._guides()
        p.setPen(QPen(QColor(pal["guide"]), 1))
        for gx in gv:
            vx = round(t.to_view(gx, 0)[0])
            p.drawLine(vx, 0, vx, self.height())
        for gy in gh:
            vy = round(t.to_view(0, gy)[1])
            p.drawLine(0, vy, self.width(), vy)
        # Auswahl
        box = self._selected_box()
        if box is not None:
            self._paint_selection(p, box, pal)
        # Linien, an denen eingerastet wird
        sx, sy = self._snap_lines
        p.setPen(QPen(QColor(pal["snap"]), 1, Qt.PenStyle.DashLine))
        for lx in sx:
            vx = round(t.to_view(lx, 0)[0])
            p.drawLine(vx, 0, vx, self.height())
        for ly in sy:
            vy = round(t.to_view(0, ly)[1])
            p.drawLine(0, vy, self.width(), vy)
        p.end()

    def _paint_selection(self, p: QPainter, box: Box, pal: dict[str, str]) -> None:
        t = self.view.transform()
        corners = [QPointF(*t.to_view(x, y)) for x, y in box.corners()]
        frame = QColor(pal["accent"])
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setPen(QPen(frame, 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPolygon(corners)
        pts = self.handle_points(box)
        rot = pts.pop(geo.ROTATE)
        top_mid = pts["n"]
        p.setPen(QPen(frame, 1))
        p.drawLine(top_mid, rot)
        p.setBrush(QColor(pal["bg"]))
        p.setPen(QPen(frame, 2))
        p.drawEllipse(rot, 5, 5)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        p.setBrush(QColor(pal["text"]))
        p.setPen(QPen(QColor(pal["bg"]), 1))
        for pt in pts.values():
            p.drawRect(
                QRect(round(pt.x() - HANDLE / 2), round(pt.y() - HANDLE / 2), HANDLE, HANDLE)
            )

    # --- Maus ---------------------------------------------------------------------------------------
    def _overlay_point(self, pos: QPointF) -> tuple[float, float]:
        return self.view.transform().to_overlay(pos.x(), pos.y())

    def mousePressEvent(self, e) -> None:
        self.setFocus()
        if e.button() != Qt.MouseButton.LeftButton or self.model.current() is None:
            return
        pos = e.position()
        ox, oy = self._overlay_point(pos)
        sel = self.model.selected()
        handle = self._hit_handle(pos)
        if handle is not None and sel is not None:
            kind = "rotate" if handle == geo.ROTATE else "resize"
            self._start_drag(kind, sel["id"], pos, handle)
            return
        guide = self._hit_guide(pos)
        if guide is not None:
            self.begin_guide(guide[0], guide[1])
            self.update_guide(QPoint(round(pos.x()), round(pos.y())))
            return
        sid = self._hit_source(ox, oy)
        self.model.select_source(sid)
        if sid is not None:
            self._start_drag("move", sid, pos, None)
        self.update()

    def _start_drag(self, kind: str, sid: str, pos: QPointF, handle: str | None) -> None:
        s = self.model.source(sid)
        if s is None:
            return
        self._drag = {
            "kind": kind, "sid": sid, "handle": handle, "start": box_of(s),
            "press_view": pos, "press": self._overlay_point(pos), "targets": self._targets(),
            "moved": False, "image": s.get("kind") == "image",
        }  # fmt: skip

    def mouseMoveEvent(self, e) -> None:
        pos = e.position()
        t = self.view.transform()
        px = t.pixel_at(pos.x(), pos.y())
        w, h = self.model.size()
        inside = self.model.current() is not None and 0 <= px[0] < w and 0 <= px[1] < h
        self.pointer_pixel.emit(inside, px[0], px[1])
        self.view.set_ruler_pointer(pos)
        if self._live_guide is not None:
            self.update_guide(QPoint(round(pos.x()), round(pos.y())))
            return
        d = self._drag
        if d is None or not (e.buttons() & Qt.MouseButton.LeftButton):
            self._update_cursor(pos)
            return
        k = t.k
        dx = (pos.x() - d["press_view"].x()) / k
        dy = (pos.y() - d["press_view"].y()) / k
        thr = geo.SNAP_PIXELS / k
        grid = self._grid()
        start: Box = d["start"]
        hit = geo.SnapHit()
        if d["kind"] == "move":
            box, hit = geo.move_box(start, dx, dy, d["targets"], thr, grid)
        elif d["kind"] == "resize":
            # F-77: Eckgriffe einer Bildquelle behalten das Seitenverhältnis; Umschalttaste löst es.
            free = bool(e.modifiers() & Qt.KeyboardModifier.ShiftModifier)
            keep = d["image"] and geo.is_corner(d["handle"]) and not free
            box, hit = geo.resize_box(
                start, d["handle"], dx, dy, d["targets"], thr, grid, keep_ratio=keep
            )
        else:
            now = self._overlay_point(pos)
            rot = geo.rotation_from_pointer(
                start, d["press"], now, bool(e.modifiers() & Qt.KeyboardModifier.ShiftModifier)
            )
            box = Box(start.x, start.y, start.w, start.h, rot)
        d["moved"] = True
        self._snap_lines = (hit.xs, hit.ys)
        self.model.set_box(d["sid"], box)
        self.update()

    def mouseReleaseEvent(self, e) -> None:
        if e.button() != Qt.MouseButton.LeftButton:
            return
        if self._live_guide is not None:
            self.end_guide(QPoint(round(e.position().x()), round(e.position().y())))
            return
        d, self._drag = self._drag, None
        self._snap_lines = ([], [])
        if d is not None and d["moved"]:
            s = self.model.source(d["sid"])
            if s is not None:
                self.model.push_history(d["sid"], d["start"], box_of(s))
        self.update()
        self._update_cursor(e.position())

    def leaveEvent(self, _e) -> None:
        self.pointer_pixel.emit(False, 0, 0)
        self.view.set_ruler_pointer(None)

    def _update_cursor(self, pos: QPointF) -> None:
        handle = self._hit_handle(pos) if self.model.selected() else None
        if handle == geo.ROTATE:
            self.setCursor(Qt.CursorShape.CrossCursor)
        elif handle is not None:
            self.setCursor(self._resize_cursor(handle))
        elif (g := self._hit_guide(pos)) is not None:
            self.setCursor(
                Qt.CursorShape.SplitHCursor if g[0] == "v" else Qt.CursorShape.SplitVCursor
            )
        else:
            ox, oy = self._overlay_point(pos)
            self.setCursor(
                Qt.CursorShape.SizeAllCursor
                if self._hit_source(ox, oy)
                else Qt.CursorShape.ArrowCursor
            )

    def _resize_cursor(self, handle: str) -> Qt.CursorShape:
        sx, sy = geo.HANDLE_DIR[handle]
        box = self._selected_box()
        ang = (
            math.degrees(math.atan2(*geo.rotate_point(sx, sy, 0, 0, box.rot if box else 0.0)[::-1]))
            % 180
        )
        if ang < 22.5 or ang >= 157.5:
            return Qt.CursorShape.SizeHorCursor
        if ang < 67.5:
            return Qt.CursorShape.SizeFDiagCursor
        if ang < 112.5:
            return Qt.CursorShape.SizeVerCursor
        return Qt.CursorShape.SizeBDiagCursor

    # --- Hilfslinien --------------------------------------------------------------------------------
    def begin_guide(self, axis: str, index: int | None) -> None:
        self._live_guide = {"axis": axis, "index": index, "pos": None}

    def update_guide(self, pos: QPoint) -> None:
        g = self._live_guide
        if g is None:
            return
        ox, oy = self._overlay_point(QPointF(pos))
        g["pos"] = geo.rint(ox if g["axis"] == "v" else oy)
        self.update()

    def end_guide(self, pos: QPoint) -> None:
        g, self._live_guide = self._live_guide, None
        if g is None:
            return
        v, h = self.model.guides()
        lst = v if g["axis"] == "v" else h
        outside = (
            not (0 <= pos.x() <= self.width())
            if g["axis"] == "v"
            else not (0 <= pos.y() <= self.height())
        )  # über dem Lineal losgelassen: Linie entfernen
        if g["index"] is not None and g["index"] < len(lst):
            lst = list(lst)
            if outside or g["pos"] is None:
                del lst[g["index"]]
            else:
                lst[g["index"]] = g["pos"]
        elif not outside and g["pos"] is not None:
            lst = [*lst, g["pos"]]
        if g["axis"] == "v":
            self.model.set_guides(lst, h)
        else:
            self.model.set_guides(v, lst)
        self.update()

    # --- Tasten und Rad -----------------------------------------------------------------------------
    def keyPressEvent(self, e) -> None:
        step = 10 if e.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1
        moves = {
            Qt.Key.Key_Left: (-step, 0), Qt.Key.Key_Right: (step, 0),
            Qt.Key.Key_Up: (0, -step), Qt.Key.Key_Down: (0, step),
        }  # fmt: skip
        if e.key() in moves and self.model.selected() is not None:
            self.model.nudge(*moves[e.key()])
            e.accept()
            return
        super().keyPressEvent(e)

    def wheelEvent(self, e) -> None:
        self.view.wheel(e)


class EditorView(QWidget):
    """Lineale, Bühne mit Webansicht, Bedienebene und Rollbalken. Ersetzt die Platzhalter-Leinwand von P05."""

    pointer_changed = pyqtSignal(bool, int, int)  # Zeiger über der Fläche?, x, y in Overlay-Pixeln
    zoom_changed = pyqtSignal(float, bool)  # wirksamer Zoom (1.0 = 100 %), «Einpassen»?
    overlay_available = pyqtSignal(bool)

    def __init__(
        self,
        model: EditorModel,
        prefs: EditorPrefs,
        use_web: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("editor_view")
        self.model, self.prefs = model, prefs
        self.theme_name = theme.DEFAULT_THEME
        self.dpr_override: float | None = None  # nur für Tests
        self._fit = prefs.zoom == FIT
        self._zoom = 1.0 if prefs.zoom == FIT else float(prefs.zoom)
        self._scroll = [0, 0]
        self._anchor: tuple[QPointF, tuple[float, float]] | None = None

        self.viewport = QWidget(self)
        self.viewport.setObjectName("editor_viewport")
        self.stage = Stage(self.viewport)
        self._use_web = use_web and preview_web.HAS_WEBENGINE
        self.web: preview_web.WebPreview | None = (
            None  # entsteht erst mit dem ersten Overlay (Chromium startet dann)
        )
        self.layer = InteractionLayer(self)
        # DIAGNOSE (P06d2): DONSTV_OFF=pointer_badge baut die Zeigeranzeige nicht (Stand P08)
        self.pointer_badge = None if diagnose.off("pointer_badge") else PointerBadge(self)
        self.ruler_top = Ruler(self, True)
        self.ruler_left = Ruler(self, False)
        self.hbar = QScrollBar(Qt.Orientation.Horizontal, self)
        self.vbar = QScrollBar(Qt.Orientation.Vertical, self)
        for bar in (self.hbar, self.vbar):
            bar.valueChanged.connect(self._scrolled)
            bar.hide()

        model.current_changed.connect(self._on_overlay)
        model.meta_changed.connect(self._on_meta)
        for sig in (
            model.box_changed,
            model.sources_changed,
            model.selection_changed,
            model.guides_changed,
        ):
            sig.connect(lambda *_: self.layer.update())
        prefs.changed.connect(self._on_prefs)
        self.layer.pointer_pixel.connect(self.pointer_changed)
        if self.pointer_badge is not None:
            self.layer.pointer_pixel.connect(self.pointer_badge.set_pointer)
        self._loaded_url: str | None = None
        self._size: tuple[int, int] = model.size()
        self._on_overlay(model.current_id)

    # --- Abfragen -----------------------------------------------------------------------------------
    def dpr(self) -> float:
        return self.dpr_override or self.devicePixelRatioF()

    def zoom(self) -> float:
        """Wirksamer Zoom: Bildschirmpixel je Overlay-Pixel (1.0 = 100 %)."""
        return self._effective_zoom()

    @property
    def fit_mode(self) -> bool:
        return self._fit

    def transform(self) -> geo.ViewTransform:
        return geo.ViewTransform(self._effective_zoom(), self.dpr(), self._origin())

    def _viewport_size(self) -> tuple[int, int]:
        return self.viewport.width(), self.viewport.height()

    def _effective_zoom(self) -> float:
        if not self._fit:
            return self._zoom
        vw, vh = self._viewport_size()
        w, h = self.model.size()
        z = geo.fit_zoom(max(1, vw - 2 * FIT_MARGIN), max(1, vh - 2 * FIT_MARGIN), w, h, self.dpr())
        return min(z, SHRUNK_ZOOM) if self.prefs.shrink else z

    # --- Zoom ---------------------------------------------------------------------------------------
    def set_zoom(self, zoom: float | str, anchor: QPointF | None = None) -> None:
        """«Einpassen» (FIT) oder ein fester Faktor (1.0 = 100 %). `anchor`: Punkt der Ansicht, der stehen bleibt."""
        if anchor is None:
            vw, vh = self._viewport_size()
            anchor = QPointF(vw / 2, vh / 2)
        t = self.transform()
        self._anchor = (anchor, t.to_overlay(anchor.x(), anchor.y()))
        if zoom == FIT:
            self._fit = True
        else:
            self._fit, self._zoom = False, float(zoom)
        self.prefs.set_zoom(zoom)
        self._relayout()

    def wheel(self, e) -> None:
        delta = e.angleDelta().y()
        if e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if delta:
                self.set_zoom(
                    geo.next_zoom(self._effective_zoom(), 1 if delta > 0 else -1), e.position()
                )
        elif e.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            self.hbar.setValue(self.hbar.value() - (PAN_STEP if delta > 0 else -PAN_STEP))
        elif delta:
            self.vbar.setValue(self.vbar.value() - (PAN_STEP if delta > 0 else -PAN_STEP))
        e.accept()

    # --- Reaktionen auf das Modell ------------------------------------------------------------------
    def _on_overlay(self, _overlay_id) -> None:
        o = self.model.current()
        self.overlay_available.emit(o is not None)
        self._size = self.model.size()
        url = self.model.preview_url() if o else None
        if url and self.web is None and self._use_web:
            self.web = preview_web.WebPreview(self.stage)
            self.web.set_fps(self.prefs.fps)
            self.web.show()
        if self.web is not None and url != self._loaded_url:
            self._loaded_url = url
            self.web.load_overlay(url) if url else self.web.clear()
        if self._fit is False:
            self._scroll = [0, 0]
        self._relayout()
        self.layer.update()

    def _on_meta(self) -> None:
        if self.model.size() != self._size:
            self._size = self.model.size()
            self._relayout()
        self.layer.update()

    def _on_prefs(self, _key: str) -> None:
        if self.web is not None:
            self.web.set_fps(self.prefs.fps)
        want_fit = self.prefs.zoom == FIT
        if want_fit != self._fit or (
            not want_fit and abs(float(self.prefs.zoom) - self._zoom) > 1e-9
        ):
            # gespeicherter Zoom wurde geladen (nicht von dieser Ansicht gesetzt)
            self._fit = want_fit
            if not want_fit:
                self._zoom = float(self.prefs.zoom)
        self._relayout()
        self.layer.update()

    def apply_theme(self, name: str) -> None:
        self.theme_name = name
        self.stage.palette_ = theme.palette(name)
        for w in (self.stage, self.ruler_top, self.ruler_left, self.layer, self.pointer_badge):
            if w is not None:
                w.update()

    def set_ruler_pointer(self, pos: QPointF | None) -> None:
        self.ruler_top.pointer = pos.x() if pos is not None else None
        self.ruler_left.pointer = pos.y() if pos is not None else None
        self.ruler_top.update()
        self.ruler_left.update()

    # --- Anordnung ----------------------------------------------------------------------------------
    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        self._relayout()

    def _scrolled(self, _value: int) -> None:
        self._scroll = [self.hbar.value(), self.vbar.value()]
        self._relayout(from_scroll=True)

    def _margin(self) -> int:
        return FIT_MARGIN if self._fit else MARGIN

    def _content(self) -> tuple[float, float]:
        w, h = self.model.size()
        k = self._effective_zoom() / self.dpr()
        m = self._margin()
        return w * k + 2 * m, h * k + 2 * m

    def _origin(self) -> tuple[float, float]:
        vw, vh = self._viewport_size()
        w, h = self.model.size()
        k = self._effective_zoom() / self.dpr()
        cw, ch = self._content()
        ox = (vw - w * k) / 2 if cw <= vw else self._margin() - self._scroll[0]
        oy = (vh - h * k) / 2 if ch <= vh else self._margin() - self._scroll[1]
        # Ganze logische Pixel: Fläche (Qt-Widget) und Umrechnung müssen denselben Ursprung haben. Bei dpr 2 ist das
        # ein Vielfaches von 2 physischen Pixeln; die 1:1-Abbildung bei 100 % bleibt davon unberührt.
        return (float(round(ox)), float(round(oy)))

    def _relayout(self, from_scroll: bool = False) -> None:
        if not hasattr(self, "layer"):
            return
        full_w, full_h = self.width() - RULER, self.height() - RULER
        bar_w = self.vbar.sizeHint().width()
        bar_h = self.hbar.sizeHint().height()
        # Erst ohne Rollbalken rechnen, dann mit (ein Balken verkleinert die Ansicht für den anderen).
        vw, vh = max(1, full_w), max(1, full_h)
        need_h = need_v = False
        for _ in range(2):
            self.viewport.setGeometry(RULER, RULER, vw, vh)
            cw, ch = self._content()
            need_h, need_v = (
                cw > full_w - (bar_w if need_v else 0),
                ch > full_h - (bar_h if need_h else 0),
            )
            vw = max(1, full_w - (bar_w if need_v else 0))
            vh = max(1, full_h - (bar_h if need_h else 0))
        self.viewport.setGeometry(RULER, RULER, vw, vh)
        cw, ch = self._content()
        if self._anchor is not None and not from_scroll:
            (ap, (ax, ay)) = self._anchor
            k = self._effective_zoom() / self.dpr()
            m = self._margin()
            self._scroll = [round(m - (ap.x() - ax * k)), round(m - (ap.y() - ay * k))]
        self._anchor = None
        self._scroll[0] = max(0, min(self._scroll[0], max(0, round(cw - vw)))) if need_h else 0
        self._scroll[1] = max(0, min(self._scroll[1], max(0, round(ch - vh)))) if need_v else 0
        for bar, need, page, total, val in (
            (self.hbar, need_h, vw, cw, self._scroll[0]),
            (self.vbar, need_v, vh, ch, self._scroll[1]),
        ):
            bar.blockSignals(True)
            bar.setRange(0, max(0, round(total - page)))
            bar.setPageStep(page)
            bar.setSingleStep(PAN_STEP)
            bar.setValue(val)
            bar.blockSignals(False)
            bar.setVisible(need)
        self.hbar.setGeometry(RULER, RULER + vh, vw, bar_h)
        self.vbar.setGeometry(RULER + vw, RULER, bar_w, vh)
        self.ruler_top.setGeometry(RULER, 0, vw, RULER)
        self.ruler_left.setGeometry(0, RULER, RULER, vh)
        self.layer.setGeometry(0, 0, vw, vh)
        self.layer.raise_()
        if self.pointer_badge is not None:
            self.pointer_badge.place()
        self._place_stage()
        for w in (self.ruler_top, self.ruler_left):
            w.update()
        self.zoom_changed.emit(self._effective_zoom(), self._fit)

    def _place_stage(self) -> None:
        """Bühne und Webansicht setzen. Die Webansicht deckt nur den sichtbaren Teil (ganze Overlay-Pixel),
        damit bei 400 % keine riesige Fläche gezeichnet werden muss."""
        t = self.transform()
        k = t.k
        w, h = self.model.size()
        ox, oy = t.origin
        vw, vh = self._viewport_size()
        self.stage.setGeometry(round(ox), round(oy), max(1, round(w * k)), max(1, round(h * k)))
        if self.web is None:
            return
        i0x = max(0, math.floor((0 - ox) / k))
        i0y = max(0, math.floor((0 - oy) / k))
        i1x = min(w, math.ceil((vw - ox) / k))
        i1y = min(h, math.ceil((vh - oy) / k))
        if i1x <= i0x or i1y <= i0y:
            self.web.setGeometry(0, 0, 1, 1)
            return
        self.web.setGeometry(
            round(i0x * k),
            round(i0y * k),
            max(1, round((i1x - i0x) * k)),
            max(1, round((i1y - i0y) * k)),
        )
        self.web.set_view(i0x, i0y, k)
