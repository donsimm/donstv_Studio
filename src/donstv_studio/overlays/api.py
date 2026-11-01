"""HTTP-Schnittstelle für Overlays und Quellen (hinter dem Token des Kern-Dienstes)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException

from donstv_studio.overlays.models import NotFoundError, OverlayError
from donstv_studio.overlays.service import OverlayService

Body_ = dict[str, Any]


def create_router(service: OverlayService) -> APIRouter:
    router = APIRouter()

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
        return [o.to_dict() for o in service.list_overlays()]

    @router.post("/overlays", status_code=201)
    async def create(body: Body_ = Body(...)) -> Body_:  # noqa: B008
        o = await run(service.create_overlay, **body)
        return o.to_dict()

    @router.get("/overlays/{overlay_id}")
    async def get(overlay_id: str) -> Body_:
        try:
            return service.get_overlay(overlay_id).to_dict()
        except NotFoundError as e:
            raise HTTPException(404, str(e)) from e

    @router.patch("/overlays/{overlay_id}")
    async def update(overlay_id: str, body: Body_ = Body(...)) -> Body_:  # noqa: B008
        return (await run(service.update_overlay, overlay_id, **body)).to_dict()

    @router.post("/overlays/{overlay_id}/duplicate", status_code=201)
    async def duplicate(overlay_id: str) -> Body_:
        return (await run(service.duplicate_overlay, overlay_id)).to_dict()

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
        return (await run(service.reorder_sources, overlay_id, order)).to_dict()

    @router.patch("/overlays/{overlay_id}/sources/{source_id}")
    async def update_source(overlay_id: str, source_id: str, body: Body_ = Body(...)) -> Body_:  # noqa: B008
        return (await run(service.update_source, overlay_id, source_id, **body)).to_dict()

    @router.delete("/overlays/{overlay_id}/sources/{source_id}", status_code=204, response_model=None)
    async def delete_source(overlay_id: str, source_id: str) -> None:
        await run(service.delete_source, overlay_id, source_id)

    return router
