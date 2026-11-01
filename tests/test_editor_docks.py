"""F-12, F-13, F-14, F-65, F-66: Docks «Overlays», «Quellen», «Eigenschaften», «Steuerung» im Hauptfenster (offscreen)."""

import json
import logging

import pytest

pytest.importorskip("PyQt6.QtWidgets", exc_type=ImportError, reason="PyQt6 ist nicht installierbar oder lädt nicht")

from PyQt6.QtCore import QPoint, QPointF, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QCheckBox, QLabel, QPushButton, QToolButton

from donstv_studio.ui import geometry as geo
from donstv_studio.ui import theme
from donstv_studio.ui.backend import DirectRunner
from donstv_studio.ui.main_window import MainWindow
from fake_backend import FakeBackend
from fake_core import FakeCore
from helpers import dispose, solid_png


@pytest.fixture
def env(app):
    core = FakeCore()
    core.backend = FakeBackend()
    core.runner = DirectRunner()
    core.backend.add("Hauptbild", 800, 400)
    w = MainWindow(core)
    w.resize(1400, 900)
    w.show()
    app.processEvents()
    core.connected.emit()  # Verbindung steht: Overlays laden
    core.settings_loaded.emit(json.dumps({}))
    app.processEvents()
    yield w, core
    dispose(app, w)


def texts(listing):
    return [listing.item(i).text() for i in range(listing.count())]


def add_text(w, text="Hallo"):
    w.sources_panel.ask_text = lambda *a, **k: text
    w.sources_panel.text_action.trigger()
    return w.model.selected_id


# --- Overlays --------------------------------------------------------------------------------------
def test_f10_overlays_dock_lists_and_selects(env):
    w, core = env
    p = w.overlays_panel
    assert texts(p.list) == ["Hauptbild"] and p.list.currentRow() == 0
    assert w.editor.isVisible() and not w.preview.canvas.isVisible()  # mit Overlay: Editor statt leerer Leinwand
    core.backend.add("Zweites")
    w.model.load()
    assert texts(p.list) == ["Hauptbild", "Zweites"]
    p.list.setCurrentRow(1)
    assert w.model.current()["name"] == "Zweites"


def test_f10_create_rename_duplicate_delete_via_buttons(env):
    w, core = env
    p = w.overlays_panel
    p.ask_text = lambda *a, **k: "Neu"
    p.add_button.click()
    assert texts(p.list) == ["Hauptbild", "Neu"] and w.model.current()["name"] == "Neu"
    item = p.list.item(1)
    item.setText("Umbenannt")  # wie nach dem Bearbeiten in der Liste
    assert core.backend.overlays[1]["name"] == "Umbenannt"
    item.setText("   ")  # leer: alter Name bleibt
    assert p.list.item(1).text() == "Umbenannt"
    p.duplicate_button.click()
    assert texts(p.list)[-1] == "Umbenannt (Kopie)"
    answers = iter([False, True])
    p.confirm = lambda *a, **k: next(answers)
    p.delete_button.click()  # abgelehnt
    assert len(core.backend.overlays) == 3
    p.delete_button.click()
    assert len(core.backend.overlays) == 2 and texts(p.list) == ["Hauptbild", "Umbenannt"]


def test_f10_empty_state_shows_hint_and_placeholder_canvas(env):
    w, core = env
    p = w.overlays_panel
    p.confirm = lambda *a, **k: True
    p.delete_button.click()
    assert core.backend.overlays == []
    assert p.stack.currentWidget() is p.stack.hint and "Noch kein Overlay" in p.stack.hint.text()
    assert w.preview.canvas.isVisible() and not w.editor.isVisible()
    assert not p.delete_button.isEnabled() and not p.duplicate_button.isEnabled() and p.add_button.isEnabled()
    assert not w.sources_panel.add_button.isEnabled()


# --- Quellen ---------------------------------------------------------------------------------------
def test_f12_sources_dock_add_remove_visibility_order(env):
    w, core = env
    p = w.sources_panel
    assert p.stack.currentWidget() is p.stack.hint
    a, b = add_text(w, "Eins"), add_text(w, "Zwei")
    assert texts(p.list) == ["Text: Zwei", "Text: Eins"]  # vorn oben, wie bei OBS
    assert p.list.currentRow() == 0 and w.model.selected_id == b
    # Klick auf das Auge schaltet die Sichtbarkeit
    p.list.visibility_clicked.emit(a)
    assert w.model.source(a)["visible"] is False and core.backend.source(w.model.current_id, a)["visible"] is False
    p.list.visibility_clicked.emit(a)
    assert w.model.source(a)["visible"] is True
    # Pfeile ändern die Reihenfolge
    p.list.setCurrentRow(1)  # «Eins» (hinten)
    assert p.up_button.isEnabled() and not p.down_button.isEnabled()
    p.up_button.click()
    assert texts(p.list) == ["Text: Eins", "Text: Zwei"]
    assert [s["id"] for s in core.backend.overlays[0]["sources"]] == [b, a]
    p.down_button.click()
    assert texts(p.list) == ["Text: Zwei", "Text: Eins"]
    # Entfernen mit Rückfrage
    p.confirm = lambda *a, **k: False
    p.delete_button.click()
    assert len(w.model.sources()) == 2
    p.confirm = lambda *a, **k: True
    p.delete_button.click()
    assert len(w.model.sources()) == 1 and len(core.backend.overlays[0]["sources"]) == 1


def test_f12_drag_and_drop_reorders_sources(env, app):
    w, core = env
    p = w.sources_panel
    a, b, c = add_text(w, "A"), add_text(w, "B"), add_text(w, "C")
    assert texts(p.list) == ["Text: C", "Text: B", "Text: A"]
    item = p.list.takeItem(0)  # «C» ganz nach unten ziehen: wie nach dem Ablegen
    p.list.insertItem(2, item)
    p.list.reordered.emit()
    QTest.qWait(30)
    assert texts(p.list) == ["Text: B", "Text: A", "Text: C"]  # von oben (vorn) nach unten (hinten)
    assert [s["id"] for s in w.model.sources()] == [c, a, b]  # im Kern: unterste Quelle zuerst
    assert [s["id"] for s in core.backend.overlays[0]["sources"]] == [c, a, b]


def test_f16_add_image_source_uploads_file(env, tmp_path):
    w, core = env
    p = w.sources_panel
    png = tmp_path / "logo.png"
    png.write_bytes(solid_png(120, 60, (255, 0, 0, 255)))
    p.pick_image = lambda: str(png)
    p.image_action.trigger()
    s = w.model.selected()
    assert s["kind"] == "image" and (s["width"], s["height"]) == (120, 60)
    assert texts(p.list)[0] == "Bild: logo.png"
    p.pick_image = lambda: ""  # Abbruch im Dialog: nichts passiert
    p.image_action.trigger()
    assert len(w.model.sources()) == 1


# --- Eigenschaften ---------------------------------------------------------------------------------
def test_f14_properties_fields_show_and_set_values_immediately(env):
    w, core = env
    p = w.properties_panel
    assert not p.fields["x"].isEnabled() and p.hint.isVisibleTo(p.body)  # ohne Auswahl
    sid = add_text(w)
    s = w.model.source(sid)
    assert p.fields["x"].value() == s["x"] and p.fields["w"].value() == 600 and p.fields["rot"].value() == 0.0
    p.fields["x"].setValue(77)  # Eingabe wirkt sofort
    assert w.model.source(sid)["x"] == 77 and core.backend.source(w.model.current_id, sid)["x"] == 77
    p.fields["y"].setValue(-20)  # auch teilweise ausserhalb
    p.fields["w"].setValue(333)
    p.fields["h"].setValue(44)
    p.fields["rot"].setValue(12.5)
    s = w.model.source(sid)
    assert (s["x"], s["y"], s["width"], s["height"], s["rotation"]) == (77, -20, 333, 44, 12.5)
    assert all(isinstance(s[k], int) for k in ("x", "y", "width", "height"))
    assert p.fields["w"].minimum() == 1 and p.fields["h"].minimum() == 1  # keine Quelle ohne Fläche
    w.model.undo()  # Zahlenfelder: ein Schritt je Feld
    assert w.model.source(sid)["rotation"] == 0.0


def test_f14_field_follows_drag_in_preview(env):
    w, core = env
    sid = add_text(w)
    w.model.set_box(sid, geo.Box(200, 100, 100, 50))
    assert w.properties_panel.fields["x"].value() == 200
    w.model.select_source(None)
    assert not w.properties_panel.fields["x"].isEnabled()


def test_f65_align_buttons_align_to_overlay(env):
    w, core = env
    p = w.properties_panel
    sid = add_text(w)
    w.model.set_box(sid, geo.Box(333, 111, 200, 100))  # Overlay 800 × 400
    expect = {"left": (0, 111), "center": (300, 111), "right": (600, 111), "top": (600, 0), "middle": (600, 150), "bottom": (600, 300)}
    for how in geo.ALIGNMENTS:
        p.align_buttons[how].click()
        s = w.model.source(sid)
        assert (s["x"], s["y"]) == expect[how], how
    assert [b.accessibleName() for b in p.align_buttons.values()] == [geo.ALIGN_LABELS[h] for h in geo.ALIGNMENTS]
    w.model.undo()
    assert w.model.source(sid)["y"] == 150


# --- Steuerung -------------------------------------------------------------------------------------
def test_f17_control_dock_shows_url_and_copies(env):
    w, core = env
    c = w.control_panel
    o = core.backend.overlays[0]
    assert c.url.text() == w.model.preview_url() and c.url.text().endswith(f"/o/{o['id']}?t={o['token']}")
    c.copy_button.click()
    assert QApplication.clipboard().text() == c.url.text()
    assert "kopiert" in w.statusBar().currentMessage()


def test_f66_control_dock_output_choice(env):
    w, core = env
    c = w.control_panel
    assert c.output.currentData() == "browser" and "verfügbar" in c.output_status.text() and "nicht" not in c.output_status.text()
    c.output.setCurrentIndex(c.output.findData("ndi"))
    assert core.backend.overlays[0]["output"] == "ndi"
    assert "nicht verfügbar" in c.output_status.text()  # NDI: im Gerüst noch nicht verfügbar (P03)
    c.output.setCurrentIndex(c.output.findData("browser"))
    assert core.backend.overlays[0]["output"] == "browser"


def test_f13_control_dock_preview_and_editor_settings_are_saved(env):
    w, core = env
    c = w.control_panel
    assert c.fps.value() == 30 and not c.shrink.isChecked() and c.snap.isChecked() and not c.grid_check.isChecked()  # Standard 30
    c.fps.setValue(15)
    c.shrink.setChecked(True)
    c.snap.setChecked(False)
    c.grid_check.setChecked(True)
    c.grid_size.setValue(25)
    assert core.store["ui.editor.preview_fps"] == "15" and core.store["ui.editor.preview_shrink"] == "1"
    assert core.store["ui.editor.snap"] == "0" and core.store["ui.editor.grid"] == "1" and core.store["ui.editor.grid_size"] == "25"
    assert w.prefs.fps == 15 and w.prefs.shrink and not w.prefs.snap and w.prefs.grid and w.prefs.grid_size == 25
    assert w.snap_action.isChecked() is False and w.grid_action.isChecked() is True  # Menü bleibt gleich
    w.snap_action.trigger()
    assert w.prefs.snap and c.snap.isChecked()
    c.clear_guides.click()
    w.model.set_guides([5], [6])
    assert c.clear_guides.isEnabled()
    c.clear_guides.click()
    assert w.model.guides() == ([], [])


def test_f13_editor_settings_restored_from_core(env):
    w, core = env
    core.settings_loaded.emit(json.dumps({"ui.editor.preview_fps": "20", "ui.editor.grid": "1", "ui.editor.grid_size": "40",
                               "ui.editor.zoom": "2.0", f"ui.guides.{w.model.current_id}": '{"v": [10], "h": [20]}'}))  # fmt: skip
    assert w.control_panel.fps.value() == 20 and w.control_panel.grid_check.isChecked()
    assert w.editor.zoom() == 2.0 and w.zoom_combo.currentText() == "200 %"
    assert w.model.guides() == ([10], [20])


# --- Rückgängig, Statuszeile, Menü -------------------------------------------------------------------
def test_f13_edit_menu_undo_redo(env, app):
    w, core = env
    assert not w.undo_action.isEnabled() and not w.redo_action.isEnabled()
    sid = add_text(w)
    w.model.change_box(sid, geo.Box(10, 10, 100, 50))
    assert w.undo_action.isEnabled()
    assert w.undo_action.shortcut().toString() == "Ctrl+Z"
    assert [s.toString() for s in w.redo_action.shortcuts()] == ["Ctrl+Y", "Ctrl+Shift+Z"]
    w.undo_action.trigger()
    assert w.model.source(sid)["x"] != 10 and w.redo_action.isEnabled()
    w.redo_action.trigger()
    assert w.model.source(sid)["x"] == 10 and not w.redo_action.isEnabled()


def test_f65_statusbar_shows_pixel_under_pointer_and_zoom(env, app):
    w, core = env
    assert w.pointer_label.text() == "X: –   Y: –"
    w.editor.set_zoom(1.0)
    app.processEvents()
    from PyQt6.QtCore import QEvent
    from PyQt6.QtGui import QMouseEvent

    t = w.editor.transform()
    pos = QPointF(*t.to_view(321.5, 123.5))
    QApplication.sendEvent(w.editor.layer, QMouseEvent(QEvent.Type.MouseMove, pos, w.editor.layer.mapToGlobal(pos),
                                                       Qt.MouseButton.NoButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier))  # fmt: skip
    assert w.pointer_label.text() == "X: 321   Y: 123"
    assert w.zoom_combo.currentText() == "100 %"
    w.zoom_combo.setCurrentIndex(w.zoom_combo.findText("400 %"))
    w.zoom_combo.activated.emit(w.zoom_combo.currentIndex())
    assert w.editor.zoom() == 4.0
    w.zoom_actions[geo.FIT].trigger()
    assert w.editor.fit_mode and w.zoom_combo.currentText() == "Einpassen"
    assert w.zoom_combo.height() <= theme.STATUS_BAR_HEIGHT


# --- Schaltflächenleisten, Stil -----------------------------------------------------------------------
def test_dock_button_bars_have_monochrome_icons_in_text_color(env, app):
    w, core = env
    expected = {
        "dock_overlays": ["plus", "trash", "duplicate"],
        "dock_sources": ["plus", "trash", "up", "down"],
        "dock_properties": [f"align_{h}" for h in geo.ALIGNMENTS],
    }
    for dock in w.docks:
        panel = w.panels[w.docks.index(dock)]
        if dock.objectName() in expected:
            assert [b.kind for b in panel.bar.buttons] == expected[dock.objectName()]
            for b in panel.bar.buttons:
                assert b.toolTip() and b.accessibleName() and not b.icon().isNull()
                assert b.width() == 26 and b.height() == 26  # OBS-Bild: 26
    for name in (theme.DARK, theme.LIGHT):
        w.set_theme(name)
        color = theme.palette(name)["text"].lower()
        img = w.overlays_panel.bar.buttons[0].icon().pixmap(32, 32).toImage()  # Originalgrösse (Faktor 2)
        colors = {img.pixelColor(x, y).name() for x in range(img.width()) for y in range(img.height()) if img.pixelColor(x, y).alpha() > 250}
        assert colors == {color}, f"Symbol nur in der Textfarbe des Themes {name}"
    assert not w.overlays_panel.bar.buttons[0].icon().pixmap(16, 16, mode=w.overlays_panel.bar.buttons[0].icon().Mode.Disabled).isNull()


def test_dock_bars_sit_at_the_bottom_of_each_dock(env, app):
    w, core = env
    for panel in (w.overlays_panel, w.sources_panel, w.properties_panel):
        bar = panel.bar
        body = panel.body
        assert bar.mapTo(body, QPoint(0, bar.height())).y() >= body.height() - 2
        assert bar.height() <= 34 and bar.width() == body.width() - 2  # abzüglich des 1-Pixel-Rahmens


def test_all_dock_texts_use_swiss_spelling(env):
    w, core = env
    for widget in w.findChildren((QLabel, QPushButton, QToolButton, QCheckBox)):
        for t in (getattr(widget, "text", lambda: "")(), widget.toolTip(), widget.accessibleName()):
            assert "ß" not in t, t
    for act in w.findChildren(__import__("PyQt6.QtGui", fromlist=["QAction"]).QAction):
        assert "ß" not in act.text()


# --- Fester Fensterkopf (P05b/P05c) ------------------------------------------------------------------
def header_geometry(w):
    parts = [w.header, w.tabbar, w.connections, w.perf, *w.connections.indicators.values(), *w.perf.fields.values()]
    return [(p.mapTo(w, QPoint(0, 0)).x(), p.mapTo(w, QPoint(0, 0)).y(), p.width(), p.height()) for p in parts]


def test_f04_header_does_not_move_with_new_docks_and_content(env, app):
    w, core = env
    before = header_geometry(w)
    sid = add_text(w, "Ein ziemlich langer Text, der in der Quellenliste sehr viel Platz brauchen würde und umbrechen könnte")
    w.model.set_box(sid, geo.Box(-50, 20, 5000, 40))
    w.editor.set_zoom(4.0)  # Rollbalken erscheinen
    w.editor.set_zoom(0.25)
    core.backend.add("Overlay mit einem sehr langen Namen " * 3)
    w.model.load()
    w.statusBar().showMessage("Eine lange Statusmeldung " * 5)
    app.processEvents()
    assert header_geometry(w) == before
    for width, height in ((1100, 700), (1920, 1080), (1400, 900)):
        w.resize(width, height)
        app.processEvents()
        g = header_geometry(w)
        assert g[0][1] == before[0][1] and g[0][3] == before[0][3] == theme.HEADER_HEIGHT  # gleiche Lage und Höhe
    w.resize(1400, 900)
    w.tabbar.setCurrentIndex(1)  # Modulwechsel (Chat-Bot) und zurück
    w.tabbar.setCurrentIndex(0)
    app.processEvents()
    assert header_geometry(w) == before


def test_f04_preview_does_not_cover_the_header(env, app):
    w, core = env
    top = w.preview.mapTo(w, QPoint(0, 0)).y()
    header_bottom = w.header.mapTo(w, QPoint(0, 0)).y() + w.header.height()
    assert top >= header_bottom
    assert w.editor.geometry().top() == 0 and w.editor.parentWidget() is w.preview


def test_f13_window_without_core_access_has_working_empty_docks(app):
    core = FakeCore()  # kein Backend: wie vor dem Start des Kern-Dienstes
    w = MainWindow(core)
    w.show()
    app.processEvents()
    assert not w.overlays_panel.add_button.isEnabled()
    assert w.preview.canvas.isVisible() and not w.editor.isVisible()
    w.close()


def test_token_never_appears_in_ui_log(env, caplog):
    w, core = env
    token = core.backend.overlays[0]["token"]
    caplog.set_level(logging.DEBUG)
    w.model.load()
    sid = add_text(w)
    w.model.set_box(sid, geo.Box(1, 2, 30, 40))
    w.control_panel.copy_button.click()
    w.model.undo()
    assert all(token not in r.getMessage() for r in caplog.records)
