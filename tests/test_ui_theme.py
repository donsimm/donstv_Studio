"""F-06, U-06: Kontrast beider Themes (ohne Qt, läuft immer)."""

import pytest

from donstv_studio.ui import theme


def test_contrast_formula_matches_wcag_reference_values():
    assert theme.contrast_ratio("#000000", "#ffffff") == pytest.approx(21.0)
    assert theme.contrast_ratio("#ffffff", "#ffffff") == pytest.approx(1.0)
    # bekannter Wert: #767676 auf Weiss = 4.54 (gerade noch AA)
    assert theme.contrast_ratio("#767676", "#ffffff") == pytest.approx(4.54, abs=0.01)
    assert theme.contrast_ratio("#777777", "#ffffff") < 4.5


@pytest.mark.parametrize("name", [theme.DARK, theme.LIGHT])
def test_f06_all_text_colors_have_contrast_4_5(name):
    p = theme.PALETTES[name]
    for fg, bg in theme.TEXT_PAIRS:
        ratio = theme.contrast_ratio(p[fg], p[bg])
        assert ratio >= theme.MIN_CONTRAST, f"{name}: {fg} auf {bg} = {ratio:.2f}"


def test_f06_every_text_color_of_the_palette_is_covered():
    text_like = {"text", "text_muted", "accent_text", "selection_text", "ok", "warn", "error"}
    used = {fg for fg, _ in theme.TEXT_PAIRS}
    assert text_like <= used


def test_f06_both_themes_define_the_same_names():
    assert theme.PALETTES[theme.DARK].keys() == theme.PALETTES[theme.LIGHT].keys()
    assert theme.DEFAULT_THEME == theme.DARK


@pytest.mark.parametrize("name", [theme.DARK, theme.LIGHT])
def test_stylesheet_only_uses_named_palette_colors(name):
    import re

    sheet = theme.stylesheet(name)
    colors = set(theme.palette(name).values())
    used = set(re.findall(r"#[0-9a-fA-F]{6}\b", sheet))
    assert used <= colors, used - colors  # keine Farbe ausserhalb der Palette
    assert theme.palette(name)["bg"] in sheet


@pytest.mark.parametrize("name", [theme.DARK, theme.LIGHT])
def test_font_is_the_system_font_with_fixed_size(name):
    sheet = theme.stylesheet(name)
    assert f"font-size: {theme.FONT_PT}pt" in sheet
    assert "font-family" not in sheet  # Schriftart bleibt die des Systems


def test_dark_theme_uses_the_colors_measured_in_the_obs_screenshot():
    p = theme.PALETTES[theme.DARK]
    assert (p["bg"], p["surface"], p["title_bg"], p["preview_bg"], p["canvas"], p["selection_bg"]) == (
        "#1d1f26", "#272a33", "#3c404d", "#13141a", "#000000", "#284cb8")
    assert theme.contrast_ratio(p["selection_text"], p["selection_bg"]) >= 7  # weisse Schrift auf kräftigem Blau


@pytest.mark.parametrize("name", [theme.DARK, theme.LIGHT])
def test_f68_graph_colors_have_contrast_3_to_the_graph_surface(name):
    p = theme.PALETTES[name]
    for fg, bg in theme.GRAPH_PAIRS:
        ratio = theme.contrast_ratio(p[fg], p[bg])
        assert ratio >= theme.MIN_GRAPH_CONTRAST, f"{name}: {fg} auf {bg} = {ratio:.2f}"
    assert {fg for fg, _ in theme.GRAPH_PAIRS} == {"perf_cpu", "perf_ram", "perf_lan"}
    assert len({p[fg] for fg, _ in theme.GRAPH_PAIRS}) == 3  # je Feld eine eigene Farbe


def test_f68_perf_colors_in_the_palette_of_both_themes():
    for name in (theme.DARK, theme.LIGHT):
        assert {"perf_cpu", "perf_ram", "perf_lan"} <= theme.PALETTES[name].keys()
