"""Logik für Overlays und Quellen. Jede Änderung meldet `overlay.changed` auf dem Bus."""

from __future__ import annotations

import copy
import dataclasses
from collections.abc import Callable
from typing import Any

from donstv_studio.core.bus import Event, EventBus
from donstv_studio.overlays.models import (
    DEFAULT_HEIGHT,
    DEFAULT_WIDTH,
    NotFoundError,
    Overlay,
    OverlayError,
    Source,
    new_id,
    new_token,
    validate_name,
    validate_output,
)
from donstv_studio.overlays.repository import OverlayRepository

EVENT_TYPE = "overlay.changed"
_SOURCE_FIELDS = {"x", "y", "width", "height", "rotation", "z", "visible", "props"}
_OVERLAY_FIELDS = {"name", "width", "height", "output"}


def _unknown(keys: set[str], allowed: set[str], what: str) -> None:
    extra = keys - allowed
    if extra:
        raise OverlayError(f"{what}: nicht änderbare oder unbekannte Felder: {', '.join(sorted(extra))}")


class OverlayService:
    def __init__(
        self,
        repo: OverlayRepository,
        bus: EventBus,
        media_exists: Callable[[str], bool] | None = None,
    ) -> None:
        self._repo = repo
        self._bus = bus
        self._media_exists = media_exists

    def _check_media(self, s: Source) -> None:
        """Eine Bildquelle darf nur auf Dateien der Bibliothek zeigen (F-16)."""
        mid = s.props.get("media_id") if s.kind == "image" else None
        if mid and self._media_exists is not None and not self._media_exists(mid):
            raise OverlayError(f"Die Mediendatei {mid!r} gibt es in der Bibliothek nicht")

    async def _changed(self, overlay_id: str, change: str, **extra: Any) -> None:
        payload = {"overlay_id": overlay_id, "change": change, **extra}
        await self._bus.publish(Event(source="overlays", type=EVENT_TYPE, payload=payload))

    def _require(self, overlay_id: str) -> Overlay:
        o = self._repo.get(overlay_id)
        if o is None:
            raise NotFoundError(f"Overlay {overlay_id!r} gibt es nicht")
        return o

    # --- Overlays (F-10, F-11, F-66) --------------------------------------
    def list_overlays(self) -> list[Overlay]:
        return self._repo.list()

    def get_overlay(self, overlay_id: str) -> Overlay:
        return self._require(overlay_id)

    async def create_overlay(
        self,
        name: str,
        width: int = DEFAULT_WIDTH,
        height: int = DEFAULT_HEIGHT,
        output: str = "browser",
    ) -> Overlay:
        o = Overlay(name=name, width=width, height=height, output=output)
        self._repo.insert(o)
        await self._changed(o.id, "created")
        return o

    async def update_overlay(self, overlay_id: str, **changes: Any) -> Overlay:
        """Name, Auflösung und Ausgabeart ändern."""
        _unknown(set(changes), _OVERLAY_FIELDS, "Overlay")
        o = self._require(overlay_id)
        new = dataclasses.replace(o, **changes)  # prüft über __post_init__
        self._repo.update_fields(new)
        for field_, label in (("name", "renamed"), ("output", "output")):
            if field_ in changes and changes[field_] != getattr(o, field_):
                await self._changed(o.id, label)
        if ("width" in changes or "height" in changes) and (
            (new.width, new.height) != (o.width, o.height)
        ):
            await self._changed(o.id, "resolution")
        return new

    async def rename_overlay(self, overlay_id: str, name: str) -> Overlay:
        return await self.update_overlay(overlay_id, name=validate_name(name))

    async def set_resolution(self, overlay_id: str, width: int, height: int) -> Overlay:
        return await self.update_overlay(overlay_id, width=width, height=height)

    async def set_output(self, overlay_id: str, output: str) -> Overlay:
        return await self.update_overlay(overlay_id, output=validate_output(output))

    async def duplicate_overlay(self, overlay_id: str) -> Overlay:
        """Kopiert alle Quellen mit neuen Kennungen und vergibt einen neuen Token."""
        o = self._require(overlay_id)
        copy_ = Overlay(
            name=f"{o.name} (Kopie)",
            width=o.width,
            height=o.height,
            output=o.output,
            token=new_token(),
            sources=[
                dataclasses.replace(s, id=new_id(), props=copy.deepcopy(s.props)) for s in o.sources
            ],
        )
        self._repo.insert(copy_)
        await self._changed(copy_.id, "duplicated", source_overlay_id=o.id)
        return copy_

    async def delete_overlay(self, overlay_id: str) -> None:
        self._require(overlay_id)
        self._repo.delete(overlay_id)
        await self._changed(overlay_id, "deleted")

    # --- Quellen (F-12) ---------------------------------------------------
    async def add_source(self, overlay_id: str, kind: str, **fields: Any) -> Source:
        _unknown(set(fields), _SOURCE_FIELDS, "Quelle")
        o = self._require(overlay_id)
        fields.setdefault("z", max((s.z for s in o.sources), default=-1) + 1)
        if not {"x", "y", "width", "height"} <= set(fields):
            raise OverlayError("Quelle braucht x, y, width und height (ganze Pixel)")
        s = Source(kind=kind, **fields)
        self._check_media(s)
        self._repo.insert_source(overlay_id, s)
        await self._changed(overlay_id, "source_added", source_id=s.id)
        return s

    def _source(self, o: Overlay, source_id: str) -> Source:
        for s in o.sources:
            if s.id == source_id:
                return s
        raise NotFoundError(f"Quelle {source_id!r} gibt es in diesem Overlay nicht")

    async def update_source(self, overlay_id: str, source_id: str, **changes: Any) -> Source:
        _unknown(set(changes), _SOURCE_FIELDS, "Quelle")
        o = self._require(overlay_id)
        new = dataclasses.replace(self._source(o, source_id), **changes)
        self._check_media(new)
        self._repo.update_source(overlay_id, new)
        await self._changed(overlay_id, "source_updated", source_id=source_id)
        return new

    async def set_source_visible(self, overlay_id: str, source_id: str, visible: bool) -> Source:
        return await self.update_source(overlay_id, source_id, visible=visible)

    async def delete_source(self, overlay_id: str, source_id: str) -> None:
        self._source(self._require(overlay_id), source_id)
        self._repo.delete_source(overlay_id, source_id)
        await self._changed(overlay_id, "source_removed", source_id=source_id)

    async def reorder_sources(self, overlay_id: str, ordered_ids: list[str]) -> Overlay:
        """Neue Reihenfolge (unten zuerst); muss genau die vorhandenen Quellen enthalten."""
        o = self._require(overlay_id)
        if sorted(ordered_ids) != sorted(s.id for s in o.sources):
            raise OverlayError("Die Reihenfolge muss genau alle Quellen des Overlays enthalten")
        self._repo.set_order(overlay_id, list(ordered_ids))
        await self._changed(overlay_id, "sources_reordered")
        return self._require(overlay_id)
