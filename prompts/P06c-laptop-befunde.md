# P06c – Befunde vom Studio-Laptop beheben

Lies `CLAUDE.md` (besonders Regel 12), `docs/02-architektur.md` (Abschnitt «Befund Debian 13» und «Diagnose bei Absturz») und `tools/diagnose_qt.py`.

## Anlass

Der Nutzer hat die Testsuite auf dem Studio-Laptop ausgeführt (Debian 13, nur Debian-Pakete: PyQt6 6.9.0 mit Qt 6.8.2, PyQt6-WebEngine 6.9.0, fastapi 0.115.11, starlette 0.46.1, pydantic 2.10.6, uvicorn 0.32.0, websockets 15.0.1). Ergebnis (Stand Commit `f688d81`, Datei `laptop-ergebnis.txt` des Nutzers, im Repo nicht vorhanden): **4 fehlgeschlagen, 410 bestanden, 2 übersprungen** (Playwright dort nicht installiert, in Ordnung), danach ein **Speicherzugriffsfehler beim Beenden des pytest-Prozesses** (Exit-Code 139). Vorher erschien 18 Mal «Release of profile requested but WebEnginePage still not deleted. Expect troubles !».

Die Fehler:
1. `tests/test_editor_web.py::test_f65_dpr_2_zoom_100_is_still_one_overlay_pixel_per_screen_pixel`: «Unterprozess lieferte nichts», stdout und stderr leer.
2. `tests/test_ui_header.py::test_f04_service_icons_do_not_change_position_or_width`: `has_icon` ist für die Dienste falsch. Im Protokoll: «SVG-Symbole brauchen das Qt-SVG-Modul».
3. `tests/test_ui_header.py::test_f04_state_symbol_and_text_with_service_icons`: `icon_pixmap()` ist `None`.
4. `tests/test_ui_header.py::test_help_about_names_ndi_trademark_only_when_ndi_icon_is_used`: der NDI-Hinweis fehlt.

Auf dem Laptop fehlt das Qt-SVG-Modul. Es ist **unbekannt**, ob die Fehler 2 bis 4 nur an Testdateien aus SVG liegen oder ob die Anwendung auf dem Laptop auch keine Symbole zeigt, obwohl `assets/icons/connections/` PNG-Dateien enthält (P05c verlangt «PNG zuerst»).

## Aufgabe (F-01, F-04, F-65)

### 1. Symbole ohne Qt-SVG-Modul (Fehler 2 bis 4)
- Prüfe zuerst, ob die Anwendung mit den **echten PNG-Dateien** aus `assets/icons/connections/` die Symbole zeigt, wenn das Qt-SVG-Modul fehlt (simuliere das Fehlen des Moduls im Test). Wenn nicht, ist das ein Fehler der Anwendung: beheben.
- Die Tests dürfen nicht vom SVG-Modul abhängen. Erzeuge Test-Symbole als PNG (grau, kein Logo). Zusätzlich je ein Test für SVG, der **mit Begründung übersprungen** wird, wenn das Modul fehlt (`pytest.importorskip` oder gleichwertig), nicht still weggelassen.
- Der NDI-Markenhinweis erscheint, sobald eine NDI-Symboldatei (PNG oder SVG) verwendet wird. Test mit PNG.

### 2. Der Unterprozess-Test mit `QT_SCALE_FACTOR=2` (Fehler 1)
- Der Test meldet bei leerer Ausgabe nur «lieferte nichts». Gib im Fehlerfall **Exit-Code, stdout und stderr vollständig** aus (nicht nur die letzten 2000 Zeichen) und starte den Unterprozess mit `python -X faulthandler`.
- Ziel: auf dem Laptop erkennbar machen, ob der Unterprozess abstürzt (Exit-Code negativ oder 139) oder nichts ausgibt. Beschreibe im Bericht, was du aus dem Code und den Qt-Quellen ableiten kannst, und kennzeichne alles, was du nicht auf Qt 6.8.2 prüfen konntest, als «nicht geprüft».
- Nicht den Test löschen und nicht abschwächen, nur weil er auf dem Laptop fehlschlägt. Wenn es sich um einen Absturz von QtWebEngine bei `QT_SCALE_FACTOR=2` unter Qt 6.8.2 handelt, ist das ein Befund für `docs/02`, und der Test wird nur mit klarer Begründung auf Qt-Versionen unter 6.9 übersprungen (Qt-Version zur Laufzeit abfragen, im Bericht ausweisen).

### 3. Speicherzugriffsfehler beim Beenden
Der Prozess stürzt nach den Tests ab, vorher kommt mehrfach «WebEnginePage still not deleted». Das kann auch das **Beenden der echten Anwendung** betreffen.
- Baue `tools/beenden_pruefung.py` (und `tools/beenden_pruefung.sh` als Aufruf), das die **echte Oberfläche** mit der Vorschau (QtWebEngine) offscreen startet, ein Overlay anlegt und anzeigt, das Fenster schliesst und den **Exit-Code des Prozesses** meldet. Mehrere Durchläufe (z. B. 5), jeder in einem eigenen Prozess, mit `python -X faulthandler`. Ausgabe: für jeden Lauf der Exit-Code und die letzten Zeilen von stderr; am Ende eine Zusammenfassung («5 von 5 Läufen mit Exit-Code 0»).
- Ermittle, in welcher Reihenfolge die Qt-Objekte beim Beenden freigegeben werden müssen (Seite vor Profil, Ansicht vor Seite, `QApplication` zuletzt), und baue das **explizite Aufräumen beim Beenden** in die Anwendung ein, mit Quellenangabe (Qt-Dokumentation zu `QWebEngineProfile`/`QWebEnginePage`, URL im Kommentar).
- Für die Testsuite: Fixture, die vor dem Ende der Sitzung alle `QWebEngineView`/`QWebEnginePage`-Objekte kontrolliert freigibt. In P06 wurde ein Aufräumen nach jedem Test zurückgenommen, weil Qt abstürzte; ein Aufräumen **einmal am Ende der Sitzung** ist ein anderer Ansatz. Wenn auch das scheitert: beschreibe, was geprüft wurde.
- Kann der Absturz in deiner Umgebung (andere Qt-Version) nicht auftreten, sag das klar. Dann liefert `tools/beenden_pruefung.sh` die Daten, und der Nutzer führt es auf dem Laptop aus.

### 4. Skripte
- `tools/laptop_pruefung.sh` ruft zusätzlich `tools/beenden_pruefung.sh` auf (nach der Testsuite), damit der Nutzer **einen** Aufruf macht und **eine** Ergebnisdatei (`laptop-ergebnis.txt`) liefert.
- `tools/laptop_pruefung.sh` meldet zusätzlich, ob das Qt-SVG-Modul vorhanden ist (`python -c "import PyQt6.QtSvg"`), und welche Debian-Pakete dafür gelten (nenne sie im Bericht nur, wenn du sie kennst; sonst «nicht geprüft»).

## Nicht bauen

Keine neuen Funktionen, keine Änderungen an P07 (Chat-Bot), kein Entfernen von Tests.

## Abnahme

- Alle Tests in beiden Umgebungen (neueste Pakete und Mindestversionen aus `pyproject.toml`) bestehen; Ergebnis nennen.
- `tools/beenden_pruefung.sh` läuft; Ergebnis aus deiner Umgebung nennen.
- Bericht nach `CLAUDE.md`, Regeln 11, 13 und 14, als `docs/berichte/P06c.md`. Am Ende: genau die Befehle, die der Nutzer auf dem Laptop ausführt.
