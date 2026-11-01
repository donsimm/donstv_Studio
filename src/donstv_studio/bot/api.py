"""Schnittstelle des Chat-Bots im Kern (nur lokal, mit Token; eingebunden in core/api.py)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from donstv_studio.bot.commands import CommandError, CommandRepository
from donstv_studio.bot.engine import CommandEngine
from donstv_studio.bot.log import BotLog
from donstv_studio.core.config import Config
from donstv_studio.core.connections.twitch import KEY_CHANNEL, KEY_CLIENT_ID, SendError
from donstv_studio.core.connections.twitch_auth import TwitchAuthError

MAX_CLIENT_ID = 100
MAX_CHANNEL = 25  # Twitch-Benutzernamen haben höchstens 25 Zeichen [nicht geprüft]


async def _json(request: Request) -> dict[str, Any]:
    try:
        body = await request.json()
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Keine gültige JSON-Anfrage") from e
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Erwartet wird ein JSON-Objekt")
    return body


def create_router(
    commands: CommandRepository, engine: CommandEngine, bot_log: BotLog, twitch, config: Config,
    fake: bool = False,
) -> APIRouter:  # fmt: skip
    r = APIRouter(prefix="/bot")

    # --- Commands (F-43) --------------------------------------------------
    @r.get("/commands")
    async def list_commands() -> list[dict]:
        return [c.to_dict() for c in commands.list()]

    @r.post("/commands")
    async def create_command(request: Request) -> dict:
        try:
            return commands.create(await _json(request)).to_dict()
        except CommandError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    @r.patch("/commands/{command_id}")
    async def update_command(command_id: str, request: Request) -> dict:
        try:
            return commands.update(command_id, await _json(request)).to_dict()
        except KeyError as e:
            raise HTTPException(status_code=404, detail="Command gibt es nicht") from e
        except CommandError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    @r.post("/commands/{command_id}/duplicate")
    async def duplicate_command(command_id: str) -> dict:
        try:
            return commands.duplicate(command_id).to_dict()
        except KeyError as e:
            raise HTTPException(status_code=404, detail="Command gibt es nicht") from e

    @r.delete("/commands/{command_id}")
    async def delete_command(command_id: str) -> dict:
        if not commands.delete(command_id):
            raise HTTPException(status_code=404, detail="Command gibt es nicht")
        return {"status": "ok"}

    # --- Protokoll (F-45) und Chat (F-41, F-42) -------------------------------
    @r.get("/log")
    async def recent_log(limit: int = 200) -> list[dict]:
        return bot_log.recent(max(1, min(limit, 1000)))

    @r.get("/chat/recent")
    async def recent_chat() -> list[dict]:
        return list(engine.history)

    @r.post("/chat/send")
    async def send_chat(request: Request) -> dict:
        text = (await _json(request)).get("text")
        if not isinstance(text, str):
            raise HTTPException(status_code=400, detail="«text» muss Text sein")
        try:
            return await twitch.send_message(text)
        except SendError as e:
            from donstv_studio.bot import log as botlog

            await bot_log.add(botlog.SEND_ERROR, f"Senden fehlgeschlagen: {e}", {"source": "Eingabefeld"})
            raise HTTPException(status_code=409, detail=str(e)) from e

    # --- Einstellungen und Anmeldung (F-40) ------------------------------------
    def settings() -> dict:
        return {
            "client_id": config.get(KEY_CLIENT_ID) or "",
            "channel": twitch.channel_login or config.get(KEY_CHANNEL) or "donstv2020",
            "bot_login": twitch.bot_login or "",
            "logged_in": fake or twitch.tokens.load("bot") is not None,
            "login": dict(twitch.login_state),
            "fake": fake,
        }

    @r.get("/settings")
    async def get_settings() -> dict:
        return settings()

    @r.put("/settings")
    async def put_settings(request: Request) -> dict:
        body = await _json(request)
        for key, field, limit in ((KEY_CLIENT_ID, "client_id", MAX_CLIENT_ID), (KEY_CHANNEL, "channel", MAX_CHANNEL)):
            if field not in body:
                continue
            value = body[field]
            if not isinstance(value, str) or len(value.strip()) > limit or any(c.isspace() for c in value.strip()):
                raise HTTPException(status_code=400, detail=f"«{field}» ist ungültig")
            config.set(key, value.strip().lower() if field == "channel" else value.strip())
        twitch.reconfigure()
        return settings()

    @r.post("/auth/bot/start")
    async def auth_start() -> dict:
        try:
            return await twitch.begin_login("bot")
        except (TwitchAuthError, ConnectionError) as e:
            raise HTTPException(status_code=409, detail=str(e)) from e

    @r.delete("/auth/bot")
    async def auth_logout() -> dict:
        await twitch.logout("bot")
        return settings()

    if fake:
        @r.post("/test/chat")
        async def test_chat(request: Request) -> dict:
            """Nur mit der Testverbindung: Chat-Nachricht eines beliebigen Nutzers erzeugen."""
            body = await _json(request)
            user, text = body.get("user", "testnutzer"), body.get("text", "")
            badges = body.get("badges") or []
            if not (isinstance(user, str) and isinstance(text, str) and isinstance(badges, list)):
                raise HTTPException(status_code=400, detail="Ungültige Testnachricht")
            return await twitch.inject(user, text, [str(b) for b in badges])

    return r
