"""Einstellungen des Editors (Einrasten, Raster, Zoom, Vorschau-Bildrate), gespeichert beim Kern unter `ui.editor.*`."""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import QObject, pyqtSignal

from donstv_studio.ui.geometry import FIT, ZOOM_STEPS
from donstv_studio.ui.preview_web import DEFAULT_FPS, MAX_FPS, MIN_FPS

KEY_SNAP = "ui.editor.snap"
KEY_GRID = "ui.editor.grid"
KEY_GRID_SIZE = "ui.editor.grid_size"
KEY_FPS = "ui.editor.preview_fps"
KEY_SHRINK = "ui.editor.preview_shrink"
KEY_ZOOM = "ui.editor.zoom"
DEFAULT_GRID_SIZE = 20
GRID_MIN, GRID_MAX = 2, 1000


def _flag(raw: str | None, default: bool) -> bool:
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "ja", "yes")


def _int(raw: str | None, default: int, lo: int, hi: int) -> int:
    try:
        return min(max(int(raw), lo), hi) if raw is not None else default
    except ValueError:
        return default


class EditorPrefs(QObject):
    changed = pyqtSignal(str)  # Schlüssel der geänderten Einstellung

    def __init__(
        self, save: Callable[[str, str], None] | None = None, parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self._save = save
        self.snap = True
        self.grid = False
        self.grid_size = DEFAULT_GRID_SIZE
        self.fps = DEFAULT_FPS
        self.shrink = False
        self.zoom: float | str = FIT  # FIT oder Faktor (1.0 = 100 %)

    def load(self, values: dict) -> None:
        old = (self.snap, self.grid, self.grid_size, self.fps, self.shrink, self.zoom)
        self.snap = _flag(values.get(KEY_SNAP), True)
        self.grid = _flag(values.get(KEY_GRID), False)
        self.grid_size = _int(values.get(KEY_GRID_SIZE), DEFAULT_GRID_SIZE, GRID_MIN, GRID_MAX)
        self.fps = _int(values.get(KEY_FPS), DEFAULT_FPS, MIN_FPS, MAX_FPS)
        self.shrink = _flag(values.get(KEY_SHRINK), False)
        raw = values.get(KEY_ZOOM)
        try:
            z = float(raw) if raw and raw != FIT else FIT
        except ValueError:
            z = FIT
        self.zoom = z if z == FIT or any(abs(z - s) < 1e-9 for s in ZOOM_STEPS) else FIT
        if old != (self.snap, self.grid, self.grid_size, self.fps, self.shrink, self.zoom):
            self.changed.emit("*")

    def _set(self, attr: str, key: str, value, text: str) -> None:
        if getattr(self, attr) == value:
            return
        setattr(self, attr, value)
        if self._save is not None:
            self._save(key, text)
        self.changed.emit(key)

    def set_snap(self, on: bool) -> None:
        self._set("snap", KEY_SNAP, bool(on), "1" if on else "0")

    def set_grid(self, on: bool) -> None:
        self._set("grid", KEY_GRID, bool(on), "1" if on else "0")

    def set_grid_size(self, size: int) -> None:
        size = min(max(int(size), GRID_MIN), GRID_MAX)
        self._set("grid_size", KEY_GRID_SIZE, size, str(size))

    def set_fps(self, fps: int) -> None:
        fps = min(max(int(fps), MIN_FPS), MAX_FPS)
        self._set("fps", KEY_FPS, fps, str(fps))

    def set_shrink(self, on: bool) -> None:
        self._set("shrink", KEY_SHRINK, bool(on), "1" if on else "0")

    def set_zoom(self, zoom: float | str) -> None:
        self._set("zoom", KEY_ZOOM, zoom, FIT if zoom == FIT else repr(float(zoom)))
