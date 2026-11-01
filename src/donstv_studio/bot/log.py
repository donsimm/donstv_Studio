"""Protokoll der Bot-Aktivität (F-45).

Jeder Eintrag wird in der Tabelle `bot_log` gespeichert und als Ereignis `bot.log` auf den Bus gelegt; die
Oberfläche erhält ihn über `/ws/events`. Texte werden vor dem Speichern geschwärzt (Regel 7).
"""

from __future__ import annotations

import json
import time
from typing import Any

from donstv_studio.core.bus import Event, EventBus
from donstv_studio.core.logging_setup import redact
from donstv_studio.core.store import Store

KEEP_ENTRIES = 5000  # ältere Einträge werden gelöscht
EVENT_TYPE = "bot.log"

# Arten der Einträge
COMMAND_RUN = "command"  # Command ausgelöst
REJECTED_COOLDOWN = "cooldown"  # abgelehnt wegen Cooldown
REJECTED_PERMISSION = "permission"  # abgelehnt wegen Berechtigung
CONNECTION = "connection"  # Verbindungsstatus
SEND_ERROR = "send_error"  # Sendefehler
AUTH = "auth"  # Anmeldung
KINDS = (COMMAND_RUN, REJECTED_COOLDOWN, REJECTED_PERMISSION, CONNECTION, SEND_ERROR, AUTH)


def _clean(value: Any) -> Any:
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, dict):
        return {str(k): _clean(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_clean(v) for v in value]
    return value


class BotLog:
    def __init__(self, store: Store, bus: EventBus, keep: int = KEEP_ENTRIES) -> None:
        self._store = store
        self._bus = bus
        self._keep = keep

    async def add(
        self, kind: str, message: str, data: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        entry = {
            "ts": time.time(),
            "kind": kind,
            "message": redact(message),
            "data": _clean(data or {}),
        }
        with self._store.transaction() as db:
            cur = db.execute(
                "INSERT INTO bot_log(ts, kind, message, data) VALUES(?, ?, ?, ?)",
                (
                    entry["ts"],
                    kind,
                    entry["message"],
                    json.dumps(entry["data"], ensure_ascii=False),
                ),
            )
            entry["seq"] = cur.lastrowid
            db.execute("DELETE FROM bot_log WHERE seq <= ?", (entry["seq"] - self._keep,))
        await self._bus.publish(Event(source="bot", type=EVENT_TYPE, payload=dict(entry)))
        return entry

    def recent(self, limit: int = 200) -> list[dict[str, Any]]:
        """Die letzten Einträge, ältester zuerst."""
        rows = self._store.query(
            "SELECT seq, ts, kind, message, data FROM bot_log ORDER BY seq DESC LIMIT ?",
            (int(limit),),
        )
        return [
            {"seq": r[0], "ts": r[1], "kind": r[2], "message": r[3], "data": json.loads(r[4])}
            for r in reversed(rows)
        ]
