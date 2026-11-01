"""Bilder für Häkchen und Pfeile der Bedienelemente (F-76), gezeichnet mit QPainter, ohne Qt-SVG-Modul.

Das Stylesheet (`theme.stylesheet`) braucht für `QCheckBox::indicator`, `QSpinBox::up-arrow` usw. Bilddateien
(`image: url(...)`). Auf dem Laptop fehlt das Qt-SVG-Modul (P06c); deshalb entstehen die Bilder hier als PNG in einem
eigenen Ordner unter dem temporären Verzeichnis, je Design einmal pro Prozess, und werden beim Beenden gelöscht.

Farben: nur benannte Werte aus `theme.PALETTES` (Häkchen «check_mark», Pfeile «arrow», ausgegraut «text_muted»).
Jede Datei gibt es einfach und doppelt gross (`@2x`, für Bildschirme mit devicePixelRatio 2).
"""

from __future__ import annotations

import atexit
import shutil
import tempfile
from pathlib import Path

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QColor, QImage, QPainter, QPen, QPolygonF

from donstv_studio.ui import theme

ARROW_SIZE = (9, 6)  # Breite, Höhe der Pfeile in logischen Pixeln (Zahlenfelder, Auswahllisten)
CHECK_SIZE = 12  # Seitenlänge des Häkchens in logischen Pixeln (Kästchen: theme.CHECK_BOX)
SCALES = (1, 2)

_dir: Path | None = None
_cache: dict[str, dict[str, str]] = {}


def _folder() -> Path:
    global _dir
    if _dir is None:
        _dir = Path(tempfile.mkdtemp(prefix="donstv-ui-"))
        atexit.register(shutil.rmtree, _dir, True)
    return _dir


def _image(w: int, h: int, scale: int) -> QImage:
    img = QImage(w * scale, h * scale, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    return img


def draw_arrow(color: str, up: bool, scale: int = 1) -> QImage:
    """Gefülltes Dreieck (Spitze oben oder unten)."""
    w, h = ARROW_SIZE
    img = _image(w, h, scale)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(color))
    s = scale
    if up:
        pts = [QPointF(0, h * s), QPointF(w * s, h * s), QPointF(w * s / 2, 0)]
    else:
        pts = [QPointF(0, 0), QPointF(w * s, 0), QPointF(w * s / 2, h * s)]
    p.drawPolygon(QPolygonF(pts))
    p.end()
    return img


def draw_check(color: str, scale: int = 1) -> QImage:
    """Häkchen aus zwei Strichen."""
    n = CHECK_SIZE
    img = _image(n, n, scale)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color))
    pen.setWidthF(2.0 * scale)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    u = n * scale / 12
    p.drawPolyline(
        QPolygonF([QPointF(2.5 * u, 6.5 * u), QPointF(5 * u, 9 * u), QPointF(9.5 * u, 3 * u)])
    )
    p.end()
    return img


def _save(img_for_scale, name: str, folder: Path) -> str:
    """Speichert `name.png` und `name@2x.png`; gibt den Pfad der einfachen Datei mit «/» zurück."""
    for scale in SCALES:
        suffix = "" if scale == 1 else f"@{scale}x"
        target = folder / f"{name}{suffix}.png"
        if not img_for_scale(scale).save(str(target), "PNG"):
            raise OSError(f"Bild {target} liess sich nicht schreiben")
    return (folder / f"{name}.png").as_posix()


def image_paths(theme_name: str) -> dict[str, str]:
    """Pfade der Bilder für das Design: check, up, down, up_disabled, down_disabled.

    Leeres Wörterbuch, wenn die Dateien nicht geschrieben werden können; dann zeichnet Qt seine eigenen Symbole.
    """
    name = theme_name if theme_name in theme.PALETTES else theme.DEFAULT_THEME
    if name in _cache:
        return _cache[name]
    pal = theme.palette(name)
    try:
        folder = _folder() / name
        folder.mkdir(parents=True, exist_ok=True)
        paths = {
            "check": _save(lambda s: draw_check(pal["check_mark"], s), "check", folder),
            "up": _save(lambda s: draw_arrow(pal["arrow"], True, s), "up", folder),
            "down": _save(lambda s: draw_arrow(pal["arrow"], False, s), "down", folder),
            "up_disabled": _save(
                lambda s: draw_arrow(pal["text_muted"], True, s), "up_disabled", folder
            ),
            "down_disabled": _save(
                lambda s: draw_arrow(pal["text_muted"], False, s), "down_disabled", folder
            ),
        }
    except OSError:
        return {}
    _cache[name] = paths
    return paths
