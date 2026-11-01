"""F-13, F-14, F-17, F-18, F-65: Vorschau mit echter Webansicht (QtWebEngine) gegen den echten Kern-Dienst.

Läuft QtWebEngine in der Umgebung nicht (Systembibliotheken, Chromium startet nicht), werden diese Tests mit
Begründung übersprungen (`pytest -rs` zeigt den Grund). Sie sind dann NICHT ausgeführt.

Enthält den Vergleichstest «Vorschau gegen Playwright-Chromium» (T-02 Vorstufe). Die endgültige Prüfung gegen OBS
macht der Nutzer.
"""

import json
import logging
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

pytest.importorskip("PyQt6.QtWidgets", exc_type=ImportError, reason="PyQt6 ist nicht installierbar oder lädt nicht")
pytest.importorskip(
    "PyQt6.QtWebEngineWidgets", exc_type=ImportError,
    reason="PyQt6-WebEngine ist nicht installiert oder lädt nicht (Debian: python3-pyqt6.qtwebengine; sonst pip install 'donstv_studio[ui]')",
)  # fmt: skip

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QImage
from PyQt6.QtWidgets import QApplication

from donstv_studio.core.config import Paths
from donstv_studio.ui import preview_web, theme
from donstv_studio.ui.backend import DirectRunner
from donstv_studio.ui.editor_model import EditorModel
from donstv_studio.ui.editor_prefs import EditorPrefs
from donstv_studio.ui.editor_view import EditorView
from editor_web_scene import RED_BOX, TEXT_BOX, CoreBackend, H, RunningService, W, build_scene
from helpers import Image

HERE = Path(__file__).parent


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def pump(ms: int) -> None:
    end = time.time() + ms / 1000
    while time.time() < end:
        QApplication.processEvents()
        time.sleep(0.01)


def js(web, code: str, timeout: float = 10.0):
    """Führt JavaScript in der Vorschau-Seite aus und wartet auf das Ergebnis."""
    box: list = []
    web.page().runJavaScript(code, 0, box.append)
    end = time.time() + timeout
    while not box and time.time() < end:
        QApplication.processEvents()
        time.sleep(0.005)
    assert box, f"JavaScript lieferte nichts: {code}"
    return box[0]


def wait_for(web, cond: str, timeout: float = 15.0) -> None:
    end = time.time() + timeout
    while time.time() < end:
        if js(web, f"!!({cond})", 5):
            return
        pump(50)
    raise AssertionError(f"Zeitüberschreitung: {cond}")


def wait_rendered(view) -> None:
    wait_for(view.web, "window.__overlay && window.__overlay.renders > 0")
    wait_for(view.web, "[...document.images].every(i => i.complete && i.naturalWidth > 0)")
    wait_for(view.web, "document.fonts.status === 'loaded'")
    pump(300)  # Zoom, Ausschnitt und Zeichnen


def dpr_failure_report(proc) -> str:
    """Vollständige Angaben, wenn der Unterprozess keine Ergebniszeile liefert (P06c, Laptop-Befund)."""
    code = proc.returncode
    if code < 0:
        art = f"Absturz durch Signal {-code}" + (" (Speicherzugriffsfehler, SIGSEGV)" if code == -11 else "")
    elif code == 139:
        art = "Absturz (139 = Speicherzugriffsfehler)"
    elif code == 0:
        art = "beendet ohne Ergebniszeile"
    else:
        art = "Fehler im Unterprozess"
    from PyQt6.QtCore import PYQT_VERSION_STR, QT_VERSION_STR

    return (
        f"Unterprozess lieferte keine Ergebniszeile. Exit-Code: {code} ({art}); "
        f"Qt {QT_VERSION_STR}, PyQt6 {PYQT_VERSION_STR}\n"
        f"--- stdout (vollständig, {len(proc.stdout)} Zeichen) ---\n{proc.stdout}\n"
        f"--- stderr (vollständig, {len(proc.stderr)} Zeichen) ---\n{proc.stderr}"
    )


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication(["donstv-tests"])


@pytest.fixture(scope="module")
def webengine(app):
    """Prüft einmal, ob QtWebEngine hier überhaupt Seiten laden kann; sonst werden alle Tests übersprungen."""
    from PyQt6.QtWebEngineWidgets import QWebEngineView

    v = QWebEngineView()
    done: list = []
    v.loadFinished.connect(done.append)
    v.setHtml("<html><body>ok</body></html>")
    v.show()
    end = time.time() + 30
    while not done and time.time() < end:
        QApplication.processEvents()
        time.sleep(0.01)
    v.close()
    if not done or done[0] is not True:
        pytest.skip("QtWebEngine kann in dieser Umgebung keine Seite laden (Chromium startet nicht)")


@pytest.fixture(scope="module")
def core(tmp_path_factory, webengine):
    paths = Paths.under(tmp_path_factory.mktemp("web"))
    svc = RunningService(paths, free_port(), free_port()).start()
    backend = CoreBackend(svc.base_url, paths.token_file)
    ids = build_scene(backend, svc.overlay_port)
    yield svc, backend, ids
    svc.stop()


@pytest.fixture
def editor(core, app):
    svc, backend, ids = core
    prefs = EditorPrefs()
    model = EditorModel(backend, DirectRunner(), None)
    model.load()
    model.select_overlay(ids["overlay"])
    view = EditorView(model, prefs)
    view.resize(2000, 1200)  # gross genug für 1920 × 1080 bei 100 % samt Rand und Linealen
    view.show()
    view.set_zoom(1.0)
    wait_rendered(view)
    yield view, model, prefs, ids, backend
    view.close()
    view.deleteLater()


def qimage_rows(img: QImage):
    """RGBA-Zeilen (bytes) eines Qt-Bildes; Qt liefert Format_RGBA8888 in Byte-Reihenfolge R, G, B, A."""
    img = img.convertToFormat(QImage.Format.Format_RGBA8888)
    w, h = img.width(), img.height()
    raw = bytes(img.constBits().asarray(img.sizeInBytes()))
    stride = img.bytesPerLine()
    return w, h, [raw[y * stride : y * stride + w * 4] for y in range(h)]


# --- Vorschau zeigt die Overlay-Seite ----------------------------------------------------------------
def test_f13_preview_loads_overlay_page_with_token_in_transparent_view(editor):
    view, model, prefs, ids, backend = editor
    assert view.web is not None and view.web.page().backgroundColor().alpha() == 0  # durchsichtig
    assert js(view.web, "location.pathname") == f"/o/{ids['overlay']}"
    assert js(view.web, "location.hostname") == "127.0.0.1"  # immer lokal, auch wenn «url» die Netzadresse nennt
    assert js(view.web, "new URLSearchParams(location.search).get('t')") == model.current()["token"]
    assert js(view.web, "document.querySelectorAll('[data-source-id]').length") == 3
    assert js(view.web, "[innerWidth, innerHeight]") == [W, H]  # 100 %: Seite 1920 × 1080 CSS-Pixel


def test_f65_zoom_100_percent_one_overlay_pixel_is_one_screen_pixel(editor):
    view, model, prefs, ids, backend = editor
    img = view.stage.grab().toImage()  # Karo (Qt) darunter, Webansicht darüber
    assert (img.width(), img.height()) == (W, H)
    x, y, w, h = (RED_BOX[k] for k in ("x", "y", "width", "height"))
    red = img.pixelColor
    assert red(x, y).name() == "#ff0000" and red(x + w - 1, y + h - 1).name() == "#ff0000"
    assert red(x - 1, y).name() != "#ff0000" and red(x, y - 1).name() != "#ff0000"  # Karo statt Rot
    assert red(x + w, y + h - 1).name() != "#ff0000"
    # Karo-Hintergrund scheint durch das durchsichtige Overlay
    a, b = theme.palette(theme.DEFAULT_THEME)["checker_a"], theme.palette(theme.DEFAULT_THEME)["checker_b"]
    assert {red(2, 2).name(), red(2 + 8, 2).name()} == {a, b}


def test_f13_selection_frame_is_drawn_by_qt_above_the_web_view(editor):
    view, model, prefs, ids, backend = editor
    model.select_source(ids["red"])
    pump(100)
    t = view.transform()
    img = view.viewport.grab().toImage()
    left, top = t.to_view(RED_BOX["x"], RED_BOX["y"])
    accent = theme.palette(theme.DEFAULT_THEME)["accent"]
    # Rahmen liegt über der roten Fläche der Webansicht
    assert img.pixelColor(round(left), round(top) + 40).name() == accent  # Rahmen: 2 Pixel, mittig auf der Kante
    assert img.pixelColor(round(left) + 30, round(top) + 40).name() == "#ff0000"  # innen weiter Rot
    # und nicht in der Seite selbst: kein zusätzliches Element im DOM
    assert js(view.web, "document.querySelectorAll('[data-source-id]').length") == 3
    assert js(view.web, "document.body.children.length") == 2  # #stage und <script>


def test_f65_zoom_200_percent_scrolled_shows_the_right_region(editor):
    view, model, prefs, ids, backend = editor
    view.resize(900, 700)
    view.set_zoom(2.0)
    pump(100)
    assert view.hbar.isVisible() and view.vbar.isVisible()
    k = view.transform().k
    assert k == 2.0
    # so verschieben, dass die rote Fläche in der Mitte der Ansicht liegt
    from donstv_studio.ui.editor_view import MARGIN

    cx, cy = RED_BOX["x"] + RED_BOX["width"] / 2, RED_BOX["y"] + RED_BOX["height"] / 2
    view.hbar.setValue(round(MARGIN + cx * k - view.viewport.width() / 2))
    view.vbar.setValue(round(MARGIN + cy * k - view.viewport.height() / 2))
    wait_for(view.web, "window.__ps && window.__ps.x > 0 && window.__ps.y > 0")
    pump(500)
    t = view.transform()
    vx, vy = t.to_view(RED_BOX["x"], RED_BOX["y"])
    assert 0 < vx < view.viewport.width() - 40 and 0 < vy < view.viewport.height() - 40  # Fläche ist sichtbar
    img = view.viewport.grab().toImage()
    red = lambda ox, oy: img.pixelColor(*[round(v) for v in t.to_view(ox, oy)]).name()
    # genau die Overlay-Pixel der Fläche sind rot (Bildschirm: 2 × 2 Pixel je Overlay-Pixel)
    assert red(RED_BOX["x"], RED_BOX["y"]) == "#ff0000"
    assert red(RED_BOX["x"] + RED_BOX["width"] - 1, RED_BOX["y"] + RED_BOX["height"] - 1) == "#ff0000"
    assert img.pixelColor(round(vx) - 1, round(vy) + 20).name() != "#ff0000"  # ein Bildschirmpixel links davon: nicht rot
    assert img.pixelColor(round(vx), round(vy) - 1).name() != "#ff0000"
    # Pixel unter dem Zeiger stimmt mit der Anzeige überein
    assert t.pixel_at(*t.to_view(RED_BOX["x"] + 10.5, RED_BOX["y"] + 10.5)) == (RED_BOX["x"] + 10, RED_BOX["y"] + 10)
    # Die Webansicht deckt nur den sichtbaren Teil ab (kein riesiger Puffer bei 200 %/400 %)
    assert view.web.width() <= view.viewport.width() + 4 and view.web.height() <= view.viewport.height() + 4


def test_f65_zoom_25_percent_below_chromium_minimum_uses_css_zoom(editor):
    view, model, prefs, ids, backend = editor
    view.dpr_override = 2.0  # k = 0,125: unter dem kleinsten Zoomfaktor von Chromium (0,25)
    view.set_zoom(0.25)
    pump(600)
    assert view.web.zoomFactor() == 0.25
    assert js(view.web, "window.__ps.css") == pytest.approx(0.5)
    assert js(view.web, "document.documentElement.style.zoom") == "0.5"
    view.dpr_override = None


# --- Änderungen ohne Neuladen (F-18) --------------------------------------------------------------------
def test_f18_edit_in_editor_updates_preview_without_reload(editor):
    view, model, prefs, ids, backend = editor
    js(view.web, "window.__marker = 777")
    before = js(view.web, "window.__overlay.renders")
    from donstv_studio.ui.geometry import Box

    model.change_box(ids["red"], Box(900, 310, 200, 150))  # DirectRunner: sofort zum Kern
    wait_for(view.web, f"document.querySelector('[data-source-id=\"{ids['red']}\"]').style.left === '900px'")
    assert js(view.web, "window.__marker") == 777  # kein Neuaufbau der Seite
    assert js(view.web, "performance.getEntriesByType('navigation').length") == 1
    assert js(view.web, "window.__overlay.renders") > before
    model.undo()
    wait_for(view.web, f"document.querySelector('[data-source-id=\"{ids['red']}\"]').style.left === '700px'")
    assert js(view.web, "window.__marker") == 777


# --- Bildrate und Navigation ---------------------------------------------------------------------------
def test_f13_preview_frame_rate_is_limited_by_setting(editor):
    view, model, prefs, ids, backend = editor
    count = (
        "window.__frames = undefined; (function () { let n = 0; const t0 = performance.now();"
        "(function f() { n++; if (performance.now() - t0 < 1500) requestAnimationFrame(f); else window.__frames = n; })(); })();"
    )

    def frames(fps: int) -> int:
        prefs.set_fps(fps)
        pump(100)
        js(view.web, count + " true")
        wait_for(view.web, "window.__frames !== undefined", 20)
        return js(view.web, "window.__frames")

    slow, fast = frames(5), frames(30)
    print(f"\nBildrate-Test: Bilder in 1,5 s bei Grenze 5/s: {slow}, bei Grenze 30/s: {fast}")
    assert slow <= 5 * 1.5 + 3  # in 1,5 s höchstens etwa 8 Bilder
    assert fast > slow


def test_f13_preview_page_cannot_navigate_away(editor):
    view, model, prefs, ids, backend = editor
    page = view.web.page()
    assert page.acceptNavigationRequest(QUrl("http://127.0.0.1:8080/o/x?t=y"), page.NavigationType.NavigationTypeTyped, True)
    assert not page.acceptNavigationRequest(QUrl("https://example.org/"), page.NavigationType.NavigationTypeLinkClicked, True)
    assert not page.acceptNavigationRequest(QUrl("http://192.168.1.5:8080/"), page.NavigationType.NavigationTypeTyped, True)


def test_preview_url_is_local_and_keeps_token():
    url = "http://192.168.1.50:8080/o/abc?t=a-b_c"
    assert preview_web.local_preview_url(url) == "http://127.0.0.1:8080/o/abc?t=a-b_c"
    assert preview_web.local_preview_url("http://[fe80::1]:9000/o/x?t=1") == "http://127.0.0.1:9000/o/x?t=1"
    assert preview_web.clamp_browser_zoom(0.125) == (0.25, 0.5)
    assert preview_web.clamp_browser_zoom(8.0) == (5.0, 1.6)
    assert preview_web.clamp_browser_zoom(1.0) == (1.0, 1.0)


def test_f13_token_does_not_reach_the_ui_log(core, app, caplog):
    svc, backend, ids = core
    caplog.set_level(logging.DEBUG)
    token = backend.list_overlays()[0]["token"]
    prefs = EditorPrefs()
    model = EditorModel(backend, DirectRunner(), None)
    model.load()
    model.select_overlay(ids["overlay"])
    view = EditorView(model, prefs)
    view.resize(900, 600)
    view.show()
    wait_rendered(view)
    view.web.page().runJavaScript(f"console.log('Adresse: ' + location.href + ' t=' + {json.dumps(token)})")
    pump(300)
    view.close()
    assert all(token not in r.getMessage() for r in caplog.records)
    assert any("Vorschau-Seite" in r.getMessage() for r in caplog.records)  # die Meldung kam an, ohne Token


# --- Vergleich mit Playwright-Chromium (T-02 Vorstufe) ----------------------------------------------------
def composite_over_black(img: Image):
    rows = []
    for r in img._rows:
        out = bytearray(len(r))
        for i in range(0, len(r), 4):
            a = r[i + 3]
            out[i] = r[i] * a // 255
            out[i + 1] = r[i + 1] * a // 255
            out[i + 2] = r[i + 2] * a // 255
            out[i + 3] = 255
        rows.append(bytes(out))
    return rows


def diff_stats(qt_rows, pw_rows, region=None, tol=8):
    x0, y0, x1, y1 = region or (0, 0, W, H)
    total = (x1 - x0) * (y1 - y0)
    differing = worst = 0
    for y in range(y0, y1):
        a, b = qt_rows[y][x0 * 4 : x1 * 4], pw_rows[y][x0 * 4 : x1 * 4]
        if a == b:
            continue
        for i in range(0, len(a), 4):
            if a[i : i + 4] != b[i : i + 4]:
                d = max(abs(a[i + c] - b[i + c]) for c in range(3))
                worst = max(worst, d)
                if d > tol:
                    differing += 1
    return differing, total, worst


@pytest.fixture(scope="module")
def pw_browser():
    sync_api = pytest.importorskip("playwright.sync_api", reason="Playwright (Python) ist nicht installiert")
    import shutil

    with sync_api.sync_playwright() as p:
        errors = []
        for kw in ({}, *({"executable_path": c} for c in (os.environ.get("DONSTV_CHROMIUM"), "/opt/pw-browsers/chromium",
                                                         shutil.which("chromium"), shutil.which("google-chrome")) if c and os.path.exists(c))):  # fmt: skip
            try:
                b = p.chromium.launch(args=["--no-sandbox"], **kw)
            except Exception as e:  # noqa: BLE001
                errors.append(str(e).splitlines()[0])
                continue
            yield b
            b.close()
            return
        pytest.skip("Playwright-Chromium nicht startbar: " + " | ".join(errors))


def test_t02_preview_vs_playwright_chromium_pixel_difference(editor, pw_browser, record_property):
    view, model, prefs, ids, backend = editor
    url = preview_web.local_preview_url(model.preview_url())
    view.stage.solid = "#000000"  # ohne Karo, damit gleich über Schwarz verglichen werden kann
    view.stage.update()
    pump(500)
    qw, qh, qt_rows = qimage_rows(view.stage.grab().toImage())
    assert (qw, qh) == (W, H)

    ctx = pw_browser.new_context(viewport={"width": W, "height": H}, device_scale_factor=1)
    page = ctx.new_page()
    page.goto(url)
    page.wait_for_function("window.__overlay && window.__overlay.renders > 0")
    page.wait_for_function("[...document.images].every(i => i.complete && i.naturalWidth > 0)")
    page.evaluate("document.fonts.ready.then(() => true)")
    pw = Image(page.screenshot(omit_background=True, full_page=False))
    ctx.close()
    pw_rows = composite_over_black(pw)

    # Bildflächen (rot, grün gedreht): exakt gleich, Abweichung 0
    red_region = (RED_BOX["x"] - 3, RED_BOX["y"] - 3, RED_BOX["x"] + RED_BOX["width"] + 3, RED_BOX["y"] + RED_BOX["height"] + 3)
    green_region = (545, 445, 655, 655)  # gedrehtes Grün: 100 × 200 um (600, 550), mit 5 Pixel Rand
    d_red = diff_stats(qt_rows, pw_rows, red_region, tol=0)
    d_green = diff_stats(qt_rows, pw_rows, green_region, tol=0)
    d_text = diff_stats(qt_rows, pw_rows, (TEXT_BOX["x"], TEXT_BOX["y"], TEXT_BOX["x"] + TEXT_BOX["width"], TEXT_BOX["y"] + TEXT_BOX["height"]), tol=8)
    d_all = diff_stats(qt_rows, pw_rows, None, tol=8)
    summary = {
        "rot_abweichende_pixel": d_red[0], "gruen_abweichende_pixel": d_green[0],
        "text_abweichende_pixel_ueber_8": d_text[0], "text_flaeche_pixel": d_text[1], "text_groesste_abweichung": d_text[2],
        "gesamt_abweichende_pixel_ueber_8": d_all[0], "gesamt_pixel": d_all[1], "gesamt_groesste_abweichung": d_all[2],
        "qt_webengine": __import__("PyQt6.QtCore", fromlist=["x"]).qVersion(),
    }  # fmt: skip
    print("\nT-02-Vorstufe:", json.dumps(summary, ensure_ascii=False))
    record_property("t02_vorschau_vs_playwright", json.dumps(summary, ensure_ascii=False))
    assert d_red[0] == 0 and d_green[0] == 0, summary  # Bildflächen und Ränder: Abweichung 0
    assert d_all[0] / d_all[1] < 0.005, summary  # höchstens 0,5 % der Pixel weichen um mehr als 8 Stufen ab


# --- devicePixelRatio 2 (eigener Prozess: Qt liest den Faktor beim Start) --------------------------------
def test_f65_dpr_2_zoom_100_is_still_one_overlay_pixel_per_screen_pixel(webengine, tmp_path):
    env = {**os.environ, "QT_SCALE_FACTOR": "2", "QT_QPA_PLATFORM": "offscreen"}
    # -X faulthandler: Bei einem Absturz (Exit-Code negativ, z. B. -11, oder 139 über eine Shell) steht die
    # Aufrufliste von Python in stderr. Der Unterprozess meldet seine Schritte in stderr («Schritt: …»).
    proc = subprocess.run(
        [sys.executable, "-X", "faulthandler", str(HERE / "editor_dpr_script.py"), str(tmp_path)],
        capture_output=True, text=True, timeout=180, env=env, cwd=str(HERE), check=False,
    )  # fmt: skip
    lines = [ln for ln in proc.stdout.splitlines() if ln.startswith("{")]
    assert lines, dpr_failure_report(proc)
    r = json.loads(lines[-1])
    print("\ndpr-2-Test:", r)
    assert r["dpr"] == 2.0
    assert r["k"] == 0.5 and r["web_zoom"] == 0.5
    assert r["stage_logical"] == [960, 540]  # 1920 × 1080 physische Pixel
    assert r["image_physical"] == [1920, 1080]
    assert r["red_inside"] == "#ff0000" and r["red_outside_left"] != "#ff0000" and r["red_outside_top"] != "#ff0000"
    assert r["red_right_last"] == "#ff0000" and r["red_right_next"] != "#ff0000"


def test_f65_dpr_failure_report_names_exit_code_and_full_output():
    """P06c: Bei leerer Ergebniszeile stehen Exit-Code und die vollständige Ausgabe in der Meldung."""
    long_err = "x" * 5000 + "ENDE"
    proc = subprocess.CompletedProcess([], -11, stdout="", stderr=long_err)
    text = dpr_failure_report(proc)
    assert "Exit-Code: -11" in text and "SIGSEGV" in text
    assert long_err in text  # nicht gekürzt
    assert "Exit-Code: 0 (beendet ohne Ergebniszeile)" in dpr_failure_report(
        subprocess.CompletedProcess([], 0, stdout="", stderr="")
    )


def test_f65_dpr_script_reports_exceptions_instead_of_silent_exit(webengine, tmp_path):
    """P06c: Eine Ausnahme im Unterprozess endet mit Exit-Code 1 und Aufrufliste, nicht still mit Exit-Code 0."""
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "DONSTV_DPR_SELFTEST_FAIL": "1"}
    proc = subprocess.run(
        [sys.executable, "-X", "faulthandler", str(HERE / "editor_dpr_script.py"), str(tmp_path)],
        capture_output=True, text=True, timeout=120, env=env, cwd=str(HERE), check=False,
    )  # fmt: skip
    assert proc.returncode == 1, dpr_failure_report(proc)
    assert "absichtlicher Fehler (Selbsttest)" in proc.stderr and "Traceback" in proc.stderr
    assert "Schritt: Kern-Dienst starten" in proc.stderr
