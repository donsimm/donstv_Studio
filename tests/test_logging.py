"""Protokoll: Rotation und Schwärzung."""

import logging

from donstv_studio.core.logging_setup import setup_logging


def test_tokens_redacted_in_log(tmp_path):
    f = tmp_path / "l.log"
    setup_logging(f, console=False)
    logging.getLogger("t").warning("GET /ws/events?token=abc123&x=1 password=hunter2 Bearer xyz")
    for h in logging.getLogger().handlers:
        h.flush()
    text = f.read_text()
    for geheim in ("abc123", "hunter2", "xyz"):
        assert geheim not in text
    assert "***" in text


def test_overlay_token_in_query_t_redacted(tmp_path):
    f = tmp_path / "l.log"
    setup_logging(f, console=False)
    logging.getLogger("t").warning("GET /o/abc?t=GEHEIMES_TOKEN HTTP/1.1 und /ws?x=1&t=ANDERES")
    for h in logging.getLogger().handlers:
        h.flush()
    text = f.read_text()
    assert "GEHEIMES_TOKEN" not in text and "ANDERES" not in text


async def test_uvicorn_websocket_lines_do_not_contain_token(tmp_path, caplog):
    """Ursache der Token-Zeilen aus P04c: `uvicorn.error` meldet «WebSocket /o/<id>?t=<Token>» [accepted].

    Das ist nicht `uvicorn.access` (dort greift `access_log=False`), sondern der Logger `uvicorn.error`,
    auch bei Stufe DEBUG («< GET …?t=…»). Der Dienst schwärzt dort selbst, unabhängig von Handlern.
    """
    import asyncio
    import contextlib
    import socket

    import httpx
    from websockets.asyncio.client import connect

    from donstv_studio.core.config import Paths
    from donstv_studio.core.service import Service

    def free_port() -> int:
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]

    # Handler aus Vortests (setup_logging) schwärzen denselben Datensatz vorher: wegräumen, sonst prüft der Test nichts.
    root = logging.getLogger()
    for h in list(root.handlers):
        if h is not caplog.handler:
            root.removeHandler(h)
    caplog.set_level(logging.DEBUG)
    port, oport = free_port(), free_port()
    svc = Service(Paths.under(tmp_path), port=port, overlay_port=oport)
    task = asyncio.create_task(svc.run())
    await asyncio.wait_for(svc.started.wait(), 10)
    try:
        async with httpx.AsyncClient(
            base_url=f"http://127.0.0.1:{port}", headers={"Authorization": f"Bearer {svc.token}"}
        ) as c:
            o = (await c.post("/overlays", json={"name": "A"})).json()
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{oport}") as oc:
            await oc.get(f"/o/{o['id']}", params={"t": o["token"]})
        async with connect(f"ws://127.0.0.1:{oport}/o/{o['id']}/ws?t={o['token']}") as ws:
            await asyncio.wait_for(ws.recv(), 5)  # Schnappschuss
        with contextlib.suppress(Exception):  # falsches Token: der Server lehnt ab
            async with connect(f"ws://127.0.0.1:{oport}/o/{o['id']}/ws?t=falsch"):
                pass
    finally:
        svc.stop_event.set()
        await asyncio.wait_for(task, 10)
    uv = [r for r in caplog.records if r.name.startswith("uvicorn")]
    assert any("WebSocket" in r.getMessage() for r in uv), "Test prüft nichts: keine WebSocket-Zeile gesehen"
    for r in uv:
        assert o["token"] not in r.getMessage(), r.getMessage()


async def test_uvicorn_access_log_stays_silent_even_if_a_handler_is_attached(tmp_path, caplog):
    """pytest 9 hängt seine Handler an `uvicorn.access` (propagate=False) und schaltet so uvicorns Zugriffslog wieder ein
    (`access_log = access_logger.hasHandlers()`). Der Dienst hält ihn trotzdem still."""
    import asyncio
    import socket

    import httpx

    from donstv_studio.core.config import Paths
    from donstv_studio.core.service import Service

    def free_port() -> int:
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]

    root = logging.getLogger()
    for h in list(root.handlers):
        if h is not caplog.handler:
            root.removeHandler(h)
    caplog.set_level(logging.DEBUG)
    port, oport = free_port(), free_port()
    svc = Service(Paths.under(tmp_path), port=port, overlay_port=oport)
    task = asyncio.create_task(svc.run())
    await asyncio.wait_for(svc.started.wait(), 10)
    access = logging.getLogger("uvicorn.access")
    access.addHandler(caplog.handler)  # wie pytest 9 es für Logger ohne Weitergabe tut
    try:
        async with httpx.AsyncClient(
            base_url=f"http://127.0.0.1:{port}", headers={"Authorization": f"Bearer {svc.token}"}
        ) as c:
            o = (await c.post("/overlays", json={"name": "A"})).json()
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{oport}") as oc:
            assert (await oc.get(f"/o/{o['id']}", params={"t": o["token"]})).status_code == 200
    finally:
        access.removeHandler(caplog.handler)
        svc.stop_event.set()
        await asyncio.wait_for(task, 10)
    assert [r for r in caplog.records if r.name == "uvicorn.access"] == []
