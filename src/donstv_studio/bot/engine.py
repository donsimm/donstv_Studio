"""Ausführung der Commands im Chat (F-44) und Chat-Verlauf für die Oberfläche (F-41).

Der Bot liest nur vom Ereignis-Bus (Regel 3). Ein Chat-Ereignis, dessen erstes Wort einem aktiven Befehl
entspricht (ohne Gross-/Kleinschreibung), löst die Antwort aus, wenn Berechtigung und Cooldown es erlauben.
Nachrichten des Bot-Kontos selbst lösen nie etwas aus (Schleifenschutz).
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from collections.abc import Callable
from typing import Any

from donstv_studio.bot import log as botlog
from donstv_studio.bot.commands import PERMISSION_NAMES, PERMISSIONS, Command, CommandRepository
from donstv_studio.bot.executor import CHAT_SEND, ActionError, ActionExecutor
from donstv_studio.bot.log import BotLog
from donstv_studio.core.bus import Event, EventBus
from donstv_studio.core.connections.twitch import CHAT_EVENT

log = logging.getLogger(__name__)

CHAT_HISTORY = 500  # so viele Nachrichten hält der Kern für die Oberfläche bereit
# Unsichtbare Zeichen, die manche Chat-Programme anhängen (z. B. U+E0000 gegen die Doppel-Sperre von Twitch)
_INVISIBLE = "\U000e0000\u200b‌‍⁠﻿"
USER_PLACEHOLDER = "{user}"


def level(roles: dict[str, bool]) -> int:
    """Höchste Stufe des Absenders: 0 Alle, 1 Abonnenten, 2 Moderatoren, 3 Streamer. [ANNAHME: Stufen schliessen
    die tieferen ein, z. B. darf ein Moderator auch Abonnenten-Commands auslösen.]"""
    if roles.get("broadcaster"):
        return 3
    if roles.get("moderator"):
        return 2
    if roles.get("subscriber"):
        return 1
    return 0


def first_word(text: str) -> str:
    cleaned = "".join(c for c in text if c not in _INVISIBLE).strip()
    return cleaned.split(maxsplit=1)[0].lower() if cleaned else ""


def render(template: str, payload: dict[str, Any]) -> str:
    """Setzt `{user}` ein (Anzeigename). Keine weiteren Platzhalter; kein str.format (sicher gegen Klammern)."""
    return template.replace(USER_PLACEHOLDER, str(payload.get("display_name") or payload.get("user_login") or ""))


class CommandEngine:
    def __init__(
        self,
        bus: EventBus,
        commands: CommandRepository,
        executor: ActionExecutor,
        bot_log: BotLog,
        chat: Callable[[], Any],
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._commands = commands
        self._executor = executor
        self._log = bot_log
        self._chat = chat
        self._clock = clock
        self._last_global: dict[str, float] = {}
        self._last_user: dict[tuple[str, str], float] = {}
        self.history: deque[dict[str, Any]] = deque(maxlen=CHAT_HISTORY)
        self._tasks: set[asyncio.Task] = set()
        self._subs = [bus.subscribe(CHAT_EVENT, self._on_chat), bus.subscribe("connection.status", self._on_status),
                      bus.subscribe("twitch.auth", self._on_auth)]  # fmt: skip

    def close(self) -> None:
        for sub in self._subs:
            sub.cancel()

    def _is_own(self, payload: dict[str, Any]) -> bool:
        conn = self._chat()
        if payload.get("from_bot"):
            return True
        if conn is not None:
            if payload.get("message_id") in getattr(conn, "sent_ids", ()):
                return True
            bot_id = getattr(conn, "bot_user_id", None)
            if bot_id and payload.get("user_id") == bot_id:
                return True
        return False

    def _find(self, word: str) -> Command | None:
        if not word:
            return None
        for cmd in self._commands.list():
            if cmd.enabled and cmd.trigger.lower() == word:
                return cmd
        return None

    async def _on_chat(self, event: Event) -> None:
        payload = event.payload
        self.history.append(dict(payload))
        if self._is_own(payload):
            return
        cmd = self._find(first_word(str(payload.get("text", ""))))
        if cmd is not None:
            # Eigene Aufgabe: Das Senden wartet auf Twitch; andere Abonnenten (Oberfläche, Overlays) sollen die
            # Nachricht vorher erhalten, und die Antwort erscheint nach der auslösenden Nachricht.
            task = asyncio.create_task(self._handle_safely(cmd, payload))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)

    async def _handle_safely(self, cmd: Command, payload: dict[str, Any]) -> None:
        try:
            await self.handle(cmd, payload)
        except Exception:
            log.exception("Command %s ist abgestürzt", cmd.trigger)

    async def drain(self) -> None:
        """Wartet, bis alle ausgelösten Commands fertig sind (Tests, Beenden)."""
        while self._tasks:
            await asyncio.gather(*list(self._tasks), return_exceptions=True)

    async def handle(self, cmd: Command, payload: dict[str, Any]) -> bool:
        user = str(payload.get("display_name") or payload.get("user_login") or "")
        user_id = str(payload.get("user_id") or payload.get("user_login") or "")
        info = {"command": cmd.trigger, "user": user}
        if level(payload.get("roles") or {}) < PERMISSIONS.index(cmd.permission):
            await self._log.add(botlog.REJECTED_PERMISSION,
                                f"{cmd.trigger} von {user} abgelehnt: nur für {PERMISSION_NAMES[cmd.permission]}", info)  # fmt: skip
            return False
        now = self._clock()
        wait_global = cmd.cooldown_global - (now - self._last_global.get(cmd.id, float("-inf")))
        wait_user = cmd.cooldown_user - (now - self._last_user.get((cmd.id, user_id), float("-inf")))
        if wait_global > 0 or wait_user > 0:
            which = "global" if wait_global >= wait_user else "pro Nutzer"
            remaining = max(1, round(max(wait_global, wait_user)))
            await self._log.add(botlog.REJECTED_COOLDOWN,
                                f"{cmd.trigger} von {user} abgelehnt: Cooldown {which}, noch {remaining} s",
                                {**info, "cooldown": which, "remaining": remaining})  # fmt: skip
            return False
        self._last_global[cmd.id] = now
        self._last_user[(cmd.id, user_id)] = now
        text = render(cmd.response, payload)
        await self._log.add(botlog.COMMAND_RUN, f"{cmd.trigger} von {user} ausgelöst", info)
        if not text.strip():
            return True
        try:
            await self._executor.run({"type": CHAT_SEND, "text": text}, info)
        except ActionError:
            return False  # schon protokolliert (Sendefehler)
        return True

    async def _on_status(self, event: Event) -> None:
        p = event.payload
        if p.get("name") != "twitch":
            return
        detail = f" ({p['detail']})" if p.get("detail") else ""
        await self._log.add(botlog.CONNECTION, f"Twitch: {p.get('status', '')}{detail}",
                            {"status": p.get("status", ""), "detail": p.get("detail", "")})  # fmt: skip

    async def _on_auth(self, event: Event) -> None:
        p = event.payload
        state = p.get("state")
        if state == "pending":
            msg = "Anmeldung Bot-Konto gestartet, Code wartet auf Bestätigung"
        elif state == "done":
            msg = f"Anmeldung Bot-Konto erfolgreich ({p.get('login', '')})"
        elif state == "failed":
            msg = f"Anmeldung Bot-Konto fehlgeschlagen: {p.get('message', '')}"
        else:
            msg = "Bot-Konto abgemeldet"
        await self._log.add(botlog.AUTH, msg, {"state": state or ""})
