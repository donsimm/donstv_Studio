"""Overlay-Server (F-17, F-18): liefert die Overlay-Seite und sendet Änderungen per WebSocket.

Eigener Port (Vorgabe 8080), getrennt von der lokalen Schnittstelle des Kern-Dienstes.
Zugriff nur mit dem Token des Overlays; bei falschem oder fehlendem Token antwortet der Server
immer gleich (404), damit niemand erfährt, ob ein Overlay existiert.
"""

from __future__ import annotations

import asyncio
import contextlib
import secrets
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from donstv_studio.core.bus import Event, EventBus
from donstv_studio.core.ws_session import run_until_closed
from donstv_studio.overlays.media import MediaLibrary
from donstv_studio.overlays.models import NotFoundError, Overlay
from donstv_studio.overlays.service import OverlayService

WEB_DIR = Path(__file__).parent / "web"
_DUMMY = secrets.token_urlsafe(32)

# Token steht in der Adresse; deshalb keine Weitergabe als Referrer und kein Zwischenspeichern.
PAGE_HEADERS = {
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
}
# Medien können SVG enthalten: im Sandkasten ausliefern, falls jemand die Datei direkt öffnet.
MEDIA_HEADERS = {
    "Cache-Control": "private, max-age=3600",
    "Content-Security-Policy": "sandbox; default-src 'none'; style-src 'unsafe-inline'",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
}


def _not_found() -> PlainTextResponse:
    return PlainTextResponse("Nicht gefunden", status_code=404, headers=PAGE_HEADERS)


def _media_ids(o: Overlay) -> set[str]:
    return {
        s.props["media_id"]
        for s in o.sources
        if s.kind == "image" and s.props.get("media_id")
    }


def create_overlay_app(service: OverlayService, media: MediaLibrary, bus: EventBus) -> FastAPI:
    app = FastAPI(title="donstv-overlays", docs_url=None, redoc_url=None, openapi_url=None)

    def authorize(overlay_id: str, token: str | None) -> Overlay | None:
        try:
            overlay = service.get_overlay(overlay_id)
        except NotFoundError:
            overlay = None
        expected = overlay.token if overlay else _DUMMY  # gleiche Arbeit, auch ohne Overlay
        ok = secrets.compare_digest((token or "").encode(), expected.encode())
        return overlay if (ok and overlay is not None) else None

    def payload(o: Overlay) -> dict[str, Any]:
        d = o.to_dict()
        d.pop("token")  # die Seite kennt das Token aus ihrer Adresse
        d.pop("output")
        d.pop("output_status")
        items = {m: media.get(m) for m in _media_ids(o)}
        d["media"] = {m: {"mime": i.mime, "name": i.name} for m, i in items.items() if i}
        return d

    @app.get("/o/{overlay_id}")
    async def page(overlay_id: str, t: str | None = None):
        if authorize(overlay_id, t) is None:
            return _not_found()
        return FileResponse(WEB_DIR / "overlay.html", media_type="text/html", headers=PAGE_HEADERS)

    @app.get("/media/{overlay_id}/{media_id}")
    async def media_file(overlay_id: str, media_id: str, t: str | None = None):
        overlay = authorize(overlay_id, t)
        if overlay is None or media_id not in _media_ids(overlay):
            return _not_found()
        item = media.get(media_id)
        if item is None or not media.path_of(item).exists():
            return _not_found()
        return FileResponse(media.path_of(item), media_type=item.mime, headers=MEDIA_HEADERS)

    @app.websocket("/o/{overlay_id}/ws")
    async def overlay_ws(ws: WebSocket, overlay_id: str) -> None:
        if authorize(overlay_id, ws.query_params.get("t")) is None:
            await ws.close(code=1008)
            return
        await ws.accept()
        changes: asyncio.Queue[str] = asyncio.Queue()

        async def on_change(event: Event) -> None:
            if event.payload.get("overlay_id") == overlay_id:
                changes.put_nowait(event.payload.get("change", ""))

        # Erst abonnieren, dann den Zustand lesen: so geht keine Änderung verloren.
        sub = bus.subscribe("overlay.changed", on_change)

        async def sender() -> None:
            await ws.send_json({"type": "snapshot", "overlay": payload(service.get_overlay(overlay_id))})
            while True:
                change = await changes.get()
                while not changes.empty():  # Änderungen bündeln, die Seite braucht nur den letzten Stand
                    change = changes.get_nowait()
                try:
                    current = service.get_overlay(overlay_id)
                except NotFoundError:
                    await ws.send_json({"type": "deleted"})
                    return
                await ws.send_json({"type": "update", "change": change, "overlay": payload(current)})

        try:
            await run_until_closed(ws, sub, sender)
        finally:
            # Schliesst der Client zuerst (OBS lädt die Seite neu, Vorschau wird geschlossen), wirft `close()` je nach
            # Starlette-Version RuntimeError oder WebSocketDisconnect(1006); beides ist hier harmlos.
            with contextlib.suppress(RuntimeError, WebSocketDisconnect):
                await ws.close()

    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")
    return app
