"""P06d3 (F-01, F-74 bis F-78): Start mit gefüllten Daten – Startprüfung mit Daten, Erfassen eines Absturzes,
Diagnose-Schalter für die übrigen Teile von P06d, Oberfläche mit gefüllter Liste und Quellen."""

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

pytest.importorskip(
    "PyQt6.QtWidgets",
    exc_type=ImportError,
    reason="PyQt6 ist nicht installierbar oder lädt nicht (Systembibliotheken fehlen?)",
)

from PyQt6.QtGui import QImage
from PyQt6.QtWidgets import QApplication, QListWidget

from donstv_studio.ui import diagnose, diagnose_p08, theme
from donstv_studio.ui import geometry as geo
from donstv_studio.ui.backend import DirectRunner
from donstv_studio.ui.editor_model import source_label
from donstv_studio.ui.main_window import MainWindow
from fake_backend import FakeBackend
from fake_core import FakeCore

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import start_pruefung as sp

NEEDS_XVFB = pytest.mark.skipif(shutil.which("Xvfb") is None, reason="Xvfb nicht installiert")
P06D3_SWITCHES = (
    "editor_view_changes",
    "editor_model_changes",
    "geometry_changes",
    "theme_changes",
    "indicators_changes",
    "docks_changes",
    "window_changes",
)


def filled_backend() -> FakeBackend:
    """3 Overlays, das erste mit 6 Quellen wie `start_pruefung.seed_data` (Text und Bild, ein Bild 6:1)."""
    b = FakeBackend()
    first = b.add("Overlay 1")
    b.add("Overlay 2")
    b.add("Overlay 3")
    media = [b.upload_media(f"/tmp/{n}.png") for n in ("banner", "quadrat", "hoch")]
    oid = first["id"]
    b.add_source(oid, "text", x=100, y=900, width=800, height=100, props={"text": "Willkommen"})
    b.add_source(
        oid, "text", x=1200, y=50, width=600, height=80, props={"text": "Zwei"}, name="Titel"
    )
    b.add_source(
        oid, "text", x=50, y=50, width=400, height=60, props={"text": "Aus"}, visible=False
    )
    for i, (m, (w, h)) in enumerate(zip(media, ((1200, 200), (256, 256), (300, 600)), strict=True)):
        b.add_source(oid, "image", x=100 + 300 * i, y=300, width=w, height=h,
                     props={"media_id": m["id"]}, rotation=15.0 if i == 2 else 0.0)  # fmt: skip
    b.calls.clear()
    return b


def run_loop(app, ms: int) -> None:
    end = time.monotonic() + ms / 1000
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def start_filled(app, monkeypatch=None, off: str = "") -> tuple[MainWindow, FakeCore]:
    if monkeypatch is not None:
        if off:
            monkeypatch.setenv(diagnose.ENV, off)
        else:
            monkeypatch.delenv(diagnose.ENV, raising=False)
    core = FakeCore()
    core.backend = filled_backend()
    core.runner = DirectRunner()
    w = MainWindow(core)
    w.resize(1300, 720)
    w.show()
    app.processEvents()
    core.connected.emit()  # wie nach dem Verbinden: erste Datenantwort, Seite «Hinweis» → «Liste»
    core.settings_loaded.emit("{}")
    return w, core


def close(app, w) -> None:
    w.close()
    w.deleteLater()
    app.processEvents()


# --- Oberfläche mit gefüllter Liste und Quellen (Aufgabe 5) --------------------------------------
def test_f01_filled_ui_runs_the_event_loop(app, monkeypatch):
    w, _ = start_filled(app, monkeypatch)
    try:
        run_loop(app, 500)
        ov, src = w.overlays_panel, w.sources_panel
        assert ov.list.count() == 3 and ov.stack.currentWidget() is ov.list
        assert src.list.count() == 6 and src.stack.currentWidget() is src.list
        assert w.model.current_id == w.model.overlays[0]["id"]
        assert "Titel" in [src.list.item(i).text() for i in range(src.list.count())]
        w.model.select_source(w.model.sources()[1]["id"])
        run_loop(app, 200)
        assert w.properties_panel.name.text() == "Titel"
    finally:
        close(app, w)


def test_f01_filled_ui_with_all_diagnose_switches(app, monkeypatch):
    w, _ = start_filled(app, monkeypatch, ",".join(diagnose.SWITCHES))
    try:
        run_loop(app, 500)
        assert w.overlays_panel.list.count() == 3 and w.sources_panel.list.count() == 6
    finally:
        close(app, w)
        monkeypatch.delenv(diagnose.ENV)
        w2 = MainWindow(FakeCore())  # Stylesheet von P06d zurück für die anderen Tests
        w2.set_theme("light")
        w2.set_theme("dark")
        close(app, w2)
    assert "image: url(" in QApplication.instance().styleSheet()


# --- Diagnose-Schalter P06d3 (Aufgabe 3) ---------------------------------------------------------
def test_f01_p06d3_switches_known_and_imply_single_switches(monkeypatch):
    assert set(P06D3_SWITCHES) <= set(diagnose.SWITCHES)
    for name, implied in diagnose.IMPLIES.items():
        monkeypatch.setenv(diagnose.ENV, name)
        assert diagnose.switched_off() == {name, *implied}
    monkeypatch.setenv(diagnose.ENV, "theme_changes, unbekannt")
    assert diagnose.switched_off() == {"theme_changes", "qss_images"}


def test_f01_switch_theme_changes_gives_the_p08_stylesheet(monkeypatch):
    assert "control_border" not in diagnose_p08.stylesheet("dark")
    monkeypatch.setenv(diagnose.ENV, "theme_changes")
    sheet = theme.stylesheet("dark", {"check": "/x.png"})
    assert sheet == diagnose_p08.stylesheet("dark")
    assert "::indicator" not in sheet and "up-button" not in sheet and "image: url(" not in sheet
    monkeypatch.delenv(diagnose.ENV)
    assert "::indicator" in theme.stylesheet("dark")


def test_f01_switch_editor_model_changes_gives_p08_labels(monkeypatch):
    s = {"kind": "text", "name": "Titel", "props": {"text": "Hallo Welt"}}
    assert source_label(s) == "Titel"
    monkeypatch.setenv(diagnose.ENV, "editor_model_changes")
    assert source_label(s) == "Text: Hallo Welt"
    assert (
        source_label({"kind": "image", "props": {"media_id": "m"}}, {"m": "a.png"}) == "Bild: a.png"
    )


def test_f01_switch_geometry_changes_gives_p08_sizes(monkeypatch):
    start = geo.Box(0, 0, 400, 100)
    assert geo.fit_inside(4000, 1000, 1920, 1080) == (1920, 480)
    keep, _ = geo.resize_box(start, "se", 100, 0, keep_ratio=True)
    assert (keep.w, keep.h) != (500, 100)
    monkeypatch.setenv(diagnose.ENV, "geometry_changes")
    assert geo.fit_inside(4000, 1000, 1920, 1080) == (1920, 1000)
    free, _ = geo.resize_box(start, "se", 100, 0, keep_ratio=True)
    assert (free.w, free.h) == (500, 100)


def test_f01_switches_docks_view_window_restore_p08(app, monkeypatch):
    normal, _ = start_filled(app, monkeypatch)
    receivers = normal.model.receivers(normal.model.sources_changed)
    assert normal.control_panel.grid_size.minimumWidth() > 0
    close(app, normal)
    w, core = start_filled(app, monkeypatch, "docks_changes,editor_view_changes,window_changes")
    try:
        run_loop(app, 200)
        src = w.sources_panel
        assert src.list.editTriggers() == QListWidget().editTriggers()  # Auslöser von Qt wie P08
        assert w.control_panel.grid_size.minimumWidth() == 0  # keine Mindestbreite
        assert not w.properties_panel.name.isVisibleTo(w)  # schliesst «rename» ein
        # Eigenschaften ohne Verbindung zu sources_changed (eine Verbindung weniger)
        assert w.model.receivers(w.model.sources_changed) == receivers - 1
        assert w.editor.pointer_badge is None
        assert w.pointer_label.text() == "X: –   Y: –"  # Zeigerlage in der Statuszeile wie P08
        w.editor.pointer_changed.emit(True, 12, 34)
        assert w.pointer_label.text() == "X: 12   Y: 34"
        sheets = []
        app_set = QApplication.setStyleSheet
        monkeypatch.setattr(
            QApplication, "setStyleSheet", lambda self, s: (sheets.append(1), app_set(self, s))
        )
        w.set_theme(w.theme)
        w._apply_theme_style()
        assert sheets  # window_changes: Stylesheet wird wie in P08 immer gesetzt
    finally:
        close(app, w)


# --- Startprüfung: Varianten, Daten, Absturz (Aufgaben 1 und 2) ----------------------------------
def test_f01_start_check_variants_parse():
    v = sp.parse_variant("daten")
    assert (v.geometry, v.overlays, v.sources, v.off, v.copy) == (
        sp.NORMAL_SIZE,
        3,
        True,
        "",
        False,
    )
    v = sp.parse_variant("daten_schmal,aus=theme_changes,docks_changes")
    assert v.geometry == sp.NARROW_SIZE and v.off == "theme_changes,docks_changes"
    assert sp.parse_variant("aus=rename").off == "rename"
    assert sp.parse_variant("daten_overlays").sources is False
    assert sp.parse_variant("daten_leer").overlays == 0
    assert sp.parse_variant("kopie").copy is True
    assert sp.parse_variant("daten_reiter").docks == "reiter"
    for bad in ("unbekannt", "daten,aus=", "daten,aus=gibtsnicht"):
        with pytest.raises(SystemExit):
            sp.parse_variant(bad)


def test_f01_start_check_png_is_valid():
    img = QImage.fromData(sp.png_bytes(1200, 200, (200, 40, 40)))
    assert (img.width(), img.height()) == (1200, 200)
    assert img.pixelColor(10, 10).red() == 200


def test_f01_start_check_extracts_full_faulthandler_output():
    err = "vorher\nFatal Python error: Segmentation fault\n\nThread 1\n" + "\n".join(
        f'  File "x.py", line {i}' for i in range(40)
    )
    part = sp.faulthandler_part(err)
    assert part.startswith("Fatal Python error") and part.count("File") == 40
    assert sp.faulthandler_part("nichts") == ""


def _xvfb_env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k not in ("DISPLAY", "QT_QPA_PLATFORM")}
    env.pop("DONSTV_OFF", None)
    return env


def _start_check(args: list[str], env: dict[str, str], timeout: int) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ROOT / "tools" / "start_pruefung.py"), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
        cwd=str(ROOT),
        check=False,
    )


@NEEDS_XVFB
@pytest.mark.parametrize("variant", ["daten", "daten_schmal"])
def test_f01_real_ui_starts_with_data_under_xvfb(variant):
    r = _start_check(["--laeufe", "5", "--variante", variant], _xvfb_env(), 5 * 150)
    out = r.stdout
    assert "5 von 5 Läufen mit Exit-Code 0" in out, out[-4000:] + r.stderr[-2000:]
    assert out.count("[Daten] 3 Overlays angelegt, 6 Quellen im ersten") == 5
    assert out.count("gespeichert: True") == 5
    assert r.returncode == 0


@NEEDS_XVFB
def test_f01_crash_is_recorded_with_full_traceback(tmp_path):
    """Ein künstlicher Speicherzugriffsfehler im Lauf der Oberfläche: Exit-Code, ganze Aufrufliste, Datei."""
    site = tmp_path / "site"
    site.mkdir()
    (site / "sitecustomize.py").write_text(
        "import sys, threading\n"
        "if '--lauf' in sys.argv:\n"
        "    import faulthandler\n"
        "    t = threading.Timer(2.0, faulthandler._sigsegv); t.daemon = True; t.start()\n"
    )
    env = _xvfb_env()
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(site), env.get("PYTHONPATH")]))
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    r = _start_check(
        ["--laeufe", "1", "--variante", "daten_overlays", "--ausgabe", str(out_dir)], env, 300
    )
    assert "Exit-Code -11" in r.stdout or "Exit-Code 139" in r.stdout, r.stdout[-3000:]
    assert "vollständige Aufrufliste von faulthandler:" in r.stdout
    assert "   # Fatal Python error: Segmentation fault" in r.stdout
    assert "ui/main.py" in r.stdout  # Hauptthread in app.exec(), nicht nur 15 Zeilen
    files = list(out_dir.glob("startpruefung-absturz-daten_overlays-1.txt"))
    assert files, r.stdout[-2000:]
    text = files[0].read_text(encoding="utf-8")
    assert "--- stderr vollständig ---" in text and "Fatal Python error" in text
    assert "--- C++-Aufrufliste ---" in text
    assert r.returncode == 1


@NEEDS_XVFB
def test_f01_copy_of_user_data_is_used_and_original_untouched(tmp_path):
    """Variante `kopie`: Datenbank und Medien des «Nutzers» (hier ein eigener Ordner) werden kopiert, nicht verändert."""
    user = tmp_path / "user"
    env = sp.run_env(user)
    port, overlay_port = sp.free_port(), sp.free_port()
    core = sp.start_core(env, port, overlay_port)
    try:
        sp.seed_data(env, port, 2, True, tmp_path)
    finally:
        sp.stop_core(core)
    db = next(user.glob("data/*/donstv.db"))
    before = (db.stat().st_mtime_ns, db.stat().st_size)
    run = _xvfb_env()
    run.update({k: env[k] for k in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME")})
    r = _start_check(["--laeufe", "1", "--variante", "kopie,aus=theme_changes"], run, 300)
    assert "1 von 1 Läufen mit Exit-Code 0" in r.stdout, r.stdout[-3000:] + r.stderr[-1000:]
    assert "Kopie der Datenbank" in r.stdout and "3 Mediendateien" in r.stdout
    assert "DONSTV_OFF='theme_changes'" in r.stdout
    assert (db.stat().st_mtime_ns, db.stat().st_size) == before


def test_f01_start_check_core_has_no_real_twitch_or_keyring(tmp_path):
    env = sp.run_env(tmp_path)
    assert env["DONSTV_TWITCH_FAKE"] == "1"
    assert env["PYTHON_KEYRING_BACKEND"] == "keyring.backends.null.Keyring"
