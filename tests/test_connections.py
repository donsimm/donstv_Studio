"""F-08: genau eine Verbindung pro Dienst."""

import pytest

from donstv_studio.core.bus import EventBus
from donstv_studio.core.connections.base import Connection, Status
from donstv_studio.core.connections.manager import ConnectionManager, DuplicateConnectionError


def test_f08_duplicate_registration_refused():
    bus, m = EventBus(), ConnectionManager()
    m.register(Connection("twitch", bus))
    with pytest.raises(DuplicateConnectionError):
        m.register(Connection("twitch", bus))
    m.register(Connection("obs", bus))
    assert m.names() == ["obs", "twitch"]
    assert m.statuses() == {"obs": "getrennt", "twitch": "getrennt"}


async def test_f08_status_published_on_bus():
    bus, got = EventBus(), []

    async def h(e):
        got.append(e.payload)

    bus.subscribe("connection.status", h)
    c = Connection("obs", bus)
    await c.set_status(Status.CONNECTING)
    await c.set_status(Status.CONNECTING)  # keine Änderung, kein Ereignis
    await c.set_status(Status.CONNECTED)
    await c.stop()
    assert [p["status"] for p in got] == ["verbindet", "verbunden", "getrennt"]
    assert got[0]["name"] == "obs"


async def test_f08_start_stop_all_survive_errors():
    bus, m = EventBus(), ConnectionManager()

    class Bad(Connection):
        async def start(self):
            raise RuntimeError("x")

    m.register(Bad("a", bus))
    m.register(Connection("b", bus))
    await m.start_all()
    await m.stop_all()


# --- P05b: YouTube als Platzhalter-Verbindung (F-04) ----------------------------------------

async def test_f04_youtube_placeholder_always_disconnected_and_not_configured():
    from donstv_studio.core.connections.youtube import YouTubeConnection

    bus, got = EventBus(), []

    async def h(e):
        got.append(e)

    bus.subscribe("connection.status", h)
    m, yt = ConnectionManager(), YouTubeConnection(bus)
    m.register(yt)
    with pytest.raises(DuplicateConnectionError):  # weiterhin genau eine Verbindung pro Dienst (F-08)
        m.register(YouTubeConnection(bus))
    await m.start_all()
    await m.stop_all()
    assert (yt.name, yt.status, yt.detail) == ("youtube", Status.DISCONNECTED, "nicht eingerichtet")
    assert m.statuses() == {"youtube": "getrennt"}
    assert m.info() == {"youtube": {"status": "getrennt", "detail": "nicht eingerichtet"}}
    assert got == []  # meldet nie etwas anderes, es gibt keine Statusänderung


async def test_f04_status_detail_is_published_and_kept():
    bus, got = EventBus(), []

    async def h(e):
        got.append(e.payload)

    bus.subscribe("connection.status", h)
    c = Connection("obs", bus)
    await c.set_status(Status.ERROR, "Passwort falsch")
    assert got[-1]["detail"] == "Passwort falsch" and c.detail == "Passwort falsch"
    await c.set_status(Status.CONNECTED)
    assert "detail" not in got[-1] and c.detail is None
