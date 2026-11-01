# P06e – Eigenschaften-Dock und Overlay-Einstellungen

Lies `CLAUDE.md` (Regel 15), `docs/01-funktionen.md` (F-80 bis F-84, F-11, F-65, F-66), `docs/02-architektur.md` (Abschnitt 3, 6, 8 Punkt 2), `docs/04-ui-design.md`, `docs/berichte/P06d.md`.

**Arbeitsweise:** wie P06d (betroffene Tests während der Arbeit, ganze Suite am Ende, keine Tests abschwächen, keine SVG-Symbole).

## Aufgaben

1. **Feld ist Regler (F-84).** Neues Bauteil `ScrubField` für die fünf Werte im Dock «Eigenschaften» (X, Y, Breite, Höhe, Drehung): ein Feld mit Balken als Füllung und Zahl rechts.
   - Ziehen ändert den Wert (grob), mit gehaltener Umschalttaste in Einerschritten (F-65); Klick ohne Ziehen öffnet die Eingabe zum Tippen (Enter/Tab übernimmt, Esc bricht ab); Pfeiltasten auf dem fokussierten Feld ±1, mit Umschalt ±10.
   - Bereiche: X und Y von −Breite (bzw. −Höhe) der Quelle bis Leinwandbreite (bzw. -höhe); Breite und Höhe von 1 bis Leinwand; Drehung −180° bis +180°, Balkenmitte bei 0°. Alle Werte ganze Pixel (Drehung wie bisher).
   - Ein Zug = ein Eintrag im Rückgängig-Verlauf. Rückgängig/Wiederholen wie bisher.
   - Daneben je Feld eine Reset-Schaltfläche (↺, ohne SVG gezeichnet): Drehung 0°, Breite und Höhe auf die ursprüngliche Grösse der Quelle (bei Bild: natürliche Grösse, ins Overlay eingepasst), X und Y zentriert im Overlay.
   - Das Bauteil ist für das Quellenfenster (P06f) wiederverwendbar (Bereich, Einheit, Standardwert als Parameter).
2. **Transformation kopieren und einfügen (F-80).** Schaltflächen «Kopieren» und «Einfügen» im Dock «Eigenschaften» (und Tasten Strg+Umschalt+C/V, wenn nichts anderes belegt ist). Übertragen alle fünf Werte, auch zwischen Quellenarten. Die Zwischenablage ist programmintern (nicht die des Systems). Einfügen ist ein Eintrag im Rückgängig-Verlauf. Ohne gewählte Quelle oder ohne kopierte Werte ist «Einfügen» ohne Wirkung mit Meldung in der Statuszeile.
3. **Sperren (F-81).** Schloss-Symbol neben dem Auge in «Quellen», Rechtsklick-Eintrag «Sperren/Entsperren», Tastenkürzel nach Muster der bestehenden. Neues Feld `locked` (Migration, Standard falsch), über die Schnittstelle des Kerns gespeichert. Gesperrt heisst: die fünf Felder grau und nicht änderbar (Balken bleibt sichtbar); Ziehen, Griffe, Pfeiltasten, Ausrichten, Einfügen und Rückgängig/Wiederholen verändern die Transformation nicht (Rückgängig überspringt oder verweigert mit Meldung, ohne den Verlauf zu beschädigen); in der Vorschau nicht wählbar (Klick trifft die Quelle darunter, kein Auswahlrahmen), in der Liste wählbar. Möglich bleiben: Name, Sichtbarkeit, Reihenfolge, Löschen (mit Rückfrage) und später das Quellenfenster. Duplizieren ergibt eine entsperrte Kopie. Auf die Ausgabe in OBS hat das Sperren keinen Einfluss. Die Kern-Schnittstelle selbst bleibt schreibbar (der Schutz ist ein Schutz der Oberfläche); sage das im Bericht.
4. **Ausgabe pro Overlay (F-82).** Im Dock «Steuerung» zwei Schalter «Browserquelle» (Standard an) und «NDI» (Standard aus, gesperrt mit «nicht verfügbar», solange F-36 fehlt). `output` wird zur Liste (Migration, `docs/02-architektur.md` Abschnitt 8 Punkt 2). Browserquelle aus: der Overlay-Server liefert die Seite und die WebSocket-Verbindung für dieses Overlay nicht aus (404, wie bei falschem Token, kein Hinweis auf Existenz); die Vorschau im Editor funktioniert weiter (eigener Vorschau-Zugang, prüfe, ob P06 ihn schon hat). Die Anzeige der URL im Dock zeigt bei «aus» einen Hinweis. Ein bereits laufender Browser in OBS verliert beim Ausschalten die Verbindung und zeigt nichts.
5. **Leinwandgrösse (F-83).** Im Dock «Steuerung»: Breite 1 bis 1920, Höhe 1 bis 1080 (zwei `ScrubField` oder Zahlenfelder), dazu Auswahl «1920 × 1080», «1280 × 720», «1080 × 1080», «1080 × 1920», «Benutzerdefiniert». Höchstwerte als **eine** Konstante im Code. Quellen bleiben unverändert (was ausserhalb liegt, wird in Vorschau und OBS abgeschnitten, in der Liste weiter wählbar). Zoom «Einpassen», Lineale, Hilfslinien und Einrasten folgen der neuen Grösse. Das Dock zeigt «In OBS Breite × Höhe der Browserquelle einstellen: …» mit «Kopieren». Prüfe gegen die OBS-Dokumentation (Quelle nennen, Regel 10), ob OBS die Grösse aus der Seite übernehmen kann; sonst nur der Hinweis. Rückgängig macht die Änderung rückgängig.

## Abnahme

- Tests mit Funktions-IDs: simulierte Maus (Ziehen, Klick, Umschalt), Tastatur, Bereiche, Reset-Werte, Kopieren/Einfügen (auch zwischen Text und Bild, gesperrt), Sperren (alle genannten Wege), Ausgabe aus/an (404 und Vorschau), Leinwandgrösse (Grenzen, Zoom, Rückgängig), Migrationen.
- Alle Tests in den Umgebungen von P08 grün, `ruff check`/`ruff format --check` ohne Befund, `tools/beenden_pruefung.sh` 5 von 5.
- Bericht `docs/berichte/P06e.md` mit «Auf dem Laptop prüfen».

## Nicht bauen

Quellenfenster, Rand, Schatten, «Einpassen» für Bilder (P06f), Mehrfachauswahl, NDI-Ausgabe selbst.
