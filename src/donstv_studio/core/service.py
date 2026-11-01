"""Kern-Dienst: startet alles und beendet sich sauber bei SIGTERM/SIGINT."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import signal

import uvicorn

from donstv_studio import __version__
from donstv_studio.core.api import create_app, create_token_file
from donstv_studio.core.bus import EventBus
from donstv_studio.core.config import Config, Paths
from donstv_studio.core.connections.manager import ConnectionManager
from donstv_studio.core.secrets import SecretStore, open_secret_store
from donstv_studio.core.store import Store
from donstv_studio.overlays.media import MediaLibrary
from donstv_studio.overlays.repository import OverlayRepository
from donstv_studio.overlays.server import create_overlay_app
from donstv_studio.overlays.service import OverlayService
from donstv_studio.overlays.urls import UrlBuilder

log = logging.getLogger(__name__)

BACKUP_CHECK_SECONDS = 3600
LOCAL_HOST = "127.0.0.1"  # in diesem Baustein nie im Heimnetz erreichbar


class Service:
    def __init__(
        self, paths: Paths, port: int | None = None, overlay_port: int | None = None
    ) -> None:
        self.paths = paths
        self._port_override = port
        self._overlay_port_override = overlay_port
        self.stop_event = asyncio.Event()
        self.started = asyncio.Event()
        self.bus = EventBus()
        self.manager = ConnectionManager()
        self.store: Store | None = None
        self.secrets: SecretStore | None = None
        self.token = ""

    async def _backup_loop(self) -> None:
        assert self.store is not None
        while True:
            try:
                self.store.backup_if_due(self.paths.backup_dir)
            except Exception:
                log.exception("Sicherung fehlgeschlagen")
            await asyncio.sleep(BACKUP_CHECK_SECONDS)

    @staticmethod
    def _make_server(app, host: str, port: int) -> uvicorn.Server:
        server = uvicorn.Server(
            uvicorn.Config(app, host=host, port=port, log_config=None, access_log=False)
        )
        server.install_signal_handlers = lambda: None  # Signale behandeln wir selbst
        return server

    @staticmethod
    async def _serve(name: str, server: uvicorn.Server) -> None:
        """uvicorn beendet den Prozess bei belegtem Port (SystemExit); hier nur protokollieren."""
        try:
            await server.serve()
        except SystemExit:
            log.error("%s liess sich nicht starten (Port belegt?)", name)

    async def _wait_started(self, server: uvicorn.Server, task: asyncio.Task) -> None:
        while not server.started and not task.done():
            await asyncio.sleep(0.05)

    async def run(self) -> None:
        self.paths.ensure()
        self.store = Store(self.paths.db_file)
        config = Config(self.store)
        self.secrets = open_secret_store(self.paths.config_dir)
        self.token = create_token_file(self.paths.token_file)
        port = self._port_override if self._port_override is not None else config.api_port
        overlay_port = (
            self._overlay_port_override
            if self._overlay_port_override is not None
            else config.overlay_port
        )
        overlay_host = config.overlay_host
        self.media = MediaLibrary(self.store, self.paths.media_dir)
        self.overlays = OverlayService(OverlayRepository(self.store), self.bus, self.media.exists)
        app = create_app(
            self.token, self.bus, self.manager, config, self.overlays, self.media, UrlBuilder(config)
        )
        overlay_app = create_overlay_app(self.overlays, self.media, self.bus)
        server = self._make_server(app, LOCAL_HOST, port)  # Kern-Schnittstelle: nur lokal
        overlay_server = self._make_server(overlay_app, overlay_host, overlay_port)
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            # ValueError: Dienst läuft nicht im Hauptthread (z. B. in Tests)
            with contextlib.suppress(NotImplementedError, RuntimeError, ValueError):
                loop.add_signal_handler(sig, self.stop_event.set)

        backup_task = asyncio.create_task(self._backup_loop())
        server_task = asyncio.create_task(self._serve("Kern-Schnittstelle", server))
        overlay_task = asyncio.create_task(self._serve("Overlay-Server", overlay_server))
        try:
            await self._wait_started(server, server_task)
            await self._wait_started(overlay_server, overlay_task)
            await self.manager.start_all()
            log.info("donstv-core %s: Kern-Schnittstelle %s:%d", __version__, LOCAL_HOST, port)
            log.info("Overlay-Server %s:%d (nur lokal: %s)", overlay_host, overlay_port, config.overlay_local_only)
            self.started.set()
            stop_task = asyncio.create_task(self.stop_event.wait())
            await asyncio.wait({stop_task, server_task}, return_when=asyncio.FIRST_COMPLETED)
            stop_task.cancel()
        finally:
            log.info("donstv-core wird beendet")
            await self.manager.stop_all()
            server.should_exit = True
            overlay_server.should_exit = True
            await asyncio.gather(server_task, overlay_task)
            backup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await backup_task
            self.store.close()
            for sig in (signal.SIGTERM, signal.SIGINT):
                with contextlib.suppress(NotImplementedError, RuntimeError, ValueError):
                    loop.remove_signal_handler(sig)
