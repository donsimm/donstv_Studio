"""Hauptfenster, Variante A (OBS klassisch): F-01, F-02, F-04, F-06.

Menüleiste, Modul-Reiter mit Verbindungsstatus, Vorschaufläche, vier Docks unten, Statuszeile.
"""

from __future__ import annotations

import base64
import binascii
import json
import logging
import time
from pathlib import Path

from PyQt6.QtCore import QByteArray, QEvent, Qt, QTimer
from PyQt6.QtGui import QAction, QActionGroup, QFontMetrics, QIcon, QKeySequence
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
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
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTabBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from donstv_studio import __version__
from donstv_studio.ui import diagnose, indicators, theme
from donstv_studio.ui import geometry as geo
from donstv_studio.ui.backend import DirectRunner, TaskRunner
from donstv_studio.ui.bot_page import BotModel, BotSettingsTab, ChatPanel, CommandsTab, LogPanel
from donstv_studio.ui.editor_docks import ControlDock, OverlaysDock, PropertiesDock, SourcesDock
from donstv_studio.ui.editor_model import EditorModel
from donstv_studio.ui.editor_prefs import EditorPrefs
from donstv_studio.ui.editor_view import EditorView
from donstv_studio.ui.widgets import (
    STATUS_STYLE,
    ConnectionStatusBar,
    DockTitleBar,
    PerfBar,
    PreviewArea,
    find_service_icon,
    placeholder,
)

log = logging.getLogger(__name__)

# Version 2: Die Anordnung aus P05 (Dock «Overlays» links) wird beim Laden verworfen.
# Version 3 (P07): Docks «Chat» und «Protokoll» des Chat-Bots; ältere Anordnungen kennen sie nicht und werden verworfen.
STATE_VERSION = 3
MODULE_OVERLAYS, MODULE_BOT = 0, 1
MODULES = ("Overlays", "Chat-Bot")
BOT_TABS = ("Actions", "Commands", "Timer", "Queues", "Einstellungen")
PERF_LEFT_GAP = 16  # zusätzlicher Abstand zwischen den Verbindungs-Buttons und der Leistungsanzeige
DOCK_HEIGHT = 215  # Höhe der Docks unten in Pixeln (OBS-Bild: 215)
# (Objektname, Titel)
DOCKS = (
    ("dock_overlays", "Overlays"),
    ("dock_sources", "Quellen"),
    ("dock_properties", "Eigenschaften"),
    ("dock_control", "Steuerung"),
)
# Docks des Moduls «Chat-Bot» (P07): (Objektname, Titel)
BOT_DOCKS = (("dock_chat", "Chat"), ("dock_bot_log", "Protokoll"))
BOT_CHAT_WIDTH = 360
KEY_THEME, KEY_GEOMETRY, KEY_STATE = "ui.theme", "ui.geometry", "ui.dock_state"
# FIX (P06d5) fix_restore_after_show: Das Fenster gilt als in seiner Endgrösse, wenn so lange keine Grössenänderung
# mehr kam. Qt selbst verwirft eine aufgeschobene Anordnung nach 150 ms ohne weitere Grössenänderung
# (qmainwindowlayout.cpp 6.8.2, Zeilen 2333–2343); 200 ms liegen darüber. Spätestens nach RESTORE_MAX_MS ab dem
# Anzeigen wird die Anordnung trotzdem angewendet.
RESTORE_SETTLE_MS = 200
RESTORE_MAX_MS = 2000
_MAXIMIZED = Qt.WindowState.WindowMaximized | Qt.WindowState.WindowFullScreen


def find_icon() -> QIcon:
    """Platzhalter-Icon aus assets/icon.svg (liegt neben src/); fehlt es, bleibt das Fenster ohne Icon."""
    path = Path(__file__).resolve().parents[3] / "assets" / "icon.svg"
    return QIcon(str(path)) if path.exists() else QIcon()


# Gespeicherte Fensterlage und Dock-Anordnung tragen die Layout-Version im Wert. Zustände aus früheren Versionen
# (ohne diese Marke) werden nicht wiederhergestellt: Auf dem Laptop (Debian 13: Qt 6.8.2 mit PyQt6 6.9.0) stürzte
# `restoreState` mit einer alten Anordnung ab, sobald der Kern verbunden war.
LAYOUT_TAG = "v3:"


def _encode(data: QByteArray) -> str:
    return LAYOUT_TAG + base64.b64encode(bytes(data)).decode("ascii")


def _decode(text: str) -> QByteArray | None:
    if not text.startswith(LAYOUT_TAG):
        return None
    try:
        return QByteArray(base64.b64decode(text[len(LAYOUT_TAG) :].encode("ascii"), validate=True))
    except (binascii.Error, ValueError, UnicodeEncodeError):
        return None


def _scroll(widget: QWidget) -> QScrollArea:
    """Inhalt mit Bildlauf: Die Reiter des Chat-Bots dürfen die Mindesthöhe des Fensters nicht vergrössern."""
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setWidget(widget)
    return area


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

        # Editor-Modell: Zugriff auf die Overlay-Schnittstelle des Kerns (P03). Ohne Zugang (Tests) bleibt es leer.
        backend = getattr(core, "backend", None)
        self.runner = getattr(core, "runner", None) or (
            TaskRunner(self) if backend is not None else DirectRunner(self)
        )
        self.prefs = EditorPrefs(getattr(core, "save_setting", None), self)
        self.model = EditorModel(backend, self.runner, getattr(core, "save_setting", None), self)
        self.bot = BotModel(getattr(core, "bot_backend", None) or backend, self.runner, self)

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
        # P06d2: Mindestbreite nach Schrift- oder Breitenwechsel der Leistungsfelder zusammengefasst nach dem Ereignis
        # neu berechnen, nie innerhalb eines Stil- oder Layout-Ereignisses (CLAUDE.md Regel 16)
        self._min_width_timer = QTimer(self)
        self._min_width_timer.setSingleShot(True)
        self._min_width_timer.setInterval(0)
        self._min_width_timer.timeout.connect(self._update_minimum_width)
        self.perf.widths_changed.connect(self._request_minimum_width)
        self._applied_geometry: bytes | None = None  # zuletzt angewandte gespeicherte Fensterlage
        # FIX (P06d5): Dock-Anordnung nur einmal und bei maximierter Lage erst nach dem Anzeigen (diagnose.py)
        # zuletzt angewandte (oder vorgemerkte) Dock-Anordnung; vorgemerkt bis nach show(); beides hergestellt
        self._applied_state: bytes | None = None
        self._pending_state: QByteArray | None = None
        self.layout_restored = False
        self._restore_started = False
        self._resized_since_show = False
        self._restore_deadline = 0.0
        self._restore_timer = QTimer(self)  # wartet, bis das Fenster seine Endgrösse hat
        self._restore_timer.setSingleShot(True)
        self._restore_timer.setInterval(RESTORE_SETTLE_MS)
        self._restore_timer.timeout.connect(self._finish_restore)
        if diagnose.fix("fix_list_after_restore"):
            for panel in (self.overlays_panel, self.sources_panel):
                panel.stack.hold()
        self._apply_theme_style()

        self._countdown = QTimer(self)
        self._countdown.setInterval(1000)
        self._countdown.timeout.connect(self._tick)

        core.connected.connect(self._on_connected)
        core.unreachable.connect(self._on_unreachable)
        core.status_changed.connect(self._on_status_changed)
        core.statuses_loaded.connect(self._on_statuses_json)
        core.settings_loaded.connect(self._on_settings_json)
        core.connected.connect(
            self.model.load
        )  # nach jedem (Wieder-)Verbinden den Stand der Overlays holen
        core.connected.connect(self.bot.load)
        if hasattr(core, "event_received"):
            core.event_received.connect(self.bot.on_event)
        self.model.error.connect(lambda msg: self.statusBar().showMessage(msg, 8000))
        self.bot.error.connect(lambda msg: self.statusBar().showMessage(msg, 8000))
        self.banner.hide()
        self._set_core_status("verbindet", "Kern-Dienst: verbindet …")

    # --- Aufbau --------------------------------------------------------
    def _build_header(self) -> None:
        """Fester Fensterkopf mit Rahmen: Modul-Reiter links, rechts Verbindungs-Buttons und ganz rechts die Leistungsanzeige.

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
        self.header.setFixedHeight(theme.HEADER_HEIGHT)
        row = QHBoxLayout(self.header)
        row.setContentsMargins(8, 0, 8, 0)
        row.setSpacing(12)
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
        row.addStretch(1)
        # Rechts: vier Verbindungs-Buttons (F-04), daneben ganz rechts die Leistungsanzeige (F-68)
        self.connections = ConnectionStatusBar()
        row.addWidget(self.connections, 0, Qt.AlignmentFlag.AlignVCenter)
        row.addSpacing(PERF_LEFT_GAP)
        self.perf = PerfBar()
        row.addWidget(self.perf, 0, Qt.AlignmentFlag.AlignVCenter)

        # Rahmen des Kopfes mit kleinem Abstand zum Fensterrand
        header_wrap = QWidget()
        header_wrap.setObjectName("header_wrap")
        wrap = QVBoxLayout(header_wrap)
        wrap.setContentsMargins(theme.HEADER_MARGIN, 2, theme.HEADER_MARGIN, theme.HEADER_MARGIN)
        wrap.addWidget(self.header)

        container = QWidget()
        container.setObjectName("menu_container")
        col = QVBoxLayout(container)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)
        col.addWidget(self.menu_bar)
        col.addWidget(header_wrap)
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
        self.editor = EditorView(self.model, self.prefs)
        self.preview.set_editor(self.editor)
        self.editor.overlay_available.connect(self.preview.show_editor)
        self.editor.zoom_changed.connect(self._show_zoom)
        page.addWidget(self.preview, 1)
        self.stack.addWidget(overlays_page)

        self.bot_tabs = QTabWidget()
        self.bot_tabs.setObjectName("bot_tabs")
        self.commands_tab = CommandsTab(self.bot)
        self.bot_settings_tab = BotSettingsTab(self.bot)
        filled = {
            "Commands": _scroll(self.commands_tab),
            "Einstellungen": _scroll(self.bot_settings_tab),
        }
        for name in BOT_TABS:
            # Actions, Timer und Queues folgen mit F-46 bis F-51.
            page = filled.get(name) or placeholder(
                f"{name}\nFolgt in einem späteren Baustein (F-46 bis F-51)."
            )
            self.bot_tabs.addTab(page, name)
        self.bot_tabs.setCurrentWidget(filled["Commands"])  # Actions ist im Gerüst leer
        self.stack.addWidget(self.bot_tabs)
        outer.addWidget(self.stack, 1)
        self.setCentralWidget(central)

    def _build_docks(self) -> None:
        self.docks: list[QDockWidget] = []
        self.dock_titles: list[DockTitleBar] = []
        self.overlays_panel = OverlaysDock(self.model)
        self.sources_panel = SourcesDock(self.model)
        # F-74: F2 benennt die gewählte Quelle auch um, wenn der Fokus in der Vorschau liegt
        if not diagnose.off("rename"):  # DIAGNOSE (P06d2): ohne Umbenennen wie P08
            self.editor.addAction(self.sources_panel.rename_action)
        self.properties_panel = PropertiesDock(self.model)
        self.control_panel = ControlDock(self.model, self.prefs)
        self.control_panel.copied.connect(
            lambda: self.statusBar().showMessage("Adresse der Browserquelle kopiert", 4000)
        )
        self.panels = [
            self.overlays_panel,
            self.sources_panel,
            self.properties_panel,
            self.control_panel,
        ]
        for (name, title), panel in zip(DOCKS, self.panels, strict=True):
            dock = QDockWidget(title, self)
            dock.setObjectName(name)
            dock.setFeatures(
                QDockWidget.DockWidgetFeature.DockWidgetClosable
                | QDockWidget.DockWidgetFeature.DockWidgetMovable
                | QDockWidget.DockWidgetFeature.DockWidgetFloatable
            )
            titlebar = DockTitleBar(dock)
            dock.setTitleBarWidget(titlebar)
            dock.setWidget(panel.body)
            dock.setMinimumHeight(theme.DOCK_TITLE_HEIGHT + 60)
            self.docks.append(dock)
            self.dock_titles.append(titlebar)

        # Docks des Chat-Bots: nur im Modul «Chat-Bot» sichtbar; nicht schliessbar, damit sie nicht verloren gehen
        self.chat_panel = ChatPanel(self.bot)
        self.log_panel = LogPanel(self.bot)
        self.bot_docks: list[QDockWidget] = []
        self._bot_docks_sized = False
        self.bot_dock_titles: list[DockTitleBar] = []
        for (name, title), panel in zip(BOT_DOCKS, (self.chat_panel, self.log_panel), strict=True):
            dock = QDockWidget(title, self)
            dock.setObjectName(name)
            dock.setFeatures(
                QDockWidget.DockWidgetFeature.DockWidgetMovable
                | QDockWidget.DockWidgetFeature.DockWidgetFloatable
            )
            titlebar = DockTitleBar(dock)
            titlebar.close_button.hide()
            dock.setTitleBarWidget(titlebar)
            dock.setWidget(panel)
            self.bot_docks.append(dock)
            self.bot_dock_titles.append(titlebar)
        self.arrange_bot_docks()

    def arrange_bot_docks(self) -> None:
        """Chat rechts, Protokoll unten (wie Streamer.bot); ausserhalb des Moduls «Chat-Bot» ausgeblendet."""
        chat, log_dock = self.bot_docks
        for dock in self.bot_docks:
            dock.setFloating(False)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, chat)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, log_dock)
        visible = self._module == MODULE_BOT
        for dock in self.bot_docks:
            dock.setVisible(visible)
        if visible:
            self._size_bot_docks()

    def _size_bot_docks(self) -> None:
        self.resizeDocks([self.bot_docks[0]], [BOT_CHAT_WIDTH], Qt.Orientation.Horizontal)
        self.resizeDocks([self.bot_docks[1]], [DOCK_HEIGHT], Qt.Orientation.Vertical)

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
        self.undo_action = QAction("&Rückgängig", self, shortcut=QKeySequence("Ctrl+Z"))
        self.redo_action = QAction("&Wiederholen", self)
        self.redo_action.setShortcuts([QKeySequence("Ctrl+Y"), QKeySequence("Ctrl+Shift+Z")])
        self.undo_action.triggered.connect(self.model.undo)
        self.redo_action.triggered.connect(self.model.redo)
        for act in (self.undo_action, self.redo_action):
            act.setEnabled(False)
            edit_menu.addAction(act)
        self.model.history_changed.connect(self._sync_history_actions)

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

        view_menu.addSeparator()
        zoom_menu = view_menu.addMenu("&Zoom")
        self.zoom_actions: dict[object, QAction] = {}
        for value, label, key in ((geo.FIT, "Einpassen", "Ctrl+0"), (0.25, "25 %", ""), (0.5, "50 %", ""),
                                  (1.0, "100 %", "Alt+1"), (2.0, "200 %", ""), (4.0, "400 %", "")):  # fmt: skip
            act = QAction(label, self, shortcut=QKeySequence(key) if key else QKeySequence())
            act.triggered.connect(lambda _=False, v=value: self.editor.set_zoom(v))
            zoom_menu.addAction(act)
            self.zoom_actions[value] = act
        zoom_in = QAction("Vergrössern", self)
        zoom_in.setShortcuts([QKeySequence("Ctrl++"), QKeySequence("Ctrl+=")])
        zoom_out = QAction("Verkleinern", self, shortcut=QKeySequence("Ctrl+-"))
        zoom_in.triggered.connect(
            lambda: self.editor.set_zoom(geo.next_zoom(self.editor.zoom(), 1))
        )
        zoom_out.triggered.connect(
            lambda: self.editor.set_zoom(geo.next_zoom(self.editor.zoom(), -1))
        )
        zoom_menu.addSeparator()
        zoom_menu.addAction(zoom_in)
        zoom_menu.addAction(zoom_out)
        self.snap_action = QAction("&Einrasten", self, checkable=True)
        self.grid_action = QAction("&Raster anzeigen", self, checkable=True)
        self.snap_action.toggled.connect(self.prefs.set_snap)
        self.grid_action.toggled.connect(self.prefs.set_grid)
        view_menu.addAction(self.snap_action)
        view_menu.addAction(self.grid_action)
        self.prefs.changed.connect(self._sync_view_actions)
        self._sync_view_actions()

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
        # Zoom (F-65), links von der Anzeige des Kern-Dienstes. Die Zeigerlage steht seit F-75 nur noch links unten
        # in der Vorschaufläche (editor_view.PointerBadge).
        self.zoom_combo = QComboBox()
        self.zoom_combo.setObjectName("zoom_combo")
        self.zoom_combo.setAccessibleName("Zoom der Vorschau")
        self.zoom_combo.setFixedHeight(theme.STATUS_BAR_HEIGHT - 6)
        for value, label in (
            (geo.FIT, "Einpassen"),
            (0.25, "25 %"),
            (0.5, "50 %"),
            (1.0, "100 %"),
            (2.0, "200 %"),
            (4.0, "400 %"),
        ):
            self.zoom_combo.addItem(label, value)
        self.zoom_combo.activated.connect(
            lambda i: self.editor.set_zoom(self.zoom_combo.itemData(i))
        )
        self.core_status = QLabel()
        self.core_status.setObjectName("core_status")
        if diagnose.off(
            "editor_view_changes"
        ):  # DIAGNOSE (P06d3): Zeigerlage in der Statuszeile wie P08
            self.pointer_label = QLabel("X: –   Y: –")
            self.pointer_label.setObjectName("pointer_label")
            self.pointer_label.setAccessibleName("Pixelposition unter dem Zeiger")
            self.pointer_label.setMinimumWidth(
                QFontMetrics(self.font()).horizontalAdvance("X: 99999   Y: 99999") + 12
            )
            self.statusBar().addPermanentWidget(self.pointer_label)
            self.editor.pointer_changed.connect(
                lambda inside, x, y: self.pointer_label.setText(
                    f"X: {x}   Y: {y}" if inside else "X: –   Y: –"
                )
            )
        self.statusBar().addPermanentWidget(self.zoom_combo)
        self.statusBar().addPermanentWidget(self.core_status)
        self.statusBar().showMessage("Bereit")

    def _sync_history_actions(self) -> None:
        self.undo_action.setEnabled(self.model.can_undo())
        self.redo_action.setEnabled(self.model.can_redo())

    def _sync_view_actions(self, *_args) -> None:
        for act, value in (
            (self.snap_action, self.prefs.snap),
            (self.grid_action, self.prefs.grid),
        ):
            act.blockSignals(True)
            act.setChecked(value)
            act.blockSignals(False)

    def _show_zoom(self, zoom: float, fit: bool) -> None:
        index = 0 if fit else next((i for i in range(self.zoom_combo.count())
                                    if self.zoom_combo.itemData(i) != geo.FIT and abs(self.zoom_combo.itemData(i) - zoom) < 1e-9), -1)  # fmt: skip
        self.zoom_combo.blockSignals(True)
        self.zoom_combo.setCurrentIndex(index)
        if index < 0:
            self.zoom_combo.setCurrentText(geo.zoom_label(zoom))
        self.zoom_combo.blockSignals(False)
        self.zoom_combo.setToolTip(f"Zoom: {'Einpassen, ' if fit else ''}{geo.zoom_label(zoom)}")

    # --- Module --------------------------------------------------------
    def set_module(self, index: int) -> None:
        if index == self._module:
            return
        if self._module == MODULE_OVERLAYS:
            # FIX (P06d5): eine noch vorgemerkte Anordnung ist die des Moduls «Overlays», nicht die angezeigte
            self._overlay_dock_state = self._take_pending_state() or self.saveState(STATE_VERSION)
        self._module = index
        self.stack.setCurrentIndex(index)
        for i, act in enumerate(self.module_actions):
            act.setChecked(i == index)
        if self.tabbar.currentIndex() != index:
            self.tabbar.setCurrentIndex(index)
        in_overlays = index == MODULE_OVERLAYS
        # Die vier Docks gehören zum Modul «Overlays», «Chat» und «Protokoll» zum Modul «Chat-Bot».
        self.docks_menu.setEnabled(in_overlays)
        if in_overlays:
            for dock in self.bot_docks:
                dock.hide()
            if self._overlay_dock_state is not None:
                self.restoreState(self._overlay_dock_state, STATE_VERSION)
        else:
            for dock in self.docks:
                dock.hide()
            for dock in self.bot_docks:
                dock.show()
            if (
                not self._bot_docks_sized
            ):  # beim ersten Zeigen: Breite des Chats, Höhe wie die Docks unten
                self._bot_docks_sized = True
                self._size_bot_docks()

    @property
    def module(self) -> int:
        return self._module

    def reset_docks(self) -> None:
        if self._module == MODULE_OVERLAYS:
            self.arrange_docks()
        else:
            self._overlay_dock_state = self._default_state
            self.arrange_bot_docks()

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
        images = None if diagnose.off("qss_images") else indicators.image_paths(self.theme)
        sheet = theme.stylesheet(self.theme, images)
        target = app or self
        # Nur bei Änderung setzen (P06d, Vorschlag 2 aus P08): setStyleSheet gestaltet alle Widgets neu und war der
        # Ort des sporadischen Absturzes in P08. Dasselbe Design erneut zu wählen, ändert deshalb nichts.
        if target.styleSheet() != sheet or diagnose.off(
            "window_stylesheet"
        ):  # DIAGNOSE (P06d4): immer wie P08
            target.setStyleSheet(sheet)
        self.connections.apply_theme(self.theme)
        self.perf.apply_theme(self.theme)
        if self.isVisible() and not diagnose.off(
            "window_minwidth"
        ):  # DIAGNOSE (P06d4): sofort wie P08
            self._request_minimum_width()  # Designwechsel im Betrieb: nach dem Ereignis, zusammengefasst
        else:
            self._update_minimum_width()  # Aufbau: vor dem Anzeigen und vor der gespeicherten Fensterlage
        for bar in self.dock_titles + self.bot_dock_titles:
            bar.apply_theme(self.theme)
        for panel in self.panels:
            panel.apply_theme(self.theme)
        self.editor.apply_theme(self.theme)
        if hasattr(self, "_core_state"):
            self._set_core_status(*self._core_state)

    def _request_minimum_width(self) -> None:
        """`_update_minimum_width` nach dem laufenden Ereignis; mehrere Anfragen ergeben einen Aufruf (P06d2)."""
        if not self._min_width_timer.isActive():
            self._min_width_timer.start()

    def _update_minimum_width(self) -> None:
        """Mindestbreite: Reiter, Leistungsfelder und vier Verbindungsanzeigen passen nebeneinander (F-68).

        Setzt Grössen sofort; deshalb nur beim Aufbau, vor dem Anwenden der Fensterlage oder über
        `_request_minimum_width` rufen, nie aus einem Stil- oder Layout-Ereignis (P06d2). Die Leistungsfelder
        werden hier direkt angeglichen, damit ihre Breite nach dem Polieren (Schrift aus dem Stylesheet) zählt.
        """
        self.header.ensurePolished()
        self.perf.equalize()
        lay = self.header.layout()
        lay.invalidate()
        lay.activate()
        width = lay.minimumSize().width() + 2 * theme.HEADER_MARGIN
        if diagnose.off("min_width"):  # DIAGNOSE: Leistungsfelder mit ihrer Breite aus P08 gezählt
            p08 = sum(f.p08_width() for f in self.perf.fields.values())
            width -= sum(f.width() for f in self.perf.fields.values()) - p08
        width = max(width, 1)
        if self.minimumWidth() != width:
            self.setMinimumWidth(width)

    # --- Leistungsanzeige läuft nur bei sichtbarem, nicht minimiertem Fenster -------------------
    def _sync_perf(self) -> None:
        self.perf.set_active(self.isVisible() and not self.isMinimized())

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._sync_perf()
        # FIX (P06d5): Anordnung nach dem ersten Anzeigen fertigstellen
        if not self._restore_started:
            self._restore_started = True
            self._restore_deadline = time.monotonic() + RESTORE_MAX_MS / 1000
            self._restore_timer.start()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        # FIX (P06d5): Nur den Zeitgeber neu starten; Grösse und Layout ändern sich hier nicht (Regel 16).
        if self._restore_timer.isActive():
            self._resized_since_show = True
            self._restore_timer.start()

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
        self.core_status.setStyleSheet(
            f"color: {theme.palette(self.theme)[color]}; font-weight: bold;"
        )

    def _on_status_changed(self, name: str, status: str, detail: str = "") -> None:
        self.connections.set_status(name, status, detail)

    def _on_statuses_json(self, text: str) -> None:
        """Signal `statuses_loaded` (JSON-Text, Regel 12)."""
        self._on_statuses(json.loads(text or "{}"))

    def _on_statuses(self, statuses: dict) -> None:
        """Zustand aller Dienste beim Verbinden: name -> {"status", "detail"}."""
        for key in self.connections.indicators:
            info = statuses.get(key) or {}
            self.connections.set_status(key, info.get("status", "getrennt"), info.get("detail", ""))

    # --- Layout merken -------------------------------------------------
    def layout_values(self) -> dict[str, str]:
        # FIX (P06d5): eine noch vorgemerkte Anordnung zuerst
        current = self._pending_state or self.saveState(STATE_VERSION)
        state = self._overlay_dock_state if self._module == MODULE_BOT else current
        return {
            KEY_THEME: self.theme,
            KEY_GEOMETRY: _encode(self.saveGeometry()),
            KEY_STATE: _encode(state) if state is not None else _encode(self._default_state),
        }

    def _on_settings_json(self, text: str) -> None:
        """Signal `settings_loaded` (JSON-Text, Regel 12)."""
        self.apply_settings(json.loads(text or "{}"))

    def apply_settings(self, values: dict) -> None:
        """Stellt Theme, Fensterposition und Dock-Anordnung aus den gespeicherten Werten her."""
        self.prefs.load(values)
        self.model.load_guides(values)
        name = values.get(KEY_THEME)
        if name in theme.PALETTES:
            self.set_theme(name, save=False)
        geometry = _decode(values.get(KEY_GEOMETRY, ""))
        if geometry is not None and not geometry.isEmpty():
            self._restore_geometry(geometry)
        state = _decode(values.get(KEY_STATE, ""))
        if state is not None and not state.isEmpty():
            if self._module == MODULE_OVERLAYS:
                self._restore_state(state)
            else:
                self._overlay_dock_state = state
        self._settings_loaded = True
        if self._pending_state is None:  # FIX (P06d5): nichts mehr wiederherzustellen
            self._mark_layout_restored()

    def _restore_state(self, state: QByteArray) -> None:
        """Gespeicherte Dock-Anordnung im Modul «Overlays» anwenden (P06d5).

        Qt 6.8.2 (qmainwindowlayout.cpp, https://raw.githubusercontent.com/qt/qtbase/v6.8.2/src/widgets/widgets/
        qmainwindowlayout.cpp): `restoreState` am verborgenen, maximierten Fenster behält eine Anordnung, die noch
        nicht passt, als `restoredState` und übernimmt sie in späteren `setGeometry`-Aufrufen (Zeilen 3250–3258,
        2321–2343). Ein zweites `restoreState` löscht die Einträge des bisherigen Zustands
        (`savedState.deleteAllLayoutItems()`, Zeile 3261), setzt `restoredState`, das dieselben Einträge kopiert
        hat, aber nicht zurück; das nächste `setGeometry` übernimmt es wieder (Zeile 2329). Das ist Lesart C des
        Berichts P06d4, gelesen, nicht gemessen. Deshalb:

        - `fix_state_once`: dieselben Bytes nur einmal anwenden (kein zweites `restoreState` beim Verbinden).
        - `fix_restore_after_show`: bei maximierter Lage erst am sichtbaren Fenster mit Endgrösse anwenden; dort nimmt
          Qt den Zweig `fitLayout` / `applyState` (Zeilen 3244–3246) und legt kein `restoredState` an.
        """
        data = bytes(state)
        # FIX (P06d5): noch nicht angewendet: nur die Vormerkung ersetzen
        if self._pending_state is not None:
            self._pending_state = state
            self._applied_state = data
            return
        if diagnose.fix("fix_state_once") and data == self._applied_state:  # FIX (P06d5)
            return
        if (
            diagnose.fix("fix_restore_after_show")
            and not self.isVisible()
            and self.windowState() & _MAXIMIZED
        ):  # FIX (P06d5): erst nach show() mit Endgrösse (`_finish_restore`)
            self._pending_state = state
            self._applied_state = data
            return
        if self.restoreState(state, STATE_VERSION):
            self._applied_state = data
        else:
            log.warning("Gespeicherte Dock-Anordnung passt nicht und wird ignoriert")

    def _take_pending_state(self) -> QByteArray | None:
        state, self._pending_state = self._pending_state, None
        return state

    def _finish_restore(self) -> None:
        """Nach dem ersten Anzeigen, sobald RESTORE_SETTLE_MS lang keine Grössenänderung kam (Zeitgeber, Regel 16).

        Endgrösse bei maximierter Lage: Das Fenstersystem hat seit dem Anzeigen mindestens einmal eine Grösse gemeldet
        (danach RESTORE_SETTLE_MS Ruhe), oder der Rahmen füllt den verfügbaren Bereich schon, oder RESTORE_MAX_MS
        sind seit dem Anzeigen vergangen.

        Wendet eine vorgemerkte Dock-Anordnung an, setzt `layout_restored` und gibt die Seitenwechsel der Listen frei.
        Ohne Vormerkung und schon gesetztes `layout_restored` (nach `apply_settings`) geschieht nichts; wurde
        `apply_settings` nie gerufen (Kern beim Start nicht erreichbar), wird `layout_restored` hier gesetzt.
        """
        state = self._pending_state
        if (
            state is not None
            and self.windowState() & _MAXIMIZED
            and not (self._resized_since_show or self._has_final_size())
            and time.monotonic() < self._restore_deadline
        ):
            self._restore_timer.start()  # Fenstersystem noch nicht fertig: weiter warten
            return
        self._pending_state = None
        restore = state is not None and self._module == MODULE_OVERLAYS
        if restore and not self.restoreState(state, STATE_VERSION):
            log.warning("Gespeicherte Dock-Anordnung passt nicht und wird ignoriert")
        self._mark_layout_restored()

    def _mark_layout_restored(self) -> None:
        """Fensterlage und Dock-Anordnung sind hergestellt (oder es gibt nichts herzustellen): `layout_restored`.

        Die Listen wechseln ihre Seite danach über einen Zeitgeber, also nach dem Layout dieser Anordnung und
        ausserhalb eines Ereignisses (Regel 16).
        """
        if self.layout_restored:
            return
        self.layout_restored = True
        QTimer.singleShot(0, self._release_lists)

    def _has_final_size(self) -> bool:
        """Maximiert oder Vollbild: Rahmen mindestens so gross wie der verfügbare Bereich des Bildschirms (±2 px)."""
        screen = self.screen()
        if screen is None:
            return True
        full = self.windowState() & Qt.WindowState.WindowFullScreen
        area = screen.geometry() if full else screen.availableGeometry()
        frame = self.frameGeometry()
        return frame.width() >= area.width() - 2 and frame.height() >= area.height() - 2

    def _release_lists(self) -> None:
        for panel in (self.overlays_panel, self.sources_panel):
            panel.stack.release()

    def _restore_geometry(self, geometry: QByteArray) -> None:
        """Gespeicherte Fensterlage anwenden (P06d2).

        - Dieselbe Lage nur einmal: Beim Start kommt sie zweimal (vor dem Anzeigen und nach dem Verbinden über
          `settings_loaded`); das zweite Mal würde das schon sichtbare Fenster ohne Grund neu setzen.
        - Erst die Mindestbreite, dann die Lage. Ist die gespeicherte Lage schmaler als die Mindestbreite (z. B. aus
          P08, vor den gleich breiten Leistungsfeldern), wird die Breite einmal auf die Mindestbreite gesetzt.
        """
        if diagnose.off(
            "window_geometry"
        ):  # DIAGNOSE (P06d4): wie P08 direkt, auch am sichtbaren Fenster
            self.restoreGeometry(geometry)
            return
        data = bytes(geometry)
        if data == self._applied_geometry:
            return
        self._applied_geometry = data
        self._min_width_timer.stop()
        self._update_minimum_width()
        self.restoreGeometry(geometry)
        if self.width() < self.minimumWidth():
            self.resize(self.minimumWidth(), self.height())

    def save_layout_now(self) -> bool:
        """Speichert Theme, Fensterlage und Dock-Anordnung sofort (beim Schliessen und bei SIGTERM/SIGINT)."""
        if not self._settings_loaded:
            return False
        ok = self._core.save_settings_blocking(self.layout_values())
        self.model.wait_idle()  # noch ausstehende Änderungen an Quellen erreichen den Kern
        return bool(ok)

    def closeEvent(self, event) -> None:
        self.save_layout_now()
        if hasattr(self.runner, "stop"):
            self.runner.stop()
        super().closeEvent(event)
