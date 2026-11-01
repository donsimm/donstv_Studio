"""Zugangsdaten: Schlüsselbund (`keyring`) mit Ersatz in einer Datei (Rechte 600)."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Protocol

log = logging.getLogger(__name__)

SERVICE_NAME = "donstv_studio"


class SecretStore(Protocol):
    def get(self, name: str) -> str | None: ...
    def set(self, name: str, value: str) -> None: ...
    def delete(self, name: str) -> None: ...


class KeyringSecrets:
    """Schlüsselbund des Systems. Doku: https://pypi.org/project/keyring/"""

    def __init__(self, service: str = SERVICE_NAME) -> None:
        self._service = service

    def get(self, name: str) -> str | None:
        import keyring

        return keyring.get_password(self._service, name)

    def set(self, name: str, value: str) -> None:
        import keyring

        keyring.set_password(self._service, name, value)

    def delete(self, name: str) -> None:
        import keyring
        from keyring.errors import PasswordDeleteError

        try:
            keyring.delete_password(self._service, name)
        except PasswordDeleteError:
            pass

    @staticmethod
    def usable() -> bool:
        """Prüft, ob ein echter Schlüsselbund vorhanden ist (kein fail/null-Backend)."""
        try:
            import keyring

            backend = keyring.get_keyring()
            if getattr(backend, "priority", 0) <= 0:
                return False
            keyring.get_password(SERVICE_NAME, "__probe__")
            return True
        except Exception:  # noqa: BLE001 – jeder Fehler heisst «nicht nutzbar»
            return False


class FileSecrets:
    """Ersatz: JSON-Datei mit Rechten 600. Nicht verschlüsselt, daher nur Notlösung."""

    def __init__(self, path: Path) -> None:
        self._path = Path(path)

    def _load(self) -> dict[str, str]:
        if not self._path.exists():
            return {}
        return json.loads(self._path.read_text(encoding="utf-8"))

    def _save(self, data: dict[str, str]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_name(self._path.name + ".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.chmod(tmp, 0o600)
        os.replace(tmp, self._path)

    def get(self, name: str) -> str | None:
        return self._load().get(name)

    def set(self, name: str, value: str) -> None:
        data = self._load()
        data[name] = value
        self._save(data)

    def delete(self, name: str) -> None:
        data = self._load()
        if data.pop(name, None) is not None:
            self._save(data)


def open_secret_store(config_dir: Path) -> SecretStore:
    """Schlüsselbund, sonst Dateiersatz mit deutlicher Warnung."""
    if KeyringSecrets.usable():
        return KeyringSecrets()
    path = Path(config_dir) / "secrets.json"
    log.warning(
        "WARNUNG: Kein nutzbarer Schlüsselbund. Zugangsdaten werden UNVERSCHLÜSSELT in %s "
        "(Rechte 600) abgelegt.",
        path,
    )
    return FileSecrets(path)
