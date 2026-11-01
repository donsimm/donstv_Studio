"""Kleine Bausteine des Hauptfensters: Verbindungsstatus und Platzhalter."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QWidget

from donstv_studio.ui import theme

# Status -> (Symbol, Farbname, Text). U-04: Zustand nie nur durch Farbe, sondern Symbol + Text.
STATUS_STYLE = {
    "verbunden": ("✔", "ok"),
    "verbindet": ("↻", "warn"),
    "getrennt": ("○", "text_muted"),
    "Fehler": ("✖", "error"),
    "unbekannt": ("?", "text_muted"),
}
SERVICES = (("twitch", "Twitch"), ("obs", "OBS"), ("ndi", "NDI"))


class ConnectionStatusBar(QWidget):
    """Zeigt Twitch, OBS und NDI immer an (F-04): «✔ Twitch: verbunden»."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(16)
        self._labels: dict[str, QLabel] = {}
        self._status: dict[str, str] = {}
        self._palette = theme.palette(theme.DEFAULT_THEME)
        for key, title in SERVICES:
            label = QLabel()
            label.setObjectName(f"status_{key}")
            label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
            self._labels[key] = label
            lay.addWidget(label)
            self.set_status(key, "unbekannt")

    def status_of(self, key: str) -> str:
        return self._status[key]

    def text_of(self, key: str) -> str:
        return self._labels[key].text()

    def set_status(self, key: str, status: str) -> None:
        if key not in self._labels:
            return  # Dienste, die hier nicht angezeigt werden
        if status not in STATUS_STYLE:
            status = "unbekannt"
        self._status[key] = status
        self._render(key)

    def set_all(self, status: str) -> None:
        for key, _ in SERVICES:
            self.set_status(key, status)

    def apply_theme(self, name: str) -> None:
        self._palette = theme.palette(name)
        for key, _ in SERVICES:
            self._render(key)

    def _render(self, key: str) -> None:
        title = dict(SERVICES)[key]
        status = self._status[key]
        symbol, color = STATUS_STYLE[status]
        label = self._labels[key]
        label.setText(f"{symbol} {title}: {status}")
        label.setToolTip(f"{title}: {status}")
        label.setStyleSheet(f"color: {self._palette[color]}; font-weight: bold;")
        label.setAccessibleName(f"{title}: {status}")


def placeholder(text: str, *, muted: bool = True) -> QLabel:
    """Beschriftete leere Fläche für Inhalte, die spätere Bausteine füllen."""
    label = QLabel(text)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setWordWrap(True)
    if muted:
        label.setProperty("muted", True)
    return label
