"""F-16, F-17, F-38: Hochladen, Browserquelle-URL, Schriftliste über die Kern-Schnittstelle."""

import pytest
from fastapi.testclient import TestClient

from donstv_studio.core.api import create_app
from donstv_studio.core.bus import EventBus
from donstv_studio.core.config import Config
from donstv_studio.core.connections.manager import ConnectionManager
from donstv_studio.core.store import Store
from donstv_studio.overlays import fonts as fontmod
from donstv_studio.overlays.media import MAX_BYTES, MediaLibrary
from donstv_studio.overlays.repository import OverlayRepository
from donstv_studio.overlays.service import OverlayService
from donstv_studio.overlays.urls import UrlBuilder
from helpers import solid_png

H = {"Authorization": "Bearer t0ken"}
PNG = solid_png(3, 3, (0, 255, 0, 255))


@pytest.fixture
def env(tmp_path):
    store, bus = Store(tmp_path / "a.db"), EventBus()
    media, cfg = MediaLibrary(store, tmp_path / "media"), Config(store)
    svc = OverlayService(OverlayRepository(store), bus, media.exists)
    app = create_app("t0ken", bus, ConnectionManager(), cfg, svc, media, UrlBuilder(cfg))
    with TestClient(app) as client:
        yield client, cfg


def upload(client, data, name="a.png", headers=H):
    return client.post("/media", params={"filename": name}, content=data, headers=headers)


def test_f16_upload_requires_token(env):
    assert upload(env[0], PNG, headers={}).status_code == 401
    assert env[0].get("/media").status_code == 401


def test_f16_upload_ok_and_list(env):
    client, _ = env
    r = upload(client, PNG, "Katze.png")
    assert r.status_code == 201
    assert r.json()["name"] == "Katze.png" and r.json()["mime"] == "image/png"
    assert [m["id"] for m in client.get("/media", headers=H).json()] == [r.json()["id"]]


def test_f16_upload_wrong_type_415_even_with_png_name(env):
    r = upload(env[0], b"das ist kein Bild", "x.png")
    assert r.status_code == 415 and "nicht erlaubt" in r.json()["detail"]


def test_f16_upload_too_large_413(env):
    r = upload(env[0], PNG + b"\0" * MAX_BYTES)
    assert r.status_code == 413 and "25 MB" in r.json()["detail"]
    assert env[0].get("/media", headers=H).json() == []


def test_f16_library_reusable_in_many_sources_and_checked(env):
    client, _ = env
    mid = upload(client, PNG).json()["id"]
    oid = client.post("/overlays", json={"name": "A"}, headers=H).json()["id"]
    box = {"x": 0, "y": 0, "width": 10, "height": 10}
    for _ in range(3):  # mehrfach verwendbar
        r = client.post(
            f"/overlays/{oid}/sources",
            json={"kind": "image", "props": {"media_id": mid}, **box},
            headers=H,
        )
        assert r.status_code == 201
    assert client.delete(f"/media/{mid}", headers=H).status_code == 409
    ghost = client.post(
        f"/overlays/{oid}/sources",
        json={"kind": "image", "props": {"media_id": "a" * 32}, **box},
        headers=H,
    )
    assert ghost.status_code == 400 and "Bibliothek" in ghost.json()["detail"]
    bad = client.post(
        f"/overlays/{oid}/sources", json={"kind": "text", "props": {"size": 0}, **box}, headers=H
    )
    assert bad.status_code == 400 and "Schriftgrösse" in bad.json()["detail"]
    assert client.delete("/media/" + "b" * 32, headers=H).status_code == 404


def test_f11_resolution_limit_via_api(env):
    r = env[0].post("/overlays", json={"name": "A", "width": 9000}, headers=H)
    assert r.status_code == 400 and "höchstens 8192" in r.json()["detail"]


def test_f17_browser_source_url(env):
    client, cfg = env
    cfg.set("overlay.public_host", "192.168.1.50")
    o = client.post("/overlays", json={"name": "A"}, headers=H).json()
    assert o["url"] == f"http://192.168.1.50:8080/o/{o['id']}?t={o['token']}"
    cfg.set("overlay.port", "9090")
    assert (
        client.get(f"/overlays/{o['id']}", headers=H)
        .json()["url"]
        .startswith("http://192.168.1.50:9090/o/")
    )
    assert (
        client.get("/overlays", headers=H).json()[0]["url"].startswith("http://192.168.1.50:9090/")
    )


def test_f17_url_host_fallbacks(env, monkeypatch):
    _, cfg = env
    from donstv_studio.overlays import urls

    monkeypatch.setattr(urls, "detect_lan_ip", lambda: "10.0.0.7")
    assert UrlBuilder(cfg).host() == "10.0.0.7"
    monkeypatch.setattr(urls, "detect_lan_ip", lambda: None)
    assert UrlBuilder(cfg).host()  # Hostname
    cfg.set("overlay.local_only", "true")
    assert UrlBuilder(cfg).host() == "127.0.0.1"


def test_f38_font_list_default_plus_system_fonts(env, monkeypatch):
    async def fake():
        return ["DejaVu Sans", "be vietnam pro", "Inter"]

    monkeypatch.setattr(fontmod, "list_system_fonts", fake)
    r = env[0].get("/fonts", headers=H).json()
    assert r["default"] == "Be Vietnam Pro"
    assert r["fonts"] == ["DejaVu Sans", "Inter"]  # Standard wird nicht doppelt geführt
    assert env[0].get("/fonts").status_code == 401


def test_f38_parse_fc_list():
    out = "Inter Display,Inter Display Thin\nInter\nBad;Name{x}\nNoto Sans CJK JP,Noto Sans CJK JP Bold\n"
    assert fontmod.parse_fc_list(out) == [
        "Inter",
        "Inter Display",
        "Inter Display Thin",
        "Noto Sans CJK JP",
        "Noto Sans CJK JP Bold",
    ]


async def test_f38_fc_list_missing_gives_empty(monkeypatch):
    import asyncio

    async def boom(*a, **k):
        raise FileNotFoundError

    monkeypatch.setattr(asyncio, "create_subprocess_exec", boom)
    assert await fontmod.list_system_fonts() == []
