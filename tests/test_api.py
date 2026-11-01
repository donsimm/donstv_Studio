"""Lokale Schnittstelle: Zugriff nur mit Token."""

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from donstv_studio.core.api import create_app, create_token_file
from donstv_studio.core.bus import Event, EventBus
from donstv_studio.core.config import Config
from donstv_studio.core.connections.base import Connection
from donstv_studio.core.connections.manager import ConnectionManager
from donstv_studio.core.store import Store

TOKEN = "t0ken"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def env(tmp_path):
    bus, mgr = EventBus(), ConnectionManager()
    mgr.register(Connection("obs", bus))
    cfg = Config(Store(tmp_path / "a.db"))
    with TestClient(create_app(TOKEN, bus, mgr, cfg)) as client:
        yield client, bus, cfg


@pytest.mark.parametrize(
    ("method", "path"),
    [("get", "/health"), ("get", "/connections"), ("get", "/config/export"), ("post", "/config/import")],
)
def test_refuses_without_or_with_wrong_token(env, method, path):
    client = env[0]
    assert getattr(client, method)(path).status_code == 401
    r = getattr(client, method)(path, headers={"Authorization": "Bearer falsch"})
    assert r.status_code == 401


def test_health_and_connections_with_token(env):
    client = env[0]
    assert client.get("/health", headers=AUTH).json() == {"status": "ok"}
    assert client.get("/connections", headers=AUTH).json() == {"obs": "getrennt"}


def test_config_export_import_roundtrip(env):
    client, _, cfg = env
    cfg.set("k", "v")
    exported = client.get("/config/export", headers=AUTH).json()
    cfg.set("k", "anders")
    assert client.post("/config/import", json=exported, headers=AUTH).status_code == 200
    assert cfg.get("k") == "v"
    assert client.post("/config/import", json={"x": 1}, headers=AUTH).status_code == 400
    r = client.post("/config/import", content="kein json", headers=AUTH)
    assert r.status_code == 400


def test_websocket_requires_token(env):
    client = env[0]
    with pytest.raises(WebSocketDisconnect), client.websocket_connect("/ws/events"):
        pass
    with pytest.raises(WebSocketDisconnect), client.websocket_connect("/ws/events?token=falsch"):
        pass


def test_websocket_receives_events(env):
    client, bus, _ = env
    with client.websocket_connect("/ws/events", headers=AUTH) as ws:
        client.portal.call(bus.publish, Event("obs", "obs.scene.changed", {"scene": "A"}, id="e1"))
        msg = ws.receive_json()
    assert msg["id"] == "e1" and msg["payload"] == {"scene": "A"}


def test_token_file_mode(tmp_path):
    import stat

    p = tmp_path / "c" / "api-token"
    t1 = create_token_file(p)
    assert p.read_text() == t1 and len(t1) >= 32
    assert stat.S_IMODE(p.stat().st_mode) == 0o600
    assert create_token_file(p) != t1


# --- P05: Einstellungen für die Oberfläche (Layout merken) ---------------------------------

def test_settings_need_token(env):
    client = env[0]
    assert client.get("/settings").status_code == 401
    assert client.put("/settings/ui.theme", json={"value": "dark"}).status_code == 401


def test_settings_put_get_roundtrip(env):
    client, _, cfg = env
    assert client.get("/settings", headers=AUTH).json() == {}
    assert client.put("/settings/ui.theme", json={"value": "light"}, headers=AUTH).status_code == 200
    assert client.put("/settings/ui.dock_state", json={"value": "QUJD"}, headers=AUTH).status_code == 200
    assert client.get("/settings", headers=AUTH).json() == {"ui.theme": "light", "ui.dock_state": "QUJD"}
    assert cfg.get("ui.theme") == "light"
    # erscheint auch im Export (F-03)
    assert client.get("/config/export", headers=AUTH).json()["settings"]["ui.theme"] == "light"


@pytest.mark.parametrize(
    ("key", "body"),
    [
        ("secret.twitch", {"value": "x"}),   # Zugangsdaten gehören nicht in die Konfiguration
        ("token.x", {"value": "x"}),
        ("UI.Theme", {"value": "x"}),         # Schlüsselform
        ("a..b", {"value": "x"}),
        ("ui.theme", {"value": 5}),           # Wert muss Text sein
        ("ui.theme", {}),
        ("ui.theme", [1]),
        ("ui.theme", {"value": "x" * 200_001}),
    ],
)
def test_settings_put_rejects_bad_input(env, key, body):
    r = env[0].put(f"/settings/{key}", json=body, headers=AUTH)
    assert r.status_code == 400, r.text
