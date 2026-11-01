"""Diagnose: zeigt jede Widget-Klasse des Editors einzeln in einem eigenen Prozess und meldet, welche abstürzt.

Aufruf: python tools/diagnose_qt.py   (im Ordner des Projekts, mit aktivierter Umgebung)
"""

import os
import subprocess
import sys

CASES = [
    "plain_toolbutton", "IconButton", "ButtonBar", "ListWithHint", "SourceList", "OverlaysDock",
    "SourcesDock", "PropertiesDock", "ControlDock", "EditorView", "MainWindow",
    "MainWindow_mit_Daten", "MainWindow_CoreLink", "MainWindow_CoreLink_gestartet", "MainWindow_Signale",
    "CL:ohne_nichts", "CL:ohne_stylesheet", "CL:ohne_editor_einbettung", "CL:ohne_modell_load", "CL:ohne_prefs_und_hilfslinien",
    "CL:direkter_runner", "CL:ohne_statuszeilen_widgets", "CL:ohne_dock_inhalt", "CL:ohne_modell_signale",
    "MainWindow_Banner", "MainWindow_Banner_Daten", "MainWindow_leer", "MainWindow_Thread_leer", "MainWindow_Thread_Daten",
]  # fmt: skip

CHILD = r"""
import sys
sys.path.insert(0, "src")
from donstv_studio.ui import preview_web  # noqa: F401
from PyQt6.QtCore import QTimer, qVersion, PYQT_VERSION_STR
from PyQt6.QtWidgets import QApplication, QToolButton, QWidget, QVBoxLayout
app = QApplication(["diag"])
case = sys.argv[1]
from donstv_studio.ui.backend import DirectRunner
from donstv_studio.ui import editor_docks as d
from donstv_studio.ui.editor_model import EditorModel
from donstv_studio.ui.editor_prefs import EditorPrefs
m = EditorModel(None, DirectRunner()); p = EditorPrefs()
host = QWidget(); lay = QVBoxLayout(host)
if case == "plain_toolbutton": w = QToolButton(); w.setText("x")
elif case == "IconButton": w = d.IconButton("plus", "Test")
elif case == "ButtonBar":
    w = d.ButtonBar(); w.add("plus", "a"); w.add("trash", "b"); w.finish()
elif case == "ListWithHint":
    from PyQt6.QtWidgets import QListWidget
    w = d._ListWithHint(QListWidget(), "Hinweis")
elif case == "SourceList": w = d.SourceList()
elif case == "OverlaysDock": w = d.OverlaysDock(m).body
elif case == "SourcesDock": w = d.SourcesDock(m).body
elif case == "PropertiesDock": w = d.PropertiesDock(m).body
elif case == "ControlDock": w = d.ControlDock(m, p).body
elif case == "EditorView":
    from donstv_studio.ui.editor_view import EditorView
    w = EditorView(m, p)
elif case == "MainWindow":
    from PyQt6.QtCore import QObject, pyqtSignal
    class C(QObject):
        connected = pyqtSignal(); unreachable = pyqtSignal(str, float); status_changed = pyqtSignal(str, str, str)
        statuses_loaded = pyqtSignal(str); settings_loaded = pyqtSignal(str)
        def save_setting(self, *a): pass
        def save_settings_blocking(self, *a, **k): return True
    from donstv_studio.ui.main_window import MainWindow
    w = MainWindow(C()); host = w
elif case.startswith("CL:"):
    patch = case[3:]
    import donstv_studio.ui.main_window as mw
    from donstv_studio.ui import theme as _theme
    from donstv_studio.ui.editor_model import EditorModel as _EM
    from donstv_studio.ui.editor_prefs import EditorPrefs as _EP
    from donstv_studio.ui.widgets import PreviewArea as _PA
    if patch == "ohne_stylesheet": _theme.stylesheet = lambda t: ""
    elif patch == "ohne_editor_einbettung": _PA.set_editor = lambda self, e: None
    elif patch == "ohne_modell_load": _EM.load = lambda self: None
    elif patch == "ohne_prefs_und_hilfslinien": _EP.load = lambda self, v: None; _EM.load_guides = lambda self, v: None
    elif patch == "direkter_runner": mw.TaskRunner = DirectRunner
    elif patch == "ohne_statuszeilen_widgets":
        _orig = mw.MainWindow._show_pointer; mw.MainWindow._show_pointer = lambda self, *p: None
        mw.MainWindow._show_zoom = lambda self, z, f: None
    elif patch == "ohne_dock_inhalt":
        from PyQt6.QtWidgets import QFrame, QLabel
        class _Stub:
            def __init__(self, *a, **k):
                self.body = QFrame(); self.body.setObjectName("dockbody"); QLabel("x", self.body)
                from PyQt6.QtCore import QObject, pyqtSignal
                self.copied = type("S", (), {"connect": lambda *a: None})()
            def apply_theme(self, n): pass
        mw.OverlaysDock = mw.SourcesDock = mw.PropertiesDock = _Stub
        mw.ControlDock = lambda model, prefs: _Stub()
    elif patch == "ohne_modell_signale":
        from PyQt6.QtCore import QObject
        for _n in ("overlays_changed", "current_changed", "meta_changed", "sources_changed", "box_changed", "selection_changed",
                   "guides_changed", "history_changed"):
            pass  # Signale sind Klassenattribute; unten werden die Verbindungen der Ansicht gekappt
        from donstv_studio.ui.editor_view import EditorView as _EV
        _EV._on_overlay = lambda self, i: None; _EV._on_meta = lambda self: None
    from donstv_studio.ui.core_link import CoreLink
    c = CoreLink(); w = mw.MainWindow(c); host = w
    saved = c.fetch_settings_blocking()
    if saved is not None: w.apply_settings(saved)
    c.start()
elif case.startswith("MainWindow_"):
    from PyQt6.QtCore import QObject, pyqtSignal
    from donstv_studio.ui.main_window import MainWindow
    if case in ("MainWindow_mit_Daten", "MainWindow_Banner", "MainWindow_Banner_Daten", "MainWindow_leer",
                "MainWindow_Thread_leer", "MainWindow_Thread_Daten"):
        with_data = case in ("MainWindow_mit_Daten", "MainWindow_Banner_Daten", "MainWindow_Thread_Daten")
        class B:
            def list_overlays(self):
                if not with_data:
                    return []
                src = lambda i, k: {"id": f"s{i}", "kind": k, "x": 10 * i, "y": 5, "width": 200, "height": 80, "rotation": 0.0,
                                    "z": i, "visible": True, "props": {"text": "Hallo"} if k == "text" else {}}
                return [{"id": "o1", "name": "Test", "width": 1920, "height": 1080, "output": "browser",
                         "output_status": "verfügbar", "token": "t", "url": "http://127.0.0.1:1/o/o1?t=t",
                         "sources": [src(0, "text"), src(1, "image")]}]
        from donstv_studio.ui.backend import TaskRunner
        class C(QObject):
            connected = pyqtSignal(); unreachable = pyqtSignal(str, float); status_changed = pyqtSignal(str, str, str)
            statuses_loaded = pyqtSignal(str); settings_loaded = pyqtSignal(str)
            backend = B()
            runner = TaskRunner() if "Thread" in case else DirectRunner()
            def save_setting(self, *a): pass
            def save_settings_blocking(self, *a, **k): return True
        c = C(); w = MainWindow(c); host = w
        w.show()
        if case == "MainWindow_Banner" or case == "MainWindow_Banner_Daten":
            c.unreachable.emit("Der Kern-Dienst antwortet nicht", 5.0)
        if case != "MainWindow_Banner":
            c.connected.emit(); c.settings_loaded.emit("{}")
    else:
        from donstv_studio.ui.core_link import CoreLink
        c = CoreLink(); w = MainWindow(c); host = w
        saved = c.fetch_settings_blocking()
        if saved is not None: w.apply_settings(saved)
        if case in ("MainWindow_CoreLink_gestartet", "MainWindow_Signale"): c.start()
        if case == "MainWindow_Signale":
            from donstv_studio.ui.signals import SignalBridge
            bridge = SignalBridge(parent=app)
if case != "MainWindow" and not case.startswith(("MainWindow_", "CL:")):
    lay.addWidget(w)
host.resize(500, 300); host.show()
QTimer.singleShot(1200, app.quit)
app.exec()
print("OK", qVersion(), PYQT_VERSION_STR)
"""


def main() -> int:
    env = {**os.environ}
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=False).stdout.strip()
    print(f"Stand des Programms: {rev}")
    bad = 0
    for case in CASES:
        r = subprocess.run([sys.executable, "-c", CHILD, case], capture_output=True, text=True, timeout=120, env=env, check=False)
        ok = r.returncode == 0 and "OK" in r.stdout
        bad += not ok
        print(f"{'OK       ' if ok else 'ABSTURZ  '} {case}  {r.stdout.strip() if ok else '(Rückgabecode ' + str(r.returncode) + ')'}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
