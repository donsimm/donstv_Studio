"""F-10, F-11, F-12, F-66: Modell und Prüfregeln."""

import dataclasses

import pytest

from donstv_studio.overlays.models import Overlay, OverlayError, Source


def src(**kw):
    base = {"kind": "text", "x": 0, "y": 0, "width": 10, "height": 10}
    return Source(**{**base, **kw})


def test_f11_defaults():
    o = Overlay(name="A")
    assert (o.width, o.height, o.output) == (1920, 1080, "browser")
    assert o.sources == []


def test_f66_token_random_and_at_least_128_bit():
    tokens = {Overlay(name="A").token for _ in range(50)}
    assert len(tokens) == 50
    # urlsafe-Base64: 6 Bit je Zeichen; 128 Bit => mindestens 22 Zeichen
    assert all(len(t) * 6 >= 128 for t in tokens)


@pytest.mark.parametrize(
    "kw", [{"width": 0}, {"height": 0}, {"width": -5}, {"width": 1.5}, {"width": True}]
)
def test_f11_overlay_size_validation(kw):
    with pytest.raises(OverlayError, match="Overlays"):
        Overlay(name="A", **kw)


def test_f10_empty_name_and_bad_output_rejected():
    with pytest.raises(OverlayError, match="Name"):
        Overlay(name="  ")
    with pytest.raises(OverlayError, match="Ausgabeart"):
        Overlay(name="A", output="hdmi")


def test_f66_ndi_stored_but_not_available():
    assert Overlay(name="A", output="ndi").output_status == "nicht verfügbar"
    assert Overlay(name="A").output_status == "verfügbar"


@pytest.mark.parametrize(
    "kw", [{"width": 0}, {"height": 0}, {"width": 0.5}, {"x": 1.5}, {"y": "3"}, {"x": None}]
)
def test_f65_source_requires_whole_pixels(kw):
    with pytest.raises(OverlayError):
        src(**kw)


def test_f12_source_may_lie_partly_outside():
    s = src(x=-50, y=2000, width=300, height=100)
    assert (s.x, s.y) == (-50, 2000)


def test_f12_rotation_decimal_allowed_and_checked():
    assert src(rotation=12.5).rotation == 12.5
    assert src(rotation=90).rotation == 90.0
    for bad in (float("nan"), float("inf"), "90", True):
        with pytest.raises(OverlayError, match="Drehung"):
            src(rotation=bad)


def test_f12_kind_and_props_checked():
    with pytest.raises(OverlayError, match="Quellenart"):
        src(kind="video")
    with pytest.raises(OverlayError, match="props"):
        src(props={"x": object()})
    with pytest.raises(OverlayError, match="visible"):
        src(visible=1)


def test_replace_revalidates():
    with pytest.raises(OverlayError):
        dataclasses.replace(src(), width=0)


def test_f65_no_percent_fields_in_model():
    names = {f.name for f in dataclasses.fields(Source)} | {
        f.name for f in dataclasses.fields(Overlay)
    }
    assert not any("percent" in n or "pct" in n for n in names)
    d = src().to_dict()
    assert all(isinstance(d[k], int) for k in ("x", "y", "width", "height", "z"))


# --- P04: Prüfung der props je Quellenart, Obergrenze der Auflösung ------------------------


def test_f11_resolution_upper_limit_8192():
    assert Overlay(name="A", width=8192, height=8192).width == 8192
    with pytest.raises(OverlayError, match="darf höchstens 8192 sein"):
        Overlay(name="A", width=8193)
    with pytest.raises(OverlayError, match="darf höchstens 8192 sein"):
        Overlay(name="A", height=9000)


def test_f15_text_props_valid():
    s = src(
        props={
            "text": "Grüezi",
            "color": "#ff8800",
            "size": 64,
            "font": "DejaVu Sans",
            "style": "comic",
        }
    )
    assert s.props["size"] == 64
    for style in ("comic", "thick", "plain", "none"):
        assert src(props={"style": style}).props["style"] == style
    src(props={})  # fehlende Werte gelten als Standard


@pytest.mark.parametrize(
    ("props", "match"),
    [
        ({"text": 5}, "Text"),
        ({"text": "x" * 5001}, "Text"),
        ({"color": "rot"}, "Farbe"),
        ({"color": "#12"}, "Farbe"),
        ({"size": 0}, "Schriftgrösse"),
        ({"size": 12.5}, "Schriftgrösse"),
        ({"size": 5000}, "höchstens"),
        ({"font": 'x"; background:url(//e)'}, "Schriftname"),
        ({"font": ""}, "Schriftname"),
        ({"style": "fett"}, "Stil"),
        ({"style": "comic_thick"}, "Stil"),  # alter Schlüssel, ersetzt durch «thick»
        ({"media_id": "a" * 32}, "unbekannte Eigenschaften"),
    ],
)
def test_f15_text_props_invalid(props, match):
    with pytest.raises(OverlayError, match=match):
        src(kind="text", props=props)


def test_f16_image_props():
    assert src(kind="image", props={"media_id": "a" * 32}).props["media_id"] == "a" * 32
    assert src(kind="image", props={"media_id": ""}).kind == "image"
    for bad in ({"media_id": "../etc"}, {"media_id": 3}, {"text": "x"}):
        with pytest.raises(OverlayError):
            src(kind="image", props=bad)
