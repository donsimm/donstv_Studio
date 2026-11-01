"""F-10, F-11, F-12, F-66: Speicherung, Dienst und Ereignisse."""

import pytest

from donstv_studio.core.bus import EventBus
from donstv_studio.core.store import Store
from donstv_studio.overlays.models import NotFoundError, OverlayError
from donstv_studio.overlays.repository import OverlayRepository
from donstv_studio.overlays.service import OverlayService

BOX = {"x": 10, "y": 20, "width": 300, "height": 100}


@pytest.fixture
def env(tmp_path):
    store = Store(tmp_path / "a.db")
    bus, events = EventBus(), []

    async def collect(e):
        events.append(e.payload)

    bus.subscribe("overlay.changed", collect)
    return OverlayService(OverlayRepository(store), bus), events, store, tmp_path


async def test_f10_create_rename_list_delete(env):
    svc, events, *_ = env
    o = await svc.create_overlay("Willkommen")
    await svc.rename_overlay(o.id, "Start")
    assert [x.name for x in svc.list_overlays()] == ["Start"]
    await svc.delete_overlay(o.id)
    assert svc.list_overlays() == []
    assert [e["change"] for e in events] == ["created", "renamed", "deleted"]
    assert all(e["overlay_id"] == o.id for e in events)
    with pytest.raises(NotFoundError):
        await svc.delete_overlay(o.id)


async def test_f11_resolution_and_validation(env):
    svc, events, *_ = env
    o = await svc.create_overlay("A")
    o2 = await svc.set_resolution(o.id, 1280, 720)
    assert (o2.width, o2.height) == (1280, 720)
    assert svc.get_overlay(o.id).width == 1280
    with pytest.raises(OverlayError):
        await svc.set_resolution(o.id, 0, 720)
    assert svc.get_overlay(o.id).width == 1280  # unverändert
    assert events[-1]["change"] == "resolution"


async def test_f66_output_choice_and_ndi_status(env):
    svc, events, *_ = env
    o = await svc.create_overlay("A")
    n = await svc.set_output(o.id, "ndi")
    assert n.to_dict()["output_status"] == "nicht verfügbar"
    assert svc.get_overlay(o.id).output == "ndi"
    assert events[-1]["change"] == "output"
    with pytest.raises(OverlayError):
        await svc.set_output(o.id, "hdmi")


async def test_f12_add_update_delete_source(env):
    svc, events, *_ = env
    o = await svc.create_overlay("A")
    s = await svc.add_source(o.id, "text", **BOX, props={"text": "Hallo"})
    await svc.update_source(o.id, s.id, x=-5, rotation=12.5)
    got = svc.get_overlay(o.id).sources[0]
    assert (got.x, got.rotation, got.props) == (-5, 12.5, {"text": "Hallo"})
    with pytest.raises(OverlayError):
        await svc.update_source(o.id, s.id, width=0)
    with pytest.raises(OverlayError, match="Felder"):
        await svc.update_source(o.id, s.id, kind="image")
    await svc.delete_source(o.id, s.id)
    assert svc.get_overlay(o.id).sources == []
    assert [e["change"] for e in events] == [
        "created", "source_added", "source_updated", "source_removed",
    ]  # fmt: skip
    with pytest.raises(NotFoundError):
        await svc.update_source(o.id, "gibtsnicht", x=1)


async def test_f12_add_source_needs_box_and_whole_pixels(env):
    svc, *_ = env
    o = await svc.create_overlay("A")
    with pytest.raises(OverlayError):
        await svc.add_source(o.id, "text", x=1, y=1)
    with pytest.raises(OverlayError, match="ganze Zahl"):
        await svc.add_source(o.id, "text", x=1.5, y=1, width=5, height=5)
    assert svc.get_overlay(o.id).sources == []


async def test_f12_order_and_visibility(env):
    svc, events, *_ = env
    o = await svc.create_overlay("A")
    a = await svc.add_source(o.id, "text", **BOX)
    b = await svc.add_source(o.id, "image", **BOX)
    c = await svc.add_source(o.id, "text", **BOX)
    assert [s.id for s in svc.get_overlay(o.id).sources] == [a.id, b.id, c.id]
    got = await svc.reorder_sources(o.id, [c.id, a.id, b.id])
    assert [s.id for s in got.sources] == [c.id, a.id, b.id]
    assert [s.z for s in got.sources] == [0, 1, 2]
    assert [s.id for s in svc.get_overlay(o.id).sources] == [c.id, a.id, b.id]
    with pytest.raises(OverlayError):
        await svc.reorder_sources(o.id, [a.id, b.id])
    await svc.set_source_visible(o.id, a.id, False)
    assert svc.get_overlay(o.id).sources[1].visible is False
    assert events[-2]["change"] == "sources_reordered"
    assert events[-1]["change"] == "source_updated"


async def test_f10_duplicate_copies_sources_with_new_ids_and_token(env):
    svc, events, *_ = env
    o = await svc.create_overlay("A", output="ndi")
    s = await svc.add_source(o.id, "text", **BOX, props={"text": "A", "size": 12})
    d = await svc.duplicate_overlay(o.id)
    assert d.id != o.id and d.token != o.token
    assert d.name == "A (Kopie)" and d.output == "ndi"
    assert len(d.sources) == 1 and d.sources[0].id != s.id
    assert d.sources[0].props == {"text": "A", "size": 12}
    d.sources[0].props["size"] = 13  # Kopie darf das Original nicht teilen
    assert svc.get_overlay(o.id).sources[0].props == {"text": "A", "size": 12}
    assert events[-1] == {"overlay_id": d.id, "change": "duplicated", "source_overlay_id": o.id}


async def test_f10_delete_removes_sources(env):
    svc, _, store, _ = env
    o = await svc.create_overlay("A")
    await svc.add_source(o.id, "text", **BOX)
    await svc.delete_overlay(o.id)
    assert store.query("SELECT COUNT(*) FROM sources")[0][0] == 0


async def test_f12_roundtrip_through_database(env):
    svc, _, store, tmp_path = env
    o = await svc.create_overlay("Rundlauf", 1280, 720, "ndi")
    await svc.add_source(o.id, "text", x=-5, y=7, width=200, height=50, rotation=33.25,
                         visible=False, props={"text": "Grüezi", "size": 12})  # fmt: skip
    await svc.add_source(o.id, "image", **BOX)
    before = svc.get_overlay(o.id).to_dict()
    store.close()
    store2 = Store(tmp_path / "a.db")  # neu öffnen
    again = OverlayService(OverlayRepository(store2), EventBus()).get_overlay(o.id).to_dict()
    assert again == before
    assert isinstance(again["sources"][0]["x"], int)


async def test_every_change_publishes_event(env):
    svc, events, *_ = env
    o = await svc.create_overlay("A")
    s = await svc.add_source(o.id, "text", **BOX)
    n0 = len(events)
    await svc.rename_overlay(o.id, "B")
    await svc.set_resolution(o.id, 800, 600)
    await svc.set_output(o.id, "ndi")
    await svc.update_source(o.id, s.id, y=1)
    await svc.reorder_sources(o.id, [s.id])
    await svc.duplicate_overlay(o.id)
    await svc.delete_source(o.id, s.id)
    await svc.delete_overlay(o.id)
    assert len(events) - n0 == 8
    assert all("overlay_id" in e for e in events)


def test_migration_2_tables_exist_and_schema_has_no_percent(tmp_path):
    store = Store(tmp_path / "a.db")
    cols = {r[1] for r in store.query("PRAGMA table_info(sources)")}
    assert {"x", "y", "width", "height", "rotation", "z", "visible", "props"} <= cols
    assert not any("percent" in c for c in cols)
