"""Unterprozess für tests/test_editor_web.py: Vorschau bei devicePixelRatio 2 (QT_SCALE_FACTOR=2).

Gibt eine JSON-Zeile aus. Prüft, dass bei 100 % ein Overlay-Pixel genau ein physisches Bildschirmpixel ist.
"""

import json
import socket
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "src"))

from PyQt6.QtWidgets import QApplication

from donstv_studio.ui import preview_web  # noqa: F401  (vor der QApplication)

app = QApplication(["donstv-dpr"])
import os

from donstv_studio.core.config import Paths
from donstv_studio.ui.backend import DirectRunner
from donstv_studio.ui.editor_model import EditorModel
from donstv_studio.ui.editor_prefs import EditorPrefs
from donstv_studio.ui.editor_view import EditorView
from editor_web_scene import RED_BOX, CoreBackend, RunningService, build_scene


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def pump(ms: int) -> None:
    end = time.time() + ms / 1000
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def js(web, code):
    box = []
    web.page().runJavaScript(code, 0, box.append)
    end = time.time() + 15
    while not box and time.time() < end:
        app.processEvents()
        time.sleep(0.005)
    return box[0] if box else None


paths = Paths.under(Path(sys.argv[1]))
svc = RunningService(paths, free_port(), free_port()).start()
try:
    backend = CoreBackend(svc.base_url, paths.token_file)
    ids = build_scene(backend, svc.overlay_port)
    model = EditorModel(backend, DirectRunner(), None)
    model.load()
    model.select_overlay(ids["overlay"])
    view = EditorView(model, EditorPrefs())
    view.resize(1100, 700)  # logisch; physisch 2200 × 1400
    view.show()
    view.set_zoom(1.0)
    end = time.time() + 30
    while time.time() < end and not (js(view.web, "window.__overlay && window.__overlay.renders") or 0) > 0:
        pump(100)
    pump(1000)
    t = view.transform()
    img = view.stage.grab().toImage()
    x, y, w, h = (RED_BOX[k] for k in ("x", "y", "width", "height"))

    def px(ox, oy):  # Overlay-Pixel -> physisches Pixel im Bild der Bühne (Faktor 2 gegenüber logisch, bei 100 % genau 1:1)
        return img.pixelColor(ox, oy).name()

    out = {
        "dpr": view.dpr(), "k": t.k, "web_zoom": view.web.zoomFactor(),
        "stage_logical": [view.stage.width(), view.stage.height()],
        "image_physical": [img.width(), img.height()],
        "red_inside": px(x, y), "red_outside_left": px(x - 1, y), "red_outside_top": px(x, y - 1),
        "red_right_last": px(x + w - 1, y + h - 1), "red_right_next": px(x + w, y + h - 1),
    }  # fmt: skip
    print(json.dumps(out))
    view.close()
finally:
    svc.stop()
    os._exit(0)  # Chromium-Prozesse nicht abwarten
