"""F-76: Häkchen, Pfeile und Rahmen der Bedienelemente in beiden Themes gut erkennbar (Kontrast mindestens 3:1).

Kontrast nach WCAG 2.x, 1.4.11 «Non-text Contrast»: https://www.w3.org/TR/WCAG21/#non-text-contrast
Die Symbole werden ohne Qt-SVG-Modul gezeichnet (PNG aus QPainter, ui/indicators.py).
"""

import re

import pytest

from donstv_studio.ui import theme


@pytest.mark.parametrize("name", [theme.DARK, theme.LIGHT])
def test_f76_controls_have_contrast_3_against_their_background(name):
    p = theme.PALETTES[name]
    for fg, bg in theme.CONTROL_PAIRS:
        ratio = theme.contrast_ratio(p[fg], p[bg])
        assert ratio >= theme.MIN_CONTROL_CONTRAST, f"{name}: {fg} auf {bg} = {ratio:.2f}"
    assert theme.MIN_CONTROL_CONTRAST == 3.0
    covered = {fg for fg, _ in theme.CONTROL_PAIRS}
    assert {"control_border", "arrow", "check_mark", "check_bg"} <= covered


@pytest.mark.parametrize("name", [theme.DARK, theme.LIGHT])
def test_f76_stylesheet_uses_named_control_colors_for_frames(name):
    c = theme.palette(name)
    sheet = theme.stylesheet(name)
    rule = re.search(
        r"QSpinBox, QDoubleSpinBox, QLineEdit, QComboBox \{\{?(.*?)\}", sheet, re.DOTALL
    )
    assert rule and f"border: 1px solid {c['control_border']}" in rule.group(1)
    assert f"QCheckBox::indicator {{ width: {theme.CHECK_BOX}px" in sheet
    assert "image: url(" not in sheet  # ohne Bilder: Qt zeichnet seine eigenen Symbole
    with_images = theme.stylesheet(name, {k: f"/x/{k}.png" for k in
                                         ("check", "up", "down", "up_disabled", "down_disabled")})  # fmt: skip
    assert "QCheckBox::indicator:checked { image: url(/x/check.png); }" in with_images
    assert "QComboBox::down-arrow { image: url(/x/down.png); }" in with_images
    assert ".svg" not in with_images


# --- mit Qt ----------------------------------------------------------------------------------------
qt = pytest.importorskip(
    "PyQt6.QtWidgets", exc_type=ImportError, reason="PyQt6 ist nicht installierbar oder lädt nicht"
)

from PyQt6.QtCore import QRect
from PyQt6.QtGui import QColor, QImage
from PyQt6.QtWidgets import QCheckBox, QComboBox, QSpinBox, QVBoxLayout, QWidget

from donstv_studio.ui import icons, indicators


def close_to(a: QColor, hex_color: str, tol: int = 40) -> bool:
    b = QColor(hex_color)
    return abs(a.red() - b.red()) + abs(a.green() - b.green()) + abs(a.blue() - b.blue()) <= tol


def count(img: QImage, rect: QRect, hex_color: str, tol: int = 40) -> int:
    n = 0
    for y in range(max(0, rect.top()), min(img.height(), rect.bottom() + 1)):
        for x in range(max(0, rect.left()), min(img.width(), rect.right() + 1)):
            if close_to(img.pixelColor(x, y), hex_color, tol):
                n += 1
    return n


@pytest.mark.parametrize("name", [theme.DARK, theme.LIGHT])
def test_f76_indicator_images_are_png_in_the_named_colors(app, name):
    paths = indicators.image_paths(name)
    assert set(paths) == {"check", "up", "down", "up_disabled", "down_disabled"}
    pal = theme.palette(name)
    for key, color in (("check", pal["check_mark"]), ("up", pal["arrow"]), ("down", pal["arrow"]),
                       ("up_disabled", pal["text_muted"])):  # fmt: skip
        assert paths[key].endswith(".png")
        img = QImage(paths[key])
        assert not img.isNull(), key
        big = QImage(paths[key].replace(".png", "@2x.png"))
        assert big.width() == 2 * img.width()
        opaque = [img.pixelColor(x, y) for y in range(img.height()) for x in range(img.width())
                  if img.pixelColor(x, y).alpha() == 255]  # fmt: skip
        assert opaque and all(close_to(c, color, 6) for c in opaque), key


def render_controls(app, name):
    host = QWidget()
    host.setObjectName("dockInner")
    host.setStyleSheet(theme.stylesheet(name, indicators.image_paths(name)))
    lay = QVBoxLayout(host)
    on, off = QCheckBox("Einrasten"), QCheckBox("Vorschau verkleinern")
    on.setChecked(True)
    spin = QSpinBox()
    spin.setRange(0, 100)
    combo = QComboBox()
    combo.addItems(["Browserquelle", "NDI"])
    for wdg in (on, off, spin, combo):
        lay.addWidget(wdg)
    host.resize(240, 160)
    host.show()
    app.processEvents()
    img = host.grab().toImage()
    return host, on, off, spin, combo, img


@pytest.mark.parametrize("name", [theme.DARK, theme.LIGHT])
def test_f76_check_mark_arrows_and_frames_are_drawn_visibly(app, name):
    pal = theme.palette(name)
    host, on, off, spin, combo, img = render_controls(app, name)
    try:
        # Häkchen: angekreuztes Kästchen in check_bg mit Häkchen in check_mark
        box = QRect(on.pos(), on.size()).adjusted(0, 0, -(on.width() - 24), 0)
        assert count(img, box, pal["check_bg"], 10) >= 20, "Kästchen nicht gefüllt"
        assert count(img, box, pal["check_mark"], 60) >= 6, "Häkchen fehlt"
        # nicht angekreuzt: Rahmen in control_border, kein Häkchen
        box_off = QRect(off.pos(), off.size()).adjusted(0, 0, -(off.width() - 24), 0)
        assert count(img, box_off, pal["control_border"], 10) >= 20
        assert count(img, box_off, pal["check_bg"], 10) == 0
        # Pfeile der Zahlenfelder: rechts im Feld, oben und unten
        right = QRect(spin.x() + spin.width() - theme.SPIN_BUTTON_WIDTH, spin.y(),
                      theme.SPIN_BUTTON_WIDTH, spin.height())  # fmt: skip
        upper = QRect(right.x(), right.y(), right.width(), right.height() // 2)
        lower = QRect(
            right.x(), right.y() + right.height() // 2, right.width(), right.height() // 2
        )
        assert count(img, upper, pal["arrow"], 60) >= 4, "Pfeil nach oben fehlt"
        assert count(img, lower, pal["arrow"], 60) >= 4, "Pfeil nach unten fehlt"
        # Pfeil der Auswahlliste
        drop = QRect(combo.x() + combo.width() - theme.COMBO_BUTTON_WIDTH, combo.y(),
                     theme.COMBO_BUTTON_WIDTH, combo.height())  # fmt: skip
        assert count(img, drop, pal["arrow"], 60) >= 4, "Pfeil der Auswahlliste fehlt"
        # Rahmen der Eingabefelder in control_border (oberste Zeile des Feldes)
        top = QRect(spin.x() + 2, spin.y(), spin.width() // 2, 1)
        assert count(img, top, pal["control_border"], 10) >= spin.width() // 2 - 2
    finally:
        host.close()
        host.deleteLater()


@pytest.mark.parametrize("name", [theme.DARK, theme.LIGHT])
def test_f76_order_arrows_of_the_sources_dock_are_visible(app, name):
    """Pfeile «nach vorn / nach hinten» (Dock «Quellen»): Textfarbe, ausgegraut Nebentext, je ≥ 3:1 zur Fläche."""
    pal = theme.palette(name)
    for kind in ("up", "down"):
        for color in (pal["text"], pal["text_muted"]):
            assert theme.contrast_ratio(color, pal["surface"]) >= theme.MIN_CONTROL_CONTRAST
            img = icons.draw_icon(kind, color).toImage()
            opaque = sum(1 for y in range(img.height()) for x in range(img.width())
                         if img.pixelColor(x, y).alpha() > 200)  # fmt: skip
            assert opaque >= 20, (kind, color)
