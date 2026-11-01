"""F-10 bis F-13: `CoreBackend` und `TaskRunner` gegen den echten Kern-Dienst (HTTP)."""

import socket
import time

import pytest

pytest.importorskip("PyQt6.QtCore", exc_type=ImportError, reason="PyQt6 ist nicht installierbar oder lädt nicht")

from PyQt6.QtCore import QCoreApplication

from donstv_studio.core.config import Paths
from donstv_studio.ui.backend import BackendError, CoreBackend, TaskRunner
from donstv_studio.ui.core_link import CoreLink
from helpers import RunningService, solid_png


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def core(tmp_path):
    paths = Paths.under(tmp_path)
    svc = RunningService(paths, free_port(), free_port()).start()
    yield svc, CoreBackend(svc.base_url, paths.token_file), paths
    svc.stop()


def test_f10_backend_covers_overlay_and_source_calls(core, tmp_path):
    svc, b, _ = core
    o = b.create_overlay("A", width=800, height=400)
    assert o["url"].endswith(f"/o/{o['id']}?t={o['token']}") and (o["width"], o["height"]) == (800, 400)
    s1 = b.add_source(o["id"], "text", x=1, y=2, width=30, height=40, props={"text": "x"})
    s2 = b.add_source(o["id"], "text", x=5, y=6, width=30, height=40)
    assert b.update_source(o["id"], s1["id"], x=11, rotation=15.0)["x"] == 11
    assert [s["id"] for s in b.reorder_sources(o["id"], [s2["id"], s1["id"]])["sources"]] == [s2["id"], s1["id"]]
    assert b.update_overlay(o["id"], name="B", output="ndi")["output_status"] == "nicht verfügbar"
    dup = b.duplicate_overlay(o["id"])
    assert dup["name"] == "B (Kopie)" and dup["token"] != o["token"]
    f = tmp_path / "bild.png"
    f.write_bytes(solid_png(10, 10, (1, 2, 3, 255)))
    item = b.upload_media(str(f))
    assert item["name"] == "bild.png" and item["mime"] == "image/png"
    b.delete_source(o["id"], s1["id"])
    b.delete_overlay(dup["id"])
    assert [x["id"] for x in b.list_overlays()] == [o["id"]]


def test_f10_backend_errors_are_user_messages_without_token(core, tmp_path):
    svc, b, paths = core
    with pytest.raises(BackendError) as e:
        b.update_overlay("gibtsnicht", name="x")
    # Seit P07 kommt die Meldung des Kerns («… gibt es nicht») statt nur «Fehler 404» bei der Oberfläche an.
    assert "gibt es nicht" in str(e.value) and svc.svc.token not in str(e.value)
    bad = tmp_path / "x.txt"
    bad.write_text("kein Bild")
    with pytest.raises(BackendError) as e2:
        b.upload_media(str(bad))
    assert "erlaubt" in str(e2.value)  # Meldung des Kerns
    with pytest.raises(BackendError):
        b.upload_media(str(tmp_path / "fehlt.png"))
    nobody = CoreBackend("http://127.0.0.1:9", paths.token_file)
    with pytest.raises(BackendError, match="antwortet nicht"):
        nobody.list_overlays()


def test_core_link_offers_backend_for_the_editor(core):
    svc, _, paths = core
    link = CoreLink(base_url=svc.base_url, token_file=paths.token_file)
    assert link.backend.list_overlays() == []


def test_task_runner_runs_in_order_in_background_and_calls_back_in_qt_thread():
    app = QCoreApplication.instance() or QCoreApplication([])
    import threading

    runner = TaskRunner()
    order, threads, errors = [], [], []
    main = threading.get_ident()
    runner.submit(lambda: order.append("a") or "A", lambda r: (order.append(r), threads.append(threading.get_ident())))
    runner.submit(lambda: (_ for _ in ()).throw(BackendError("kaputt")), None, lambda e: errors.append(str(e)))
    runner.submit(lambda: order.append("c") or "C", lambda r: order.append(r))
    assert runner.wait_idle(5)
    end = time.time() + 5
    while len(order) < 4 and time.time() < end:
        app.processEvents()
        time.sleep(0.01)
    runner.stop()
    assert order == ["a", "c", "A", "C"] and errors == ["kaputt"]  # Aufträge der Reihe nach im Hintergrund, Rückrufe danach in Reihenfolge
    assert threads == [main]  # Rückruf im Qt-Thread
