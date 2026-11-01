"""Einstiegspunkt `donstv-studio`: startet die Oberfläche und verbindet sich mit dem Kern-Dienst."""

from __future__ import annotations

import logging
import os
import sys

log = logging.getLogger(__name__)


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
    # QtWebEngine muss vor der QApplication importiert werden (siehe preview_web.py).
    from donstv_studio.ui import preview_web  # noqa: F401
    from donstv_studio.ui.core_link import CoreLink
    from donstv_studio.ui.main_window import MainWindow
    from donstv_studio.ui.signals import SignalBridge

    # Unter Linux X11 (xcb, auf Wayland über XWayland) vor Wayland: CLAUDE.md nennt X11 als Zielsystem, und nur dort
    # lassen sich Fensterlage und schwebende Docks sicher speichern und wiederherstellen. Ein vom Nutzer
    # gesetztes QT_QPA_PLATFORM gilt weiter. Fehlt xcb, probiert Qt den nächsten Eintrag.
    if sys.platform.startswith("linux"):
        os.environ.setdefault("QT_QPA_PLATFORM", "xcb;wayland")
    if (
        os.geteuid() == 0
    ):  # Chromium startet als root nur ohne Sandbox (Entwicklungsumgebung, nicht der Laptop)
        os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox")
    app = QApplication(sys.argv[:1])
    app.setApplicationName("donstv_Studio")
    core = CoreLink()
    window = MainWindow(core)
    saved = core.fetch_settings_blocking()  # vor dem Anzeigen, damit nichts flackert
    if saved is not None:
        window.apply_settings(saved)
    core.start()
    window.show()
    # SIGTERM und SIGINT: Layout speichern, dann beenden (nicht nur beim normalen Schliessen).
    bridge = SignalBridge(parent=app)

    def on_signal(_num: int) -> None:
        window.save_layout_now()
        app.quit()

    bridge.received.connect(on_signal)
    log.info("Oberfläche bereit; SIGTERM und SIGINT speichern das Layout")
    code = app.exec()
    bridge.close()
    core.stop()
    shutdown(app, window)
    return code


def shutdown(app, window) -> None:
    """Explizites Aufräumen beim Beenden (P06c, F-01): Webansichten, dann Fenster, die QApplication zuletzt.

    Ohne diesen Schritt räumt Python beim Beenden in beliebiger Reihenfolge auf; dann kann ein Profil von
    QtWebEngine vor seiner Seite freigegeben werden. Reihenfolge und Quellen: `preview_web.RELEASE_ORDER`.
    """
    from PyQt6.QtCore import QCoreApplication, QEvent

    from donstv_studio.ui import preview_web

    n = preview_web.release_web_views(app)  # Ansicht vor Seite vor Profil
    window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()
    log.info("Beenden: %d Webansicht(en) und Hauptfenster freigegeben", n)
