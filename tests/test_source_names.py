"""F-74: Name einer Quelle – Datenmodell, Migration, Dienst und Schnittstelle (ohne Qt)."""

import pytest
from fastapi.testclient import TestClient

from donstv_studio.core.api import create_app
from donstv_studio.core.bus import EventBus
from donstv_studio.core.config import Config
from donstv_studio.core.connections.manager import ConnectionManager
from donstv_studio.core.store import MIGRATIONS, Store
from donstv_studio.overlays.models import (
    MAX_SOURCE_NAME,
    OverlayError,
    Source,
    default_source_name,
)
from donstv_studio.overlays.repository import OverlayRepository
from donstv_studio.overlays.service import OverlayService

BOX = {"x": 10, "y": 20, "width": 300, "height": 100}
H = {"Authorization": "Bearer t0ken"}


@pytest.fixture
def svc(tmp_path):
    store = Store(tmp_path / "a.db")
    yield OverlayService(OverlayRepository(store), EventBus()), store
    store.close()


def test_f74_default_name_is_the_former_automatic_label():
    assert default_source_name("text", {"text": "Willkommen"}) == "Text: Willkommen"
    assert default_source_name("text", {"text": "  \n Zeile 1\nZeile 2"}) == "Text: Zeile 1"
    assert default_source_name("text", {"text": "x" * 31}) == "Text: " + "x" * 30 + "…"
    assert default_source_name("text", {"text": "x" * 30}) == "Text: " + "x" * 30
    assert default_source_name("text", {}) == "Text"
    assert default_source_name("image", {"media_id": ""}) == "Bild"
    assert default_source_name("image", {}, "logo.png") == "Bild: logo.png"


def test_f74_source_gets_default_name_and_keeps_given_name():
    s = Source(kind="text", props={"text": "Hallo"}, **BOX)
    assert s.name == "Text: Hallo" and s.to_dict()["name"] == "Text: Hallo"
    assert Source(kind="text", name="  Titel  ", **BOX).name == "Titel"  # Leerraum am Rand weg
    assert Source(kind="image", **BOX).name == "Bild"


@pytest.mark.parametrize("bad", [None, 5, "x" * (MAX_SOURCE_NAME + 1)])
def test_f74_invalid_names_are_refused(bad):
    with pytest.raises(OverlayError, match="Name"):
        Source(kind="text", name=bad, **BOX)


async def test_f74_rename_is_stored_and_does_not_change_the_output(svc):
    service, store = svc
    o = await service.create_overlay("A")
    s = await service.add_source(o.id, "text", props={"text": "Hallo"}, **BOX)
    assert s.name == "Text: Hallo"
    renamed = await service.update_source(o.id, s.id, name="Begrüssung")
    assert renamed.name == "Begrüssung"
    again = OverlayRepository(store).get(o.id).sources[0]
    assert again.name == "Begrüssung"
    # Der Name ist nur eine Bezeichnung: Lage, Grösse und Inhalt bleiben
    assert (again.x, again.y, again.width, again.height, again.props) == (
        10, 20, 300, 100, {"text": "Hallo"},
    )  # fmt: skip
    with pytest.raises(OverlayError, match="leer"):
        await service.update_source(o.id, s.id, name="   ")
    assert OverlayRepository(store).get(o.id).sources[0].name == "Begrüssung"


async def test_f74_duplicate_keeps_the_names(svc):
    service, _ = svc
    o = await service.create_overlay("A")
    await service.add_source(o.id, "text", name="Titel", **BOX)
    copy = await service.duplicate_overlay(o.id)
    assert [s.name for s in copy.sources] == ["Titel"]


def test_f74_rename_over_http(tmp_path):
    store = Store(tmp_path / "a.db")
    svc = OverlayService(OverlayRepository(store), EventBus())
    app = create_app("t0ken", EventBus(), ConnectionManager(), Config(store), svc)
    with TestClient(app) as client:
        oid = client.post("/overlays", json={"name": "A"}, headers=H).json()["id"]
        s = client.post(f"/overlays/{oid}/sources", json={"kind": "text", **BOX}, headers=H).json()
        assert s["name"] == "Text"
        r = client.patch(f"/overlays/{oid}/sources/{s['id']}", json={"name": "Logo"}, headers=H)
        assert r.status_code == 200 and r.json()["name"] == "Logo"
        r = client.patch(f"/overlays/{oid}/sources/{s['id']}", json={"name": ""}, headers=H)
        assert r.status_code == 400 and "leer" in r.json()["detail"]
        assert client.get(f"/overlays/{oid}", headers=H).json()["sources"][0]["name"] == "Logo"
    store.close()


def test_f74_migration_gives_existing_sources_their_former_label(tmp_path):
    path = tmp_path / "a.db"
    old = Store(path, migrations=MIGRATIONS[:5])  # Stand vor F-74 (Schema 5)
    long_text = "Ein sehr langer Titel mit mehr als dreissig Zeichen"
    with old.transaction() as db:
        db.execute(
            "INSERT INTO overlays (id,name,width,height,output,token) VALUES ('o','A',10,10,'browser','t')"
        )
        db.execute(
            "INSERT INTO media (id,name,mime,ext,size,created_at) "
            "VALUES ('" + "a" * 32 + "','logo.png','image/png','png',1,0)"
        )
        rows = [
            ("s1", "text", '{"text": "Hallo"}'),
            ("s2", "text", '{"text": "  \\n Zeile 1\\nZeile 2"}'),
            ("s3", "text", '{"text": "' + long_text + '"}'),
            ("s4", "text", "{}"),
            ("s5", "text", '{"text": "   "}'),
            ("s6", "image", '{"media_id": "' + "a" * 32 + '"}'),
            ("s7", "image", '{"media_id": ""}'),
            ("s8", "text", '{"text": "Zeile\\r\\nZwei"}'),
        ]
        for sid, kind, props in rows:
            db.execute(
                "INSERT INTO sources (id, overlay_id, kind, x, y, width, height, rotation, z, "
                "visible, props) VALUES (?,'o',?,0,0,5,5,0,0,1,?)",
                (sid, kind, props),
            )
    assert old.schema_version == 5
    old.close()

    new = Store(path)
    assert new.schema_version == MIGRATIONS[-1][0] >= 6
    names = {s.id: s.name for s in OverlayRepository(new).get("o").sources}
    assert names == {
        "s1": "Text: Hallo",
        "s2": "Text: Zeile 1",
        "s3": "Text: " + long_text[:30] + "…",
        "s4": "Text",
        "s5": "Text",
        "s6": "Bild: logo.png",
        "s7": "Bild",
        "s8": "Text: Zeile",
    }
    # gleich wie die Vorgabe für neue Quellen
    for s in OverlayRepository(new).get("o").sources:
        media = "logo.png" if s.props.get("media_id") else ""
        assert s.name == default_source_name(s.kind, s.props, media), s.id
    new.close()
    Store(path).close()  # erneutes Öffnen ändert nichts
