"""Einstiegspunkt `donstv-studio`: startet die Oberfläche und verbindet sich mit dem Kern-Dienst."""

from __future__ import annotations

import os
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

    # Unter Linux X11 (xcb, auf Wayland über XWayland) vor Wayland: CLAUDE.md nennt X11 als Zielsystem, und nur dort
    # lassen sich Fensterlage und schwebende Docks sicher speichern und wiederherstellen. Ein vom Nutzer
    # gesetztes QT_QPA_PLATFORM gilt weiter. Fehlt xcb, probiert Qt den nächsten Eintrag.
    if sys.platform.startswith("linux"):
        os.environ.setdefault("QT_QPA_PLATFORM", "xcb;wayland")
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
