"""Hauptfenster, Variante A (OBS klassisch): F-01, F-02, F-04, F-06.

Menüleiste, Modul-Reiter mit Verbindungsstatus, Vorschaufläche, vier Docks unten, Statuszeile.
"""

from __future__ import annotations

import base64
import binascii
import logging
from pathlib import Path

from PyQt6.QtCore import QByteArray, QEvent, Qt, QTimer
from PyQt6.QtGui import QAction, QActionGroup, QIcon, QKeySequence
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QDockWidget,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenuBar,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QStackedWidget,
    QTabBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from donstv_studio import __version__
from donstv_studio.ui import theme
from donstv_studio.ui.widgets import (
    STATUS_STYLE,
    ConnectionStatusBar,
    DockTitleBar,
    PerfBar,
    PreviewArea,
    PreviewBar,
    find_service_icon,
    placeholder,
)

log = logging.getLogger(__name__)

# Version 2: Die Anordnung aus P05 (Dock «Overlays» links) wird beim Laden verworfen.
STATE_VERSION = 2
MODULE_OVERLAYS, MODULE_BOT = 0, 1
MODULES = ("Overlays", "Chat-Bot")
BOT_TABS = ("Actions", "Commands", "Timer", "Queues", "Einstellungen")
# (Objektname, Titel, Platzhaltertext)
PERF_LEFT_GAP = 12  # zusätzlicher Abstand zwischen Reitern und Leistungsanzeige
DOCK_HEIGHT = 215  # Höhe der Docks unten in Pixeln (OBS-Bild: 215)
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

        self._build_header()
        self._build_central()
        self._build_docks()
        self._build_menus()
        self._build_status_bar()

        self.arrange_docks()
        self._default_state = self.saveState(STATE_VERSION)
        self._apply_theme_style()

        self._countdown = QTimer(self)
        self._countdown.setInterval(1000)
        self._countdown.timeout.connect(self._tick)

        core.connected.connect(self._on_connected)
        core.unreachable.connect(self._on_unreachable)
        core.status_changed.connect(self._on_status_changed)
        core.statuses_loaded.connect(self._on_statuses)
        core.settings_loaded.connect(self.apply_settings)
        self.banner.hide()
        self._set_core_status("verbindet", "Kern-Dienst: verbindet …")

    # --- Aufbau --------------------------------------------------------
    def _build_header(self) -> None:
        """Fester Fensterkopf: Modul-Reiter links, Verbindungsanzeigen rechts.

        Er wird als Menü-Widget gesetzt (`setMenuWidget`) und liegt damit unter der Menüleiste über
        der ganzen Fensterbreite und über allen Docks. Eine Werkzeugleiste käme in Frage, lässt sich
        aber per Kontextmenü ausblenden und verschieben, und Docks können neben ihr in dieselbe
        Zeile rücken. Das Menü-Widget kann weder gelöst noch ausgeblendet werden, und kein Dock
        und keine Fenstergrösse ändert seine Lage.
        """
        self.menu_bar = QMenuBar()
        self.menu_bar.setObjectName("menubar")

        self.header = QWidget()
        self.header.setObjectName("header")
        self.header.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        row = QHBoxLayout(self.header)
        row.setContentsMargins(8, 0, 8, 0)
        row.setSpacing(12)
        self.header.setFixedHeight(theme.HEADER_HEIGHT)
        self.tabbar = QTabBar()
        self.tabbar.setObjectName("module_tabs")
        self.tabbar.setExpanding(False)
        self.tabbar.setDrawBase(False)
        self.tabbar.setAccessibleName("Modul")
        # Die Reiter behalten ihre natürliche Breite: weder gestaucht noch mit Laufpfeilen verschoben.
        self.tabbar.setUsesScrollButtons(False)
        self.tabbar.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        for name in MODULES:
            self.tabbar.addTab(name)
        self.tabbar.currentChanged.connect(self.set_module)
        row.addWidget(self.tabbar, 0, Qt.AlignmentFlag.AlignVCenter)
        # Leistungsanzeige (F-68): links angeschlossen an die Reiter, feste Breite je Feld
        row.addSpacing(PERF_LEFT_GAP)
        self.perf = PerfBar()
        row.addWidget(self.perf, 0, Qt.AlignmentFlag.AlignVCenter)
        row.addStretch(1)
        self.connections = ConnectionStatusBar()
        row.addWidget(self.connections, 0, Qt.AlignmentFlag.AlignVCenter)

        container = QWidget()
        container.setObjectName("menu_container")
        col = QVBoxLayout(container)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)
        col.addWidget(self.menu_bar)
        col.addWidget(self.header)
        self.setMenuWidget(container)

    def _build_central(self) -> None:
        central = QWidget()
        outer = QVBoxLayout(central)
        outer.setContentsMargins(theme.DOCK_GAP, theme.DOCK_GAP, theme.DOCK_GAP, 0)
        outer.setSpacing(theme.DOCK_GAP)

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

        overlays_page = QWidget()
        page = QVBoxLayout(overlays_page)
        page.setContentsMargins(0, 0, 0, 0)
        page.setSpacing(theme.DOCK_GAP)
        self.preview = PreviewArea()
        self.preview_bar = PreviewBar()
        page.addWidget(self.preview, 1)
        page.addWidget(self.preview_bar)
        self.stack.addWidget(overlays_page)

        self.bot_tabs = QTabWidget()
        self.bot_tabs.setObjectName("bot_tabs")
        for name in BOT_TABS:
            self.bot_tabs.addTab(placeholder(f"{name}\nInhalt folgt mit dem Chat-Bot-Baustein."), name)
        self.stack.addWidget(self.bot_tabs)
        outer.addWidget(self.stack, 1)
        self.setCentralWidget(central)

    def _build_docks(self) -> None:
        self.docks: list[QDockWidget] = []
        self.dock_titles: list[DockTitleBar] = []
        for name, title, text in DOCKS:
            dock = QDockWidget(title, self)
            dock.setObjectName(name)
            dock.setFeatures(
                QDockWidget.DockWidgetFeature.DockWidgetClosable
                | QDockWidget.DockWidgetFeature.DockWidgetMovable
                | QDockWidget.DockWidgetFeature.DockWidgetFloatable
            )
            titlebar = DockTitleBar(dock)
            dock.setTitleBarWidget(titlebar)
            body = QFrame()
            body.setObjectName("dockbody")
            lay = QVBoxLayout(body)
            lay.setContentsMargins(6, 6, 6, 6)
            lay.addWidget(placeholder(f"{text}\nInhalt folgt."))
            dock.setWidget(body)
            dock.setMinimumHeight(theme.DOCK_TITLE_HEIGHT + 60)
            self.docks.append(dock)
            self.dock_titles.append(titlebar)

    def arrange_docks(self) -> None:
        """Standardanordnung (Variante A): vier Docks nebeneinander unten, wie bei OBS."""
        for dock in self.docks:
            dock.setFloating(False)  # zuerst andocken, sonst bliebe ein schwebendes Dock schwebend
            self.removeDockWidget(dock)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.docks[0])
        for left, right in zip(self.docks, self.docks[1:], strict=False):
            self.splitDockWidget(left, right, Qt.Orientation.Horizontal)
        for dock in self.docks:
            dock.show()
        self.resizeDocks(self.docks, [1] * len(self.docks), Qt.Orientation.Horizontal)
        self.resizeDocks([self.docks[0]], [DOCK_HEIGHT], Qt.Orientation.Vertical)

    def _build_menus(self) -> None:
        bar = self.menu_bar
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
        self.statusBar().setSizeGripEnabled(False)
        self.statusBar().setFixedHeight(theme.STATUS_BAR_HEIGHT)
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
            self.arrange_docks()
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
        self.perf.apply_theme(self.theme)
        self._update_minimum_width()
        for bar in self.dock_titles:
            bar.apply_theme(self.theme)
        if hasattr(self, "_core_state"):
            self._set_core_status(*self._core_state)

    def _update_minimum_width(self) -> None:
        """Mindestbreite: Reiter, Leistungsfelder und vier Verbindungsanzeigen passen nebeneinander (F-68)."""
        self.header.ensurePolished()
        lay = self.header.layout()
        lay.invalidate()
        lay.activate()
        self.setMinimumWidth(max(lay.minimumSize().width(), 1))

    # --- Leistungsanzeige läuft nur bei sichtbarem, nicht minimiertem Fenster -------------------
    def _sync_perf(self) -> None:
        self.perf.set_active(self.isVisible() and not self.isMinimized())

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._sync_perf()

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self._sync_perf()

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange:
            self._sync_perf()

    def open_settings(self) -> None:
        self.settings_dialog = SettingsDialog(self)
        self.settings_dialog.show()

    def _about(self) -> None:
        text = f"donstv_Studio {__version__}\nOverlays und Chat-Bot."
        if find_service_icon("ndi") is not None:  # NDI-Symbol in Gebrauch: Markenhinweis nötig
            text += "\n\nNDI® is a registered trademark of Vizrt NDI AB."
        QMessageBox.about(self, "Über donstv_Studio", text)

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

    def _on_status_changed(self, name: str, status: str, detail: str = "") -> None:
        self.connections.set_status(name, status, detail)

    def _on_statuses(self, statuses: dict) -> None:
        """Zustand aller Dienste beim Verbinden: name -> {"status", "detail"}."""
        for key in self.connections.indicators:
            info = statuses.get(key) or {}
            self.connections.set_status(key, info.get("status", "getrennt"), info.get("detail", ""))

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
