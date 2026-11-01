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
- Ist das Fenster zu schmal für alle Felder, werden die Leistungsfelder **ausgeblendet** (ab einer festen Breite), die Reiter und Verbindungsanzeigen verschieben sich dabei nicht. Lege die Mindestbreite fest und nenne sie im Bericht.
- Fehlt eine `/proc`-Datei oder ist sie nicht lesbar: das Feld zeigt «–» und die Anwendung läuft ohne Fehler weiter.
- Ein Menüpunkt «Ansicht → Leistungsanzeige» schaltet die Anzeige ein oder aus. Der Zustand wird wie das Layout im Kern gespeichert (`ui.perf_visible`). Beim Ausschalten bleibt die Lage von Reitern und Verbindungsanzeigen gleich.

### 2. Tests
- Berechnung (ohne Oberfläche): CPU-Prozent aus zwei `/proc/stat`-Messungen, RAM aus `/proc/meminfo`, LAN-Raten aus zwei `/proc/net/dev`-Messungen. Mit Testdateien (Beispielinhalte), Wertebereiche (0 bis 100 %), Zähler-Überlauf und fehlende Dateien.
- Formatierung: kbit/s und Mbit/s, GiB, Rundung, Länge des Textes ≤ der berechneten festen Breite.
- Oberfläche (offscreen): Lage und Grösse von Reitern, Verbindungsanzeigen und Leistungsfeldern bleiben identisch bei Wertänderungen, bei allen Dock-Anordnungen, bei Moduswechsel und beim Ein- und Ausschalten der Anzeige (Reiter und Verbindungsanzeigen bleiben gleich). Gegenprobe im Bericht nennen.
- Verlaufspuffer: genau 60 Werte, ältester fällt heraus.
- **Eigenlast:** Miss die Rechenzeit einer Messung samt Zeichnen und nenne sie im Bericht. Ziel: unter 1 % einer CPU-Sekunde pro Sekunde [ANNAHME] auf der Testumgebung. Der Zielrechner ist schwach (i7-4500U); nenne, was du nicht dort gemessen hast.
- Kontrast: Die neuen Farben bestehen den bestehenden Kontrasttest in beiden Themes.

### 3. Dienst-Symbole (Rückfrage des Nutzers)
Auf dem Laptop sind keine Symbole sichtbar, weil die Dateien unter `assets/icons/connections/` fehlen (der Nutzer liefert sie, du zeichnest keine). Prüfe nur, dass die Anzeige mit echten Dateien funktioniert, und ergänze, falls nötig, **PNG-Unterstützung zuerst**: Eine PNG-Datei (mit Transparenz) muss auch dann angezeigt werden, wenn das Qt-SVG-Modul fehlt. Ist eine SVG-Datei vorhanden und das SVG-Modul fehlt, zeigt die Oberfläche **einen einmaligen Hinweis in der Statuszeile oder im Protokoll** («SVG-Symbole brauchen das Qt-SVG-Modul, Debian: vermutlich libqt6svg6») statt still nichts anzuzeigen. Schreibe das in `assets/icons/connections/README.md`. Test mit einer selbst erzeugten PNG-Datei (grau, kein Logo).

### 4. Dokumentation
- `docs/01-funktionen.md`: neue Funktion **F-68** «Leistungsanzeige (CPU, RAM, LAN) im Fensterkopf, ein-/ausschaltbar» (SOLL, Quelle: Vorgabe) und **F-69** «Leistungsdaten des Streaming-PCs aus OBS (über die OBS-Verbindung, Anforderung `GetStats` von obs-websocket, in der Dokumentation prüfen)» (KANN). F-69 wird nicht gebaut.
- `docs/04-ui-design.md`: Fensterkopf um die Leistungsanzeige ergänzen, Quelle `docs/referenz/vorbild-leistungsanzeige.png`.

## Nicht bauen

Keine Daten des Streaming-PCs (F-69), keine GPU-Anzeige, keine Temperaturen, keine Auswahl einzelner Schnittstellen, keine Overlay-Bearbeitung (P06).

Halte dich an `CLAUDE.md`, Regel 11 (Abschlussbericht). Tests in zwei Umgebungen (neueste Pakete und Mindestversionen aus `pyproject.toml`), beide Ergebnisse nennen. Anleitung «Auf dem Laptop prüfen» am Ende. Committe mit F-Nummern und pushe auf `claude/epic-faraday-4rfiwx`.
