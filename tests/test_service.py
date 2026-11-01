"""Dienst: Start, /health mit und ohne Token, sauberes Beenden."""

import asyncio
import socket

import httpx

from donstv_studio.core.config import Paths
from donstv_studio.core.service import Service


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def test_service_start_health_stop(tmp_path):
    paths, port, oport = Paths.under(tmp_path), free_port(), free_port()
    svc = Service(paths, port=port, overlay_port=oport)
    task = asyncio.create_task(svc.run())
    await asyncio.wait_for(svc.started.wait(), 10)
    async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}") as c:
        assert (await c.get("/health")).status_code == 401
        r = await c.get("/health", headers={"Authorization": f"Bearer {svc.token}"})
        assert r.status_code == 200
    # F-17: Overlay-Server auf eigenem Port, Token pro Overlay
    async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}", headers={"Authorization": f"Bearer {svc.token}"}) as c:
        o = (await c.post("/overlays", json={"name": "A"})).json()
    assert o["url"].endswith(f"/o/{o['id']}?t={o['token']}")
    async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{oport}") as oc:
        assert (await oc.get(f"/o/{o['id']}", params={"t": o["token"]})).status_code == 200
        assert (await oc.get(f"/o/{o['id']}", params={"t": "x"})).status_code == 404
        assert (await oc.get("/health")).status_code == 404  # Kern-Schnittstelle nicht hier
    assert (paths.token_file.stat().st_mode & 0o777) == 0o600
    svc.stop_event.set()
    await asyncio.wait_for(task, 10)
    assert list(paths.backup_dir.glob("donstv-*.db"))  # Sicherung beim Start
