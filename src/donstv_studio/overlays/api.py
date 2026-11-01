"""HTTP-Schnittstelle für Overlays, Quellen, Bibliothek und Schriften (hinter dem Kern-Token)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException, Request

from donstv_studio.overlays.fonts import font_choices
from donstv_studio.overlays.media import (
    MAX_BYTES,
    InUseError,
    MediaError,
    MediaLibrary,
    MediaNotFoundError,
    TooLargeError,
    UnsupportedTypeError,
)
from donstv_studio.overlays.models import NotFoundError, Overlay, OverlayError
from donstv_studio.overlays.service import OverlayService
from donstv_studio.overlays.urls import UrlBuilder

Body_ = dict[str, Any]


def create_router(
    service: OverlayService,
    urls: UrlBuilder | None = None,
    media: MediaLibrary | None = None,
) -> APIRouter:
    router = APIRouter()

    def out(o: Overlay) -> Body_:
        d = o.to_dict()
        if urls is not None:
            d["url"] = urls.overlay_url(o)  # F-17: fertige URL für die Browserquelle in OBS
        return d

    async def run(func, *args, **kwargs):
        # Aufruf hier, damit auch falsche Feldnamen (TypeError) als 400 gemeldet werden.
        try:
            return await func(*args, **kwargs)
        except NotFoundError as e:
            raise HTTPException(404, str(e)) from e
        except (OverlayError, TypeError) as e:
            raise HTTPException(400, str(e)) from e

    @router.get("/overlays")
    async def list_overlays() -> list[Body_]:
        return [out(o) for o in service.list_overlays()]

    @router.post("/overlays", status_code=201)
    async def create(body: Body_ = Body(...)) -> Body_:  # noqa: B008
        return out(await run(service.create_overlay, **body))

    @router.get("/overlays/{overlay_id}")
    async def get(overlay_id: str) -> Body_:
        try:
            return out(service.get_overlay(overlay_id))
        except NotFoundError as e:
            raise HTTPException(404, str(e)) from e

    @router.patch("/overlays/{overlay_id}")
    async def update(overlay_id: str, body: Body_ = Body(...)) -> Body_:  # noqa: B008
        return out(await run(service.update_overlay, overlay_id, **body))

    @router.post("/overlays/{overlay_id}/duplicate", status_code=201)
    async def duplicate(overlay_id: str) -> Body_:
        return out(await run(service.duplicate_overlay, overlay_id))

    @router.delete("/overlays/{overlay_id}", status_code=204, response_model=None)
    async def delete(overlay_id: str) -> None:
        await run(service.delete_overlay, overlay_id)

    @router.post("/overlays/{overlay_id}/sources", status_code=201)
    async def add_source(overlay_id: str, body: Body_ = Body(...)) -> Body_:  # noqa: B008
        if "kind" not in body:
            raise HTTPException(400, "«kind» fehlt")
        return (await run(service.add_source, overlay_id, **body)).to_dict()

    @router.put("/overlays/{overlay_id}/sources/order")
    async def reorder(overlay_id: str, body: Body_ = Body(...)) -> Body_:  # noqa: B008
        order = body.get("order")
        if not isinstance(order, list):
            raise HTTPException(400, "«order» muss eine Liste von Quellen-Kennungen sein")
        return out(await run(service.reorder_sources, overlay_id, order))

    @router.patch("/overlays/{overlay_id}/sources/{source_id}")
    async def update_source(overlay_id: str, source_id: str, body: Body_ = Body(...)) -> Body_:  # noqa: B008
        return (await run(service.update_source, overlay_id, source_id, **body)).to_dict()

    @router.delete(
        "/overlays/{overlay_id}/sources/{source_id}", status_code=204, response_model=None
    )
    async def delete_source(overlay_id: str, source_id: str) -> None:
        await run(service.delete_source, overlay_id, source_id)

    @router.get("/fonts")
    async def fonts() -> Body_:
        return await font_choices()

    if media is not None:
        _add_media_routes(router, media)
    return router


def _add_media_routes(router: APIRouter, media: MediaLibrary) -> None:
    @router.post("/media", status_code=201)
    async def upload(request: Request, filename: str = "") -> Body_:
        declared = request.headers.get("content-length")
        if declared and declared.isdigit() and int(declared) > MAX_BYTES:
            raise HTTPException(413, "Die Datei ist grösser als 25 MB")
        try:
            item = await media.save(filename, request.stream())
        except TooLargeError as e:
            raise HTTPException(413, str(e)) from e
        except UnsupportedTypeError as e:
            raise HTTPException(415, str(e)) from e
        except MediaError as e:
            raise HTTPException(400, str(e)) from e
        return item.to_dict()

    @router.get("/media")
    async def list_media() -> list[Body_]:
        return [m.to_dict() for m in media.list()]

    @router.delete("/media/{media_id}", status_code=204, response_model=None)
    async def delete_media(media_id: str) -> None:
        try:
            media.delete(media_id)
        except MediaNotFoundError as e:
            raise HTTPException(404, str(e)) from e
        except InUseError as e:
            raise HTTPException(409, str(e)) from e
