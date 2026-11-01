"""Gemeinsamer Ablauf eines WebSocket-Handlers mit Bus-Abo (lokale Schnittstelle und Overlay-Server).

FastAPI/Starlette WebSockets: https://fastapi.tiangolo.com/advanced/websockets/
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Awaitable, Callable

from fastapi import WebSocket, WebSocketDisconnect

from donstv_studio.core.bus import Subscription


async def run_until_closed(
    ws: WebSocket, subscription: Subscription, sender: Callable[[], Awaitable[None]]
) -> None:
    """Läuft, bis `sender` endet oder der Client die Verbindung schliesst; beendet danach Abo und Aufgaben.

    Der Empfänger liest nur, um das Schliessen (auch beim Beenden des Dienstes) zu bemerken; sonst bliebe der
    Handler im Sender hängen und uvicorn würde auf ihn warten.
    """

    async def receiver() -> None:
        while True:
            await ws.receive_text()

    tasks = [asyncio.create_task(sender()), asyncio.create_task(receiver())]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        subscription.cancel()
        for t in tasks:
            t.cancel()
        for t in tasks:
            with contextlib.suppress(asyncio.CancelledError, WebSocketDisconnect, RuntimeError):
                await t
