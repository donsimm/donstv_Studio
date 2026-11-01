"""Hält genau eine Verbindung pro Dienstname (F-08)."""

from __future__ import annotations

import logging

from donstv_studio.core.connections.base import Connection

log = logging.getLogger(__name__)


class DuplicateConnectionError(Exception):
    """Für diesen Namen gibt es schon eine Verbindung."""


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[str, Connection] = {}

    def register(self, connection: Connection) -> None:
        if connection.name in self._connections:
            raise DuplicateConnectionError(
                f"Verbindung «{connection.name}» ist schon registriert (F-08: eine pro Dienst)"
            )
        self._connections[connection.name] = connection

    def get(self, name: str) -> Connection | None:
        return self._connections.get(name)

    def names(self) -> list[str]:
        return sorted(self._connections)

    def statuses(self) -> dict[str, str]:
        return {n: c.status.value for n, c in sorted(self._connections.items())}

    async def start_all(self) -> None:
        for conn in self._connections.values():
            try:
                await conn.start()
            except Exception:
                log.exception("Verbindung «%s» liess sich nicht starten", conn.name)

    async def stop_all(self) -> None:
        for conn in self._connections.values():
            try:
                await conn.stop()
            except Exception:
                log.exception("Verbindung «%s» liess sich nicht beenden", conn.name)
