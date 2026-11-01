"""F-13, F-65: Bedienung der Vorschau mit simulierter Maus und Tastatur (offscreen, ohne Webansicht).

Die Webansicht (QtWebEngine) wird in tests/test_editor_web.py geprüft. Hier geht es um Ziehen, Griffe, Zoom,
Einrasten, Hilfslinien und Rückgängig auf der Bedienebene.
"""

import pytest

pytest.importorskip(
    "PyQt6.QtWidgets", exc_type=ImportError, reason="PyQt6 ist nicht installierbar oder lädt nicht"
)

from PyQt6.QtCore import QEvent, QPointF, Qt
from PyQt6.QtGui import QMouseEvent, QWheelEvent
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from donstv_studio.ui import geometry as geo
from donstv_studio.ui import theme
from donstv_studio.ui.backend import DirectRunner
from donstv_studio.ui.editor_model import EditorModel
from donstv_studio.ui.editor_prefs import EditorPrefs
from donstv_studio.ui.editor_view import EditorView
from donstv_studio.ui.geometry import FIT
from fake_backend import FakeBackend

NO, SHIFT = Qt.KeyboardModifier.NoModifier, Qt.KeyboardModifier.ShiftModifier


@pytest.fixture
def env(app):
    backend = FakeBackend()
    backend.add("Test", 800, 400)
    saved: dict[str, str] = {}
    prefs = EditorPrefs(lambda k, v: saved.__setitem__(k, v))
    model = EditorModel(backend, DirectRunner(), lambda k, v: saved.__setitem__(k, v))
    model.load()
    view = EditorView(model, prefs, use_web=False)
    view.resize(1100, 700)
    view.show()
    view.set_zoom(1.0)
    app.processEvents()
    yield view, model, prefs, backend, saved
    view.close()
    view.deleteLater()


def add(model, x, y, w, h, text="Q"):
    model.add_text_source(text)
    sid = model.selected_id
    model.set_box(sid, geo.Box(x, y, w, h))
    return sid


def ev(kind, layer, x, y, button, buttons, mods=NO):
    pos = QPointF(x, y)
    return QMouseEvent(kind, pos, layer.mapToGlobal(pos), button, buttons, mods)


def press(layer, x, y, mods=NO):
    QApplication.sendEvent(
        layer,
        ev(
            QEvent.Type.MouseButtonPress,
            layer,
            x,
            y,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            mods,
        ),
    )


def move(layer, x, y, mods=NO, held=True):
    b = Qt.MouseButton.LeftButton if held else Qt.MouseButton.NoButton
    QApplication.sendEvent(
        layer, ev(QEvent.Type.MouseMove, layer, x, y, Qt.MouseButton.NoButton, b, mods)
    )


def release(layer, x, y, mods=NO):
    QApplication.sendEvent(
        layer,
        ev(
            QEvent.Type.MouseButtonRelease,
            layer,
            x,
            y,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
            mods,
        ),
    )


def drag(layer, p0, p1, mods=NO, steps=5):
    press(layer, *p0, mods)
    for i in range(1, steps + 1):
        move(layer, p0[0] + (p1[0] - p0[0]) * i / steps, p0[1] + (p1[1] - p0[1]) * i / steps, mods)
    release(layer, *p1, mods)


def layer_image(view):
    """Was die Bedienebene allein zeichnet (ohne Hintergrund): durchsichtig, wo nichts gezeichnet wird."""
    from PyQt6.QtGui import QImage
    from PyQt6.QtWidgets import QWidget

    img = QImage(view.layer.size(), QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    view.layer.render(img, flags=QWidget.RenderFlag.DrawChildren)
    return img


def at(view, x, y):
    """Ansichtskoordinate der Overlay-Pixelmitte (x + 0,5, y + 0,5)."""
    return view.transform().to_view(x + 0.5, y + 0.5)


# --- Auswahl ---------------------------------------------------------------------------------------
def test_f13_click_selects_topmost_source_and_empty_clears(env):
    view, model, *_ = env
    a = add(model, 100, 100, 200, 100, "A")
    b = add(model, 150, 120, 200, 100, "B")  # liegt vorn
    model.select_source(None)
    press(view.layer, *at(view, 200, 150))  # Überlappung
    release(view.layer, *at(view, 200, 150))
    assert model.selected_id == b
    press(view.layer, *at(view, 110, 105))
    release(view.layer, *at(view, 110, 105))
    assert model.selected_id == a
    press(view.layer, *at(view, 700, 350))
    release(view.layer, *at(view, 700, 350))
    assert model.selected_id is None


def test_f13_hidden_source_cannot_be_selected(env):
    view, model, *_ = env
    a = add(model, 100, 100, 200, 100)
    model.set_visible(a, False)
    model.select_source(None)
    press(view.layer, *at(view, 150, 150))
    release(view.layer, *at(view, 150, 150))
    assert model.selected_id is None


# --- Verschieben -----------------------------------------------------------------------------------
@pytest.mark.parametrize(("zoom", "dx_screen", "dy_screen", "expect"), [
    (1.0, 37, -12, (137, 88)), (0.5, 10, 10, (120, 120)), (2.0, 10, 6, (105, 103)), (2.0, 7, 7, (104, 104)), (4.0, 3, 5, (101, 101)),
])  # fmt: skip
def test_f65_drag_moves_in_whole_overlay_pixels(env, zoom, dx_screen, dy_screen, expect):
    view, model, prefs, *_ = env
    prefs.set_snap(False)
    sid = add(model, 100, 100, 100, 100)
    view.set_zoom(zoom)
    p0 = view.transform().to_view(150, 150)
    drag(view.layer, p0, (p0[0] + dx_screen, p0[1] + dy_screen))
    s = model.source(sid)
    assert (s["x"], s["y"]) == expect
    assert isinstance(s["x"], int) and isinstance(s["y"], int)


def test_f65_zoom_100_percent_pointer_coordinate(env):
    view, model, *_ = env
    seen = []
    view.pointer_changed.connect(lambda inside, x, y: seen.append((x, y) if inside else None))
    for x, y in ((0, 0), (123, 45), (799, 399)):
        move(view.layer, *at(view, x, y), held=False)
        assert seen[-1] == (x, y)
    view.layer.leaveEvent(QEvent(QEvent.Type.Leave))
    assert seen[-1] is None


def test_f65_drag_is_one_undo_step_and_restores(env):
    view, model, prefs, backend, _ = env
    prefs.set_snap(False)
    sid = add(model, 100, 100, 100, 100)
    p0 = view.transform().to_view(150, 150)
    drag(view.layer, p0, (p0[0] + 40, p0[1] + 25), steps=8)
    assert (model.source(sid)["x"], model.source(sid)["y"]) == (140, 125)
    assert backend.source(model.current_id, sid)["x"] == 140  # auch im Kern
    model.undo()
    assert (model.source(sid)["x"], model.source(sid)["y"]) == (100, 100)
    model.redo()
    assert (model.source(sid)["x"], model.source(sid)["y"]) == (140, 125)


def test_f13_click_without_moving_creates_no_undo_step(env):
    view, model, *_ = env
    sid = add(model, 100, 100, 100, 100)
    before = model.can_undo()
    press(view.layer, *at(view, 150, 150))
    release(view.layer, *at(view, 150, 150))
    assert model.can_undo() == before and model.source(sid)["x"] == 100


# --- Skalieren -------------------------------------------------------------------------------------
@pytest.mark.parametrize(("handle", "d", "expect"), [
    ("e", (40, 0), (100, 100, 140, 100)), ("w", (-30, 0), (70, 100, 130, 100)), ("s", (0, 25), (100, 100, 100, 125)),
    ("n", (0, -20), (100, 80, 100, 120)), ("se", (15, 15), (100, 100, 115, 115)), ("nw", (-10, -10), (90, 90, 110, 110)),
    ("ne", (10, -10), (100, 90, 110, 110)), ("sw", (-10, 10), (90, 100, 110, 110)),
])  # fmt: skip
def test_f13_resize_handles_give_whole_pixel_values(env, handle, d, expect):
    view, model, prefs, *_ = env
    prefs.set_snap(False)
    sid = add(model, 100, 100, 100, 100)
    pt = view.layer.handle_points()[handle]
    drag(view.layer, (pt.x(), pt.y()), (pt.x() + d[0], pt.y() + d[1]))
    s = model.source(sid)
    assert (s["x"], s["y"], s["width"], s["height"]) == expect


def test_f13_resize_at_zoom_200_uses_overlay_pixels(env):
    view, model, prefs, *_ = env
    prefs.set_snap(False)
    sid = add(model, 100, 100, 100, 100)
    view.set_zoom(2.0)
    pt = view.layer.handle_points()["se"]
    drag(
        view.layer, (pt.x(), pt.y()), (pt.x() + 20, pt.y() + 10)
    )  # 20 × 10 Bildschirmpixel = 10 × 5 Overlay-Pixel
    s = model.source(sid)
    assert (s["width"], s["height"]) == (110, 105)


# --- Drehen ----------------------------------------------------------------------------------------
def test_f13_rotate_handle_turns_source_and_shift_snaps_to_15_degrees(env):
    view, model, prefs, *_ = env
    prefs.set_snap(False)
    sid = add(model, 300, 150, 200, 100)  # Mitte (400, 200)
    rot = view.layer.handle_points()[geo.ROTATE]
    cx, cy = view.transform().to_view(400, 200)
    drag(
        view.layer, (rot.x(), rot.y()), (cx + 100, cy)
    )  # Zeiger rechts der Mitte: 90° im Uhrzeigersinn
    assert model.source(sid)["rotation"] == 90.0
    model.undo()
    assert model.source(sid)["rotation"] == 0.0
    import math

    ang = math.radians(-90 + 37)
    target = (cx + 100 * math.cos(ang), cy + 100 * math.sin(ang))
    rot = view.layer.handle_points()[geo.ROTATE]
    drag(view.layer, (rot.x(), rot.y()), target, mods=SHIFT)
    assert model.source(sid)["rotation"] == 30.0
    model.undo()
    rot = view.layer.handle_points()[geo.ROTATE]
    drag(view.layer, (rot.x(), rot.y()), target)
    assert model.source(sid)["rotation"] == 37.0


def test_f13_rotated_source_is_hit_by_its_rotated_outline(env):
    view, model, *_ = env
    sid = add(model, 300, 150, 200, 100)
    model.change_box(
        sid, geo.Box(300, 150, 200, 100, 90.0)
    )  # Mitte (400, 200); gedreht 100 breit, 200 hoch
    model.select_source(None)
    press(view.layer, *at(view, 400, 290))  # unterhalb der Mitte: nur im gedrehten Rechteck
    release(view.layer, *at(view, 400, 290))
    assert model.selected_id == sid
    model.select_source(None)
    press(view.layer, *at(view, 320, 200))  # liegt im ungedrehten, nicht im gedrehten Rechteck
    release(view.layer, *at(view, 320, 200))
    assert model.selected_id is None


# --- Pfeiltasten -----------------------------------------------------------------------------------
def test_f65_arrow_keys_move_one_pixel_and_shift_ten(env):
    view, model, *_ = env
    sid = add(model, 100, 100, 50, 50)
    view.layer.setFocus()
    for key, mods, expect in (
        (Qt.Key.Key_Right, NO, (101, 100)), (Qt.Key.Key_Down, NO, (101, 101)),
        (Qt.Key.Key_Left, SHIFT, (91, 101)), (Qt.Key.Key_Up, SHIFT, (91, 91)),
    ):  # fmt: skip
        QTest.keyClick(view.layer, key, mods)
        s = model.source(sid)
        assert (s["x"], s["y"]) == expect
    model.undo()  # alle Pfeilschritte in einem Zug
    assert (model.source(sid)["x"], model.source(sid)["y"]) == (100, 100)


def test_f65_arrow_keys_do_nothing_without_selection(env):
    view, model, *_ = env
    sid = add(model, 100, 100, 50, 50)
    model.select_source(None)
    QTest.keyClick(view.layer, Qt.Key.Key_Right)
    assert model.source(sid)["x"] == 100


# --- Zoom ------------------------------------------------------------------------------------------
def test_f65_zoom_steps_and_fit(env):
    view, *_ = env
    for z in (0.25, 0.5, 1.0, 2.0, 4.0):
        view.set_zoom(z)
        assert view.zoom() == z and not view.fit_mode
        assert view.transform().k == pytest.approx(z)
    view.set_zoom(FIT)
    assert view.fit_mode
    w, h = view.model.size()
    sw, sh = view.stage.width(), view.stage.height()
    assert sw <= view.viewport.width() and sh <= view.viewport.height()
    assert abs(sw / sh - w / h) < 0.02
    assert view.zoom() == pytest.approx(
        geo.fit_zoom(view.viewport.width() - 16, view.viewport.height() - 16, w, h, 1.0)
    )


def test_f65_ctrl_wheel_zooms_in_steps_and_keeps_point_under_pointer(env):
    view, model, *_ = env
    view.set_zoom(1.0)
    anchor = view.transform().to_view(400, 200)
    wheel = QWheelEvent(QPointF(*anchor), view.layer.mapToGlobal(QPointF(*anchor)), QPointF(0, 0).toPoint(),
                        QPointF(0, 120).toPoint(), Qt.MouseButton.NoButton, Qt.KeyboardModifier.ControlModifier,
                        Qt.ScrollPhase.NoScrollPhase, False)  # fmt: skip
    QApplication.sendEvent(view.layer, wheel)
    assert view.zoom() == 2.0
    after = view.transform().to_view(400, 200)
    assert after == pytest.approx(anchor, abs=1.5)


def test_f65_zoom_400_scrolls_and_keeps_pixel_mapping(env):
    view, model, *_ = env
    view.set_zoom(4.0)
    assert view.hbar.isVisible() and view.vbar.isVisible()  # 3200 × 1600 passt nicht in 1080 × 680
    t0 = view.transform()
    view.hbar.setValue(view.hbar.value() + 100)
    t1 = view.transform()
    assert t0.origin[0] - t1.origin[0] == pytest.approx(100, abs=1)
    assert t1.k == 4.0 and t1.pixel_at(*t1.to_view(10.5, 20.5)) == (10, 20)


def test_f65_dpr_2_maps_one_overlay_pixel_to_one_physical_pixel(env):
    view, model, *_ = env
    view.dpr_override = 2.0
    view.set_zoom(1.0)
    t = view.transform()
    assert t.k == 0.5
    assert (view.stage.width(), view.stage.height()) == (400, 200)  # 800 × 400 physische Pixel
    assert t.pixel_at(*t.to_view(123.5, 45.5)) == (123, 45)
    view.dpr_override = 1.0
    view.set_zoom(1.0)
    assert (view.stage.width(), view.stage.height()) == (800, 400)


def test_f65_shrink_preview_limits_fit_zoom(env):
    view, model, prefs, *_ = env
    view.set_zoom(FIT)
    assert view.zoom() > 0.5  # 800 × 400 in 1080 × 680: mehr als 100 %
    prefs.set_shrink(True)
    assert view.zoom() == pytest.approx(0.5)
    prefs.set_shrink(False)
    assert view.zoom() > 0.5


def test_f65_zoom_is_remembered(env):
    view, model, prefs, _, saved = env
    view.set_zoom(2.0)
    assert saved["ui.editor.zoom"] == "2.0"
    view.set_zoom(FIT)
    assert saved["ui.editor.zoom"] == "fit"
    p2 = EditorPrefs()
    p2.load(
        {
            "ui.editor.zoom": "0.5",
            "ui.editor.snap": "0",
            "ui.editor.grid_size": "30",
            "ui.editor.preview_fps": "999",
        }
    )
    assert (p2.zoom, p2.snap, p2.grid_size, p2.fps) == (0.5, False, 30, 60)
    p2.load({"ui.editor.zoom": "3.7", "ui.editor.grid_size": "abc"})  # ungültig: Standardwerte
    assert p2.zoom == FIT and p2.grid_size == 20


# --- Einrasten, Hilfslinien, Raster ------------------------------------------------------------------
def test_f65_snap_to_overlay_edge_and_center_and_other_source(env):
    view, model, prefs, *_ = env
    sid = add(model, 100, 100, 100, 100)
    other = add(model, 500, 200, 100, 100, "Anderes")
    model.select_source(sid)
    p0 = view.transform().to_view(150, 150)
    drag(view.layer, p0, (p0[0] - 97, p0[1]))  # linke Kante 100 -> 3: rastet am Rand (0) ein
    assert model.source(sid)["x"] == 0
    model.undo()
    drag(
        view.layer, p0, (p0[0] + 402, p0[1] + 1)
    )  # linke Kante 502 -> 500: linke Kante der anderen Quelle
    assert model.source(sid)["x"] == 500
    model.undo()
    drag(
        view.layer, p0, (p0[0] + 355, p0[1] + 1)
    )  # rechte Kante 555 -> 550: Mitte der anderen Quelle
    assert model.source(sid)["x"] + 100 == 550
    assert model.selected_id == sid and other != sid


def test_f65_snap_can_be_switched_off(env):
    view, model, prefs, *_ = env
    prefs.set_snap(False)
    sid = add(model, 100, 100, 100, 100)
    p0 = view.transform().to_view(150, 150)
    drag(view.layer, p0, (p0[0] - 97, p0[1]))
    assert model.source(sid)["x"] == 3
    prefs.set_snap(True)
    model.undo()
    drag(view.layer, p0, (p0[0] - 97, p0[1]))
    assert model.source(sid)["x"] == 0


def test_f65_snap_to_grid(env):
    view, model, prefs, *_ = env
    sid = add(
        model, 101, 103, 40, 40
    )  # Kanten, Mitte und Gegenkante liegen gleich weit von einer Rasterlinie
    model.select_source(sid)
    prefs.set_grid_size(20)
    prefs.set_grid(True)
    p0 = view.transform().to_view(110, 110)
    drag(
        view.layer, p0, (p0[0] + 1, p0[1] - 2)
    )  # linke Kante 102, obere 101: je 2 bzw. 1 Pixel neben 100
    s = model.source(sid)
    assert (s["x"], s["y"]) == (100, 100)


def test_f65_drag_from_ruler_creates_guide_and_move_snaps_to_it(env):
    view, model, prefs, _, saved = env
    top = view.ruler_top
    viewport_pt = view.transform().to_view(0, 250)  # waagerechte Hilfslinie bei y = 250
    start = top.mapFromGlobal(view.layer.mapToGlobal(QPointF(100, 0).toPoint()))
    press_ev = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(start), top.mapToGlobal(QPointF(start)),
                           Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, NO)  # fmt: skip
    QApplication.sendEvent(top, press_ev)
    target = view.layer.mapToGlobal(QPointF(300, viewport_pt[1]))
    QApplication.sendEvent(top, QMouseEvent(QEvent.Type.MouseMove, top.mapFromGlobal(target), target,
                                            Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton, NO))  # fmt: skip
    QApplication.sendEvent(top, QMouseEvent(QEvent.Type.MouseButtonRelease, top.mapFromGlobal(target), target,
                                            Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton, NO))  # fmt: skip
    assert model.guides() == ([], [250])
    assert saved[f"ui.guides.{model.current_id}"]  # pro Overlay gespeichert
    sid = add(model, 100, 100, 100, 100)
    p0 = view.transform().to_view(150, 150)
    drag(
        view.layer, p0, (p0[0], p0[1] + 147)
    )  # untere Kante 200 -> 347 liegt nahe 350? Nein: obere Kante 247 -> 250
    assert model.source(sid)["y"] == 250


def test_f65_guide_can_be_moved_and_dragged_back_onto_the_ruler_to_delete(env):
    view, model, *_ = env
    model.set_guides([300], [])
    x = view.transform().to_view(300, 0)[0]
    drag(view.layer, (x, 100), (x + 50, 100))
    assert model.guides() == ([350], [])
    x = view.transform().to_view(350, 0)[0]
    press(view.layer, x, 100)
    move(view.layer, -30, 100)  # links aus der Ansicht heraus, über das Lineal
    release(view.layer, -30, 100)
    assert model.guides() == ([], [])


def test_f65_guides_are_whole_pixels_and_cleared_by_button_logic(env):
    view, model, *_ = env
    model.set_guides([10, 20], [30])
    assert all(isinstance(v, int) for v in model.guides()[0] + model.guides()[1])
    model.set_guides([], [])
    assert model.guides() == ([], [])


# --- Zeichnen ----------------------------------------------------------------------------------------
def test_f13_selection_frame_and_handles_drawn_by_qt_in_accent_color(env):
    view, model, prefs, *_ = env
    add(model, 100, 100, 200, 100)
    view.apply_theme(theme.DARK)
    app = QApplication.instance()
    app.processEvents()
    img = layer_image(view)
    t = view.transform()
    left, top = t.to_view(100, 100)
    accent = theme.palette(theme.DARK)["accent"]
    on_edge = img.pixelColor(
        round(left), round(top + 25)
    )  # linke Kante, zwischen zwei Griffen (Rahmen 2 Pixel breit)
    assert on_edge.name() == accent
    handle = img.pixelColor(
        round(left), round(top + 50)
    )  # Mitte der linken Kante: Griff in der Textfarbe
    assert handle.name() == theme.palette(theme.DARK)["text"]
    model.select_source(None)
    app.processEvents()
    assert (
        layer_image(view).pixelColor(round(left), round(top + 25)).alpha() == 0
    )  # ohne Auswahl: durchsichtig


def test_f65_layer_is_transparent_everywhere_else(env):
    view, model, *_ = env
    add(model, 100, 100, 100, 100)
    model.select_source(None)
    QApplication.instance().processEvents()
    img = layer_image(view)
    assert (
        img.pixelColor(5, 5).alpha() == 0
        and img.pixelColor(img.width() // 2, img.height() - 3).alpha() == 0
    )


def test_f13_rulers_follow_zoom(env):
    view, *_ = env
    from donstv_studio.ui.editor_view import ruler_step

    assert ruler_step(1.0) == 100 and ruler_step(4.0) == 20 and ruler_step(0.25) == 500
    assert ruler_step(1 / 64) >= 1000
