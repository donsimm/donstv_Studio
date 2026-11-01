"""F-40 bis F-45: Schnittstelle des Bots im Kern und Prüfung «kein Token in Protokoll oder Konfiguration» (Regel 7)."""

import asyncio
import json
import logging

import pytest
from fastapi.testclient import TestClient

from donstv_studio.bot.api import create_router
from donstv_studio.bot.commands import CommandRepository
from donstv_studio.bot.engine import CommandEngine
from donstv_studio.bot.executor import ActionExecutor
from donstv_studio.bot.log import BotLog
from donstv_studio.core.api import create_app
from donstv_studio.core.bus import EventBus
from donstv_studio.core.config import Config, Paths
from donstv_studio.core.connections.fake_twitch import FakeTwitch
from donstv_studio.core.connections.manager import ConnectionManager
from donstv_studio.core.connections.twitch import KEY_CLIENT_ID, TwitchConnection
from donstv_studio.core.connections.twitch_auth import Tokens, TokenStore
from donstv_studio.core.logging_setup import setup_logging
from donstv_studio.core.secrets import FileSecrets
from donstv_studio.core.store import Store

TOKEN = "api-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def env(tmp_path):
    bus, mgr = EventBus(), ConnectionManager()
    store = Store(tmp_path / "a.db")
    cfg = Config(store)
    twitch = FakeTwitch(bus)
    mgr.register(twitch)
    log = BotLog(store, bus)
    repo = CommandRepository(store)
    engine = CommandEngine(bus, repo, ActionExecutor(lambda: twitch, log), log, lambda: twitch)
    app = create_app(TOKEN, bus, mgr, cfg, bot_router=create_router(repo, engine, log, twitch, cfg, fake=True))
    with TestClient(app) as client:
        client.portal.call(twitch.start)
        client.engine = engine
        yield client, twitch, cfg


def test_bot_api_requires_token(env):
    client = env[0]
    assert client.get("/bot/commands").status_code == 401
    assert client.post("/bot/chat/send", json={"text": "x"}).status_code == 401


def test_f43_commands_crud_over_api(env):
    client = env[0]
    r = client.post("/bot/commands", json={"name": "Test", "trigger": "!test", "response": "Hi {user}"}, headers=AUTH)
    assert r.status_code == 200
    cid = r.json()["id"]
    assert client.post("/bot/commands", json={"name": "X", "trigger": "!test"}, headers=AUTH).status_code == 400
    assert client.patch(f"/bot/commands/{cid}", json={"cooldown_user": 30}, headers=AUTH).json()["cooldown_user"] == 30
    dup = client.post(f"/bot/commands/{cid}/duplicate", headers=AUTH).json()
    assert dup["trigger"] == "!test2"
    assert len(client.get("/bot/commands", headers=AUTH).json()) == 2
    assert client.delete(f"/bot/commands/{dup['id']}", headers=AUTH).status_code == 200
    assert client.delete(f"/bot/commands/{dup['id']}", headers=AUTH).status_code == 404
    assert client.patch("/bot/commands/gibtsnicht", json={}, headers=AUTH).status_code == 404


def test_f44_f45_test_chat_triggers_command_and_log(env):
    client, twitch, _ = env
    client.post("/bot/commands", json={"name": "Test", "trigger": "!test", "response": "Hi {user}"}, headers=AUTH)
    client.post("/bot/test/chat", json={"user": "Anna", "text": "!test"}, headers=AUTH)
    client.portal.call(client.engine.drain)
    assert twitch.sent == ["Hi Anna"]
    texts = [m["text"] for m in client.get("/bot/chat/recent", headers=AUTH).json()]
    assert texts == ["!test", "Hi Anna"]
    log = client.get("/bot/log", headers=AUTH).json()
    assert any(e["kind"] == "command" and "Anna" in e["message"] for e in log)


def test_f42_send_over_api_and_error(env):
    client, twitch, _ = env
    assert client.post("/bot/chat/send", json={"text": "Hallo"}, headers=AUTH).status_code == 200
    assert twitch.sent == ["Hallo"]
    r = client.post("/bot/chat/send", json={"text": "  "}, headers=AUTH)
    assert r.status_code == 409 and r.json()["detail"] == "Leere Nachricht"
    assert client.get("/bot/log", headers=AUTH).json()[-1]["kind"] == "send_error"


def test_settings_client_id_is_stored_in_core_settings(env):
    client, _, cfg = env
    r = client.put("/bot/settings", json={"client_id": " abc123 ", "channel": "DonsTV2020"}, headers=AUTH)
    assert r.status_code == 200 and r.json()["client_id"] == "abc123"
    assert cfg.get("twitch.client_id") == "abc123" and cfg.get("twitch.channel") == "donstv2020"
    assert client.put("/bot/settings", json={"client_id": "mit leer"}, headers=AUTH).status_code == 400
    assert client.get("/bot/settings", headers=AUTH).json()["fake"] is True


def test_events_reach_websocket(env):
    client, twitch, _ = env
    with client.websocket_connect("/ws/events", headers=AUTH) as ws:
        client.post("/bot/test/chat", json={"user": "Ben", "text": "Hallo"}, headers=AUTH)
        msg = ws.receive_json()
        while msg["type"] != "twitch.chat.message":
            msg = ws.receive_json()
        assert msg["payload"]["display_name"] == "Ben"


# --- Abnahme: kein Token im Protokoll oder in der Konfiguration ------------------------------------

class TokenHttp:
    """Wie Twitch; Antworten und Fehler enthalten die Tokens absichtlich, damit ein Leck sichtbar würde."""

    def __init__(self):
        self.valid = {"GEHEIM-access-1"}

    async def request(self, method, url, *, headers=None, form=None, json_body=None):
        auth = (headers or {}).get("Authorization", "")
        token = auth.split(" ", 1)[1] if " " in auth else ""
        if url.endswith("/oauth2/validate"):
            if token not in self.valid:
                return 401, {"message": f"invalid access token {token}"}
            return 200, {"login": "donstvbot", "user_id": "1001", "expires_in": 100,  # bald ab: Erneuerung
                         "scopes": ["user:read:chat", "user:write:chat"]}  # fmt: skip
        if url.endswith("/oauth2/token"):
            self.valid.add("GEHEIM-access-2")
            return 200, {"access_token": "GEHEIM-access-2", "refresh_token": "GEHEIM-refresh-2"}
        if "/users" in url:
            return 200, {"data": [{"id": "1000", "login": "donstv2020"}]}
        return 403, {"message": f"Forbidden Bearer {token}"}  # Abo abgelehnt: Fehlerweg wird protokolliert


async def test_no_token_in_log_or_config(tmp_path):
    paths = Paths.under(tmp_path)
    paths.ensure()
    setup_logging(paths.log_file, level=logging.DEBUG, console=False)
    try:
        store = Store(paths.db_file)
        cfg = Config(store)
        cfg.set(KEY_CLIENT_ID, "cid-oeffentlich")
        secrets = FileSecrets(paths.config_dir / "secrets.json")
        tokens = TokenStore(secrets)
        tokens.save("bot", Tokens("GEHEIM-access-1", "GEHEIM-refresh-1"))
        bus = EventBus()
        bot_log = BotLog(store, bus)
        conn = TwitchConnection(bus, cfg.get, tokens, TokenHttp(), ws_connect=_fake_ws,
                                initial_delay=0.01, max_delay=0.02)  # fmt: skip
        engine = CommandEngine(bus, CommandRepository(store), ActionExecutor(lambda: conn, bot_log), bot_log,
                               lambda: conn)  # fmt: skip
        await conn.start()
        for _ in range(200):
            await asyncio.sleep(0.01)
            if len(bot_log.recent()) > 5:
                break
        await conn.stop()
        engine.close()
        await bot_log.add("auth", "Antwort: access_token=GEHEIM-access-9", {"raw": "refresh_token: GEHEIM-x"})
        assert tokens.load("bot").access_token == "GEHEIM-access-2"  # wurde erneuert und gespeichert
        for handler in logging.getLogger().handlers:
            handler.flush()
        log_text = paths.log_file.read_text(encoding="utf-8")
        export = cfg.export_json()
        db_text = json.dumps(store.query("SELECT * FROM settings") + store.query("SELECT * FROM bot_log"))
        assert "Fehler 403" in db_text  # das Protokoll enthält den Fehlerweg
        for text in (log_text, export, db_text):
            assert "GEHEIM" not in text
        store.close()
    finally:
        logging.getLogger().handlers.clear()


class _FakeSocket:
    def __init__(self):
        self.sent = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def recv(self):
        if not self.sent:
            self.sent = True
            return json.dumps({"metadata": {"message_type": "session_welcome"},
                               "payload": {"session": {"id": "s", "keepalive_timeout_seconds": 10}}})  # fmt: skip
        await asyncio.sleep(3600)


def _fake_ws(url):
    return _FakeSocket()
