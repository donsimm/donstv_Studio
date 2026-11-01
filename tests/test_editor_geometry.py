"""F-13, F-65: Rechnen im Editor (ohne Qt): Zoom und devicePixelRatio, Verschieben, Skalieren, Drehen, Einrasten, Ausrichten."""

import math

import pytest

from donstv_studio.ui import geometry as geo
from donstv_studio.ui.geometry import Box, ViewTransform


# --- Zoom und devicePixelRatio (F-65) ----------------------------------------------------------------
@pytest.mark.parametrize("dpr", [1.0, 2.0])
def test_f65_zoom_100_percent_is_one_overlay_pixel_per_screen_pixel(dpr):
    t = ViewTransform(zoom=1.0, dpr=dpr, origin=(10.0, 20.0))
    # logische Qt-Pixel je Overlay-Pixel: bei dpr 2 genau 0,5 (also 1 physisches Pixel)
    assert t.k * dpr == pytest.approx(1.0)
    assert t.stage_size(1920, 1080) == (1920 / dpr, 1080 / dpr)
    # zwei benachbarte Overlay-Pixel liegen genau ein physisches Pixel auseinander
    x0, _ = t.to_view(100, 0)
    x1, _ = t.to_view(101, 0)
    assert (x1 - x0) * dpr == pytest.approx(1.0)
    assert t.web_zoom == pytest.approx(1 / dpr)  # Chromium rechnet selbst mit dem dpr von Qt


@pytest.mark.parametrize("dpr", [1.0, 2.0])
@pytest.mark.parametrize("zoom", geo.ZOOM_STEPS)
def test_f65_pixel_under_pointer_roundtrip(dpr, zoom):
    t = ViewTransform(zoom=zoom, dpr=dpr, origin=(13.0, 7.0))
    for x, y in ((0, 0), (1, 1), (959, 539), (1919, 1079)):
        vx, vy = t.to_view(x + 0.5, y + 0.5)  # Mitte des Pixels
        assert t.pixel_at(vx, vy) == (x, y)
        assert t.to_overlay(*t.to_view(x, y)) == pytest.approx((x, y))


def test_f65_pointer_pixel_at_100_percent_matches_screen_pixel():
    t = ViewTransform(zoom=1.0, dpr=1.0, origin=(40.0, 30.0))
    assert t.pixel_at(40, 30) == (0, 0)
    assert t.pixel_at(40 + 123, 30 + 456) == (123, 456)
    assert t.pixel_at(39, 29) == (-1, -1)  # links oben ausserhalb


def test_f65_fit_zoom_and_steps():
    assert geo.fit_zoom(960, 540, 1920, 1080, 1.0) == pytest.approx(0.5)
    assert geo.fit_zoom(960, 540, 1920, 1080, 2.0) == pytest.approx(
        1.0
    )  # dpr 2: 960 logisch = 1920 physisch
    assert geo.fit_zoom(1000, 100, 1920, 1080, 1.0) == pytest.approx(100 / 1080)  # Höhe begrenzt
    assert geo.ZOOM_STEPS == (0.25, 0.5, 1.0, 2.0, 4.0)
    assert geo.next_zoom(1.0, 1) == 2.0 and geo.next_zoom(1.0, -1) == 0.5
    assert geo.next_zoom(4.0, 1) == 4.0 and geo.next_zoom(0.25, -1) == 0.25
    assert geo.next_zoom(0.37, 1) == 0.5 and geo.next_zoom(0.37, -1) == 0.25
    assert geo.zoom_label(0.5) == "50 %" and geo.zoom_label(4.0) == "400 %"


# --- Verschieben ---------------------------------------------------------------------------------------
def test_f13_move_gives_whole_pixels():
    b = Box(100, 50, 200, 100)
    moved, _ = geo.move_box(b, 10.4, -3.6)
    assert (moved.x, moved.y, moved.w, moved.h) == (110, 46, 200, 100)
    assert all(isinstance(v, int) for v in (moved.x, moved.y, moved.w, moved.h))
    moved, _ = geo.move_box(b, 0.5, 0.49)  # .5 rundet nach oben, nicht zur geraden Zahl
    assert (moved.x, moved.y) == (101, 50)


def test_f65_nudge():
    assert geo.nudge_box(Box(5, 5, 10, 10), -1, 0) == Box(4, 5, 10, 10)
    assert geo.nudge_box(Box(5, 5, 10, 10), 0, 10) == Box(5, 15, 10, 10)


# --- Skalieren -----------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("handle", "dx", "dy", "expected"),
    [
        ("e", 20, 99, (100, 50, 220, 100)),  # nur Breite
        ("w", -20, 99, (80, 50, 220, 100)),  # linke Kante wandert, rechte bleibt
        ("s", 99, 30, (100, 50, 200, 130)),
        ("n", 99, -30, (100, 20, 200, 130)),
        ("se", 20, 30, (100, 50, 220, 130)),
        ("nw", -20, -30, (80, 20, 220, 130)),
        ("ne", 20, -30, (100, 20, 220, 130)),
        ("sw", -20, 30, (80, 50, 220, 130)),
    ],
)
def test_f13_resize_handles_keep_opposite_edge(handle, dx, dy, expected):
    box, _ = geo.resize_box(Box(100, 50, 200, 100), handle, dx, dy)
    assert (box.x, box.y, box.w, box.h) == expected


def test_f13_resize_minimum_one_pixel_and_flip_is_prevented():
    box, _ = geo.resize_box(Box(100, 50, 200, 100), "e", -500, 0)
    assert box.w == 1 and box.x == 100
    box, _ = geo.resize_box(Box(100, 50, 200, 100), "w", 500, 0)
    assert box.w == 1 and box.x + box.w == 300  # rechte Kante bleibt


def test_f13_resize_rotated_keeps_opposite_corner():
    start = Box(100, 100, 200, 100, 90.0)
    anchor_before = geo.rotate_point(
        start.cx - 100, start.cy - 50, start.cx, start.cy, 90.0
    )  # Ecke «nw» ist gegenüber «se»
    # «se» um 30 Pixel in lokaler x-Richtung ziehen: lokale x-Achse zeigt bei 90° nach unten (+y)
    box, _ = geo.resize_box(start, "se", 0, 30)
    assert (box.w, box.h) == (230, 100)
    anchor_after = geo.rotate_point(box.cx - box.w / 2, box.cy - box.h / 2, box.cx, box.cy, 90.0)
    assert anchor_after == pytest.approx(anchor_before, abs=0.51)
    assert box.rot == 90.0


# --- Drehen --------------------------------------------------------------------------------------------
def test_f13_rotate_follows_pointer_and_shift_steps_15_degrees():
    b = Box(0, 0, 200, 100)  # Mitte (100, 50)
    press = (100.0, -50.0)  # genau über der Mitte (Drehgriff)
    now = (200.0, 50.0)  # rechts von der Mitte: 90° im Uhrzeigersinn
    assert geo.rotation_from_pointer(b, press, now, False) == 90.0
    odd = (
        100 + 100 * math.cos(math.radians(-90 + 37)),
        50 + 100 * math.sin(math.radians(-90 + 37)),
    )
    assert geo.rotation_from_pointer(b, press, odd, False) == 37.0  # ganze Grad
    assert geo.rotation_from_pointer(b, press, odd, True) == 30.0  # Umschalttaste: 15°-Schritte
    third = (
        100 + 100 * math.cos(math.radians(-90 + 83)),
        50 + 100 * math.sin(math.radians(-90 + 83)),
    )
    assert geo.rotation_from_pointer(b, press, third, True) == 90.0
    assert geo.rotation_from_pointer(
        Box(0, 0, 200, 100, 170.0), press, now, False
    ) == pytest.approx(-100.0)  # (-180, 180]


def test_normalize_angle():
    assert geo.normalize_angle(190) == -170 and geo.normalize_angle(-190) == 170
    assert (
        geo.normalize_angle(180) == 180
        and geo.normalize_angle(-180) == 180
        and geo.normalize_angle(360) == 0
    )


# --- Einrasten -----------------------------------------------------------------------------------------
def test_f65_snap_to_overlay_edges_and_center():
    t = geo.snap_targets(1920, 1080, [], [], [])
    moved, hit = geo.move_box(Box(100, 100, 200, 100), -97, 0, t, 6)  # linke Kante nähert sich 0
    assert moved.x == 0 and hit.xs == [0.0]
    moved, hit = geo.move_box(
        Box(100, 100, 200, 100), 757, 0, t, 6
    )  # Mitte der Quelle (860+100 = 960)
    assert moved.x + moved.w / 2 == 960 and 960.0 in hit.xs
    moved, _ = geo.move_box(Box(100, 100, 200, 100), 300, 0, t, 6)  # weit weg: kein Einrasten
    assert moved.x == 400


def test_f65_snap_to_guides_and_other_sources():
    other = Box(1000, 400, 300, 100)
    t = geo.snap_targets(1920, 1080, [500], [250], [other])
    moved, hit = geo.move_box(
        Box(0, 0, 100, 100), 404, 0, t, 6
    )  # rechte Kante 504 -> Hilfslinie 500
    assert moved.x + moved.w == 500 and 500.0 in hit.xs
    moved, hit = geo.move_box(
        Box(0, 0, 100, 100), 903, 0, t, 6
    )  # rechte Kante 1003 -> linke Kante der anderen (1000)
    assert moved.x + moved.w == 1000
    moved, hit = geo.move_box(
        Box(0, 0, 100, 100), 0, 248, t, 6
    )  # obere Kante 248 -> Hilfslinie 250
    assert moved.y == 250 and 250.0 in hit.ys


def test_f65_snap_switched_off_gives_plain_move():
    moved, hit = geo.move_box(Box(100, 100, 200, 100), -97, 0, None, 6)
    assert moved.x == 3 and hit.xs == []


def test_f65_snap_flags_select_targets():
    other = Box(1000, 400, 300, 100)
    only_edges = geo.snap_targets(
        1920, 1080, [500], [], [other], edges=True, guides=False, sources=False
    )
    assert 500.0 not in only_edges.xs and 1000.0 not in only_edges.xs and 0.0 in only_edges.xs
    nothing = geo.snap_targets(
        1920, 1080, [500], [], [other], edges=False, guides=False, sources=False
    )
    assert nothing.xs == [] and nothing.ys == []


def test_f65_snap_to_grid():
    moved, hit = geo.move_box(Box(0, 0, 100, 100), 41, 0, geo.SnapTargets(), 6, grid=20)
    assert moved.x == 40 and hit.dx == pytest.approx(-1)
    moved, _ = geo.move_box(
        Box(0, 0, 100, 100), 50, 0, geo.SnapTargets(), 4, grid=20
    )  # zu weit von allen Rasterlinien
    assert moved.x == 50


def test_f65_snap_during_resize_only_for_unrotated():
    t = geo.snap_targets(1920, 1080, [], [], [])
    box, hit = geo.resize_box(
        Box(100, 100, 200, 100), "e", 1617, 0, t, 6
    )  # rechte Kante 1917 -> 1920
    assert box.x + box.w == 1920 and 1920.0 in hit.xs
    box, hit = geo.resize_box(Box(100, 100, 200, 100, 10.0), "e", 1617, 0, t, 6)
    assert hit.xs == []


# --- Ausrichten ----------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("how", "expected"),
    [
        ("left", (0, 300)), ("center", (860, 300)), ("right", (1720, 300)),
        ("top", (500, 0)), ("middle", (500, 490)), ("bottom", (500, 980)),
    ],
)  # fmt: skip
def test_f65_align_to_overlay(how, expected):
    b = geo.align_box(Box(500, 300, 200, 100), how, 1920, 1080)
    assert (b.x, b.y) == expected and (b.w, b.h) == (200, 100)


def test_f65_align_odd_size_rounds_up_not_to_even():
    assert (
        geo.align_box(Box(0, 0, 101, 100), "center", 1920, 1080).x == 910
    )  # (1920-101)/2 = 909.5 -> 910


def test_f65_align_rotated_uses_bounding_box():
    b = geo.align_box(
        Box(500, 300, 200, 100, 90.0), "left", 1920, 1080
    )  # gedreht: 100 breit, 200 hoch
    assert b.bounds()[0] == pytest.approx(0, abs=0.5)
    with pytest.raises(ValueError):
        geo.align_box(Box(0, 0, 1, 1), "diagonal", 10, 10)


def test_box_contains_respects_rotation():
    b = Box(0, 0, 200, 100, 90.0)  # Mitte (100, 50), gedreht: x in 50..150, y in -50..150
    assert b.contains(100, 140) and not b.contains(10, 50)
    assert Box(0, 0, 10, 10).contains(5, 5) and not Box(0, 0, 10, 10).contains(11, 5)
