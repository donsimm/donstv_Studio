# P05b – Fensterkopf fixieren, YouTube-Status, Stil nach OBS

Lies `CLAUDE.md`, `docs/04-ui-design.md` und `prompts/P05-oberflaeche.md`.
Sieh dir beide Bilder an (Datei lesen, sie sind Bilder):
- `docs/referenz/screenshot-donstv-studio-p05.png`: unser Fenster nach P05, auf dem Laptop (GNOME, 1920×1080).
- `docs/referenz/screenshot-obs-30.2.3.1.png`: OBS 30.2.3.1 als Vorbild für Schrift, Abstände und Aufbau.

## Anlass (Rückmeldung des Nutzers nach dem ersten Start auf dem Laptop)

1. Die Reiter «Overlays» und «Chat-Bot» und die Verbindungsanzeigen liegen im mittleren Bereich. Das Dock «Overlays» links schiebt sie nach rechts. Das darf nicht passieren.
2. In der Verbindungsleiste fehlt YouTube.
3. Der Stil soll näher an OBS liegen (Schriftgrössen, Abstände, Aussehen der Docks).

## Aufgabe (F-01, F-02, F-04, F-06)

### 1. Fester Fensterkopf
- Reiter «Overlays» / «Chat-Bot» und die Verbindungsanzeigen bilden einen festen Kopf über der **gesamten Fensterbreite**, direkt unter der Menüleiste und **über allen Docks** (zum Beispiel als nicht verschiebbare, nicht lösbare `QToolBar` im oberen Bereich oder per `setMenuWidget`; wähle die Lösung, die das zuverlässig leistet, und begründe sie im Bericht).
- Der Kopf darf sich durch **nichts** verschieben: nicht durch Docks links, rechts, unten, schwebend oder ausgeblendet, nicht durch Fenstergrösse (Breite und Höhe ändern sich, die linke Lage der Reiter nicht), nicht durch Wechsel des Moduls.
- Die Verbindungsanzeigen stehen rechtsbündig. Jede hat eine **feste Mindestbreite**, die für den längsten Text reicht («verbindet», «getrennt», «Fehler»). Ändert sich ein Zustand, verschiebt sich keine andere Anzeige und kein Reiter.
- Test (offscreen): Position und Grösse der Reiter und jeder Verbindungsanzeige sind **identisch** (gleiche Pixel), wenn das Dock «Overlays» links, rechts, unten, schwebend oder ausgeblendet ist, und bei allen Zuständen der Verbindungen. Der Test muss fehlschlagen, wenn der Kopf wieder in den Mittelbereich verschoben wird (Gegenprobe im Bericht nennen).

### 2. YouTube als Verbindung
- Reihenfolge der Anzeigen: Twitch, YouTube, OBS, NDI. Jede mit Symbol und Text (U-04).
- YouTube hat im Gerüst keine echte Verbindung (F-55 ist KANN). Es soll eine Verbindung mit dem Namen `youtube` im Verbindungs-Verwalter von P02 vorhanden sein, die immer «getrennt» meldet und im Tipp-Text «nicht eingerichtet» sagt. Das sorgt dafür, dass später dieselbe Anzeige echte Zustände zeigt. Nicht mehr bauen.
- `docs/01-funktionen.md` (F-04) und `docs/04-ui-design.md` (U-04, Hauptfenster) auf «Twitch, YouTube, OBS, NDI» ändern.

### 3. Standardanordnung der Docks
Im Bild steht «Overlays» links über die volle Höhe. Variante A verlangt etwas anderes: **unten vier Docks nebeneinander** (Overlays, Quellen, Eigenschaften, Steuerung), darüber die Vorschaufläche, wie bei OBS. Die Standardanordnung («Docks → Standardanordnung») und der erste Start ohne gespeicherte Werte müssen das zeigen. Der Nutzer darf die Docks weiterhin verschieben.

### 4. Stil nach OBS
Nimm das OBS-Bild als Vorbild. Prüfe die Werte selbst im Bild, schreibe sie nicht aus der Erinnerung:
- **Schrift:** die Systemschrift (nicht fest eine Schriftart setzen), Grössen so, dass Menüleiste, Dock-Titel (fett), Beschriftungen und Statuszeile im Verhältnis zueinander wie bei OBS wirken. Miss die Texthöhen in beiden Bildern und nenne im Bericht die gewählten Punktgrössen.
- **Docks:** Titelzeile fett mit kleinen Symbolen rechts (Lösen, Schliessen), schmaler Titel, ruhige Trennlinien.
- **Leiste unter der Vorschau** wie «Keine Quelle ausgewählt | Eigenschaften | Filter» bei OBS: als Platzhalter «Keine Quelle ausgewählt» mit gesperrten Schaltflächen «Eigenschaften» und «Filter» (Funktion folgt in P06).
- **Listen:** gewählte Zeile in kräftigem Blau mit weisser Schrift, Zeilenhöhe wie OBS.
- **Vorschaufläche:** dunkler Hintergrund mit einem Rand um die Leinwand (schwarze Fläche in der Mitte, wie OBS), nicht rahmenlos bis an den Rand.
- **Statuszeile** unten rechts mit den Angaben, die schon da sind.
- Die Farben bleiben in `ui/theme.py` an einer Stelle. Beide Themes (dunkel und hell) behalten Kontrast ≥ 4,5:1, der Test aus P05 bleibt gültig. Übernimm die OBS-Farben nur, wenn sie diesen Test bestehen, sonst nahe Werte wählen und das melden.
- Das Aussehen der Fensterleiste (weisse GNOME-Titelleiste im Bild) ist Sache des Systems und wird nicht verändert.

### 5. Prüfung
- Zwei Bildschirmfotos im Offscreen-Modus (Overlays-Modul, dunkel; Chat-Bot-Modul, hell) mit 1920×1080 ansehen und mit dem OBS-Bild vergleichen. Beschreibe im Bericht, was noch abweicht.
- Tests in zwei Umgebungen (neueste Pakete und Mindestversionen aus `pyproject.toml`); beide Ergebnisse nennen.
- Anleitung «Auf dem Laptop prüfen» am Ende des Berichts.

## Nicht bauen

Keine Overlay-Bearbeitung (P06), keine echte YouTube-Verbindung, keine Chat-Funktion.

Halte dich an `CLAUDE.md`, Regel 11 (Abschlussbericht). Committe mit F-Nummern und pushe auf `claude/epic-faraday-4rfiwx`.
