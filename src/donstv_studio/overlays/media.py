"""Bibliothek für Bilder (F-16): Dateien prüfen, speichern, mehrfach verwenden.

Der Typ wird am Inhalt (Magic Bytes) erkannt, nicht an der Dateiendung.
Quellen der Signaturen:
- PNG:  https://www.w3.org/TR/PNG/#5PNG-file-signature
- JPEG: https://www.w3.org/Graphics/JPEG/jfif3.pdf (Start of Image FF D8 FF)
- GIF:  https://www.w3.org/Graphics/GIF/spec-gif89a.txt (Header «GIF87a»/«GIF89a»)
- WebP: https://developers.google.com/speed/webp/docs/riff_container («RIFF», «WEBP»)
- WebM: https://www.matroska.org/technical/elements.html (EBML-Kopf 1A 45 DF A3, DocType «webm»)
- SVG:  https://www.w3.org/TR/SVG11/ (Wurzelelement «svg»)
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import re
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

from donstv_studio.core.store import Store

MAX_BYTES = 25 * 1024 * 1024  # 25 MB pro Datei (F-16)
MAX_NAME = 200

# Endung und MIME-Typ je erkannter Art
TYPES = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "gif": "image/gif",
    "webp": "image/webp",
    "svg": "image/svg+xml",
    "webm": "video/webm",
}


class MediaError(ValueError):
    """Datei abgelehnt; Meldung für Nutzer."""


class TooLargeError(MediaError):
    pass


class UnsupportedTypeError(MediaError):
    pass


class InUseError(MediaError):
    pass


class MediaNotFoundError(LookupError):
    pass


@dataclass(frozen=True)
class MediaItem:
    id: str
    name: str
    mime: str
    ext: str
    size: int
    created_at: float

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "mime": self.mime, "size": self.size}


def detect_type(head: bytes) -> str | None:
    """Erkennt die Dateiart an den ersten Bytes (ohne SVG, das braucht mehr Text)."""
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    if head.startswith(b"\x1a\x45\xdf\xa3") and b"webm" in head[:64]:
        return "webm"
    return None


_ACTIVE_SVG = re.compile(rb"<\s*script|<\s*foreignobject|javascript:|\son[a-z]+\s*=|<!entity", re.IGNORECASE)


def _check_svg(head: bytes, whole: bytes) -> bool:
    text = head.lstrip(b"\xef\xbb\xbf \t\r\n")
    if not (text.startswith((b"<svg", b"<?xml", b"<!--", b"<!DOCTYPE", b"<!doctype")) and b"<svg" in head.lower()):
        return False
    if _ACTIVE_SVG.search(whole):
        raise UnsupportedTypeError("Die SVG-Datei enthält aktive Inhalte (Skripte) und wird abgelehnt")
    return True


def clean_name(name: str | None) -> str:
    base = os.path.basename((name or "").replace("\\", "/")).strip()
    base = re.sub(r"[\x00-\x1f]", "", base)
    return (base or "Bild")[:MAX_NAME]


class MediaLibrary:
    def __init__(self, store: Store, directory: Path) -> None:
        self._store = store
        self._dir = Path(directory)
        self._dir.mkdir(parents=True, exist_ok=True)

    def _item(self, row: tuple) -> MediaItem:
        return MediaItem(*row)

    def list(self) -> list[MediaItem]:
        rows = self._store.query(
            "SELECT id, name, mime, ext, size, created_at FROM media ORDER BY created_at, rowid"
        )
        return [self._item(r) for r in rows]

    def get(self, media_id: str) -> MediaItem | None:
        rows = self._store.query(
            "SELECT id, name, mime, ext, size, created_at FROM media WHERE id = ?", (media_id,)
        )
        return self._item(rows[0]) if rows else None

    def exists(self, media_id: str) -> bool:
        return self.get(media_id) is not None

    def path_of(self, item: MediaItem) -> Path:
        return self._dir / f"{item.id}.{item.ext}"

    def used_by(self, media_id: str) -> list[str]:
        """Kennungen der Overlays, die diese Datei in einer Quelle verwenden."""
        rows = self._store.query(
            "SELECT DISTINCT overlay_id FROM sources "
            "WHERE kind = 'image' AND json_extract(props, '$.media_id') = ?",
            (media_id,),
        )
        return [r[0] for r in rows]

    async def save(self, name: str | None, chunks: AsyncIterator[bytes]) -> MediaItem:
        """Nimmt eine Datei entgegen; bricht bei mehr als 25 MB oder falschem Typ ab."""
        tmp = self._dir / f".upload-{uuid.uuid4().hex}.tmp"
        size = 0
        try:
            # Dateizugriffe in einem Thread, damit der Ereignisfluss nicht blockiert.
            f = await asyncio.to_thread(tmp.open, "wb")
            try:
                async for chunk in chunks:
                    size += len(chunk)
                    if size > MAX_BYTES:
                        raise TooLargeError(
                            f"Die Datei ist grösser als {MAX_BYTES // (1024 * 1024)} MB"
                        )
                    await asyncio.to_thread(f.write, chunk)
            finally:
                await asyncio.to_thread(f.close)
            if size == 0:
                raise UnsupportedTypeError("Die Datei ist leer")
            data = await asyncio.to_thread(tmp.read_bytes)
            kind = detect_type(data[:4096])
            if kind is None and _check_svg(data[:4096], data):
                kind = "svg"
            if kind is None:
                raise UnsupportedTypeError(
                    "Dateityp nicht erlaubt; erlaubt sind png, jpg, gif, webp, svg und webm"
                )
            item = MediaItem(
                id=uuid.uuid4().hex,
                name=clean_name(name),
                mime=TYPES[kind],
                ext=kind,
                size=size,
                created_at=time.time(),
            )
            tmp.replace(self.path_of(item))
        finally:
            with contextlib.suppress(FileNotFoundError):
                tmp.unlink()
        with self._store.transaction() as db:
            db.execute(
                "INSERT INTO media (id, name, mime, ext, size, created_at) VALUES (?,?,?,?,?,?)",
                (item.id, item.name, item.mime, item.ext, item.size, item.created_at),
            )
        return item

    def delete(self, media_id: str) -> None:
        item = self.get(media_id)
        if item is None:
            raise MediaNotFoundError(f"Datei {media_id!r} gibt es nicht")
        if self.used_by(media_id):
            raise InUseError("Die Datei wird noch von einer Quelle verwendet")
        with self._store.transaction() as db:
            db.execute("DELETE FROM media WHERE id = ?", (media_id,))
        with contextlib.suppress(FileNotFoundError):
            self.path_of(item).unlink()
