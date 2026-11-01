# P06d3 – Absturz beim Laden der Daten beheben (Fortsetzung von P06d2)

Lies `CLAUDE.md` (Regeln 12, 15, 16), `docs/befunde/absturz-p06d.md` **einschliesslich «Nachtrag 2026-11-01»**, `docs/berichte/P06d2.md`.

**Lage:** P06d2 hat den Absturz auf dem Laptop **nicht** behoben. Handtest mit echten Daten: Exit-Code 139 (3 von 3 Läufen, mit und ohne `QT_QPA_PLATFORM=xcb`, auch mit allen fünf `DONSTV_OFF`-Schaltern). Die Startprüfung aus P06d2 war grün, weil sie mit **leerem Kern** startet. Python-Aufrufliste beim Absturz: `OverlaysDock.refresh` → `_ListWithHint.sync` → `setCurrentWidget` (`editor_docks.py` Zeilen 169 und 226), ausgelöst von `EditorModel._loaded` aus `backend._drain`, also beim ersten Laden der Overlay-Liste. Der Code von `sync` ist seit P06 unverändert; die Ursache liegt in einem Zustand, den P06d davor erzeugt.

## Aufgaben

1. **Startprüfung mit Daten.** Neue Variante `daten` in `tools/start_pruefung.py`: Vor dem Start legt das Werkzeug im leeren Kern über die lokale API (nicht über die Oberfläche) mindestens 3 Overlays an, davon eines mit 6 Quellen (Text, Bild; ein Bild mit Seitenverhältnis ungleich der Fläche; eine gesperrte Quelle nur, wenn es das Datenmodell schon gibt) und eine gespeicherte Fensterlage wie in `standard`. Dazu `daten_schmal` (Daten plus schmale Fensterlage). Ausgabe wie bei den anderen Varianten. `tools/laptop_pruefung.sh` führt `daten` und `daten_schmal` in `kurz` (je 5 Läufe) und im vollen Lauf (je 20 Läufe) aus. **Prüfe zuerst in deinem Container (Xvfb), ob `daten` den Absturz bereits dort zeigt.** Wenn ja: das ist der Reproduzierer; arbeite damit. Wenn nein: sag das klar im Bericht und arbeite über die Laptop-Läufe (Aufgabe 3).
2. **Absturz selbst erfassen.** Bei Exit-Code 139 gibt die Startprüfung die vollständige Python-Aufrufliste von `faulthandler` aus (nicht nur 15 Zeilen) und schreibt sie nach `startpruefung-absturz-<variante>-<lauf>.txt`. Optional (nur wenn `gdb` vorhanden): C++-Aufrufliste aus dem Core.
3. **Eingrenzen nach Daten und Teilen.** Neue Diagnose-Schalter in `ui/diagnose.py` zusätzlich zu den alten (`DONSTV_OFF`), für die übrigen P06d-Teile, jeweils Stand P08 für diesen Teil: `editor_view_changes` (alles Neue in `editor_view.py`), `editor_model_changes`, `geometry_changes`, `theme_changes`, `indicators_changes` und `docks_changes`. Wo ein Schalter nicht sauber trennbar ist, sag es. Dann ist `tools/start_pruefung.py --variante daten,aus=…` die Messung für den Nutzer. Dazu je ein Lauf-Satz mit leerer Liste, nur Overlays ohne Quellen, mit Quellen (damit klar ist, ab wann der Absturz auftritt).
4. **Ursache im Code.** Lies `git diff 6dc8f44..54f6696 -- src/donstv_studio/ui` nochmals, jetzt mit der Frage: Was geschieht in `OverlaysDock.refresh`, `_sync_current`, `EditorModel._loaded` und im Aufbau der Dock-Inhalte (Quellenliste, Eigenschaften), wenn die erste Datenantwort eintrifft? Achte auf: Widgets, die gelöscht (`deleteLater`, `setParent(None)`, `clear()` auf Liste) und danach noch von einem Layout oder Signal erreicht werden; Rückrufe (Lambdas, Signale), die auf freigegebene Python- oder C++-Objekte zeigen; neue Verbindungen mit `Qt.QueuedConnection`; Aufrufe aus dem Hintergrund-Thread an Widgets; Wiedereintritt. Belege je Hypothese (Regel 9: nicht raten; belegt / widerlegt / nicht geprüft).
5. **Behebung** erst, wenn die Ursache durch Messung (Aufgabe 1 oder 3) eingegrenzt ist; sonst nur Werkzeug und Bericht liefern. Verhalten F-74 bis F-78 bleibt, Tests nicht abschwächen. Neue Tests: Oberfläche mit gefüllter Liste und Quellen starten und die Hauptschleife einige hundert Millisekunden laufen lassen (unter `xcb`/Xvfb, falls verfügbar).
6. **Regel 16 gilt ab jetzt mit Daten** (steht bereits in `CLAUDE.md`).

## Abnahme

- Tests in den drei Umgebungen grün, `ruff` ohne Befund.
- Bericht `docs/berichte/P06d3.md` nach Regeln 11, 13, 14 mit: Reproduktion in deinem Container (ja/nein), Hypothesenbewertung, Änderungen, ehrlicher Satz, dass die Wirkung auf dem Laptop noch nicht gemessen ist, und «Auf dem Laptop prüfen»: `tools/laptop_pruefung.sh kurz` (ohne `daten` ist das nicht aussagekräftig), danach Handtest mit echten Daten dreimal.

## Nicht bauen

Keine neuen Funktionen. P06e und P06f folgen erst, wenn Start und Handtest auf dem Laptop stabil sind.
