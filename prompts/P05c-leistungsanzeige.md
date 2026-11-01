# P05c – Leistungsanzeige im Fensterkopf, Dienst-Symbole prüfen

Lies `CLAUDE.md`, `docs/04-ui-design.md` und `prompts/P05b-fensterkopf-und-stil.md`.
Sieh dir diese Bilder an (Dateien lesen):
- `docs/referenz/vorbild-leistungsanzeige.png`: **Vorbild** der Leistungsanzeige (CPU, RAM, LAN mit kleinen Verlaufsgrafiken). Es stammt aus einer Systemanzeige des Nutzers. Übernimm Aufbau und Inhalt, nicht die Farben oder die Schrift: Sie soll im Stil von donstv_Studio erscheinen (`ui/theme.py`).
- `docs/referenz/screenshot-donstv-studio-p05b.png`: Stand nach P05b auf dem Laptop.

## Aufgabe (neue Funktion F-68, siehe unten; F-04)

### 1. Leistungsanzeige im festen Fensterkopf
Im Kopf (P05b, `setMenuWidget`) erscheint zwischen den Reitern links und den Verbindungsanzeigen rechts eine Leistungsanzeige mit drei Feldern, jedes mit Beschriftung, Wert und einem Verlauf der letzten 60 Sekunden:

| Feld | Wert (Beispiel aus dem Vorbild) | Quelle |
|---|---|---|
| CPU | «4 %» (Gesamtauslastung aller Kerne) | `/proc/stat` |
| RAM | «5.3 / 15.5 GiB» (belegt / gesamt) | `/proc/meminfo` (belegt = gesamt − verfügbar, `MemAvailable`) |
| LAN | «↓ 3  ↑ 99 kbit/s» (Empfang / Senden, automatisch kbit/s oder Mbit/s) | `/proc/net/dev` |

- Lies die Werte **direkt aus `/proc`**, ohne neues Paket [ANNAHME: Zielsystem Debian 13]. Nur ein Zeitgeber der Oberfläche, **1 Messung pro Sekunde**, keine eigenen Threads. Die Anzeige läuft nicht weiter, wenn das Fenster minimiert ist.
- LAN: Summe aller Schnittstellen ausser `lo` und virtuellen (`docker*`, `veth*`, `br-*`, `virbr*`, `tun*`, `tap*`). Der Verlauf zeigt die Summe aus Empfang und Senden, der Wert nennt beide getrennt. Prüfe auf dem Rechner, welche Namen es gibt, und nenne die verwendete Auswahl im Bericht.
- Verlauf: eine mit `QPainter` gezeichnete Fläche mit Linie, Farben aus `ui/theme.py` (je Feld eine Akzentfarbe aus dem Theme, in beiden Themes mit ausreichendem Kontrast zur Fläche, ≥ 3:1 für Grafik). Der **Wert steht immer als Text** daneben (U-04: nie nur Grafik oder Farbe).
- Das Aussehen passt zum Rest: gleiche Schrift (System, 10 pt), gleiche Farben, gleicher Rand wie die Verbindungsanzeigen. Nicht grösser als der Kopf (Höhe wie bisher).
- **Feste Lage (wie P05b):** Jedes Feld hat eine feste Breite, berechnet für den längsten möglichen Text (z. B. «999.9 / 999.9 GiB», «↓ 999.9 Mbit/s  ↑ 999.9 Mbit/s»). Ändert sich ein Wert, verschiebt sich nichts. Reiter und Verbindungsanzeigen behalten ihre Lage exakt. Die bestehenden Tests zur festen Lage laufen weiter und werden um die Leistungsfelder erweitert.
- Damit die Anzeige immer sichtbar ist, bekommt das Hauptfenster eine **Mindestbreite**, bei der alle Teile des Kopfes (Reiter, Leistungsfelder, vier Verbindungsanzeigen) nebeneinander Platz haben. Berechne sie aus den festen Breiten, setze sie als Mindestgrösse des Fensters und nenne den Wert im Bericht. Test: Bei dieser Mindestbreite überlappt nichts und nichts ist abgeschnitten.
- **Der Kopf wird höher.** Der Nutzer wünscht ausdrücklich einen etwas kräftigeren Kopf. Erhöhe die Kopfzeile von heute auf etwa 44 bis 48 Pixel [ANNAHME], mit Verlaufsgrafiken von etwa 28 Pixeln Höhe. Reiter und Verbindungsanzeigen werden senkrecht mittig ausgerichtet. Nenne die gewählte Höhe im Bericht. Das Verhältnis zu OBS (Dock-Titel 26 px usw.) bleibt sonst unverändert.
- Fehlt eine `/proc`-Datei oder ist sie nicht lesbar: das Feld zeigt «–» und die Anwendung läuft ohne Fehler weiter.
- Die Leistungsanzeige ist **immer sichtbar**. Es gibt keinen Schalter und keine Einstellung dafür.

### 2. Tests
- Berechnung (ohne Oberfläche): CPU-Prozent aus zwei `/proc/stat`-Messungen, RAM aus `/proc/meminfo`, LAN-Raten aus zwei `/proc/net/dev`-Messungen. Mit Testdateien (Beispielinhalte), Wertebereiche (0 bis 100 %), Zähler-Überlauf und fehlende Dateien.
- Formatierung: kbit/s und Mbit/s, GiB, Rundung, Länge des Textes ≤ der berechneten festen Breite.
- Oberfläche (offscreen): Lage und Grösse von Reitern, Verbindungsanzeigen und Leistungsfeldern bleiben identisch bei Wertänderungen, bei allen Dock-Anordnungen, bei Moduswechsel und bei allen Fenstergrössen ab der Mindestbreite. Gegenprobe im Bericht nennen.
- Verlaufspuffer: genau 60 Werte, ältester fällt heraus.
- **Eigenlast:** Miss die Rechenzeit einer Messung samt Zeichnen und nenne sie im Bericht. Ziel: unter 1 % einer CPU-Sekunde pro Sekunde [ANNAHME] auf der Testumgebung. Der Zielrechner ist schwach (i7-4500U); nenne, was du nicht dort gemessen hast.
- Kontrast: Die neuen Farben bestehen den bestehenden Kontrasttest in beiden Themes.

### 3. Dienst-Symbole
Die Dateien liegen jetzt im Repo unter `assets/icons/connections/` (`twitch`, `youtube`, `obs`, `ndi`, je als `.svg` und `.png`; Herkunft und Hinweise in der `README.md` dort). Du zeichnest und änderst keine Symbole.
- Die Symbole sind **einfarbig** (die PNG-Dateien weiss mit Transparenz, die SVG-Dateien einfarbig). Die Oberfläche färbt sie in der **Textfarbe des aktuellen Themes** ein (Alpha-Maske mit der Farbe füllen, z. B. `QPainter.CompositionMode_SourceIn`), damit sie im dunklen und im hellen Design sichtbar sind. Beim Theme-Wechsel werden sie neu eingefärbt.
- **PNG zuerst:** Eine PNG-Datei muss auch angezeigt werden, wenn das Qt-SVG-Modul fehlt. Sind PNG und SVG vorhanden, wird PNG verwendet. Ist nur eine SVG-Datei vorhanden und das SVG-Modul fehlt, zeigt die Oberfläche einmalig einen Hinweis im Protokoll («SVG-Symbole brauchen das Qt-SVG-Modul, Debian: vermutlich libqt6svg6»).
- Symbolgrösse 16 Pixel (bei hohem Kopf darf sie auf 20 Pixel steigen, dann bleibt der reservierte Platz in der Breite fest). Der Platz ist fest, die Lage bleibt wie in P05b.
- Test: mit den echten Dateien aus dem Repo sind im dunklen und im hellen Design Pixel in der Textfarbe des Themes vorhanden (nicht weiss auf weiss). Test ohne SVG-Modul (simuliert): PNG wird angezeigt. Lage und Breite der Anzeigen sind mit und ohne Dateien gleich (wie P05b).
- Der NDI-Markenhinweis in «Hilfe → Über» erscheint, weil die Datei vorhanden ist. Prüfe das.

### 4. Dokumentation
- `docs/01-funktionen.md`: neue Funktion **F-68** «Leistungsanzeige (CPU, RAM, LAN) im Fensterkopf, immer sichtbar» (SOLL, Quelle: Vorgabe) und **F-69** «Leistungsdaten des Streaming-PCs aus OBS (über die OBS-Verbindung, Anforderung `GetStats` von obs-websocket, in der Dokumentation prüfen)» (KANN). F-69 wird nicht gebaut.
- `docs/04-ui-design.md`: Fensterkopf um die Leistungsanzeige ergänzen, Quelle `docs/referenz/vorbild-leistungsanzeige.png`.

## Nicht bauen

Keine Daten des Streaming-PCs (F-69), keine Ein-/Ausschalter für die Anzeige, keine GPU-Anzeige, keine Temperaturen, keine Auswahl einzelner Schnittstellen, keine Overlay-Bearbeitung (P06).

Halte dich an `CLAUDE.md`, Regel 11 (Abschlussbericht). Tests in zwei Umgebungen (neueste Pakete und Mindestversionen aus `pyproject.toml`), beide Ergebnisse nennen. Anleitung «Auf dem Laptop prüfen» am Ende. Committe mit F-Nummern und pushe auf `claude/epic-faraday-4rfiwx`.
