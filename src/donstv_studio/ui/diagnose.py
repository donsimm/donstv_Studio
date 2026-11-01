"""DIAGNOSE (P06d2): Teile aus P06d einzeln abschalten, um die Ursache des Absturzes beim Start einzugrenzen.

Nur zur Diagnose, nicht für den Betrieb. Umgebungsvariable `DONSTV_OFF` mit einer Liste (Komma oder Leerzeichen):

- `perf_equalize`  F-78: Leistungsfelder nicht gleich breit; jedes Feld hat seine eigene feste Breite (Stand P08)
- `pointer_badge`  F-75: keine Zeigeranzeige in der Vorschau (Stand P08: Widget gibt es nicht)
- `qss_images`     F-76: Stylesheet ohne Bilder für Häkchen und Pfeile (Stand P08: keine Bilder)
- `min_width`      Mindestbreite des Fensters wie in P08 (Leistungsfelder nicht mitgezählt, siehe unten)
- `rename`         F-74: kein Feld «Name», keine Aktion «Umbenennen» (Stand P08)

Jeder Schalter stellt für sich den Stand von P08 für diesen Teil her. Werkzeug: `tools/start_pruefung.py --variante aus=…`.
"""

from __future__ import annotations

import os

ENV = "DONSTV_OFF"
SWITCHES = ("perf_equalize", "pointer_badge", "qss_images", "min_width", "rename")


def switched_off() -> frozenset[str]:
    raw = os.environ.get(ENV, "")
    return frozenset(p for p in raw.replace(",", " ").split() if p in SWITCHES)


def off(name: str) -> bool:
    """True, wenn der Teil `name` über `DONSTV_OFF` abgeschaltet ist (nur Diagnose)."""
    return name in switched_off()
