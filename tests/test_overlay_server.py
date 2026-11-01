"""F-17, F-18, F-19: Overlay-Server – Token, Snapshot, Update, Medien, statische Dateien."""

from functools import partial

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from donstv_studio.core.bus import EventBus
from donstv_studio.core.store import Store
from donstv_studio.overlays.media import MediaLibrary
from donstv_studio.overlays.repository import OverlayRepository
from donstv_studio.overlays.server import WEB_DIR, create_overlay_app
from donstv_studio.overlays.service import OverlayService
from helpers import solid_png

PNG = solid_png(4, 4, (255, 0, 0, 255))


async def _chunks(data):
    yield data


@pytest.fixture
def env(tmp_path):
    store, bus = Store(tmp_path / "a.db"), EventBus()
    media = MediaLibrary(store, tmp_path / "media")
    svc = OverlayService(OverlayRepository(store), bus, media.exists)
    with TestClient(create_overlay_app(svc, media, bus)) as client:
        def call(f, *a, **k):
            return client.portal.call(partial(f, *a, **k))

        item = call(media.save, "r.png", _chunks(PNG))
        o = call(svc.create_overlay, "A")
        text = call(svc.add_source, o.id, "text", x=10, y=20, width=300, height=80,
                    props={"text": "Hallo", "size": 40})  # fmt: skip
        img = call(svc.add_source, o.id, "image", x=5, y=6, width=50, height=60,
                   props={"media_id": item.id})  # fmt: skip
        yield client, call, svc, o, text, img, item


def test_f17_token_right_wrong_missing(env):
    client, _, _, o, *_ = env
    ok = client.get(f"/o/{o.id}", params={"t": o.token})
    assert ok.status_code == 200 and "overlay.js" in ok.text
    assert ok.headers["cache-control"] == "no-store"
    assert ok.headers["referrer-policy"] == "no-referrer"
    bad = client.get(f"/o/{o.id}", params={"t": "falsch"})
    missing = client.get(f"/o/{o.id}")
    unknown = client.get("/o/gibtsnicht", params={"t": o.token})
    # alle Fehlerfälle sehen gleich aus: kein Hinweis, ob das Overlay existiert
    for r in (bad, missing, unknown):
        assert r.status_code == 404
        assert (r.text, r.headers["content-type"]) == (bad.text, bad.headers["content-type"])


def test_f17_page_is_html_without_token_leak(env):
    client, _, _, o, *_ = env
    assert o.token not in client.get(f"/o/{o.id}", params={"t": o.token}).text


def test_f17_websocket_token_required(env):
    client, _, _, o, *_ = env
    for url in (f"/o/{o.id}/ws", f"/o/{o.id}/ws?t=falsch", f"/o/gibtsnicht/ws?t={o.token}"):
        with pytest.raises(WebSocketDisconnect), client.websocket_connect(url):
            pass


def test_f18_snapshot_then_update_on_every_change(env):
    client, call, svc, o, text, img, item = env
    with client.websocket_connect(f"/o/{o.id}/ws?t={o.token}") as ws:
        snap = ws.receive_json()
        assert snap["type"] == "snapshot"
        ov = snap["overlay"]
        assert "token" not in ov and (ov["width"], ov["height"]) == (1920, 1080)
        assert [s["id"] for s in ov["sources"]] == [text.id, img.id]
        assert ov["media"] == {item.id: {"mime": "image/png", "name": "r.png"}}

        call(svc.update_source, o.id, text.id, x=111, props={"text": "Neu"})
        msg = ws.receive_json()
        assert msg["type"] == "update" and msg["change"] == "source_updated"
        assert msg["overlay"]["sources"][0]["x"] == 111
        assert msg["overlay"]["sources"][0]["props"]["text"] == "Neu"

        call(svc.set_resolution, o.id, 1280, 720)
        msg = ws.receive_json()
        assert (msg["overlay"]["width"], msg["overlay"]["height"]) == (1280, 720)

        call(svc.delete_overlay, o.id)
        assert ws.receive_json() == {"type": "deleted"}


def test_f18_changes_of_other_overlays_not_sent(env):
    client, call, svc, o, text, *_ = env
    other = call(svc.create_overlay, "B")
    with client.websocket_connect(f"/o/{o.id}/ws?t={o.token}") as ws:
        ws.receive_json()
        call(svc.rename_overlay, other.id, "B2")
        call(svc.update_source, o.id, text.id, y=99)
        assert ws.receive_json()["overlay"]["sources"][0]["y"] == 99


def test_f16_media_needs_token_and_reference(env):
    client, call, svc, o, _text, _img, item = env
    r = client.get(f"/media/{o.id}/{item.id}", params={"t": o.token})
    assert r.status_code == 200 and r.content == PNG and r.headers["content-type"] == "image/png"
    assert "sandbox" in r.headers["content-security-policy"]
    assert r.headers["x-content-type-options"] == "nosniff"
    for params in ({}, {"t": "falsch"}):
        assert client.get(f"/media/{o.id}/{item.id}", params=params).status_code == 404
    # Datei der Bibliothek, die dieses Overlay nicht verwendet, bleibt gesperrt
    other = call(svc.create_overlay, "B")
    assert client.get(f"/media/{other.id}/{item.id}", params={"t": other.token}).status_code == 404
    assert client.get(f"/media/{o.id}/..%2Fx", params={"t": o.token}).status_code == 404


def test_f19_font_served_locally_from_static(env):
    client, *_ = env
    r = client.get("/static/fonts/BeVietnamPro-Regular.ttf")
    assert r.status_code == 200 and len(r.content) > 50_000
    assert "BeVietnamPro-Regular.ttf" in client.get("/static/overlay.css").text
    assert client.get("/static/fonts/OFL.txt").status_code == 200
    assert client.get("/static/../server.py").status_code == 404
    import re

    web = "".join((WEB_DIR / n).read_text(encoding="utf-8") for n in ("overlay.css", "overlay.html", "overlay.js"))
    # Kommentare (Quellenangaben) ausnehmen; geladen wird nur, was in url(), src oder href steht
    code = re.sub(r"/\*.*?\*/", "", web, flags=re.DOTALL)
    assert not re.search(r"(?:url\(|src=|href=|@import)\s*[\"']?(?:https?:)?//", code)  # kein CDN


def test_static_has_no_media_or_database(env):
    client, *_ = env
    assert client.get("/static/donstv.db").status_code == 404
    assert client.get("/").status_code == 404
