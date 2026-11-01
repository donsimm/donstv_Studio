"""Datenmodell für Overlays und Quellen (F-10, F-11, F-12, F-66).

Lage und Grösse sind ganze Pixel (F-65, CLAUDE.md Regel 4); es gibt keine Prozentwerte.
"""

from __future__ import annotations

import json
import math
import secrets
import uuid
from dataclasses import dataclass, field
from typing import Any

SOURCE_KINDS = ("text", "image")
OUTPUTS = ("browser", "ndi")
DEFAULT_WIDTH = 1920
DEFAULT_HEIGHT = 1080
TOKEN_BYTES = 32  # 256 Bit, verlangt sind mindestens 128 Bit


class OverlayError(ValueError):
    """Ungültige Eingabe; die Meldung ist für Nutzer gedacht."""


class NotFoundError(LookupError):
    """Overlay oder Quelle existiert nicht."""


def new_id() -> str:
    return uuid.uuid4().hex


def new_token() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)


def _int(value: Any, label: str, minimum: int | None = None) -> int:
    # bool ist in Python ein int, hier aber nie gemeint.
    if isinstance(value, bool) or not isinstance(value, int):
        raise OverlayError(f"{label} muss eine ganze Zahl (Pixel) sein, erhalten: {value!r}")
    if minimum is not None and value < minimum:
        raise OverlayError(f"{label} muss mindestens {minimum} sein, erhalten: {value}")
    return value


def validate_name(name: Any) -> str:
    if not isinstance(name, str) or not name.strip():
        raise OverlayError("Der Name darf nicht leer sein")
    return name.strip()


def validate_output(output: Any) -> str:
    if output not in OUTPUTS:
        raise OverlayError(f"Ausgabeart muss «browser» oder «ndi» sein, erhalten: {output!r}")
    return output


@dataclass
class Source:
    kind: str
    x: int
    y: int
    width: int
    height: int
    rotation: float = 0.0
    z: int = 0
    visible: bool = True
    props: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=new_id)

    def __post_init__(self) -> None:
        if self.kind not in SOURCE_KINDS:
            raise OverlayError(f"Unbekannte Quellenart {self.kind!r}; erlaubt: {', '.join(SOURCE_KINDS)}")
        _int(self.x, "x")
        _int(self.y, "y")  # Lage darf teilweise ausserhalb des Overlays liegen
        _int(self.width, "Breite der Quelle", 1)
        _int(self.height, "Höhe der Quelle", 1)
        _int(self.z, "z")
        if isinstance(self.rotation, bool) or not isinstance(self.rotation, int | float):
            raise OverlayError(f"Drehung muss eine Zahl (Grad) sein, erhalten: {self.rotation!r}")
        if not math.isfinite(self.rotation):
            raise OverlayError("Drehung muss eine endliche Zahl sein")
        self.rotation = float(self.rotation)
        if not isinstance(self.visible, bool):
            raise OverlayError(f"«visible» muss wahr oder falsch sein, erhalten: {self.visible!r}")
        if not isinstance(self.props, dict):
            raise OverlayError("«props» muss ein Objekt sein")
        try:
            json.dumps(self.props)
        except (TypeError, ValueError) as e:
            raise OverlayError(f"«props» ist nicht speicherbar: {e}") from e

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "rotation": self.rotation,
            "z": self.z,
            "visible": self.visible,
            "props": self.props,
        }


@dataclass
class Overlay:
    name: str
    width: int = DEFAULT_WIDTH
    height: int = DEFAULT_HEIGHT
    output: str = "browser"
    token: str = field(default_factory=new_token)
    sources: list[Source] = field(default_factory=list)
    id: str = field(default_factory=new_id)

    def __post_init__(self) -> None:
        self.name = validate_name(self.name)
        _int(self.width, "Breite des Overlays", 1)
        _int(self.height, "Höhe des Overlays", 1)
        validate_output(self.output)

    @property
    def output_status(self) -> str:
        """NDI darf gespeichert werden, ist aber noch nicht aktiv (F-36 folgt)."""
        return "verfügbar" if self.output == "browser" else "nicht verfügbar"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "width": self.width,
            "height": self.height,
            "output": self.output,
            "output_status": self.output_status,
            "token": self.token,
            "sources": [s.to_dict() for s in self.sources],
        }
