"""Datenmodell für Overlays und Quellen (F-10, F-11, F-12, F-66).

Lage und Grösse sind ganze Pixel (F-65, CLAUDE.md Regel 4); es gibt keine Prozentwerte.
"""

from __future__ import annotations

import json
import math
import re
import secrets
import uuid
from dataclasses import dataclass, field
from typing import Any

SOURCE_KINDS = ("text", "image")
OUTPUTS = ("browser", "ndi")
DEFAULT_WIDTH = 1920
DEFAULT_HEIGHT = 1080
TOKEN_BYTES = 32  # 256 Bit, verlangt sind mindestens 128 Bit
MAX_SIDE = 8192  # [ANNAHME] Obergrenze für Breite und Höhe eines Overlays, in Pixeln

DEFAULT_FONT = "Be Vietnam Pro"
TEXT_STYLES = ("comic", "comic_thick", "plain", "none")  # Comic, Comic dick, Schlicht, Ohne
TEXT_STYLE_LABELS = {"comic": "Comic", "comic_thick": "Comic dick", "plain": "Schlicht", "none": "Ohne"}
MAX_TEXT_LENGTH = 5000
MAX_FONT_SIZE = 2000
_COLOR = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
# Schriftname geht in CSS; deshalb nur harmlose Zeichen (keine Anführungszeichen, Klammern { } ; < >).
_FONT = re.compile(r"^[\w .,+&()\-]{1,100}$")
_MEDIA_ID = re.compile(r"^[0-9a-f]{32}$")


class OverlayError(ValueError):
    """Ungültige Eingabe; die Meldung ist für Nutzer gedacht."""


class NotFoundError(LookupError):
    """Overlay oder Quelle existiert nicht."""


def new_id() -> str:
    return uuid.uuid4().hex


def new_token() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)


def _int(value: Any, label: str, minimum: int | None = None, maximum: int | None = None) -> int:
    # bool ist in Python ein int, hier aber nie gemeint.
    if isinstance(value, bool) or not isinstance(value, int):
        raise OverlayError(f"{label} muss eine ganze Zahl (Pixel) sein, erhalten: {value!r}")
    if minimum is not None and value < minimum:
        raise OverlayError(f"{label} muss mindestens {minimum} sein, erhalten: {value}")
    if maximum is not None and value > maximum:
        raise OverlayError(f"{label} darf höchstens {maximum} sein, erhalten: {value}")
    return value


def _only_keys(props: dict[str, Any], allowed: set[str], kind: str) -> None:
    extra = set(props) - allowed
    if extra:
        raise OverlayError(
            f"Quelle «{kind}»: unbekannte Eigenschaften: {', '.join(sorted(extra))}; "
            f"erlaubt: {', '.join(sorted(allowed))}"
        )


def validate_props(kind: str, props: dict[str, Any]) -> None:
    """Prüft die Eigenschaften je Quellenart (F-15, F-16, F-38). Fehlende Werte gelten als Standard."""
    if kind == "text":
        _only_keys(props, {"text", "color", "size", "font", "style"}, kind)
        if "text" in props and (
            not isinstance(props["text"], str) or len(props["text"]) > MAX_TEXT_LENGTH
        ):
            raise OverlayError(f"Text muss eine Zeichenkette mit höchstens {MAX_TEXT_LENGTH} Zeichen sein")
        if "color" in props and not (isinstance(props["color"], str) and _COLOR.match(props["color"])):
            raise OverlayError(f"Farbe muss die Form #RRGGBB haben, erhalten: {props['color']!r}")
        if "size" in props:
            _int(props["size"], "Schriftgrösse", 1, MAX_FONT_SIZE)
        if "font" in props and not (isinstance(props["font"], str) and _FONT.match(props["font"])):
            raise OverlayError(f"Ungültiger Schriftname: {props['font']!r}")
        if "style" in props and props["style"] not in TEXT_STYLES:
            raise OverlayError(
                f"Stil muss einer von {', '.join(TEXT_STYLES)} sein, erhalten: {props['style']!r}"
            )
    elif kind == "image":
        _only_keys(props, {"media_id"}, kind)
        if "media_id" in props and not (
            props["media_id"] == "" or (isinstance(props["media_id"], str) and _MEDIA_ID.match(props["media_id"]))
        ):
            raise OverlayError(f"Ungültige Bild-Kennung: {props['media_id']!r}")


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
        validate_props(self.kind, self.props)

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
        _int(self.width, "Breite des Overlays", 1, MAX_SIDE)
        _int(self.height, "Höhe des Overlays", 1, MAX_SIDE)
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
