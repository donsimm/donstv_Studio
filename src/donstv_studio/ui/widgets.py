"""Bausteine des Hauptfensters: Verbindungsanzeigen, Dock-Titel, Vorschaufläche, Platzhalter."""

from __future__ import annotations

import logging
from pathlib import Path

from PyQt6.QtCore import QEvent, QPointF, QRectF, QSize, Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QIcon, QPainter, QPen, QPixmap, QPolygonF
from PyQt6.QtWidgets import (
    QDockWidget,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QWidget,
)

from donstv_studio.ui import perf, theme

log = logging.getLogger(__name__)

try:  # Das SVG-Modul ist optional: PNG-Symbole müssen auch ohne es erscheinen (F-04).
    from PyQt6 import QtSvg  # noqa: F401

    HAS_SVG = True
except ImportError:  # pragma: no cover - hängt von der Installation ab
    HAS_SVG = False
_svg_hint_given = False

# Status -> (Zustandszeichen, Farbname). U-04: Zustand nie nur durch Farbe, sondern Zeichen + Text.
STATUS_STYLE = {
    "verbunden": ("✔", "ok"),
    "verbindet": ("↻", "warn"),
    "getrennt": ("○", "text_muted"),
    "Fehler": ("✖", "error"),
    "unbekannt": ("?", "text_muted"),
}
# Reihenfolge der Anzeigen: Twitch, YouTube, OBS, NDI
SERVICES = (("twitch", "Twitch"), ("youtube", "YouTube"), ("obs", "OBS"), ("ndi", "NDI"))
SERVICE_ICON_SIZE = 16  # Pixel
ICON_SCALE = 2  # Symbole werden doppelt gross vorbereitet, damit sie auch bei hoher Auflösung scharf sind
ICON_GAP = 6
SERVICE_GAP = 12
INDICATOR_PADDING = 8


def connection_icon_dir() -> Path:
    """Ordner der Dienst-Symbole; liegt neben src/ (assets/icons/connections)."""
    return Path(__file__).resolve().parents[3] / "assets" / "icons" / "connections"


def load_service_pixmap(key: str, directory: Path | None = None) -> QPixmap | None:
    """Quell-Bild des Dienst-Symbols (einfarbig, mit Alpha). None, wenn keine brauchbare Datei da ist.

    PNG zuerst: Es wird auch ohne das Qt-SVG-Modul angezeigt. Nur eine SVG-Datei und kein SVG-Modul:
    einmalig ein Hinweis im Protokoll. Die Logos legt der Nutzer ab (siehe README dort).
    """
    global _svg_hint_given
    folder = directory or connection_icon_dir()
    size = SERVICE_ICON_SIZE * ICON_SCALE
    png = folder / f"{key}.png"
    if png.is_file():
        pm = QPixmap(str(png))
        if not pm.isNull():
            return pm.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    svg = folder / f"{key}.svg"
    if svg.is_file():
        if not HAS_SVG:
            if not _svg_hint_given:
                _svg_hint_given = True
                log.warning("SVG-Symbole brauchen das Qt-SVG-Modul, Debian: vermutlich libqt6svg6")
            return None
        pm = QIcon(str(svg)).pixmap(size, size)
        if not pm.isNull():
            return pm
    return None


def tint_pixmap(source: QPixmap, color: str) -> QPixmap:
    """Füllt die Alpha-Maske des Bildes mit der Farbe (SourceIn); Grösse SERVICE_ICON_SIZE bei Faktor 2."""
    pm = QPixmap(source.size())
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.drawPixmap(0, 0, source)
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    p.fillRect(pm.rect(), QColor(color))
    p.end()
    pm.setDevicePixelRatio(ICON_SCALE)
    return pm


def find_service_icon(key: str, directory: Path | None = None) -> QIcon | None:
    """Symbol des Dienstes (PNG vor SVG) als QIcon, unverändert eingefärbt. None, wenn keine Datei brauchbar ist."""
    pm = load_service_pixmap(key, directory)
    return QIcon(pm) if pm is not None else None


class ConnectionIndicator(QWidget):
    """Eine Verbindungsanzeige: [Dienst-Symbol] «✔ Twitch: verbunden». Feste Breite (F-04)."""

    def __init__(self, key: str, title: str, icon: QPixmap | None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.key, self.title = key, title
        self.status = "unbekannt"
        self.detail = ""
        self._palette = theme.palette(theme.DEFAULT_THEME)
        self._last_style = ""
        self.setObjectName(f"indicator_{key}")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(ICON_GAP)
        # Der Platz für das Symbol bleibt immer reserviert, auch ohne Datei: so verschiebt sich
        # nichts, wenn Symbole später dazukommen.
        self.icon_label = QLabel()
        self.icon_label.setObjectName(f"icon_{key}")
        self.icon_label.setFixedSize(SERVICE_ICON_SIZE, SERVICE_ICON_SIZE)
        self._icon_source = icon
        self.has_icon = icon is not None
        lay.addWidget(self.icon_label)
        self.text_label = QLabel()
        self.text_label.setObjectName(f"status_{key}")
        self.text_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        lay.addWidget(self.text_label)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        self.render()
        self._tint_icon()

    def _tint_icon(self) -> None:
        """Symbol in der Textfarbe des aktuellen Themes (sonst weiss auf hellem Grund unsichtbar)."""
        if self._icon_source is not None:
            self.icon_label.setPixmap(tint_pixmap(self._icon_source, self._palette["text"]))

    def text(self) -> str:
        return self.text_label.text()

    def set_state(self, status: str, detail: str = "") -> None:
        self.status = status if status in STATUS_STYLE else "unbekannt"
        self.detail = detail
        self.render()

    def apply_palette(self, palette: dict[str, str]) -> None:
        self._palette = palette
        self.render()
        self._tint_icon()

    def render(self) -> None:
        symbol, color = STATUS_STYLE[self.status]
        self.text_label.setText(f"{symbol} {self.title}: {self.status}")
        tip = f"{self.title}: {self.status}" + (f" ({self.detail})" if self.detail else "")
        self.setToolTip(tip)
        self.setAccessibleName(tip)
        style = f"color: {self._palette[color]}; font-weight: bold;"
        if style != self._last_style:  # nicht bei jedem Zustand neu setzen (löst sonst Neuberechnung aus)
            self._last_style = style
            self.text_label.setStyleSheet(style)
        self.update_width()

    def update_width(self) -> None:
        """Feste Breite für den längsten möglichen Text («↻ Twitch: verbindet» o. ä.)."""
        self.ensurePolished()
        font = QFont(self.text_label.font())
        font.setBold(True)
        fm = QFontMetrics(font)
        widest = max(fm.horizontalAdvance(f"{s} {self.title}: {st}") for st, (s, _) in STATUS_STYLE.items())
        self.text_label.setFixedWidth(widest + INDICATOR_PADDING)
        self.setFixedWidth(SERVICE_ICON_SIZE + ICON_GAP + widest + INDICATOR_PADDING)

    def event(self, e: QEvent) -> bool:
        if e.type() in (QEvent.Type.StyleChange, QEvent.Type.FontChange, QEvent.Type.PolishRequest):
            ok = super().event(e)
            self.update_width()
            return ok
        return super().event(e)


class ConnectionStatusBar(QWidget):
    """Twitch, YouTube, OBS und NDI immer sichtbar (F-04), rechtsbündig, jede mit fester Breite."""

    def __init__(self, parent: QWidget | None = None, icon_dir: Path | None = None) -> None:
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(SERVICE_GAP)
        self.indicators: dict[str, ConnectionIndicator] = {}
        for key, title in SERVICES:
            ind = ConnectionIndicator(key, title, load_service_pixmap(key, icon_dir))
            self.indicators[key] = ind
            lay.addWidget(ind)

    def status_of(self, key: str) -> str:
        return self.indicators[key].status

    def text_of(self, key: str) -> str:
        return self.indicators[key].text()

    def tooltip_of(self, key: str) -> str:
        return self.indicators[key].toolTip()

    def has_icon(self, key: str) -> bool:
        return self.indicators[key].has_icon

    def set_status(self, key: str, status: str, detail: str = "") -> None:
        if key in self.indicators:  # Dienste, die hier nicht angezeigt werden, bleiben unbeachtet
            self.indicators[key].set_state(status, detail)

    def set_all(self, status: str) -> None:
        for ind in self.indicators.values():
            ind.set_state(status, ind.detail)

    def apply_theme(self, name: str) -> None:
        pal = theme.palette(name)
        for ind in self.indicators.values():
            ind.apply_palette(pal)


# --- Leistungsanzeige (F-68) -----------------------------------------------------------------

PERF_HEIGHT = theme.PERF_TEXT_ROW + 1 + theme.PERF_GRAPH_HEIGHT
PERF_TEXT_ROW = theme.PERF_TEXT_ROW
PERF_GAP = 8


class PerfField(QWidget):
    """Ein Feld: Beschriftung links, Wert rechts, darunter der Verlauf der letzten 60 Sekunden.

    Alles wird in einem Widget gezeichnet; feste Breite für den längsten möglichen Text. Der Wert steht
    immer als Text da (U-04), die Grafik allein sagt nichts.
    """

    PAD = 6
    MIN_WIDTH = 120

    def __init__(self, key: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.key = key
        self.title = perf.TITLES[key]
        self.value_text = perf.NO_VALUE
        self.values: list[float] = [0.0] * perf.HISTORY_LENGTH
        self.scale = 1.0
        self._palette = theme.palette(theme.DEFAULT_THEME)
        self.setObjectName(f"perf_{key}")
        self.setFixedHeight(PERF_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setAccessibleName(f"{self.title}: {self.value_text}")
        self.update_width()

    def _value_font(self) -> QFont:
        font = QFont(self.font())
        font.setBold(True)
        return font

    def update_width(self) -> None:
        """Feste Breite für den längsten möglichen Text (z. B. «↓ 999.9 Mbit/s  ↑ 999.9 Mbit/s»)."""
        title_w = QFontMetrics(self.font()).horizontalAdvance(self.title)
        longest = max(
            QFontMetrics(self._value_font()).horizontalAdvance(t) for t in (perf.LONGEST[self.key], perf.NO_VALUE)
        )
        self.setFixedWidth(max(self.MIN_WIDTH, 2 * self.PAD + title_w + 2 * self.PAD + longest))

    def event(self, e: QEvent) -> bool:
        if e.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange, QEvent.Type.PolishRequest):
            ok = super().event(e)
            self.update_width()
            return ok
        return super().event(e)

    def apply_palette(self, palette: dict[str, str]) -> None:
        self._palette = palette
        self.update()

    def set_value(self, text: str, values: list[float], scale: float) -> None:
        self.value_text, self.values, self.scale = text, values, scale
        tip = f"{self.title}: {text} (letzte {perf.HISTORY_LENGTH} Sekunden)"
        self.setToolTip(tip)
        self.setAccessibleName(f"{self.title}: {text}")
        self.update()

    def graph_rect(self) -> QRectF:
        return QRectF(0, PERF_TEXT_ROW + 1, self.width(), theme.PERF_GRAPH_HEIGHT)

    def paintEvent(self, _e) -> None:
        pal = self._palette
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Textzeile: Beschriftung (Nebentext) links, Wert (fett) rechts
        row = QRectF(self.PAD, 0, self.width() - 2 * self.PAD, PERF_TEXT_ROW)
        p.setPen(QColor(pal["text_muted"]))
        p.drawText(row, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), self.title)
        p.setFont(self._value_font())
        p.setPen(QColor(pal["text"]))
        p.drawText(row, int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter), self.value_text)
        # Verlauf: Fläche mit Linie
        g = self.graph_rect()
        p.fillRect(g, QColor(pal["surface"]))
        line = QColor(pal[f"perf_{self.key}"])
        inner = g.adjusted(1, 2, -1, -1)
        n = len(self.values)
        if n > 1 and self.scale > 0:
            pts = [
                QPointF(
                    inner.left() + i * inner.width() / (n - 1),
                    inner.bottom() - min(max(v / self.scale, 0.0), 1.0) * inner.height(),
                )
                for i, v in enumerate(self.values)
            ]
            fill = QColor(line)
            fill.setAlpha(70)
            area = QPolygonF([QPointF(inner.left(), inner.bottom()), *pts, QPointF(inner.right(), inner.bottom())])
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(fill)
            p.drawPolygon(area)
            pen = QPen(line)
            pen.setWidthF(1.5)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPolyline(QPolygonF(pts))
        p.setPen(QPen(QColor(pal["border"])))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(g.adjusted(0, 0, -1, -1))
        p.end()


class PerfBar(QWidget):
    """CPU, RAM, LAN mit Verlauf (F-68). Ein Zeitgeber der Oberfläche, 1 Messung pro Sekunde, keine Threads."""

    INTERVAL_MS = 1000

    def __init__(self, parent: QWidget | None = None, sampler: perf.Sampler | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("perf_bar")
        self.sampler = sampler or perf.Sampler()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(PERF_GAP)
        self.fields: dict[str, PerfField] = {}
        self.history: dict[str, perf.History] = {}
        for key in perf.FIELDS:
            self.fields[key] = PerfField(key)
            self.history[key] = perf.History()
            lay.addWidget(self.fields[key])
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._mem: tuple[int, int] | None = None
        self.timer = QTimer(self)
        self.timer.setInterval(self.INTERVAL_MS)
        self.timer.timeout.connect(self.tick)
        for key in perf.FIELDS:
            self._show(key, perf.NO_VALUE)

    def apply_theme(self, name: str) -> None:
        pal = theme.palette(name)
        for f in self.fields.values():
            f.apply_palette(pal)

    # --- Zeitgeber: läuft nur, solange das Fenster sichtbar und nicht minimiert ist ---
    def set_active(self, active: bool) -> None:
        if active and not self.timer.isActive():
            self.sampler.reset()  # die erste Messung nach einer Pause setzt nur den Ausgangspunkt
            self.timer.start()
            self.tick()
        elif not active and self.timer.isActive():
            self.timer.stop()

    def tick(self) -> None:
        self.apply(self.sampler.sample())

    def apply(self, s: perf.Sample) -> None:
        self._mem = s.mem
        self.history["cpu"].add(s.cpu)
        self.history["ram"].add(s.mem[0] if s.mem else None)
        self.history["lan"].add(sum(s.net) if s.net else None)
        self._show("cpu", perf.format_cpu(s.cpu))
        self._show("ram", perf.format_mem(s.mem))
        self._show("lan", perf.format_net(s.net))

    def _show(self, key: str, text: str) -> None:
        values = self.history[key].values()
        self.fields[key].set_value(text, values, perf.graph_scale(key, values, self._mem))


def placeholder(text: str, *, muted: bool = True) -> QLabel:
    """Beschriftete leere Fläche für Inhalte, die spätere Bausteine füllen."""
    label = QLabel(text)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setWordWrap(True)
    if muted:
        label.setProperty("muted", True)
    return label


# --- Dock-Titelzeile (wie OBS: fetter Titel, kleine Symbole rechts) --------------------------

def make_dock_icon(kind: str, color: str, size: int = 16) -> QIcon:
    """Zeichnet das Symbol «Lösen» oder «Schliessen» in der Textfarbe des Themes."""
    ratio = 2  # scharf auch bei hoher Auflösung
    pm = QPixmap(size * ratio, size * ratio)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color))
    pen.setWidthF(1.5 * ratio)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    u = size * ratio / 16
    if kind == "close":
        p.drawLine(QPointF(4.5 * u, 4.5 * u), QPointF(11.5 * u, 11.5 * u))
        p.drawLine(QPointF(11.5 * u, 4.5 * u), QPointF(4.5 * u, 11.5 * u))
    else:  # «float»: zwei überlappende Rechtecke
        p.drawRect(QRectF(3.5 * u, 6.5 * u, 6 * u, 6 * u))
        p.drawPolyline([QPointF(6.5 * u, 6.5 * u), QPointF(6.5 * u, 3.5 * u),
                        QPointF(12.5 * u, 3.5 * u), QPointF(12.5 * u, 9.5 * u),
                        QPointF(9.5 * u, 9.5 * u)])  # fmt: skip
    p.end()
    pm.setDevicePixelRatio(ratio)
    return QIcon(pm)


class DockTitleBar(QWidget):
    """Eigene Titelzeile: fester Titel links (fett), «Lösen» und «Schliessen» rechts."""

    def __init__(self, dock: QDockWidget) -> None:
        super().__init__(dock)
        self._dock = dock
        self.setObjectName("dockTitle")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)  # Hintergrund aus dem Stylesheet
        self.setFixedHeight(theme.DOCK_TITLE_HEIGHT)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 0, 4, 0)
        lay.setSpacing(2)
        self.title = QLabel(dock.windowTitle())
        self.title.setObjectName("dockTitleText")
        lay.addWidget(self.title, 1)
        self.float_button = self._button("Lösen", dock_toggle_float=True)
        self.close_button = self._button("Schliessen")
        self.float_button.clicked.connect(lambda: dock.setFloating(not dock.isFloating()))
        self.close_button.clicked.connect(dock.close)
        lay.addWidget(self.float_button)
        lay.addWidget(self.close_button)
        dock.windowTitleChanged.connect(self.title.setText)
        self.apply_theme(theme.DEFAULT_THEME)

    def sizeHint(self) -> QSize:
        # Das Dock-Layout fragt die Höhe hier ab (nicht über setFixedHeight): sonst beginnt der
        # Inhalt zu früh und überdeckt den unteren Teil der Titelzeile.
        return QSize(super().sizeHint().width(), theme.DOCK_TITLE_HEIGHT)

    def minimumSizeHint(self) -> QSize:
        return QSize(super().minimumSizeHint().width(), theme.DOCK_TITLE_HEIGHT)

    def _button(self, tip: str, dock_toggle_float: bool = False) -> QToolButton:
        b = QToolButton(self)
        b.setObjectName("dockFloat" if dock_toggle_float else "dockClose")
        b.setAutoRaise(True)
        b.setToolTip(f"{tip}: {self._dock.windowTitle()}")
        b.setAccessibleName(f"{tip}: {self._dock.windowTitle()}")
        b.setFixedSize(20, 20)
        b.setIconSize(QSize(14, 14))
        b.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        return b

    def apply_theme(self, name: str) -> None:
        color = theme.palette(name)["text"]
        self.float_button.setIcon(make_dock_icon("float", color))
        self.close_button.setIcon(make_dock_icon("close", color))


# --- Vorschaufläche und Leiste darunter (wie OBS) ---------------------------------------------

class PreviewArea(QFrame):
    """Dunkle Fläche mit schwarzer Leinwand in der Mitte. Seitenverhältnis wie das Overlay."""

    MARGIN = 8

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("preview")
        self.ratio = 1920 / 1080  # P06 setzt hier die Auflösung des gewählten Overlays
        self.canvas = QFrame(self)
        self.canvas.setObjectName("canvas")
        lay = QHBoxLayout(self.canvas)
        self.canvas_label = placeholder("Vorschaufläche\nHier erscheint später das gewählte Overlay.")
        self.canvas_label.setObjectName("canvas_label")
        lay.addWidget(self.canvas_label)

    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        self.layout_canvas()

    def layout_canvas(self) -> None:
        aw, ah = max(1, self.width() - 2 * self.MARGIN), max(1, self.height() - 2 * self.MARGIN)
        w, h = (aw, round(aw / self.ratio)) if aw / ah < self.ratio else (round(ah * self.ratio), ah)
        self.canvas.setGeometry((self.width() - w) // 2, (self.height() - h) // 2, w, h)


class PreviewBar(QFrame):
    """«Keine Quelle ausgewählt | Eigenschaften | Filter» unter der Vorschau; Funktion folgt in P06."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("previewbar")
        self.setFixedHeight(theme.PREVIEW_BAR_HEIGHT)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 0, 6, 0)
        lay.setSpacing(8)
        self.label = QLabel("Keine Quelle ausgewählt")
        self.label.setObjectName("previewbar_label")
        self.properties = QPushButton("Eigenschaften")
        self.filters = QPushButton("Filter")
        for b in (self.properties, self.filters):
            b.setEnabled(False)  # gesperrt, bis P06 die Quellen bearbeitbar macht
        self.properties.setObjectName("previewbar_properties")
        self.filters.setObjectName("previewbar_filters")
        lay.addWidget(self.label)
        lay.addWidget(self.properties)
        lay.addWidget(self.filters)
        lay.addStretch(1)
