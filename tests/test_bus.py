"""F-08: Ereignis-Bus."""

from donstv_studio.core.bus import Event, EventBus


async def test_f08_delivery_by_pattern():
    bus, got = EventBus(), []

    async def h(e):
        got.append(e.type)

    bus.subscribe("twitch.*", h)
    await bus.publish(Event("twitch", "twitch.chat.message"))
    await bus.publish(Event("obs", "obs.scene.changed"))
    assert got == ["twitch.chat.message"]


async def test_f08_duplicate_id_dropped():
    bus, got = EventBus(), []

    async def h(e):
        got.append(e.id)

    bus.subscribe("*", h)
    assert await bus.publish(Event("a", "x.y", id="1")) is True
    assert await bus.publish(Event("a", "x.y", id="1")) is False
    assert got == ["1"]


async def test_f08_crashing_subscriber_does_not_stop_others(caplog):
    bus, got = EventBus(), []

    async def bad(e):
        raise RuntimeError("kaputt")

    async def good(e):
        got.append(e.id)

    bus.subscribe("*", bad)
    bus.subscribe("*", good)
    await bus.publish(Event("a", "x", id="1"))
    await bus.publish(Event("a", "x", id="2"))
    assert got == ["1", "2"]
    assert "abgestürzt" in caplog.text


async def test_f08_unsubscribe():
    bus, got = EventBus(), []

    async def h(e):
        got.append(e.id)

    sub = bus.subscribe("*", h)
    sub.cancel()
    await bus.publish(Event("a", "x"))
    assert got == []
