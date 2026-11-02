"""Startprüfung der echten Oberfläche mit echtem Fenstersystem (P06d2, P06d3, P06d4, F-01, CLAUDE.md Regel 16).

Startet mehrmals (Vorgabe 20) je einen eigenen Prozess mit `python -X faulthandler`. Jeder Lauf:
1. startet einen Kern-Dienst als **eigenen Prozess** (wie auf dem Laptop) in einem leeren Ordner
   (eigene Ports, eigenes Token, nichts vom Nutzer wird berührt),
2. legt je nach Variante vorher eine gespeicherte Fensterlage ab (`save_geometry`, eigener Prozess mit der echten
   Oberfläche, so wie sie selbst speichert) und danach Overlays und Quellen über die lokale API des Kerns
   (`seed_data`, nicht über die Oberfläche),
3. startet die echte Oberfläche über `donstv_studio.ui.main.main()` mit `QT_QPA_PLATFORM=xcb`
   (nicht `offscreen`); die Oberfläche beendet sich nach `DONSTV_AUTOQUIT_MS` selbst,
4. endet normal (kein os._exit).

Fenstersystem: das vorhandene `DISPLAY`. Ohne `DISPLAY` startet das Skript ein eigenes `Xvfb` (falls
installiert) und schreibt das deutlich in die Ausgabe; ohne beides bricht es mit Exit-Code 2 ab.

Varianten (`--variante`):
- `standard`          leere Daten, keine gespeicherte Fensterlage
- `schmal`            gespeicherte Fensterlage schmaler als die Mindestbreite, sonst leer
- `daten`             gespeicherte Fensterlage (normal breit) und gefüllte Daten: 3 Overlays, eines davon mit
                      6 Quellen (Text und Bild, ein Bild mit anderem Seitenverhältnis als die Fläche)
- `daten_schmal`      wie `daten`, aber mit der schmalen Fensterlage von `schmal`
- `daten_leer`        nur die gespeicherte Fensterlage von `daten`, keine Overlays (Lauf-Satz «leere Liste»)
- `daten_overlays`    Fensterlage und 3 Overlays **ohne** Quellen (Lauf-Satz «nur Overlays»)
- `daten_reiter`      wie `daten`, gespeicherte Dock-Anordnung mit Reitern («Quellen» hinter «Overlays»,
                      «Steuerung» hinter «Eigenschaften»)
- `daten_schwebend`   wie `daten`, gespeicherte Dock-Anordnung mit schwebendem Dock «Overlays»
- `kopie`             eine **Kopie** der echten Daten des Nutzers (Datenbank mit Overlays, Quellen, gespeicherter
                      Fensterlage und Dock-Anordnung, dazu die Mediendateien) in den leeren Ordner; das Original
                      wird nur gelesen (`copy_user_data`). Zugangsdaten werden nicht kopiert.
- `kopie_ohne_lage`   P06d4: wie `kopie`, in der Kopie ohne gespeicherte Fensterlage und Dock-Anordnung
                      (Schlüssel `ui.geometry` und `ui.dock_state`)
- `kopie_ohne_geometrie`  P06d4: wie `kopie`, in der Kopie nur ohne Fensterlage (`ui.geometry`)
- `kopie_ohne_anordnung`  P06d4: wie `kopie`, in der Kopie nur ohne Dock-Anordnung (`ui.dock_state`)
- `kopie_ohne_quellen`    P06d4: wie `kopie`, in der Kopie bleiben die Overlays, alle Quellen werden entfernt
- `daten_maximiert`   P06d4 (Ergänzung): wie `daten`, die Fensterlage wird von einem maximierten Fenster gespeichert
- `aus=<Liste>`       wie `standard`, mit `DONSTV_OFF=<Liste>` (Diagnose-Schalter, siehe `ui/diagnose.py`);
                      mehrere Teile mit Komma, z. B. `aus=perf_equalize,min_width`
- `<Variante>,aus=<Liste>`  eine der Varianten oben mit Diagnose-Schaltern, z. B. `daten,aus=theme_changes`

Ausgabe: je Lauf der Exit-Code mit Deutung und die letzten 15 Zeilen von stderr, am Ende
«N von M Läufen mit Exit-Code 0». Bei den Varianten `kopie…` vor dem ersten Lauf die Beschreibung der Lage in der
Kopie (`tools/lage_beschreiben.py`, Zeilen «[Lage]»). Bei einem Absturz (Exit-Code 139 oder −11, 134 oder −6)
zusätzlich die vollständige Aufrufliste von `faulthandler` (alle Threads) und, für die ersten zwei Abstürze je
Aufruf (`--max-dateien`), die Datei `startpruefung-absturz-<variante>-<lauf>.txt` im Ordner des Repos (ganzes
stderr; mit `gdb` und Core-Datei auch die C++-Aufrufliste, sonst der Grund, warum es keine gibt). Exit-Code dieses
Skripts: 0, wenn alle Läufe mit 0 enden, sonst 1.

Aufruf:  python tools/start_pruefung.py [--laeufe 20] [--variante standard] [--autoquit-ms 4000] [--ausgabe .]
         (oder tools/start_pruefung.sh)
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import zlib
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from beenden_pruefung import TAIL_LINES, describe, free_port

ROOT = Path(__file__).resolve().parents[1]
RUN_TIMEOUT = 120  # Sekunden je Lauf
CORE_TIMEOUT = 30  # Sekunden, bis der Kern-Dienst antworten muss
AUTOQUIT_MS = 4000  # Vorgabe: so lange bleibt die Oberfläche offen
# Breite der gespeicherten Fensterlage in der Variante «schmal»: grösser als die Mindestbreite von P08 (986 px),
# kleiner als die von P06d (1209 px in der Sitzung von P06d)
NARROW_SIZE = (1000, 700)
# Gespeicherte Fensterlage der Varianten mit Daten: breiter als die Mindestbreite, kleiner als ein Bildschirm mit
# 1366 × 768 px (Annahme für den Laptop, nicht gemessen)
NORMAL_SIZE = (1300, 720)
CRASH_CODES = (139, -11, 134, -6)  # Speicherzugriffsfehler und Abbruch (SIGSEGV, SIGABRT)
GDB_TIMEOUT = 120
# P06d4: Absturzdateien je Aufruf (Variante); weitere Abstürze nur in der Ausgabe
MAX_CRASH_FILES = 2
CPP_LINES = 40  # Zeilen der C++-Aufrufliste in der Ausgabe (die Datei enthält alle)
GDB_HINT = "gdb fehlt: keine C++-Aufrufliste (Debian: sudo apt install gdb)"

CORE_SCRIPT = r"""
import asyncio, sys
from donstv_studio.core.config import Paths
from donstv_studio.core.service import Service
paths = Paths.from_xdg()
paths.ensure()
asyncio.run(Service(paths, port=int(sys.argv[1]), overlay_port=int(sys.argv[2])).run())
"""


DOCK_MODES = ("standard", "reiter", "schwebend")


@dataclass(frozen=True)
class Variant:
    """Was vor dem Start im leeren Kern liegt."""

    label: str  # wie angegeben, für Ausgabe und Dateinamen
    geometry: tuple[int, int] | None  # gespeicherte Fensterlage (Breite, Höhe) oder keine
    overlays: int  # Anzahl Overlays
    sources: bool  # das erste Overlay bekommt 6 Quellen
    off: str  # Wert für DONSTV_OFF
    docks: str = "standard"  # gespeicherte Dock-Anordnung (DOCK_MODES)
    copy: bool = False  # Kopie der echten Daten des Nutzers statt angelegter Daten
    strip: tuple[str, ...] = ()  # P06d4: was in der Kopie entfernt wird (STRIP_PARTS)
    maximized: bool = False  # P06d4: Fensterlage von einem maximierten Fenster gespeichert


# P06d4: Teile, die in der Kopie entfernt werden können: Einstellungsschlüssel oder Tabelle
STRIP_PARTS = {"geometry": "ui.geometry", "state": "ui.dock_state", "sources": "sources"}

# Name -> (Fensterlage, Overlays, Quellen, Dock-Anordnung, weitere Felder von Variant)
BASES: dict[str, tuple[tuple[int, int] | None, int, bool, str, dict]] = {
    "standard": (None, 0, False, "standard", {}),
    "schmal": (NARROW_SIZE, 0, False, "standard", {}),
    "daten": (NORMAL_SIZE, 3, True, "standard", {}),
    "daten_schmal": (NARROW_SIZE, 3, True, "standard", {}),
    "daten_leer": (NORMAL_SIZE, 0, False, "standard", {}),
    "daten_overlays": (NORMAL_SIZE, 3, False, "standard", {}),
    # P06d3: eigene Dock-Anordnung, wie sie ein Nutzer speichert (die Prüfung oben kennt nur die Standardanordnung)
    "daten_reiter": (NORMAL_SIZE, 3, True, "reiter", {}),
    "daten_schwebend": (NORMAL_SIZE, 3, True, "schwebend", {}),
    # P06d4 (Ergänzung): Fensterlage eines maximierten Fensters (die echten Daten könnten so gespeichert sein)
    "daten_maximiert": (NORMAL_SIZE, 3, True, "standard", {"maximized": True}),
    # P06d3: Kopie der echten Daten (copy_user_data)
    "kopie": (None, 0, False, "standard", {"copy": True}),
    # P06d4: Kopie der echten Daten mit genau einer Änderung (nur an der Kopie)
    "kopie_ohne_lage": (None, 0, False, "standard", {"copy": True, "strip": ("geometry", "state")}),
    "kopie_ohne_geometrie": (None, 0, False, "standard", {"copy": True, "strip": ("geometry",)}),
    "kopie_ohne_anordnung": (None, 0, False, "standard", {"copy": True, "strip": ("state",)}),
    "kopie_ohne_quellen": (None, 0, False, "standard", {"copy": True, "strip": ("sources",)}),
}


def step(text: str) -> None:
    print(f"Schritt: {text}", file=sys.stderr, flush=True)


def run_env(base: Path) -> dict[str, str]:
    """Umgebung eines Laufs: alles in den leeren Ordner `base`."""
    env = {**os.environ}
    env["XDG_CONFIG_HOME"] = str(base / "config")
    env["XDG_DATA_HOME"] = str(base / "data")
    env["XDG_STATE_HOME"] = str(base / "state")
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(ROOT / "src"), env.get("PYTHONPATH")]))
    if hasattr(os, "geteuid") and os.geteuid() == 0:  # Chromium startet als root nur ohne Sandbox
        env.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox")
    # P06d3: Der Kern der Prüfung darf keine zweite Verbindung zu Twitch öffnen (F-08, CLAUDE.md Regel 3): kein Zugriff
    # auf den Schlüsselbund des Nutzers (Backend «null», https://pypi.org/project/keyring/, Abschnitt
    # «Configuring») und die Testverbindung statt Twitch (DONSTV_TWITCH_FAKE, core/service.py).
    env["PYTHON_KEYRING_BACKEND"] = "keyring.backends.null.Keyring"
    env["DONSTV_TWITCH_FAKE"] = "1"
    return env


# --- Kern-Dienst als eigener Prozess -------------------------------------------------------------
def token_file_of(env: dict[str, str]) -> Path:
    from donstv_studio.core.config import Paths

    old = {k: os.environ.get(k) for k in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME")}
    os.environ.update({k: env[k] for k in old})
    try:
        return Paths.from_xdg().token_file
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def start_core(env: dict[str, str], port: int, overlay_port: int) -> subprocess.Popen:
    proc = subprocess.Popen(
        [sys.executable, "-c", CORE_SCRIPT, str(port), str(overlay_port)],
        env=env,
        cwd=str(ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    from donstv_studio.ui.backend import CoreBackend

    token_file = token_file_of(env)
    deadline = time.monotonic() + CORE_TIMEOUT
    last: Exception | None = None
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"Kern-Dienst beendet mit Exit-Code {proc.returncode}")
        try:
            if token_file.exists():
                CoreBackend(f"http://127.0.0.1:{port}", token_file)._call("GET", "/settings")
                return proc
        except Exception as e:  # noqa: BLE001 – der Kern startet noch
            last = e
        time.sleep(0.2)
    proc.kill()
    raise RuntimeError(f"Kern-Dienst antwortet nicht ({last})")


def stop_core(proc: subprocess.Popen) -> None:
    proc.terminate()
    try:
        proc.wait(15)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(5)


# --- Daten über die lokale API (P06d3) -----------------------------------------------------------
def png_bytes(width: int, height: int, rgb: tuple[int, int, int]) -> bytes:
    """Einfarbiges PNG ohne Qt (der Steuerprozess lädt kein Qt-Fenstersystem)."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    row = b"\x00" + bytes(rgb) * width
    raw = zlib.compress(row * height, 9)
    head = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", head) + chunk(b"IDAT", raw) + chunk(b"IEND", b"")


def seed_data(env: dict[str, str], port: int, overlays: int, sources: bool, folder: Path) -> str:
    """Legt `overlays` Overlays an, das erste mit 6 Quellen (falls `sources`). Gibt eine Zeile für die Ausgabe zurück.

    Quellen im ersten Overlay (1920 × 1080): 3 Textquellen (eine davon ausgeblendet, eine mit Namen) und 3 Bildquellen
    (Banner 1200 × 200, also 6:1 statt 16:9; Quadrat 256 × 256; Hochformat 300 × 600, gedreht). Eine gesperrte
    Quelle gibt es im Datenmodell noch nicht (`overlays/models.py`, `Source`), deshalb keine.
    """
    if overlays <= 0:
        return "keine Overlays angelegt"
    from donstv_studio.ui.backend import CoreBackend

    api = CoreBackend(f"http://127.0.0.1:{port}", token_file_of(env))
    made = [api.create_overlay(f"Overlay {i}") for i in range(1, overlays + 1)]
    count = 0
    if sources:
        oid = made[0]["id"]
        images = []
        for name, (w, h, rgb) in {
            "banner.png": (1200, 200, (200, 40, 40)),
            "quadrat.png": (256, 256, (40, 160, 60)),
            "hoch.png": (300, 600, (40, 60, 200)),
        }.items():
            path = folder / name
            path.write_bytes(png_bytes(w, h, rgb))
            images.append((api.upload_media(str(path)), w, h))
        texts = (
            {"x": 100, "y": 900, "width": 800, "height": 100, "props": {"text": "Willkommen"}},
            {"x": 1200, "y": 50, "width": 600, "height": 80, "props": {"text": "Zweite Zeile"},
             "name": "Titel oben"},
            {"x": 50, "y": 50, "width": 400, "height": 60, "props": {"text": "Ausgeblendet"},
             "visible": False},
        )  # fmt: skip
        for fields in texts:
            api.add_source(oid, "text", **fields)
            count += 1
        for i, (item, w, h) in enumerate(images):
            fields = {"x": 100 + 300 * i, "y": 300, "width": w, "height": h}
            if i == 2:
                fields["rotation"] = 15.0
            api.add_source(oid, "image", props={"media_id": item["id"]}, **fields)
            count += 1
    return f"{len(made)} Overlays angelegt, {count} Quellen im ersten"


def copy_user_data(env: dict[str, str], strip: tuple[str, ...] = ()) -> str:
    """Variante `kopie`: Datenbank und Mediendateien des Nutzers in den Ordner der Prüfung kopieren.

    Quelle sind die Ordner des Nutzers (XDG wie `donstv-core`), Ziel die Ordner aus `env`. Die Datenbank wird über die
    Sicherungsschnittstelle von SQLite gelesen (`Connection.backup`, https://docs.python.org/3/library/sqlite3.html),
    nur lesend geöffnet; das geht auch, während `donstv-core` des Nutzers läuft. Nicht kopiert: Zugangsdaten
    (Schlüsselbund, Datei im Konfigurationsordner) und das Token der Schnittstelle (der Kern erzeugt ein neues).

    `strip` (P06d4, `STRIP_PARTS`): danach in der **Kopie** Einstellungen (`geometry`, `state`) oder alle Quellen
    (`sources`) entfernen. Das Original wird dabei nicht geöffnet.
    """
    import sqlite3

    from donstv_studio.core.config import Paths

    src = Paths.from_xdg()  # Umgebung des Steuerprozesses = die des Nutzers
    old = {k: os.environ.get(k) for k in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME")}
    os.environ.update({k: env[k] for k in old})
    try:
        dst = Paths.from_xdg()
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    if not src.db_file.exists():
        raise RuntimeError(f"keine Datenbank des Nutzers unter {src.db_file}")
    dst.ensure()
    source = sqlite3.connect(f"{src.db_file.as_uri()}?mode=ro", uri=True)
    target = sqlite3.connect(dst.db_file)
    try:
        source.backup(target)
    finally:
        source.close()
    try:
        removed = strip_copy(target, strip)
    finally:
        target.close()
    files = 0
    if src.media_dir.is_dir():
        shutil.copytree(src.media_dir, dst.media_dir, dirs_exist_ok=True)
        files = sum(1 for p in dst.media_dir.rglob("*") if p.is_file())
    text = (
        f"Kopie der Datenbank ({src.db_file.stat().st_size // 1024} KB) und {files} Mediendateien"
    )
    return f"{text}; in der Kopie entfernt: {removed}" if strip else text


def copy_db_file(env: dict[str, str]) -> Path:
    """Pfad der Datenbank im Ordner der Prüfung (Ziel von `copy_user_data`)."""
    from donstv_studio.core.config import Paths

    old = {k: os.environ.get(k) for k in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME")}
    os.environ.update({k: env[k] for k in old})
    try:
        return Paths.from_xdg().db_file
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def strip_copy(con, strip: tuple[str, ...]) -> str:
    """P06d4: Teile aus der **Kopie** entfernen (offene Verbindung zur Kopie). Gibt eine Zeile für die Ausgabe."""
    done = []
    for part in strip:
        what = STRIP_PARTS[part]
        if part == "sources":
            n = con.execute("DELETE FROM sources").rowcount
            done.append(f"{n} Quellen")
        else:
            n = con.execute("DELETE FROM settings WHERE key = ?", (what,)).rowcount
            done.append(f"{what} ({'war gespeichert' if n else 'war nicht gespeichert'})")
    con.commit()
    return ", ".join(done) or "nichts"


# --- gespeicherte Fensterlage ---------------------------------------------------------------------
def arrange(window, mode: str) -> None:
    """Dock-Anordnung vor dem Speichern: `standard` (unverändert), `reiter` oder `schwebend`."""
    docks = {d.objectName(): d for d in window.docks}
    if mode == "reiter":
        window.tabifyDockWidget(docks["dock_overlays"], docks["dock_sources"])
        window.tabifyDockWidget(docks["dock_properties"], docks["dock_control"])
        docks["dock_overlays"].raise_()
    elif mode == "schwebend":
        dock = docks["dock_overlays"]
        dock.setFloating(True)
        dock.setGeometry(60, 60, 320, 260)


def save_geometry(
    port: int, width: int, height: int, docks: str = "standard", maximized: bool = False
) -> int:
    """Eigener Prozess: legt eine gespeicherte Fensterlage `width` × `height` im (noch leeren) Kern ab.

    `MainWindow.layout_values()` speichert `saveGeometry()` und `saveState(STATE_VERSION)` mit der Marke
    `LAYOUT_TAG` (beides seit P08 unverändert). Das Fenster wird hier mit aufgehobener Mindestbreite auf die Grösse
    gebracht, gezeigt und gespeichert; genau so läge eine Lage aus P08 im Kern (schmal) oder eine Lage, die der
    Nutzer selbst eingestellt hat (normal).
    """
    os.environ["DONSTV_CORE_PORT"] = str(port)
    from PyQt6.QtWidgets import QApplication

    from donstv_studio.ui import preview_web  # noqa: F401  (vor der QApplication)
    from donstv_studio.ui.core_link import CoreLink
    from donstv_studio.ui.main_window import KEY_GEOMETRY, MainWindow

    app = QApplication(["start_pruefung_geometrie"])
    core = CoreLink()
    window = MainWindow(core)
    window.show()
    for _ in range(10):  # erst alles Ausstehende (auch die Mindestbreite) erledigen lassen
        app.processEvents()
        time.sleep(0.02)
    window.setMinimumWidth(0)  # wie P08: dort war die Mindestbreite kleiner
    window.resize(width, height)
    arrange(window, docks)
    # P06d4: saveGeometry speichert dann «maximiert» und die normale Lage width × height
    if maximized:
        window.showMaximized()
    for _ in range(20):
        app.processEvents()
        time.sleep(0.02)
    values = window.layout_values()
    got = window.width()
    is_max = window.isMaximized()
    tabs = sum(len(window.tabifiedDockWidgets(d)) for d in window.docks) // 2
    floating = sum(d.isFloating() for d in window.docks)
    ok = core.save_settings_blocking(values)
    print(
        f"gespeicherte Fensterlage: {got} px breit, {len(values[KEY_GEOMETRY])} Zeichen, Docks {docks} "
        f"({tabs} Reiterpaare, {floating} schwebend, {'maximiert' if is_max else 'nicht maximiert'}), "
        f"gespeichert: {bool(ok)}",
        file=sys.stderr,
    )
    window.close()
    from donstv_studio.ui import main as ui_main

    ui_main.shutdown(app, window)
    if maximized:
        return 0 if ok and is_max else 4
    return 0 if ok and abs(got - width) < 100 else 4


# --- ein Lauf (im eigenen Prozess) -------------------------------------------------------------
def single_run(port: int) -> int:
    os.environ["DONSTV_CORE_PORT"] = str(port)
    from PyQt6.QtCore import PYQT_VERSION_STR, QT_VERSION_STR

    from donstv_studio.ui import main as ui_main

    step(
        f"Oberfläche starten (Qt {QT_VERSION_STR}, PyQt6 {PYQT_VERSION_STR}, "
        f"QT_QPA_PLATFORM={os.environ.get('QT_QPA_PLATFORM')}, DISPLAY={os.environ.get('DISPLAY')}, "
        f"DONSTV_OFF={os.environ.get('DONSTV_OFF', '')!r})"
    )
    code = ui_main.main()
    step(f"main() beendet mit {code}; Python beendet sich jetzt normal")
    return code


# --- Fenstersystem -------------------------------------------------------------------------------
def ensure_display() -> tuple[subprocess.Popen | None, str]:
    """Gibt (eigenes Xvfb oder None, Beschreibung) zurück; ohne Fenstersystem SystemExit(2)."""
    if os.environ.get("DISPLAY"):
        return None, f"vorhandenes DISPLAY={os.environ['DISPLAY']}"
    xvfb = shutil.which("Xvfb")
    if not xvfb:
        print(
            "KEIN DISPLAY und kein Xvfb: die Startprüfung braucht ein echtes Fenstersystem (X11). "
            "Bitte in einer grafischen Sitzung ausführen."
        )
        raise SystemExit(2)
    for num in range(91, 120):
        if Path(f"/tmp/.X11-unix/X{num}").exists() or Path(f"/tmp/.X{num}-lock").exists():
            continue
        proc = subprocess.Popen(
            [xvfb, f":{num}", "-screen", "0", "1920x1080x24", "-nolisten", "tcp"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(50):
            if Path(f"/tmp/.X11-unix/X{num}").exists():
                os.environ["DISPLAY"] = f":{num}"
                return proc, (
                    f"KEIN DISPLAY: eigenes Xvfb auf :{num} gestartet (virtuelles X11 ohne "
                    "Fenstermanager, nicht das Fenstersystem des Laptops)"
                )
            time.sleep(0.1)
        proc.kill()
    print("KEIN DISPLAY, und Xvfb liess sich nicht starten.")
    raise SystemExit(2)


# --- Absturz erfassen (P06d3) ---------------------------------------------------------------------
def faulthandler_part(stderr: str) -> str:
    """Die vollständige Ausgabe von faulthandler (ab «Fatal Python error»), sonst leer."""
    i = stderr.find("Fatal Python error")
    return stderr[i:] if i >= 0 else ""


def allow_core_files() -> str:
    """Core-Dateien für die Kindprozesse erlauben (Grenze wird vererbt). Nur mit gdb sinnvoll."""
    import resource

    soft, hard = resource.getrlimit(resource.RLIMIT_CORE)
    try:
        resource.setrlimit(resource.RLIMIT_CORE, (hard, hard))
    except (ValueError, OSError) as e:
        return f"Core-Dateien nicht erlaubt ({e})"
    return f"Core-Dateien erlaubt (Grenze {hard if hard >= 0 else 'unbegrenzt'}, vorher {soft})"


def core_settings() -> str:
    """P06d4: alles, wovon eine Core-Datei abhängt, in einer Zeile (für Ausgabe und Absturzdatei)."""
    import resource

    def read(path: str) -> str:
        try:
            return Path(path).read_text().strip()
        except OSError:
            return "?"

    soft, hard = resource.getrlimit(resource.RLIMIT_CORE)

    def limit(v: int) -> str:
        return "unbegrenzt" if v == resource.RLIM_INFINITY else str(v)

    gdb = shutil.which("gdb")
    return (
        f"gdb: {gdb or 'fehlt'}; coredumpctl: {shutil.which('coredumpctl') or 'fehlt'}; "
        f"RLIMIT_CORE {limit(soft)}/{limit(hard)} (weich/hart); "
        f"core_pattern: {read('/proc/sys/kernel/core_pattern')}; "
        f"core_uses_pid: {read('/proc/sys/kernel/core_uses_pid')}"
    )


def core_backtrace(pid: int, cwd: Path) -> str:
    """C++-Aufrufliste aus der Core-Datei (nur mit gdb). Unterstützt eine Datei im Arbeitsordner oder coredumpctl.

    Ohne Ergebnis nennt der Text den Grund (P06d4): gdb fehlt, keine Core-Datei im Ordner des Laufs (mit den
    Einstellungen aus `core_settings` und den Dateien im Ordner) oder die Ausgabe von coredumpctl.
    """
    gdb = shutil.which("gdb")
    if not gdb:
        return GDB_HINT
    cmds = ["-batch", "-ex", "info sharedlibrary Qt6Core", "-ex", "thread apply all bt 60"]
    cores = sorted(cwd.glob("core*"), key=lambda p: p.stat().st_mtime)
    try:
        if cores:
            out = subprocess.run(
                [gdb, *cmds, sys.executable, str(cores[-1])],
                capture_output=True,
                text=True,
                timeout=GDB_TIMEOUT,
                check=False,
            )
            return f"Core-Datei {cores[-1].name}:\n{out.stdout}{out.stderr}"
        if shutil.which("coredumpctl"):
            time.sleep(2)  # systemd-coredump schreibt die Datei nach dem Ende des Prozesses
            out = subprocess.run(
                ["coredumpctl", "--no-pager", "debug", f"--debugger={gdb}",
                 "-A", " ".join(f"'{c}'" if " " in c else c for c in cmds), str(pid)],
                capture_output=True, text=True, timeout=GDB_TIMEOUT, check=False,
            )  # fmt: skip
            return f"coredumpctl (PID {pid}, Exit-Code {out.returncode}):\n{out.stdout}{out.stderr}"
    except subprocess.TimeoutExpired:
        return "gdb: Zeitüberschreitung"
    names = sorted(p.name for p in cwd.iterdir())
    return (
        f"keine Core-Datei im Ordner des Laufs und kein coredumpctl ({core_settings()}; "
        f"Dateien im Ordner: {', '.join(names) or 'keine'})"
    )


def cpp_frames(backtrace: str) -> list[str]:
    """P06d4: Kopfzeilen und die Aufrufliste des abgestürzten Threads für die Ausgabe.

    gdb meldet ihn als «[Current thread is N (…)]»; seine Aufrufliste steht unter «Thread N (…):». Ohne diese Angabe
    die erste Aufrufliste unter einer Zeile «Thread …», ohne Aufrufliste die ersten Zeilen (z. B. der Grund).
    """
    lines = backtrace.splitlines()
    head = [
        line
        for line in lines
        if line.startswith(("Core-Datei", "coredumpctl", "Program terminated", "[Current thread"))
    ]
    match = re.search(r"\[Current thread is (\d+) ", backtrace)
    marker = f"Thread {match.group(1)} (" if match else "Thread "
    start = next((i for i, line in enumerate(lines) if line.startswith(marker)), None)
    if start is None:
        return lines[:CPP_LINES]
    frames = [lines[start]]
    for line in lines[start + 1 :]:
        if not line.lstrip().startswith("#"):
            break
        frames.append(line)
    return (head + frames)[:CPP_LINES]


# --- Steuerung: mehrere Läufe -------------------------------------------------------------------
def run_child(args: list[str], env: dict[str, str], cwd: Path) -> tuple[int, str, int]:
    """(Exit-Code, stderr, PID). Läuft in `cwd` (eine Core-Datei landet dort)."""
    cmd = [sys.executable, "-X", "faulthandler", str(Path(__file__).resolve()), *args]
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        cwd=str(cwd),
    )
    try:
        _, err = proc.communicate(timeout=RUN_TIMEOUT)
        return proc.returncode, err, proc.pid
    except subprocess.TimeoutExpired:
        proc.kill()
        _, err = proc.communicate()
        return -9999, (err or "") + f"\nZeitüberschreitung nach {RUN_TIMEOUT} s", proc.pid


def parse_variant(text: str) -> Variant:
    """`standard`, `schmal`, `daten`, …, `aus=<Liste>` oder `<Variante>,aus=<Liste>` → Variant."""
    base, off = text, ""
    if text.startswith("aus="):
        base, off = "standard", text[4:]
    elif ",aus=" in text:
        base, off = text.split(",aus=", 1)
    if base not in BASES:
        raise SystemExit(
            f"Unbekannte Variante «{text}»: {', '.join(BASES)}, aus=<Liste> oder <Variante>,aus=<Liste>"
        )
    # P06d4: im Werkzeug mehrere Schalter auch mit Leerzeichen (wie DONSTV_OFF), z. B. «aus=a b»
    off = off.replace(" ", ",")
    if off or text.startswith("aus=") or ",aus=" in text:
        from donstv_studio.ui import diagnose

        parts = [p.strip() for p in off.split(",") if p.strip()]
        unknown = [p for p in parts if p not in diagnose.SWITCHES]
        if not parts or unknown:
            raise SystemExit(
                f"Unbekannte Teile {unknown or '(keine)'}; erlaubt: {', '.join(diagnose.SWITCHES)}"
            )
        off = ",".join(parts)
    geometry, overlays, sources, docks, extra = BASES[base]
    return Variant(text, geometry, overlays, sources, off, docks, **extra)


def describe_copy(env: dict[str, str]) -> list[str]:
    """P06d4: Lage in der Kopie (`tools/lage_beschreiben.py`); ein Fehler wird gemeldet, bricht aber nicht ab."""
    import lage_beschreiben

    try:
        return lage_beschreiben.describe(copy_db_file(env))
    except Exception as e:  # noqa: BLE001 – nur Beschreibung, die Prüfung läuft weiter
        return [f"nicht lesbar ({type(e).__name__}: {e})"]


def sqlite3_error() -> type[Exception]:
    import sqlite3

    return sqlite3.Error


def file_label(text: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in text)[:80]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--laeufe", type=int, default=20)
    parser.add_argument("--variante", default="standard")
    parser.add_argument("--autoquit-ms", type=int, default=AUTOQUIT_MS)
    parser.add_argument(
        "--ausgabe", type=Path, default=ROOT, help="Ordner für startpruefung-absturz-*.txt"
    )
    parser.add_argument("--lauf", type=int, metavar="PORT", help=argparse.SUPPRESS)  # intern
    parser.add_argument("--geometrie", type=int, metavar="PORT", help=argparse.SUPPRESS)  # intern
    parser.add_argument("--groesse", default="1000x700", help=argparse.SUPPRESS)  # intern
    parser.add_argument("--docks", default="standard", choices=DOCK_MODES, help=argparse.SUPPRESS)
    parser.add_argument("--maximiert", action="store_true", help=argparse.SUPPRESS)  # intern
    parser.add_argument(
        "--max-dateien",
        type=int,
        default=MAX_CRASH_FILES,
        help="höchstens so viele Absturzdateien je Aufruf (P06d4)",
    )
    args = parser.parse_args()
    if args.lauf:
        return single_run(args.lauf)
    if args.geometrie:
        w, h = (int(v) for v in args.groesse.split("x"))
        return save_geometry(args.geometrie, w, h, args.docks, args.maximiert)

    sys.path.insert(0, str(ROOT / "src"))
    variant = parse_variant(args.variante)
    xvfb, display = ensure_display()
    cores = allow_core_files() if shutil.which("gdb") else GDB_HINT
    from PyQt6.QtCore import PYQT_VERSION_STR, QT_VERSION_STR

    print(
        f"== Startprüfung: Variante {variant.label}, {args.laeufe} Läufe, Qt {QT_VERSION_STR}, "
        f"PyQt6 {PYQT_VERSION_STR}, QT_QPA_PLATFORM=xcb, {display}, "
        f"DONSTV_AUTOQUIT_MS={args.autoquit_ms}, {cores}"
    )
    print(f"== Core-Dateien: {core_settings()}")
    sys.stdout.flush()
    codes: list[int] = []
    saved_files = 0
    try:
        for n in range(1, args.laeufe + 1):
            with tempfile.TemporaryDirectory(prefix="donstv-start-") as tmp:
                base = Path(tmp)
                env = run_env(base)
                env["QT_QPA_PLATFORM"] = "xcb"
                env["DONSTV_AUTOQUIT_MS"] = str(args.autoquit_ms)
                env["DISPLAY"] = os.environ["DISPLAY"]
                env.pop("DONSTV_OFF", None)
                port, overlay_port = free_port(), free_port()
                start = time.monotonic()
                prefix = ""
                if variant.copy:
                    try:
                        prefix = f"[Daten] {copy_user_data(env, variant.strip)}\n"
                    except (OSError, RuntimeError, sqlite3_error()) as e:
                        codes.append(-9997)
                        print(f"== Lauf {n}: Kopie der echten Daten nicht möglich ({e})")
                        continue
                    if n == 1:  # P06d4: Lage in der Kopie beschreiben, ohne Geheimnisse
                        print("== Lage in der Kopie (tools/lage_beschreiben.py):")
                        for line in describe_copy(env):
                            print(f"   [Lage] {line}")
                try:
                    core = start_core(env, port, overlay_port)
                except RuntimeError as e:
                    codes.append(-9998)
                    print(f"== Lauf {n}: Kern-Dienst startet nicht ({e})")
                    continue
                try:
                    if variant.geometry is not None:
                        size = "x".join(str(v) for v in variant.geometry)
                        gargs = [
                            "--geometrie",
                            str(port),
                            "--groesse",
                            size,
                            "--docks",
                            variant.docks,
                        ]
                        if variant.maximized:
                            gargs.append("--maximiert")
                        gcode, gerr, _ = run_child(gargs, env, base)
                        tail = gerr.splitlines()[-TAIL_LINES:]
                        prefix += "".join(f"[Fensterlage] {line}\n" for line in tail)
                        if gcode != 0:
                            prefix += f"[Fensterlage] Exit-Code {gcode}: Lage nicht abgelegt\n"
                    if variant.overlays:
                        try:
                            text = seed_data(env, port, variant.overlays, variant.sources, base)
                        except Exception as e:  # noqa: BLE001 – in der Ausgabe melden, Lauf zählt nicht
                            text = f"FEHLER beim Anlegen der Daten: {e}"
                            codes.append(-9997)
                            print(f"== Lauf {n}: {text}")
                            continue
                        prefix += f"[Daten] {text}\n"
                    if variant.off:
                        env["DONSTV_OFF"] = variant.off
                    code, err, pid = run_child(["--lauf", str(port)], env, base)
                    backtrace = core_backtrace(pid, base) if code in CRASH_CODES else ""
                finally:
                    stop_core(core)
            codes.append(code)
            label = "Zeitüberschreitung" if code == -9999 else describe(code)
            print(f"== Lauf {n}: Exit-Code {code} ({label}), {time.monotonic() - start:.1f} s")
            print(f"   letzte {TAIL_LINES} Zeilen von stderr:")
            for line in prefix.splitlines() + err.splitlines()[-TAIL_LINES:]:
                print(f"   | {line}")
            if code in CRASH_CODES:
                print("   vollständige Aufrufliste von faulthandler:")
                for line in (
                    faulthandler_part(err) or "(keine Ausgabe von faulthandler)"
                ).splitlines():
                    print(f"   # {line}")
                print("   C++-Aufrufliste (abgestürzter Thread):")
                for line in cpp_frames(backtrace):
                    print(f"   C++ | {line}")
                if saved_files < args.max_dateien:  # P06d4: höchstens zwei Dateien je Variante
                    saved_files += 1
                    report = (
                        args.ausgabe / f"startpruefung-absturz-{file_label(variant.label)}-{n}.txt"
                    )
                    report.write_text(
                        f"Variante {variant.label}, Lauf {n}, Exit-Code {code} ({label})\n"
                        f"Qt {QT_VERSION_STR}, PyQt6 {PYQT_VERSION_STR}, {display}\n"
                        f"Core-Dateien: {core_settings()}\n\n"
                        f"--- Vorbereitung ---\n{prefix}\n--- stderr vollständig ---\n{err}\n"
                        f"--- C++-Aufrufliste ---\n{backtrace}\n",
                        encoding="utf-8",
                    )
                    print(
                        f"   gespeichert: {report.name} (ganzes stderr, C++-Aufrufliste oder ihr Fehlen)"
                    )
                else:
                    print(
                        f"   keine Datei: schon {args.max_dateien} Absturzdateien für diese Variante"
                    )
            sys.stdout.flush()
    finally:
        if xvfb is not None:
            xvfb.terminate()
            xvfb.wait(10)
    ok = sum(1 for c in codes if c == 0)
    print(
        f"== Zusammenfassung Startprüfung (Variante {variant.label}): {ok} von {len(codes)} Läufen "
        f"mit Exit-Code 0 (Exit-Codes: {codes})"
    )
    return 0 if ok == len(codes) and codes else 1


if __name__ == "__main__":
    sys.exit(main())
