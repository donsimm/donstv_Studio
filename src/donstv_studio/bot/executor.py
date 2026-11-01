"""Ausführungs-Schnittstelle (Vorbereitung für F-47 und F-57).

`ActionExecutor.run(action, context)` führt eine Aktion aus. Im Gerüst gibt es nur «Chat-Antwort senden»
(`{"type": "chat.send", "text": …}`). Spätere Bausteine (Sub-Actions, C#-Prozess) hängen weitere Arten an,
ohne dass Commands den Chat selbst kennen müssen.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from donstv_studio.bot import log as botlog
from donstv_studio.bot.log import BotLog

CHAT_SEND = "chat.send"
ACTION_TYPES = (CHAT_SEND,)


class ActionError(Exception):
    """Aktion liess sich nicht ausführen."""


class ActionExecutor:
    def __init__(self, chat: Callable[[], Any], bot_log: BotLog) -> None:
        """`chat` liefert die Twitch-Verbindung (mit `send_message`), so gibt es nur die eine Instanz (F-08)."""
        self._chat = chat
        self._log = bot_log

    async def run(self, action: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        kind = action.get("type")
        if kind == CHAT_SEND:
            return await self._chat_send(str(action.get("text", "")), context)
        raise ActionError(f"Unbekannte Aktion: {kind!r}")

    async def _chat_send(self, text: str, context: dict[str, Any]) -> dict[str, Any]:
        conn = self._chat()
        try:
            if conn is None:
                raise ActionError("Keine Twitch-Verbindung")
            return await conn.send_message(text)
        except Exception as e:
            await self._log.add(
                botlog.SEND_ERROR, f"Senden fehlgeschlagen: {e}",
                {"command": context.get("command", ""), "user": context.get("user", "")},
            )  # fmt: skip
            raise ActionError(str(e)) from e
