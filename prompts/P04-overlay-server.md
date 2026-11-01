# P04 – Overlay-Server und Browserquelle

Lies `CLAUDE.md`, `docs/02-architektur.md` (Abschnitte 1, 2, 6), `docs/03-hardware-netzwerk.md` (Abschnitt 2) und `docs/04-ui-design.md` (Abschnitt 5).

## Aufgabe (F-15, F-16, F-17, F-18, F-19, F-38)

1. **Overlay-Server** im Kern-Dienst, eigener Port (Vorgabe 8080 [ANNAHME], konfigurierbar), Adresse konfigurierbar. Standard: alle Schnittstellen des Heimnetzes. In der Konfiguration gibt es eine Zeile «nur lokal».
   - `GET /o/{overlay_id}?t={token}` liefert die Overlay-Seite. Falscher oder fehlender Token → 404 (kein Hinweis, ob das Overlay existiert).
   - `WS /o/{overlay_id}/ws?t={token}`: sendet beim Verbinden `snapshot` (vollständiger Zustand), danach `update` bei jedem Ereignis `overlay.changed`. Die Seite baut sich ohne Neuladen um (F-18).
   - Statische Dateien (Schrift, Bibliothek) nur unter `/static/` und `/media/{overlay_id}/...` mit Token.
2. **Overlay-Seite** (HTML, CSS, JavaScript in `src/donstv_studio/overlays/web/`):
   - Hintergrund transparent. Fläche genau `width × height` Pixel, keine Skalierung, kein Rand, keine Bildlaufleisten.
   - Quellen werden mit `position:absolute`, `left/top/width/height` in ganzen Pixeln und `transform: rotate()` um die Mitte gesetzt; Reihenfolge über `z`.
   - Quelle `text`: Inhalt, Farbe, Grösse, Schriftart, Stil (Comic, Comic dick, Schlicht, Ohne). Die Stile übernimmst du aus dem Repo https://github.com/donsimm/overlay-game-tool (`app/modules.py`, `web/overlays/`); lies die Dateien, übernimm nur Text und Stile, keine Spiele oder Server.
   - Quelle `image`: Bild aus einer Bibliothek (png, jpg, gif, webp, svg, webm), maximal 25 MB pro Datei, mehrfach verwendbar. Hoch­laden über die Schnittstelle des Kern-Dienstes; Typ und Grösse serverseitig prüfen, nicht nach der Dateiendung allein.
   - Schrift: Standard **Be Vietnam Pro**, lokal eingebunden, kein CDN. Lade die Schriftdateien aus der offiziellen Quelle (Google Fonts, SIL Open Font License), lege Lizenztext und Quelle in `src/donstv_studio/overlays/web/fonts/` ab. Ist das Netz gesperrt, schreibe das in den Bericht. Die Schrift pro Textquelle ist wählbar (F-38): Liste der installierten Systemschriften plus Standard. (Eigene Schriftdateien F-39 folgen später.)
   - Wiederverbinden der WebSocket-Verbindung mit wachsender Wartezeit; bei Verlust zeigt die Seite nichts Störendes an (OBS-Bild bleibt sauber).
3. **Browserquelle-URL**: Die Schnittstelle liefert für jedes Overlay die vollständige URL mit Adresse des Laptops (Heimnetz-IP oder Hostname, konfigurierbar) und Token.

## Abnahme

- Tests: Token-Prüfung (richtig, falsch, fehlend), Snapshot und Update über WebSocket, Datei-Prüfung beim Hochladen (zu gross, falscher Typ), Bibliothek mehrfach verwendbar.
- Eine Overlay-Seite mit Text- und Bildquelle wird in `chromium` (Playwright, falls vorhanden) bei 1920×1080 geöffnet; Screenshot zeigt Quellen auf den erwarteten Pixelpositionen (Test mit bekannten Koordinaten, Abweichung 0 Pixel).
- Eine Änderung per Schnittstelle erscheint im geöffneten Browser ohne Neuladen.

## Nicht bauen

Keine Oberfläche, keine Animationen (F-20), keine weiteren Quellenarten, kein NDI.
