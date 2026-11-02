"""DIAGNOSE (P06d2, P06d3): Teile aus P06d einzeln abschalten, um die Ursache des Absturzes beim Start einzugrenzen.

Nur zur Diagnose, nicht für den Betrieb. Umgebungsvariable `DONSTV_OFF` mit einer Liste (Komma oder Leerzeichen).
Jeder Schalter stellt für sich den Stand von P08 (`6dc8f44`) für diesen Teil her. Werkzeug:
`tools/start_pruefung.py --variante daten,aus=…`.

Schalter aus P06d2 (einzelne Stellen):

- `perf_equalize`  F-78: Leistungsfelder nicht gleich breit; jedes Feld hat seine eigene feste Breite (Stand P08)
- `pointer_badge`  F-75: keine Zeigeranzeige in der Vorschau (Stand P08: Widget gibt es nicht)
- `qss_images`     F-76: Stylesheet ohne Bilder für Häkchen und Pfeile (Stand P08: keine Bilder)
- `min_width`      Mindestbreite des Fensters wie in P08 (Leistungsfelder mit ihrer Breite aus P08 gezählt)
- `rename`         F-74: kein Feld «Name», keine Aktion «Umbenennen» (Stand P08)

Schalter aus P06d3 (je eine ganze Datei aus `git diff 6dc8f44..54f6696 -- src/donstv_studio/ui`):

- `editor_view_changes`   `editor_view.py`: keine Zeigeranzeige (schliesst `pointer_badge` ein), Zeiger gilt immer
                          als «innen», Eckgriffe ohne festes Seitenverhältnis; dazu die Zeigeranzeige wieder in der
                          Statuszeile wie in P08 (Gegenstück in `main_window.py`)
- `editor_model_changes`  `editor_model.py`: Anzeigename der Quellen wie in P08 (ohne Feld «name»), neue Bildquelle
                          ohne Seitenverhältnis (nur auf die Fläche begrenzt). Rückgängig für Namen bleibt (wird beim
                          Start nicht gebraucht; nicht sauber trennbar, ohne `rename_source` zu entfernen)
- `geometry_changes`      `geometry.py`: `fit_inside` wie P08 (`min`), `resize_box` ohne `keep_ratio`. Reine
                          Rechenfunktionen, beim Start nicht aufgerufen
- `theme_changes`         `theme.py`: Stylesheet von P08 (ohne Regeln für Pfeil-Schaltflächen, Kästchen, ohne
                          Farbe `control_border`, ohne Bilder; schliesst `qss_images` ein)
- `indicators_changes`    `indicators.py`: Bilder werden nicht erzeugt (schliesst `qss_images` ein; ohne Bilder
                          wird `indicators.py` gar nicht benutzt, das ist derselbe Zustand)
- `docks_changes`         `editor_docks.py`: keine Mindestbreite für «Rasterweite», Quellenliste mit den
                          Bearbeitungs-Auslösern von Qt und ohne Kontextmenü, Eigenschaften ohne Verbindung zu
                          `sources_changed` und ohne Feld «Name» (schliesst `rename` ein)
- `window_changes`        `main_window.py`: Stylesheet bei jedem Designaufruf neu setzen und Mindestbreite immer
                          sofort (P08); gespeicherte Fensterlage direkt mit `restoreGeometry`, auch ein zweites Mal
                          nach dem Verbinden (P08, vor P06d2)

Nicht schaltbar: `perf.py` (nur die Textliste `width_texts`, mit `perf_equalize` nicht benutzt) und `widgets.py`
ausserhalb von `perf_equalize`; `main.py` (`DONSTV_AUTOQUIT_MS`, ohne die Variable ohne Wirkung).
"""

from __future__ import annotations

import os

ENV = "DONSTV_OFF"
SWITCHES = (
    "perf_equalize",
    "pointer_badge",
    "qss_images",
    "min_width",
    "rename",
    "editor_view_changes",
    "editor_model_changes",
    "geometry_changes",
    "theme_changes",
    "indicators_changes",
    "docks_changes",
    "window_changes",
)
# Ein Schalter für eine ganze Datei schliesst die Einzelschalter darin ein
IMPLIES: dict[str, tuple[str, ...]] = {
    "editor_view_changes": ("pointer_badge",),
    "theme_changes": ("qss_images",),
    "indicators_changes": ("qss_images",),
    "docks_changes": ("rename",),
}


def switched_off() -> frozenset[str]:
    raw = os.environ.get(ENV, "")
    names = {p for p in raw.replace(",", " ").split() if p in SWITCHES}
    for name in list(names):
        names.update(IMPLIES.get(name, ()))
    return frozenset(names)


def off(name: str) -> bool:
    """True, wenn der Teil `name` über `DONSTV_OFF` abgeschaltet ist (nur Diagnose)."""
    return name in switched_off()
