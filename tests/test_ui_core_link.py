"""F-04, Verbindung der Oberfläche zum Kern-Dienst (echter Dienst im Thread, Qt offscreen)."""

import socket
import time

import pytest

pytest.importorskip(
    "PyQt6.QtWidgets",
    exc_type=ImportError,
    reason="PyQt6 ist nicht installierbar oder lädt nicht (Systembibliotheken fehlen?)",
)

from PyQt6.QtWidgets import QApplication

from donstv_studio.core.config import Paths
from donstv_studio.core.connections.base import Connection, Status
from donstv_studio.ui.core_link import CoreLink
from donstv_studio.ui.main_window import MainWindow
from helpers import RunningService


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def wait_until(app, cond, timeout=10.0):
    end = time.time() + timeout
    while time.time() < end:
        app.processEvents()
        if cond():
            return True
        time.sleep(0.01)
    return False


class Recorder:
    def __init__(self, link: CoreLink) -> None:
        self.connected = 0
        self.unreachable: list[tuple[str, float]] = []
        self.status: list[tuple[str, str, str]] = []
        self.statuses: list[dict] = []
        self.settings: list[dict] = []
        link.connected.connect(lambda: setattr(self, "connected", self.connected + 1))
        link.unreachable.connect(lambda r, s: self.unreachable.append((r, s)))
        link.status_changed.connect(lambda n, s, d: self.status.append((n, s, d)))
        link.statuses_loaded.connect(self.statuses.append)
        link.settings_loaded.connect(self.settings.append)


@pytest.fixture
def paths(tmp_path):
    return Paths.under(tmp_path)


def make_link(paths, port):
    return CoreLink(f"http://127.0.0.1:{port}", paths.token_file, initial_delay=0.2, max_delay=0.5)


def test_core_not_running_reports_unreachable_then_connects_when_it_starts(app, paths):
    port = free_port()
    link = make_link(paths, port)
    rec = Recorder(link)
    link.start()
    try:
        assert wait_until(app, lambda: len(rec.unreachable) >= 2)  # wiederholt, ohne Absturz
        reason, retry = rec.unreachable[0]
        assert "Kern-Dienst" in reason and retry > 0
        assert rec.connected == 0
        assert link.fetch_settings_blocking(0.5) is None  # kein Absturz, nur «nichts»

        core = RunningService(paths, port, free_port()).start()  # jetzt startet der Kern
        try:
            assert wait_until(app, lambda: rec.connected == 1)
            assert rec.settings == [{}]
            # YouTube ist als Platzhalter-Verbindung immer da: «getrennt, nicht eingerichtet».
            # Twitch (P07) ohne Client-ID ebenfalls «getrennt, nicht eingerichtet».
            assert wait_until(app, lambda: len(rec.statuses) == 1)
            assert rec.statuses[0]["youtube"] == {"status": "getrennt", "detail": "nicht eingerichtet"}
            assert rec.statuses[0]["twitch"]["status"] == "getrennt"
            assert rec.statuses[0]["twitch"]["detail"].startswith("nicht eingerichtet")
            # Statusereignis vom Kern erreicht die Oberfläche
            conn = Connection("obs", core.svc.bus)
            core.svc.manager.register(conn)
            core.run(conn.set_status, Status.CONNECTED)
            assert wait_until(app, lambda: ("obs", "verbunden", "") in rec.status)
        finally:
            core.stop()
        # Kern beendet -> wieder «nicht erreichbar», Versuche laufen weiter
        n = len(rec.unreachable)
        assert wait_until(app, lambda: len(rec.unreachable) > n + 1)
    finally:
        link.stop()


def test_settings_roundtrip_through_core_interface(app, paths):
    core = RunningService(paths, free_port(), free_port()).start()
    link = make_link(paths, core.port)
    try:
        assert link.fetch_settings_blocking() == {}
        assert link.save_settings_blocking({"ui.theme": "light", "ui.dock_state": "QUJD"})
        link.save_setting("ui.geometry", "R0VP")
        assert wait_until(app, lambda: (link.fetch_settings_blocking() or {}).get("ui.geometry") == "R0VP")
        assert link.fetch_settings_blocking() == {
            "ui.theme": "light", "ui.dock_state": "QUJD", "ui.geometry": "R0VP",
        }  # fmt: skip
        # Der Dienst speichert in seiner Datenbank, die Oberfläche legt keine eigene Datei an
        assert core.svc.store.get_setting("ui.theme") == "light"
        # Zugangsdaten-Schlüssel werden abgelehnt
        assert link.save_settings_blocking({"secret.x": "y"}) is False
    finally:
        core.stop()


def test_wrong_token_is_reported_not_crashing(app, paths):
    core = RunningService(paths, free_port(), free_port()).start()
    try:
        paths.token_file.write_text("falsches-token")
        link = make_link(paths, core.port)
        rec = Recorder(link)
        link.start()
        assert wait_until(app, lambda: rec.unreachable)
        assert rec.connected == 0
        link.stop()
        assert link.fetch_settings_blocking(0.5) is None
    finally:
        core.stop()


def test_window_with_real_core_shows_status_and_saves_layout(app, paths):
    core = RunningService(paths, free_port(), free_port()).start()
    link = make_link(paths, core.port)
    w = MainWindow(link)
    try:
        conn = Connection("obs", core.svc.bus)
        core.svc.manager.register(conn)
        core.run(conn.set_status, Status.CONNECTING)
        link.start()
        w.show()
        assert wait_until(app, lambda: "verbunden" in w.core_status.text())
        assert wait_until(app, lambda: "verbindet" in w.connections.text_of("obs"))
        core.run(conn.set_status, Status.CONNECTED)
        assert wait_until(app, lambda: "verbunden" in w.connections.text_of("obs"))
        assert wait_until(app, lambda: w._settings_loaded)
        w.set_theme("light")
        w.docks[0].hide()
        w.close()  # speichert über den Kern
        saved = link.fetch_settings_blocking()
        assert saved["ui.theme"] == "light" and saved["ui.geometry"] and saved["ui.dock_state"]
    finally:
        link.stop()
        core.stop()

    # Neustart: Einstellungen kommen aus der Datenbank des Kerns
    core2 = RunningService(paths, free_port(), free_port()).start()
    link2 = make_link(paths, core2.port)
    w2 = MainWindow(link2)
    try:
        link2.start()
        w2.show()
        assert wait_until(app, lambda: w2.theme == "light")
        assert wait_until(app, lambda: w2.docks[0].isHidden())
    finally:
        w2.close()
        link2.stop()
        core2.stop()


def test_core_stops_promptly_while_the_ui_is_connected(app, paths):
    """Regression: /ws/events hielt das Beenden des Kerns auf, solange die Oberfläche verbunden war."""
    core = RunningService(paths, free_port(), free_port()).start()
    link = make_link(paths, core.port)
    rec = Recorder(link)
    link.start()
    try:
        assert wait_until(app, lambda: rec.connected == 1)
        t0 = time.time()
        core.stop()  # die Verbindung der Oberfläche ist noch offen
        assert time.time() - t0 < 3.0
        assert not core.thread.is_alive()
        assert wait_until(app, lambda: rec.unreachable)  # die Oberfläche bemerkt es und versucht es neu
    finally:
        link.stop()


def test_f41_f45_bot_events_and_api_through_real_core(app, paths, monkeypatch):
    """Kern mit Testverbindung (DONSTV_TWITCH_FAKE=1): Ereignisse kommen als JSON-Text an (Regel 12)."""
    import json

    monkeypatch.setenv("DONSTV_TWITCH_FAKE", "1")
    core = RunningService(paths, free_port(), free_port()).start()
    link = make_link(paths, core.port)
    got: list[tuple[str, str]] = []
    link.event_received.connect(lambda kind, text: got.append((kind, text)))
    rec = Recorder(link)
    try:
        link.start()
        assert wait_until(app, lambda: rec.connected == 1)
        b = link.backend
        b.bot_create_command(name="Test", trigger="!test", response="Hallo {user}")
        core.run(core.svc.twitch.inject, "Anna", "!test")
        assert wait_until(app, lambda: any(k == "bot.log" for k, _ in got))
        # Reihenfolge wie im Chat: erst die auslösende Nachricht, dann die Antwort
        assert wait_until(app, lambda: [json.loads(t)["text"] for k, t in got if k == "twitch.chat.message"]
                          == ["!test", "Hallo Anna"])  # fmt: skip
        assert all(isinstance(t, str) for _, t in got)
        assert [m["text"] for m in b.bot_chat_recent()] == ["!test", "Hallo Anna"]
        assert b.bot_settings()["fake"] is True
        with pytest.raises(Exception, match="gibt es schon"):  # Meldung des Kerns erreicht die Oberfläche
            b.bot_create_command(name="Nochmal", trigger="!test")
        assert rec.statuses[0]["twitch"] == {"status": "verbunden",
                                             "detail": "donstvbot im Kanal donstv2020 (Testverbindung)"}  # fmt: skip
    finally:
        link.stop()
        core.stop()
