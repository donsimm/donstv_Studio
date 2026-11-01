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
from donstv_studio.overlays.repository import OverlayRepository
from donstv_studio.overlays.service import OverlayService

log = logging.getLogger(__name__)

BACKUP_CHECK_SECONDS = 3600
LOCAL_HOST = "127.0.0.1"  # in diesem Baustein nie im Heimnetz erreichbar


class Service:
    def __init__(self, paths: Paths, port: int | None = None) -> None:
        self.paths = paths
        self._port_override = port
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

    async def run(self) -> None:
        self.paths.ensure()
        self.store = Store(self.paths.db_file)
        config = Config(self.store)
        self.secrets = open_secret_store(self.paths.config_dir)
        self.token = create_token_file(self.paths.token_file)
        port = self._port_override if self._port_override is not None else config.api_port
        self.overlays = OverlayService(OverlayRepository(self.store), self.bus)
        app = create_app(self.token, self.bus, self.manager, config, self.overlays)
        server = uvicorn.Server(
            uvicorn.Config(
                app, host=LOCAL_HOST, port=port, log_config=None, access_log=False
            )
        )
        server.install_signal_handlers = lambda: None  # Signale behandeln wir selbst
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            with contextlib.suppress(NotImplementedError, RuntimeError):
                loop.add_signal_handler(sig, self.stop_event.set)

        backup_task = asyncio.create_task(self._backup_loop())
        server_task = asyncio.create_task(server.serve())
        try:
            while not server.started and not server_task.done():
                await asyncio.sleep(0.05)
            await self.manager.start_all()
            log.info("donstv-core %s läuft auf %s:%d", __version__, LOCAL_HOST, port)
            self.started.set()
            stop_task = asyncio.create_task(self.stop_event.wait())
            await asyncio.wait({stop_task, server_task}, return_when=asyncio.FIRST_COMPLETED)
            stop_task.cancel()
        finally:
            log.info("donstv-core wird beendet")
            await self.manager.stop_all()
            server.should_exit = True
            await server_task
            backup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await backup_task
            self.store.close()
            for sig in (signal.SIGTERM, signal.SIGINT):
                with contextlib.suppress(NotImplementedError, RuntimeError, ValueError):
                    loop.remove_signal_handler(sig)
