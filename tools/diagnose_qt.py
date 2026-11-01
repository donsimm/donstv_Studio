"""Diagnose: zeigt jede Widget-Klasse des Editors einzeln in einem eigenen Prozess und meldet, welche abstürzt.

Aufruf: python tools/diagnose_qt.py   (im Ordner des Projekts, mit aktivierter Umgebung)
"""

import os
import subprocess
import sys

CASES = [
    "plain_toolbutton", "IconButton", "ButtonBar", "ListWithHint", "SourceList", "OverlaysDock",
    "SourcesDock", "PropertiesDock", "ControlDock", "EditorView", "MainWindow",
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
        statuses_loaded = pyqtSignal(dict); settings_loaded = pyqtSignal(dict)
        def save_setting(self, *a): pass
        def save_settings_blocking(self, *a, **k): return True
    from donstv_studio.ui.main_window import MainWindow
    w = MainWindow(C()); host = w
if case != "MainWindow":
    lay.addWidget(w)
host.resize(500, 300); host.show()
QTimer.singleShot(1200, app.quit)
app.exec()
print("OK", qVersion(), PYQT_VERSION_STR)
"""


def main() -> int:
    env = {**os.environ}
    bad = 0
    for case in CASES:
        r = subprocess.run([sys.executable, "-c", CHILD, case], capture_output=True, text=True, timeout=120, env=env, check=False)
        ok = r.returncode == 0 and "OK" in r.stdout
        bad += not ok
        print(f"{'OK       ' if ok else 'ABSTURZ  '} {case}  {r.stdout.strip() if ok else '(Rückgabecode ' + str(r.returncode) + ')'}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
