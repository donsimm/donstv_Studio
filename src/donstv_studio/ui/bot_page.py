"""Modul «Chat-Bot» (F-41 bis F-45) nach docs/04-ui-design.md, Abschnitt 4.

Reiter «Commands» (Tabelle, Neu, Duplizieren, Löschen, Importieren gesperrt, Bereich «Command bearbeiten»),
Reiter «Einstellungen» (Client-ID, Kanal, Anmeldung des Bot-Kontos), Chat-Dock und Protokoll-Dock.
Alles Fachliche läuft über die Schnittstelle des Kerns (`/bot/...`); Ereignisse kommen über `/ws/events`
als JSON-Text (Regel 12).
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import QObject, Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from donstv_studio.ui.editor_docks import confirm

CHAT_LIMIT = 500  # Nachrichten im Chat-Dock (Speicher begrenzt)
LOG_LIMIT = 500  # Einträge im Protokoll-Dock
MAX_COOLDOWN = 86_400
MAX_RESPONSE = 500
PERMISSIONS = (("everyone", "Alle"), ("subscriber", "Abonnenten"), ("moderator", "Moderatoren"),
               ("broadcaster", "Streamer"))  # fmt: skip
PERMISSION_NAMES = dict(PERMISSIONS)
LOG_KINDS = {
    "command": "Command",
    "cooldown": "Cooldown",
    "permission": "Berechtigung",
    "connection": "Verbindung",
    "send_error": "Sendefehler",
    "auth": "Anmeldung",
}
COLUMNS = ("Name", "Befehl", "Berechtigung", "Cooldown", "Aktiv")


def clock(ts: float, seconds: bool = False) -> str:
    return time.strftime("%H:%M:%S" if seconds else "%H:%M", time.localtime(ts))


def cooldown_text(cmd: dict) -> str:
    """«30 s / 60 s» (global / pro Nutzer)."""
    return f"{cmd.get('cooldown_global', 0)} s / {cmd.get('cooldown_user', 0)} s"


class BotModel(QObject):
    """Zustand des Moduls; Aufrufe an den Kern laufen über den Runner (wie der Editor)."""

    commands_changed = pyqtSignal()
    chat_added = pyqtSignal(str)  # Nachricht als JSON-Text
    chat_reset = pyqtSignal()
    log_added = pyqtSignal(str)  # Eintrag als JSON-Text
    log_reset = pyqtSignal()
    settings_changed = pyqtSignal()
    selection_changed = pyqtSignal(str)  # Kennung des gewählten Commands oder ""
    error = pyqtSignal(str)
    sent = pyqtSignal()

    def __init__(self, backend, runner, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._backend = backend
        self._runner = runner
        self.commands: list[dict] = []
        self.selected_id = ""
        self.settings: dict[str, Any] = {}
        self.chat: list[dict] = []
        self.log: list[dict] = []

    @property
    def available(self) -> bool:
        return self._backend is not None and hasattr(self._backend, "bot_commands")

    def _submit(self, fn: Callable, on_done: Callable | None = None, **fields: Any) -> None:
        if not self.available:
            return
        self._runner.submit(fn, on_done, self._failed, fields=fields if fields else None)

    def _failed(self, error: Exception) -> None:
        self.error.emit(str(error))

    # --- Laden ------------------------------------------------------------
    def load(self) -> None:
        """Nach jedem (Wieder-)Verbinden mit dem Kern."""
        if self.available:
            self._submit(self._backend.bot_commands, self._set_commands)
            self._submit(self._backend.bot_settings, self._set_settings)
            self._submit(self._backend.bot_chat_recent, self._set_chat)
            self._submit(self._backend.bot_log, self._set_log)

    def _set_commands(self, commands: list[dict]) -> None:
        self.commands = list(commands or [])
        if self.selected_id and self.command(self.selected_id) is None:
            self.selected_id = ""
        self.commands_changed.emit()
        self.selection_changed.emit(self.selected_id)

    def _set_settings(self, settings: dict) -> None:
        self.settings = dict(settings or {})
        self.settings_changed.emit()

    def _set_chat(self, messages: list[dict]) -> None:
        self.chat = list(messages or [])[-CHAT_LIMIT:]
        self.chat_reset.emit()

    def _set_log(self, entries: list[dict]) -> None:
        self.log = list(entries or [])[-LOG_LIMIT:]
        self.log_reset.emit()

    # --- Ereignisse vom Kern ------------------------------------------------
    def on_event(self, kind: str, payload_json: str) -> None:
        try:
            payload = json.loads(payload_json)
        except ValueError:
            return
        if not isinstance(payload, dict):
            return
        if kind == "twitch.chat.message":
            if any(m.get("message_id") == payload.get("message_id") for m in self.chat[-50:]):
                return  # schon über /bot/chat/recent geladen
            self.chat.append(payload)
            del self.chat[:-CHAT_LIMIT]
            self.chat_added.emit(payload_json)
        elif kind == "bot.log":
            self.log.append(payload)
            del self.log[:-LOG_LIMIT]
            self.log_added.emit(payload_json)
        elif kind == "twitch.auth":
            self.settings = {**self.settings, "login": payload}
            if payload.get("state") == "done":
                self.settings["logged_in"] = True
                self.settings["bot_login"] = payload.get("login", "")
            elif payload.get("state") == "idle":
                self.settings["logged_in"] = False
                self.settings["bot_login"] = ""
            self.settings_changed.emit()

    # --- Commands -------------------------------------------------------------
    def command(self, command_id: str) -> dict | None:
        return next((c for c in self.commands if c["id"] == command_id), None)

    def select(self, command_id: str) -> None:
        if command_id != self.selected_id:
            self.selected_id = command_id
            self.selection_changed.emit(command_id)

    def _reload_and_select(self, command_id: str) -> None:
        def done(commands: list[dict]) -> None:
            self.selected_id = command_id
            self._set_commands(commands)

        self._submit(self._backend.bot_commands, done)

    def free_trigger(self, base: str = "!neu") -> str:
        taken = {c["trigger"].lower() for c in self.commands}
        if base not in taken:
            return base
        n = 2
        while f"{base}{n}" in taken:
            n += 1
        return f"{base}{n}"

    def create(self) -> None:
        trigger = self.free_trigger()
        self._submit(self._backend.bot_create_command, lambda c: self._reload_and_select(c["id"]),
                     name="Neuer Command", trigger=trigger, response="", enabled=False)  # fmt: skip

    def update(self, command_id: str, fields: dict[str, Any]) -> None:
        self._submit(lambda **f: self._backend.bot_update_command(command_id, **f),
                     lambda c: self._reload_and_select(c["id"]), **fields)  # fmt: skip

    def duplicate(self, command_id: str) -> None:
        self._submit(lambda: self._backend.bot_duplicate_command(command_id),
                     lambda c: self._reload_and_select(c["id"]))  # fmt: skip

    def delete(self, command_id: str) -> None:
        self._submit(
            lambda: self._backend.bot_delete_command(command_id),
            lambda _r: self._reload_and_select(""),
        )

    # --- Chat, Einstellungen, Anmeldung ---------------------------------------
    def send(self, text: str) -> None:
        self._submit(lambda: self._backend.bot_send(text), lambda _r: self.sent.emit())

    def save_settings(self, client_id: str, channel: str) -> None:
        self._submit(
            lambda: self._backend.bot_save_settings(client_id=client_id, channel=channel),
            self._set_settings,
        )

    def login(self) -> None:
        def started(state: dict) -> None:
            self.settings = {**self.settings, "login": state}
            self.settings_changed.emit()

        self._submit(self._backend.bot_login, started)

    def logout(self) -> None:
        self._submit(self._backend.bot_logout, self._set_settings)


def _section(title: str) -> QGroupBox:
    box = QGroupBox(title)
    box.setObjectName("bot_section")
    return box


class CommandsTab(QWidget):
    """Tabelle der Commands mit Schaltflächen und Bereich «Command bearbeiten» (F-43)."""

    def __init__(self, model: BotModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.model = model
        self.setObjectName("bot_commands")
        outer = QHBoxLayout(self)

        left = QVBoxLayout()
        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setObjectName("commands_table")
        self.table.setAccessibleName("Commands")
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self._selected)
        self.table.itemChanged.connect(self._item_changed)
        left.addWidget(self.table, 1)
        buttons = QHBoxLayout()
        self.new_button = QPushButton("Neu")
        self.duplicate_button = QPushButton("Duplizieren")
        self.delete_button = QPushButton("Löschen")
        self.import_button = QPushButton("Importieren")
        self.import_button.setEnabled(False)
        self.import_button.setToolTip("Importieren: folgt")
        for name, b in (("cmd_new", self.new_button), ("cmd_duplicate", self.duplicate_button),
                        ("cmd_delete", self.delete_button), ("cmd_import", self.import_button)):  # fmt: skip
            b.setObjectName(name)
            buttons.addWidget(b)
        self.import_hint = QLabel("Importieren folgt")
        self.import_hint.setProperty("muted", True)
        buttons.addWidget(self.import_hint)
        buttons.addStretch(1)
        self.new_button.clicked.connect(lambda: model.create())
        self.duplicate_button.clicked.connect(
            lambda: model.selected_id and model.duplicate(model.selected_id)
        )
        self.delete_button.clicked.connect(self.remove)
        left.addLayout(buttons)
        outer.addLayout(left, 3)

        self.editor = _section("Command bearbeiten")
        self.editor.setObjectName("command_editor")
        grid = QGridLayout(self.editor)
        self.name = QLineEdit()
        self.name.setObjectName("cmd_name")
        self.name.setMaxLength(100)
        self.trigger = QLineEdit()
        self.trigger.setObjectName("cmd_trigger")
        self.trigger.setMaxLength(50)
        self.trigger.setPlaceholderText("z. B. !regeln")
        self.permission = QComboBox()
        self.permission.setObjectName("cmd_permission")
        for key, label in PERMISSIONS:
            self.permission.addItem(label, key)
        self.cooldown_global = self._spin("cmd_cooldown_global")
        self.cooldown_user = self._spin("cmd_cooldown_user")
        self.response = QPlainTextEdit()
        self.response.setObjectName("cmd_response")
        self.response.setPlaceholderText("Antworttext, {user} wird durch den Namen ersetzt")
        self.response.textChanged.connect(self._count)
        self.count = QLabel()
        self.count.setObjectName("cmd_count")
        self.count.setProperty("muted", True)
        self.enabled = QCheckBox("Aktiv")
        self.enabled.setObjectName("cmd_enabled")
        self.save_button = QPushButton("Speichern")
        self.save_button.setObjectName("cmd_save")
        self.save_button.clicked.connect(self.save)
        rows = (("Name", self.name), ("Befehl", self.trigger), ("Berechtigung", self.permission),
                ("Cooldown global", self.cooldown_global), ("Cooldown pro Nutzer", self.cooldown_user))  # fmt: skip
        for r, (label, widget) in enumerate(rows):
            lbl = QLabel(label)
            lbl.setBuddy(widget)
            grid.addWidget(lbl, r, 0)
            grid.addWidget(widget, r, 1)
        grid.addWidget(QLabel("Antworttext"), len(rows), 0, Qt.AlignmentFlag.AlignTop)
        grid.addWidget(self.response, len(rows), 1)
        grid.addWidget(self.count, len(rows) + 1, 1, Qt.AlignmentFlag.AlignRight)
        grid.addWidget(self.enabled, len(rows) + 2, 1)
        grid.addWidget(self.save_button, len(rows) + 3, 1, Qt.AlignmentFlag.AlignRight)
        self.hint = QLabel("Kein Command gewählt")
        self.hint.setObjectName("command_hint")
        self.hint.setProperty("muted", True)
        grid.addWidget(self.hint, len(rows) + 4, 0, 1, 2)
        outer.addWidget(self.editor, 2)

        self.ask_confirm = confirm
        model.commands_changed.connect(self.refresh)
        model.selection_changed.connect(self._show)
        self.refresh()
        self._show("")

    @staticmethod
    def _spin(name: str) -> QSpinBox:
        s = QSpinBox()
        s.setObjectName(name)
        s.setRange(0, MAX_COOLDOWN)
        s.setSuffix(" s")
        return s

    def _count(self) -> None:
        n = len(self.response.toPlainText())
        self.count.setText(f"{n} / {MAX_RESPONSE} Zeichen")

    def refresh(self) -> None:
        self.table.blockSignals(True)
        self.table.setRowCount(len(self.model.commands))
        for row, cmd in enumerate(self.model.commands):
            values = (cmd["name"], cmd["trigger"], PERMISSION_NAMES.get(cmd["permission"], cmd["permission"]),
                      cooldown_text(cmd))  # fmt: skip
            for col, text in enumerate(values):
                item = QTableWidgetItem(text)
                item.setData(Qt.ItemDataRole.UserRole, cmd["id"])
                self.table.setItem(row, col, item)
            active = QTableWidgetItem("ja" if cmd["enabled"] else "nein")
            active.setFlags(
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsUserCheckable
            )
            active.setCheckState(
                Qt.CheckState.Checked if cmd["enabled"] else Qt.CheckState.Unchecked
            )
            active.setData(Qt.ItemDataRole.UserRole, cmd["id"])
            active.setToolTip("Aktiv: Haken setzen oder entfernen")
            self.table.setItem(row, 4, active)
            if cmd["id"] == self.model.selected_id:
                self.table.selectRow(row)
        self.table.blockSignals(False)
        self._enable()

    def _enable(self) -> None:
        has = bool(self.model.selected_id)
        self.duplicate_button.setEnabled(has)
        self.delete_button.setEnabled(has)
        self.new_button.setEnabled(self.model.available)

    def _selected(self) -> None:
        items = self.table.selectedItems()
        self.model.select(items[0].data(Qt.ItemDataRole.UserRole) if items else "")

    def _item_changed(self, item: QTableWidgetItem) -> None:
        if item.column() == 4:
            self.model.update(
                item.data(Qt.ItemDataRole.UserRole),
                {"enabled": item.checkState() == Qt.CheckState.Checked},
            )

    def _show(self, command_id: str) -> None:
        cmd = self.model.command(command_id) if command_id else None
        for w in (self.name, self.trigger, self.permission, self.cooldown_global, self.cooldown_user,
                  self.response, self.enabled, self.save_button):  # fmt: skip
            w.setEnabled(cmd is not None)
        self.hint.setVisible(cmd is None)
        cmd = cmd or {"name": "", "trigger": "", "permission": "everyone", "cooldown_global": 0,
                      "cooldown_user": 0, "response": "", "enabled": False}  # fmt: skip
        self.name.setText(cmd["name"])
        self.trigger.setText(cmd["trigger"])
        self.permission.setCurrentIndex(max(0, self.permission.findData(cmd["permission"])))
        self.cooldown_global.setValue(int(cmd["cooldown_global"]))
        self.cooldown_user.setValue(int(cmd["cooldown_user"]))
        self.response.setPlainText(cmd["response"])
        self.enabled.setChecked(bool(cmd["enabled"]))
        self._count()
        self._enable()

    def values(self) -> dict[str, Any]:
        return {
            "name": self.name.text(),
            "trigger": self.trigger.text(),
            "permission": self.permission.currentData(),
            "cooldown_global": self.cooldown_global.value(),
            "cooldown_user": self.cooldown_user.value(),
            "response": self.response.toPlainText(),
            "enabled": self.enabled.isChecked(),
        }

    def save(self) -> None:
        if self.model.selected_id:
            self.model.update(self.model.selected_id, self.values())

    def remove(self) -> None:
        cmd = self.model.command(self.model.selected_id)
        if cmd and self.ask_confirm(self, "Command löschen", f"Command «{cmd['name']}» ({cmd['trigger']}) löschen?",
                                    "Löschen"):  # fmt: skip
            self.model.delete(cmd["id"])


class BotSettingsTab(QWidget):
    """Client-ID, Kanal und Anmeldung des Bot-Kontos (F-40, Zusatz 2)."""

    def __init__(self, model: BotModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.model = model
        self.setObjectName("bot_settings")
        lay = QVBoxLayout(self)

        app_box = _section("Twitch-Anwendung")
        grid = QGridLayout(app_box)
        self.client_id = QLineEdit()
        self.client_id.setObjectName("client_id")
        self.client_id.setMaxLength(100)
        self.client_id.setPlaceholderText("Client-ID von dev.twitch.tv/console")
        self.channel = QLineEdit()
        self.channel.setObjectName("channel")
        self.channel.setMaxLength(25)
        self.channel.setPlaceholderText("donstv2020")
        self.save_button = QPushButton("Speichern")
        self.save_button.setObjectName("settings_save")
        self.save_button.clicked.connect(lambda: model.save_settings(self.client_id.text().strip(),
                                                                     self.channel.text().strip()))  # fmt: skip
        for r, (label, widget) in enumerate(
            (("Client-ID", self.client_id), ("Kanal", self.channel))
        ):
            lbl = QLabel(label)
            lbl.setBuddy(widget)
            grid.addWidget(lbl, r, 0)
            grid.addWidget(widget, r, 1)
        grid.addWidget(self.save_button, 2, 1, Qt.AlignmentFlag.AlignRight)
        note = QLabel(
            "Die Client-ID ist kein Geheimnis und wird in den Einstellungen des Kerns gespeichert."
        )
        note.setWordWrap(True)
        note.setProperty("muted", True)
        grid.addWidget(note, 3, 0, 1, 2)
        lay.addWidget(app_box)

        account = _section("Bot-Konto")
        acc = QVBoxLayout(account)
        self.account_label = QLabel()
        self.account_label.setObjectName("account_label")
        self.account_label.setWordWrap(True)
        acc.addWidget(self.account_label)
        self.code_frame = QFrame()
        code_lay = QVBoxLayout(self.code_frame)
        code_lay.setContentsMargins(0, 0, 0, 0)
        self.code_label = QLabel()
        self.code_label.setObjectName("code_label")
        self.code_label.setWordWrap(True)
        self.code_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        code_lay.addWidget(self.code_label)
        code_buttons = QHBoxLayout()
        self.open_button = QPushButton("Adresse öffnen")
        self.open_button.setObjectName("open_activate")
        self.copy_button = QPushButton("Code kopieren")
        self.copy_button.setObjectName("copy_code")
        self.open_button.clicked.connect(self._open)
        self.copy_button.clicked.connect(self._copy)
        code_buttons.addWidget(self.open_button)
        code_buttons.addWidget(self.copy_button)
        code_buttons.addStretch(1)
        code_lay.addLayout(code_buttons)
        acc.addWidget(self.code_frame)
        row = QHBoxLayout()
        self.login_button = QPushButton("Anmelden")
        self.login_button.setObjectName("login")
        self.logout_button = QPushButton("Abmelden")
        self.logout_button.setObjectName("logout")
        self.login_button.clicked.connect(lambda: model.login())
        self.logout_button.clicked.connect(lambda: model.logout())
        row.addWidget(self.login_button)
        row.addWidget(self.logout_button)
        row.addStretch(1)
        acc.addLayout(row)
        lay.addWidget(account)
        lay.addStretch(1)
        self.open_url = lambda url: QDesktopServices.openUrl(QUrl(url))
        model.settings_changed.connect(self.refresh)
        self.refresh()

    def _login(self) -> dict:
        return self.model.settings.get("login") or {}

    def refresh(self) -> None:
        s = self.model.settings
        if not self.client_id.hasFocus():
            self.client_id.setText(s.get("client_id", ""))
        if not self.channel.hasFocus():
            self.channel.setText(s.get("channel", ""))
        login = self._login()
        state = login.get("state", "idle")
        if s.get("fake"):
            text = f"Testverbindung aktiv: {s.get('bot_login') or 'donstvbot'} (keine echte Verbindung zu Twitch)"
        elif s.get("logged_in"):
            text = f"Angemeldet als {s.get('bot_login') or 'Bot-Konto'}"
        else:
            text = "Nicht angemeldet. Melde dich mit dem Konto «donstvbot» an."
        if state == "failed":
            text += f"\nAnmeldung fehlgeschlagen: {login.get('message', '')}"
        self.account_label.setText(text)
        pending = state == "pending"
        self.code_frame.setVisible(pending)
        if pending:
            self.code_label.setText(
                f"Öffne {login.get('verification_uri', '')} im Browser, melde dich dort als «donstvbot» an "
                f"und bestätige den Code {login.get('user_code', '')}."
            )
        available = self.model.available and not s.get("fake")
        self.login_button.setEnabled(available and bool(s.get("client_id")))
        self.login_button.setToolTip(
            "" if s.get("client_id") else "Zuerst die Client-ID eintragen und speichern"
        )
        self.logout_button.setEnabled(available and bool(s.get("logged_in")))
        self.save_button.setEnabled(self.model.available)

    def _open(self) -> None:
        url = self._login().get("verification_uri", "")
        if url.startswith("https://"):
            self.open_url(url)

    def _copy(self) -> None:
        QApplication.clipboard().setText(str(self._login().get("user_code", "")))


class ChatPanel(QWidget):
    """Live-Chat mit Eingabefeld und «Senden» (F-41, F-42)."""

    def __init__(self, model: BotModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.model = model
        self.setObjectName("chat_panel")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        self.list = QListWidget()
        self.list.setObjectName("chat_list")
        self.list.setAccessibleName("Chat")
        self.list.setWordWrap(True)
        lay.addWidget(self.list, 1)
        row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setObjectName("chat_input")
        self.input.setMaxLength(500)
        self.input.setPlaceholderText("Nachricht an den Chat")
        self.input.setAccessibleName("Nachricht an den Chat")
        self.send_button = QPushButton("Senden")
        self.send_button.setObjectName("chat_send")
        self.send_button.clicked.connect(self.send)
        self.input.returnPressed.connect(self.send)
        row.addWidget(self.input, 1)
        row.addWidget(self.send_button)
        lay.addLayout(row)
        model.chat_added.connect(self._added)
        model.chat_reset.connect(self._reset)
        model.sent.connect(self.input.clear)

    @staticmethod
    def line(m: dict) -> str:
        roles = m.get("roles") or {}
        mark = "★ " if roles.get("broadcaster") else ("⚔ " if roles.get("moderator") else "")
        return f"{clock(float(m.get('ts') or time.time()))}  {mark}{m.get('display_name', '')}: {m.get('text', '')}"

    def _append(self, m: dict) -> None:
        self.list.addItem(self.line(m))
        while self.list.count() > CHAT_LIMIT:
            self.list.takeItem(0)
        self.list.scrollToBottom()

    def _added(self, payload_json: str) -> None:
        self._append(json.loads(payload_json))

    def _reset(self) -> None:
        self.list.clear()
        for m in self.model.chat:
            self._append(m)

    def send(self) -> None:
        text = self.input.text().strip()
        if text:
            self.model.send(text)


class LogPanel(QWidget):
    """Letzte Bot-Ereignisse (F-45)."""

    def __init__(self, model: BotModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.model = model
        self.setObjectName("log_panel")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        self.list = QListWidget()
        self.list.setObjectName("bot_log_list")
        self.list.setAccessibleName("Protokoll")
        lay.addWidget(self.list)
        model.log_added.connect(lambda text: self._append(json.loads(text)))
        model.log_reset.connect(self._reset)

    @staticmethod
    def line(e: dict) -> str:
        return f"{clock(float(e.get('ts') or time.time()), seconds=True)}  {LOG_KINDS.get(e.get('kind', ''), e.get('kind', ''))}: {e.get('message', '')}"

    def _append(self, e: dict) -> None:
        self.list.addItem(self.line(e))
        while self.list.count() > LOG_LIMIT:
            self.list.takeItem(0)
        self.list.scrollToBottom()

    def _reset(self) -> None:
        self.list.clear()
        for e in self.model.log:
            self._append(e)
