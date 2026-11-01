"""Gemeinsame Szene für die Tests mit echter Webansicht: Kern-Dienst, Overlay mit Text, rotem und gedrehtem grünem Bild."""

from donstv_studio.ui.backend import CoreBackend
from helpers import GREEN, GREEN_BOX, RED, RED_BOX, TEXT_BOX, H, RunningService, W, solid_png

__all__ = [
    "GREEN_BOX",
    "RED_BOX",
    "TEXT_BOX",
    "CoreBackend",
    "H",
    "RunningService",
    "W",
    "build_scene",
]


def build_scene(backend: CoreBackend, overlay_port: int) -> dict:
    """Legt das Overlay über die Schnittstelle des Kerns an. Rückgabe: Kennungen.

    `overlay_port`: Port, auf dem der Test-Dienst lauscht. Die Adresse («url») nennt den Port aus der Konfiguration
    (`overlay.port`, Standard 8080); im Test wird er deshalb auf den freien Port gesetzt.
    """
    import tempfile
    from pathlib import Path

    backend._call("PUT", "/settings/overlay.port", {"value": str(overlay_port)})

    o = backend.create_overlay("Webtest")
    ids = {"overlay": o["id"]}
    with tempfile.TemporaryDirectory() as tmp:
        for key, rgba, w, h in (("red", RED, 200, 150), ("green", GREEN, 200, 100)):
            f = Path(tmp) / f"{key}.png"
            f.write_bytes(solid_png(w, h, rgba))
            ids[f"{key}_media"] = backend.upload_media(str(f))["id"]
    for key, kind, box, extra in (
        (
            "text",
            "text",
            TEXT_BOX,
            {"props": {"text": "Hallo Welt", "size": 48, "color": "#ffffff", "style": "comic"}},
        ),
        ("red", "image", RED_BOX, {"props": {"media_id": ids["red_media"]}}),
        ("green", "image", GREEN_BOX, {"props": {"media_id": ids["green_media"]}, "rotation": 90}),
    ):
        ids[key] = backend.add_source(o["id"], kind, **box, **extra)["id"]
    return ids


__all__ = [
    "GREEN",
    "GREEN_BOX",
    "RED",
    "RED_BOX",
    "TEXT_BOX",
    "CoreBackend",
    "H",
    "RunningService",
    "W",
    "build_scene",
]
