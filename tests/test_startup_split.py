"""P06d4 (F-01, F-78): `window_changes` in drei Schalter aufgeteilt, Kopie der echten Daten mit einer Änderung,
Beschreibung der gespeicherten Lage ohne Geheimnisse, Absturzdateien begrenzt."""

import hashlib
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip(
    "PyQt6.QtWidgets",
    exc_type=ImportError,
    reason="PyQt6 ist nicht installierbar oder lädt nicht (Systembibliotheken fehlen?)",
)

from PyQt6.QtCore import QRect, Qt
from PyQt6.QtWidgets import QApplication, QDockWidget, QLabel, QMainWindow

from donstv_studio.core.store import Store
from donstv_studio.ui import diagnose
from donstv_studio.ui import main_window as mw
from test_startup_data import NEEDS_XVFB, _start_check, _xvfb_env, close, run_loop, start_filled

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import lage_beschreiben as lb
import start_pruefung as sp

WINDOW_SWITCHES = ("window_stylesheet", "window_minwidth", "window_geometry")


# --- Aufgabe 1: drei Schalter statt einem -------------------------------------------------------
def test_f01_p06d4_window_changes_is_short_for_the_three_switches(monkeypatch):
    assert set(WINDOW_SWITCHES) <= set(diagnose.SWITCHES)
    assert diagnose.IMPLIES["window_changes"] == WINDOW_SWITCHES
    monkeypatch.setenv(diagnose.ENV, "window_changes")
    assert diagnose.switched_off() == {"window_changes", *WINDOW_SWITCHES}
    for name in WINDOW_SWITCHES:
        monkeypatch.setenv(diagnose.ENV, name)
        assert diagnose.switched_off() == {name}  # jeder für sich, ohne die anderen


def _probe(app, monkeypatch, off: str) -> dict:
    """Startet die gefüllte Oberfläche mit `off` und misst die drei Teile von `main_window.py` einzeln."""
    w, _ = start_filled(app, monkeypatch, off)
    try:
        run_loop(app, 200)
        result = {}
        # Stylesheet: dasselbe Design noch einmal anwenden
        sheets = []
        app_set = QApplication.setStyleSheet
        with monkeypatch.context() as m:  # stellt beim Verlassen den Zustand der Klasse richtig her
            m.setattr(
                QApplication, "setStyleSheet", lambda self, s: (sheets.append(1), app_set(self, s))
            )
            w._apply_theme_style()
        result["stylesheet_set"] = bool(sheets)
        # Mindestbreite: am sichtbaren Fenster sofort oder über den Zeitgeber
        calls = []
        update = w._update_minimum_width
        monkeypatch.setattr(w, "_update_minimum_width", lambda: (calls.append(1), update()))
        w._min_width_timer.stop()
        w._apply_theme_style()
        result["minwidth_now"] = bool(calls)
        result["minwidth_timer"] = w._min_width_timer.isActive()
        run_loop(app, 50)
        # Fensterlage: dieselbe Lage zweimal anwenden
        restored, calls[:] = [], []
        orig = w.restoreGeometry
        monkeypatch.setattr(w, "restoreGeometry", lambda g: (restored.append(1), orig(g))[1])
        geometry = w.saveGeometry()
        w._applied_geometry = None
        w._restore_geometry(geometry)
        w._restore_geometry(geometry)
        result["geometry_applied"] = len(restored)
        result["minwidth_before_geometry"] = bool(calls)
        return result
    finally:
        close(app, w)


P06D4_NORMAL = {
    "stylesheet_set": False,
    "minwidth_now": False,
    "minwidth_timer": True,
    "geometry_applied": 1,
    "minwidth_before_geometry": True,
}
P06D4_EFFECT = {
    "window_stylesheet": {"stylesheet_set": True},
    "window_minwidth": {"minwidth_now": True, "minwidth_timer": False},
    "window_geometry": {"geometry_applied": 2, "minwidth_before_geometry": False},
}


@pytest.mark.parametrize("off", ["", *WINDOW_SWITCHES, "window_changes"])
def test_f01_p06d4_each_window_switch_restores_only_its_part(app, monkeypatch, off):
    """Jeder Schalter ändert genau seinen Teil (Stand P08); `window_changes` alle drei."""
    expected = dict(P06D4_NORMAL)
    for name in WINDOW_SWITCHES if off == "window_changes" else (off,) if off else ():
        expected.update(P06D4_EFFECT[name])
    assert _probe(app, monkeypatch, off) == expected


# --- Aufgabe 2: Kopie der echten Daten mit einer Änderung -----------------------------------------
def test_f01_p06d4_copy_variants_parse():
    expected = {
        "kopie": (),
        "kopie_ohne_lage": ("geometry", "state"),
        "kopie_ohne_geometrie": ("geometry",),
        "kopie_ohne_anordnung": ("state",),
        "kopie_ohne_quellen": ("sources",),
    }
    for name, strip in expected.items():
        v = sp.parse_variant(name)
        assert (v.copy, v.strip, v.geometry, v.overlays) == (True, strip, None, 0)
        assert sp.parse_variant(f"{name},aus=window_geometry").off == "window_geometry"
    v = sp.parse_variant("kopie,aus=window_stylesheet window_minwidth")
    assert v.off == "window_stylesheet,window_minwidth" and v.copy
    m = sp.parse_variant("daten_maximiert")
    assert m.maximized and m.geometry == sp.NORMAL_SIZE and not m.copy
    assert not sp.parse_variant("daten").maximized


def _user_data(base: Path) -> Path:
    """Datenbank eines «Nutzers» mit Fensterlage, Anordnung, Theme, 2 Overlays und 3 Quellen."""
    db = sp.copy_db_file(sp.run_env(base))  # Pfad wie beim Kern (XDG_DATA_HOME unter `base`)
    store = Store(db)
    store.set_setting(mw.KEY_GEOMETRY, "v3:AAAA")
    store.set_setting(mw.KEY_STATE, "v3:BBBB")
    store.set_setting(mw.KEY_THEME, "light")
    store.close()
    con = sqlite3.connect(db)
    for i in (1, 2):
        con.execute(
            "INSERT INTO overlays VALUES (?, ?, 1920, 1080, 'browser', ?)",
            (f"o{i}", f"Geheim{i}", f"t{i}"),
        )
    for i in range(3):
        con.execute(
            "INSERT INTO sources (id, overlay_id, kind, x, y, width, height, rotation, z, visible, props) "
            "VALUES (?, 'o1', 'text', 0, 0, 10, 10, 0, ?, 1, '{}')",
            (f"s{i}", i),
        )
    con.commit()
    con.close()
    return db


def _fingerprint(db: Path) -> str:
    """Prüfsumme der Datenbankdatei. Nur lesendes Öffnen einer WAL-Datenbank legt bei SQLite die Hilfsdateien
    `-wal` (leer) und `-shm` an, falls sie fehlen (beobachtet); die Daten bleiben unverändert."""
    wal = db.with_name(db.name + "-wal")
    assert not wal.exists() or wal.stat().st_size == 0  # nichts geschrieben
    return hashlib.sha256(db.read_bytes()).hexdigest()


@pytest.mark.parametrize(
    ("name", "gone_keys", "sources"),
    [
        ("kopie", (), 3),
        ("kopie_ohne_lage", (mw.KEY_GEOMETRY, mw.KEY_STATE), 3),
        ("kopie_ohne_geometrie", (mw.KEY_GEOMETRY,), 3),
        ("kopie_ohne_anordnung", (mw.KEY_STATE,), 3),
        ("kopie_ohne_quellen", (), 0),
    ],
)
def test_f01_p06d4_copy_changes_only_the_copy(tmp_path, monkeypatch, name, gone_keys, sources):
    user = tmp_path / "user"
    db = _user_data(user)
    before = _fingerprint(db)
    for k, v in sp.run_env(user).items():
        if k.startswith("XDG_"):
            monkeypatch.setenv(k, v)  # Steuerprozess = Umgebung des Nutzers
    env = sp.run_env(tmp_path / "pruefung")
    text = sp.copy_user_data(env, sp.parse_variant(name).strip)
    assert "Kopie der Datenbank" in text
    copy = sp.copy_db_file(env)
    con = sqlite3.connect(copy)
    keys = {k for (k,) in con.execute("SELECT key FROM settings")}
    n_sources = con.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
    n_overlays = con.execute("SELECT COUNT(*) FROM overlays").fetchone()[0]
    con.close()
    all_keys = {mw.KEY_GEOMETRY, mw.KEY_STATE, mw.KEY_THEME}
    assert keys & all_keys == all_keys - set(gone_keys)
    assert (n_overlays, n_sources) == (2, sources)  # Overlays bleiben immer
    assert _fingerprint(db) == before  # das Original ist unverändert
    con = sqlite3.connect(f"{db.as_uri()}?mode=ro", uri=True)
    assert con.execute("SELECT COUNT(*) FROM sources").fetchone()[0] == 3
    assert len(con.execute("SELECT key FROM settings").fetchall()) == 3
    con.close()


# --- Aufgabe 3: Lage beschreiben ------------------------------------------------------------------
def _window_with_docks() -> QMainWindow:
    win = QMainWindow()
    win.setDockNestingEnabled(True)
    win.setCentralWidget(QLabel())
    docks = []
    for name in lb.DOCK_NAMES:
        d = QDockWidget(name, win)
        d.setObjectName(name)
        d.setWidget(QLabel())
        win.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, d)
        docks.append(d)
    return win, docks


def test_f01_p06d4_geometry_is_read_from_the_qt_format(app):
    win, _ = _window_with_docks()
    win.setGeometry(QRect(40, 60, 1100, 650))
    data = bytes(win.saveGeometry())
    lines = lb.describe_geometry(data)
    assert lines[0] == "Qt-Format Version 3.0"
    assert "Fenster (geometry): x 40, y 60, 1100 × 650 px" in lines
    assert "normal (normalGeometry): x 40, y 60, 1100 × 650 px" in lines
    assert "maximiert: nein, Vollbild: nein" in lines
    screen_w = QApplication.primaryScreen().geometry().width()
    assert f"Bildschirmbreite beim Speichern: {screen_w} px" in lines
    assert "Bildschirmnummer: 0" in lines
    assert lb.describe_geometry(b"\x00\x01")[0].startswith("nicht lesbar")
    assert lb.describe_geometry(b"\x00" * 40)[0].startswith("nicht lesbar (Kennzahl")
    win.deleteLater()


def test_f01_p06d4_state_is_described_by_qt(app):
    assert mw.STATE_VERSION == 3  # wie in lage_beschreiben.describe (Vorgabe)
    win, docks = _window_with_docks()
    win.tabifyDockWidget(docks[0], docks[1])
    docks[3].setFloating(True)
    docks[5].hide()
    data = bytes(win.saveState(mw.STATE_VERSION))
    lines = lb.describe_state(data, mw.STATE_VERSION)
    assert lines[0] == "Kennzeichen 0xFF (passt), Version 3"
    assert "restoreState mit Version 3: angenommen" in lines
    assert "Reiterpaare: 1 (Gruppen: dock_overlays + dock_sources)" in lines
    assert "schwebende Docks: 1 (dock_control)" in lines
    assert any(line.startswith("sichtbare Docks: 5 ") for line in lines)
    assert (
        lb.describe_state(data, 2)[-1]
        == "restoreState mit Version 2: abgelehnt (wird nicht angewandt)"
    )
    win.deleteLater()


def test_f01_p06d4_description_has_no_names_or_secrets(tmp_path, app):
    db = _user_data(tmp_path / "user")
    win, _ = _window_with_docks()
    win.setGeometry(QRect(10, 20, 900, 500))
    con = sqlite3.connect(db)
    con.execute(
        "UPDATE settings SET value = ? WHERE key = ?",
        (mw._encode(win.saveGeometry()), mw.KEY_GEOMETRY),
    )
    con.execute(
        "UPDATE settings SET value = ? WHERE key = ?", (mw._encode(win.saveState(3)), mw.KEY_STATE)
    )
    con.execute("INSERT INTO settings VALUES ('twitch.token', 'GEHEIMESTOKEN')")
    con.commit()
    con.close()
    before = _fingerprint(db)
    out = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "lage_beschreiben.py"), "--db", str(db)],
        capture_output=True, text=True, timeout=120, check=False,
    )  # fmt: skip
    text = out.stdout
    assert out.returncode == 0, out.stderr
    assert "Theme: light" in text and "Overlays: 2, Quellen: 3" in text
    assert "Fenster (geometry): x 10, y 20, 900 × 500 px" in text
    assert "restoreState mit Version 3: angenommen" in text
    assert "Geheim" not in text and "GEHEIMESTOKEN" not in text and "token" not in text.lower()
    assert _fingerprint(db) == before
    assert lb.decode("ohne Marke")[0] is None and "ohne Marke v3:" in lb.decode("ohne Marke")[1]
    assert lb.decode(None) == (None, "nicht gespeichert")
    win.deleteLater()


# --- Aufgaben 4 und 5: Absturzdateien und C++-Aufrufliste ------------------------------------------
def test_f01_p06d4_cpp_frames_of_the_crashed_thread():
    bt = (
        "Core-Datei core:\n[New LWP 12]\nProgram terminated with signal SIGSEGV, Segmentation fault.\n"
        "#0  0x9 in __pthread_kill_implementation ()\n[Current thread is 2 (Thread 0x7f (LWP 12))]\n"
        "From To Syms Read Shared Object Library\n\n"
        "Thread 3 (Thread 0x8f):\n#0  0x3 in poll ()\n\n"
        "Thread 2 (Thread 0x7f (LWP 12)):\n#0  0x1 in raise () from libc.so.6\n"
        "#1  0x2 in QLayoutPrivate::doResize() ()\n\nThread 1 (Thread 0x6f):\n#0  0x4 in wait ()\n"
    )
    frames = sp.cpp_frames(bt)
    assert frames[0] == "Core-Datei core:"
    assert "Thread 2 (Thread 0x7f (LWP 12)):" in frames
    assert frames[-1].endswith("QLayoutPrivate::doResize() ()")
    assert not any("poll" in f or "wait ()" in f for f in frames)
    assert sp.cpp_frames(sp.GDB_HINT) == [sp.GDB_HINT]
    assert "sudo apt install gdb" in sp.GDB_HINT


def test_f01_p06d4_core_settings_name_everything_a_core_file_needs():
    text = sp.core_settings()
    for part in ("gdb:", "coredumpctl:", "RLIMIT_CORE", "core_pattern:", "core_uses_pid:"):
        assert part in text


@NEEDS_XVFB
def test_f01_p06d4_crash_files_are_limited(tmp_path):
    """Drei künstliche Abstürze, höchstens eine Datei (`--max-dateien 1`); Vorgabe sind zwei."""
    assert sp.MAX_CRASH_FILES == 2
    site = tmp_path / "site"
    site.mkdir()
    (site / "sitecustomize.py").write_text(
        "import sys, threading\n"
        "if '--lauf' in sys.argv:\n"
        "    import ctypes\n"  # nicht faulthandler._sigsegv: das setzt RLIMIT_CORE auf 0
        "    t = threading.Timer(1.5, ctypes.string_at, (0,)); t.daemon = True; t.start()\n"
    )
    env = _xvfb_env()
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(site), env.get("PYTHONPATH")]))
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    r = _start_check(
        [
            "--laeufe",
            "3",
            "--variante",
            "standard",
            "--ausgabe",
            str(out_dir),
            "--max-dateien",
            "1",
        ],
        env,
        600,
    )
    assert r.stdout.count("vollständige Aufrufliste von faulthandler:") == 3, r.stdout[-3000:]
    assert r.stdout.count("C++-Aufrufliste (abgestürzter Thread):") == 3
    assert r.stdout.count("keine Datei: schon 1 Absturzdateien") == 2
    assert "== Core-Dateien: gdb:" in r.stdout
    files = sorted(out_dir.glob("startpruefung-absturz-*.txt"))
    assert [f.name for f in files] == ["startpruefung-absturz-standard-1.txt"]
    text = files[0].read_text(encoding="utf-8")
    assert "Core-Dateien: gdb:" in text
    if shutil.which("gdb"):  # mit gdb: Core-Datei und Aufrufliste des abgestürzten Threads
        assert "Core-Datei core" in text and "Program terminated with signal SIGSEGV" in text
        assert r.stdout.count("   C++ | Thread ") == 3, r.stdout[-3000:]
