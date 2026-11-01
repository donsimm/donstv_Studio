"""Prüfung des Beendens der echten Oberfläche mit Vorschau (P06c, F-01).

Startet mehrmals (Standard 5) je einen eigenen Prozess mit `python -X faulthandler`. Jeder Lauf:
1. startet einen Kern-Dienst in einem leeren Ordner (eigene Ports, eigenes Token, nichts vom Nutzer wird berührt),
2. legt über die Schnittstelle ein Overlay mit einer Textquelle an,
3. startet die echte Oberfläche über `donstv_studio.ui.main.main()` (offscreen, mit QtWebEngine-Vorschau),
4. wählt das Overlay, wartet, bis die Vorschau-Seite gezeichnet hat, und schliesst das Fenster,
5. endet normal (kein os._exit), damit das Aufräumen von Qt und Python beim Beenden mitgeprüft wird.

Ausgabe: je Lauf der Exit-Code und die letzten Zeilen von stderr, am Ende eine Zusammenfassung.
Exit-Code dieses Skripts: 0, wenn alle Läufe mit 0 enden, sonst 1.

Aufruf:  python tools/beenden_pruefung.py [--laeufe 5]   (oder tools/beenden_pruefung.sh)
"""

from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TAIL_LINES = 15
RUN_TIMEOUT = 180  # Sekunden je Lauf
PROFILE_WARNING = "Release of profile requested but WebEnginePage still not deleted"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def step(text: str) -> None:
    print(f"Schritt: {text}", file=sys.stderr, flush=True)


# --- ein Lauf (im eigenen Prozess) -------------------------------------------------------------
def single_run(base: Path) -> int:
    """Ein Lauf; Rückgabe ist der Exit-Code von `donstv_studio.ui.main.main()`."""
    import asyncio
    import threading

    # Alles in den leeren Ordner: Einstellungen, Datenbank, Token, Protokoll
    os.environ["XDG_CONFIG_HOME"] = str(base / "config")
    os.environ["XDG_DATA_HOME"] = str(base / "data")
    os.environ["XDG_STATE_HOME"] = str(base / "state")
    port, overlay_port = free_port(), free_port()
    os.environ["DONSTV_CORE_PORT"] = str(port)
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox --disable-gpu")

    from donstv_studio.core.config import Paths
    from donstv_studio.core.service import Service
    from donstv_studio.ui.backend import CoreBackend

    paths = Paths.from_xdg()
    step("Kern-Dienst starten")
    svc = Service(paths, port=port, overlay_port=overlay_port)
    ready = threading.Event()
    holder: dict = {}

    def runner() -> None:
        async def run() -> None:
            holder["loop"] = asyncio.get_running_loop()
            task = asyncio.create_task(svc.run())
            await svc.started.wait()
            ready.set()
            await task

        asyncio.run(run())

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    if not ready.wait(30):
        print("Kern-Dienst startet nicht", file=sys.stderr)
        return 2

    step("Overlay anlegen")
    backend = CoreBackend(f"http://127.0.0.1:{port}", paths.token_file)
    backend._call("PUT", "/settings/overlay.port", {"value": str(overlay_port)})
    overlay = backend.create_overlay("Beenden-Prüfung")
    backend.add_source(overlay["id"], "text", x=100, y=100, width=400, height=80, props={"text": "Prüfung"})

    from PyQt6.QtCore import PYQT_VERSION_STR, QT_VERSION_STR, QTimer
    from PyQt6.QtWidgets import QApplication

    from donstv_studio.ui import main as ui_main
    from donstv_studio.ui.main_window import MainWindow

    step(f"Oberfläche starten (Qt {QT_VERSION_STR}, PyQt6 {PYQT_VERSION_STR})")
    state = {"deadline": time.monotonic() + 60, "rendered": False}
    original_show = MainWindow.show

    def show_and_drive(window: MainWindow) -> None:
        original_show(window)
        timer = QTimer(window)

        def tick() -> None:
            model = window.model
            if model.current_id != overlay["id"] and model.overlay(overlay["id"]) is not None:
                step("Overlay wählen")
                model.select_overlay(overlay["id"])
            web = getattr(window.editor, "web", None)
            if web is not None and not state["rendered"]:
                web.page().runJavaScript(
                    "!!(window.__overlay && window.__overlay.renders > 0)",
                    0,
                    lambda ok: state.update(rendered=bool(ok)),
                )
            if state["rendered"] or time.monotonic() > state["deadline"]:
                timer.stop()
                step("Vorschau gezeichnet" if state["rendered"] else "Zeitüberschreitung: Vorschau zeichnet nicht")
                step("Fenster schliessen")
                window.close()
                QApplication.quit()

        timer.timeout.connect(tick)
        timer.start(200)

    MainWindow.show = show_and_drive  # nur in diesem Prozess
    code = ui_main.main()
    step(f"main() beendet mit {code}; Vorschau gezeichnet: {state['rendered']}")
    loop = holder.get("loop")
    if loop is not None:
        loop.call_soon_threadsafe(svc.stop_event.set)
    thread.join(20)
    step("Kern-Dienst gestoppt; Python beendet sich jetzt normal")
    if not state["rendered"]:
        return 3
    return code


# --- Steuerung: mehrere Läufe -------------------------------------------------------------------
def describe(code: int) -> str:
    if code == 0:
        return "in Ordnung"
    if code < 0:
        return f"Absturz durch Signal {-code}" + (" (Speicherzugriffsfehler)" if code == -11 else "")
    if code == 139:
        return "Speicherzugriffsfehler"
    if code == 3:
        return "Vorschau hat nicht gezeichnet"
    return "Fehler"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--laeufe", type=int, default=5)
    parser.add_argument("--lauf", metavar="ORDNER", help=argparse.SUPPRESS)  # intern: ein Lauf
    args = parser.parse_args()
    if args.lauf:
        return single_run(Path(args.lauf))

    env = {**os.environ, "QT_QPA_PLATFORM": os.environ.get("QT_QPA_PLATFORM", "offscreen")}
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(ROOT / "src"), env.get("PYTHONPATH")]))
    codes, warnings = [], []
    for n in range(1, args.laeufe + 1):
        with tempfile.TemporaryDirectory(prefix="donstv-beenden-") as tmp:
            cmd = [sys.executable, "-X", "faulthandler", str(Path(__file__).resolve()), "--lauf", tmp]
            start = time.monotonic()
            try:
                proc = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=RUN_TIMEOUT, env=env, cwd=str(ROOT), check=False
                )
                code, err = proc.returncode, proc.stderr
            except subprocess.TimeoutExpired as e:
                code = -9999
                err = (e.stderr or b"").decode(errors="replace") if isinstance(e.stderr, bytes) else (e.stderr or "")
                err += f"\nZeitüberschreitung nach {RUN_TIMEOUT} s"
        codes.append(code)
        label = "Zeitüberschreitung" if code == -9999 else describe(code)
        warn = err.count(PROFILE_WARNING)
        warnings.append(warn)
        print(f"== Lauf {n}: Exit-Code {code} ({label}), {time.monotonic() - start:.1f} s, "
              f"Meldung «WebEnginePage still not deleted»: {warn} Mal")
        print(f"   letzte {TAIL_LINES} Zeilen von stderr:")
        for line in err.splitlines()[-TAIL_LINES:]:
            print(f"   | {line}")
        sys.stdout.flush()
    ok = sum(1 for c in codes if c == 0)
    print(f"== Zusammenfassung: {ok} von {len(codes)} Läufen mit Exit-Code 0 (Exit-Codes: {codes}); "
          f"Meldung «WebEnginePage still not deleted» insgesamt {sum(warnings)} Mal")
    return 0 if ok == len(codes) else 1


if __name__ == "__main__":
    sys.exit(main())
