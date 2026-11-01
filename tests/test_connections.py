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
