import os

# Qt-Tests ohne Bildschirm (Debian-Laptop: X11, Tests: offscreen)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if hasattr(os, "geteuid") and os.geteuid() == 0:  # Chromium (QtWebEngine) läuft als root nur ohne Sandbox
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox --disable-gpu")
os.environ.setdefault("QT_QUICK_BACKEND", "software")


def pytest_configure(config):
    """QtWebEngine verlangt: Import vor der QApplication, und die QApplication braucht einen Programmnamen.

    Alle UI-Tests teilen diese eine Anwendung (`QApplication.instance()`).
    """
    try:
        from PyQt6.QtWidgets import QApplication

        from donstv_studio.ui import preview_web  # noqa: F401
    except ImportError:  # PyQt6 fehlt: UI-Tests werden übersprungen
        return
    if QApplication.instance() is None:
        config._qt_app = QApplication(["donstv-tests"])  # Verweis halten, sonst wird die Anwendung abgeräumt

