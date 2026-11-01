"""Bausteine des Hauptfensters: Verbindungsanzeigen, Dock-Titel, Vorschaufläche, Platzhalter."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QEvent, QPointF, QRectF, QSize, Qt
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QIcon, QPainter, QPen, QPixmap
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

from donstv_studio.ui import theme

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
ICON_GAP = 6
SERVICE_GAP = 12
INDICATOR_PADDING = 8


def connection_icon_dir() -> Path:
    """Ordner der Dienst-Symbole; liegt neben src/ (assets/icons/connections)."""
    return Path(__file__).resolve().parents[3] / "assets" / "icons" / "connections"


def find_service_icon(key: str, directory: Path | None = None) -> QIcon | None:
    """Symbol des Dienstes aus <key>.svg oder <key>.png. None, wenn keine brauchbare Datei da ist.

    Die Logos legt der Nutzer ab; sie werden hier weder erzeugt noch geladen (siehe README dort).
    """
    folder = directory or connection_icon_dir()
    for ext in ("svg", "png"):
        path = folder / f"{key}.{ext}"
        if path.is_file():
            icon = QIcon(str(path))
            if not icon.isNull() and not icon.pixmap(SERVICE_ICON_SIZE, SERVICE_ICON_SIZE).isNull():
                return icon
    return None


class ConnectionIndicator(QWidget):
    """Eine Verbindungsanzeige: [Dienst-Symbol] «✔ Twitch: verbunden». Feste Breite (F-04)."""

    def __init__(self, key: str, title: str, icon: QIcon | None, parent: QWidget | None = None) -> None:
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
        self.has_icon = icon is not None
        if icon is not None:
            self.icon_label.setPixmap(icon.pixmap(SERVICE_ICON_SIZE, SERVICE_ICON_SIZE))
        lay.addWidget(self.icon_label)
        self.text_label = QLabel()
        self.text_label.setObjectName(f"status_{key}")
        self.text_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        lay.addWidget(self.text_label)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        self.render()

    def text(self) -> str:
        return self.text_label.text()

    def set_state(self, status: str, detail: str = "") -> None:
        self.status = status if status in STATUS_STYLE else "unbekannt"
        self.detail = detail
        self.render()

    def apply_palette(self, palette: dict[str, str]) -> None:
        self._palette = palette
        self.render()

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
            ind = ConnectionIndicator(key, title, find_service_icon(key, icon_dir))
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
