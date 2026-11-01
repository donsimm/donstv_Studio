"""Commands des Chat-Bots (F-43): Datenmodell, Prüfung und Speicher (Tabelle `bot_commands`)."""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, replace
from typing import Any

from donstv_studio.core.store import Store

# Berechtigungen, aufsteigend. Wer eine höhere Stufe hat, darf auch alles darunter.
PERMISSIONS = ("everyone", "subscriber", "moderator", "broadcaster")
PERMISSION_NAMES = {
    "everyone": "Alle",
    "subscriber": "Abonnenten",
    "moderator": "Moderatoren",
    "broadcaster": "Streamer",
}
MAX_NAME = 100
MAX_TRIGGER = 50
MAX_RESPONSE = 500  # Twitch begrenzt eine Chat-Nachricht auf 500 Zeichen (Quelle: twitch.py, MAX_MESSAGE)
MAX_COOLDOWN = 86_400  # Sekunden (ein Tag)
FIELDS = ("name", "trigger", "permission", "cooldown_global", "cooldown_user", "response", "enabled")


class CommandError(ValueError):
    """Ungültige Angaben zu einem Command; die Meldung ist für Nutzer gedacht."""


@dataclass(frozen=True)
class Command:
    id: str
    name: str
    trigger: str  # z. B. «!regeln», ohne Leerzeichen, klein geschrieben verglichen
    permission: str = "everyone"
    cooldown_global: int = 0  # Sekunden
    cooldown_user: int = 0  # Sekunden
    response: str = ""
    enabled: bool = True
    position: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise CommandError(f"«{field}» muss eine ganze Zahl sein")
    if not 0 <= value <= MAX_COOLDOWN:
        raise CommandError(f"«{field}» muss zwischen 0 und {MAX_COOLDOWN} Sekunden liegen")
    return value


def validate(fields: dict[str, Any]) -> dict[str, Any]:
    """Prüft und normiert die Felder (nur bekannte Felder, unbekannte führen zu einem Fehler)."""
    unknown = set(fields) - set(FIELDS)
    if unknown:
        raise CommandError(f"Unbekannte Felder: {', '.join(sorted(unknown))}")
    out: dict[str, Any] = {}
    if "name" in fields:
        name = fields["name"]
        if not isinstance(name, str) or not name.strip():
            raise CommandError("Der Name darf nicht leer sein")
        if len(name) > MAX_NAME:
            raise CommandError(f"Der Name ist länger als {MAX_NAME} Zeichen")
        out["name"] = name.strip()
    if "trigger" in fields:
        trig = fields["trigger"]
        if not isinstance(trig, str):
            raise CommandError("Der Befehl muss Text sein")
        trig = trig.strip()
        if not trig or any(c.isspace() for c in trig):
            raise CommandError("Der Befehl muss ein Wort ohne Leerzeichen sein, z. B. «!regeln»")
        if len(trig) > MAX_TRIGGER:
            raise CommandError(f"Der Befehl ist länger als {MAX_TRIGGER} Zeichen")
        out["trigger"] = trig
    if "permission" in fields:
        if fields["permission"] not in PERMISSIONS:
            raise CommandError("Unbekannte Berechtigung")
        out["permission"] = fields["permission"]
    for key in ("cooldown_global", "cooldown_user"):
        if key in fields:
            out[key] = _int(fields[key], key)
    if "response" in fields:
        resp = fields["response"]
        if not isinstance(resp, str):
            raise CommandError("Der Antworttext muss Text sein")
        if len(resp) > MAX_RESPONSE:
            raise CommandError(f"Der Antworttext ist länger als {MAX_RESPONSE} Zeichen")
        out["response"] = resp
    if "enabled" in fields:
        if not isinstance(fields["enabled"], bool):
            raise CommandError("«enabled» muss wahr oder falsch sein")
        out["enabled"] = fields["enabled"]
    return out


_COLUMNS = "id, name, trigger, permission, cooldown_global, cooldown_user, response, enabled, position"


def _row(row: tuple) -> Command:
    return Command(row[0], row[1], row[2], row[3], int(row[4]), int(row[5]), row[6], bool(row[7]), int(row[8]))


class CommandRepository:
    """Lesen und Schreiben der Commands. Der Befehl ist eindeutig (ohne Gross-/Kleinschreibung)."""

    def __init__(self, store: Store) -> None:
        self._store = store

    def list(self) -> list[Command]:
        rows = self._store.query(f"SELECT {_COLUMNS} FROM bot_commands ORDER BY position, name")
        return [_row(r) for r in rows]

    def get(self, command_id: str) -> Command | None:
        rows = self._store.query(f"SELECT {_COLUMNS} FROM bot_commands WHERE id = ?", (command_id,))
        return _row(rows[0]) if rows else None

    def _check_unique(self, trigger: str, own_id: str | None) -> None:
        for cmd in self.list():
            if cmd.trigger.lower() == trigger.lower() and cmd.id != own_id:
                raise CommandError(f"Den Befehl «{trigger}» gibt es schon (Command «{cmd.name}»)")

    def _write(self, cmd: Command) -> None:
        with self._store.transaction() as db:
            db.execute(
                f"INSERT INTO bot_commands({_COLUMNS}) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET name=excluded.name, trigger=excluded.trigger, "
                "permission=excluded.permission, cooldown_global=excluded.cooldown_global, "
                "cooldown_user=excluded.cooldown_user, response=excluded.response, "
                "enabled=excluded.enabled, position=excluded.position",
                (cmd.id, cmd.name, cmd.trigger, cmd.permission, cmd.cooldown_global, cmd.cooldown_user,
                 cmd.response, int(cmd.enabled), cmd.position),
            )  # fmt: skip

    def _next_position(self) -> int:
        rows = self._store.query("SELECT COALESCE(MAX(position), -1) FROM bot_commands")
        return int(rows[0][0]) + 1

    def create(self, fields: dict[str, Any]) -> Command:
        data = validate(fields)
        for required in ("name", "trigger"):
            if required not in data:
                raise CommandError("Name und Befehl sind Pflichtfelder")
        self._check_unique(data["trigger"], None)
        cmd = Command(id=uuid.uuid4().hex, position=self._next_position(), **data)
        self._write(cmd)
        return cmd

    def update(self, command_id: str, fields: dict[str, Any]) -> Command:
        cmd = self.get(command_id)
        if cmd is None:
            raise KeyError(command_id)
        data = validate(fields)
        if "trigger" in data:
            self._check_unique(data["trigger"], command_id)
        cmd = replace(cmd, **data)
        self._write(cmd)
        return cmd

    def duplicate(self, command_id: str) -> Command:
        """Kopie mit freiem Befehl («!regeln» → «!regeln2»), inaktiv, damit sie nicht sofort antwortet."""
        src = self.get(command_id)
        if src is None:
            raise KeyError(command_id)
        taken = {c.trigger.lower() for c in self.list()}
        n = 2
        while f"{src.trigger}{n}".lower() in taken:
            n += 1
        cmd = replace(src, id=uuid.uuid4().hex, name=f"{src.name} (Kopie)"[:MAX_NAME],
                      trigger=f"{src.trigger}{n}"[:MAX_TRIGGER], enabled=False, position=self._next_position())  # fmt: skip
        self._check_unique(cmd.trigger, cmd.id)
        self._write(cmd)
        return cmd

    def delete(self, command_id: str) -> bool:
        with self._store.transaction() as db:
            return db.execute("DELETE FROM bot_commands WHERE id = ?", (command_id,)).rowcount > 0
