"""Zugriff des Editors auf die Overlay-Schnittstelle des Kerns (P03) und ordentliche Auftragsausführung.

`CoreBackend` spricht per HTTP mit dem Kern (lokal, Token aus P02). `TaskRunner` führt die Aufrufe nacheinander
in einem Hintergrundthread aus, damit die Oberfläche beim Ziehen nie auf das Netz wartet. Wiederholte Änderungen
an derselben Quelle werden zusammengefasst («letzter Stand gewinnt»). `DirectRunner` führt alles sofort im
aufrufenden Thread aus; so laufen Tests ohne Threads.
"""

from __future__ import annotations

import collections
import logging
import threading
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal

from donstv_studio.ui.core_link import HTTP_TIMEOUT, CoreUnavailableError, http_request, read_token

log = logging.getLogger(__name__)

UPLOAD_TIMEOUT = 30.0
MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # wie der Kern (overlays/media.py MAX_BYTES)


class BackendError(Exception):
    """Fehler beim Aufruf des Kerns; die Meldung ist für Nutzer gedacht."""


class CoreBackend:
    """Overlay-Aufrufe über HTTP. Jede Methode blockiert; sie läuft im `TaskRunner`."""

    def __init__(self, base_url: str, token_file: Path) -> None:
        self.base_url = base_url
        self._token_file = token_file

    def _call(self, method: str, path: str, body: dict | None = None):
        try:
            return http_request(self.base_url, read_token(self._token_file), method, path, body, HTTP_TIMEOUT)
        except CoreUnavailableError as e:
            raise BackendError(str(e)) from e

    def list_overlays(self) -> list[dict]:
        return self._call("GET", "/overlays") or []

    def create_overlay(self, name: str, **fields: Any) -> dict:
        return self._call("POST", "/overlays", {"name": name, **fields})

    def update_overlay(self, overlay_id: str, **fields: Any) -> dict:
        return self._call("PATCH", f"/overlays/{overlay_id}", fields)

    def duplicate_overlay(self, overlay_id: str) -> dict:
        return self._call("POST", f"/overlays/{overlay_id}/duplicate", {})

    def delete_overlay(self, overlay_id: str) -> None:
        self._call("DELETE", f"/overlays/{overlay_id}")

    def add_source(self, overlay_id: str, kind: str, **fields: Any) -> dict:
        return self._call("POST", f"/overlays/{overlay_id}/sources", {"kind": kind, **fields})

    def update_source(self, overlay_id: str, source_id: str, **fields: Any) -> dict:
        return self._call("PATCH", f"/overlays/{overlay_id}/sources/{source_id}", fields)

    def delete_source(self, overlay_id: str, source_id: str) -> None:
        self._call("DELETE", f"/overlays/{overlay_id}/sources/{source_id}")

    def reorder_sources(self, overlay_id: str, order: list[str]) -> dict:
        return self._call("PUT", f"/overlays/{overlay_id}/sources/order", {"order": order})

    def upload_media(self, path: str) -> dict:
        """Lädt eine Bilddatei in die Bibliothek des Kerns (F-16). Der Kern prüft Art und Grösse."""
        file = Path(path)
        try:
            if file.stat().st_size > MAX_UPLOAD_BYTES:
                raise BackendError("Die Datei ist grösser als 25 MB")
            data = file.read_bytes()
        except OSError as e:
            raise BackendError(f"Die Datei lässt sich nicht lesen: {e.strerror or e}") from e
        url = f"{self.base_url}/media?{urllib.parse.urlencode({'filename': file.name})}"
        req = urllib.request.Request(
            url, data=data, method="POST",
            headers={"Authorization": f"Bearer {read_token(self._token_file)}", "Content-Type": "application/octet-stream"},
        )  # fmt: skip
        try:
            with urllib.request.urlopen(req, timeout=UPLOAD_TIMEOUT) as resp:
                import json

                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            raise BackendError(_upload_message(e)) from e
        except (urllib.error.URLError, OSError, TimeoutError, CoreUnavailableError) as e:
            raise BackendError("Der Kern-Dienst antwortet nicht") from e


def _upload_message(e: urllib.error.HTTPError) -> str:
    try:
        import json

        detail = json.loads(e.read()).get("detail")
        if isinstance(detail, str):
            return detail
    except (ValueError, OSError, AttributeError):
        pass
    return f"Der Kern-Dienst lehnt die Datei ab (Fehler {e.code})"


class _Task:
    def __init__(self, fn: Callable, fields: dict | None, key: object, on_done, on_error) -> None:
        self.fn, self.fields, self.key = fn, fields, key
        self.callbacks: list[tuple[Callable | None, Callable | None]] = [(on_done, on_error)]


class DirectRunner(QObject):
    """Führt Aufträge sofort aus (Tests). Gleiche Schnittstelle wie `TaskRunner`."""

    def submit(self, fn, on_done=None, on_error=None, *, key=None, fields=None) -> None:
        try:
            result = fn(**fields) if fields is not None else fn()
        except Exception as e:  # noqa: BLE001 – jeder Fehler wird gemeldet
            if on_error:
                on_error(e)
            else:
                log.warning("Auftrag fehlgeschlagen: %s", e)
            return
        if on_done:
            on_done(result)

    def wait_idle(self, timeout: float = 5.0) -> bool:
        return True


class TaskRunner(QObject):
    """Ein Hintergrundthread, der Aufträge der Reihe nach ausführt; Rückmeldungen laufen im Qt-Thread."""

    # Ergebnisse gehen über eine Warteschlange; das Signal selbst trägt keine Daten. Python-Objekte als Signalargumente
    # über Threads hinweg stürzten auf dem Laptop ab (Debian 13: Qt 6.8.2 mit PyQt6 6.9.0).
    _wake = pyqtSignal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._pending: list[_Task] = []
        self._busy = False
        self._cond = threading.Condition()
        self._stopping = False
        self._results: collections.deque = collections.deque()
        self._wake.connect(self._drain)
        self._thread = threading.Thread(target=self._work, name="editor-backend", daemon=True)
        self._thread.start()

    def submit(self, fn, on_done=None, on_error=None, *, key=None, fields=None) -> None:
        """Reiht einen Auftrag ein. Mit `key` und `fields` werden noch wartende Aufträge desselben Schlüssels
        zusammengefasst: die Felder werden vereinigt, der spätere Wert gewinnt."""
        with self._cond:
            if key is not None:
                for t in self._pending:
                    if t.key == key and t.fields is not None and fields is not None:
                        t.fields.update(fields)
                        t.callbacks.append((on_done, on_error))
                        return
            self._pending.append(_Task(fn, dict(fields) if fields is not None else None, key, on_done, on_error))
            self._cond.notify()

    def wait_idle(self, timeout: float = 5.0) -> bool:
        """Wartet, bis alle Aufträge ausgeführt sind (z. B. beim Beenden). True, wenn fertig."""
        with self._cond:
            return self._cond.wait_for(lambda: not self._pending and not self._busy, timeout)

    def stop(self) -> None:
        with self._cond:
            self._stopping = True
            self._cond.notify_all()

    def _work(self) -> None:
        while True:
            with self._cond:
                self._cond.wait_for(lambda: self._pending or self._stopping)
                if self._stopping and not self._pending:
                    return
                task = self._pending.pop(0)
                self._busy = True
            try:
                result = task.fn(**task.fields) if task.fields is not None else task.fn()
                error = None
            except Exception as e:  # noqa: BLE001
                result, error = None, e
            for on_done, on_error in task.callbacks:
                cb = on_error if error is not None else on_done
                self._results.append((cb, error if error is not None else result, error))
            self._wake.emit()
            with self._cond:
                self._busy = False
                self._cond.notify_all()

    def _drain(self) -> None:
        while self._results:
            callback, value, error = self._results.popleft()
            if callback is not None:
                callback(value)
            elif error is not None:
                log.warning("Auftrag fehlgeschlagen: %s", error)
