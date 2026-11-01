"""Startprüfung der echten Oberfläche mit echtem Fenstersystem (P06d2, F-01, CLAUDE.md Regel 16).

Startet mehrmals (Vorgabe 20) je einen eigenen Prozess mit `python -X faulthandler`. Jeder Lauf:
1. startet einen Kern-Dienst als **eigenen Prozess** (wie auf dem Laptop) in einem leeren Ordner
   (eigene Ports, eigenes Token, nichts vom Nutzer wird berührt),
2. legt bei der Variante `schmal` vorher eine gespeicherte Fensterlage ab, die schmaler ist als die
   Mindestbreite des Fensters (so wie P08 sie gespeichert hätte, siehe `save_narrow_geometry`),
3. startet die echte Oberfläche über `donstv_studio.ui.main.main()` mit `QT_QPA_PLATFORM=xcb`
   (nicht `offscreen`); die Oberfläche beendet sich nach `DONSTV_AUTOQUIT_MS` selbst,
4. endet normal (kein os._exit).

Fenstersystem: das vorhandene `DISPLAY`. Ohne `DISPLAY` startet das Skript ein eigenes `Xvfb` (falls
installiert) und schreibt das deutlich in die Ausgabe; ohne beides bricht es mit Exit-Code 2 ab.

Varianten (`--variante`):
- `standard`        leere Daten
- `schmal`          gespeicherte Fensterlage schmaler als die Mindestbreite
- `aus=<Liste>`     wie `standard`, mit `DONSTV_OFF=<Liste>` (Diagnose-Schalter, siehe `ui/diagnose.py`);
                    mehrere Teile mit Komma, z. B. `aus=perf_equalize,min_width`

Ausgabe: je Lauf der Exit-Code mit Deutung und die letzten 15 Zeilen von stderr, am Ende
«N von M Läufen mit Exit-Code 0». Exit-Code dieses Skripts: 0, wenn alle Läufe mit 0 enden, sonst 1.

Aufruf:  python tools/start_pruefung.py [--laeufe 20] [--variante standard] [--autoquit-ms 4000]
         (oder tools/start_pruefung.sh)
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
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

CORE_SCRIPT = r"""
import asyncio, sys
from donstv_studio.core.config import Paths
from donstv_studio.core.service import Service
paths = Paths.from_xdg()
paths.ensure()
asyncio.run(Service(paths, port=int(sys.argv[1]), overlay_port=int(sys.argv[2])).run())
"""


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
    return env


# --- Kern-Dienst als eigener Prozess -------------------------------------------------------------
def start_core(env: dict[str, str], port: int, overlay_port: int) -> subprocess.Popen:
    proc = subprocess.Popen(
        [sys.executable, "-c", CORE_SCRIPT, str(port), str(overlay_port)],
        env=env,
        cwd=str(ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    from donstv_studio.core.config import Paths
    from donstv_studio.ui.backend import CoreBackend

    old = {k: os.environ.get(k) for k in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME")}
    os.environ.update({k: env[k] for k in old})
    try:
        token_file = Paths.from_xdg().token_file
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
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


# --- Variante «schmal»: Fensterlage wie aus P08 ---------------------------------------------------
def save_narrow_geometry(port: int) -> int:
    """Eigener Prozess: legt eine gespeicherte Fensterlage schmaler als die Mindestbreite im Kern ab.

    `MainWindow.layout_values()` speichert `saveGeometry()` und `saveState(STATE_VERSION)` mit der Marke
    `LAYOUT_TAG` (beides seit P08 unverändert). Das Fenster wird hier mit aufgehobener Mindestbreite auf
    `NARROW_SIZE` gebracht, gezeigt und gespeichert; genau so läge eine Lage aus P08 im Kern.
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
    window.resize(*NARROW_SIZE)
    for _ in range(20):
        app.processEvents()
        time.sleep(0.02)
    values = window.layout_values()
    width = window.width()
    ok = core.save_settings_blocking(values)
    print(
        f"gespeicherte Fensterlage: {width} px breit, {len(values[KEY_GEOMETRY])} Zeichen, "
        f"gespeichert: {bool(ok)}",
        file=sys.stderr,
    )
    window.close()
    from donstv_studio.ui import main as ui_main

    ui_main.shutdown(app, window)
    return 0 if ok and width < 1100 else 4


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


# --- Steuerung: mehrere Läufe -------------------------------------------------------------------
def run_child(args: list[str], env: dict[str, str]) -> tuple[int, str]:
    cmd = [sys.executable, "-X", "faulthandler", str(Path(__file__).resolve()), *args]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=RUN_TIMEOUT,
            env=env,
            cwd=str(ROOT),
            check=False,
        )
        return proc.returncode, proc.stderr
    except subprocess.TimeoutExpired as e:
        err = e.stderr.decode(errors="replace") if isinstance(e.stderr, bytes) else (e.stderr or "")
        return -9999, err + f"\nZeitüberschreitung nach {RUN_TIMEOUT} s"


def parse_variant(text: str) -> tuple[str, str]:
    """`standard`, `schmal` oder `aus=<Liste>` → (Name, Wert für DONSTV_OFF)."""
    if text in ("standard", "schmal"):
        return text, ""
    if text.startswith("aus="):
        from donstv_studio.ui import diagnose

        parts = [p.strip() for p in text[4:].split(",") if p.strip()]
        unknown = [p for p in parts if p not in diagnose.SWITCHES]
        if not parts or unknown:
            raise SystemExit(
                f"Unbekannte Teile {unknown or '(keine)'}; erlaubt: {', '.join(diagnose.SWITCHES)}"
            )
        return "aus", ",".join(parts)
    raise SystemExit(f"Unbekannte Variante «{text}»: standard, schmal oder aus=<Liste>")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--laeufe", type=int, default=20)
    parser.add_argument("--variante", default="standard")
    parser.add_argument("--autoquit-ms", type=int, default=AUTOQUIT_MS)
    parser.add_argument("--lauf", type=int, metavar="PORT", help=argparse.SUPPRESS)  # intern
    parser.add_argument("--geometrie", type=int, metavar="PORT", help=argparse.SUPPRESS)  # intern
    args = parser.parse_args()
    if args.lauf:
        return single_run(args.lauf)
    if args.geometrie:
        return save_narrow_geometry(args.geometrie)

    sys.path.insert(0, str(ROOT / "src"))
    name, off = parse_variant(args.variante)
    xvfb, display = ensure_display()
    from PyQt6.QtCore import PYQT_VERSION_STR, QT_VERSION_STR

    print(
        f"== Startprüfung: Variante {args.variante}, {args.laeufe} Läufe, Qt {QT_VERSION_STR}, "
        f"PyQt6 {PYQT_VERSION_STR}, QT_QPA_PLATFORM=xcb, {display}, "
        f"DONSTV_AUTOQUIT_MS={args.autoquit_ms}"
    )
    sys.stdout.flush()
    codes: list[int] = []
    try:
        for n in range(1, args.laeufe + 1):
            with tempfile.TemporaryDirectory(prefix="donstv-start-") as tmp:
                env = run_env(Path(tmp))
                env["QT_QPA_PLATFORM"] = "xcb"
                env["DONSTV_AUTOQUIT_MS"] = str(args.autoquit_ms)
                env["DISPLAY"] = os.environ["DISPLAY"]
                if off:
                    env["DONSTV_OFF"] = off
                else:
                    env.pop("DONSTV_OFF", None)
                port, overlay_port = free_port(), free_port()
                start = time.monotonic()
                prefix = ""
                try:
                    core = start_core(env, port, overlay_port)
                except RuntimeError as e:
                    codes.append(-9998)
                    print(f"== Lauf {n}: Kern-Dienst startet nicht ({e})")
                    continue
                try:
                    if name == "schmal":
                        gcode, gerr = run_child(["--geometrie", str(port)], env)
                        tail = gerr.splitlines()[-TAIL_LINES:]
                        prefix = "".join(f"[Fensterlage] {line}\n" for line in tail)
                        if gcode != 0:
                            prefix += f"[Fensterlage] Exit-Code {gcode}: Lage nicht abgelegt\n"
                    code, err = run_child(["--lauf", str(port)], env)
                finally:
                    stop_core(core)
            codes.append(code)
            label = "Zeitüberschreitung" if code == -9999 else describe(code)
            print(f"== Lauf {n}: Exit-Code {code} ({label}), {time.monotonic() - start:.1f} s")
            print(f"   letzte {TAIL_LINES} Zeilen von stderr:")
            for line in prefix.splitlines() + err.splitlines()[-TAIL_LINES:]:
                print(f"   | {line}")
            sys.stdout.flush()
    finally:
        if xvfb is not None:
            xvfb.terminate()
            xvfb.wait(10)
    ok = sum(1 for c in codes if c == 0)
    print(
        f"== Zusammenfassung Startprüfung (Variante {args.variante}): {ok} von {len(codes)} Läufen "
        f"mit Exit-Code 0 (Exit-Codes: {codes})"
    )
    return 0 if ok == len(codes) and codes else 1


if __name__ == "__main__":
    sys.exit(main())
