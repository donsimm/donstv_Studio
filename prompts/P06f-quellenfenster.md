# P06f – Quellenfenster

Lies `CLAUDE.md` (Regel 15), `docs/01-funktionen.md` (F-79, F-67, F-70, F-38, F-15), `docs/04-ui-design.md`, `docs/referenz/` (Textstile), `docs/berichte/P04b.md` falls vorhanden, `docs/berichte/P06e.md`.

**Arbeitsweise:** wie P06d. Ein neues Fenster pro Quelle darf nicht zu Abstürzen führen: Regel 12, P08 Abschnitt 6 (sporadischer Absturz in `QApplication.setStyleSheet` beim Freigeben von Hauptfenstern). Das Quellenfenster ist ein `QDialog`/`QWidget` mit Eltern, nicht modal; gib es beim Schliessen und beim Löschen der Quelle geordnet frei und teste das wiederholt (mindestens 50-mal öffnen/schliessen in einem Test, auch mit Theme-Wechsel dazwischen).

## Aufgaben

1. **Öffnen (F-79).** Doppelklick auf eine Quelle in der Liste «Quellen» oder in der Vorschau öffnet das Quellenfenster dieser Quelle (in der Vorschau kollidiert Doppelklick nicht mit Ziehen; gesperrte Quellen sind dort nicht wählbar, also nur über die Liste). Nicht blockierend, das Fenster darf offen bleiben, während im Editor weitergearbeitet wird. Pro Quelle höchstens ein Fenster (erneut öffnen holt es nach vorn). Wird die Quelle gelöscht, schliesst das Fenster; wird eine andere Quelle gewählt, bleibt es bei der eigenen. Fenstergrösse und -lage werden gemerkt (Versionsmarke, Regel 12).
2. **Verhalten.** Änderungen wirken sofort in der Vorschau (über die bestehende Schnittstelle, nur `update`-Nachricht), kein «OK/Abbrechen». Jede Änderung ist ein Eintrag im Rückgängig-Verlauf des Editors (Strg+Z wirkt auch bei offenem Fenster). Reset je Feld auf den Standardwert (Bauteil `ScrubField` aus P06e für Zahlenwerte). Das Fenster bleibt auch bei gesperrten Quellen bedienbar (es betrifft die Transformation nicht).
3. **Textquelle.** Felder: Text (mehrzeilig), Schrift (Liste wie bisher, F-38; Be Vietnam Pro Standard), Grösse, Farbe, Stil (Comic, Comic dick, Schlicht, Ohne, wie P04b), **Gewicht** und **Ausrichtung** links/Mitte/rechts (F-67, bisher fest 800 und Mitte), **Rand** (Farbe, Breite) und **Schatten** (Farbe, Versatz X/Y, Unschärfe). Rand und Schatten kommen als neue Eigenschaften der Textquelle ins Datenmodell (Prüfung der Werte serverseitig, ganze Pixel, Grenzen nennen) und in die Overlay-Seite (`overlays/web/`), damit OBS genau wie die Vorschau zeichnet. Sie müssen mit den vorhandenen Stilen zusammenspielen (Stile aus P04b unverändert; Rand/Schatten gelten zusätzlich oder ersetzen den Stil-Effekt nur dort, wo sich beides beisst; beschreibe die gewählte Regel im Bericht). Vergleichstest wie in P06: Pixel-Differenz zwischen Vorschau und Chromium (Playwright, falls vorhanden).
4. **Bildquelle.** Bild wechseln (aus der Bibliothek), Anpassung «Einpassen» (Standard, heute `object-fit: contain`), «Füllen» (`cover`), «Strecken» (`fill`), «Original» (`none`), neues Feld mit Prüfung. Beim Wechsel der Anpassung bleibt der Rahmen unverändert.
5. **Aufbau.** Ein Fenster pro Quellenart mit gemeinsamem Rahmen (Titel «Quelle: <Name>», Gruppen mit Überschriften, gleiche Abstände und Schriften wie die Docks, beide Themes, Kontrast aus F-76). Neue Quellenarten fügen später nur ihr eigenes Formular hinzu (Register Art → Formular).

## Abnahme

- Tests mit Funktions-IDs: Öffnen (Liste, Vorschau, eins pro Quelle), Sofortwirkung, Rückgängig, Reset, Löschen schliesst, Wiederholtes Öffnen/Schliessen ohne Absturz, Datenprüfung für Rand/Schatten/Gewicht/Ausrichtung, Overlay-Seite zeichnet Rand/Schatten (Playwright oder, wenn nicht vorhanden, Prüfung des erzeugten CSS und Hinweis im Bericht).
- Alle Tests in den Umgebungen von P08 grün, `ruff` ohne Befund, `tools/beenden_pruefung.sh` 5 von 5.
- Bericht `docs/berichte/P06f.md` mit «Auf dem Laptop prüfen».

## Nicht bauen

Weitere Quellenarten (Chat-Box, Alert-Box …), eigene Schriftdateien (F-39), Animationen, Mehrfachauswahl.
