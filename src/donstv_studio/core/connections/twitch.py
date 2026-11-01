"""Twitch-Verbindung (F-08, F-40, F-41, F-42): genau eine Instanz im Kern.

Chat empfangen: EventSub über WebSocket, Abo `channel.chat.message` (Version 1) mit dem Benutzer-Token des
Bot-Kontos. Twitch empfiehlt EventSub und die Chat-API statt IRC für neue Chat-Bots.
Chat senden: Helix «Send Chat Message» (`POST /helix/chat/messages`).

Quellen (in dieser Sitzung nicht abrufbar, siehe Bericht P07, «nicht geprüft»):
- Chat-Überblick und Empfehlung: https://dev.twitch.tv/docs/chat/
- EventSub über WebSocket (Welcome, Keepalive, Reconnect, Revocation, 10 s bis zum ersten Abo):
  https://dev.twitch.tv/docs/eventsub/handling-websocket-events/
- Abo-Art und Bedingung: https://dev.twitch.tv/docs/eventsub/eventsub-subscription-types/#channelchatmessage
- Ereignisdaten: https://dev.twitch.tv/docs/eventsub/eventsub-reference/#channel-chat-message-event
- Abo anlegen: https://dev.twitch.tv/docs/api/reference/#create-eventsub-subscription
- Senden: https://dev.twitch.tv/docs/api/reference/#send-chat-message
- Benutzer-Kennungen: https://dev.twitch.tv/docs/api/reference/#get-users
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import re
import time
from collections import deque
from collections.abc import Callable
from datetime import datetime
from typing import Any

from donstv_studio.core.bus import Event, EventBus
from donstv_studio.core.connections.base import Connection, Status
from donstv_studio.core.connections.twitch_auth import (
    SCOPES,
    DeviceLogin,
    HttpClient,
    Tokens,
    TokenStore,
    TwitchAuth,
    TwitchAuthError,
)

log = logging.getLogger(__name__)

EVENTSUB_URL = "wss://eventsub.wss.twitch.tv/ws"
HELIX = "https://api.twitch.tv/helix"
CHAT_EVENT = "twitch.chat.message"
AUTH_EVENT = "twitch.auth"
MAX_MESSAGE = 500  # Zeichen; Grenze von «Send Chat Message»
NOT_CONFIGURED = "nicht eingerichtet"  # Anfang des Hinweises: Anzeige grau (ui/widgets.py)
VALIDATE_EVERY = 3600.0  # Sekunden: Twitch verlangt die Prüfung mindestens stündlich
REFRESH_MARGIN = 300  # Sekunden vor Ablauf erneuern
DEFAULT_KEEPALIVE = 10.0
KEEPALIVE_GRACE = 5.0
INITIAL_DELAY, MAX_DELAY = 1.0, 60.0
SENT_IDS = 500  # so viele eigene Nachrichten-Kennungen merken (Schleifenschutz)

KEY_CLIENT_ID = "twitch.client_id"
KEY_CHANNEL = "twitch.channel"
DEFAULT_CHANNEL = "donstv2020"  # Angabe des Nutzers (P07)

WsConnect = Callable[[str], Any]  # gibt einen asynchronen Kontextmanager mit recv()/close() zurück


class SendError(Exception):
    """Nachricht wurde nicht gesendet; Meldung für Nutzer."""


def _default_ws_connect(url: str):
    from websockets.asyncio.client import connect

    return connect(url, open_timeout=10, ping_interval=None)  # Keepalive kommt von Twitch selbst


_RFC3339 = re.compile(r"^(?P<head>[^.]+?)(?:\.(?P<frac>\d+))?(?P<tz>Z|[+-]\d\d:\d\d)$")


def _parse_ts(text: str | None) -> float:
    """RFC 3339 mit bis zu neun Nachkommastellen (Twitch) in Sekunden seit 1970; sonst die aktuelle Zeit."""
    m = _RFC3339.match(text or "")
    if not m:
        return time.time()
    tz = "+00:00" if m["tz"] == "Z" else m["tz"]
    try:
        return datetime.fromisoformat(
            f"{m['head']}.{(m['frac'] or '0')[:6].ljust(6, '0')}{tz}"
        ).timestamp()
    except ValueError:
        return time.time()


def roles_from_badges(badges: list[str]) -> dict[str, bool]:
    """Rollen aus den Abzeichen (set_id). «founder» zählt als Abonnent. [ANNAHME]"""
    s = set(badges)
    return {
        "broadcaster": "broadcaster" in s,
        "moderator": "moderator" in s,
        "subscriber": bool(s & {"subscriber", "founder"}),
        "vip": "vip" in s,
    }


def normalize_chat(
    event: dict[str, Any], ts: str | None, bot_user_id: str | None
) -> dict[str, Any]:
    """Übersetzt ein EventSub-Ereignis `channel.chat.message` in die Nutzlast von `twitch.chat.message`."""
    badges = [str(b.get("set_id", "")) for b in event.get("badges") or [] if isinstance(b, dict)]
    message = event.get("message") or {}
    user_id = str(event.get("chatter_user_id", ""))
    return {
        "message_id": str(event.get("message_id", "")),
        "user_id": user_id,
        "user_login": str(event.get("chatter_user_login", "")),
        "display_name": str(event.get("chatter_user_name") or event.get("chatter_user_login", "")),
        "text": str(message.get("text", "")),
        "badges": badges,
        "roles": roles_from_badges(badges),
        "ts": _parse_ts(ts),
        "channel": str(event.get("broadcaster_user_login", "")),
        "color": str(event.get("color") or ""),
        "from_bot": bool(bot_user_id) and user_id == bot_user_id,
    }


def chat_event(payload: dict[str, Any]) -> Event:
    """Kennung des Bus-Ereignisses aus der Nachrichten-Kennung: doppelte Nachrichten verwirft der Bus."""
    return Event(source="twitch", type=CHAT_EVENT, payload=payload, id=f"twitch.chat:{payload['message_id']}",
                 ts=payload["ts"])  # fmt: skip


class _Reconnect(Exception):
    def __init__(self, url: str) -> None:
        self.url = url


class TwitchConnection(Connection):
    """Chat lesen und senden mit dem Bot-Konto im Kanal (Einstellung `twitch.channel`)."""

    def __init__(
        self,
        bus: EventBus,
        get_setting: Callable[[str], str | None],
        tokens: TokenStore,
        http: HttpClient,
        ws_connect: WsConnect | None = None,
        eventsub_url: str = EVENTSUB_URL,
        helix_url: str = HELIX,
        initial_delay: float = INITIAL_DELAY,
        max_delay: float = MAX_DELAY,
    ) -> None:
        super().__init__("twitch", bus)
        self._get = get_setting
        self.tokens = tokens
        self._http = http
        self.auth = TwitchAuth(http)
        self._ws_connect = ws_connect or _default_ws_connect
        self._eventsub_url = eventsub_url
        self._helix_url = helix_url
        self._initial, self._max = initial_delay, max_delay
        self._task: asyncio.Task | None = None
        self._wake = asyncio.Event()
        self._stopping = False
        self.bot_login: str | None = None
        self.bot_user_id: str | None = None
        self.channel_id: str | None = None
        self.channel_login: str | None = None
        self.sent_ids: deque[str] = deque(maxlen=SENT_IDS)
        self._validated_at = 0.0
        self._login_task: asyncio.Task | None = None
        self.login: DeviceLogin | None = None
        self.login_state: dict[str, Any] = {"state": "idle"}
        self.detail = NOT_CONFIGURED

    # --- Einstellungen ------------------------------------------------
    @property
    def client_id(self) -> str:
        return (self._get(KEY_CLIENT_ID) or "").strip()

    @property
    def channel(self) -> str:
        return (self._get(KEY_CHANNEL) or DEFAULT_CHANNEL).strip().lower()

    def reconfigure(self) -> None:
        """Nach Änderung von Client-ID, Kanal oder Anmeldung: Verbindung neu aufbauen."""
        self._wake.set()

    def account_text(self) -> str:
        """Für den Tipp der Statusanzeige, z. B. «donstvbot im Kanal donstv2020»."""
        return f"{self.bot_login or '?'} im Kanal {self.channel_login or self.channel}"

    # --- Lebenslauf ---------------------------------------------------
    async def start(self) -> None:
        if self._task is None:
            self._stopping = False
            self._task = asyncio.create_task(self._run(), name="twitch")

    async def stop(self) -> None:
        self._stopping = True
        self._wake.set()
        for task in (self._task, self._login_task):
            if task is not None:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await task
        self._task = self._login_task = None
        await self.set_status(Status.DISCONNECTED)

    async def _wait_wake(self, timeout: float | None) -> None:
        try:
            await asyncio.wait_for(self._wake.wait(), timeout)
        except TimeoutError:
            pass
        self._wake.clear()

    async def _run(self) -> None:
        delay = self._initial
        while not self._stopping:
            self._wake.clear()
            if not self.client_id:
                await self.set_status(Status.DISCONNECTED, f"{NOT_CONFIGURED}: Client-ID fehlt")
                await self._wait_wake(None)
                continue
            if self.tokens.load("bot") is None:
                await self.set_status(
                    Status.DISCONNECTED, f"{NOT_CONFIGURED}: Bot-Konto nicht angemeldet"
                )
                await self._wait_wake(None)
                continue
            await self.set_status(Status.CONNECTING, f"Kanal {self.channel}")
            try:
                await self._session()
                delay = self._initial  # war verbunden: schnell neu versuchen
                reason = "Verbindung abgebrochen"
            except asyncio.CancelledError:
                raise
            except TwitchAuthError as e:
                reason = str(e)
            except Exception as e:  # noqa: BLE001 – jeder Fehler führt zu einem neuen Versuch
                log.warning("Twitch: %s", e)
                reason = str(e) or type(e).__name__
            if self._stopping:
                break
            if self._wake.is_set():  # Einstellungen geändert: sofort neu
                delay = self._initial
                continue
            await self.set_status(Status.ERROR, f"{reason}; neuer Versuch in {round(delay)} s")
            await self._wait_wake(delay)
            delay = min(delay * 2, self._max)

    # --- Token --------------------------------------------------------
    async def _ensure_token(self, force_refresh: bool = False) -> Tokens:
        tokens = self.tokens.load("bot")
        if tokens is None:
            raise TwitchAuthError("Bot-Konto nicht angemeldet")
        info = None if force_refresh else await self.auth.validate(tokens.access_token)
        if info is None or int(info.get("expires_in", 0) or 0) < REFRESH_MARGIN:
            tokens = await self.auth.refresh(
                self.client_id, tokens.refresh_token, self.tokens.client_secret()
            )
            self.tokens.save("bot", tokens)
            info = await self.auth.validate(tokens.access_token)
            if info is None:
                raise TwitchAuthError("Twitch lehnt den erneuerten Zugang ab. Bitte neu anmelden.")
            log.info("Twitch: Zugang des Bot-Kontos erneuert")
        missing = [s for s in SCOPES["bot"] if s not in (info.get("scopes") or [])]
        if missing:
            raise TwitchAuthError(
                f"Dem Bot-Konto fehlen Rechte ({', '.join(missing)}). Bitte neu anmelden."
            )
        self.bot_login = str(info.get("login", "")) or None
        self.bot_user_id = str(info.get("user_id", "")) or None
        self._validated_at = time.monotonic()
        return tokens

    async def _helix(
        self, method: str, path: str, *, json_body: Any = None, retry: bool = True
    ) -> tuple[int, Any]:
        tokens = self.tokens.load("bot")
        if tokens is None:
            raise TwitchAuthError("Bot-Konto nicht angemeldet")
        headers = {"Authorization": f"Bearer {tokens.access_token}", "Client-Id": self.client_id}
        status, body = await self._http.request(
            method, self._helix_url + path, headers=headers, json_body=json_body
        )
        if status == 401 and retry:  # abgelaufen: einmal erneuern und wiederholen
            await self._ensure_token(force_refresh=True)
            return await self._helix(method, path, json_body=json_body, retry=False)
        return status, body

    async def _resolve_channel(self) -> None:
        status, body = await self._helix("GET", f"/users?login={self.channel}")
        data = body.get("data") if isinstance(body, dict) else None
        if status != 200 or not data:
            raise TwitchAuthError(
                f"Den Kanal «{self.channel}» gibt es bei Twitch nicht (Fehler {status})"
            )
        self.channel_id = str(data[0]["id"])
        self.channel_login = str(data[0].get("login", self.channel))

    async def _subscribe(self, session_id: str) -> None:
        body = {
            "type": "channel.chat.message",
            "version": "1",
            "condition": {"broadcaster_user_id": self.channel_id, "user_id": self.bot_user_id},
            "transport": {"method": "websocket", "session_id": session_id},
        }
        status, resp = await self._helix("POST", "/eventsub/subscriptions", json_body=body)
        if status not in (200, 202):
            msg = resp.get("message", "") if isinstance(resp, dict) else ""
            raise TwitchAuthError(
                f"Chat-Abo abgelehnt (Fehler {status}{': ' + msg if msg else ''})"
            )

    # --- Sitzung ------------------------------------------------------
    async def _session(self) -> None:
        await self._ensure_token()
        await self._resolve_channel()
        url, first = self._eventsub_url, True
        while True:
            try:
                await self._socket(url, first)
                return
            except _Reconnect as r:  # Twitch verlangt einen Wechsel: Abos bleiben bestehen
                url, first = r.url, False

    async def _recv(self, ws, timeout: float) -> dict[str, Any]:
        """Nächste Nachricht; leeres Wörterbuch, wenn sich die Einstellungen geändert haben (`reconfigure`)."""
        recv = asyncio.ensure_future(ws.recv())
        wake = asyncio.ensure_future(self._wake.wait())
        try:
            done, _ = await asyncio.wait(
                {recv, wake}, timeout=timeout, return_when=asyncio.FIRST_COMPLETED
            )
        finally:
            for t in (recv, wake):
                if not t.done():
                    t.cancel()
            for t in (recv, wake):
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await t
        if recv in done:
            raw = recv.result()
        elif wake in done:
            return {}
        else:
            raise ConnectionError("Keine Keepalive-Nachricht von Twitch")
        try:
            msg = json.loads(raw)
        except ValueError:
            return {}
        return msg if isinstance(msg, dict) else {}

    async def _socket(self, url: str, subscribe: bool) -> None:
        async with self._ws_connect(url) as ws:
            welcome = await self._recv(ws, 10.0)
            meta = welcome.get("metadata") or {}
            if meta.get("message_type") != "session_welcome":
                raise ConnectionError("Twitch hat die Sitzung nicht begrüsst")
            session = (welcome.get("payload") or {}).get("session") or {}
            keepalive = float(session.get("keepalive_timeout_seconds") or DEFAULT_KEEPALIVE)
            if subscribe:
                await self._subscribe(str(session.get("id", "")))
            await self.set_status(Status.CONNECTED, self.account_text())
            while True:
                if time.monotonic() - self._validated_at > VALIDATE_EVERY:
                    await self._ensure_token()
                msg = await self._recv(ws, keepalive + KEEPALIVE_GRACE)
                await self._handle(msg)
                if self._wake.is_set():
                    return  # Einstellungen geändert

    async def _handle(self, msg: dict[str, Any]) -> None:
        meta = msg.get("metadata") or {}
        kind = meta.get("message_type")
        payload = msg.get("payload") or {}
        if kind == "notification":
            sub = payload.get("subscription") or {}
            if sub.get("type") == "channel.chat.message":
                data = normalize_chat(
                    payload.get("event") or {}, meta.get("message_timestamp"), self.bot_user_id
                )
                if data["message_id"]:
                    await self._bus.publish(chat_event(data))
        elif kind == "session_reconnect":
            new_url = (payload.get("session") or {}).get("reconnect_url")
            if new_url:
                raise _Reconnect(str(new_url))
        elif kind == "revocation":
            status = (payload.get("subscription") or {}).get("status", "")
            raise TwitchAuthError(f"Twitch hat das Chat-Abo beendet ({status})")
        # session_keepalive: nichts zu tun, der Empfang selbst setzt die Wartezeit zurück

    # --- Senden (F-42) --------------------------------------------------
    async def send_message(self, text: str) -> dict[str, Any]:
        """Sendet eine Nachricht als Bot-Konto. Wirft SendError, wenn Twitch sie nicht annimmt."""
        text = text.strip()
        if not text:
            raise SendError("Leere Nachricht")
        if len(text) > MAX_MESSAGE:
            raise SendError(f"Nachricht länger als {MAX_MESSAGE} Zeichen")
        if self.status != Status.CONNECTED or not self.channel_id or not self.bot_user_id:
            raise SendError("Twitch ist nicht verbunden")
        body = {"broadcaster_id": self.channel_id, "sender_id": self.bot_user_id, "message": text}
        try:
            status, resp = await self._helix("POST", "/chat/messages", json_body=body)
        except (TwitchAuthError, ConnectionError) as e:
            raise SendError(str(e)) from e
        data = (resp.get("data") or [{}])[0] if isinstance(resp, dict) else {}
        if status != 200 or not data.get("is_sent"):
            reason = (data.get("drop_reason") or {}).get("message") or (
                resp.get("message") if isinstance(resp, dict) else ""
            )
            raise SendError(
                f"Twitch hat die Nachricht nicht angenommen ({reason or f'Fehler {status}'})"
            )
        message_id = str(data.get("message_id", ""))
        if message_id:
            self.sent_ids.append(message_id)
        return {"message_id": message_id}

    # --- Anmeldung (F-40) -----------------------------------------------
    async def _auth_event(self, state: str, **extra: Any) -> None:
        self.login_state = {"role": "bot", "state": state, **extra}
        await self._bus.publish(
            Event(source="twitch", type=AUTH_EVENT, payload=dict(self.login_state))
        )

    async def begin_login(self, role: str = "bot") -> dict[str, Any]:
        """Startet den Device Code Grant Flow. Gibt Code und Adresse zurück; die Abfrage läuft im Hintergrund."""
        if role != "bot":
            raise TwitchAuthError("Im Gerüst meldet sich nur das Bot-Konto an")
        if not self.client_id:
            raise TwitchAuthError("Zuerst die Client-ID eintragen")
        start = await self.auth.start_device(self.client_id, SCOPES[role])
        if self._login_task is not None:
            self._login_task.cancel()
        self.login = DeviceLogin(
            self.auth, self.client_id, role, start, self.tokens.client_secret()
        )
        info = {"user_code": self.login.user_code, "verification_uri": self.login.verification_uri,
                "expires_at": self.login.expires_at}  # fmt: skip
        await self._auth_event("pending", **info)
        self._login_task = asyncio.create_task(self._finish_login(self.login))
        return dict(self.login_state)

    async def _finish_login(self, login: DeviceLogin) -> None:
        try:
            tokens = await login.wait()
            info = await self.auth.validate(tokens.access_token)
            if info is None:
                raise TwitchAuthError("Twitch lehnt den neuen Zugang ab")
            self.tokens.save(login.role, tokens)
            self.bot_login = str(info.get("login", "")) or None
            await self._auth_event("done", login=self.bot_login or "")
            self.reconfigure()
        except asyncio.CancelledError:
            raise
        except (TwitchAuthError, ConnectionError) as e:
            await self._auth_event("failed", message=str(e))

    async def logout(self, role: str = "bot") -> None:
        self.tokens.clear(role)
        self.bot_login = self.bot_user_id = None
        await self._auth_event("idle")
        self.reconfigure()
