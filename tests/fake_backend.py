"""In-Memory-Ersatz für `CoreBackend` (Tests der Oberfläche ohne Kern-Dienst). Verhält sich wie die Schnittstelle P03."""

import copy
import uuid

from donstv_studio.ui.backend import BackendError


class FakeBackend:
    def __init__(self) -> None:
        self.overlays: list[dict] = []
        self.calls: list[tuple] = []
        self.fail_next: str | None = None
        self.media: dict[str, dict] = {}

    def _log(self, *call) -> None:
        self.calls.append(call)
        if self.fail_next is not None:
            msg, self.fail_next = self.fail_next, None
            raise BackendError(msg)

    def _overlay(self, overlay_id: str) -> dict:
        for o in self.overlays:
            if o["id"] == overlay_id:
                return o
        raise BackendError("Overlay gibt es nicht")

    def _public(self, o: dict) -> dict:
        d = copy.deepcopy(o)
        d["url"] = f"http://192.168.1.50:8080/o/{o['id']}?t={o['token']}"
        d["output_status"] = "verfügbar" if o["output"] == "browser" else "nicht verfügbar"
        return d

    def add(self, name: str, width: int = 1920, height: int = 1080) -> dict:
        o = {"id": uuid.uuid4().hex, "name": name, "width": width, "height": height, "output": "browser",
             "token": uuid.uuid4().hex + "GEHEIM", "sources": []}  # fmt: skip
        self.overlays.append(o)
        return o

    def list_overlays(self):
        self._log("list")
        return [self._public(o) for o in self.overlays]

    def create_overlay(self, name, **fields):
        self._log("create_overlay", name)
        return self._public(self.add(name, **fields))

    def update_overlay(self, overlay_id, **fields):
        self._log("update_overlay", overlay_id, fields)
        o = self._overlay(overlay_id)
        o.update(fields)
        return self._public(o)

    def duplicate_overlay(self, overlay_id):
        self._log("duplicate_overlay", overlay_id)
        src = self._overlay(overlay_id)
        new = self.add(f"{src['name']} (Kopie)", src["width"], src["height"])
        new["sources"] = [{**copy.deepcopy(s), "id": uuid.uuid4().hex} for s in src["sources"]]
        return self._public(new)

    def delete_overlay(self, overlay_id):
        self._log("delete_overlay", overlay_id)
        self.overlays.remove(self._overlay(overlay_id))

    def add_source(self, overlay_id, kind, **fields):
        self._log("add_source", overlay_id, kind, fields)
        o = self._overlay(overlay_id)
        s = {
            "id": uuid.uuid4().hex,
            "kind": kind,
            "rotation": 0.0,
            "visible": True,
            "props": {},
            "z": len(o["sources"]),
        }
        s.update(fields)
        o["sources"].append(s)
        return copy.deepcopy(s)

    def update_source(self, overlay_id, source_id, **fields):
        self._log("update_source", overlay_id, source_id, dict(fields))
        for s in self._overlay(overlay_id)["sources"]:
            if s["id"] == source_id:
                s.update(fields)
                return copy.deepcopy(s)
        raise BackendError("Quelle gibt es nicht")

    def delete_source(self, overlay_id, source_id):
        self._log("delete_source", overlay_id, source_id)
        o = self._overlay(overlay_id)
        o["sources"] = [s for s in o["sources"] if s["id"] != source_id]

    def reorder_sources(self, overlay_id, order):
        self._log("reorder_sources", overlay_id, list(order))
        o = self._overlay(overlay_id)
        by_id = {s["id"]: s for s in o["sources"]}
        o["sources"] = [by_id[i] for i in order]
        for z, s in enumerate(o["sources"]):
            s["z"] = z
        return self._public(o)

    def upload_media(self, path):
        self._log("upload_media", path)
        item = {
            "id": uuid.uuid4().hex,
            "name": path.rsplit("/", 1)[-1],
            "mime": "image/png",
            "size": 1,
        }
        self.media[item["id"]] = item
        return item

    def source(self, overlay_id: str, source_id: str) -> dict:
        return next(s for s in self._overlay(overlay_id)["sources"] if s["id"] == source_id)
