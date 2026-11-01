"""Twitch-Anmeldung (F-40): Device Code Grant Flow, Token-Erneuerung und Token-Prüfung.

Gewählter Ablauf: «Device Code Grant Flow» (DCF) mit einer Anwendung vom Typ «Public». Er braucht weder einen
lokalen Webserver noch ein Client-Secret; der Nutzer gibt auf https://www.twitch.tv/activate einen Code ein.
Twitch nennt ihn für Geräte und Anwendungen ohne eigenen Browser bzw. mit eingeschränkter Eingabe.

Quellen (in dieser Sitzung nicht abrufbar, da dev.twitch.tv vom Netz der Sitzung gesperrt war; Stand des
Wissens, im Bericht als «nicht geprüft» gekennzeichnet):
- Ablauf, Endpunkte und Felder: https://dev.twitch.tv/docs/authentication/getting-tokens-oauth/#device-code-grant-flow
- grant_type ist die volle URN «urn:ietf:params:oauth:grant-type:device_code» (die Doku nannte zeitweise nur
  «device_code»): https://discuss.dev.twitch.com/t/device-code-flow-documentation-fixes/59136
- Erneuern: https://dev.twitch.tv/docs/authentication/refresh-tokens/
- Prüfen (mindestens stündlich verlangt): https://dev.twitch.tv/docs/authentication/validate-tokens/
- Scopes: https://dev.twitch.tv/docs/authentication/scopes/

Tokens liegen nur im Speicher für Zugangsdaten (`core/secrets.py`), getrennt nach Rolle im Schlüsselnamen
(`twitch.bot.access_token`, `twitch.broadcaster.access_token`, …). Sie erscheinen nie im Protokoll.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol

from donstv_studio.core.secrets import SecretStore

log = logging.getLogger(__name__)

DEVICE_URL = "https://id.twitch.tv/oauth2/device"
TOKEN_URL = "https://id.twitch.tv/oauth2/token"
VALIDATE_URL = "https://id.twitch.tv/oauth2/validate"
DEVICE_GRANT = "urn:ietf:params:oauth:grant-type:device_code"
HTTP_TIMEOUT = 15.0

ROLES = ("bot", "broadcaster")
# Bot-Konto: Chat lesen (EventSub channel.chat.message) und senden (Send Chat Message).
# https://dev.twitch.tv/docs/eventsub/eventsub-subscription-types/#channelchatmessage
# https://dev.twitch.tv/docs/api/reference/#send-chat-message
SCOPES = {"bot": ("user:read:chat", "user:write:chat"), "broadcaster": ()}
CLIENT_SECRET_KEY = "twitch.client_secret"  # nur nötig bei einer Anwendung vom Typ «Confidential»


class TwitchAuthError(Exception):
    """Anmeldung oder Erneuerung fehlgeschlagen; Meldung für Nutzer."""


class AuthorizationPending(TwitchAuthError):
    """Der Nutzer hat den Code noch nicht bestätigt."""


class SlowDown(TwitchAuthError):
    """Zu häufig abgefragt; Abstand vergrössern."""


class HttpClient(Protocol):
    async def request(
        self, method: str, url: str, *, headers: dict[str, str] | None = None,
        form: dict[str, str] | None = None, json_body: Any = None,
    ) -> tuple[int, Any]: ...  # fmt: skip


class UrllibHttp:
    """HTTP über die Standardbibliothek in einem Hintergrundthread (keine zusätzliche Abhängigkeit)."""

    def __init__(self, timeout: float = HTTP_TIMEOUT) -> None:
        self._timeout = timeout

    def _do(
        self, method: str, url: str, headers: dict[str, str], data: bytes | None
    ) -> tuple[int, Any]:
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                status, raw = resp.status, resp.read()
        except urllib.error.HTTPError as e:
            status, raw = e.code, e.read()
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            raise ConnectionError("Twitch ist nicht erreichbar") from e
        try:
            body = json.loads(raw) if raw else {}
        except ValueError:
            body = {}
        return status, body

    async def request(self, method, url, *, headers=None, form=None, json_body=None):
        hdrs = dict(headers or {})
        data = None
        if form is not None:
            data = urllib.parse.urlencode(form).encode()
            hdrs["Content-Type"] = "application/x-www-form-urlencoded"
        elif json_body is not None:
            data = json.dumps(json_body).encode()
            hdrs["Content-Type"] = "application/json"
        return await asyncio.to_thread(self._do, method, url, hdrs, data)


def _message(body: Any, fallback: str) -> str:
    if isinstance(body, dict):
        msg = body.get("message") or body.get("error")
        if isinstance(msg, str) and msg:
            return msg
    return fallback


@dataclass
class Tokens:
    access_token: str
    refresh_token: str


class TokenStore:
    """Tokens je Rolle über `secrets.py`; Rolle steht im Schlüsselnamen."""

    def __init__(self, secrets: SecretStore) -> None:
        self._secrets = secrets

    @staticmethod
    def key(role: str, kind: str) -> str:
        if role not in ROLES:
            raise ValueError(f"Unbekannte Rolle: {role}")
        return f"twitch.{role}.{kind}"

    def load(self, role: str) -> Tokens | None:
        access = self._secrets.get(self.key(role, "access_token"))
        refresh = self._secrets.get(self.key(role, "refresh_token"))
        return Tokens(access, refresh or "") if access else None

    def save(self, role: str, tokens: Tokens) -> None:
        self._secrets.set(self.key(role, "access_token"), tokens.access_token)
        self._secrets.set(self.key(role, "refresh_token"), tokens.refresh_token)

    def clear(self, role: str) -> None:
        self._secrets.delete(self.key(role, "access_token"))
        self._secrets.delete(self.key(role, "refresh_token"))

    def client_secret(self) -> str | None:
        return self._secrets.get(CLIENT_SECRET_KEY) or None


class TwitchAuth:
    """Aufrufe an id.twitch.tv."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    async def start_device(self, client_id: str, scopes: tuple[str, ...]) -> dict[str, Any]:
        """Schritt 1: Gerätecode anfordern. Antwort: device_code, user_code, verification_uri, interval, expires_in."""
        status, body = await self._http.request(
            "POST", DEVICE_URL, form={"client_id": client_id, "scopes": " ".join(scopes)}
        )
        if status != 200 or not isinstance(body, dict) or "device_code" not in body:
            raise TwitchAuthError(
                f"Twitch lehnt die Anmeldung ab: {_message(body, f'Fehler {status}')}"
            )
        return body

    async def poll_device(self, client_id: str, scopes: tuple[str, ...], device_code: str,
                          client_secret: str | None = None) -> Tokens:  # fmt: skip
        """Schritt 2: Tokens abholen. Wirft AuthorizationPending, solange der Nutzer nicht bestätigt hat."""
        form = {"client_id": client_id, "scopes": " ".join(scopes), "device_code": device_code,
                "grant_type": DEVICE_GRANT}  # fmt: skip
        if client_secret:
            form["client_secret"] = client_secret
        status, body = await self._http.request("POST", TOKEN_URL, form=form)
        if status == 200 and isinstance(body, dict) and body.get("access_token"):
            return Tokens(body["access_token"], body.get("refresh_token", ""))
        msg = _message(body, f"Fehler {status}")
        if msg == "authorization_pending":
            raise AuthorizationPending(msg)
        if msg == "slow_down":
            raise SlowDown(msg)
        if msg in ("expired_token", "invalid device code"):
            raise TwitchAuthError("Der Code ist abgelaufen. Bitte die Anmeldung neu starten.")
        raise TwitchAuthError(f"Anmeldung fehlgeschlagen: {msg}")

    async def refresh(
        self, client_id: str, refresh_token: str, client_secret: str | None = None
    ) -> Tokens:
        """Neues Zugriffstoken. Bei «Public»-Anwendungen ohne Client-Secret."""
        if not refresh_token:
            raise TwitchAuthError("Kein Aktualisierungs-Token vorhanden. Bitte neu anmelden.")
        form = {
            "client_id": client_id,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
        if client_secret:
            form["client_secret"] = client_secret
        status, body = await self._http.request("POST", TOKEN_URL, form=form)
        if status == 200 and isinstance(body, dict) and body.get("access_token"):
            return Tokens(body["access_token"], body.get("refresh_token") or refresh_token)
        raise TwitchAuthError(
            f"Erneuern fehlgeschlagen ({_message(body, f'Fehler {status}')}). Bitte neu anmelden."
        )

    async def validate(self, access_token: str) -> dict[str, Any] | None:
        """Prüft das Token. Antwort: client_id, login, user_id, scopes, expires_in. None bei 401 (ungültig)."""
        status, body = await self._http.request(
            "GET", VALIDATE_URL, headers={"Authorization": f"OAuth {access_token}"}
        )
        if status == 401:
            return None
        if status != 200 or not isinstance(body, dict):
            raise TwitchAuthError(f"Token-Prüfung fehlgeschlagen (Fehler {status})")
        return body


class DeviceLogin:
    """Eine laufende Anmeldung mit Gerätecode: fragt im vorgegebenen Abstand ab, bis bestätigt oder abgelaufen."""

    def __init__(self, auth: TwitchAuth, client_id: str, role: str, start: dict[str, Any],
                 client_secret: str | None = None, sleep=asyncio.sleep) -> None:  # fmt: skip
        self.role = role
        self.user_code = str(start.get("user_code", ""))
        self.verification_uri = str(start.get("verification_uri", "https://www.twitch.tv/activate"))
        self.expires_at = time.time() + float(start.get("expires_in", 1800))
        self._interval = max(1.0, float(start.get("interval", 5)))
        self._device_code = str(start["device_code"])
        self._auth, self._client_id, self._secret, self._sleep = (
            auth,
            client_id,
            client_secret,
            sleep,
        )
        self._scopes = SCOPES[role]

    async def wait(self) -> Tokens:
        while time.time() < self.expires_at:
            await self._sleep(self._interval)
            try:
                return await self._auth.poll_device(
                    self._client_id, self._scopes, self._device_code, self._secret
                )
            except AuthorizationPending:
                continue
            except SlowDown:
                self._interval += 5  # RFC 8628, Abschnitt 3.5: Abstand um 5 Sekunden vergrössern
        raise TwitchAuthError("Der Code ist abgelaufen. Bitte die Anmeldung neu starten.")
