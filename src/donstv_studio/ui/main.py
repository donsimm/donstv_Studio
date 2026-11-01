"""Einstiegspunkt `donstv-studio`: startet die Oberfläche und verbindet sich mit dem Kern-Dienst."""

from __future__ import annotations

import sys


def main() -> int:
    try:
        from PyQt6.QtWidgets import QApplication
    except ImportError as e:  # PyQt6 ist nur ein Extra («ui»)
        print(
            "donstv-studio braucht PyQt6 (Debian: python3-pyqt6 und python3-pyqt6.qtwebengine; "
            f"sonst pip install 'donstv_studio[ui]'). Fehler: {e}",
            file=sys.stderr,
        )
        return 1
    from donstv_studio.ui.core_link import CoreLink
    from donstv_studio.ui.main_window import MainWindow

    app = QApplication(sys.argv[:1])
    app.setApplicationName("donstv_Studio")
    core = CoreLink()
    window = MainWindow(core)
    saved = core.fetch_settings_blocking()  # vor dem Anzeigen, damit nichts flackert
    if saved is not None:
        window.apply_settings(saved)
    core.start()
    window.show()
    code = app.exec()
    core.stop()
    return code
