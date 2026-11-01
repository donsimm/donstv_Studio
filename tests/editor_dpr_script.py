"""Unterprozess für tests/test_editor_web.py: Vorschau bei devicePixelRatio 2 (QT_SCALE_FACTOR=2).

Gibt eine JSON-Zeile aus. Prüft, dass bei 100 % ein Overlay-Pixel genau ein physisches Bildschirmpixel ist.
"""

import json
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "src"))


def step(text: str) -> None:
    """Fortschritt in stderr, sofort geschrieben: Bei einem Absturz zeigt die letzte Zeile, wie weit es kam."""
    print(f"Schritt: {text}", file=sys.stderr, flush=True)


step("Start, Import PyQt6")
from PyQt6.QtCore import PYQT_VERSION_STR, QT_VERSION_STR
from PyQt6.QtWidgets import QApplication

step(f"Qt {QT_VERSION_STR}, PyQt6 {PYQT_VERSION_STR}; Import QtWebEngine")
from donstv_studio.ui import preview_web  # noqa: F401  (vor der QApplication)

step("QApplication anlegen")
app = QApplication(["donstv-dpr"])
import os

from donstv_studio.core.config import Paths
from donstv_studio.ui.backend import DirectRunner
from donstv_studio.ui.editor_model import EditorModel
from donstv_studio.ui.editor_prefs import EditorPrefs
from donstv_studio.ui.editor_view import EditorView
from editor_web_scene import RED_BOX, CoreBackend, RunningService, build_scene
from helpers import free_port, pump


def js(web, code):
    box = []
    web.page().runJavaScript(code, 0, box.append)
    end = time.time() + 15
    while not box and time.time() < end:
        app.processEvents()
        time.sleep(0.005)
    return box[0] if box else None


paths = Paths.under(Path(sys.argv[1]))
exit_code = 0
step("Kern-Dienst starten")
svc = RunningService(paths, free_port(), free_port()).start()
try:
    backend = CoreBackend(svc.base_url, paths.token_file)
    ids = build_scene(backend, svc.overlay_port)
    model = EditorModel(backend, DirectRunner(), None)
    model.load()
    model.select_overlay(ids["overlay"])
    if os.environ.get("DONSTV_DPR_SELFTEST_FAIL") == "1":  # nur für den Test der Fehlermeldung
        raise RuntimeError("absichtlicher Fehler (Selbsttest)")
    step("Editor anlegen und anzeigen")
    view = EditorView(model, EditorPrefs())
    view.resize(1100, 700)  # logisch; physisch 2200 × 1400
    view.show()
    view.set_zoom(1.0)
    step("auf erstes Zeichnen der Overlay-Seite warten (QtWebEngine)")
    end = time.time() + 30
    while (
        time.time() < end
        and not (js(view.web, "window.__overlay && window.__overlay.renders") or 0) > 0
    ):
        pump(100)
    pump(1000)
    step("Bild der Bühne aufnehmen")
    t = view.transform()
    img = view.stage.grab().toImage()
    x, y, w, h = (RED_BOX[k] for k in ("x", "y", "width", "height"))

    def px(
        ox, oy
    ):  # Overlay-Pixel -> physisches Pixel im Bild der Bühne (Faktor 2 gegenüber logisch, bei 100 % genau 1:1)
        return img.pixelColor(ox, oy).name()

    out = {
        "dpr": view.dpr(), "k": t.k, "web_zoom": view.web.zoomFactor(),
        "stage_logical": [view.stage.width(), view.stage.height()],
        "image_physical": [img.width(), img.height()],
        "red_inside": px(x, y), "red_outside_left": px(x - 1, y), "red_outside_top": px(x, y - 1),
        "red_right_last": px(x + w - 1, y + h - 1), "red_right_next": px(x + w, y + h - 1),
    }  # fmt: skip
    print(json.dumps(out), flush=True)  # vor os._exit: sonst kann die Zeile im Puffer bleiben
    step("Ergebnis geschrieben")
    view.close()
except BaseException:  # noqa: BLE001 - jede Ausnahme muss vor os._exit sichtbar werden
    # Ohne diesen Block verschluckt os._exit unten jede Ausnahme: Der Prozess endete mit Exit-Code 0 und leerer
    # Ausgabe (Befund vom Laptop, P06c). Jetzt: Aufrufliste in stderr und Exit-Code 1.
    traceback.print_exc()
    exit_code = 1
finally:
    svc.stop()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(exit_code)  # Chromium-Prozesse nicht abwarten
