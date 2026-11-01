"""F-41 bis F-45: Modul «Chat-Bot» im Hauptfenster (offscreen, ohne Kern-Dienst, mit nachgebauter Schnittstelle)."""

import copy
import json
import time
import uuid

import pytest

pytest.importorskip(
    "PyQt6.QtWidgets", exc_type=ImportError, reason="PyQt6 ist nicht installierbar oder lädt nicht"
)

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from donstv_studio.ui.backend import BackendError, DirectRunner
from donstv_studio.ui.bot_page import CHAT_LIMIT
from donstv_studio.ui.main_window import MainWindow
from fake_core import FakeCore


class FakeBotBackend:
    """Verhält sich wie `/bot/...` im Kern (bot/api.py)."""

    def __init__(self):
        self.commands = []
        self.sent = []
        self.settings = {"client_id": "", "channel": "donstv2020", "bot_login": "", "logged_in": False,
                         "login": {"state": "idle"}, "fake": False}  # fmt: skip
        self.fail_next = None

    def _check(self):
        if self.fail_next:
            msg, self.fail_next = self.fail_next, None
            raise BackendError(msg)

    def bot_commands(self):
        return copy.deepcopy(self.commands)

    def bot_create_command(self, **fields):
        self._check()
        cmd = {"id": uuid.uuid4().hex, "name": "", "trigger": "", "permission": "everyone", "cooldown_global": 0,
               "cooldown_user": 0, "response": "", "enabled": True, "position": len(self.commands)}  # fmt: skip
        cmd.update(fields)
        self.commands.append(cmd)
        return copy.deepcopy(cmd)

    def bot_update_command(self, command_id, **fields):
        self._check()
        cmd = next(c for c in self.commands if c["id"] == command_id)
        cmd.update(fields)
        return copy.deepcopy(cmd)

    def bot_duplicate_command(self, command_id):
        src = next(c for c in self.commands if c["id"] == command_id)
        return self.bot_create_command(**{**src, "id": uuid.uuid4().hex, "name": src["name"] + " (Kopie)",
                                          "trigger": src["trigger"] + "2", "enabled": False})  # fmt: skip

    def bot_delete_command(self, command_id):
        self.commands = [c for c in self.commands if c["id"] != command_id]

    def bot_log(self):
        return [
            {
                "seq": 1,
                "ts": time.time(),
                "kind": "connection",
                "message": "Twitch: verbunden",
                "data": {},
            }
        ]

    def bot_chat_recent(self):
        return [
            {
                "message_id": "a",
                "display_name": "Anna",
                "text": "Hallo",
                "ts": time.time(),
                "roles": {},
            }
        ]

    def bot_send(self, text):
        self._check()
        self.sent.append(text)
        return {"message_id": "s"}

    def bot_settings(self):
        return copy.deepcopy(self.settings)

    def bot_save_settings(self, **fields):
        self.settings.update(fields)
        return copy.deepcopy(self.settings)

    def bot_login(self):
        self.settings["login"] = {"role": "bot", "state": "pending", "user_code": "ABCDEFGH",
                                  "verification_uri": "https://www.twitch.tv/activate?public=true"}  # fmt: skip
        return copy.deepcopy(self.settings["login"])

    def bot_logout(self):
        self.settings.update(logged_in=False, bot_login="", login={"state": "idle"})
        return copy.deepcopy(self.settings)


class BotCore(FakeCore):
    from PyQt6.QtCore import pyqtSignal

    event_received = pyqtSignal(str, str)


@pytest.fixture
def env(app):
    core = BotCore()
    core.bot_backend = FakeBotBackend()
    core.runner = DirectRunner()
    w = MainWindow(core)
    w.resize(1400, 900)
    w.show()
    app.processEvents()
    core.connected.emit()
    core.settings_loaded.emit(json.dumps({}))
    w.set_module(1)
    app.processEvents()
    yield w, core, core.bot_backend
    w.close()
    w.deleteLater()


def table_rows(w):
    t = w.commands_tab.table
    return [[t.item(r, c).text() for c in range(t.columnCount())] for r in range(t.rowCount())]


def test_f41_bot_docks_only_in_bot_module(env, app):
    w, *_ = env
    assert all(d.isVisible() for d in w.bot_docks)
    assert not any(d.isVisible() for d in w.docks)
    assert [d.windowTitle() for d in w.bot_docks] == ["Chat", "Protokoll"]
    assert all(not b.close_button.isVisible() for b in w.bot_dock_titles)  # nicht schliessbar
    w.set_module(0)
    app.processEvents()
    assert not any(d.isVisible() for d in w.bot_docks) and all(d.isVisible() for d in w.docks)
    w.set_module(1)
    assert all(d.isVisible() for d in w.bot_docks)


def test_f43_commands_table_and_buttons(env):
    w, core, backend = env
    tab = w.commands_tab
    assert tab.import_button.text() == "Importieren" and not tab.import_button.isEnabled()
    assert "folgt" in tab.import_button.toolTip() and tab.import_hint.text() == "Importieren folgt"
    assert not tab.duplicate_button.isEnabled() and not tab.delete_button.isEnabled()
    assert (
        not tab.save_button.isEnabled()
        and tab.hint.isVisibleTo(tab)
        and tab.hint.text() == "Kein Command gewählt"
    )
    tab.new_button.click()
    assert table_rows(w) == [["Neuer Command", "!neu", "Alle", "0 s / 0 s", "nein"]]
    assert w.bot.selected_id == backend.commands[0]["id"] and tab.save_button.isEnabled()
    tab.new_button.click()
    assert [r[1] for r in table_rows(w)] == ["!neu", "!neu2"]  # freier Befehl


def test_f43_edit_and_save(env):
    w, core, backend = env
    tab = w.commands_tab
    tab.new_button.click()
    tab.name.setText("Test")
    tab.trigger.setText("!test")
    tab.permission.setCurrentIndex(tab.permission.findData("moderator"))
    tab.cooldown_global.setValue(30)
    tab.cooldown_user.setValue(60)
    tab.response.setPlainText("Hallo {user}")
    tab.enabled.setChecked(True)
    assert tab.count.text() == "12 / 500 Zeichen"
    tab.save_button.click()
    cmd = backend.commands[0]
    assert (cmd["name"], cmd["trigger"], cmd["permission"], cmd["cooldown_global"], cmd["cooldown_user"],
            cmd["response"], cmd["enabled"]) == ("Test", "!test", "moderator", 30, 60, "Hallo {user}", True)  # fmt: skip
    assert table_rows(w) == [["Test", "!test", "Moderatoren", "30 s / 60 s", "ja"]]


def test_f43_active_checkbox_duplicate_delete(env):
    w, core, backend = env
    tab = w.commands_tab
    tab.new_button.click()
    tab.table.item(0, 4).setCheckState(Qt.CheckState.Checked)
    assert backend.commands[0]["enabled"] is True
    tab.duplicate_button.click()
    assert [r[1] for r in table_rows(w)] == [
        "!neu",
        "!neu2",
    ] and w.bot.selected_id == backend.commands[1]["id"]
    tab.ask_confirm = lambda *a: True
    tab.delete_button.click()
    assert [r[1] for r in table_rows(w)] == ["!neu"] and w.bot.selected_id == ""


def test_error_from_core_shows_in_status_bar(env):
    w, core, backend = env
    w.commands_tab.new_button.click()
    backend.fail_next = "Den Befehl «!neu» gibt es schon"
    w.commands_tab.save_button.click()
    assert "gibt es schon" in w.statusBar().currentMessage()


def test_f41_chat_dock_shows_history_events_and_limits(env, app):
    w, core, _ = env
    chat = w.chat_panel.list
    assert chat.count() == 1 and chat.item(0).text().endswith("Anna: Hallo")
    msg = {
        "message_id": "b",
        "display_name": "Ben",
        "text": "Hi",
        "ts": time.time(),
        "roles": {"moderator": True},
    }
    core.event_received.emit("twitch.chat.message", json.dumps(msg))
    core.event_received.emit("twitch.chat.message", json.dumps(msg))  # gleiche Kennung: nur einmal
    assert chat.count() == 2 and "⚔ Ben: Hi" in chat.item(1).text()
    for i in range(CHAT_LIMIT + 5):
        core.event_received.emit(
            "twitch.chat.message", json.dumps({**msg, "message_id": f"x{i}", "text": str(i)})
        )
    assert chat.count() == CHAT_LIMIT and len(w.bot.chat) == CHAT_LIMIT
    assert chat.item(CHAT_LIMIT - 1).text().endswith(f": {CHAT_LIMIT + 4}")


def test_f42_send_from_chat_dock(env):
    w, core, backend = env
    p = w.chat_panel
    p.input.setText("Hallo Chat")
    p.send_button.click()
    assert backend.sent == ["Hallo Chat"] and p.input.text() == ""
    p.input.setText("geht nicht")
    backend.fail_next = "Twitch ist nicht verbunden"
    p.send_button.click()
    assert p.input.text() == "geht nicht"  # bleibt stehen
    assert "nicht verbunden" in w.statusBar().currentMessage()
    p.input.setText("   ")
    p.send()
    assert backend.sent == ["Hallo Chat"]


def test_f45_log_dock(env):
    w, core, _ = env
    log = w.log_panel.list
    assert log.count() == 1 and "Verbindung: Twitch: verbunden" in log.item(0).text()
    entry = {
        "seq": 2,
        "ts": time.time(),
        "kind": "cooldown",
        "message": "!test von Anna abgelehnt",
        "data": {},
    }
    core.event_received.emit("bot.log", json.dumps(entry))
    assert "Cooldown: !test von Anna abgelehnt" in log.item(1).text()


def test_f40_settings_client_id_and_login(env):
    w, core, backend = env
    s = w.bot_settings_tab
    assert not s.login_button.isEnabled()  # ohne Client-ID keine Anmeldung
    s.client_id.setText("abc123")
    s.save_button.click()
    assert backend.settings["client_id"] == "abc123" and backend.settings["channel"] == "donstv2020"
    assert s.login_button.isEnabled() and not s.logout_button.isEnabled()
    assert not s.code_frame.isVisible()
    s.login_button.click()
    assert s.code_frame.isVisibleTo(s) and "ABCDEFGH" in s.code_label.text()
    opened = []
    s.open_url = opened.append
    s.open_button.click()
    assert opened == ["https://www.twitch.tv/activate?public=true"]
    s.copy_button.click()
    assert QApplication.clipboard().text() == "ABCDEFGH"
    core.event_received.emit(
        "twitch.auth", json.dumps({"role": "bot", "state": "done", "login": "donstvbot"})
    )
    assert s.account_label.text() == "Angemeldet als donstvbot" and not s.code_frame.isVisibleTo(s)
    assert s.logout_button.isEnabled()
    s.logout_button.click()
    assert s.account_label.text().startswith("Nicht angemeldet")


def test_f04_twitch_tooltip_names_account(env):
    w, core, _ = env
    core.status_changed.emit("twitch", "verbunden", "donstvbot im Kanal donstv2020")
    assert w.connections.tooltip_of("twitch") == "Twitch: verbunden (donstvbot im Kanal donstv2020)"
    core.status_changed.emit("twitch", "getrennt", "nicht eingerichtet: Client-ID fehlt")
    assert (
        w.connections.indicators["twitch"].color_name() == "text_muted"
    )  # grau: nicht eingerichtet
    core.status_changed.emit("twitch", "getrennt", "")
    assert w.connections.indicators["twitch"].color_name() == "error"


def test_bot_module_without_backend_stays_empty(app):
    core = BotCore()
    w = MainWindow(core)
    w.set_module(1)
    assert w.commands_tab.table.rowCount() == 0 and not w.commands_tab.new_button.isEnabled()
    w.close()
