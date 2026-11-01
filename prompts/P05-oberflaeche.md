# P05 – Hauptfenster

Lies `CLAUDE.md`, `docs/04-ui-design.md` und `docs/02-architektur.md` (Abschnitte 1, 2, 4).

## Aufgabe (F-01, F-02, F-04, F-06)

Baue das Hauptfenster der Oberfläche (PyQt6) in `src/donstv_studio/ui/`, Variante A (OBS klassisch).

1. **Aufbau**: Menüleiste (Datei, Bearbeiten, Ansicht, Docks, Werkzeuge, Hilfe), Modul-Reiter oben «Overlays» und «Chat-Bot», rechts davon der Verbindungsstatus (Twitch, OBS, NDI). Darunter die Vorschaufläche (Platzhalter, P06 füllt sie), unten die vier Docks «Overlays», «Quellen», «Eigenschaften», «Steuerung» als echte `QDockWidget`: in Grösse veränderbar, verschiebbar, schwebend, ausblendbar. Statuszeile unten.
2. **Modul «Chat-Bot»**: Reiter Actions, Commands, Timer, Queues, Einstellungen als leere Platzhalter mit Beschriftung. Aufbau wie in `docs/04-ui-design.md`, Abschnitt 4. Inhalte folgen in P07.
3. **Verbindung zum Kern-Dienst**: Die Oberfläche startet den Kern-Dienst nicht selbst, sondern verbindet sich lokal (Token aus P02). Ist er nicht erreichbar: klare Meldung und Wiederholversuch; die Oberfläche stürzt nicht ab. Verbindungsstatus kommt über `/ws/events`.
4. **Status nie nur durch Farbe** (U-04): Text und Symbol, zusätzlich Farbe.
5. **Theme** (F-06): dunkel (Standard) und hell, umschaltbar in «Einstellungen». Alle Farben als benannte Werte an einer Stelle. Test: Kontrast von Text zu Hintergrund mindestens 4.5:1 für alle Textfarben beider Themes (berechne das Verhältnis nach WCAG 2.x). Die Farben aus den Mockups sind Platzhalter; wähle sachliche Werte und melde sie im Bericht.
6. **Layout merken**: Fensterposition, Dock-Anordnung und Theme werden gespeichert und beim Start wiederhergestellt (über die Schnittstelle des Kerns, nicht in einer eigenen Datei).
7. Beschriftungen Deutsch, Schweizer Rechtschreibung.

## Abnahme

- Test mit `QT_QPA_PLATFORM=offscreen`: Fenster startet, Modulumschalter wechselt, Theme wechselt, Dock-Anordnung wird gespeichert und geladen.
- Test des Kontrastverhältnisses für beide Themes.
- Test: Kern-Dienst nicht erreichbar → Meldung, kein Absturz.
- Du startest die Oberfläche und bestätigst das Aussehen.

## Nicht bauen

Keine Overlay-Bearbeitung (P06), keine Chat-Funktion (P07).
