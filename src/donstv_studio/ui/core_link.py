"""Verbindung der Oberfläche zum Kern-Dienst (lokal, mit Token aus P02).

Die Oberfläche startet den Kern-Dienst nicht. Sie verbindet sich mit `/ws/events`, holt
Einstellungen und Verbindungsstatus und versucht es bei Ausfall mit wachsender Wartezeit erneut.
Netzwerkarbeit läuft in einem eigenen Thread; Ergebnisse kommen als Qt-Signale.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import urllib.error
import urllib.request
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal
from websockets.asyncio.client import connect

from donstv_studio.core.config import DEFAULT_API_PORT, Paths

log = logging.getLogger(__name__)

HTTP_TIMEOUT = 3.0
FORWARDED_EVENTS = ("twitch.chat.message", "bot.log", "twitch.auth")  # an die Oberfläche (Chat-Bot)


class CoreUnavailableError(Exception):
    """Kern-Dienst nicht erreichbar; Meldung für Nutzer."""


def default_base_url() -> str:
    port = os.environ.get("DONSTV_CORE_PORT") or DEFAULT_API_PORT
    return f"http://127.0.0.1:{port}"


def read_token(token_file: Path) -> str:
    try:
        token = token_file.read_text(encoding="utf-8").strip()
    except OSError as e:
        raise CoreUnavailableError(
            "Die Token-Datei des Kern-Dienstes fehlt. Läuft «donstv-core»?"
        ) from e
    if not token:
        raise CoreUnavailableError("Die Token-Datei des Kern-Dienstes ist leer")
    return token


def http_request(
    base_url: str, token: str, method: str, path: str, body: dict | None = None,
    timeout: float = HTTP_TIMEOUT,
):  # fmt: skip
    """Einfache JSON-Anfrage mit Token. Wirft CoreUnavailableError bei Netzfehlern."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        base_url + path, data=data, method=method,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )  # fmt: skip
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise CoreUnavailableError("Der Kern-Dienst lehnt das Token ab (401)") from e
        detail = (
            _detail(e) if e.code in (400, 404, 409) else None
        )  # Meldung des Kerns für Nutzer (z. B. P07)
        raise CoreUnavailableError(
            detail or f"Der Kern-Dienst antwortet mit Fehler {e.code}"
        ) from e
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        raise CoreUnavailableError("Der Kern-Dienst antwortet nicht") from e
    return json.loads(raw) if raw else None


def _detail(e: urllib.error.HTTPError) -> str | None:
    try:
        detail = json.loads(e.read()).get("detail")
    except (ValueError, OSError, AttributeError):
        return None
    return detail if isinstance(detail, str) and detail else None


def describe(error: BaseException) -> str:
    if isinstance(error, CoreUnavailableError):
        return str(error)
    return "Der Kern-Dienst ist nicht erreichbar"


class CoreLink(QObject):
    connected = pyqtSignal()
    unreachable = pyqtSignal(str, float)  # Meldung, Sekunden bis zum nächsten Versuch
    status_changed = pyqtSignal(str, str, str)  # Dienst, Status, Hinweis
    # Regel 12: nur einfache Typen in Signalen über Threads; Wörterbücher als JSON-Text (P08)
    statuses_loaded = pyqtSignal(str)  # JSON-Text: Dienst -> {"status", "detail"}
    settings_loaded = pyqtSignal(str)  # JSON-Text: Schlüssel -> Wert
    # Chat-Bot (P07): Art und Nutzlast als JSON-Text
    event_received = pyqtSignal(str, str)

    def __init__(
        self,
        base_url: str | None = None,
        token_file: Path | None = None,
        initial_delay: float = 1.0,
        max_delay: float = 10.0,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.base_url = base_url or default_base_url()
        self._token_file = token_file or Paths.from_xdg().token_file
        from donstv_studio.ui.backend import (
            CoreBackend,  # hier, weil backend.py dieses Modul importiert
        )

        self.backend = CoreBackend(
            self.base_url, self._token_file
        )  # Overlay-Schnittstelle für den Editor (P06)
        self._initial = initial_delay
        self._max = max_delay
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop: asyncio.Event | None = None

    # --- Lebenslauf ----------------------------------------------------
    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run_thread, name="core-link", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._thread is None:
            return
        if self._loop is not None and self._stop is not None:
            self._loop.call_soon_threadsafe(self._stop.set)
        self._thread.join(3)
        self._thread = None

    def _run_thread(self) -> None:
        asyncio.run(self._main())

    # --- Anfragen ------------------------------------------------------
    def _request(
        self, method: str, path: str, body: dict | None = None, timeout: float = HTTP_TIMEOUT
    ):
        return http_request(
            self.base_url, read_token(self._token_file), method, path, body, timeout
        )

    def fetch_settings_blocking(self, timeout: float = 1.5) -> dict | None:
        """Einstellungen vor dem ersten Anzeigen holen; None, wenn der Kern nicht antwortet."""
        try:
            return self._request("GET", "/settings", timeout=timeout)
        except CoreUnavailableError:
            return None

    def save_setting(self, key: str, value: str) -> None:
        """Speichert im Hintergrund; Fehler werden nur protokolliert."""

        def work() -> None:
            try:
                self._request("PUT", f"/settings/{key}", {"value": value})
            except CoreUnavailableError as e:
                log.warning("Einstellung %s nicht gespeichert: %s", key, e)

        threading.Thread(target=work, daemon=True).start()

    def save_settings_blocking(self, values: dict[str, str], timeout: float = 2.0) -> bool:
        """Speichert mehrere Einstellungen und wartet (z. B. beim Beenden)."""
        try:
            for key, value in values.items():
                self._request("PUT", f"/settings/{key}", {"value": value}, timeout=timeout)
        except CoreUnavailableError as e:
            log.warning("Einstellungen nicht gespeichert: %s", e)
            return False
        return True

    # --- Verbindung ----------------------------------------------------
    async def _main(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._stop = asyncio.Event()
        delay = self._initial
        while not self._stop.is_set():
            session = asyncio.create_task(self._session())
            stopper = asyncio.create_task(self._stop.wait())
            await asyncio.wait({session, stopper}, return_when=asyncio.FIRST_COMPLETED)
            if not session.done():  # stop() wurde gerufen: Sitzung sofort beenden
                session.cancel()
                await asyncio.gather(session, return_exceptions=True)
                break
            stopper.cancel()
            try:
                session.result()
                delay = self._initial  # war verbunden; nach dem Abbruch schnell neu versuchen
                reason = "Die Verbindung zum Kern-Dienst ist abgebrochen"
            except Exception as e:  # noqa: BLE001 – jeder Fehler heisst «nicht erreichbar»
                reason = describe(e)
            if self._stop.is_set():
                break
            self.unreachable.emit(reason, delay)
            try:
                await asyncio.wait_for(self._stop.wait(), delay)
            except TimeoutError:
                pass
            delay = min(delay * 2, self._max)

    async def _session(self) -> None:
        token = read_token(self._token_file)  # bei jedem Versuch neu: das Token wechselt je Start
        ws_url = self.base_url.replace("http://", "ws://", 1) + "/ws/events"
        async with connect(
            ws_url, additional_headers={"Authorization": f"Bearer {token}"}, open_timeout=3
        ) as ws:
            # Erst abonnieren, dann Zustand lesen: so geht kein Statuswechsel verloren.
            settings = await asyncio.to_thread(self._request, "GET", "/settings")
            statuses = await asyncio.to_thread(self._request, "GET", "/connections/info")
            self.connected.emit()
            self.settings_loaded.emit(json.dumps(settings or {}, ensure_ascii=False))
            self.statuses_loaded.emit(json.dumps(statuses or {}, ensure_ascii=False))
            async for raw in ws:
                try:
                    event = json.loads(raw)
                except ValueError:
                    continue
                kind = event.get("type")
                if kind in FORWARDED_EVENTS:
                    self.event_received.emit(
                        str(kind), json.dumps(event.get("payload", {}), ensure_ascii=False)
                    )
                if kind == "connection.status":
                    p = event.get("payload", {})
                    if "name" in p and "status" in p:
                        self.status_changed.emit(
                            str(p["name"]), str(p["status"]), str(p.get("detail", ""))
                        )
