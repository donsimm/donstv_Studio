"""YouTube-Verbindung als Platzhalter (F-04, F-55 ist KANN).

Im Gerüst gibt es keine echte Verbindung zu YouTube. Der Eintrag existiert, damit die
Statusanzeige der Oberfläche später dieselbe Verbindung mit echten Zuständen zeigt (F-08).
"""

from __future__ import annotations

from donstv_studio.core.bus import EventBus
from donstv_studio.core.connections.base import Connection

NOT_CONFIGURED = "nicht eingerichtet"


class YouTubeConnection(Connection):
    """Meldet immer «getrennt» und baut nie eine Verbindung auf."""

    def __init__(self, bus: EventBus) -> None:
        super().__init__("youtube", bus)
        self.detail = NOT_CONFIGURED

    async def start(self) -> None:
        """Nichts zu starten: kein Zugang eingerichtet."""

    async def stop(self) -> None:
        """Nichts zu beenden; der Zustand bleibt «getrennt»."""
