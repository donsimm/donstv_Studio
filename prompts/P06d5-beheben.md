# P06d5 – Absturz beheben: Lage und Anordnung nur einmal, in fester Reihenfolge

Lies `CLAUDE.md` (Regeln 9, 12, 15, 16), `docs/befunde/absturz-p06d.md` **mit allen Nachträgen, besonders «Nachtrag 2026-11-02 (2)»**, `docs/berichte/P06d4.md` (Abschnitt 6, Lesarten A bis D).

**Lage:** Der Absturz tritt nur auf, wenn eine **maximierte Fensterlage und** eine **Dock-Anordnung** gespeichert sind (je eines allein: 5 von 5 in Ordnung). Die Quellen sind nicht nötig. `window_stylesheet` allein hilft, mit einem zweiten Teil stürzt es wieder in 2 von 5 Läufen: der Absturz hängt am Zeitpunkt, nicht am Stylesheet. Beide Wege der C++-Aufrufliste enden in `QLayoutPrivate::doResize()` mit einem ungültigen Zeiger (Lesart C: aufgeschobenes `restoredState` in `QMainWindowLayout` bei maximiertem Fenster, Qt 6.8.2). **Das ist noch nicht bewiesen.** Dieser Auftrag behebt trotzdem, weil jede Massnahme unten ohnehin richtig ist und die Messung zeigt, welche nötig war.

## Aufgaben

1. **Massnahmen als Schalter, standardmässig EIN.** Jede Massnahme ist in `ui/diagnose.py` benannt und lässt sich mit `DONSTV_OFF=<name>` zurück auf den Stand P06d4 schalten (Markierung `# FIX (P06d5)`). So misst `fein` später, welche nötig ist.
   - `fix_state_once`: `restoreState` und `restoreGeometry` nur anwenden, wenn die Bytes sich vom zuletzt angewendeten Stand unterscheiden (wie schon bei der Geometrie, `_applied_geometry`). Beim zweiten `apply_settings` (über `settings_loaded`, sichtbares Fenster) wird nichts wiederhergestellt, was schon angewendet ist. Beachte: `_overlay_dock_state` und das Modul-Umschalten (MW Z. 549 bis 550) bleiben wie sie sind.
   - `fix_restore_after_show`: Ist die gespeicherte Lage maximiert (oder Vollbild), wird die Dock-Anordnung **nicht** am verborgenen Fenster wiederhergestellt, sondern einmal nach `show()` und nachdem das Fenster seine Endgrösse hat, **nicht in einem Ereignis-Handler**, sondern über `QTimer.singleShot(0, …)` (Regel 16). Nicht maximiert: wie bisher.
   - `fix_list_after_restore`: `OverlaysDock.refresh` / `_ListWithHint.sync` ändern die Seite des `QStackedWidget` erst, wenn Lage und Anordnung wiederhergestellt sind. Bis dahin merkt sich der Dock nur die Daten (Sicherung gegen Weg 2). Ein Flag am Hauptfenster (`layout_restored`), das nach dem Wiederherstellen (oder wenn es nichts wiederherzustellen gibt) gesetzt wird.
   - Optional **eine** weitere Massnahme, falls du aus dem Qt-Quelltext 6.8.2 (`qmainwindowlayout.cpp`, Zeilen 2274 bis 2343 und 3244 bis 3275, https://raw.githubusercontent.com/qt/qtbase/v6.8.2/src/widgets/widgets/qmainwindowlayout.cpp) eine begründete Möglichkeit siehst, das aufgeschobene `restoredState` sicher zu verbrauchen. Nenne Zeilen und Grund im Bericht. Keine Raterei: ohne Beleg weglassen.
   - Die Diagnose-Schalter `window_stylesheet`, `window_minwidth`, `window_geometry` bleiben **unverändert** (Standard: P06d-Form, Schalter ergibt P08-Form).
2. **Nachstellen im Container versuchen.** Neue Variante `daten_laptop` in `tools/start_pruefung.py`: Xvfb 1920 × 1080 (mit `openbox`), Fensterlage maximiert (normal 1918 × 1011 bei y 69, wie auf dem Laptop), Dock-Anordnung **ohne Reiterpaare** (die vier Docks nebeneinander oder untereinander, keine Gruppen), 2 Overlays mit 3 Quellen, Theme `dark`. Prüfe, ob der Absturz **ohne** die Massnahmen (alle drei `aus=`) damit auftritt. Tritt er auf: Das ist der Reproduzierer, miss damit Massnahme für Massnahme. Tritt er nicht auf: im Bericht sagen, was du probiert hast (Anordnungen, Fenstermanager, Bildschirmgrösse), und mit Aufgabe 3 weitermachen.
3. **`tools/laptop_pruefung.sh beheben`:** je 20 Läufe `kopie`; je 10 Läufe `kopie,aus=fix_state_once`, `kopie,aus=fix_restore_after_show`, `kopie,aus=fix_list_after_restore`, `kopie,aus=fix_state_once fix_restore_after_show fix_list_after_restore` (alle Massnahmen aus = Stand P06d4, muss wieder abstürzen: Gegenprobe), danach 10 Läufe `daten` und 10 Läufe `kopie_ohne_quellen`. Zusammenfassung und Sammeldatei wie bei `fein`.
4. **Handtest-Vorbereitung:** In `laptop_pruefung.sh beheben` am Ende: Hinweis, dass der Nutzer die Oberfläche mit seinen echten Daten **dreimal von Hand** startet und beendet (Exit-Code 0, `echo $?`), plus der Befehl dafür.
5. **Tests:** Tests in den drei Umgebungen grün, `ruff` ohne Befund; neue Tests je Massnahme (misst: `restoreState` wird beim zweiten `apply_settings` mit denselben Bytes nicht erneut aufgerufen; bei maximierter Lage kein `restoreState` vor `show()`; Liste ändert die Seite erst nach `layout_restored`; jede Massnahme hat ihren Schalter, der den alten Stand herstellt). Kein bestehender Test wird abgeschwächt. Beim Zurückfallen ohne Datenänderung bleibt das Verhalten der Oberfläche gleich (Speichern und Wiederherstellen in beiden Modulen «Overlays» und «Chat-Bot» prüfen).

## Abnahme

- Container: alle Tests grün; Startprüfung `daten`, `daten_maximiert`, `daten_laptop` mit allen Massnahmen 20 von 20.
- Bericht `docs/berichte/P06d5.md` nach den Regeln 11, 13, 14, mit «Auf dem Laptop prüfen»: `git pull`, `tools/laptop_pruefung.sh beheben`, drei Handtests, danach `laptop-ergebnis.txt` und, falls vorhanden, `startpruefung-absturz-zusammen.txt` anhängen. Im Bericht ehrlich trennen, was gemessen und was nur gelesen ist.
- Die Behebung gilt **erst** als wirksam, wenn auf dem Laptop `kopie` 20 von 20 Exit-Code 0 hat **und** die drei Handtests Exit-Code 0.

## Nicht bauen

Keine neuen Funktionen. P06e und P06f folgen erst nach stabilem Start. Die Diagnose-Schalter und `ui/diagnose_p08.py` bleiben bis dahin im Code.
