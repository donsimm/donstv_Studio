"""Testverbindung «Twitch» ohne Netz (P07, Tests und Betrieb ohne Client-ID).

Verhält sich nach aussen wie `TwitchConnection`: Name «twitch», Status, `send_message`, Ereignisse
`twitch.chat.message` auf dem Bus. Gesendete Nachrichten kommen wie bei Twitch als Chat-Ereignis des Bot-Kontos
zurück (EventSub liefert auch die eigenen Nachrichten). Im Kern wird sie mit `DONSTV_TWITCH_FAKE=1` gewählt.
"""

from __future__ import annotations

import itertools
import time
from collections import deque
from typing import Any

from donstv_studio.core.bus import EventBus
from donstv_studio.core.connections.base import Connection, Status
from donstv_studio.core.connections.twitch import (
    MAX_MESSAGE,
    SENT_IDS,
    SendError,
    chat_event,
    roles_from_badges,
)

BOT_LOGIN, BOT_ID = "donstvbot", "1001"
CHANNEL_LOGIN, CHANNEL_ID = "donstv2020", "1000"


class FakeTwitch(Connection):
    def __init__(self, bus: EventBus, echo: bool = True) -> None:
        super().__init__("twitch", bus)
        self.echo = echo
        self.sent: list[str] = []
        self.sent_ids: deque[str] = deque(maxlen=SENT_IDS)
        self.fail_next: str | None = None
        self.bot_login, self.bot_user_id = BOT_LOGIN, BOT_ID
        self.channel_login, self.channel_id = CHANNEL_LOGIN, CHANNEL_ID
        self.login_state: dict[str, Any] = {"role": "bot", "state": "done", "login": BOT_LOGIN}
        self._ids = itertools.count(1)

    def account_text(self) -> str:
        return f"{self.bot_login} im Kanal {self.channel_login} (Testverbindung)"

    def reconfigure(self) -> None:
        """Nichts neu aufzubauen."""

    async def start(self) -> None:
        await self.set_status(Status.CONNECTED, self.account_text())

    async def inject(self, user: str, text: str, badges: list[str] | None = None, *,
                     message_id: str | None = None, user_id: str | None = None) -> dict[str, Any]:  # fmt: skip
        """Erzeugt eine Chat-Nachricht wie von Twitch und legt sie auf den Bus."""
        badges = list(badges or [])
        payload = {
            "message_id": message_id or f"fake-{next(self._ids)}",
            "user_id": user_id or ("1000" if "broadcaster" in badges else f"u-{user.lower()}"),
            "user_login": user.lower(),
            "display_name": user,
            "text": text,
            "badges": badges,
            "roles": roles_from_badges(badges),
            "ts": time.time(),
            "channel": self.channel_login,
            "color": "",
            "from_bot": (user_id or "") == self.bot_user_id or user.lower() == self.bot_login,
        }
        await self._bus.publish(chat_event(payload))
        return payload

    async def send_message(self, text: str) -> dict[str, Any]:
        text = text.strip()
        if self.fail_next is not None:
            msg, self.fail_next = self.fail_next, None
            raise SendError(msg)
        if not text:
            raise SendError("Leere Nachricht")
        if len(text) > MAX_MESSAGE:
            raise SendError(f"Nachricht länger als {MAX_MESSAGE} Zeichen")
        if self.status != Status.CONNECTED:
            raise SendError("Twitch ist nicht verbunden")
        self.sent.append(text)
        message_id = f"fake-sent-{next(self._ids)}"
        self.sent_ids.append(message_id)
        if self.echo:
            await self.inject(self.bot_login, text, [], message_id=message_id, user_id=self.bot_user_id)
        return {"message_id": message_id}

    async def begin_login(self, role: str = "bot", on_done=None) -> dict[str, Any]:
        return dict(self.login_state)

    async def logout(self, role: str = "bot") -> None:
        """Die Testverbindung bleibt angemeldet."""
