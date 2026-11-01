"""Hilfen für Tests: kleine PNG-Dateien erzeugen und lesen (ohne Pillow), freie Ports, Warten auf Qt, Testszene."""

import socket
import struct
import time
import zlib

# Testszene der Pixeltests (Overlay-Seite in Chromium und Vorschau in QtWebEngine)
W, H = 1920, 1080
RED, GREEN = (255, 0, 0, 255), (0, 255, 0, 255)
TEXT_BOX = dict(x=100, y=50, width=400, height=80)
RED_BOX = dict(x=700, y=300, width=200, height=150)
GREEN_BOX = dict(x=500, y=500, width=200, height=100)  # 90° gedreht: 100 × 200 um (600, 550)


def free_port() -> int:
    """Freier TCP-Port auf 127.0.0.1."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_until(app, cond, timeout: float = 5.0) -> bool:
    """Verarbeitet Qt-Ereignisse, bis `cond()` wahr ist; False nach `timeout` Sekunden."""
    end = time.time() + timeout
    while time.time() < end:
        app.processEvents()
        if cond():
            return True
        time.sleep(0.01)
    return False


def pump(ms: int) -> None:
    """Verarbeitet Qt-Ereignisse während `ms` Millisekunden."""
    from PyQt6.QtWidgets import QApplication

    end = time.time() + ms / 1000
    while time.time() < end:
        QApplication.processEvents()
        time.sleep(0.01)


def _chunk(kind: bytes, data: bytes) -> bytes:
    body = kind + data
    return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))


def solid_png(width: int, height: int, rgba: tuple[int, int, int, int]) -> bytes:
    """Einfarbiges 8-Bit-RGBA-PNG."""
    row = b"\x00" + bytes(rgba) * width
    raw = row * height
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + _chunk(b"IDAT", zlib.compress(raw))
        + _chunk(b"IEND", b"")
    )


class Image:
    """Gelesenes RGBA-PNG (8 Bit, nicht verschachtelt), z. B. ein Playwright-Screenshot."""

    def __init__(self, data: bytes) -> None:
        assert data.startswith(b"\x89PNG\r\n\x1a\n")
        pos, idat = 8, b""
        while pos < len(data):
            (n,) = struct.unpack(">I", data[pos : pos + 4])
            kind, body = data[pos + 4 : pos + 8], data[pos + 8 : pos + 8 + n]
            if kind == b"IHDR":
                self.width, self.height, depth, ctype, _, _, interlace = struct.unpack(">IIBBBBB", body)
                assert (depth, ctype, interlace) == (8, 6, 0), "nur RGBA 8 Bit"
            elif kind == b"IDAT":
                idat += body
            pos += 12 + n
        raw, stride, bpp = zlib.decompress(idat), self.width * 4, 4
        rows: list[bytearray] = []
        prev = bytearray(stride)
        for y in range(self.height):
            ft, line = raw[y * (stride + 1)], bytearray(raw[y * (stride + 1) + 1 : (y + 1) * (stride + 1)])
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                b = prev[i]
                c = prev[i - bpp] if i >= bpp else 0
                if ft == 1:
                    line[i] = (line[i] + a) & 255
                elif ft == 2:
                    line[i] = (line[i] + b) & 255
                elif ft == 3:
                    line[i] = (line[i] + (a + b) // 2) & 255
                elif ft == 4:
                    p = a + b - c
                    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                    pr = a if pa <= pb and pa <= pc else (b if pb <= pc else c)
                    line[i] = (line[i] + pr) & 255
            rows.append(line)
            prev = line
        self._rows = rows

    def pixel(self, x: int, y: int) -> tuple[int, int, int, int]:
        r = self._rows[y]
        return tuple(r[x * 4 : x * 4 + 4])  # type: ignore[return-value]

    def opaque_bbox(self, x0=0, y0=0, x1=None, y1=None):
        """Kleinster Rahmen um alle nicht ganz durchsichtigen Pixel im Ausschnitt."""
        x1 = self.width if x1 is None else x1
        y1 = self.height if y1 is None else y1
        xs, ys = [], []
        for y in range(y0, y1):
            row = self._rows[y]
            for x in range(x0, x1):
                if row[x * 4 + 3]:
                    xs.append(x)
                    ys.append(y)
        return (min(xs), min(ys), max(xs), max(ys)) if xs else None


class RunningService:
    """Startet den Kern-Dienst in einem eigenen Thread (für Tests mit Browser oder Oberfläche)."""

    def __init__(self, paths, port: int, overlay_port: int) -> None:
        import asyncio
        import threading

        from donstv_studio.core.service import Service

        self.paths, self.port, self.overlay_port = paths, port, overlay_port
        self.svc = Service(paths, port=port, overlay_port=overlay_port)
        self.loop = None
        self._ready = threading.Event()
        self._asyncio = asyncio

        def runner():
            async def main():
                self.loop = asyncio.get_running_loop()
                task = asyncio.create_task(self.svc.run())
                await self.svc.started.wait()
                self._ready.set()
                await task

            asyncio.run(main())

        self.thread = threading.Thread(target=runner, daemon=True)

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def start(self) -> "RunningService":
        self.thread.start()
        assert self._ready.wait(20), "Dienst startet nicht"
        return self

    def stop(self) -> None:
        if self.loop is not None:
            self.loop.call_soon_threadsafe(self.svc.stop_event.set)
        self.thread.join(20)

    def run(self, coro_func, *args):
        """Führt eine Coroutine in der Schleife des Dienstes aus und wartet auf das Ergebnis."""
        fut = self._asyncio.run_coroutine_threadsafe(coro_func(*args), self.loop)
        return fut.result(10)


# Fenster mit QtWebEngine bleiben bis zum Ende der Testsitzung (P06c: Freigabe nach jedem Test stürzte in P06 ab);
# `tests/conftest.py` gibt sie in `pytest_sessionfinish` frei.
KEEP_UNTIL_SESSION_END: list = []


def dispose(app, *widgets) -> None:
    """Schliesst Test-Fenster und gibt sie sofort frei (P08, Testdauer).

    `deleteLater()` allein wirkt in Tests nicht: Ohne laufende Ereignisschleife verarbeitet Qt die verzögerte Löschung
    nicht, alle Fenster bleiben bis zum Ende der Sitzung bestehen, und jedes `QApplication.setStyleSheet` (beim Anlegen
    eines Hauptfensters) muss alle alten Widgets neu gestalten. `sendPostedEvents(None, DeferredDelete)` führt die
    Löschung aus (wie `preview_web.release_web_views`). Widgets mit einer QWebEngineView werden nur geschlossen und
    erst am Sitzungsende freigegeben.
    """
    from PyQt6.QtCore import QCoreApplication, QEvent

    try:
        from PyQt6.QtWebEngineWidgets import QWebEngineView
    except ImportError:
        QWebEngineView = None
    for w in widgets:
        w.close()
        if QWebEngineView is not None and (isinstance(w, QWebEngineView) or w.findChildren(QWebEngineView)):
            KEEP_UNTIL_SESSION_END.append(w)
        else:
            w.deleteLater()
    app.processEvents()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
