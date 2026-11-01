"""F-01, F-02, F-04, F-06: Hauptfenster (offscreen, ohne Kern-Dienst)."""

import json

import pytest

pytest.importorskip(
    "PyQt6.QtWidgets",
    exc_type=ImportError,
    reason="PyQt6 ist nicht installierbar oder lädt nicht (Systembibliotheken fehlen?)",
)

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDockWidget, QLabel, QTabWidget

from donstv_studio.ui import theme
from donstv_studio.ui.main_window import KEY_THEME, MainWindow
from fake_core import FakeCore
from helpers import dispose


@pytest.fixture
def make(app):
    windows = []

    def factory(core=None):
        core = core or FakeCore()
        w = MainWindow(core)
        w.show()
        app.processEvents()
        windows.append(w)
        return w, core

    yield factory
    dispose(app, *windows)


def test_f01_window_structure(make):
    w, _ = make()
    assert w.windowTitle() == "donstv_Studio"
    assert not w.windowIcon().isNull()  # Platzhalter-Icon aus assets/icon.svg
    assert [a.text().replace("&", "") for a in w.menu_bar.actions()] == [
        "Datei", "Bearbeiten", "Ansicht", "Docks", "Werkzeuge", "Hilfe",
    ]  # fmt: skip
    titles = [d.windowTitle() for d in w.findChildren(QDockWidget)]
    # vier Docks des Moduls «Overlays», dazu «Chat» und «Protokoll» des Moduls «Chat-Bot» (P07, nur dort sichtbar)
    assert sorted(titles) == [
        "Chat",
        "Eigenschaften",
        "Overlays",
        "Protokoll",
        "Quellen",
        "Steuerung",
    ]
    assert all(d.isHidden() for d in w.bot_docks)
    assert w.statusBar() is not None and w.preview.isVisible()
    assert w.menuWidget().isAncestorOf(w.menu_bar)
    assert w.centralWidget() is not None


def test_f01_docks_are_real_dockwidgets_movable_floatable_closable(make, app):
    w, _ = make()
    assert len(w.docks) == 4
    for dock in w.docks:
        f = dock.features()
        assert f & QDockWidget.DockWidgetFeature.DockWidgetMovable
        assert f & QDockWidget.DockWidgetFeature.DockWidgetFloatable
        assert f & QDockWidget.DockWidgetFeature.DockWidgetClosable
        assert dock.objectName()  # nötig für das Speichern der Anordnung
        assert w.dockWidgetArea(dock) == Qt.DockWidgetArea.BottomDockWidgetArea
    d = w.docks[0]
    d.setFloating(True)
    assert d.isFloating()
    d.setFloating(False)
    d.hide()
    assert not d.isVisible()
    d.toggleViewAction().trigger()  # Menü «Docks» blendet ein
    assert d.isVisible()
    w.docks[1].resize(500, 200)  # Grösse veränderbar
    assert w.docks[1].width() >= 100


def test_f02_module_switch(make, app):
    w, _ = make()
    assert w.module == 0 and w.stack.currentIndex() == 0
    assert w.tabbar.count() == 2
    assert [w.tabbar.tabText(i) for i in range(2)] == ["Overlays", "Chat-Bot"]
    w.tabbar.setCurrentIndex(1)
    assert w.module == 1 and w.stack.currentWidget() is w.bot_tabs
    assert [w.bot_tabs.tabText(i) for i in range(5)] == [
        "Actions",
        "Commands",
        "Timer",
        "Queues",
        "Einstellungen",
    ]
    assert isinstance(w.bot_tabs, QTabWidget)
    assert not any(d.isVisible() for d in w.docks)  # Docks gehören zu «Overlays»
    assert not w.docks_menu.isEnabled()
    w.module_actions[0].trigger()  # Menü «Ansicht»
    assert w.module == 0 and w.tabbar.currentIndex() == 0
    assert all(d.isVisible() for d in w.docks)
    assert w.docks_menu.isEnabled()


def test_f04_status_never_only_by_color(make):
    w, _ = make()
    seen = {}
    for status in ("verbunden", "verbindet", "getrennt", "Fehler", "unbekannt"):
        w.connections.set_status("twitch", status)
        text = w.connections.text_of("twitch")
        assert status in text and "Twitch" in text  # Text
        symbol = text.split()[0]
        assert symbol and not symbol.isalnum()  # Symbol
        seen[status] = symbol
    assert len(set(seen.values())) == 5  # jeder Zustand hat ein eigenes Symbol
    for key in ("twitch", "youtube", "obs", "ndi"):  # alle vier immer sichtbar
        assert w.connections.indicators[key].isVisible()


def test_f04_status_events_update_labels(make, app):
    w, core = make()
    core.connected.emit()
    core.statuses_loaded.emit(
        json.dumps({"twitch": {"status": "verbunden", "detail": ""}})
    )  # übrige: im Kern unbekannt
    assert "verbunden" in w.connections.text_of("twitch")
    for key in ("youtube", "obs", "ndi"):
        assert "getrennt" in w.connections.text_of(key)
    core.status_changed.emit("obs", "Fehler", "")
    assert w.connections.status_of("obs") == "Fehler" and "Fehler" in w.connections.text_of("obs")
    core.status_changed.emit("unbekannter_dienst", "verbunden", "")  # wird ignoriert, kein Absturz


def test_core_unreachable_shows_message_without_crash(make, app):
    w, core = make()
    core.unreachable.emit("Der Kern-Dienst ist nicht erreichbar", 3.0)
    assert w.banner.isVisible()
    text = w.banner_label.text()
    assert "nicht erreichbar" in text and "donstv-core" in text and "3 s" in text
    assert "nicht erreichbar" in w.core_status.text()
    assert all(
        w.connections.status_of(k) == "unbekannt" for k in ("twitch", "youtube", "obs", "ndi")
    )
    # Wiederholversuch zählt herunter, dann wieder erreichbar
    w._tick()
    assert "2 s" in w.banner_label.text()
    core.unreachable.emit("Der Kern-Dienst antwortet nicht", 6.0)
    assert "6 s" in w.banner_label.text()
    core.connected.emit()
    assert not w.banner.isVisible() and "verbunden" in w.core_status.text()
    # Fenster bleibt bedienbar
    w.set_module(1)
    w.set_module(0)


def test_f06_theme_switch_dark_default_and_light(make, app):
    w, core = make()
    core.settings_loaded.emit(json.dumps({}))  # Kern erreichbar, nichts gespeichert
    assert w.theme == theme.DARK
    assert theme.palette("dark")["bg"] in app.styleSheet()
    w.open_settings()
    d = w.settings_dialog
    assert d.windowTitle() == "Einstellungen"
    assert d.radios["dark"].isChecked() and [r.text() for r in d.radios.values()] == [
        "Dunkel",
        "Hell",
    ]
    d.radios["light"].setChecked(True)  # Auswahl im Dialog
    assert w.theme == theme.LIGHT
    assert theme.palette("light")["bg"] in app.styleSheet()
    assert theme.palette("dark")["bg"] not in app.styleSheet()
    assert core.store[KEY_THEME] == "light"  # gespeichert
    assert w.connections.text_of("twitch")  # Statusfarben folgen dem Theme
    assert w.connections.indicators["twitch"]._palette == theme.palette("light")
    d.radios["dark"].setChecked(True)
    assert core.store[KEY_THEME] == "dark" and w.theme == "dark"
    d.accept()


def test_f06_invalid_theme_ignored(make):
    w, _ = make()
    w.set_theme("pink")
    w.apply_settings({KEY_THEME: "pink"})
    assert w.theme == theme.DARK


def test_layout_saved_and_restored(make, app):
    w, core = make()
    core.settings_loaded.emit(json.dumps({}))
    w.move(37, 53)
    size = (w.minimumWidth() + 40, 480)  # Mindestbreite des Fensterkopfes (F-68) beachten
    w.resize(*size)
    w.docks[1].hide()
    w.docks[2].setFloating(True)
    w.docks[2].move(200, 150)
    w.set_theme("light")
    app.processEvents()
    values = w.layout_values()
    assert set(values) == {"ui.theme", "ui.geometry", "ui.dock_state"}
    assert values["ui.theme"] == "light"
    w.close()  # speichert über die Schnittstelle des Kerns
    saved = dict(core.store)
    assert set(saved) == {"ui.theme", "ui.geometry", "ui.dock_state"}
    assert saved["ui.dock_state"]
    assert saved["ui.theme"] == "light"

    w2, core2 = make()
    assert w2.theme == "dark" and not w2.docks[1].isHidden()  # vor dem Laden: Standard
    core2.settings_loaded.emit(json.dumps(saved))  # wie nach dem Verbinden
    app.processEvents()
    assert w2.theme == "light"
    assert w2.docks[1].isHidden()
    assert w2.docks[2].isFloating()
    assert not w2.docks[0].isFloating() and not w2.docks[0].isHidden()
    # Die Breite ist durch die Mindestbreite und den Offscreen-Bildschirm (800×600) begrenzt, die Höhe nicht.
    assert w2.height() == size[1] and w2.minimumWidth() <= w2.width() <= size[0]


def test_layout_not_saved_before_settings_were_loaded(make):
    w, core = make()  # Kern nie erreicht: gespeicherte Werte dürfen nicht überschrieben werden
    w.close()
    assert core.store == {}


def test_layout_saved_while_in_chatbot_module_keeps_overlay_docks(make, app):
    w, core = make()
    core.settings_loaded.emit(json.dumps({}))
    w.docks[3].hide()
    w.set_module(1)  # Docks werden dabei ausgeblendet
    vals = w.layout_values()
    w2, core2 = make()
    core2.settings_loaded.emit(json.dumps(vals))
    assert (
        w2.docks[3].isHidden() and not w2.docks[0].isHidden()
    )  # nicht alle als «versteckt» gespeichert


def test_invalid_saved_values_do_not_crash(make):
    w, core = make()
    core.settings_loaded.emit(
        json.dumps({"ui.theme": "dark", "ui.geometry": "###", "ui.dock_state": "AAAA"})
    )
    core.settings_loaded.emit(json.dumps({"ui.geometry": "", "ui.dock_state": "!"}))
    assert w.theme == "dark"
    assert all(not d.isHidden() for d in w.docks)


def test_reset_docks_restores_default(make, app):
    w, _ = make()
    for d in w.docks:
        d.hide()
    w.reset_docks_action.trigger()
    assert all(not d.isHidden() for d in w.docks)


def test_texts_use_swiss_spelling(make):
    w, _ = make()
    texts = [a.text() for m in w.menu_bar.findChildren(type(w.docks_menu)) for a in m.actions()]
    texts += [lbl.text() for lbl in w.findChildren(QLabel)]
    assert not any("ß" in t for t in texts)


def test_f01_layout_values_without_version_tag_are_not_restored(make, app):
    """Zustände aus früheren Versionen (ohne Marke) werden nicht wiederhergestellt: Auf dem Laptop (Qt 6.8.2 mit PyQt6 6.9.0)
    stürzte `restoreState` mit einer alten Anordnung ab, sobald der Kern verbunden war."""
    import base64

    a, _ = make()
    a.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, a.docks[0])
    app.processEvents()
    old = {
        "ui.geometry": base64.b64encode(bytes(a.saveGeometry())).decode(),
        "ui.dock_state": base64.b64encode(
            bytes(a.saveState(2))
        ).decode(),  # Format von vor der Marke
    }
    b, _ = make()
    before = bytes(b.saveState(2))
    b.apply_settings(old)
    assert bytes(b.saveState(2)) == before  # nichts wiederhergestellt
    saved = a.layout_values()
    assert saved["ui.dock_state"].startswith("v3:") and saved["ui.geometry"].startswith("v3:")
    c, _ = make()
    c.apply_settings(saved)  # mit Marke: wiederhergestellt
    assert c.dockWidgetArea(c.docks[0]) == Qt.DockWidgetArea.LeftDockWidgetArea
