"""P06d5 (F-01, F-78): Massnahmen gegen den Absturz beim Start – Dock-Anordnung nur einmal, bei maximierter Lage erst
nach dem Anzeigen, Seitenwechsel der Listen erst nach `layout_restored`; jede Massnahme mit ihrem Schalter."""

import json
import shutil
import time

import pytest

pytest.importorskip(
    "PyQt6.QtWidgets",
    exc_type=ImportError,
    reason="PyQt6 ist nicht installierbar oder lädt nicht (Systembibliotheken fehlen?)",
)

from PyQt6.QtCore import Qt

from donstv_studio.ui import diagnose
from donstv_studio.ui import main_window as mw
from donstv_studio.ui.backend import DirectRunner
from donstv_studio.ui.main_window import KEY_GEOMETRY, KEY_STATE, STATE_VERSION, MainWindow
from fake_core import FakeCore
from test_startup_data import NEEDS_XVFB, _start_check, _xvfb_env, filled_backend, run_loop

ALL_FIXES = " ".join(diagnose.FIXES)
SETTLE = (mw.RESTORE_SETTLE_MS + 300) / 1000


@pytest.fixture
def windows(app, monkeypatch):
    monkeypatch.delenv(diagnose.ENV, raising=False)
    made = []

    def factory(off: str = "", filled: bool = False) -> tuple[MainWindow, FakeCore]:
        if off:
            monkeypatch.setenv(diagnose.ENV, off)
        else:
            monkeypatch.delenv(diagnose.ENV, raising=False)
        core = FakeCore()
        if filled:
            core.backend = filled_backend()
            core.runner = DirectRunner()
        w = MainWindow(core)
        made.append(w)
        return w, core

    yield factory
    for w in made:
        w.close()
        w.deleteLater()
    app.processEvents()


def count_restores(w: MainWindow) -> list[bytes]:
    """Ersetzt `restoreState` am Fenster durch eine zählende Hülle (Python ruft über das Attribut)."""
    calls: list[bytes] = []
    original = w.restoreState

    def counting(state, version=0):
        calls.append(bytes(state))
        return original(state, version)

    w.restoreState = counting
    return calls


def saved_values(app, *, maximized: bool, tabbed: bool = True) -> dict[str, str]:
    """Gespeicherte Werte wie `layout_values`: Anordnung mit Reitern, Fensterlage (maximiert oder nicht)."""
    src = MainWindow(FakeCore())
    try:
        if tabbed:
            src.tabifyDockWidget(src.docks[0], src.docks[1])
        if maximized:
            # saveGeometry merkt «maximiert» auch am verborgenen Fenster
            src.setWindowState(Qt.WindowState.WindowMaximized)
        app.processEvents()
        values = src.layout_values()
    finally:
        src.deleteLater()
        app.processEvents()
    return values


def wait(app, seconds: float) -> None:
    run_loop(app, int(seconds * 1000))


# --- Schalter ------------------------------------------------------------------------------------
def test_f01_p06d5_each_fix_has_its_switch(monkeypatch):
    assert diagnose.FIXES == ("fix_state_once", "fix_restore_after_show", "fix_list_after_restore")
    monkeypatch.delenv(diagnose.ENV, raising=False)
    assert all(diagnose.fix(name) for name in diagnose.FIXES)  # standardmässig ein
    for name in diagnose.FIXES:
        assert name in diagnose.SWITCHES
        monkeypatch.setenv(diagnose.ENV, name)
        assert not diagnose.fix(name)
        assert all(diagnose.fix(other) for other in diagnose.FIXES if other != name)
    # alte Schalter berühren die Massnahmen nicht
    monkeypatch.setenv(diagnose.ENV, "window_changes")
    assert all(diagnose.fix(name) for name in diagnose.FIXES)


# --- fix_state_once ------------------------------------------------------------------------------
@pytest.mark.parametrize("off", ["", "fix_state_once"])
def test_f01_p06d5_state_is_not_restored_twice_with_the_same_bytes(app, windows, off):
    values = saved_values(app, maximized=False)
    w, core = windows(off)
    calls = count_restores(w)
    w.apply_settings(values)  # vor dem Anzeigen (main.py)
    w.show()
    wait(app, SETTLE)
    core.settings_loaded.emit(json.dumps(values))  # nach dem Verbinden, Fenster sichtbar
    app.processEvents()
    expected = 2 if off else 1  # mit Schalter: Stand P06d4 (zweimal)
    assert len(calls) == expected
    assert w.tabifiedDockWidgets(w.docks[0]) == [w.docks[1]]
    other = saved_values(app, maximized=False, tabbed=False)  # andere Bytes: wieder angewendet
    core.settings_loaded.emit(json.dumps(other))
    app.processEvents()
    assert len(calls) == expected + 1 and not w.tabifiedDockWidgets(w.docks[0])


# --- fix_restore_after_show ----------------------------------------------------------------------
@pytest.mark.parametrize("off", ["", "fix_restore_after_show"])
def test_f01_p06d5_maximized_state_is_restored_after_show(app, windows, off):
    values = saved_values(app, maximized=True)
    w, core = windows(off)
    calls = count_restores(w)
    w.apply_settings(values)
    assert w.windowState() & Qt.WindowState.WindowMaximized
    if off:  # Stand P06d4: am verborgenen Fenster
        assert len(calls) == 1 and w.layout_restored  # nichts vorgemerkt
        return
    assert calls == [] and not w.layout_restored  # kein restoreState vor show()
    assert w.layout_values()[KEY_STATE] == values[KEY_STATE]  # vorgemerkt, nicht verloren
    w.show()
    app.processEvents()
    assert calls == []  # nicht im Ereignis von show(), sondern über den Zeitgeber
    wait(app, SETTLE)
    assert len(calls) == 1 and w.isVisible() and w.layout_restored
    assert w.tabifiedDockWidgets(w.docks[0]) == [w.docks[1]]
    core.settings_loaded.emit(json.dumps(values))  # dieselben Bytes nach dem Verbinden: nichts
    app.processEvents()
    assert len(calls) == 1


def test_f01_p06d5_normal_state_is_still_restored_before_show(app, windows):
    values = saved_values(app, maximized=False)
    w, _ = windows()
    calls = count_restores(w)
    w.apply_settings(values)
    assert len(calls) == 1 and not w.isVisible()
    assert w.tabifiedDockWidgets(w.docks[0]) == [w.docks[1]]


def test_f01_p06d5_restore_waits_for_the_final_size(app, windows, monkeypatch):
    """Maximiert: Solange das Fenster nicht seine Endgrösse hat, wartet der Zeitgeber (höchstens RESTORE_MAX_MS)."""
    values = saved_values(app, maximized=True)
    w, _ = windows()
    calls = count_restores(w)
    monkeypatch.setattr(w, "_has_final_size", lambda: False)
    w.apply_settings(values)
    w.show()
    app.processEvents()
    # Offscreen meldet eine Grösse; hier: Fenstersystem noch nicht fertig
    w._resized_since_show = False
    wait(app, SETTLE)
    assert calls == [] and not w.layout_restored
    w._restore_deadline = time.monotonic()  # Frist abgelaufen: trotzdem anwenden
    wait(app, SETTLE)
    assert len(calls) == 1 and w.layout_restored


def test_f01_p06d5_module_switch_before_restore_keeps_the_saved_state(app, windows):
    values = saved_values(app, maximized=True)
    w, _ = windows()
    w.apply_settings(values)
    w.show()
    app.processEvents()
    w.set_module(mw.MODULE_BOT)  # bevor die vorgemerkte Anordnung angewendet ist
    assert w.layout_values()[KEY_STATE] == values[KEY_STATE]
    wait(app, SETTLE)
    assert w.layout_restored
    w.set_module(mw.MODULE_OVERLAYS)
    app.processEvents()
    assert w.tabifiedDockWidgets(w.docks[0]) == [w.docks[1]]


# --- fix_list_after_restore ----------------------------------------------------------------------
@pytest.mark.parametrize("off", ["", "fix_list_after_restore"])
def test_f01_p06d5_list_page_changes_only_after_layout_restored(app, windows, off):
    w, core = windows(off, filled=True)
    ov, src = w.overlays_panel.stack, w.sources_panel.stack
    assert not w.layout_restored
    core.connected.emit()  # erste Datenantwort vor dem Anzeigen und vor dem Wiederherstellen
    assert w.overlays_panel.list.count() == 3 and w.sources_panel.list.count() == 6
    if off:  # Stand P06d4: Seite sofort
        assert ov.currentWidget() is ov.listing and src.currentWidget() is src.listing
        return
    assert ov.currentWidget() is ov.hint and src.currentWidget() is src.hint
    w.show()
    app.processEvents()
    assert ov.currentWidget() is ov.hint  # noch nicht im Ereignis von show()
    wait(app, SETTLE)
    assert w.layout_restored
    assert ov.currentWidget() is ov.listing and src.currentWidget() is src.listing
    w.model.overlays = []  # danach wie bisher sofort
    w.overlays_panel.list.clear()
    ov.sync()
    assert ov.currentWidget() is ov.hint


def test_f01_p06d5_layout_restored_at_once_when_nothing_is_pending(app, windows):
    """Nicht maximiert (oder nichts gespeichert): `layout_restored` gleich nach `apply_settings`, ohne zu warten."""
    w, core = windows(filled=True)
    w.apply_settings(saved_values(app, maximized=False))
    assert w.layout_restored
    core.connected.emit()
    app.processEvents()
    ov = w.overlays_panel.stack
    assert ov.currentWidget() is ov.listing
    w2, _ = windows()
    w2.apply_settings({})
    assert w2.layout_restored


def test_f01_p06d5_maximized_list_waits_for_the_pending_state(app, windows):
    w, core = windows(filled=True)
    w.apply_settings(saved_values(app, maximized=True))
    assert not w.layout_restored  # Anordnung vorgemerkt
    w.show()
    app.processEvents()
    core.connected.emit()
    core.settings_loaded.emit("{}")  # zweites apply_settings ohne Werte: Vormerkung bleibt
    app.processEvents()
    ov = w.overlays_panel.stack
    assert not w.layout_restored and ov.currentWidget() is ov.hint
    wait(app, SETTLE)
    assert w.layout_restored and ov.currentWidget() is ov.listing
    assert w.tabifiedDockWidgets(w.docks[0]) == [w.docks[1]]


# --- Speichern und Wiederherstellen unverändert (beide Module) -----------------------------------
@pytest.mark.parametrize("off", ["", ALL_FIXES])
@pytest.mark.parametrize("module", [mw.MODULE_OVERLAYS, mw.MODULE_BOT])
@pytest.mark.parametrize("maximized", [False, True])
def test_f01_p06d5_save_and_restore_in_both_modules(app, windows, off, module, maximized):
    w, core = windows(off)
    w.show()
    wait(app, SETTLE)
    core.settings_loaded.emit("{}")
    w.tabifyDockWidget(w.docks[2], w.docks[3])
    w.docks[1].hide()
    if maximized:
        w.showMaximized()
    app.processEvents()
    w.set_module(module)
    app.processEvents()
    saved = w.layout_values()
    w2, core2 = windows(off)
    w2.apply_settings(saved)  # vor dem Anzeigen
    w2.show()
    wait(app, SETTLE)
    core2.settings_loaded.emit(json.dumps(saved))  # nach dem Verbinden
    wait(app, SETTLE)
    assert bool(w2.windowState() & Qt.WindowState.WindowMaximized) == maximized
    assert w2.layout_restored
    assert w2.tabifiedDockWidgets(w2.docks[2]) == [w2.docks[3]]
    assert w2.docks[1].isHidden() and not w2.docks[0].isHidden()
    w2.set_module(mw.MODULE_BOT)
    app.processEvents()
    assert all(d.isHidden() for d in w2.docks) and all(not d.isHidden() for d in w2.bot_docks)
    w2.set_module(mw.MODULE_OVERLAYS)
    app.processEvents()
    assert w2.tabifiedDockWidgets(w2.docks[2]) == [w2.docks[3]]
    assert w2.docks[1].isHidden() and not w2.docks[0].isHidden()
    again = w2.layout_values()
    assert all(again[k].startswith(mw.LAYOUT_TAG) for k in (KEY_GEOMETRY, KEY_STATE))
    assert w2.restoreState(mw._decode(again[KEY_STATE]), STATE_VERSION)


# --- Startprüfung mit echtem Fenstersystem (Xvfb und openbox) ------------------------------------
def test_f01_p06d5_laptop_variants_parse():
    import start_pruefung as sp

    v = sp.parse_variant("daten_laptop")
    assert v.maximized and v.wm and v.geometry == (1918, 1011) and v.position == (1, 69)
    assert v.overlays == 2 and v.source_count == 3 and v.docks == "standard"
    assert sp.parse_variant("daten_laptop_breit").docks == "breit"
    assert sp.parse_variant("daten_laptop_untereinander").docks == "untereinander"
    off = sp.parse_variant(f"daten_laptop,aus={ALL_FIXES}").off
    assert off == ",".join(diagnose.FIXES)


@NEEDS_XVFB
@pytest.mark.skipif(shutil.which("openbox") is None, reason="openbox fehlt (maximieren)")
@pytest.mark.parametrize("variant", ["daten_laptop", "daten_laptop_breit"])
def test_f01_p06d5_laptop_layout_starts_with_the_fixes(variant):
    r = _start_check(["--laeufe", "3", "--variante", variant], _xvfb_env(), 3 * 150)
    assert r.returncode == 0, r.stdout[-3000:]
    assert "3 von 3 Läufen mit Exit-Code 0" in r.stdout
    assert "maximiert" in r.stdout and "0 Reiterpaare" in r.stdout
