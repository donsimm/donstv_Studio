"""Lokale Schnittstelle (nur 127.0.0.1) mit Token-Zugriff.

FastAPI: https://fastapi.tiangolo.com/ – WebSockets: https://fastapi.tiangolo.com/advanced/websockets/
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import secrets
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from donstv_studio.core.bus import Event, EventBus
from donstv_studio.core.config import Config, ConfigError
from donstv_studio.core.connections.manager import ConnectionManager

log = logging.getLogger(__name__)

WS_QUEUE_SIZE = 1000
bearer = HTTPBearer(auto_error=False)


def create_token_file(path: Path) -> str:
    """Erzeugt ein neues Token und schreibt es mit Rechten 600."""
    token = secrets.token_urlsafe(32)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(token)
    os.chmod(path, 0o600)
    return token


def create_app(
    token: str, bus: EventBus, manager: ConnectionManager, config: Config
) -> FastAPI:
    app = FastAPI(title="donstv-core", docs_url=None, redoc_url=None, openapi_url=None)
    def valid(candidate: str | None) -> bool:
        return candidate is not None and secrets.compare_digest(candidate, token)

    def require_token(
        cred: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    ) -> None:
        if cred is None or not valid(cred.credentials):
            raise HTTPException(status_code=401, detail="Token fehlt oder ist falsch")

    @app.get("/health", dependencies=[Depends(require_token)])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/connections", dependencies=[Depends(require_token)])
    async def connections() -> dict[str, str]:
        return manager.statuses()

    @app.get("/config/export", dependencies=[Depends(require_token)])
    async def config_export() -> dict[str, Any]:
        return config.export_data()

    @app.post("/config/import", dependencies=[Depends(require_token)])
    async def config_import(request: Request) -> dict[str, str]:
        try:
            data = await request.json()
            config.import_data(data)
        except (ConfigError, ValueError) as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        return {"status": "ok"}

    @app.websocket("/ws/events")
    async def ws_events(ws: WebSocket) -> None:
        # Token per Header «Authorization: Bearer …» oder Abfrage-Parameter «token».
        header = ws.headers.get("authorization", "")
        candidate = header[7:] if header.lower().startswith("bearer ") else ws.query_params.get("token")
        if not valid(candidate):
            await ws.close(code=1008)
            return
        await ws.accept()
        queue: asyncio.Queue[Event] = asyncio.Queue(WS_QUEUE_SIZE)

        async def forward(event: Event) -> None:
            if queue.full():
                with contextlib.suppress(asyncio.QueueEmpty):
                    queue.get_nowait()  # langsamster Client verliert das älteste Ereignis
            queue.put_nowait(event)

        sub = bus.subscribe("*", forward)
        try:
            while True:
                event = await queue.get()
                await ws.send_json(event.to_dict())
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            sub.cancel()

    return app
