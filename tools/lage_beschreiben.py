"""Gespeicherte Fensterlage und Dock-Anordnung beschreiben, ohne Geheimnisse (P06d4, F-01).

Liest aus einer Datenbank von donstv_Studio (Vorgabe: die des Nutzers, nur lesend geöffnet) die Einstellungen
`ui.geometry` (Fensterlage, `QWidget::saveGeometry`), `ui.dock_state` (Dock-Anordnung, `QMainWindow::saveState`) und
`ui.theme` und gibt aus:

- Fensterlage: Länge, Marke `v3:`, Kennzahl und Version des Qt-Formats, Rahmen-, Normal- und Fenstergeometrie in
  Pixeln, Bildschirmnummer, Breite des Bildschirms beim Speichern, maximiert, Vollbild,
- Dock-Anordnung: Länge, Marke, Kennzeichen und Version, dazu (über `QMainWindow.restoreState` in einem eigenen
  Prozess mit `QT_QPA_PLATFORM=offscreen`, nur die sechs Docks mit ihren Objektnamen, keine echte Oberfläche):
  ob sie passt, Reiterpaare, schwebende und sichtbare Docks,
- Theme, Anzahl Overlays und Quellen (nur Zahlen).

Keine Zugangsdaten, keine Namen von Overlays, Quellen oder Mediendateien.

Format der Fensterlage (Qt 6.8.2, `src/widgets/kernel/qwidget.cpp`, `QWidget::saveGeometry`, Zeilen 7375–7399,
https://raw.githubusercontent.com/qt/qtbase/v6.8.2/src/widgets/kernel/qwidget.cpp): `QDataStream` mit Version
`Qt_4_0` (Bytefolge gross-endian, Vorgabe von `QDataStream`: `src/corelib/serialization/qdatastream.h`,
Zeile 226), Kennzahl `0x1D9D0CB` (quint32), Version (2 × quint16),
`frameGeometry`, `normalGeometry` (je `QRect`), Bildschirmnummer (qint32), maximiert, Vollbild (je quint8),
Bildschirmbreite (qint32, ab Version 2), `geometry` (`QRect`, ab Version 3). `QRect` als vier qint32 links, oben,
rechts, unten (`src/corelib/tools/qrect.cpp`, `operator<<`, Zeilen 1227–1236); Breite = rechts − links + 1.

Format der Dock-Anordnung (`src/widgets/widgets/qmainwindow.cpp`, `QMainWindow::saveState`, Zeilen 1203–1212):
`QDataStream` `Qt_5_0`, Kennzeichen `QMainWindowLayout::VersionMarker` = `0xff` (int, `qmainwindowlayout_p.h`
Zeile 581), Version (int, hier `STATE_VERSION`), dann der Zustand des Layouts. Der Rest wird nicht von Hand gelesen,
sondern von Qt selbst (`restoreState`).

Aufruf:  python tools/lage_beschreiben.py [--db <Pfad zur donstv.db>]
"""

from __future__ import annotations

import argparse
import base64
import binascii
import json
import os
import sqlite3
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAYOUT_TAG = "v3:"  # wie ui/main_window.py
KEY_THEME, KEY_GEOMETRY, KEY_STATE = "ui.theme", "ui.geometry", "ui.dock_state"
GEOMETRY_MAGIC = 0x1D9D0CB
STATE_MARKER = 0xFF
# Objektnamen der Docks wie ui/main_window.py (DOCKS, BOT_DOCKS)
DOCK_NAMES = (
    "dock_overlays",
    "dock_sources",
    "dock_properties",
    "dock_control",
    "dock_chat",
    "dock_bot_log",
)


def decode(text: str | None) -> tuple[bytes | None, str]:
    """(Bytes, Beschreibung) aus einem gespeicherten Wert `v3:<base64>` wie `main_window._decode`."""
    if not text:
        return None, "nicht gespeichert"
    if not text.startswith(LAYOUT_TAG):
        return None, f"{len(text)} Zeichen, ohne Marke {LAYOUT_TAG} (wird nicht angewandt)"
    try:
        data = base64.b64decode(text[len(LAYOUT_TAG) :].encode("ascii"), validate=True)
    except (binascii.Error, ValueError, UnicodeEncodeError):
        return None, f"{len(text)} Zeichen, Marke {LAYOUT_TAG}, Inhalt nicht lesbar (kein Base64)"
    return data, f"{len(text)} Zeichen, Marke {LAYOUT_TAG}, {len(data)} Byte"


def _rect(data: bytes, pos: int) -> tuple[str, int]:
    left, top, right, bottom = struct.unpack_from(">iiii", data, pos)
    return f"x {left}, y {top}, {right - left + 1} × {bottom - top + 1} px", pos + 16


def describe_geometry(data: bytes) -> list[str]:
    """Inhalt von `QWidget::saveGeometry` (Format siehe oben). Nicht lesbar → eine Zeile «nicht lesbar»."""
    try:
        magic, major, minor = struct.unpack_from(">IHH", data, 0)
        if magic != GEOMETRY_MAGIC:
            return [f"nicht lesbar (Kennzahl 0x{magic:X} statt 0x{GEOMETRY_MAGIC:X})"]
        lines = [f"Qt-Format Version {major}.{minor}"]
        frame, pos = _rect(data, 8)
        normal, pos = _rect(data, pos)
        screen, maximized, fullscreen = struct.unpack_from(">iBB", data, pos)
        pos += 6
        lines += [f"Rahmen (frameGeometry): {frame}", f"normal (normalGeometry): {normal}"]
        lines.append(f"Bildschirmnummer: {screen}")
        lines.append(
            f"maximiert: {'ja' if maximized else 'nein'}, Vollbild: {'ja' if fullscreen else 'nein'}"
        )
        if major > 1:
            (width,) = struct.unpack_from(">i", data, pos)
            pos += 4
            lines.append(f"Bildschirmbreite beim Speichern: {width} px")
        if major > 2:
            geom, pos = _rect(data, pos)
            lines.append(f"Fenster (geometry): {geom}")
        if pos != len(data):
            lines.append(f"Hinweis: {len(data) - pos} Byte nach dem bekannten Inhalt")
        return lines
    except struct.error:
        return [f"nicht lesbar (nur {len(data)} Byte)"]


def state_header(data: bytes) -> str:
    try:
        marker, version = struct.unpack_from(">ii", data, 0)
    except struct.error:
        return f"nicht lesbar (nur {len(data)} Byte)"
    ok = "passt" if marker == STATE_MARKER else f"falsch, erwartet 0x{STATE_MARKER:X}"
    return f"Kennzeichen 0x{marker & 0xFFFFFFFF:X} ({ok}), Version {version}"


STATE_SCRIPT = r"""
import base64, json, sys
from PyQt6.QtWidgets import QApplication, QDockWidget, QLabel, QMainWindow
from PyQt6.QtCore import QByteArray, Qt
app = QApplication(["lage_beschreiben"])
win = QMainWindow()
win.setDockNestingEnabled(True)
win.setCentralWidget(QLabel())
docks = []
for name in json.loads(sys.argv[2]):
    d = QDockWidget(name, win)
    d.setObjectName(name)
    d.setWidget(QLabel())
    win.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, d)
    docks.append(d)
ok = win.restoreState(QByteArray(base64.b64decode(sys.stdin.read())), int(sys.argv[1]))
pairs = sum(len(win.tabifiedDockWidgets(d)) for d in docks) // 2
groups = []
for d in docks:
    group = sorted([d.objectName()] + [t.objectName() for t in win.tabifiedDockWidgets(d)])
    if len(group) > 1 and group not in groups:
        groups.append(group)
print(json.dumps({
    "ok": ok,
    "pairs": pairs,
    "groups": groups,
    "floating": [d.objectName() for d in docks if d.isFloating()],
    "visible": [d.objectName() for d in docks if not d.isHidden()],
}))
"""


def describe_state(data: bytes, version: int) -> list[str]:
    """Dock-Anordnung über Qt selbst (eigener Prozess, offscreen). Ohne PyQt6: eine Zeile mit dem Grund."""
    lines = [state_header(data)]
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
    try:
        out = subprocess.run(
            [sys.executable, "-c", STATE_SCRIPT, str(version), json.dumps(DOCK_NAMES)],
            input=base64.b64encode(data).decode("ascii"),
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
            check=False,
        )
        info = json.loads(out.stdout.strip().splitlines()[-1])
    except (subprocess.TimeoutExpired, json.JSONDecodeError, IndexError, OSError) as e:
        return [*lines, f"Inhalt über Qt nicht lesbar ({type(e).__name__})"]
    if not info["ok"]:
        return [*lines, f"restoreState mit Version {version}: abgelehnt (wird nicht angewandt)"]
    groups = "; ".join(" + ".join(g) for g in info["groups"]) or "keine"
    return [
        *lines,
        f"restoreState mit Version {version}: angenommen",
        f"Reiterpaare: {info['pairs']} (Gruppen: {groups})",
        f"schwebende Docks: {len(info['floating'])} ({', '.join(info['floating']) or 'keine'})",
        f"sichtbare Docks: {len(info['visible'])} ({', '.join(info['visible']) or 'keine'})",
    ]


def user_db() -> Path:
    sys.path.insert(0, str(ROOT / "src"))
    from donstv_studio.core.config import Paths

    return Paths.from_xdg().db_file


def read_db(db: Path) -> dict:
    """Nur lesend: Einstellungen für Lage und Theme, Anzahl Overlays und Quellen."""
    con = sqlite3.connect(f"{db.as_uri()}?mode=ro", uri=True)
    try:
        rows = con.execute(
            "SELECT key, value FROM settings WHERE key IN (?, ?, ?)",
            (KEY_THEME, KEY_GEOMETRY, KEY_STATE),
        ).fetchall()
        overlays = con.execute("SELECT COUNT(*) FROM overlays").fetchone()[0]
        sources = con.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
    finally:
        con.close()
    return {**dict(rows), "overlays": overlays, "sources": sources}


def describe(db: Path, state_version: int = 3) -> list[str]:
    values = read_db(db)
    lines = [f"Theme: {values.get(KEY_THEME) or 'nicht gespeichert'}"]
    lines.append(f"Overlays: {values['overlays']}, Quellen: {values['sources']}")
    geometry, text = decode(values.get(KEY_GEOMETRY))
    lines.append(f"Fensterlage ({KEY_GEOMETRY}): {text}")
    if geometry is not None:
        lines += [f"  {line}" for line in describe_geometry(geometry)]
    state, text = decode(values.get(KEY_STATE))
    lines.append(f"Dock-Anordnung ({KEY_STATE}): {text}")
    if state is not None:
        lines += [f"  {line}" for line in describe_state(state, state_version)]
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", type=Path, help="Datenbank (Vorgabe: die des Nutzers, nur lesend)")
    args = parser.parse_args()
    db = args.db or user_db()
    if not db.exists():
        print(f"keine Datenbank unter {db}")
        return 1
    for line in describe(db):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
