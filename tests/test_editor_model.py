"""F-10 bis F-14, F-65: Zustand des Editors mit Rückgängig/Wiederholen, Hilfslinien und Fehlerfall (ohne Kern, ohne Fenster)."""

import json

import pytest

pytest.importorskip("PyQt6.QtCore", exc_type=ImportError, reason="PyQt6 ist nicht installierbar oder lädt nicht")

from donstv_studio.ui.backend import DirectRunner, TaskRunner
from donstv_studio.ui.editor_model import EditorModel, box_of, source_label
from donstv_studio.ui.geometry import Box
from fake_backend import FakeBackend


@pytest.fixture
def env():
    backend = FakeBackend()
    o = backend.add("Hauptbild")
    saved: dict[str, str] = {}
    model = EditorModel(backend, DirectRunner(), lambda k, v: saved.__setitem__(k, v))
    model.load()
    return backend, model, saved, o


def add_text(model, text="Hallo"):
    model.add_text_source(text)
    return model.selected_id


def test_f10_load_selects_first_overlay(env):
    backend, model, _, o = env
    assert [x["name"] for x in model.overlays] == ["Hauptbild"] and model.current_id == o["id"]
    assert model.size() == (1920, 1080)
    assert model.preview_url().endswith(f"/o/{o['id']}?t={o['token']}")  # Feld «url» der Schnittstelle (P04)


def test_f10_create_rename_duplicate_delete(env):
    backend, model, _, o = env
    model.create_overlay("Zweites")
    assert model.current().get("name") == "Zweites" and len(model.overlays) == 2
    two = model.current_id
    model.rename_overlay(two, "  Umbenannt ")
    assert model.current()["name"] == "Umbenannt" and backend.overlays[1]["name"] == "Umbenannt"
    model.rename_overlay(two, "   ")  # leerer Name wird ignoriert
    assert model.current()["name"] == "Umbenannt"
    model.duplicate_overlay(two)
    assert model.current()["name"] == "Umbenannt (Kopie)" and len(model.overlays) == 3
    model.delete_overlay(model.current_id)
    assert len(model.overlays) == 2 and len(backend.overlays) == 2
    model.delete_overlay(two)
    assert model.current_id == o["id"]  # ein anderes Overlay wird gewählt
    model.delete_overlay(o["id"])
    assert model.current_id is None and model.overlays == [] and backend.overlays == []


def test_f12_add_text_source_is_centered_and_selected(env):
    backend, model, _, o = env
    sid = add_text(model, "Willkommen")
    s = model.source(sid)
    assert s["kind"] == "text" and s["props"]["text"] == "Willkommen"
    assert (s["width"], s["height"]) == (600, 120) and (s["x"], s["y"]) == ((1920 - 600) // 2, (1080 - 120) // 2)
    assert backend.source(o["id"], sid)["x"] == s["x"]
    assert source_label(s) == "Text: Willkommen"


def test_f12_add_image_source_uploads_then_adds(env):
    backend, model, _, o = env
    model.add_image_source("/tmp/logo.png", (300, 200))
    s = model.selected()
    assert s["kind"] == "image" and (s["width"], s["height"]) == (300, 200)
    assert s["props"]["media_id"] in backend.media
    assert source_label(s, model.media_names) == "Bild: logo.png"
    model.add_image_source("/tmp/gross.png", (5000, 3000))  # grösser als das Overlay: auf die Overlay-Grösse begrenzt
    assert (model.selected()["width"], model.selected()["height"]) == (1920, 1080)
    model.add_image_source("/tmp/x.svg", None)  # Grösse unbekannt (SVG): Standardgrösse
    assert (model.selected()["width"], model.selected()["height"]) == (400, 300)


def test_f12_delete_visibility_and_order(env):
    backend, model, _, o = env
    a, b, c = add_text(model, "A"), add_text(model, "B"), add_text(model, "C")
    assert [s["id"] for s in model.sources()] == [a, b, c]
    model.move_in_order(a, +1)  # nach vorn
    assert [s["id"] for s in model.sources()] == [b, a, c]
    assert [s["id"] for s in backend.overlays[0]["sources"]] == [b, a, c]
    assert [s["z"] for s in model.sources()] == [0, 1, 2]
    model.move_in_order(c, +1)  # schon ganz vorn: nichts
    assert [s["id"] for s in model.sources()] == [b, a, c]
    model.move_in_order(b, -1)  # schon ganz hinten
    assert [s["id"] for s in model.sources()] == [b, a, c]
    model.set_order([c, b, a])
    assert [s["id"] for s in backend.overlays[0]["sources"]] == [c, b, a]
    model.set_order([c, b])  # unvollständig: abgelehnt
    assert [s["id"] for s in model.sources()] == [c, b, a]
    model.set_visible(a, False)
    assert model.source(a)["visible"] is False and backend.source(o["id"], a)["visible"] is False
    model.delete_source(b)
    assert [s["id"] for s in model.sources()] == [c, a] and len(backend.overlays[0]["sources"]) == 2
    assert model.selected_id is None or model.selected_id != b


def test_f65_set_box_whole_pixels_and_sync(env):
    backend, model, _, o = env
    sid = add_text(model)
    model.change_box(sid, Box(10, 20, 300, 80, 15.0))
    assert box_of(model.source(sid)) == Box(10, 20, 300, 80, 15.0)
    sent = backend.source(o["id"], sid)
    assert (sent["x"], sent["y"], sent["width"], sent["height"], sent["rotation"]) == (10, 20, 300, 80, 15.0)
    assert all(isinstance(sent[k], int) for k in ("x", "y", "width", "height"))


def test_f13_undo_redo_for_position_size_rotation(env):
    backend, model, _, o = env
    sid = add_text(model)
    start = box_of(model.source(sid))
    model.change_box(sid, Box(100, 100, 200, 100))
    model.change_box(sid, Box(150, 100, 200, 100))
    model.change_box(sid, Box(150, 100, 250, 100, 30.0))
    assert model.can_undo() and not model.can_redo()
    model.undo()
    assert box_of(model.source(sid)) == Box(150, 100, 200, 100)
    model.undo()
    assert box_of(model.source(sid)) == Box(100, 100, 200, 100)
    model.undo()
    assert box_of(model.source(sid)) == start and not model.can_undo() and model.can_redo()
    model.redo()
    model.redo()
    assert box_of(model.source(sid)) == Box(150, 100, 200, 100)
    assert backend.source(o["id"], sid)["x"] == 150  # auch im Kern
    model.change_box(sid, Box(0, 0, 10, 10))  # neue Änderung leert «Wiederholen»
    assert not model.can_redo()
    model.undo()
    model.undo()
    model.undo()
    model.undo()  # mehr Schritte als vorhanden: harmlos
    assert box_of(model.source(sid)) == start


def test_f65_arrow_nudges_merge_into_one_undo_step(env):
    _, model, _, _ = env
    sid = add_text(model)
    x0 = model.source(sid)["x"]
    for _ in range(5):
        model.nudge(1, 0)
    model.nudge(0, 10)
    assert model.source(sid)["x"] == x0 + 5
    model.undo()  # alle Schritte in einem Zug (innerhalb des Zeitfensters)
    assert model.source(sid)["x"] == x0


def test_f13_history_is_kept_per_overlay_and_dropped_with_deleted_source(env):
    backend, model, _, o = env
    sid = add_text(model)
    model.change_box(sid, Box(1, 1, 50, 50))
    model.create_overlay("B")
    assert not model.can_undo()  # anderes Overlay, eigener Verlauf
    model.select_overlay(o["id"])
    assert model.can_undo()
    model.delete_source(sid)
    assert not model.can_undo()


def test_f13_failed_update_resyncs_from_core(env):
    backend, model, _, o = env
    sid = add_text(model)
    errors = []
    model.error.connect(errors.append)
    backend.fail_next = "Der Kern-Dienst antwortet nicht"
    model.set_box(sid, Box(5, 5, 50, 50))
    assert errors == ["Der Kern-Dienst antwortet nicht"]
    assert box_of(model.source(sid)) == box_of(backend.source(o["id"], sid))  # Stand nach dem Neuladen = Kern


def test_f65_guides_per_overlay_saved_and_restored(env):
    backend, model, saved, o = env
    model.set_guides([500, 100, 100], [250])
    assert model.guides() == ([100, 500], [250])  # sortiert, ohne Doppelte
    key = f"ui.guides.{o['id']}"
    assert json.loads(saved[key]) == {"v": [100, 500], "h": [250]}
    model.create_overlay("B")
    assert model.guides() == ([], [])  # eigene Linien je Overlay
    fresh = EditorModel(backend, DirectRunner(), None)
    fresh.load()
    fresh.load_guides({key: saved[key], "ui.theme": "dark", "ui.guides.kaputt": "{nicht json"})
    fresh.select_overlay(o["id"])
    assert fresh.guides() == ([100, 500], [250])
    model.select_overlay(o["id"])
    model.set_guides([], [])
    assert saved[key] == ""  # leer = entfernt
    model.delete_overlay(o["id"])
    assert saved[key] == ""


def test_f66_output_choice_saved_to_core(env):
    backend, model, _, o = env
    model.set_output(o["id"], "ndi")
    assert backend.overlays[0]["output"] == "ndi" and model.current()["output_status"] == "nicht verfügbar"
    model.set_output(o["id"], "browser")
    assert model.current()["output_status"] == "verfügbar"


def test_runner_merges_pending_updates_of_the_same_source():
    """Zusammenfassen: Von vielen Ziehschritten erreicht den Kern nur der letzte Stand (aber nie ein veralteter)."""
    import threading

    from PyQt6.QtCore import QCoreApplication

    runner = TaskRunner()
    gate = threading.Event()
    calls: list[dict] = []
    runner.submit(lambda: gate.wait(5))  # hält den Hintergrundthread an
    for i in range(50):
        runner.submit(lambda **f: calls.append(f), key=("o", "s"), fields={"x": i, "y": 7})
    gate.set()
    assert runner.wait_idle(5)
    QCoreApplication.processEvents()
    runner.stop()
    assert calls == [{"x": 49, "y": 7}]
