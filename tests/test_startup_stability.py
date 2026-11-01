"""P06d2 (F-01, F-68, F-78): Absturz beim Start seit P06d – keine Grössenänderung in Stil- oder Layout-Ereignissen,
gleiche Breite idempotent, gespeicherte schmale Fensterlage, Diagnose-Schalter, Startprüfung unter Xvfb."""

import inspect
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip(
    "PyQt6.QtWidgets",
    exc_type=ImportError,
    reason="PyQt6 ist nicht installierbar oder lädt nicht (Systembibliotheken fehlen?)",
)

from PyQt6.QtCore import QCoreApplication, QEvent
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication

from donstv_studio.ui import diagnose, main_window
from donstv_studio.ui import main as ui_main
from donstv_studio.ui.main_window import KEY_GEOMETRY, MainWindow
from donstv_studio.ui.widgets import PerfBar, PerfField
from fake_core import FakeCore

ROOT = Path(__file__).resolve().parents[1]
# Methoden, in denen keine Grösse gesetzt werden darf (CLAUDE.md Regel 16)
BIG_FONT = "QWidget { font-size: 16pt; }"
EVENT_HANDLERS = {"event", "resizeEvent", "changeEvent", "polish", "eventFilter", "showEvent"}


@pytest.fixture
def make(app):
    windows = []

    def factory(show=True):
        w = MainWindow(FakeCore())
        if show:
            w.resize(1280, 800)
            w.show()
            app.processEvents()
        windows.append(w)
        return w

    yield factory
    for w in windows:
        w.close()
        w.deleteLater()
    app.processEvents()


@pytest.fixture
def size_calls(monkeypatch):
    """Ersatz für setFixedWidth (Leistungsfelder) und setMinimumWidth (Hauptfenster): zählt jeden Aufruf und
    merkt sich die Python-Methoden auf dem Weg dorthin."""
    calls = []
    orig_fixed = PerfField.setFixedWidth
    orig_min = MainWindow.setMinimumWidth

    def record(kind):
        names = [f.function for f in inspect.stack()[2:12]]
        calls.append((kind, names))

    def fixed(self, w):
        record("setFixedWidth")
        return orig_fixed(self, w)

    def minimum(self, w):
        record("setMinimumWidth")
        return orig_min(self, w)

    monkeypatch.setattr(PerfField, "setFixedWidth", fixed)
    monkeypatch.setattr(MainWindow, "setMinimumWidth", minimum)
    return calls


def inside_handler(calls):
    return [(kind, names) for kind, names in calls if EVENT_HANDLERS & set(names)]


def settle(app, rounds=5):
    for _ in range(rounds):
        app.processEvents()


# --- keine Grössenänderung in Stil-, Schrift- oder Layout-Ereignissen ------------------------------
def test_f78_no_set_fixed_width_inside_style_or_layout_events(make, app, size_calls):
    w = make()  # Aufbau mit Stylesheet und Polieren
    font = QFont(app.font())
    try:
        w.set_theme("light")  # Stylesheet neu: StyleChange und Polieren aller Widgets
        settle(app)
        w.set_theme("dark")
        settle(app)
        bigger = QFont(font)
        bigger.setPointSizeF(font.pointSizeF() + 3)
        app.setFont(bigger)  # Schriftwechsel der Anwendung: FontChange an alle Widgets
        settle(app)
        w.perf.setStyleSheet(
            BIG_FONT
        )  # eigener Stil: StyleChange, Polieren und FontChange der Felder
        settle(app)
        for f in w.perf.fields.values():  # Stil- und Polier-Ereignisse direkt
            QCoreApplication.sendEvent(f, QEvent(QEvent.Type.StyleChange))
            QCoreApplication.sendEvent(f, QEvent(QEvent.Type.PolishRequest))
            QCoreApplication.sendEvent(f, QEvent(QEvent.Type.FontChange))
        settle(app)
        w.resize(w.minimumWidth() + 50, 700)
        settle(app)
        assert size_calls, "es wurde gar keine Breite gesetzt; der Test misst nichts"
        assert inside_handler(size_calls) == []
        # das Verhalten bleibt: gleiche Breite für die neue Schrift, Mindestbreite passt dazu
        widths = {f.width() for f in w.perf.fields.values()}
        assert len(widths) == 1
        assert widths.pop() == max(f.needed_width() for f in w.perf.fields.values())
        assert (
            w.minimumWidth()
            == w.header.layout().minimumSize().width() + 2 * main_window.theme.HEADER_MARGIN
        )
    finally:
        app.setFont(font)
        w.perf.setStyleSheet("")
        settle(app)


def test_f78_font_change_is_applied_once_after_the_event(make, app, size_calls):
    w = make()
    before = w.perf.fields["cpu"].width()
    try:
        size_calls.clear()
        w.perf.setStyleSheet(
            BIG_FONT
        )  # grössere Schrift: Stil- und Schriftereignisse an alle drei Felder
        # im Ereignis selbst noch nichts gesetzt, erst nach der Ereignisschleife (Zeitgeber 0 ms)
        assert [c for c in size_calls if c[0] == "setFixedWidth"] == []
        settle(app)
        fixed = [c for c in size_calls if c[0] == "setFixedWidth"]
        assert len(fixed) == 3  # drei Felder, je ein Mal, trotz vieler Ereignisse
        assert all("equalize" in names for _kind, names in fixed)
        assert len({f.width() for f in w.perf.fields.values()}) == 1
        assert w.perf.fields["cpu"].width() > before
    finally:
        w.perf.setStyleSheet("")
        settle(app)


def test_f78_single_perf_field_without_bar_updates_after_the_event(app, size_calls):
    f = PerfField("cpu")
    f.ensurePolished()
    size_calls.clear()
    before = f.width()
    f.setStyleSheet(BIG_FONT)
    assert size_calls == []
    settle(app)
    assert [k for k, _ in size_calls] == ["setFixedWidth"]
    assert f.width() == f.needed_width() > before
    f.deleteLater()
    settle(app)


def test_f78_equalize_is_idempotent(make, app, size_calls):
    w = make()
    settle(app)
    widths = {k: f.width() for k, f in w.perf.fields.items()}
    emitted = []
    w.perf.widths_changed.connect(lambda: emitted.append(1))
    size_calls.clear()
    for _ in range(3):
        w.perf.equalize()
    settle(app)
    assert size_calls == []  # keine Breite gesetzt, Mindestbreite nicht neu gesetzt
    assert emitted == []
    assert {k: f.width() for k, f in w.perf.fields.items()} == widths


def test_f78_requests_are_coalesced(app, size_calls):
    bar = PerfBar()
    settle(app)
    for f in bar.fields.values():
        f.setFixedWidth(10)  # künstlich falsch
    size_calls.clear()
    for _ in range(10):
        bar.request_equalize()
    assert size_calls == []
    settle(app)
    assert len(size_calls) == 3
    assert len({f.width() for f in bar.fields.values()}) == 1
    bar.deleteLater()
    settle(app)


# --- gespeicherte schmale Fensterlage --------------------------------------------------------------
def narrow_values(app):
    """Gespeicherte Werte mit einer Fensterlage schmaler als die Mindestbreite (wie aus P08)."""
    w = MainWindow(FakeCore())
    w.show()
    settle(app)
    w.setMinimumWidth(0)
    w.resize(700, 600)
    settle(app)
    values = w.layout_values()
    narrow = w.width()
    w.close()
    w.deleteLater()
    settle(app)
    return values, narrow


def test_f01_saved_narrow_geometry_is_adjusted_safely_at_start(make, app, monkeypatch):
    values, narrow = narrow_values(app)
    w = make(show=False)
    assert narrow < w.minimumWidth()
    restored = []
    orig = MainWindow.restoreGeometry
    monkeypatch.setattr(
        MainWindow, "restoreGeometry", lambda self, g: restored.append(1) or orig(self, g)
    )
    w.apply_settings(values)  # wie main(): vor dem Anzeigen
    assert restored == [1]
    assert w.width() >= w.minimumWidth()
    w.show()
    settle(app)
    assert w.width() >= w.minimumWidth()
    # nach dem Verbinden kommen dieselben Werte noch einmal (Signal settings_loaded): Lage nicht erneut gesetzt
    w._core.settings_loaded.emit(json.dumps(values))
    settle(app)
    assert restored == [1]
    assert w.width() >= w.minimumWidth()


def test_f01_minimum_width_applies_before_the_saved_geometry(make, app, monkeypatch):
    values, _narrow = narrow_values(app)
    w = make(show=False)
    order = []
    orig_restore = MainWindow.restoreGeometry
    orig_update = MainWindow._update_minimum_width
    monkeypatch.setattr(
        MainWindow,
        "restoreGeometry",
        lambda self, g: order.append("lage") or orig_restore(self, g),
    )
    monkeypatch.setattr(
        MainWindow,
        "_update_minimum_width",
        lambda self: order.append("mindestbreite") or orig_update(self),
    )
    w.apply_settings(values)
    assert order[-2:] == ["mindestbreite", "lage"]


def test_f01_other_saved_geometry_is_still_applied(make, app):
    values, _narrow = narrow_values(app)
    w = make()
    w.apply_settings(values)
    first = w.geometry()
    other = MainWindow(FakeCore())
    other.resize(other.minimumWidth() + 30, 500)
    other.show()
    settle(app)
    changed = dict(values, **{KEY_GEOMETRY: other.layout_values()[KEY_GEOMETRY]})
    w.apply_settings(changed)
    settle(app)
    assert w.height() == 500 and w.geometry() != first
    other.close()
    other.deleteLater()


# --- Diagnose-Schalter (DONSTV_OFF) und DONSTV_AUTOQUIT_MS -----------------------------------------
def test_f01_diagnose_switches_parse(monkeypatch):
    monkeypatch.setenv(diagnose.ENV, "perf_equalize, rename unbekannt,min_width")
    assert diagnose.switched_off() == {"perf_equalize", "rename", "min_width"}
    monkeypatch.delenv(diagnose.ENV)
    assert diagnose.switched_off() == frozenset()


def test_f01_diagnose_switches_restore_p08_parts(make, app, monkeypatch):
    normal = make()
    min_normal = normal.minimumWidth()
    monkeypatch.setenv(diagnose.ENV, ",".join(diagnose.SWITCHES))
    w = make()
    settle(app)
    fields = w.perf.fields.values()
    assert [f.width() for f in fields] == [f.p08_width() for f in fields]  # perf_equalize
    assert w.editor.pointer_badge is None  # pointer_badge
    assert "image: url(" not in QApplication.instance().styleSheet()  # qss_images
    assert w.minimumWidth() < min_normal  # min_width
    assert not w.properties_panel.name.isVisibleTo(w)  # rename
    assert w.sources_panel.rename_action not in w.sources_panel.list.actions()
    assert w.sources_panel.rename_action not in w.editor.actions()
    monkeypatch.delenv(diagnose.ENV)
    w.set_theme("light")  # Stylesheet mit Bildern zurück für die anderen Tests
    w.set_theme("dark")
    settle(app)
    assert "image: url(" in QApplication.instance().styleSheet()


def test_f01_autoquit_variable(monkeypatch):
    monkeypatch.delenv("DONSTV_AUTOQUIT_MS", raising=False)
    assert ui_main._autoquit_ms() is None
    monkeypatch.setenv("DONSTV_AUTOQUIT_MS", "2500")
    assert ui_main._autoquit_ms() == 2500
    monkeypatch.setenv("DONSTV_AUTOQUIT_MS", "bald")
    assert ui_main._autoquit_ms() is None


# --- Startprüfung mit echtem Fenstersystem (Xvfb) ---------------------------------------------------
@pytest.mark.skipif(shutil.which("Xvfb") is None, reason="Xvfb nicht installiert")
def test_f01_real_ui_starts_20_times_with_xcb_under_xvfb():
    env = {k: v for k, v in os.environ.items() if k not in ("DISPLAY", "QT_QPA_PLATFORM")}
    env.pop("DONSTV_OFF", None)
    r = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "start_pruefung.py"), "--laeufe", "20"],
        capture_output=True,
        text=True,
        timeout=20 * 150,
        env=env,
        cwd=str(ROOT),
        check=False,
    )
    assert "20 von 20 Läufen mit Exit-Code 0" in r.stdout, r.stdout[-4000:] + r.stderr[-2000:]
    assert r.returncode == 0
