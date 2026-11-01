"""F-40, F-41, F-42, F-08: Twitch-Verbindung gegen einen nachgebauten EventSub-Server und nachgebaute HTTP-Antworten.

Kein Netzzugriff: Der WebSocket-Server läuft lokal (127.0.0.1), HTTP-Aufrufe beantwortet `FakeHttp`.
Die Nachrichtenformen folgen https://dev.twitch.tv/docs/eventsub/handling-websocket-events/ (nicht geprüft, siehe P07).
"""

import asyncio
import json

import pytest
from websockets.asyncio.server import serve

from donstv_studio.core.bus import EventBus
from donstv_studio.core.connections.base import Status
from donstv_studio.core.connections.twitch import (
    KEY_CLIENT_ID,
    SendError,
    TwitchConnection,
    _parse_ts,
    normalize_chat,
)
from donstv_studio.core.connections.twitch_auth import (
    DEVICE_GRANT,
    DeviceLogin,
    Tokens,
    TokenStore,
    TwitchAuth,
    TwitchAuthError,
)

BOT_ID, CHANNEL_ID = "1001", "1000"


class MemorySecrets:
    def __init__(self):
        self.data = {}

    def get(self, name):
        return self.data.get(name)

    def set(self, name, value):
        self.data[name] = value

    def delete(self, name):
        self.data.pop(name, None)


class FakeHttp:
    """Antwortet wie id.twitch.tv und api.twitch.tv; merkt sich alle Aufrufe."""

    def __init__(self):
        self.calls = []
        self.valid = {"acc-1"}
        self.refresh_to = "acc-2"
        self.send_status = 200
        self.subscribe_status = 202
        self.poll = ["authorization_pending", "ok"]

    async def request(self, method, url, *, headers=None, form=None, json_body=None):
        self.calls.append((method, url, dict(headers or {}), dict(form or {}), json_body))
        auth = (headers or {}).get("Authorization", "")
        token = auth.split(" ", 1)[1] if " " in auth else ""
        if url.endswith("/oauth2/validate"):
            if token not in self.valid:
                return 401, {"status": 401, "message": "invalid access token"}
            return 200, {"client_id": "cid", "login": "donstvbot", "user_id": BOT_ID,
                         "scopes": ["user:read:chat", "user:write:chat"], "expires_in": 9000}  # fmt: skip
        if url.endswith("/oauth2/token"):
            if form.get("grant_type") == "refresh_token":
                self.valid.add(self.refresh_to)
                return 200, {"access_token": self.refresh_to, "refresh_token": "ref-2"}
            step = self.poll.pop(0)
            if step == "ok":
                self.valid.add("acc-new")
                return 200, {"access_token": "acc-new", "refresh_token": "ref-new"}
            return 400, {"status": 400, "message": step}
        if url.endswith("/oauth2/device"):
            return 200, {"device_code": "dev-123", "user_code": "ABCDEFGH", "interval": 5, "expires_in": 1800,
                         "verification_uri": "https://www.twitch.tv/activate?public=true&device-code=ABCDEFGH"}  # fmt: skip
        if token not in self.valid:
            return 401, {"message": "Invalid OAuth token"}
        if "/users?login=" in url:
            return 200, {"data": [{"id": CHANNEL_ID, "login": "donstv2020"}]}
        if url.endswith("/eventsub/subscriptions"):
            return self.subscribe_status, {
                "data": [{"id": "sub-1", "status": "enabled"}],
                "message": "Forbidden",
            }
        if url.endswith("/chat/messages"):
            if self.send_status != 200:
                return self.send_status, {"message": "kaputt"}
            return 200, {"data": [{"message_id": "sent-1", "is_sent": True}]}
        return 404, {}

    def urls(self):
        return [c[1].split("?")[0].rsplit("/", 2)[-1] for c in self.calls]


def welcome(session_id="sess-1", keepalive=10):
    return json.dumps({"metadata": {"message_id": "w", "message_type": "session_welcome"},
                       "payload": {"session": {"id": session_id, "status": "connected",
                                               "keepalive_timeout_seconds": keepalive}}})  # fmt: skip


def chat_notification(message_id, text="Hallo", user_id="42", login="anna", badges=()):
    return json.dumps({
        "metadata": {"message_id": f"meta-{message_id}", "message_type": "notification",
                     "message_timestamp": "2026-11-01T12:00:00.123456789Z",
                     "subscription_type": "channel.chat.message"},
        "payload": {"subscription": {"type": "channel.chat.message"},
                    "event": {"broadcaster_user_id": CHANNEL_ID, "broadcaster_user_login": "donstv2020",
                              "chatter_user_id": user_id, "chatter_user_login": login, "chatter_user_name": login.title(),
                              "message_id": message_id, "message": {"text": text, "fragments": []},
                              "color": "#FF0000",
                              "badges": [{"set_id": b, "id": "1", "info": ""} for b in badges]}},
    })  # fmt: skip


class Server:
    """Lokaler EventSub-Nachbau. `script` ist eine Liste von Nachrichten, die nach dem Welcome gesendet werden."""

    def __init__(self):
        self.script = []
        self.connections = 0
        self.paths = []
        self.hold = asyncio.Event()

    async def handler(self, ws):
        self.connections += 1
        self.paths.append(ws.request.path)
        await ws.send(welcome(f"sess-{self.connections}"))
        for item in list(self.script):
            if callable(item):
                item = item(self)
            await ws.send(item)
        self.script = []
        await self.hold.wait()

    async def __aenter__(self):
        self._srv = await serve(self.handler, "127.0.0.1", 0)
        self.port = self._srv.sockets[0].getsockname()[1]
        self.url = f"ws://127.0.0.1:{self.port}/ws"
        return self

    async def __aexit__(self, *exc):
        self.hold.set()
        self._srv.close()
        await self._srv.wait_closed()


async def wait_for(cond, timeout=5.0):
    end = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < end:
        if cond():
            return True
        await asyncio.sleep(0.01)
    return False


def make_conn(server_url, http, secrets=None, client_id="cid", logged_in=True, **kw):
    secrets = secrets or MemorySecrets()
    settings = {KEY_CLIENT_ID: client_id} if client_id else {}
    tokens = TokenStore(secrets)
    if logged_in:
        tokens.save("bot", Tokens("acc-1", "ref-1"))
    bus = EventBus()
    conn = TwitchConnection(bus, settings.get, tokens, http, eventsub_url=server_url,
                            initial_delay=0.05, max_delay=0.2, **kw)  # fmt: skip
    return conn, bus, settings, secrets


@pytest.fixture
def collect():
    def attach(bus, pattern="*"):
        got = []

        async def h(e):
            got.append(e)

        bus.subscribe(pattern, h)
        return got

    return attach


async def test_f41_receives_chat_and_drops_duplicate_ids(collect):
    http = FakeHttp()
    async with Server() as srv:
        srv.script = [chat_notification("m-1", "!test", badges=["subscriber"]), chat_notification("m-1", "!test"),
                      json.dumps({"metadata": {"message_type": "session_keepalive"}, "payload": {}}),
                      chat_notification("m-2", "Zweite")]  # fmt: skip
        conn, bus, *_ = make_conn(srv.url, http)
        chat = collect(bus, "twitch.chat.message")
        statuses = collect(bus, "connection.status")
        await conn.start()
        try:
            assert await wait_for(lambda: len(chat) == 2)
            await asyncio.sleep(0.05)
            assert [e.payload["message_id"] for e in chat] == ["m-1", "m-2"]  # Duplikat verworfen
            p = chat[0].payload
            assert (p["user_login"], p["display_name"], p["text"], p["badges"]) == (
                "anna",
                "Anna",
                "!test",
                ["subscriber"],
            )
            assert p["roles"]["subscriber"] and not p["roles"]["moderator"] and not p["from_bot"]
            assert conn.status == Status.CONNECTED
            # F-04 Zusatz 4: Tipp nennt Konto und Kanal
            assert statuses[-1].payload["detail"] == "donstvbot im Kanal donstv2020"
            sub = next(c for c in http.calls if c[1].endswith("/eventsub/subscriptions"))
            assert sub[4]["condition"] == {"broadcaster_user_id": CHANNEL_ID, "user_id": BOT_ID}
            assert sub[4]["transport"] == {"method": "websocket", "session_id": "sess-1"}
            assert sub[2]["Client-Id"] == "cid"
        finally:
            await conn.stop()
    assert conn.status == Status.DISCONNECTED


async def test_f42_send_message_and_refresh_on_401(collect):
    http = FakeHttp()
    async with Server() as srv:
        conn, bus, _, secrets = make_conn(srv.url, http)
        await conn.start()
        try:
            assert await wait_for(lambda: conn.status == Status.CONNECTED)
            assert await conn.send_message("Hallo Chat") == {"message_id": "sent-1"}
            assert "sent-1" in conn.sent_ids
            body = http.calls[-1][4]
            assert body == {
                "broadcaster_id": CHANNEL_ID,
                "sender_id": BOT_ID,
                "message": "Hallo Chat",
            }
            # Zugang läuft ab: 401, Erneuerung, Wiederholung mit neuem Token
            http.valid.discard("acc-1")
            assert await conn.send_message("Noch einmal") == {"message_id": "sent-1"}
            assert secrets.data["twitch.bot.access_token"] == "acc-2"
            assert secrets.data["twitch.bot.refresh_token"] == "ref-2"
            refresh = next(c for c in http.calls if c[3].get("grant_type") == "refresh_token")
            assert refresh[3] == {
                "client_id": "cid",
                "grant_type": "refresh_token",
                "refresh_token": "ref-1",
            }
            http.send_status = 400
            with pytest.raises(SendError):
                await conn.send_message("geht nicht")
            with pytest.raises(SendError):
                await conn.send_message("x" * 501)
        finally:
            await conn.stop()


async def test_send_when_disconnected_fails():
    conn, *_ = make_conn("ws://127.0.0.1:9/ws", FakeHttp())
    with pytest.raises(SendError, match="nicht verbunden"):
        await conn.send_message("hallo")


async def test_f40_without_client_id_or_login_not_configured(collect):
    http = FakeHttp()
    conn, bus, settings, _ = make_conn("ws://127.0.0.1:9/ws", http, client_id="", logged_in=False)
    await conn.start()
    try:
        assert await wait_for(lambda: conn.detail == "nicht eingerichtet: Client-ID fehlt")
        assert conn.status == Status.DISCONNECTED
        settings[KEY_CLIENT_ID] = "cid"
        conn.reconfigure()
        assert await wait_for(
            lambda: conn.detail == "nicht eingerichtet: Bot-Konto nicht angemeldet"
        )
        assert http.calls == []  # ohne Anmeldung kein Aufruf an Twitch
    finally:
        await conn.stop()


async def test_reconnect_with_growing_delay(collect):
    http = FakeHttp()
    http.subscribe_status = 403  # Abo abgelehnt: Fehler, neuer Versuch
    async with Server() as srv:
        conn, bus, *_ = make_conn(srv.url, http)
        statuses = collect(bus, "connection.status")
        await conn.start()
        try:
            assert await wait_for(lambda: srv.connections >= 3)
            errors = [e.payload["detail"] for e in statuses if e.payload["status"] == "Fehler"]
            assert "Fehler 403" in errors[0]
            delays = [d.rsplit("in ", 1)[1] for d in errors[:3]]
            assert delays[0] == "0 s" or delays[0] != delays[2]  # 0.05 → 0.1 → 0.2 (gerundet)
            assert conn.status in (Status.ERROR, Status.CONNECTING)
        finally:
            await conn.stop()


async def test_session_reconnect_moves_to_new_url_without_resubscribing(collect):
    http = FakeHttp()
    async with Server() as srv:

        def reconnect(server):
            return json.dumps({"metadata": {"message_type": "session_reconnect"},
                               "payload": {"session": {"id": "sess-1", "status": "reconnecting",
                                                       "reconnect_url": server.url + "?neu=1"}}})  # fmt: skip

        srv.script = [reconnect]
        conn, bus, *_ = make_conn(srv.url, http)
        await conn.start()
        try:
            assert await wait_for(lambda: srv.connections == 2)
            srv.script = []
            await asyncio.sleep(0.1)
            assert srv.paths[1] == "/ws?neu=1"
            subs = [c for c in http.calls if c[1].endswith("/eventsub/subscriptions")]
            assert len(subs) == 1  # Abos bleiben beim Wechsel bestehen
            assert conn.status == Status.CONNECTED
        finally:
            await conn.stop()


async def test_keepalive_timeout_reconnects():
    http = FakeHttp()
    async with Server() as srv:
        conn, bus, *_ = make_conn(srv.url, http)
        import donstv_studio.core.connections.twitch as tw

        old = tw.KEEPALIVE_GRACE
        tw.KEEPALIVE_GRACE = -9.8  # Keepalive 10 s − 9.8 s = 0.2 s ohne Nachricht → neu verbinden
        try:
            await conn.start()
            assert await wait_for(lambda: srv.connections >= 2)
        finally:
            tw.KEEPALIVE_GRACE = old
            await conn.stop()


async def test_f40_device_login_stores_tokens_by_role(collect):
    http = FakeHttp()
    conn, bus, _, secrets = make_conn("ws://127.0.0.1:9/ws", http, logged_in=False)
    auth_events = collect(bus, "twitch.auth")
    info = None
    try:
        # schnelle Abfrage: Abstand 5 s wird im Test durch ein kurzes Schlafen ersetzt
        import donstv_studio.core.connections.twitch as tw

        orig = tw.DeviceLogin

        class Quick(orig):
            def __init__(self, *a, **k):
                super().__init__(*a, **k, sleep=lambda s: asyncio.sleep(0.01))

        tw.DeviceLogin = Quick
        try:
            info = await conn.begin_login("bot")
            assert await wait_for(
                lambda: auth_events and auth_events[-1].payload["state"] == "done"
            )
        finally:
            tw.DeviceLogin = orig
    finally:
        await conn.stop()
    assert info["user_code"] == "ABCDEFGH" and info["verification_uri"].startswith(
        "https://www.twitch.tv/activate"
    )
    assert secrets.data == {
        "twitch.bot.access_token": "acc-new",
        "twitch.bot.refresh_token": "ref-new",
    }
    device = next(c for c in http.calls if c[1].endswith("/oauth2/device"))
    assert device[3] == {"client_id": "cid", "scopes": "user:read:chat user:write:chat"}
    poll = [c for c in http.calls if c[3].get("grant_type") == DEVICE_GRANT]
    assert len(poll) == 2 and "client_secret" not in poll[0][3]  # «Public»: kein Client-Secret
    with pytest.raises(TwitchAuthError):
        await conn.begin_login("broadcaster")  # im Gerüst nicht nötig


async def test_device_login_slow_down_and_expiry():
    http = FakeHttp()
    http.poll = ["slow_down", "authorization_pending", "ok"]
    sleeps = []

    async def sleep(s):
        sleeps.append(s)

    start = await TwitchAuth(http).start_device("cid", ("user:read:chat",))
    login = DeviceLogin(TwitchAuth(http), "cid", "bot", start, sleep=sleep)
    tokens = await login.wait()
    assert tokens.access_token == "acc-new" and sleeps == [
        5.0,
        10.0,
        10.0,
    ]  # nach «slow_down» 5 s mehr
    http.poll = ["authorization_pending"] * 3
    expired = DeviceLogin(TwitchAuth(http), "cid", "bot", {**start, "expires_in": -1}, sleep=sleep)
    with pytest.raises(TwitchAuthError, match="abgelaufen"):
        await expired.wait()


async def test_logout_removes_tokens():
    http = FakeHttp()
    conn, bus, _, secrets = make_conn("ws://127.0.0.1:9/ws", http)
    await conn.logout("bot")
    assert secrets.data == {}


def test_token_keys_carry_role():
    assert TokenStore.key("bot", "access_token") == "twitch.bot.access_token"
    assert TokenStore.key("broadcaster", "refresh_token") == "twitch.broadcaster.refresh_token"
    with pytest.raises(ValueError):
        TokenStore.key("admin", "access_token")


def test_normalize_and_timestamp():
    p = normalize_chat({"chatter_user_id": BOT_ID, "chatter_user_login": "donstvbot", "message_id": "x",
                        "message": {"text": "hi"}, "badges": [{"set_id": "broadcaster"}]}, None, BOT_ID)  # fmt: skip
    assert p["from_bot"] and p["roles"]["broadcaster"] and p["display_name"] == "donstvbot"
    assert _parse_ts("2026-11-01T12:00:00.123456789Z") == pytest.approx(1793534400.123456)
    assert _parse_ts("2026-11-01T12:00:00Z") == pytest.approx(1793534400.0)
