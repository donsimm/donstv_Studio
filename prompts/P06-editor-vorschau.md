# P06 – Editor und Vorschau

Lies `CLAUDE.md`, `docs/02-architektur.md` (Abschnitt 4), `docs/01-funktionen.md` (F-13, F-14, F-65) und `docs/04-ui-design.md`.

## Aufgabe (F-13, F-14, F-65)

Fülle die Docks «Overlays», «Quellen», «Eigenschaften», «Steuerung» und die Vorschaufläche.

1. **Docks Overlays und Quellen**: anlegen, umbenennen, duplizieren, löschen; Quellen hinzufügen (Text, Bild), entfernen, Reihenfolge ändern (Ziehen und Schaltflächen), ein-/ausblenden. Alles über die Schnittstelle des Kerns (P03).
2. **Vorschaufläche**: `QWebEngineView` lädt dieselbe Overlay-Seite wie die Browserquelle (P04), mit einem eigenen Vorschau-Zugang. Karo-Hintergrund hinter dem transparenten Overlay. Qt zeichnet Auswahlrahmen und Griffe **über** der Webansicht, nicht innerhalb der Overlay-Seite.
3. **Bedienung**: Quelle anklicken wählt sie; Ziehen verschiebt; Eckgriffe und Seitengriffe ändern die Grösse; Drehgriff dreht (Umschalttaste rastet in 15°-Schritten). Mehrfachauswahl nicht in diesem Baustein.
4. **Pixelgenau (F-65)**:
   - Alle Werte in ganzen Pixeln der Overlay-Auflösung; die Anzeige unter dem Zeiger nennt die Overlay-Pixelkoordinate.
   - Zoom: «Einpassen», 25 %, 50 %, 100 %, 200 %, 400 %; bei 100 % ist ein Overlay-Pixel genau ein Bildschirmpixel. Das Rendern der Vorschau muss auf `devicePixelRatio` achten (Test auf 1 und 2).
   - Pfeiltasten verschieben um 1 Pixel, mit Umschalttaste um 10.
   - Eigenschaften-Dock: Felder X, Y, Breite, Höhe, Drehung mit Zahleneingabe; Änderungen wirken sofort.
   - Lineale oben und links, Hilfslinien (aus dem Lineal ziehen, speichern pro Overlay), Einrasten an Hilfslinien, Rändern und Mitte des Overlays und an anderen Quellen (ein- und ausschaltbar), Raster mit einstellbarer Weite.
   - Ausrichten: links, Mitte, rechts, oben, Mitte, unten, bezogen auf das Overlay.
5. **Dock Steuerung**: Anzeige der Browserquelle-URL mit «Kopieren»; Auswahl der Ausgabeart «Browserquelle» oder «NDI» pro Overlay (NDI zeigt «nicht verfügbar», P03). Einstellung für die Vorschau: Bildrate (Standard 30) und «Vorschau verkleinern».
6. **Rückgängig/Wiederholen** für Lage- und Grössenänderungen und Eigenschaftenfelder (Strg+Z, Strg+Y).
7. **Leistung**: Die Vorschau muss auf schwacher Hardware benutzbar bleiben: Bildrate begrenzbar, kein Neuaufbau der ganzen Seite bei kleinen Änderungen (nur `update`-Nachricht, P04).

## Abnahme

- Tests (offscreen): Verschieben, Skalieren, Drehen per simulierter Maus ergibt die erwarteten ganzzahligen Werte; Pfeiltasten; Zoom 100 %: Zeigerkoordinate stimmt; Einrasten; Rückgängig.
- Vergleichstest (T-02 Vorstufe): Vorschau-Screenshot und Playwright-Chromium-Screenshot derselben Overlay-Seite bei 1920×1080, Pixel-Differenz wird berechnet und im Bericht genannt. Die endgültige Prüfung gegen OBS macht der Nutzer (T-02).
- Du startest die Oberfläche und prüfst Bedienung und Pixelgenauigkeit.

## Nicht bauen

Keine Animationen, keine weiteren Quellenarten, kein NDI, keine Mehrfachauswahl.
