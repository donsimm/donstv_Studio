"""Konfiguration und Pfade (XDG) sowie Export/Import (F-03)."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from donstv_studio.core.store import Store

APP_DIR = "donstv_studio"
EXPORT_VERSION = 1
DEFAULT_API_PORT = 8765
# Overlay-Server (F-17). Vorgaben [ANNAHME]: Port 8080, alle Schnittstellen des Heimnetzes.
DEFAULT_OVERLAY_PORT = 8080
DEFAULT_OVERLAY_HOST = "0.0.0.0"
LOCAL_ONLY_HOST = "127.0.0.1"
_KEY = re.compile(r"^[a-z0-9_]+(\.[a-z0-9_]+)*$")
MAX_VALUE_LENGTH = 200_000
_TRUE = {"1", "true", "ja", "yes", "on"}
# Schlüssel mit diesen Präfixen sind Zugangsdaten und gehören nie in den Export.
SECRET_PREFIXES = ("secret.", "secrets.", "credential.", "token.", "password.")


class ConfigError(ValueError):
    """Ungültige Konfigurationsdatei."""


def _xdg(env: str, fallback: str) -> Path:
    value = os.environ.get(env)
    base = Path(value) if value and os.path.isabs(value) else Path.home() / fallback
    return base / APP_DIR


@dataclass(frozen=True)
class Paths:
    config_dir: Path
    data_dir: Path
    log_dir: Path

    @classmethod
    def from_xdg(cls) -> Paths:
        return cls(
            config_dir=_xdg("XDG_CONFIG_HOME", ".config"),
            data_dir=_xdg("XDG_DATA_HOME", ".local/share"),
            log_dir=_xdg("XDG_STATE_HOME", ".local/state") / "log",
        )

    @classmethod
    def under(cls, base: Path) -> Paths:
        """Alle Ordner unter einem Basisordner (für Tests)."""
        return cls(base / "config", base / "data", base / "log")

    @property
    def db_file(self) -> Path:
        return self.data_dir / "donstv.db"

    @property
    def backup_dir(self) -> Path:
        return self.data_dir / "backups"

    @property
    def token_file(self) -> Path:
        return self.config_dir / "api-token"

    @property
    def media_dir(self) -> Path:
        return self.data_dir / "media"

    @property
    def log_file(self) -> Path:
        return self.log_dir / "donstv-core.log"

    def ensure(self) -> None:
        for d in (self.config_dir, self.data_dir, self.backup_dir, self.media_dir, self.log_dir):
            d.mkdir(parents=True, exist_ok=True)
        self.config_dir.chmod(0o700)


def is_secret_key(key: str) -> bool:
    return key.lower().startswith(SECRET_PREFIXES)


class Config:
    def __init__(self, store: Store) -> None:
        self._store = store

    @property
    def api_port(self) -> int:
        raw = self._store.get_setting("api.port")
        return int(raw) if raw else DEFAULT_API_PORT

    @property
    def overlay_port(self) -> int:
        raw = self._store.get_setting("overlay.port")
        return int(raw) if raw else DEFAULT_OVERLAY_PORT

    @property
    def overlay_local_only(self) -> bool:
        """Konfigurationszeile «nur lokal» (`overlay.local_only`)."""
        return (self._store.get_setting("overlay.local_only") or "false").strip().lower() in _TRUE

    @property
    def overlay_host(self) -> str:
        """Lauschadresse. «nur lokal» gewinnt immer gegen `overlay.host`."""
        if self.overlay_local_only:
            return LOCAL_ONLY_HOST
        return self._store.get_setting("overlay.host") or DEFAULT_OVERLAY_HOST

    @property
    def overlay_public_host(self) -> str | None:
        """Adresse oder Hostname des Laptops für die Browserquelle-URL (leer = automatisch)."""
        return self._store.get_setting("overlay.public_host") or None

    def get(self, key: str, default: str | None = None) -> str | None:
        return self._store.get_setting(key, default)

    def set(self, key: str, value: str) -> None:
        if is_secret_key(key):
            raise ConfigError(
                f"Zugangsdaten gehören in den Schlüsselbund, nicht in die Konfiguration: {key}"
            )
        self._store.set_setting(key, value)

    def set_checked(self, key: str, value: str) -> None:
        """Wie `set`, prüft zusätzlich Form des Schlüssels und Länge des Werts (für die Schnittstelle)."""
        if not _KEY.match(key):
            raise ConfigError(f"Ungültiger Schlüssel: {key!r}")
        if len(value) > MAX_VALUE_LENGTH:
            raise ConfigError(f"Wert zu lang (höchstens {MAX_VALUE_LENGTH} Zeichen)")
        self.set(key, value)

    def export_data(self) -> dict[str, Any]:
        settings = {k: v for k, v in self._store.all_settings().items() if not is_secret_key(k)}
        return {"version": EXPORT_VERSION, "settings": settings}

    def export_json(self) -> str:
        return json.dumps(self.export_data(), ensure_ascii=False, indent=2, sort_keys=True)

    def import_data(self, data: Any) -> None:
        if not isinstance(data, dict) or "version" not in data:
            raise ConfigError("Konfigurationsdatei ohne Versionsfeld")
        if data["version"] != EXPORT_VERSION:
            raise ConfigError(f"Nicht unterstützte Version: {data['version']!r}")
        settings = data.get("settings")
        if not isinstance(settings, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in settings.items()
        ):
            raise ConfigError("«settings» muss Text-Schlüssel mit Text-Werten enthalten")
        bad = [k for k in settings if is_secret_key(k)]
        if bad:
            raise ConfigError(f"Zugangsdaten im Import nicht erlaubt: {', '.join(sorted(bad))}")
        self._store.replace_settings(settings)

    def import_json(self, text: str) -> None:
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise ConfigError(f"Keine gültige JSON-Datei: {e}") from e
        self.import_data(data)
