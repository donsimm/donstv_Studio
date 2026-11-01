"""F-10, F-11, F-12, F-66: HTTP-Schnittstelle mit Token."""

import pytest
from fastapi.testclient import TestClient

from donstv_studio.core.api import create_app
from donstv_studio.core.bus import EventBus
from donstv_studio.core.config import Config
from donstv_studio.core.connections.manager import ConnectionManager
from donstv_studio.core.store import Store
from donstv_studio.overlays.repository import OverlayRepository
from donstv_studio.overlays.service import OverlayService

H = {"Authorization": "Bearer t0ken"}
BOX = {"x": 1, "y": 2, "width": 30, "height": 40}


@pytest.fixture
def env(tmp_path):
    store, bus, events = Store(tmp_path / "a.db"), EventBus(), []

    async def collect(e):
        events.append(e.payload)

    bus.subscribe("overlay.changed", collect)
    svc = OverlayService(OverlayRepository(store), bus)
    app = create_app("t0ken", bus, ConnectionManager(), Config(store), svc)
    with TestClient(app) as client:
        yield client, events


@pytest.mark.parametrize(
    ("method", "path"),
    [("get", "/overlays"), ("post", "/overlays"), ("get", "/overlays/x"), ("delete", "/overlays/x"),
     ("post", "/overlays/x/sources"), ("put", "/overlays/x/sources/order")],
)  # fmt: skip
def test_f10_refused_without_token(env, method, path):
    assert getattr(env[0], method)(path).status_code == 401


def test_f10_f11_f66_full_cycle(env):
    c, events = env
    r = c.post("/overlays", json={"name": "A"}, headers=H)
    assert r.status_code == 201
    o = r.json()
    assert (o["width"], o["height"], o["output"]) == (1920, 1080, "browser")
    oid = o["id"]
    r = c.patch(f"/overlays/{oid}", json={"name": "B", "width": 1280, "height": 720, "output": "ndi"}, headers=H)
    assert r.json()["output_status"] == "nicht verfügbar"
    assert c.get(f"/overlays/{oid}", headers=H).json()["name"] == "B"
    dup = c.post(f"/overlays/{oid}/duplicate", headers=H).json()
    assert dup["token"] != o["token"]
    assert len(c.get("/overlays", headers=H).json()) == 2
    assert c.delete(f"/overlays/{oid}", headers=H).status_code == 204
    assert c.get(f"/overlays/{oid}", headers=H).status_code == 404
    assert {e["change"] for e in events} >= {"created", "renamed", "resolution", "output", "duplicated", "deleted"}


def test_f12_source_cycle_and_errors(env):
    c, events = env
    oid = c.post("/overlays", json={"name": "A"}, headers=H).json()["id"]
    a = c.post(f"/overlays/{oid}/sources", json={"kind": "text", **BOX}, headers=H).json()
    b = c.post(f"/overlays/{oid}/sources", json={"kind": "image", **BOX}, headers=H).json()
    r = c.put(f"/overlays/{oid}/sources/order", json={"order": [b["id"], a["id"]]}, headers=H)
    assert [s["id"] for s in r.json()["sources"]] == [b["id"], a["id"]]
    r = c.patch(f"/overlays/{oid}/sources/{a['id']}", json={"visible": False, "x": -3}, headers=H)
    assert r.json()["visible"] is False and r.json()["x"] == -3
    assert c.delete(f"/overlays/{oid}/sources/{a['id']}", headers=H).status_code == 204
    assert [e["change"] for e in events][-1] == "source_removed"
    # Fehler mit klarer Meldung
    assert c.post(f"/overlays/{oid}/sources", json={"kind": "text", **BOX, "width": 0}, headers=H).status_code == 400
    r = c.post(f"/overlays/{oid}/sources", json={"kind": "text", **BOX, "x": 1.5}, headers=H)
    assert r.status_code == 400 and "ganze Zahl" in r.json()["detail"]
    assert c.post(f"/overlays/{oid}/sources", json=BOX, headers=H).status_code == 400
    assert c.post("/overlays", json={"name": ""}, headers=H).status_code == 400
    assert c.post("/overlays", json={"name": "A", "unbekannt": 1}, headers=H).status_code == 400
    assert c.patch(f"/overlays/{oid}", json={"id": "x"}, headers=H).status_code == 400
    assert c.patch("/overlays/nope", json={"name": "x"}, headers=H).status_code == 404
    assert c.put(f"/overlays/{oid}/sources/order", json={"order": "x"}, headers=H).status_code == 400
