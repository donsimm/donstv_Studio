"""Basisklasse einer Verbindung zu einem Dienst (F-08)."""

from __future__ import annotations

from enum import StrEnum

from donstv_studio.core.bus import Event, EventBus


class Status(StrEnum):
    DISCONNECTED = "getrennt"
    CONNECTING = "verbindet"
    CONNECTED = "verbunden"
    ERROR = "Fehler"


class Connection:
    """Gemeinsame Verbindung zu genau einem Dienst. Unterklassen überschreiben start/stop."""

    def __init__(self, name: str, bus: EventBus) -> None:
        self.name = name
        self._bus = bus
        self._status = Status.DISCONNECTED
        self.detail: str | None = None  # kurzer Hinweis zum Zustand, z. B. «nicht eingerichtet»

    @property
    def status(self) -> Status:
        return self._status

    async def set_status(self, status: Status, detail: str | None = None) -> None:
        """Setzt den Status und veröffentlicht `connection.status` (nur bei Änderung)."""
        if status == self._status:
            return
        self._status = status
        self.detail = detail
        payload = {"name": self.name, "status": status.value}
        if detail:
            payload["detail"] = detail
        await self._bus.publish(Event(source=self.name, type="connection.status", payload=payload))

    async def start(self) -> None:
        """Baut die Verbindung auf. Die Basisklasse hat keine echte Verbindung."""

    async def stop(self) -> None:
        """Trennt die Verbindung."""
        await self.set_status(Status.DISCONNECTED)
