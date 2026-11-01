# P06d – Editor: Fehler und Kleinkram

Lies `CLAUDE.md` (Regel 15: Zielumgebung Debian 13), `docs/01-funktionen.md` (F-74 bis F-78), `docs/04-ui-design.md`, `docs/berichte/P08.md`.

**Arbeitsweise:** Während der Arbeit nur die betroffenen Testdateien ausführen (die ganze Suite braucht über 12 Minuten). Am Ende einmal die ganze Suite in den drei Umgebungen aus P06c/P08 und `tools/beenden_pruefung.sh`. Keine Tests löschen oder abschwächen. Symbole und Pfeile **ohne Qt-SVG-Modul** zeichnen (auf dem Laptop fehlt es): mit `QPainter` auf `QPixmap` oder PNG, nicht SVG.

## Aufgaben

1. **Quellen umbenennen (F-74).** Rechtsklick «Umbenennen», Taste F2 und ein Feld «Name» oben im Dock «Eigenschaften». Der Name ist nur eine Bezeichnung. Prüfe zuerst, ob `Source` schon ein Feld für den Namen hat (`overlays/models.py`); wenn nein, Feld mit Vorgabe (heutiger automatischer Name) und Migration. Doppelklick in der Liste **nicht** zum Umbenennen verwenden (reserviert für F-79). Rückgängig/Wiederholen erfasst die Umbenennung. Leerer Name wird abgelehnt (Meldung in der Statuszeile).
2. **Zeigerposition (F-75).** «X: … Y: …» in Overlay-Pixeln links unten **in der Vorschaufläche**, von Qt über der Webansicht gezeichnet (nicht in der Overlay-Seite, die Ausgabe in OBS bleibt gleich). Lesbar auf hellem und dunklem Untergrund (halbtransparenter Grund), ausserhalb der Fläche «–». Aus der Statuszeile entfernen (nur an einer Stelle). Test: Position bei Zoom 25 %, 100 %, 400 %.
3. **Kontrast der Bedienelemente (F-76).** Häkchen von Kontrollkästchen (z. B. «Einrasten», «Vorschau verkleinern»), Pfeile von `QSpinBox`, `QComboBox` und Listen, Rahmen der Eingabefelder in **beiden Themes** (dunkel, hell). Farben als benannte Werte in `ui/theme.py`. Test: Kontrastverhältnis (WCAG 2.x) mindestens 3:1 gegen den Untergrund für diese Elemente, zusätzlich zum bestehenden Test für Text (4.5:1). Die Pfeile der Zahlenfelder müssen sichtbar sein; prüfe auch die Pfeile der Reihenfolge-Schaltflächen im Dock «Quellen». Bildschirmfoto (offscreen) beider Themes im Bericht beschreiben.
4. **Bildquellen (F-77).** Eckgriffe behalten das Seitenverhältnis der Quelle am Anfang des Ziehens, die Umschalttaste löst es; Seitengriffe sind frei. Beim Hinzufügen eines Bildes bekommt der Rahmen das Seitenverhältnis des Bildes (Grösse so, dass es ins Overlay passt, ganze Pixel). Gilt nur für Bildquellen; Textquellen unverändert. Mit Drehung prüfen (Verhältnis gilt im Koordinatensystem der Quelle). Hintergrund: Die Overlay-Seite setzt `object-fit: contain` (`overlays/web/overlay.css`), sonst kein Eingriff.
5. **Leistungsanzeige (F-78).** CPU, RAM und LAN im Fensterkopf gleich breit; die Breite ändert sich bei keinem Wert (längster möglicher Text, z. B. «15.5 / 15.5 GiB» und «↓ 999 ↑ 999 Mbit/s»). Test mit mehreren Werten: Breiten gleich, Kopf verschiebt sich nicht (wie bei P05b).
6. **Stylesheet nur bei Änderung (Vorschlag 2 aus P08, Abschnitt 6).** `MainWindow._apply_theme_style` setzt das Stylesheet nur, wenn es sich geändert hat. Grund: `setStyleSheet` gestaltet alle Widgets neu und war in P08 der Ort des sporadischen Absturzes. Messe in den Tests die Dauer vorher und nachher und nenne die Zahlen. Die Wahl desselben Designs ändert dann nichts mehr; das ist gewollt.
7. **README.** Abschnitt «Zweck»: Satz «Stand: Version 0.1, Projektgerüst. Es gibt noch keine Funktion …» durch den heutigen Stand ersetzen (Module, was läuft, Verweis auf `docs/05-prompt-plan.md`).

## Abnahme

- Neue Tests mit Funktions-IDs; alle Tests in den Umgebungen von P08 grün, `ruff check` und `ruff format --check` ohne Befund, `tools/beenden_pruefung.sh` 5 von 5.
- Bericht `docs/berichte/P06d.md` mit Abschnitt «Auf dem Laptop prüfen» (`tools/laptop_pruefung.sh`, danach von Hand: Häkchen und Pfeile erkennbar, Zeigerposition links unten, Quelle umbenennen, Bild skalieren, Kopf bleibt stabil).

## Nicht bauen

Regler im Feld, Reset, Kopieren/Einfügen, Sperren, Leinwandgrösse, Ausgabe-Schalter, Quellenfenster (alles P06e/P06f).
