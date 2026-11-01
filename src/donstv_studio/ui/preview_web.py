"""Webansicht der Vorschau (F-13): lädt dieselbe Overlay-Seite wie die Browserquelle in OBS (P04).

WICHTIG: Dieses Modul muss vor dem Anlegen der `QApplication` importiert werden (QtWebEngine verlangt das,
sonst lässt sich der OpenGL-Kontext nicht teilen). `donstv_studio.ui.main` und `tests/conftest.py` tun das.
https://doc.qt.io/qt-6/qtwebengine-overview.html  (Abschnitt «Using Qt WebEngine Widgets»)

Die Seite wird mit dem Token des Overlays geladen (Feld «url» der Schnittstelle, P04). Die Adresse enthält das Token
und wird deshalb nirgends protokolliert; Meldungen der Seite laufen durch `RedactFilter`.
"""

from __future__ import annotations

import logging
from urllib.parse import urlsplit, urlunsplit

from PyQt6.QtCore import QObject, Qt, QUrl, QUrlQuery
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QWidget

from donstv_studio.core.logging_setup import RedactFilter

log = logging.getLogger(__name__)
log.addFilter(RedactFilter())  # auch wenn jemand Meldungen mit Token durchreicht

try:
    from PyQt6.QtWebEngineCore import (
        QWebEnginePage,
        QWebEngineProfile,
        QWebEngineScript,
        QWebEngineSettings,
    )
    from PyQt6.QtWebEngineWidgets import QWebEngineView

    HAS_WEBENGINE = True
    WEBENGINE_ERROR = ""
except ImportError as e:  # pragma: no cover - hängt von der Installation ab
    HAS_WEBENGINE = False
    WEBENGINE_ERROR = str(e)

LOCAL_HOST = "127.0.0.1"
DEFAULT_FPS = 30
MIN_FPS, MAX_FPS = 1, 60
BROWSER_ZOOM_MIN, BROWSER_ZOOM_MAX = 0.25, 5.0  # Bereich von QWebEngineView.setZoomFactor (Qt-Dokumentation)

# Wird beim Laden in die Seite eingefügt (nur Vorschau, nicht die Browserquelle):
# - Bildrate: `requestAnimationFrame` wird auf höchstens `fps` Aufrufe je Sekunde begrenzt.
# - Ausschnitt: Die Webansicht zeigt nur den sichtbaren Teil des Overlays; `__ps` ist der Versatz in Overlay-Pixeln.
# - Zoom unter 25 %: Chromium zoomt höchstens bis 0,25; der Rest kommt über CSS `zoom` am Wurzelelement.
PREVIEW_SCRIPT = r"""
(function () {
  "use strict";
  var fps = 30, last = 0;
  var raf = window.requestAnimationFrame.bind(window);
  window.requestAnimationFrame = function (cb) {
    return raf(function step(t) {
      if (t - last >= 1000 / fps - 2) { last = t; cb(t); } else { raf(step); }
    });
  };
  window.__ps = { x: 0, y: 0, css: 1 };
  function apply() {
    document.documentElement.style.zoom = window.__ps.css === 1 ? "" : String(window.__ps.css);
    window.scrollTo(window.__ps.x, window.__ps.y);
  }
  window.__previewSet = function (x, y, css, rate) {
    window.__ps = { x: x, y: y, css: css };
    if (rate) { fps = Math.max(1, rate); }
    apply();
  };
  // Der Aufbau der Seite ändert Breite und Höhe von <body>; dann den Ausschnitt erneut setzen.
  document.addEventListener("DOMContentLoaded", function () {
    new MutationObserver(apply).observe(document.body, { attributes: true, attributeFilter: ["style"] });
  });
})();
"""


def local_preview_url(url: str) -> str:
    """Adresse für die Vorschau: gleicher Pfad und gleiches Token, aber immer über die lokale Adresse.

    [ANNAHME] Der Overlay-Server lauscht auf 0.0.0.0 oder 127.0.0.1 (Standard, `overlay.host`); beides ist über
    127.0.0.1 erreichbar, auch wenn das Netzkabel steckt oder nicht.
    """
    parts = urlsplit(url)
    port = f":{parts.port}" if parts.port else ""
    return urlunsplit((parts.scheme or "http", f"{LOCAL_HOST}{port}", parts.path, parts.query, ""))


def clamp_browser_zoom(k: float) -> tuple[float, float]:
    """Zerlegt den gewünschten Zoom in (Zoomfaktor der Webansicht, CSS-Rest)."""
    f = min(max(k, BROWSER_ZOOM_MIN), BROWSER_ZOOM_MAX)
    return f, k / f


if HAS_WEBENGINE:

    class PreviewPage(QWebEnginePage):
        """Seite der Vorschau: durchsichtig, bleibt auf dem lokalen Overlay-Server, schreibt keine Token ins Protokoll."""

        def __init__(self, profile: QWebEngineProfile, parent: QObject | None = None) -> None:
            super().__init__(profile, parent)
            self.setBackgroundColor(QColor(0, 0, 0, 0))

        def _token(self) -> str:
            return QUrlQuery(self.url()).queryItemValue("t")

        def javaScriptConsoleMessage(self, level, message: str, line: int, source: str) -> None:
            token = self._token()
            if token:  # das genaue Token überall schwärzen, in welcher Form es auch ausgegeben wird
                message = message.replace(token, "***")
            log.debug("Vorschau-Seite (Zeile %d): %s", line, message)

        def acceptNavigationRequest(self, url: QUrl, nav_type, is_main_frame: bool) -> bool:
            # Nur die lokale Overlay-Seite; kein Verlassen der Seite (Links, Weiterleitungen).
            return url.scheme() in ("about", "data") or url.host() == LOCAL_HOST

    class WebPreview(QWebEngineView):
        """Webansicht ohne Mausbedienung; die Qt-Ebene darüber nimmt Maus und Tastatur."""

        def __init__(self, parent: QWidget | None = None) -> None:
            super().__init__(parent)
            # Profil ohne Namen: nichts wird auf die Platte geschrieben. Es darf erst nach der Seite verschwinden
            # («Release of profile requested but WebEnginePage still not deleted»), darum ohne Eltern.
            self.profile_ = QWebEngineProfile()
            self.page_ = PreviewPage(self.profile_, self)
            self.page_.destroyed.connect(self.profile_.deleteLater)
            self.setPage(self.page_)
            s = self.page_.settings()
            for attr in (
                QWebEngineSettings.WebAttribute.LocalStorageEnabled,
                QWebEngineSettings.WebAttribute.PluginsEnabled,
                QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows,
                QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard,
                QWebEngineSettings.WebAttribute.ScrollAnimatorEnabled,
            ):
                s.setAttribute(attr, False)
            s.setAttribute(QWebEngineSettings.WebAttribute.ShowScrollBars, False)
            self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            script = QWebEngineScript()
            script.setName("donstv-preview")
            script.setSourceCode(PREVIEW_SCRIPT)
            script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
            script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
            script.setRunsOnSubFrames(False)
            self.page_.scripts().insert(script)
            self._fps = DEFAULT_FPS
            self._state: tuple[float, float, float] = (0.0, 0.0, 1.0)
            self.page_.loadFinished.connect(lambda _ok: self._push())

        def load_overlay(self, url: str) -> None:
            self.setUrl(QUrl(local_preview_url(url)))  # nicht protokollieren: enthält das Token

        def clear(self) -> None:
            self.setUrl(QUrl("about:blank"))

        def set_fps(self, fps: int) -> None:
            self._fps = max(MIN_FPS, min(MAX_FPS, int(fps)))
            self._push()

        def set_view(self, scroll_x: float, scroll_y: float, k: float) -> None:
            """Zoom und Ausschnitt: k = logische Pixel je Overlay-Pixel, scroll_* = linke obere Ecke in Overlay-Pixeln."""
            factor, css = clamp_browser_zoom(k)
            if abs(self.zoomFactor() - factor) > 1e-9:
                self.setZoomFactor(factor)
            self._state = (scroll_x, scroll_y, css)
            self._push()

        def _push(self) -> None:
            x, y, css = self._state
            self.page_.runJavaScript(
                f"window.__previewSet && window.__previewSet({x!r}, {y!r}, {css!r}, {self._fps});"
            )

else:  # pragma: no cover - ohne QtWebEngine bleibt die Vorschau leer, der Editor funktioniert trotzdem
    WebPreview = None  # type: ignore[assignment,misc]
