"""Speicherung von Overlays und Quellen in SQLite (Tabellen aus Migration 2)."""

from __future__ import annotations

import json

from donstv_studio.core.store import Store
from donstv_studio.overlays.models import Overlay, Source

_SRC_COLS = "id, kind, x, y, width, height, rotation, z, visible, props"


def _source(row: tuple) -> Source:
    return Source(
        id=row[0],
        kind=row[1],
        x=row[2],
        y=row[3],
        width=row[4],
        height=row[5],
        rotation=row[6],
        z=row[7],
        visible=bool(row[8]),
        props=json.loads(row[9]),
    )


def _source_params(overlay_id: str, s: Source) -> tuple:
    return (
        s.id, overlay_id, s.kind, s.x, s.y, s.width, s.height, s.rotation, s.z,
        1 if s.visible else 0, json.dumps(s.props, ensure_ascii=False),
    )  # fmt: skip


_INSERT_SRC = (
    "INSERT INTO sources (id, overlay_id, kind, x, y, width, height, rotation, z, visible, props) "
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
)
_UPDATE_SRC = (
    "UPDATE sources SET kind=?, x=?, y=?, width=?, height=?, rotation=?, z=?, visible=?, props=? "
    "WHERE id=? AND overlay_id=?"
)


class OverlayRepository:
    def __init__(self, store: Store) -> None:
        self._store = store

    def _sources_of(self, overlay_id: str) -> list[Source]:
        rows = self._store.query(
            f"SELECT {_SRC_COLS} FROM sources WHERE overlay_id = ? ORDER BY z, rowid", (overlay_id,)
        )
        return [_source(r) for r in rows]

    def _overlay(self, row: tuple) -> Overlay:
        return Overlay(
            id=row[0], name=row[1], width=row[2], height=row[3], output=row[4], token=row[5],
            sources=self._sources_of(row[0]),
        )  # fmt: skip

    def list(self) -> list[Overlay]:
        rows = self._store.query(
            "SELECT id, name, width, height, output, token FROM overlays ORDER BY rowid"
        )
        return [self._overlay(r) for r in rows]

    def get(self, overlay_id: str) -> Overlay | None:
        rows = self._store.query(
            "SELECT id, name, width, height, output, token FROM overlays WHERE id = ?",
            (overlay_id,),
        )
        return self._overlay(rows[0]) if rows else None

    def insert(self, o: Overlay) -> None:
        with self._store.transaction() as db:
            db.execute(
                "INSERT INTO overlays (id, name, width, height, output, token) VALUES (?,?,?,?,?,?)",
                (o.id, o.name, o.width, o.height, o.output, o.token),
            )
            db.executemany(_INSERT_SRC, [_source_params(o.id, s) for s in o.sources])

    def update_fields(self, o: Overlay) -> None:
        with self._store.transaction() as db:
            db.execute(
                "UPDATE overlays SET name=?, width=?, height=?, output=? WHERE id=?",
                (o.name, o.width, o.height, o.output, o.id),
            )

    def delete(self, overlay_id: str) -> None:
        with self._store.transaction() as db:
            db.execute("DELETE FROM overlays WHERE id = ?", (overlay_id,))  # Quellen: CASCADE

    def insert_source(self, overlay_id: str, s: Source) -> None:
        with self._store.transaction() as db:
            db.execute(_INSERT_SRC, _source_params(overlay_id, s))

    def update_source(self, overlay_id: str, s: Source) -> None:
        with self._store.transaction() as db:
            p = _source_params(overlay_id, s)
            db.execute(_UPDATE_SRC, (*p[2:], s.id, overlay_id))

    def delete_source(self, overlay_id: str, source_id: str) -> None:
        with self._store.transaction() as db:
            db.execute(
                "DELETE FROM sources WHERE id = ? AND overlay_id = ?", (source_id, overlay_id)
            )

    def set_order(self, overlay_id: str, ordered_ids: list[str]) -> None:
        with self._store.transaction() as db:
            db.executemany(
                "UPDATE sources SET z = ? WHERE id = ? AND overlay_id = ?",
                [(z, sid, overlay_id) for z, sid in enumerate(ordered_ids)],
            )
