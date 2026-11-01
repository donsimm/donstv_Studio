"""F-15, F-16, F-17, F-18, F-19, F-65: Overlay-Seite in echtem Chromium (Playwright).

Wird übersprungen, wenn Playwright oder Chromium fehlen. Der Grund steht dann in der
Skip-Meldung (`pytest -rs` zeigt sie an).
"""

import asyncio
import os
import shutil
import threading
from pathlib import Path

import httpx
import pytest

from donstv_studio.core.config import Paths
from donstv_studio.core.service import Service
from helpers import GREEN, GREEN_BOX, RED, RED_BOX, TEXT_BOX, H, Image, W, free_port, solid_png

sync_api = pytest.importorskip(
    "playwright.sync_api", reason="Playwright (Python) ist nicht installiert"
)


def _chromium_candidates():
    yield {}  # Standard von Playwright
    for path in (os.environ.get("DONSTV_CHROMIUM"), "/opt/pw-browsers/chromium",
                 shutil.which("chromium"), shutil.which("chromium-browser"), shutil.which("google-chrome")):  # fmt: skip
        if path and os.path.exists(path):
            yield {"executable_path": path}


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as p:
        errors = []
        for kw in _chromium_candidates():
            try:
                b = p.chromium.launch(args=["--no-sandbox"], **kw)
            except Exception as e:  # noqa: BLE001
                errors.append(f"{kw or 'Standard'}: {str(e).splitlines()[0]}")
                continue
            yield b
            b.close()
            return
        pytest.skip("Chromium nicht startbar: " + " | ".join(errors))


@pytest.fixture(scope="module")
def stack(tmp_path_factory):
    paths = Paths.under(tmp_path_factory.mktemp("browser"))
    port, oport = free_port(), free_port()
    box: dict = {}
    ready = threading.Event()

    def runner():
        async def main():
            svc = Service(paths, port=port, overlay_port=oport)
            box["svc"], box["loop"] = svc, asyncio.get_running_loop()
            task = asyncio.create_task(svc.run())
            await svc.started.wait()
            ready.set()
            await task

        asyncio.run(main())

    t = threading.Thread(target=runner, daemon=True)
    t.start()
    assert ready.wait(20), "Dienst startet nicht"
    svc = box["svc"]
    api = httpx.Client(
        base_url=f"http://127.0.0.1:{port}", headers={"Authorization": f"Bearer {svc.token}"}
    )
    yield api, f"http://127.0.0.1:{oport}"
    api.close()
    box["loop"].call_soon_threadsafe(svc.stop_event.set)
    t.join(20)


@pytest.fixture
def scene(stack):
    """Overlay mit Text, rotem Bild und gedrehtem grünem Bild an bekannten Pixelpositionen."""
    api, base = stack

    def upload(rgba, w, h):
        r = api.post("/media", params={"filename": "t.png"}, content=solid_png(w, h, rgba))
        assert r.status_code == 201, r.text
        return r.json()["id"]

    o = api.post("/overlays", json={"name": "Browsertest"}).json()
    red, green = upload(RED, 200, 150), upload(GREEN, 200, 100)
    ids = {}
    for key, kind, box, extra in (
        (
            "text",
            "text",
            TEXT_BOX,
            {"props": {"text": "Hallo Welt", "size": 48, "color": "#ffffff", "style": "none"}},
        ),
        ("red", "image", RED_BOX, {"props": {"media_id": red}}),
        ("green", "image", GREEN_BOX, {"props": {"media_id": green}, "rotation": 90}),
    ):
        r = api.post(f"/overlays/{o['id']}/sources", json={"kind": kind, **box, **extra})
        assert r.status_code == 201, r.text
        ids[key] = r.json()["id"]
    page_url = f"{base}/o/{o['id']}?t={o['token']}"
    yield api, o, ids, page_url, base
    api.delete(f"/overlays/{o['id']}")


def open_page(browser, url):
    ctx = browser.new_context(viewport={"width": W, "height": H}, device_scale_factor=1)
    page = ctx.new_page()
    requests = []
    page.on("request", lambda r: requests.append(r.url))
    page.goto(url)
    page.wait_for_function("window.__overlay && window.__overlay.renders > 0")
    page.wait_for_function("[...document.images].every(i => i.complete && i.naturalWidth > 0)")
    page.evaluate("document.fonts.ready.then(() => true)")
    return ctx, page, requests


def shot(page) -> Image:
    return Image(page.screenshot(omit_background=True, full_page=False))


def test_f65_sources_at_expected_pixels_deviation_zero(browser, scene):
    api, o, ids, url, base = scene
    ctx, page, _ = open_page(browser, url)
    try:
        # DOM: genau die gespeicherten ganzen Pixel
        for key, box in (("text", TEXT_BOX), ("red", RED_BOX), ("green", GREEN_BOX)):
            r = page.evaluate(
                'id => { const e = document.querySelector(`[data-source-id="${id}"]`); '
                "return [e.offsetLeft, e.offsetTop, e.offsetWidth, e.offsetHeight]; }",
                ids[key],
            )
            assert r == [box["x"], box["y"], box["width"], box["height"]], key
        st = page.evaluate(
            "(() => { const s = document.getElementById('stage').getBoundingClientRect();"
            " return [s.left, s.top, s.width, s.height]; })()"
        )
        assert st == [0, 0, W, H]  # keine Skalierung, kein Rand
        assert page.evaluate(
            "[document.documentElement.scrollWidth, document.documentElement.scrollHeight,"
            " innerWidth, innerHeight]"
        ) == [W, H, W, H]  # keine Bildlaufleisten

        img = shot(page)
        assert (img.width, img.height) == (W, H)
        # Rotes Bild: Fläche exakt gefüllt, Rand exakt aussen durchsichtig
        x, y, w, h = (RED_BOX[k] for k in ("x", "y", "width", "height"))
        assert img.opaque_bbox(0, 250, W, H) is not None
        for yy in range(y, y + h):
            for xx in (x, x + w - 1):
                assert img.pixel(xx, yy) == RED
        for xx in range(x, x + w):
            for yy in (y, y + h - 1):
                assert img.pixel(xx, yy) == RED
        assert img.pixel(x + 100, y + 75) == RED
        for px in ((x - 1, y), (x, y - 1), (x + w, y), (x + w - 1, y + h), (x - 1, y + h - 1)):
            assert img.pixel(*px)[3] == 0, px
        # Gedrehtes grünes Bild (90° um die Mitte): 200×100 wird zu 100×200 um (600, 550)
        for px in ((550, 450), (649, 450), (550, 649), (649, 649), (600, 550)):
            assert img.pixel(*px) == GREEN, px
        for px in ((549, 550), (650, 550), (600, 449), (600, 650)):
            assert img.pixel(*px)[3] == 0, px
        # Text: nur innerhalb seines Rahmens, nichts links/oberhalb
        bbox = img.opaque_bbox(0, 0, W, 300)
        assert bbox is not None, "Text nicht gezeichnet"
        assert bbox[0] >= TEXT_BOX["x"] and bbox[1] >= TEXT_BOX["y"]
        assert (
            bbox[2] < TEXT_BOX["x"] + TEXT_BOX["width"]
            and bbox[3] < TEXT_BOX["y"] + TEXT_BOX["height"]
        )
    finally:
        ctx.close()


def test_f18_change_appears_without_reload(browser, scene):
    api, o, ids, url, base = scene
    ctx, page, _ = open_page(browser, url)
    try:
        page.evaluate("window.__marker = 12345")
        renders = page.evaluate("window.__overlay.renders")
        r = api.patch(f"/overlays/{o['id']}/sources/{ids['red']}", json={"x": 900, "y": 310})
        assert r.status_code == 200
        page.wait_for_function(
            "id => document.querySelector(`[data-source-id=\"${id}\"]`).style.left === '900px'",
            arg=ids["red"],
        )
        # Seite wurde nicht neu geladen: Marke da, genau eine Navigation, weitere Zeichnung
        assert page.evaluate("window.__marker") == 12345
        assert page.evaluate("performance.getEntriesByType('navigation').length") == 1
        assert page.evaluate("window.__overlay.renders") > renders
        img = shot(page)
        assert img.pixel(900, 310) == RED and img.pixel(700, 300)[3] == 0

        # Text ändern, ausblenden, Quelle löschen
        api.patch(
            f"/overlays/{o['id']}/sources/{ids['text']}",
            json={"props": {"text": "Neu", "size": 48}},
        )
        page.wait_for_function(
            "id => document.querySelector(`[data-source-id=\"${id}\"]`).textContent === 'Neu'",
            arg=ids["text"],
        )
        api.patch(f"/overlays/{o['id']}/sources/{ids['green']}", json={"visible": False})
        page.wait_for_function(
            "id => getComputedStyle(document.querySelector(`[data-source-id=\"${id}\"]`)).display === 'none'",
            arg=ids["green"],
        )
        api.delete(f"/overlays/{o['id']}/sources/{ids['green']}")
        page.wait_for_function(
            'id => !document.querySelector(`[data-source-id="${id}"]`)', arg=ids["green"]
        )
        # Auflösung
        api.patch(f"/overlays/{o['id']}", json={"width": 1280, "height": 720})
        page.wait_for_function("document.getElementById('stage').style.width === '1280px'")
        assert page.evaluate("window.__marker") == 12345
    finally:
        ctx.close()


def test_f18_reconnects_quietly_and_keeps_picture(browser, scene):
    api, o, ids, url, base = scene
    ctx, page, _ = open_page(browser, url)
    try:
        page.wait_for_function("window.__overlay.connected")
        page.evaluate("window.__overlay.socket.close()")
        page.wait_for_function("!window.__overlay.connected")
        assert (
            page.query_selector(f'[data-source-id="{ids["red"]}"]') is not None
        )  # Bild bleibt stehen
        page.wait_for_function("window.__overlay.connected", timeout=10_000)
        api.patch(f"/overlays/{o['id']}/sources/{ids['red']}", json={"x": 1000})
        page.wait_for_function(
            "id => document.querySelector(`[data-source-id=\"${id}\"]`).style.left === '1000px'",
            arg=ids["red"],
        )
    finally:
        ctx.close()


def test_f19_f38_f15_local_font_style_and_no_external_requests(browser, scene):
    api, o, ids, url, base = scene
    ctx, page, requests = open_page(browser, url)
    try:
        assert page.evaluate(
            "document.fonts.check('800 16px \"Be Vietnam Pro\"')"
        )  # Gewicht der Textquelle
        loaded = page.evaluate(
            "[...document.fonts].filter(f => f.status === 'loaded').map(f => f.family)"
        )
        assert any("Be Vietnam Pro" in f for f in loaded)
        css = lambda sid, prop: page.evaluate(
            '([id, p]) => getComputedStyle(document.querySelector(`[data-source-id="${id}"]`))[p]',
            [sid, prop],
        )
        assert "Be Vietnam Pro" in css(ids["text"], "fontFamily")  # Standard
        assert css(ids["text"], "fontSize") == "48px"
        assert css(ids["text"], "color") == "rgb(255, 255, 255)"
        # Stil und Schriftart pro Quelle (die Stile selbst: test_f15_text_styles_match_reference)
        api.patch(
            f"/overlays/{o['id']}/sources/{ids['text']}",
            json={
                "props": {"text": "X", "style": "comic", "font": "DejaVu Sans", "color": "#ff0000"}
            },
        )
        page.wait_for_function(
            "id => document.querySelector(`[data-source-id=\"${id}\"]`).classList.contains('txt-comic')",
            arg=ids["text"],
        )
        assert css(ids["text"], "fontFamily").startswith('"DejaVu Sans"')
        assert css(ids["text"], "color") == "rgb(255, 0, 0)"
        # Kein CDN: alle Anfragen gehen an den Overlay-Server selbst
        hosts = {r.split("/")[2] for r in requests if r.startswith("http")}
        assert hosts == {base.split("//")[1]}, hosts
    finally:
        ctx.close()


def test_f17_wrong_token_shows_nothing(browser, scene):
    api, o, ids, url, base = scene
    ctx = browser.new_context()
    page = ctx.new_page()
    try:
        resp = page.goto(f"{base}/o/{o['id']}?t=falsch")
        assert resp.status == 404
        assert page.evaluate("typeof window.__overlay") == "undefined"
    finally:
        ctx.close()


REFERENCE = Path(__file__).parent.parent / "docs" / "referenz" / "textstile-overlay-game-tool.css"


def test_f15_text_styles_match_reference(browser, scene):
    """Jeder Stil: text-shadow und filter entsprechen den Regeln der Referenzdatei."""
    api, o, ids, url, base = scene
    ctx, page, _ = open_page(browser, url)
    try:
        # Referenzwerte in einer getrennten, leeren Seite lesen. Würden die Originalregeln in die
        # Overlay-Seite eingefügt, überschrieben sie dort die Regeln aus overlay.css (Scheinvergleich).
        refpage = ctx.new_page()
        refpage.set_content(
            "<style>"
            + REFERENCE.read_text(encoding="utf-8")
            + "</style>"
            + "".join(
                f'<div id="ref-{k}" class="txt-{k}" style="font-size:48px">X</div>'
                for k in ("comic", "thick", "plain")
            )
        )
        refvals = {
            k: tuple(
                refpage.evaluate(
                    f"() => {{ const c = getComputedStyle(document.getElementById('ref-{k}')); return [c.textShadow, c.filter]; }}"
                )
            )
            for k in ("comic", "thick", "plain")
        }
        refpage.close()
        assert all(v[0] != "none" for v in refvals.values())
        sel = 'document.querySelector(`[data-source-id="${id}"]`)'
        cs = lambda target, prop: page.evaluate(
            f"([id, p]) => getComputedStyle({target})[p]", [ids["text"], prop]
        )
        seen = {}
        for style in ("comic", "thick", "plain", "none"):
            r = api.patch(
                f"/overlays/{o['id']}/sources/{ids['text']}",
                json={"props": {"text": "Aa", "size": 48, "style": style}},
            )
            assert r.status_code == 200, r.text
            page.wait_for_function(
                f"id => {sel}.classList.contains('txt-{style}')", arg=ids["text"]
            )
            shadow, flt = cs(sel, "textShadow"), cs(sel, "filter")
            if style == "none":
                assert (shadow, flt) == ("none", "none")
                continue
            assert (shadow, flt) == refvals[style], style
            assert shadow != "none"
            seen[style] = (shadow, flt)
        assert seen["plain"][1] == "none"  # «Schlicht» hat im Original keinen drop-shadow-Filter
        assert "drop-shadow" in seen["comic"][1] and "drop-shadow" in seen["thick"][1]
        assert len({v for v in seen.values()}) == 3  # drei verschiedene Stile
        # Ränder in em wachsen mit der Schriftgrösse in Pixeln (props.size)
        api.patch(
            f"/overlays/{o['id']}/sources/{ids['text']}",
            json={"props": {"text": "Aa", "size": 100, "style": "comic"}},
        )
        page.wait_for_function(f"id => {sel}.style.fontSize === '100px'", arg=ids["text"])
        assert cs(sel, "textShadow").startswith("rgb(0, 0, 0) 6.7px 0px 0px,")  # 0.067em × 100 px
        # Standardstil ohne Angabe: comic
        api.patch(
            f"/overlays/{o['id']}/sources/{ids['text']}", json={"props": {"text": "Aa", "size": 48}}
        )
        page.wait_for_function(f"id => {sel}.classList.contains('txt-comic')", arg=ids["text"])
    finally:
        ctx.close()


def test_f15_f19_text_base_rule_and_extrabold_really_loaded(browser, scene):
    """Textquelle ohne weitere Angaben: Gewicht 800, zentriert, Zeilenhöhe 1.15, echte Schriftdatei."""
    api, o, ids, url, base = scene
    ctx, page, requests = open_page(browser, url)
    try:
        r = api.post(
            f"/overlays/{o['id']}/sources",
            json={
                "kind": "text",
                "x": 0,
                "y": 700,
                "width": 600,
                "height": 200,
                "props": {"text": "Hallo"},
            },
        )
        assert r.status_code == 201
        sid = r.json()["id"]
        page.wait_for_function(
            "id => document.querySelector(`[data-source-id=\"${id}\"]`)?.textContent === 'Hallo'",
            arg=sid,
        )
        page.evaluate("document.fonts.ready.then(() => true)")
        css = lambda prop: page.evaluate(
            '([id, p]) => getComputedStyle(document.querySelector(`[data-source-id="${id}"]`))[p]',
            [sid, prop],
        )
        assert css("fontWeight") == "800"
        assert css("textAlign") == "center"
        assert css("lineHeight") == "55.2px"  # 1.15 × 48 px (Standardgrösse der Seite)
        assert css("fontFamily").startswith('"Be Vietnam Pro"')
        assert css("whiteSpace") == "pre-wrap"  # bewusste Abweichung vom Original (`pre`)
        # Echte Datei, kein Ersatz: Das FontFace mit Gewicht 800 ist geladen, die Datei wurde geholt.
        # (document.fonts.check allein genügt nicht: es meldet auch bei fehlender Schriftdefinition «wahr».)
        assert page.evaluate("document.fonts.check('800 48px \"Be Vietnam Pro\"', 'Hallo')")
        faces = page.evaluate("[...document.fonts].map(f => [f.family, f.weight, f.status])")
        assert ["Be Vietnam Pro", "800", "loaded"] in [[a.strip('"'), b, c] for a, b, c in faces], (
            faces
        )
        assert any(u.endswith("/static/fonts/BeVietnamPro-ExtraBold.ttf") for u in requests), (
            requests
        )
        # Sichtbar: Text ist mittig im Rahmen (Rahmen 0..600), nicht linksbündig
        img = shot(page)
        bbox = img.opaque_bbox(0, 700, 600, 900)
        assert bbox is not None
        assert abs((bbox[0] + bbox[2]) / 2 - 300) < 30, bbox
    finally:
        ctx.close()
