# P06d4 – Absturz: die drei Fenster-Teile und die echten Daten trennen

Lies `CLAUDE.md` (Regeln 9, 12, 15, 16), `docs/befunde/absturz-p06d.md` **mit beiden Nachträgen (2026-11-01 und 2026-11-02)**, `docs/berichte/P06d3.md`.

**Lage:** Mit `tools/laptop_pruefung.sh eingrenzen` ist der Absturz auf dem Laptop erstmals reproduzierbar: Variante `kopie` (Kopie der echten Daten des Nutzers) stürzt 0 von 5 Läufen ohne Absturz durch (alle −11), `kopie,aus=window_changes` läuft 5 von 5. Alle anderen Schalter helfen nicht, `daten` läuft ebenfalls. Der Absturz hängt also an (a) mindestens einem der drei Teile, die `window_changes` zusammenfasst, und (b) etwas in den echten Daten, das `daten` nicht hat.

**Dieser Auftrag liefert Messwerkzeug und Beschreibung, keine Behebung.** Die Behebung folgt in P06d5, sobald der Nutzer gemessen hat. (Regel 9: nicht raten.)

## Aufgaben

1. **`window_changes` aufteilen** in drei Schalter, jeder für sich der Stand P08 für genau diesen Teil (in `ui/diagnose.py`, `ui/main_window.py`, Markierung `# DIAGNOSE (P06d4)`): `window_stylesheet` (Stylesheet bei jedem Aufruf setzen), `window_minwidth` (Mindestbreite sofort statt über den Zeitgeber), `window_geometry` (`restoreGeometry` direkt, ohne «dieselbe Lage nur einmal», ohne Breitenanpassung). `window_changes` bleibt als Kurzform für alle drei (`IMPLIES`).
2. **Die echten Daten aufteilen.** Neue Varianten von `tools/start_pruefung.py`, jeweils Kopie der echten Daten mit einer Änderung (das Original wird nie verändert, nur die Kopie):
   - `kopie_ohne_lage`: ohne gespeicherte Fensterlage und Dock-Anordnung (Schlüssel `geometry` und `state`),
   - `kopie_ohne_geometrie`: nur `geometry` entfernt, `state` bleibt,
   - `kopie_ohne_anordnung`: nur `state` entfernt, `geometry` bleibt,
   - `kopie_ohne_quellen`: Overlays bleiben, aber ohne Quellen (nur für die Kopie).
   Jede Variante lässt sich mit `,aus=<Liste>` kombinieren.
3. **Lage beschreiben, ohne Geheimnisse.** `start_pruefung` (oder ein kleines Werkzeug `tools/lage_beschreiben.py`) gibt für die Kopie aus, was in `geometry` und `state` steckt: Länge, Versionsmarke, Fensterlage in Pixeln (Position und Grösse; bei `QMainWindow.restoreGeometry` mit `QByteArray` aus dem Qt-Format, falls lesbar, sonst «nicht lesbar»), ob maximiert oder Vollbild, Bildschirmnummer, Anzahl Reiterpaare und schwebender Docks aus dem Zustand, aktuelles Theme. Keine Zugangsdaten, keine Dateinamen der Medien.
4. **`tools/laptop_pruefung.sh fein`:** je 5 Läufe für `kopie`, `kopie,aus=window_stylesheet`, `kopie,aus=window_minwidth`, `kopie,aus=window_geometry`, danach `kopie,aus=window_stylesheet window_minwidth`, `kopie,aus=window_stylesheet window_geometry`, `kopie,aus=window_minwidth window_geometry`, danach die vier Varianten aus Aufgabe 2 ohne Schalter. Zusammenfassung wie bei `eingrenzen`. Die Absturzdateien sollen höchstens **zwei je Variante** behalten (eine Variante mit 5 Dateien braucht niemand), und alle in **einer** Datei `startpruefung-absturz-zusammen.txt` sammeln, damit der Nutzer eine Anlage schicken kann.
5. **C++-Aufrufliste:** Die Absturzdateien sagen «mit C++-Aufrufliste», die Berichtsdatei enthält aber keine. Finde heraus, warum (gdb installiert? `core_pattern`?), und gib im Bericht den Befehl an, den der Nutzer auf dem Laptop braucht (Paket `gdb` aus Debian, Hinweis `sudo apt install gdb`), damit die C++-Aufrufliste beim nächsten Lauf in der Zusammenfassung erscheint.
6. **Lesen:** Beschreibe im Bericht, was nach dem Code (`main_window.py`: `apply_settings`, `_restore_geometry`, `_apply_theme_style`, `_update_minimum_width`, `settings_loaded`) beim Start in welcher Reihenfolge geschieht, bei den echten Daten und bei `daten`, und welche der drei Teile bei der Reihenfolge `restoreGeometry` → `restoreState` → erste Datenantwort → `setCurrentWidget` mitspielen können. Belege je Aussage mit Zeilennummern; Qt-Quelltext 6.8.2 als Quelle (Regel 10), sonst «nicht geprüft».

## Abnahme

- Tests in den drei Umgebungen grün, `ruff` ohne Befund; neue Tests für die Schalter und die vier Varianten (Aufteilung wirkt, Kopie wird nie verändert).
- Bericht `docs/berichte/P06d4.md` nach den Regeln 11, 13, 14, mit «Auf dem Laptop prüfen»: `git pull`, `tools/laptop_pruefung.sh fein`, danach `startpruefung-absturz-zusammen.txt` und `laptop-ergebnis.txt` anhängen.

## Nicht bauen

Keine Behebung, keine neuen Funktionen. P06e und P06f folgen erst nach stabilem Start.
