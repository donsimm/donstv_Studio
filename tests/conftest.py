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



def pytest_sessionfinish(session, exitstatus):
    """Einmal am Ende der Sitzung (P06c): alle QWebEngineView mit Seite und Profil kontrolliert freigeben,
    solange die QApplication noch besteht. Grund: Speicherzugriffsfehler beim Beenden von pytest auf dem
    Laptop nach «Release of profile requested but WebEnginePage still not deleted». Nach jedem Test
    aufzuräumen führte in P06 zu Abstürzen; darum nur hier. Reihenfolge: `preview_web.RELEASE_ORDER`.
    """
    try:
        from donstv_studio.ui import preview_web
    except ImportError:
        return
    n = preview_web.release_web_views()
    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    if n and reporter is not None:  # print() wäre hier noch abgefangen
        reporter.write_line(f"Aufräumen am Sitzungsende: {n} Webansicht(en) freigegeben")
