"""F-01, F-02, F-04: fester Fensterkopf, YouTube, Dienst-Symbole, Standardanordnung, OBS-Stil."""

import pytest

pytest.importorskip(
    "PyQt6.QtWidgets",
    exc_type=ImportError,
    reason="PyQt6 ist nicht installierbar oder lädt nicht (Systembibliotheken fehlen?)",
)

from PyQt6.QtCore import QObject, QPoint, Qt, pyqtSignal
from PyQt6.QtWidgets import QApplication, QDockWidget, QListWidget, QMessageBox

from donstv_studio.ui import theme, widgets
from donstv_studio.ui.main_window import STATE_VERSION, MainWindow
from donstv_studio.ui.widgets import SERVICES, STATUS_STYLE, ConnectionStatusBar

STATES = tuple(STATUS_STYLE)
SERVICE_KEYS = [k for k, _ in SERVICES]


class FakeCore(QObject):
    connected = pyqtSignal()
    unreachable = pyqtSignal(str, float)
    status_changed = pyqtSignal(str, str, str)
    statuses_loaded = pyqtSignal(dict)
    settings_loaded = pyqtSignal(dict)

    def save_setting(self, key, value):
        pass

    def save_settings_blocking(self, values, timeout=2.0):
        return True


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def make(app):
    windows = []

    def factory(width=1280, height=800, core=None):
        w = MainWindow(core or FakeCore())
        w.resize(width, height)
        w.show()
        app.processEvents()
        windows.append(w)
        return w

    yield factory
    for w in windows:
        w.close()
        w.deleteLater()
    app.processEvents()


def header_geometry(w):
    """Lage und Grösse der Reiter und jeder Verbindungsanzeige in Fensterkoordinaten.

    Rechtsbündige Teile werden vom rechten Fensterrand aus gemessen: Ändert sich die Breite des
    Fensters, bleibt dieser Abstand gleich.
    """

    def rect(widget, origin=None):
        tl = widget.mapTo(w, origin or QPoint(0, 0))
        return tl.x(), tl.y(), widget.width(), widget.height()

    tabs = []
    for i in range(w.tabbar.count()):
        r = w.tabbar.tabRect(i)
        x, y, _, _ = rect(w.tabbar, r.topLeft())
        tabs.append((x, y, r.width(), r.height()))
    inds = {}
    for k, ind in w.connections.indicators.items():
        x, y, wd, h = rect(ind)
        inds[k] = (w.width() - (x + wd), y, wd, h)  # Abstand zum rechten Rand
        ix, iy, iw, ih = rect(ind.icon_label)
        inds[k + "_icon"] = (ix - x, iy - y, iw, ih)
    return {"tabs": tabs, "indicators": inds, "header_height": w.header.height()}


# --- 1. Fester Kopf ---------------------------------------------------------------------------

def test_f01_header_is_part_of_the_menu_area_not_of_the_middle(make):
    w = make()
    assert w.menuWidget().isAncestorOf(w.header)
    assert not w.centralWidget().isAncestorOf(w.header)
    assert w.header.width() == w.width()  # ganze Fensterbreite
    top = w.header.mapTo(w, QPoint(0, 0))
    assert top.x() == 0
    for dock in w.docks:  # über allen Docks
        assert w.header.geometry().bottom() < dock.mapTo(w, QPoint(0, 0)).y()
    assert w.header.mapTo(w, QPoint(0, 0)).y() >= w.menu_bar.geometry().bottom()  # direkt unter dem Menü


def test_f01_header_never_moves_dock_positions(make, app):
    w = make()
    base = header_geometry(w)
    d = w.docks[0]  # «Overlays»
    for area in (Qt.DockWidgetArea.LeftDockWidgetArea, Qt.DockWidgetArea.RightDockWidgetArea,
                 Qt.DockWidgetArea.BottomDockWidgetArea, Qt.DockWidgetArea.TopDockWidgetArea):  # fmt: skip
        w.addDockWidget(area, d)
        d.show()
        app.processEvents()
        assert header_geometry(w) == base, area
    d.setFloating(True)  # schwebend
    app.processEvents()
    assert header_geometry(w) == base
    d.setFloating(False)
    d.hide()  # ausgeblendet
    app.processEvents()
    assert header_geometry(w) == base
    d.show()
    for i, dock in enumerate(w.docks):  # alle Docks um das Fenster verteilt
        w.addDockWidget((Qt.DockWidgetArea.LeftDockWidgetArea, Qt.DockWidgetArea.RightDockWidgetArea,
                         Qt.DockWidgetArea.BottomDockWidgetArea)[i % 3], dock)  # fmt: skip
        dock.show()
    app.processEvents()
    assert header_geometry(w) == base
    w.reset_docks_action.trigger()
    app.processEvents()
    assert header_geometry(w) == base


def test_f01_header_ignores_window_size(make, app):
    w = make()
    base = header_geometry(w)
    for size in ((900, 600), (1500, 1000), (1100, 640), (1920, 1080)):
        w.resize(*size)
        app.processEvents()
        g = header_geometry(w)
        assert g == base, size  # linke Lage der Reiter und Abstand der Anzeigen zum rechten Rand gleich


def test_f01_header_ignores_module_switch_and_banner(make, app):
    w = make()
    base = header_geometry(w)
    w.set_module(1)
    app.processEvents()
    assert header_geometry(w) == base
    w.docks_menu.setEnabled(True)
    w._core.unreachable.emit("Der Kern-Dienst ist nicht erreichbar", 3.0)  # Meldung unter dem Kopf
    app.processEvents()
    assert header_geometry(w) == base
    w.set_module(0)
    app.processEvents()
    assert header_geometry(w) == base


def test_f04_indicators_have_fixed_width_for_every_state(make, app):
    w = make()
    base = header_geometry(w)
    for key in SERVICE_KEYS:
        for state in STATES:
            w.connections.set_status(key, state, "x" if state == "Fehler" else "")
            app.processEvents()
            assert header_geometry(w) == base, (key, state)  # keine andere Anzeige und kein Reiter rückt
    for state in STATES:  # alle gleichzeitig
        w.connections.set_all(state)
        app.processEvents()
        assert header_geometry(w) == base, state
    texts = {s: w.connections.text_of("twitch") for s in STATES if not w.connections.set_status("twitch", s)}
    assert len(set(texts.values())) == len(STATES)
    # die feste Breite reicht für den längsten Text
    for key in SERVICE_KEYS:
        ind = w.connections.indicators[key]
        assert ind.text_label.sizeHint().width() <= ind.text_label.width()


def test_f04_indicators_right_aligned_with_fixed_gaps(make):
    w = make()
    rects = [w.connections.indicators[k].mapTo(w, QPoint(0, 0)).x() for k in SERVICE_KEYS]
    assert rects == sorted(rects)  # Reihenfolge Twitch, YouTube, OBS, NDI
    last = w.connections.indicators["ndi"]
    right_edge = last.mapTo(w, QPoint(0, 0)).x() + last.width()
    assert w.width() - right_edge <= 20  # rechtsbündig, nur Rand
    left_of_tabs = w.tabbar.mapTo(w, QPoint(0, 0)).x()
    assert left_of_tabs <= 12  # Reiter ganz links


def test_header_test_would_catch_header_inside_the_middle_area(make, app):
    """Gegenprobe im Test selbst: Steckt der Kopf im Mittelbereich, ändert ein Dock links die Lage."""
    w = make()
    w.header.setParent(None)  # aus dem Menübereich nehmen und in die Mitte setzen (wie in P05)
    w.centralWidget().layout().insertWidget(0, w.header)
    w.header.show()
    app.processEvents()
    base = header_geometry(w)
    w.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, w.docks[0])
    app.processEvents()
    assert header_geometry(w) != base  # der Test erkennt die Verschiebung


# --- 2. YouTube und Dienst-Symbole --------------------------------------------------------------

def test_f04_order_and_all_four_services_with_symbol_and_text(make):
    w = make()
    assert SERVICE_KEYS == ["twitch", "youtube", "obs", "ndi"]
    assert list(w.connections.indicators) == SERVICE_KEYS
    for key, title in SERVICES:
        text = w.connections.text_of(key)
        assert title in text and "unbekannt" in text  # Text
        assert text.split()[0] in {s for s, _ in STATUS_STYLE.values()}  # Zustandszeichen


def test_f04_youtube_tooltip_says_not_configured(make):
    w = make()
    core = w._core
    core.statuses_loaded.emit({"youtube": {"status": "getrennt", "detail": "nicht eingerichtet"}})
    assert "getrennt" in w.connections.text_of("youtube")
    assert w.connections.tooltip_of("youtube") == "YouTube: getrennt (nicht eingerichtet)"
    assert w.connections.tooltip_of("twitch") == "Twitch: getrennt"
    core.status_changed.emit("youtube", "getrennt", "nicht eingerichtet")  # Ereignis trägt den Hinweis


SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64"><rect width="64" height="64" fill="#808080"/></svg>'


def write_test_icons(folder, keys):
    """Selbst erzeugte Test-SVGs, keine Logos."""
    folder.mkdir(parents=True, exist_ok=True)
    for k in keys:
        (folder / f"{k}.svg").write_text(SVG)


def bar_geometry(bar):
    out = {}
    for k, ind in bar.indicators.items():
        out[k] = (ind.width(), ind.height(), ind.icon_label.size().width(), ind.text_label.width())
    return out


def test_f04_service_icons_do_not_change_position_or_width(make, app, tmp_path, monkeypatch):
    # ohne Symbole (Ordner im Repo enthält noch keine Dateien)
    monkeypatch.setattr(widgets, "connection_icon_dir", lambda: tmp_path / "leer")
    w_without = make()
    assert not any(w_without.connections.has_icon(k) for k in SERVICE_KEYS)
    before = header_geometry(w_without)
    # mit Symbolen für alle vier
    folder = tmp_path / "mit"
    write_test_icons(folder, SERVICE_KEYS)
    monkeypatch.setattr(widgets, "connection_icon_dir", lambda: folder)
    w_with = make()
    assert all(w_with.connections.has_icon(k) for k in SERVICE_KEYS)
    for k in SERVICE_KEYS:
        pm = w_with.connections.indicators[k].icon_label.pixmap()
        assert pm is not None and not pm.isNull()
        assert w_with.connections.indicators[k].icon_label.size().width() == widgets.SERVICE_ICON_SIZE
    assert header_geometry(w_with) == before  # Lage und Breite unverändert
    # nur einige Symbole: ebenfalls gleich
    folder2 = tmp_path / "teilweise"
    write_test_icons(folder2, ["twitch", "ndi"])
    monkeypatch.setattr(widgets, "connection_icon_dir", lambda: folder2)
    w_part = make()
    assert [w_part.connections.has_icon(k) for k in SERVICE_KEYS] == [True, False, False, True]
    assert header_geometry(w_part) == before


def test_f04_state_symbol_and_text_stay_next_to_service_icon(make, tmp_path, monkeypatch):
    folder = tmp_path / "i"
    write_test_icons(folder, SERVICE_KEYS)
    monkeypatch.setattr(widgets, "connection_icon_dir", lambda: folder)
    w = make()
    for state in STATES:
        w.connections.set_status("obs", state)
        t = w.connections.text_of("obs")
        assert state in t and "OBS" in t and t.split()[0] == STATUS_STYLE[state][0]  # Zeichen + Text
    # Dienst-Symbol steht vor dem Text
    ind = w.connections.indicators["obs"]
    assert ind.icon_label.mapTo(w, QPoint(0, 0)).x() < ind.text_label.mapTo(w, QPoint(0, 0)).x()


def test_f04_missing_or_broken_icon_file_is_no_error(tmp_path):
    folder = tmp_path / "kaputt"
    folder.mkdir()
    (folder / "twitch.svg").write_text("das ist kein SVG")
    (folder / "obs.png").write_bytes(b"kein PNG")
    (folder / "ndi.svg").write_bytes(b"")
    assert widgets.find_service_icon("twitch", folder) is None
    assert widgets.find_service_icon("obs", folder) is None
    assert widgets.find_service_icon("ndi", folder) is None
    assert widgets.find_service_icon("youtube", folder) is None
    QApplication.instance() or QApplication([])
    bar = ConnectionStatusBar(icon_dir=folder)  # kein Fehler
    assert not any(bar.has_icon(k) for k in SERVICE_KEYS)


def test_f04_icon_dir_documented_in_repo():
    from pathlib import Path

    readme = Path(widgets.connection_icon_dir()) / "README.md"
    text = readme.read_text(encoding="utf-8")
    for name in ("twitch.svg", "youtube.svg", "obs.svg", "ndi.svg"):
        assert name in text
    assert "Nutzungsregeln" in text and "NDI® is a registered trademark of Vizrt NDI AB" in text
    assert "ß" not in text


def test_help_about_names_ndi_trademark_only_when_ndi_icon_is_used(make, tmp_path, monkeypatch):
    shown = []
    monkeypatch.setattr(QMessageBox, "about", lambda parent, title, text: shown.append(text))
    w = make()
    monkeypatch.setattr("donstv_studio.ui.main_window.find_service_icon", lambda key, d=None: None)
    w._about()
    assert "NDI® is a registered trademark of Vizrt NDI AB" not in shown[-1]
    folder = tmp_path / "i"
    write_test_icons(folder, ["ndi"])
    monkeypatch.setattr(
        "donstv_studio.ui.main_window.find_service_icon",
        lambda key, d=None: widgets.find_service_icon(key, folder),
    )
    w._about()
    assert "NDI® is a registered trademark of Vizrt NDI AB" in shown[-1]


# --- 3. Standardanordnung -----------------------------------------------------------------------

def assert_default_arrangement(w, app):
    app.processEvents()
    tops = {d.mapTo(w, QPoint(0, 0)).y() for d in w.docks}
    xs = [d.mapTo(w, QPoint(0, 0)).x() for d in w.docks]
    assert len(tops) == 1, tops  # alle vier auf einer Höhe
    assert xs == sorted(xs) and len(set(xs)) == 4  # nebeneinander: Overlays, Quellen, Eigenschaften, Steuerung
    assert [d.windowTitle() for d in w.docks] == ["Overlays", "Quellen", "Eigenschaften", "Steuerung"]
    for d in w.docks:
        assert w.dockWidgetArea(d) == Qt.DockWidgetArea.BottomDockWidgetArea
        assert not d.isFloating() and d.isVisible()
    widths = [d.width() for d in w.docks]
    assert max(widths) - min(widths) <= 4  # etwa gleich breit
    docks_top = tops.pop()
    prev = w.preview.mapTo(w, QPoint(0, 0))
    assert prev.y() + w.preview.height() <= docks_top  # Vorschau darüber
    assert prev.x() <= 8 and w.preview.width() >= w.width() - 16  # über die volle Breite
    assert abs(w.docks[0].height() - 215) <= 20  # Höhe wie bei OBS


def test_f01_first_start_shows_four_docks_in_a_row_below_the_preview(make, app):
    w = make(1920, 1080)
    assert_default_arrangement(w, app)


def test_f01_reset_action_restores_default_arrangement(make, app):
    w = make(1920, 1080)
    w.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, w.docks[0])  # wie im Bild von P05
    w.docks[2].setFloating(True)
    w.docks[3].hide()
    app.processEvents()
    w.reset_docks_action.trigger()
    assert_default_arrangement(w, app)


def test_f01_old_p05_state_with_dock_on_the_left_is_ignored(make, app):
    old = make(1920, 1080)
    old.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, old.docks[0])
    app.processEvents()
    import base64

    stale = base64.b64encode(bytes(old.saveState(STATE_VERSION - 1))).decode()  # Version 1 = P05
    w = make(1920, 1080)
    w.apply_settings({"ui.dock_state": stale})
    assert_default_arrangement(w, app)


def test_f01_user_can_still_move_docks_and_state_roundtrips(make, app):
    w = make(1920, 1080)
    w.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, w.docks[0])
    app.processEvents()
    values = w.layout_values()
    w2 = make(1920, 1080)
    w2.apply_settings(values)
    app.processEvents()
    assert w2.dockWidgetArea(w2.docks[0]) == Qt.DockWidgetArea.LeftDockWidgetArea


# --- 4. Stil nach OBS ---------------------------------------------------------------------------

def test_obs_style_font_sizes_and_dock_title(make, app):
    w = make(1920, 1080)
    assert w.menu_bar.font().pointSizeF() == pytest.approx(theme.FONT_PT, abs=0.5)
    bar = w.dock_titles[0]
    assert bar.height() == theme.DOCK_TITLE_HEIGHT  # 26 px wie OBS
    assert bar.title.font().bold() and bar.title.font().pointSizeF() == pytest.approx(theme.FONT_PT, abs=0.5)
    assert bar.float_button.toolTip().startswith("Lösen") and bar.close_button.toolTip().startswith("Schliessen")
    assert not bar.float_button.icon().isNull() and not bar.close_button.icon().isNull()
    assert w.statusBar().height() == theme.STATUS_BAR_HEIGHT


def test_obs_style_dock_content_starts_below_the_title_bar(make, app):
    w = make(1920, 1080)
    for dock, bar in zip(w.docks, w.dock_titles, strict=True):
        body = dock.widget()
        top = dock.mapFromGlobal(body.mapToGlobal(QPoint(0, 0))).y()
        assert top == bar.geometry().bottom() + 1 == theme.DOCK_TITLE_HEIGHT  # kein Überdecken
    d, bar = w.docks[0], w.dock_titles[0]
    img = w.grab().toImage()
    x, y0 = d.mapTo(w, QPoint(0, 0)).x() + 150, d.mapTo(w, QPoint(0, 0)).y()
    colors = ["#%06x" % (img.pixel(x, y0 + dy) & 0xFFFFFF) for dy in range(theme.DOCK_TITLE_HEIGHT + 2)]
    p = theme.palette(theme.DARK)
    assert colors[: theme.DOCK_TITLE_HEIGHT] == [p["title_bg"]] * theme.DOCK_TITLE_HEIGHT  # 26 Zeilen Titelfarbe
    assert colors[theme.DOCK_TITLE_HEIGHT] == p["surface"]


def test_obs_style_dock_title_buttons_work(make, app):
    w = make(1920, 1080)
    d, bar = w.docks[1], w.dock_titles[1]
    bar.float_button.click()
    assert d.isFloating()
    bar.float_button.click()
    assert not d.isFloating()
    bar.close_button.click()
    assert d.isHidden()
    d.toggleViewAction().trigger()  # Menü «Docks» blendet wieder ein
    assert d.isVisible()


def pixel(widget, x, y):
    img = widget.grab().toImage()
    return "#%06x" % (img.pixel(x, y) & 0xFFFFFF)


def test_obs_style_dock_title_and_body_colors_dark(make, app):
    w = make(1920, 1080)
    p = theme.palette(theme.DARK)
    bar = w.dock_titles[0]
    assert pixel(bar, bar.width() // 2, 3) == p["title_bg"]  # Titelzeile #3c404d
    body = w.docks[0].widget()
    assert pixel(body, body.width() // 2, body.height() - 10) == p["surface"]


def test_obs_style_list_rows_selected_blue_with_white_text(make, app):
    w = make(1920, 1080)
    lst = QListWidget(w)
    lst.addItems(["Szene A", "Szene B"])
    lst.resize(300, 200)
    lst.move(10, 10)
    lst.show()
    lst.setCurrentRow(0)
    app.processEvents()
    first, second = lst.visualItemRect(lst.item(0)), lst.visualItemRect(lst.item(1))
    assert first.height() == theme.LIST_ROW_HEIGHT == second.height()  # Zeilenhöhe wie OBS (26 px)
    p = theme.palette(theme.DARK)
    img = lst.viewport().grab().toImage()
    far_right = first.right() - 4
    assert "#%06x" % (img.pixel(far_right, first.center().y()) & 0xFFFFFF) == p["selection_bg"]
    assert "#%06x" % (img.pixel(far_right, second.center().y()) & 0xFFFFFF) == p["surface"]
    # Schrift der gewählten Zeile ist weiss: ein heller Pixel im Textbereich
    row = [img.pixel(x, first.center().y() + dy) & 0xFFFFFF for x in range(first.left(), first.left() + 80)
           for dy in range(-6, 7)]  # fmt: skip
    assert 0xFFFFFF in row
    lst.deleteLater()


def test_obs_style_preview_has_black_canvas_with_border(make, app):
    w = make(1920, 1080)
    pv, cv = w.preview, w.preview.canvas
    p = theme.palette(theme.DARK)
    assert pixel(pv, 2, 2) == p["preview_bg"]  # dunkler Rand
    assert pixel(cv, cv.width() // 2, 5) == p["canvas"] == "#000000"
    assert cv.x() > 0 and cv.y() > 0 and cv.x() + cv.width() < pv.width()  # Rand rundum, nicht bis zum Rand
    assert abs((cv.x() + cv.width() / 2) - pv.width() / 2) <= 1  # mittig
    assert abs(cv.width() / cv.height() - 16 / 9) < 0.02
    w.resize(1000, 700)
    app.processEvents()
    assert abs(cv.width() / cv.height() - 16 / 9) < 0.02 and cv.width() <= pv.width() - 2 * pv.MARGIN


def test_obs_style_preview_bar_placeholder_with_disabled_buttons(make):
    w = make()
    bar = w.preview_bar
    assert bar.label.text() == "Keine Quelle ausgewählt"
    assert [bar.properties.text(), bar.filters.text()] == ["Eigenschaften", "Filter"]
    assert not bar.properties.isEnabled() and not bar.filters.isEnabled()
    assert bar.height() == theme.PREVIEW_BAR_HEIGHT
    # Leiste liegt direkt unter der Vorschau, vor den Docks
    assert w.preview.geometry().bottom() < bar.mapTo(w, QPoint(0, 0)).y() < w.docks[0].mapTo(w, QPoint(0, 0)).y()


def test_obs_style_status_bar_has_core_status_on_the_right(make):
    w = make(1920, 1080)
    right = w.core_status.mapTo(w, QPoint(0, 0)).x() + w.core_status.width()
    assert w.width() - right <= 8
    assert "Kern-Dienst" in w.core_status.text()


def test_obs_style_light_theme_still_readable(make, app):
    w = make(1280, 800)
    w.set_theme("light")
    app.processEvents()
    p = theme.palette("light")
    bar = w.dock_titles[0]
    assert pixel(bar, bar.width() // 2, 3) == p["title_bg"]
    assert pixel(w.preview.canvas, 20, 20) == p["canvas"]


def test_dock_titles_follow_theme_icons(make):
    w = make()
    before = w.dock_titles[0].close_button.icon().pixmap(14, 14).toImage()
    w.set_theme("light")
    after = w.dock_titles[0].close_button.icon().pixmap(14, 14).toImage()
    assert before != after  # Symbole in der Textfarbe des neuen Themes


def test_all_docks_are_qdockwidgets_with_custom_title(make):
    w = make()
    for d in w.docks:
        assert isinstance(d, QDockWidget) and d.titleBarWidget() is not None
