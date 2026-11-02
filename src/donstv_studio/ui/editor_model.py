"""Zustand des Editors (F-12, F-13, F-14, F-65): Overlays, Quellen, Auswahl, Hilfslinien, Rückgängig.

Die Oberfläche arbeitet sofort auf einer lokalen Kopie (kein Warten auf das Netz beim Ziehen); der Kern wird über
den `TaskRunner` nachgeführt. Schlägt ein Aufruf fehl, wird der Stand neu vom Kern geladen und eine Meldung gesendet.
Alles Fachliche läuft über die Schnittstelle des Kerns (P03), nicht am Kern vorbei.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal

from donstv_studio.overlays.models import MAX_SOURCE_NAME, default_source_name
from donstv_studio.ui import diagnose, diagnose_p08
from donstv_studio.ui.geometry import Box, fit_inside, nudge_box

log = logging.getLogger(__name__)

HISTORY_LIMIT = 200
MERGE_WINDOW_S = (
    0.8  # Pfeiltasten und Zahlenfelder innerhalb dieser Zeit ergeben einen Rückgängig-Schritt
)
GUIDE_KEY = (
    "ui.guides."  # Einstellungsschlüssel: ui.guides.<Overlay-Kennung> -> {"v": [...], "h": [...]}
)
DEFAULT_TEXT = "Text"
DEFAULT_TEXT_SIZE = (600, 120)
DEFAULT_IMAGE_SIZE = (400, 300)
MAX_GUIDES = 200


def box_of(source: dict) -> Box:
    return Box(
        source["x"],
        source["y"],
        source["width"],
        source["height"],
        float(source.get("rotation", 0.0)),
    )


def source_label(source: dict, media_names: dict[str, str] | None = None) -> str:
    """Anzeigename in der Quellenliste: der Name der Quelle (F-74), sonst der vorgegebene Name."""
    if diagnose.off("editor_model_changes"):  # DIAGNOSE (P06d3): Anzeigename wie P08
        return diagnose_p08.source_label(source, media_names)
    name = source.get("name")
    if isinstance(name, str) and name.strip():
        return name
    props = source.get("props") or {}
    media = (media_names or {}).get(props.get("media_id", ""), "")
    return default_source_name(source["kind"], props, media)


@dataclass
class _Command:
    """Ein Rückgängig-Schritt: `field` «box» (Lage, Grösse, Drehung als Box) oder «name» (Text)."""

    overlay_id: str
    source_id: str
    before: Any
    after: Any
    merge_key: str | None = None
    stamp: float = 0.0
    field: str = "box"


class _History:
    def __init__(self) -> None:
        self.undo: list[_Command] = []
        self.redo: list[_Command] = []


class EditorModel(QObject):
    overlays_changed = pyqtSignal()  # Liste oder Namen der Overlays
    current_changed = pyqtSignal(
        str
    )  # Kennung des gewählten Overlays oder "" (Regel 12: kein object)
    meta_changed = pyqtSignal()  # Name, Auflösung, Ausgabeart des gewählten Overlays
    sources_changed = pyqtSignal()  # Liste, Reihenfolge, Sichtbarkeit der Quellen
    box_changed = pyqtSignal(str)  # Lage, Grösse oder Drehung einer Quelle
    selection_changed = pyqtSignal(str)  # Kennung der gewählten Quelle oder ""
    guides_changed = pyqtSignal()
    history_changed = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(
        self, backend, runner, save_setting: Callable[[str, str], None] | None = None, parent=None
    ) -> None:
        super().__init__(parent)
        self._backend = backend
        self._runner = runner
        self._save_setting = save_setting
        self.overlays: list[dict] = []
        self.current_id: str | None = None
        self.selected_id: str | None = None
        self.media_names: dict[str, str] = {}
        self._guides: dict[str, dict[str, list[int]]] = {}
        self._history: dict[str, _History] = {}
        self._clock = time.monotonic

    # --- Abfragen ---------------------------------------------------------------------------------
    @property
    def available(self) -> bool:
        return self._backend is not None

    def current(self) -> dict | None:
        return self.overlay(self.current_id)

    def overlay(self, overlay_id: str | None) -> dict | None:
        return next((o for o in self.overlays if o["id"] == overlay_id), None)

    def sources(self) -> list[dict]:
        """Quellen des gewählten Overlays, unterste zuerst (Reihenfolge wie im Kern)."""
        o = self.current()
        return o["sources"] if o else []

    def source(self, source_id: str | None) -> dict | None:
        return next((s for s in self.sources() if s["id"] == source_id), None)

    def selected(self) -> dict | None:
        return self.source(self.selected_id)

    def size(self) -> tuple[int, int]:
        o = self.current()
        return (o["width"], o["height"]) if o else (1920, 1080)

    def preview_url(self) -> str | None:
        """Adresse der Overlay-Seite mit Token (Feld «url» des Kerns). Wird nie protokolliert."""
        o = self.current()
        return o.get("url") if o else None

    def others(self) -> list[Box]:
        """Lage der übrigen sichtbaren Quellen (Ziele zum Einrasten)."""
        return [
            box_of(s)
            for s in self.sources()
            if s["id"] != self.selected_id and s.get("visible", True)
        ]

    # --- Laden ------------------------------------------------------------------------------------
    def load(self) -> None:
        if self._backend is None:
            return
        self._runner.submit(self._backend.list_overlays, self._loaded, self._failed)

    def _loaded(self, overlays: list[dict]) -> None:
        self.overlays = overlays
        for o in overlays:
            o["sources"] = sorted(o.get("sources", []), key=lambda s: s.get("z", 0))
        self.overlays_changed.emit()
        if self.overlay(self.current_id) is None:
            self.select_overlay(overlays[0]["id"] if overlays else None)
        else:
            self.meta_changed.emit()
            self.sources_changed.emit()
            if self.selected() is None:
                self.select_source(None)

    def _failed(self, error: Exception) -> None:
        self.error.emit(str(error))

    def _resync(self, error: Exception) -> None:
        """Nach einem fehlgeschlagenen Aufruf: Meldung und Stand neu vom Kern holen."""
        self.error.emit(str(error))
        self.load()

    # --- Overlays (F-10, F-11) --------------------------------------------------------------------
    def select_overlay(self, overlay_id: str | None) -> None:
        if overlay_id is not None and self.overlay(overlay_id) is None:
            overlay_id = None
        changed = overlay_id != self.current_id
        self.current_id = overlay_id
        if changed:
            self.selected_id = None
        self.current_changed.emit(overlay_id or "")
        self.meta_changed.emit()
        self.sources_changed.emit()
        if changed:
            self.selection_changed.emit("")
        self.history_changed.emit()
        self.guides_changed.emit()

    def create_overlay(self, name: str) -> None:
        self._runner.submit(lambda: self._backend.create_overlay(name), self._created, self._failed)

    def _created(self, overlay: dict) -> None:
        overlay.setdefault("sources", [])
        self.overlays.append(overlay)
        self.overlays_changed.emit()
        self.select_overlay(overlay["id"])

    def rename_overlay(self, overlay_id: str, name: str) -> None:
        name = name.strip()
        o = self.overlay(overlay_id)
        if o is None or not name or name == o["name"]:
            return
        o["name"] = name
        self.overlays_changed.emit()
        self.meta_changed.emit()
        self._runner.submit(
            lambda: self._backend.update_overlay(overlay_id, name=name), None, self._resync
        )

    def duplicate_overlay(self, overlay_id: str) -> None:
        self._runner.submit(
            lambda: self._backend.duplicate_overlay(overlay_id), self._created, self._failed
        )

    def delete_overlay(self, overlay_id: str) -> None:
        o = self.overlay(overlay_id)
        if o is None:
            return
        index = self.overlays.index(o)
        self.overlays.remove(o)
        self._history.pop(overlay_id, None)
        if self._guides.pop(overlay_id, None) is not None or self._save_setting:
            self._persist_guides_value(
                overlay_id, ""
            )  # Hilfslinien des gelöschten Overlays entfernen
        self._runner.submit(lambda: self._backend.delete_overlay(overlay_id), None, self._resync)
        self.overlays_changed.emit()
        if self.current_id == overlay_id:
            nxt = self.overlays[min(index, len(self.overlays) - 1)]["id"] if self.overlays else None
            self.current_id = None
            self.select_overlay(nxt)

    def set_output(self, overlay_id: str, output: str) -> None:
        o = self.overlay(overlay_id)
        if o is None or o["output"] == output:
            return
        o["output"] = output
        o["output_status"] = "verfügbar" if output == "browser" else "nicht verfügbar"
        self.meta_changed.emit()
        self._runner.submit(
            lambda: self._backend.update_overlay(overlay_id, output=output), None, self._resync
        )

    # --- Quellen (F-12) ---------------------------------------------------------------------------
    def select_source(self, source_id: str | None) -> None:
        if source_id is not None and self.source(source_id) is None:
            source_id = None
        self.selected_id = source_id
        self.selection_changed.emit(source_id or "")

    def add_text_source(self, text: str = DEFAULT_TEXT) -> None:
        o = self.current()
        if o is None:
            return
        w, h = DEFAULT_TEXT_SIZE
        self._add_source(
            o, "text", min(w, o["width"]), min(h, o["height"]), {"text": text or DEFAULT_TEXT}
        )

    def add_image_source(self, path: str, natural: tuple[int, int] | None = None) -> None:
        """Lädt die Datei in die Bibliothek und legt eine Bildquelle an (F-16). `natural`: Bildgrösse in Pixeln."""
        o = self.current()
        if o is None:
            return
        overlay_id = o["id"]
        w, h = natural if natural and natural[0] > 0 and natural[1] > 0 else DEFAULT_IMAGE_SIZE
        # F-77: Rahmen im Seitenverhältnis des Bildes, verkleinert, bis er ins Overlay passt (ganze Pixel)
        if diagnose.off("editor_model_changes"):  # DIAGNOSE (P06d3): nur begrenzt wie P08
            w, h = min(w, o["width"]), min(h, o["height"])
        else:
            w, h = fit_inside(w, h, o["width"], o["height"])

        def uploaded(item: dict) -> None:
            self.media_names[item["id"]] = item.get("name", "")
            target = self.overlay(overlay_id)
            if target is not None:
                name = default_source_name("image", {}, item.get("name", ""))[:MAX_SOURCE_NAME]
                self._add_source(target, "image", w, h, {"media_id": item["id"]}, name)

        self._runner.submit(lambda: self._backend.upload_media(path), uploaded, self._failed)

    def _add_source(
        self, overlay: dict, kind: str, w: int, h: int, props: dict, name: str = ""
    ) -> None:
        overlay_id = overlay["id"]
        fields = {
            "x": (overlay["width"] - w) // 2,
            "y": (overlay["height"] - h) // 2,
            "width": w,
            "height": h,
            "props": props,
        }
        if name:
            fields["name"] = name

        def added(source: dict) -> None:
            target = self.overlay(overlay_id)
            if target is None:
                return
            target["sources"].append(source)
            if self.current_id == overlay_id:
                self.sources_changed.emit()
                self.select_source(source["id"])

        self._runner.submit(
            lambda: self._backend.add_source(overlay_id, kind, **fields), added, self._failed
        )

    def delete_source(self, source_id: str) -> None:
        o = self.current()
        s = self.source(source_id)
        if o is None or s is None:
            return
        overlay_id = o["id"]
        o["sources"].remove(s)
        hist = self._history.get(overlay_id)
        if hist:
            hist.undo = [c for c in hist.undo if c.source_id != source_id]
            hist.redo = [c for c in hist.redo if c.source_id != source_id]
        if self.selected_id == source_id:
            self.select_source(None)
        self.sources_changed.emit()
        self.history_changed.emit()
        self._runner.submit(
            lambda: self._backend.delete_source(overlay_id, source_id), None, self._resync
        )

    def set_visible(self, source_id: str, visible: bool) -> None:
        o, s = self.current(), self.source(source_id)
        if o is None or s is None or s["visible"] == visible:
            return
        s["visible"] = visible
        self.sources_changed.emit()
        self._send_source(o["id"], source_id, {"visible": visible})

    # --- Name (F-74) -----------------------------------------------------------------------------
    def _set_name(self, source_id: str, name: str) -> bool:
        o, s = self.current(), self.source(source_id)
        if o is None or s is None or s.get("name") == name:
            return False
        s["name"] = name
        self.sources_changed.emit()
        self._send_source(o["id"], source_id, {"name": name})
        return True

    def rename_source(self, source_id: str, name: str) -> bool:
        """Benennt eine Quelle um (mit Rückgängig-Schritt). Leerer Name: abgelehnt, Meldung über `error`."""
        s = self.source(source_id)
        if s is None:
            return False
        name = name.strip() if isinstance(name, str) else ""
        if not name:
            self.error.emit("Der Name der Quelle darf nicht leer sein")
            return False
        if len(name) > MAX_SOURCE_NAME:
            self.error.emit(f"Der Name der Quelle darf höchstens {MAX_SOURCE_NAME} Zeichen haben")
            return False
        before = source_label(s, self.media_names)
        if name == before and s.get("name") == name:
            return True
        self._set_name(source_id, name)
        self._push(source_id, before, name, "name")
        return True

    def move_in_order(self, source_id: str, direction: int) -> None:
        """direction > 0: nach vorn (oben in der Liste); < 0: nach hinten."""
        o = self.current()
        if o is None:
            return
        ids = [s["id"] for s in o["sources"]]
        if source_id not in ids:
            return
        i = ids.index(source_id)
        j = i + (1 if direction > 0 else -1)
        if not 0 <= j < len(ids):
            return
        ids[i], ids[j] = ids[j], ids[i]
        self.set_order(ids)

    def set_order(self, ids: list[str]) -> None:
        """Neue Reihenfolge, unterste Quelle zuerst."""
        o = self.current()
        if o is None or sorted(ids) != sorted(s["id"] for s in o["sources"]):
            return
        by_id = {s["id"]: s for s in o["sources"]}
        o["sources"] = [by_id[i] for i in ids]
        for z, s in enumerate(o["sources"]):
            s["z"] = z
        self.sources_changed.emit()
        overlay_id = o["id"]
        self._runner.submit(
            lambda: self._backend.reorder_sources(overlay_id, list(ids)), None, self._resync
        )

    # --- Lage und Grösse (F-13, F-14, F-65) -------------------------------------------------------
    def _send_source(self, overlay_id: str, source_id: str, fields: dict[str, Any]) -> None:
        backend = self._backend

        def send(**f: Any) -> dict:
            return backend.update_source(overlay_id, source_id, **f)

        self._runner.submit(send, None, self._resync, key=(overlay_id, source_id), fields=fields)

    def set_box(self, source_id: str, box: Box) -> Box | None:
        """Setzt Lage, Grösse und Drehung sofort (lokal und im Kern, zusammengefasst). Kein Rückgängig-Schritt."""
        o, s = self.current(), self.source(source_id)
        if o is None or s is None:
            return None
        before = box_of(s)
        if before == box:
            return before
        s["x"], s["y"], s["width"], s["height"], s["rotation"] = (
            box.x,
            box.y,
            box.w,
            box.h,
            float(box.rot),
        )
        self.box_changed.emit(source_id)
        self._send_source(
            o["id"],
            source_id,
            {"x": box.x, "y": box.y, "width": box.w, "height": box.h, "rotation": float(box.rot)},
        )
        return before

    def push_history(
        self, source_id: str, before: Box, after: Box, merge_key: str | None = None
    ) -> None:
        self._push(source_id, before, after, "box", merge_key)

    def _push(
        self, source_id: str, before: Any, after: Any, field: str, merge_key: str | None = None
    ) -> None:
        o = self.current()
        if o is None or before == after:
            return
        hist = self._history.setdefault(o["id"], _History())
        now = self._clock()
        top = hist.undo[-1] if hist.undo else None
        if (
            merge_key is not None and top is not None and top.merge_key == merge_key
            and top.source_id == source_id and top.field == field
            and now - top.stamp <= MERGE_WINDOW_S
        ):  # fmt: skip
            top.after, top.stamp = after, now
        else:
            hist.undo.append(_Command(o["id"], source_id, before, after, merge_key, now, field))
            del hist.undo[:-HISTORY_LIMIT]
        hist.redo.clear()
        self.history_changed.emit()

    def change_box(self, source_id: str, box: Box, merge_key: str | None = None) -> None:
        """Ändert die Lage mit einem Rückgängig-Schritt (Zahlenfelder, Pfeiltasten, Ausrichten)."""
        before = self.set_box(source_id, box)
        if before is not None:
            self.push_history(source_id, before, box, merge_key)

    def nudge(self, dx: int, dy: int) -> None:
        s = self.selected()
        if s is not None:
            self.change_box(s["id"], nudge_box(box_of(s), dx, dy), merge_key="nudge")

    def _hist(self) -> _History | None:
        return self._history.get(self.current_id or "")

    def can_undo(self) -> bool:
        h = self._hist()
        return bool(h and h.undo)

    def can_redo(self) -> bool:
        h = self._hist()
        return bool(h and h.redo)

    def undo(self) -> None:
        h = self._hist()
        if not h or not h.undo:
            return
        cmd = h.undo.pop()
        h.redo.append(cmd)
        self._apply(cmd, cmd.before)
        self.select_source(cmd.source_id)
        self.history_changed.emit()

    def redo(self) -> None:
        h = self._hist()
        if not h or not h.redo:
            return
        cmd = h.redo.pop()
        h.undo.append(cmd)
        self._apply(cmd, cmd.after)
        self.select_source(cmd.source_id)
        self.history_changed.emit()

    def _apply(self, cmd: _Command, value: Any) -> None:
        if cmd.field == "name":
            self._set_name(cmd.source_id, value)
        else:
            self.set_box(cmd.source_id, value)

    # --- Hilfslinien (pro Overlay gespeichert) ----------------------------------------------------
    def guides(self, overlay_id: str | None = None) -> tuple[list[int], list[int]]:
        """(senkrechte Linien mit x, waagerechte Linien mit y) des Overlays."""
        g = self._guides.get(overlay_id or self.current_id or "", {})
        return list(g.get("v", [])), list(g.get("h", []))

    def set_guides(self, v: list[int], h: list[int]) -> None:
        if self.current_id is None:
            return
        v, h = sorted(set(v))[:MAX_GUIDES], sorted(set(h))[:MAX_GUIDES]
        self._guides[self.current_id] = {"v": v, "h": h}
        self._persist_guides_value(self.current_id, json.dumps({"v": v, "h": h}) if v or h else "")
        self.guides_changed.emit()

    def _persist_guides_value(self, overlay_id: str, value: str) -> None:
        if self._save_setting is not None:
            self._save_setting(GUIDE_KEY + overlay_id, value)

    def load_guides(self, settings: dict[str, str]) -> None:
        """Liest die gespeicherten Hilfslinien aus den Einstellungen des Kerns."""
        found: dict[str, dict[str, list[int]]] = {}
        for key, raw in settings.items():
            if not key.startswith(GUIDE_KEY) or not raw:
                continue
            try:
                data = json.loads(raw)
                v = [int(x) for x in data.get("v", [])]
                h = [int(x) for x in data.get("h", [])]
            except (ValueError, TypeError, AttributeError):
                log.warning("Hilfslinien in %s ungültig und ignoriert", key)
                continue
            found[key[len(GUIDE_KEY) :]] = {"v": v[:MAX_GUIDES], "h": h[:MAX_GUIDES]}
        self._guides = found
        self.guides_changed.emit()

    def wait_idle(self, timeout: float = 3.0) -> bool:
        """Wartet, bis alle Änderungen beim Kern angekommen sind (z. B. vor dem Beenden)."""
        return self._runner.wait_idle(timeout)
