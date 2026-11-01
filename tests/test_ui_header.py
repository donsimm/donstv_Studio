"""F-01, F-02, F-04: fester Fensterkopf, YouTube, Dienst-Symbole, Standardanordnung, OBS-Stil."""

import itertools

import pytest

pytest.importorskip(
    "PyQt6.QtWidgets",
    exc_type=ImportError,
    reason="PyQt6 ist nicht installierbar oder lädt nicht (Systembibliotheken fehlen?)",
)

from PyQt6.QtCore import QObject, QPoint, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFontMetrics
from PyQt6.QtWidgets import QApplication, QDockWidget, QListWidget, QMessageBox

from donstv_studio.ui import perf, theme, widgets
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
    """Lage und Grösse der Reiter, Verbindungs-Buttons und Leistungsfelder in Fensterkoordinaten.

    Rechtsbündige Teile (Buttons, Leistungsfelder) werden vom rechten Fensterrand aus gemessen: Ändert
    sich die Breite des Fensters, bleibt dieser Abstand gleich.
    """

    def rect(widget, origin=None):
        tl = widget.mapTo(w, origin or QPoint(0, 0))
        return tl.x(), tl.y(), widget.width(), widget.height()

    def from_right(widget):
        x, y, wd, h = rect(widget)
        return w.width() - (x + wd), y, wd, h

    tabs = []
    for i in range(w.tabbar.count()):
        r = w.tabbar.tabRect(i)
        x, y, _, _ = rect(w.tabbar, r.topLeft())
        tabs.append((x, y, r.width(), r.height()))
    inds = {k: from_right(ind) for k, ind in w.connections.indicators.items()}
    fields = {k: from_right(f) for k, f in w.perf.fields.items()}
    return {"tabs": tabs, "indicators": inds, "perf": fields, "header_height": w.header.height()}


# --- 1. Fester Kopf ---------------------------------------------------------------------------

def test_f01_header_is_part_of_the_menu_area_not_of_the_middle(make):
    w = make()
    assert w.menuWidget().isAncestorOf(w.header)
    assert not w.centralWidget().isAncestorOf(w.header)
    assert w.header.width() == w.width() - 2 * theme.HEADER_MARGIN  # ganze Fensterbreite, Rahmen mit kleinem Rand
    top = w.header.mapTo(w, QPoint(0, 0))
    assert top.x() == theme.HEADER_MARGIN
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
    low = w.minimumWidth()
    for size in ((low, 600), (low + 1, 700), (low + 120, 640), (1920, 1080), (2400, 1300), (low, 900)):
        w.resize(*size)
        app.processEvents()
        g = header_geometry(w)
        assert g == base, size  # linke Lage der Reiter und Abstand der Anzeigen zum rechten Rand gleich


def test_f68_perf_fields_keep_position_and_size_when_values_change(make, app):
    w = make()
    base = header_geometry(w)
    longest = perf.Sample(cpu=100.0, mem=(int(999.9 * perf.GIB), int(999.9 * perf.GIB)), net=(999.9e6, 999.9e6))
    shortest = perf.Sample(cpu=0.0, mem=(0, 1024), net=(0.0, 0.0))
    for sample in (longest, shortest, perf.Sample(), longest, perf.Sample(cpu=4.0, mem=(5 * perf.GIB, 15 * perf.GIB), net=(3000, 99000))):
        w.perf.apply(sample)
        app.processEvents()
        assert header_geometry(w) == base
        w.grab()  # zeichnet: keine Ausnahme
    w.set_theme("light")
    app.processEvents()
    assert header_geometry(w) == base


def test_f68_perf_texts_fit_into_fixed_widths(make):
    w = make()
    for key, f in w.perf.fields.items():
        fm = QFontMetrics(f._value_font())
        title_w = QFontMetrics(f.font()).horizontalAdvance(f.title)
        for text in (perf.LONGEST[key], perf.NO_VALUE):
            assert title_w + fm.horizontalAdvance(text) + 2 * f.PAD <= f.width(), (key, text)
        assert f.height() == widgets.PERF_HEIGHT <= theme.HEADER_HEIGHT
    assert [f.title for f in w.perf.fields.values()] == ["CPU", "RAM", "LAN"]


def test_f68_perf_shows_value_as_text_and_dash_without_data(make):
    w = make()
    w.perf.apply(perf.Sample(cpu=4.2, mem=(int(5.3 * perf.GIB), int(15.5 * perf.GIB)), net=(3000, 99000)))
    f = w.perf.fields
    assert (f["cpu"].value_text, f["ram"].value_text) == ("4 %", "5.3 / 15.5 GiB")
    assert f["lan"].value_text == "↓ 3  ↑ 99 kbit/s"
    assert f["cpu"].accessibleName() == "CPU: 4 %"
    w.perf.apply(perf.Sample())  # /proc nicht lesbar
    assert [x.value_text for x in f.values()] == ["–", "–", "–"]


def test_f68_perf_history_has_exactly_60_values_oldest_drops_out(make):
    w = make()
    for i in range(75):
        w.perf.apply(perf.Sample(cpu=float(i)))
    values = w.perf.fields["cpu"].values
    assert len(values) == perf.HISTORY_LENGTH == 60
    assert values == [float(i) for i in range(15, 75)]


def test_f68_header_height_and_vertical_centering(make):
    w = make()
    assert w.header.height() == theme.HEADER_HEIGHT and theme.HEADER_HEIGHT > 48  # höher als in P05c (48)
    assert theme.PERF_GRAPH_HEIGHT == 28
    mid = w.header.height() / 2
    for widget in [w.tabbar, w.perf, w.connections]:
        top = widget.mapTo(w.header, QPoint(0, 0)).y()
        assert abs(top + widget.height() / 2 - mid) <= 1.5, widget


def header_parts(w):
    parts = [("tabs", w.tabbar)] + [(k, i) for k, i in w.connections.indicators.items()] + [("perf", w.perf)]
    return [(n, widget.mapTo(w, QPoint(0, 0)).x(), widget.width()) for n, widget in parts]


def test_f68_minimum_width_fits_everything_without_overlap_or_clipping(make, app):
    w = make()
    assert w.minimumWidth() == w.header.layout().minimumSize().width() + 2 * theme.HEADER_MARGIN
    w.resize(100, 700)  # kleiner geht nicht
    app.processEvents()
    assert w.width() == w.minimumWidth()
    parts = header_parts(w)
    for (n1, x1, w1), (n2, x2, w2) in itertools.pairwise(parts):
        assert x1 + w1 <= x2, (n1, n2)  # nichts überlappt
    assert parts[0][1] >= 0 and parts[-1][1] + parts[-1][2] <= w.width()  # nichts abgeschnitten
    assert w.tabbar.width() >= w.tabbar.sizeHint().width()  # Reiter nicht gestaucht, keine Laufpfeile
    for i in range(w.tabbar.count()):
        assert w.tabbar.tabRect(i).left() >= 0
    # in beiden Themes
    w.set_theme("light")
    app.processEvents()
    assert w.minimumWidth() == w.header.layout().minimumSize().width() + 2 * theme.HEADER_MARGIN


def test_f68_perf_bar_does_not_run_while_minimized_or_hidden(make, app):
    w = make()
    assert w.perf.timer.isActive() and w.perf.timer.interval() == 1000
    w.showMinimized()
    app.processEvents()
    assert not w.perf.timer.isActive()
    w.showNormal()
    app.processEvents()
    assert w.perf.timer.isActive()
    w.hide()
    assert not w.perf.timer.isActive()


def test_f68_perf_is_always_visible_no_switch(make):
    w = make()
    assert w.perf.isVisible() and all(f.isVisible() for f in w.perf.fields.values())
    from PyQt6.QtGui import QAction

    texts = [a.text().lower() for m in w.menu_bar.findChildren(type(w.docks_menu)) for a in m.actions()]
    assert not any("leistung" in t for t in texts)  # kein Schalter
    assert not [a for a in w.findChildren(QAction) if "leistung" in a.text().lower()]


def test_f68_perf_tick_with_missing_proc_files_does_not_fail(make, tmp_path):
    w = make()
    w.perf.sampler = perf.Sampler(paths=perf.ProcPaths(tmp_path / "a", tmp_path / "b", tmp_path / "c"))
    w.perf.tick()
    w.perf.tick()
    assert [x.value_text for x in w.perf.fields.values()] == ["–", "–", "–"]


def test_f68_perf_load_per_tick_is_small(make, app):
    """Eigenlast: Messen, Rechnen, Zeichnen. Ziel < 1 % einer CPU-Sekunde (also < 10 ms pro Messung)."""
    import time

    w = make()
    for _ in range(5):  # Aufwärmen
        w.perf.tick()
        w.perf.grab()
    n = 100
    start = time.process_time()
    for _ in range(n):
        w.perf.tick()
        w.perf.grab()  # erzwingt das Zeichnen der drei Felder
    per_tick_ms = (time.process_time() - start) / n * 1000
    print(f"Eigenlast pro Messung samt Zeichnen: {per_tick_ms:.2f} ms")
    assert per_tick_ms < 10, per_tick_ms


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
    for key in SERVICE_KEYS:  # feste Grösse der Buttons
        ind = w.connections.indicators[key]
        assert (ind.width(), ind.height()) == (theme.CONN_BUTTON_WIDTH, theme.CONN_BUTTON_HEIGHT)


def test_f04_buttons_left_of_the_perf_bar_and_perf_bar_at_the_far_right(make):
    w = make()
    xs = [w.connections.indicators[k].mapTo(w, QPoint(0, 0)).x() for k in SERVICE_KEYS]
    assert xs == sorted(xs)  # Reihenfolge Twitch, YouTube, OBS, NDI
    ndi = w.connections.indicators["ndi"]
    perf_left = w.perf.mapTo(w, QPoint(0, 0)).x()
    assert ndi.mapTo(w, QPoint(0, 0)).x() + ndi.width() < perf_left  # Buttons links der Leistungsanzeige
    right_edge = perf_left + w.perf.width()
    assert w.width() - right_edge <= theme.HEADER_MARGIN + 12  # Leistungsanzeige ganz rechts
    assert w.tabbar.mapTo(w, QPoint(0, 0)).x() <= 16  # Reiter ganz links


def test_f04_button_color_follows_the_state_and_state_is_also_a_sign_and_text(make):
    w = make()
    ind = w.connections.indicators["twitch"]
    cases = [
        ("verbunden", "", "ok"),  # grün
        ("getrennt", "", "error"),  # rot
        ("Fehler", "x", "error"),
        ("verbindet", "", "warn"),  # orange
        ("getrennt", "nicht eingerichtet", "text_muted"),  # ausgegraut
        ("unbekannt", "", "text_muted"),
    ]
    seen = set()
    for status, detail, color in cases:
        ind.set_state(status, detail)
        assert ind.color_name() == color, (status, detail)
        assert status in ind.text() and ind.text().split()[0] == STATUS_STYLE[status][0]  # Zeichen + Text
        assert status in ind.toolTip() and status in ind.accessibleName()
        seen.add(color)
    assert seen == {"ok", "warn", "error", "text_muted"}
    pal = theme.palette(theme.DARK)
    ind.set_state("verbunden")
    img = ind.grab().toImage()
    assert img.pixelColor(ind.width() // 2, 1).name() == pal["ok"]  # Rand oben in Grün
    ind.set_state("verbindet")
    assert ind.grab().toImage().pixelColor(ind.width() // 2, 1).name() == pal["warn"]
    ind.set_state("getrennt")
    assert ind.grab().toImage().pixelColor(ind.width() // 2, 1).name() == pal["error"]
    ind.set_state("getrennt", "nicht eingerichtet")
    assert ind.grab().toImage().pixelColor(ind.width() // 2, 1).name() == pal["text_muted"]


def test_f04_dot_sign_is_drawn_on_the_button(make):
    w = make()
    ind = w.connections.indicators["obs"]
    ind.set_state("verbunden")
    a = ind.grab().toImage()
    ind.set_state("Fehler")
    b = ind.grab().toImage()
    dot = (ind.width() - 9, ind.height() - 9)
    assert a.pixelColor(*dot) != b.pixelColor(*dot)


def test_f04_header_has_a_subtle_frame_all_around(make, app):
    w = make(1600, 900)
    p = theme.palette(theme.DARK)
    img = w.grab().toImage()
    h = w.header
    tl = h.mapTo(w, QPoint(0, 0))
    mid_x, mid_y = tl.x() + h.width() // 2, tl.y() + h.height() // 2
    for x, y in ((mid_x, tl.y()), (mid_x, tl.y() + h.height() - 1), (tl.x(), mid_y), (tl.x() + h.width() - 1, mid_y)):
        assert img.pixelColor(x, y).name() == p["border"], (x, y)  # Rahmen oben, unten, links, rechts
    assert theme.contrast_ratio(p["border"], p["bg"]) < 2.5  # dezent


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
        out[k] = (ind.width(), ind.height())
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
        pm = w_with.connections.indicators[k].icon_pixmap()
        assert pm is not None and not pm.isNull()
        assert pm.deviceIndependentSize().width() == widgets.SERVICE_ICON_SIZE
    assert header_geometry(w_with) == before  # Lage und Breite unverändert
    # nur einige Symbole: ebenfalls gleich
    folder2 = tmp_path / "teilweise"
    write_test_icons(folder2, ["twitch", "ndi"])
    monkeypatch.setattr(widgets, "connection_icon_dir", lambda: folder2)
    w_part = make()
    assert [w_part.connections.has_icon(k) for k in SERVICE_KEYS] == [True, False, False, True]
    assert header_geometry(w_part) == before


def test_f04_state_symbol_and_text_with_service_icons(make, tmp_path, monkeypatch):
    folder = tmp_path / "i"
    write_test_icons(folder, SERVICE_KEYS)
    monkeypatch.setattr(widgets, "connection_icon_dir", lambda: folder)
    w = make()
    for state in STATES:
        w.connections.set_status("obs", state)
        t = w.connections.text_of("obs")
        assert state in t and "OBS" in t and t.split()[0] == STATUS_STYLE[state][0]  # Zeichen + Text
        assert w.connections.indicators["obs"].icon_pixmap() is not None


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


# --- Dienst-Symbole mit den echten Dateien (P05c) ------------------------------------------------

def tinted_pixels(label):
    """Farben (ohne Alpha) aller sichtbaren Pixel des Symbols."""
    img = label.icon_pixmap().toImage()
    out = set()
    for y in range(img.height()):
        for x in range(img.width()):
            c = img.pixelColor(x, y)
            if c.alpha() > 200:
                out.add(c.name())
    return out


@pytest.mark.parametrize("name", [theme.DARK, theme.LIGHT])
def test_f04_real_icons_are_drawn_in_the_text_color_of_the_theme(make, app, name):
    w = make()
    w.set_theme(name)
    app.processEvents()
    text = theme.palette(name)["text"]
    w.connections.set_all("verbunden")  # ausgegraute Symbole sind im Nebentext-Ton, siehe unten
    for key in SERVICE_KEYS:
        assert w.connections.has_icon(key), key  # die Dateien liegen im Repo
        colors = tinted_pixels(w.connections.indicators[key])
        assert colors, key  # sichtbare Pixel vorhanden
        ref = QColor(text)
        for c in colors:  # Textfarbe (±2 wegen Rundung bei Alpha), nicht weiss auf weiss
            q = QColor(c)
            assert max(abs(q.red() - ref.red()), abs(q.green() - ref.green()), abs(q.blue() - ref.blue())) <= 2, (key, c)
        assert theme.contrast_ratio(text, theme.palette(name)["bg"]) >= 4.5


def test_f04_icons_are_retinted_when_the_theme_changes(make, app):
    w = make()
    label = w.connections.indicators["twitch"]
    dark = label.icon_pixmap().toImage()
    w.set_theme("light")
    app.processEvents()
    light = label.icon_pixmap().toImage()
    assert dark != light
    w.set_theme("dark")
    assert label.icon_pixmap().toImage() == dark


def test_f04_icon_files_in_the_repo_are_single_colour_with_alpha():
    from PyQt6.QtGui import QPixmap

    for key in SERVICE_KEYS:
        pm = QPixmap(str(widgets.connection_icon_dir() / f"{key}.png"))
        assert not pm.isNull() and pm.width() >= 64
        assert pm.hasAlphaChannel()


def make_png_dir(folder, keys, color="#ff0000"):
    from PyQt6.QtGui import QColor, QImage

    folder.mkdir(parents=True, exist_ok=True)
    for k in keys:
        img = QImage(64, 64, QImage.Format.Format_ARGB32)
        img.fill(QColor(color))
        img.save(str(folder / f"{k}.png"))


def test_f04_png_is_shown_without_the_svg_module(make, app, tmp_path, monkeypatch):
    monkeypatch.setattr(widgets, "HAS_SVG", False)  # Qt-SVG-Modul fehlt (simuliert)
    folder = tmp_path / "png"
    make_png_dir(folder, SERVICE_KEYS)
    monkeypatch.setattr(widgets, "connection_icon_dir", lambda: folder)
    w = make()
    assert all(w.connections.has_icon(k) for k in SERVICE_KEYS)
    assert tinted_pixels(w.connections.indicators["obs"])
    # auch die echten Dateien im Repo: PNG vorhanden, also angezeigt
    monkeypatch.undo()
    monkeypatch.setattr(widgets, "HAS_SVG", False)
    w2 = make()
    assert all(w2.connections.has_icon(k) for k in SERVICE_KEYS)


def test_f04_png_wins_over_svg_when_both_exist(tmp_path, monkeypatch):
    make_png_dir(tmp_path, ["twitch"])
    (tmp_path / "twitch.svg").write_text(SVG)  # grau, 64 × 64
    for has_svg in (True, False):
        monkeypatch.setattr(widgets, "HAS_SVG", has_svg)
        QApplication.instance() or QApplication([])
        pm = widgets.load_service_pixmap("twitch", tmp_path)
        assert pm is not None
        assert pm.toImage().pixelColor(pm.width() // 2, pm.height() // 2).name() == "#ff0000"  # PNG, nicht SVG


def test_f04_only_svg_without_svg_module_gives_one_hint_in_the_log(tmp_path, monkeypatch, caplog):
    QApplication.instance() or QApplication([])
    write_test_icons(tmp_path, ["twitch", "obs"])
    monkeypatch.setattr(widgets, "HAS_SVG", False)
    monkeypatch.setattr(widgets, "_svg_hint_given", False)
    with caplog.at_level("WARNING"):
        assert widgets.load_service_pixmap("twitch", tmp_path) is None
        assert widgets.load_service_pixmap("obs", tmp_path) is None
    hints = [r for r in caplog.records if "Qt-SVG-Modul" in r.getMessage()]
    assert len(hints) == 1  # einmalig
    assert "libqt6svg6" in hints[0].getMessage()


def test_f04_layout_is_the_same_with_png_only_svg_only_and_no_files(make, tmp_path, monkeypatch):
    monkeypatch.setattr(widgets, "connection_icon_dir", lambda: tmp_path / "leer")
    base = header_geometry(make())
    png = tmp_path / "png"
    make_png_dir(png, SERVICE_KEYS)
    monkeypatch.setattr(widgets, "connection_icon_dir", lambda: png)
    assert header_geometry(make()) == base
    monkeypatch.setattr(widgets, "connection_icon_dir", lambda: widgets.Path(__file__).parents[1] / "assets/icons/connections")
    assert header_geometry(make()) == base  # echte Dateien


def test_help_about_names_ndi_trademark_with_the_real_icon_file(make, monkeypatch):
    shown = []
    monkeypatch.setattr(QMessageBox, "about", lambda parent, title, text: shown.append(text))
    w = make()
    w._about()  # echte Dateien im Repo: ndi.png/ndi.svg vorhanden
    assert "NDI® is a registered trademark of Vizrt NDI AB" in shown[-1]


def test_f04_not_configured_button_is_greyed_out_icon_in_muted_color(make):
    w = make()
    ind = w.connections.indicators["youtube"]
    ind.set_state("getrennt", "nicht eingerichtet")
    muted = QColor(theme.palette(theme.DARK)["text_muted"])
    for c in tinted_pixels(ind):
        q = QColor(c)
        assert max(abs(q.red() - muted.red()), abs(q.green() - muted.green()), abs(q.blue() - muted.blue())) <= 2
