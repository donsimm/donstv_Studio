"""Ersatz für `CoreLink` in Tests der Oberfläche ohne Kern-Dienst: dieselben Signale, Einstellungen im Speicher."""

from PyQt6.QtCore import QObject, pyqtSignal


class FakeCore(QObject):
    connected = pyqtSignal()
    unreachable = pyqtSignal(str, float)
    status_changed = pyqtSignal(str, str, str)
    statuses_loaded = pyqtSignal(str)  # JSON-Text wie CoreLink
    settings_loaded = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.store: dict[str, str] = {}

    def save_setting(self, key, value):
        self.store[key] = value

    def save_settings_blocking(self, values, timeout=2.0):
        self.store.update(values)
        return True
