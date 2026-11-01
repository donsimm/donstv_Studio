"""Hauptfenster, Variante A (OBS klassisch): F-01, F-02, F-04, F-06.

Menüleiste, Modul-Reiter mit Verbindungsstatus, Vorschaufläche, vier Docks unten, Statuszeile.
"""

from __future__ import annotations

import base64
import binascii
import logging
from pathlib import Path

from PyQt6.QtCore import QByteArray, Qt, QTimer
from PyQt6.QtGui import QAction, QActionGroup, QIcon, QKeySequence
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QDockWidget,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QStackedWidget,
    QTabBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from donstv_studio import __version__
from donstv_studio.ui import theme
from donstv_studio.ui.widgets import STATUS_STYLE, ConnectionStatusBar, placeholder

log = logging.getLogger(__name__)

STATE_VERSION = 1
MODULE_OVERLAYS, MODULE_BOT = 0, 1
MODULES = ("Overlays", "Chat-Bot")
BOT_TABS = ("Actions", "Commands", "Timer", "Queues", "Einstellungen")
# (Objektname, Titel, Platzhaltertext)
DOCKS = (
    ("dock_overlays", "Overlays", "Liste der Overlays: anlegen, kopieren, löschen."),
    ("dock_sources", "Quellen", "Quellen des gewählten Overlays: Reihenfolge, Sichtbarkeit."),
    ("dock_properties", "Eigenschaften", "Lage, Grösse und Inhalt der gewählten Quelle."),
    ("dock_control", "Steuerung", "URL der Browserquelle, Ausgabeart, Speichern."),
)
KEY_THEME, KEY_GEOMETRY, KEY_STATE = "ui.theme", "ui.geometry", "ui.dock_state"


def find_icon() -> QIcon:
    """Platzhalter-Icon aus assets/icon.svg (liegt neben src/); fehlt es, bleibt das Fenster ohne Icon."""
    path = Path(__file__).resolve().parents[3] / "assets" / "icon.svg"
    return QIcon(str(path)) if path.exists() else QIcon()


def _encode(data: QByteArray) -> str:
    return base64.b64encode(bytes(data)).decode("ascii")


def _decode(text: str) -> QByteArray | None:
    try:
        return QByteArray(base64.b64decode(text.encode("ascii"), validate=True))
    except (binascii.Error, ValueError, UnicodeEncodeError):
        return None


class SettingsDialog(QDialog):
    """Einstellungen: Design der Oberfläche (F-06)."""

    def __init__(self, window: MainWindow) -> None:
        super().__init__(window)
        self.setWindowTitle("Einstellungen")
        self.setObjectName("settings_dialog")
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Design der Programmoberfläche"))
        self.radios: dict[str, QRadioButton] = {}
        for key in (theme.DARK, theme.LIGHT):
            radio = QRadioButton(theme.THEME_NAMES[key])
            radio.setObjectName(f"theme_{key}")
            radio.setChecked(window.theme == key)
            radio.toggled.connect(lambda on, k=key: on and window.set_theme(k))
            self.radios[key] = radio
            lay.addWidget(radio)
        close = QPushButton("Schliessen")
        close.clicked.connect(self.accept)
        lay.addWidget(close)


class MainWindow(QMainWindow):
    def __init__(self, core) -> None:
        super().__init__()
        self._core = core
        self.theme = theme.DEFAULT_THEME
        self._module = MODULE_OVERLAYS
        self._overlay_dock_state: QByteArray | None = None
        self._settings_loaded = False
        self._retry_remaining = 0
        self._reason = ""

        self.setWindowTitle("donstv_Studio")
        self.setWindowIcon(find_icon())
        self.resize(1280, 800)
        self.setDockNestingEnabled(True)

        self._build_central()
        self._build_docks()
        self._build_menus()
        self._build_status_bar()

        self._default_state = self.saveState(STATE_VERSION)
        self._apply_theme_style()

        self._countdown = QTimer(self)
        self._countdown.setInterval(1000)
        self._countdown.timeout.connect(self._tick)

        core.connected.connect(self._on_connected)
        core.unreachable.connect(self._on_unreachable)
        core.status_changed.connect(self.connections.set_status)
        core.statuses_loaded.connect(self._on_statuses)
        core.settings_loaded.connect(self.apply_settings)
        self.banner.hide()
        self._set_core_status("verbindet", "Kern-Dienst: verbindet …")

    # --- Aufbau --------------------------------------------------------
    def _build_central(self) -> None:
        central = QWidget()
        outer = QVBoxLayout(central)
        outer.setContentsMargins(8, 8, 8, 4)

        header = QHBoxLayout()
        self.tabbar = QTabBar()
        self.tabbar.setObjectName("module_tabs")
        self.tabbar.setExpanding(False)
        self.tabbar.setAccessibleName("Modul")
        for name in MODULES:
            self.tabbar.addTab(name)
        self.tabbar.currentChanged.connect(self.set_module)
        header.addWidget(self.tabbar)
        header.addStretch(1)
        self.connections = ConnectionStatusBar()
        header.addWidget(self.connections)
        outer.addLayout(header)

        self.banner = QFrame()
        self.banner.setObjectName("banner")
        banner_lay = QHBoxLayout(self.banner)
        self.banner_label = QLabel()
        self.banner_label.setObjectName("banner_label")
        self.banner_label.setWordWrap(True)
        banner_lay.addWidget(self.banner_label)
        outer.addWidget(self.banner)

        self.stack = QStackedWidget()
        self.stack.setObjectName("modules")
        self.preview = QFrame()
        self.preview.setObjectName("preview")
        pv = QVBoxLayout(self.preview)
        pv.addWidget(placeholder("Vorschaufläche\nHier erscheint später das gewählte Overlay."))
        self.stack.addWidget(self.preview)

        self.bot_tabs = QTabWidget()
        self.bot_tabs.setObjectName("bot_tabs")
        for name in BOT_TABS:
            self.bot_tabs.addTab(placeholder(f"{name}\nInhalt folgt mit dem Chat-Bot-Baustein."), name)
        self.stack.addWidget(self.bot_tabs)
        outer.addWidget(self.stack, 1)
        self.setCentralWidget(central)

    def _build_docks(self) -> None:
        self.docks: list[QDockWidget] = []
        for name, title, text in DOCKS:
            dock = QDockWidget(title, self)
            dock.setObjectName(name)
            dock.setFeatures(
                QDockWidget.DockWidgetFeature.DockWidgetClosable
                | QDockWidget.DockWidgetFeature.DockWidgetMovable
                | QDockWidget.DockWidgetFeature.DockWidgetFloatable
            )
            dock.setWidget(placeholder(f"{text}\nInhalt folgt."))
            dock.setMinimumHeight(120)
            self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, dock)
            self.docks.append(dock)

    def _build_menus(self) -> None:
        bar = self.menuBar()
        file_menu = bar.addMenu("&Datei")
        quit_action = QAction("&Beenden", self, shortcut=QKeySequence("Ctrl+Q"))
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        edit_menu = bar.addMenu("B&earbeiten")
        for text, key in (("&Rückgängig", "Ctrl+Z"), ("&Wiederholen", "Ctrl+Shift+Z")):
            act = QAction(text, self, shortcut=QKeySequence(key))
            act.setEnabled(False)  # folgt mit dem Editor (P06)
            edit_menu.addAction(act)

        view_menu = bar.addMenu("&Ansicht")
        group = QActionGroup(self)
        self.module_actions: list[QAction] = []
        for i, name in enumerate(MODULES):
            act = QAction(name, self, checkable=True, shortcut=QKeySequence(f"Ctrl+{i + 1}"))
            act.setChecked(i == self._module)
            act.triggered.connect(lambda _=False, idx=i: self.set_module(idx))
            group.addAction(act)
            view_menu.addAction(act)
            self.module_actions.append(act)

        self.docks_menu = bar.addMenu("D&ocks")
        for dock in self.docks:
            self.docks_menu.addAction(dock.toggleViewAction())
        self.docks_menu.addSeparator()
        self.reset_docks_action = QAction("&Standardanordnung", self)
        self.reset_docks_action.triggered.connect(self.reset_docks)
        self.docks_menu.addAction(self.reset_docks_action)

        tools_menu = bar.addMenu("&Werkzeuge")
        settings = QAction("&Einstellungen …", self, shortcut=QKeySequence("Ctrl+,"))
        settings.triggered.connect(self.open_settings)
        tools_menu.addAction(settings)

        help_menu = bar.addMenu("&Hilfe")
        about = QAction("&Über donstv_Studio", self)
        about.triggered.connect(self._about)
        help_menu.addAction(about)

    def _build_status_bar(self) -> None:
        self.core_status = QLabel()
        self.core_status.setObjectName("core_status")
        self.statusBar().addPermanentWidget(self.core_status)
        self.statusBar().showMessage("Bereit")

    # --- Module --------------------------------------------------------
    def set_module(self, index: int) -> None:
        if index == self._module:
            return
        if self._module == MODULE_OVERLAYS:
            self._overlay_dock_state = self.saveState(STATE_VERSION)
        self._module = index
        self.stack.setCurrentIndex(index)
        for i, act in enumerate(self.module_actions):
            act.setChecked(i == index)
        if self.tabbar.currentIndex() != index:
            self.tabbar.setCurrentIndex(index)
        in_overlays = index == MODULE_OVERLAYS
        # Die Docks gehören zum Modul «Overlays».
        self.docks_menu.setEnabled(in_overlays)
        if in_overlays:
            if self._overlay_dock_state is not None:
                self.restoreState(self._overlay_dock_state, STATE_VERSION)
        else:
            for dock in self.docks:
                dock.hide()

    @property
    def module(self) -> int:
        return self._module

    def reset_docks(self) -> None:
        if self._module == MODULE_OVERLAYS:
            self.restoreState(self._default_state, STATE_VERSION)
        else:
            self._overlay_dock_state = self._default_state

    # --- Theme ---------------------------------------------------------
    def set_theme(self, name: str, save: bool = True) -> None:
        if name not in theme.PALETTES:
            return
        changed = name != self.theme
        self.theme = name
        self._apply_theme_style()
        if changed and save and self._settings_loaded:
            self._core.save_setting(KEY_THEME, name)

    def _apply_theme_style(self) -> None:
        app = QApplication.instance()
        sheet = theme.stylesheet(self.theme)
        (app or self).setStyleSheet(sheet)
        self.connections.apply_theme(self.theme)
        if hasattr(self, "_core_state"):
            self._set_core_status(*self._core_state)

    def open_settings(self) -> None:
        self.settings_dialog = SettingsDialog(self)
        self.settings_dialog.show()

    def _about(self) -> None:
        QMessageBox.about(self, "Über donstv_Studio", f"donstv_Studio {__version__}\nOverlays und Chat-Bot.")

    # --- Kern-Dienst ---------------------------------------------------
    def _on_connected(self) -> None:
        self._countdown.stop()
        self.banner.hide()
        self._set_core_status("verbunden", "Kern-Dienst: verbunden")

    def _on_unreachable(self, reason: str, retry_seconds: float) -> None:
        self.connections.set_all("unbekannt")
        self._reason = reason
        self._retry_remaining = round(retry_seconds)
        self._render_unreachable()
        self.banner.show()
        if not self._countdown.isActive():
            self._countdown.start()

    def _tick(self) -> None:
        self._retry_remaining = max(0, self._retry_remaining - 1)
        self._render_unreachable()

    def _render_unreachable(self) -> None:
        retry = f" Neuer Versuch in {self._retry_remaining} s." if self._retry_remaining else ""
        self.banner_label.setText(
            f"⚠ {self._reason}.{retry}\nStarte den Kern-Dienst im Terminal mit «donstv-core»."
        )
        self._set_core_status("Fehler", "Kern-Dienst: nicht erreichbar")

    def _set_core_status(self, status: str, text: str) -> None:
        """Zustand des Kern-Dienstes in der Statuszeile: Symbol + Text + Farbe (U-04)."""
        self._core_state = (status, text)
        symbol, color = STATUS_STYLE[status]
        self.core_status.setText(f"{symbol} {text}")
        self.core_status.setStyleSheet(f"color: {theme.palette(self.theme)[color]}; font-weight: bold;")

    def _on_statuses(self, statuses: dict) -> None:
        for key in ("twitch", "obs", "ndi"):
            self.connections.set_status(key, statuses.get(key, "getrennt"))

    # --- Layout merken -------------------------------------------------
    def layout_values(self) -> dict[str, str]:
        state = self._overlay_dock_state if self._module == MODULE_BOT else self.saveState(STATE_VERSION)
        return {
            KEY_THEME: self.theme,
            KEY_GEOMETRY: _encode(self.saveGeometry()),
            KEY_STATE: _encode(state) if state is not None else _encode(self._default_state),
        }

    def apply_settings(self, values: dict) -> None:
        """Stellt Theme, Fensterposition und Dock-Anordnung aus den gespeicherten Werten her."""
        name = values.get(KEY_THEME)
        if name in theme.PALETTES:
            self.set_theme(name, save=False)
        geometry = _decode(values.get(KEY_GEOMETRY, ""))
        if geometry is not None and not geometry.isEmpty():
            self.restoreGeometry(geometry)
        state = _decode(values.get(KEY_STATE, ""))
        if state is not None and not state.isEmpty():
            if self._module == MODULE_OVERLAYS:
                if not self.restoreState(state, STATE_VERSION):
                    log.warning("Gespeicherte Dock-Anordnung passt nicht und wird ignoriert")
            else:
                self._overlay_dock_state = state
        self._settings_loaded = True

    def closeEvent(self, event) -> None:
        if self._settings_loaded:
            self._core.save_settings_blocking(self.layout_values())
        super().closeEvent(event)
