"""Adresse der Browserquelle (F-17): http://<Laptop>:<Port>/o/<Kennung>?t=<Token>."""

from __future__ import annotations

import socket
from urllib.parse import quote

from donstv_studio.core.config import Config
from donstv_studio.overlays.models import Overlay


def detect_lan_ip() -> str | None:
    """Ermittelt die Heimnetz-Adresse. Es werden keine Pakete gesendet (UDP-connect)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 9))  # TEST-NET-1, RFC 5737
            ip = s.getsockname()[0]
        return None if ip.startswith("127.") or ip == "0.0.0.0" else ip
    except OSError:
        return None


class UrlBuilder:
    def __init__(self, config: Config) -> None:
        self._config = config

    def host(self) -> str:
        c = self._config
        if c.overlay_public_host:
            return c.overlay_public_host
        if c.overlay_local_only:
            return "127.0.0.1"
        return detect_lan_ip() or socket.gethostname() or "127.0.0.1"

    def overlay_url(self, overlay: Overlay) -> str:
        host = self.host()
        if ":" in host and not host.startswith("["):  # IPv6
            host = f"[{host}]"
        return f"http://{host}:{self._config.overlay_port}/o/{overlay.id}?t={quote(overlay.token)}"
