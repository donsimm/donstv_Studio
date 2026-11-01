"""Ereignis-Bus (F-08): Verbindungen veröffentlichen, Bausteine abonnieren."""

from __future__ import annotations

import fnmatch
import logging
import time
import uuid
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)

Handler = Callable[["Event"], Awaitable[None]]

# Wie viele Kennungen für die Erkennung von Duplikaten gemerkt werden.
MAX_SEEN_IDS = 10_000


@dataclass(frozen=True)
class Event:
    """Normiertes Ereignis: Kennung, Zeit, Quelle, Art, Nutzlast."""

    source: str
    type: str
    payload: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "ts": self.ts,
            "source": self.source,
            "type": self.type,
            "payload": self.payload,
        }


class Subscription:
    """Handle zum Abbestellen."""

    def __init__(self, bus: EventBus, pattern: str, handler: Handler) -> None:
        self._bus = bus
        self.pattern = pattern
        self.handler = handler

    def cancel(self) -> None:
        self._bus._remove(self)


class EventBus:
    """Asynchroner Bus. Muster wie `twitch.*` (fnmatch, `*` passt auch auf Punkte)."""

    def __init__(self, max_seen_ids: int = MAX_SEEN_IDS) -> None:
        self._subs: list[Subscription] = []
        self._seen: OrderedDict[str, None] = OrderedDict()
        self._max_seen = max_seen_ids

    def subscribe(self, pattern: str, handler: Handler) -> Subscription:
        sub = Subscription(self, pattern, handler)
        self._subs.append(sub)
        return sub

    def _remove(self, sub: Subscription) -> None:
        if sub in self._subs:
            self._subs.remove(sub)

    async def publish(self, event: Event) -> bool:
        """Stellt zu. Gibt False zurück, wenn die Kennung schon bekannt war (verworfen)."""
        if event.id in self._seen:
            log.debug("Doppeltes Ereignis verworfen: %s", event.id)
            return False
        self._seen[event.id] = None
        while len(self._seen) > self._max_seen:
            self._seen.popitem(last=False)
        for sub in list(self._subs):
            if not fnmatch.fnmatchcase(event.type, sub.pattern):
                continue
            try:
                await sub.handler(event)
            except Exception:
                # Ein abgestürzter Abonnent darf Bus und andere nicht stoppen.
                log.exception("Abonnent für %r ist abgestürzt (Ereignis %s)", sub.pattern, event.type)
        return True
