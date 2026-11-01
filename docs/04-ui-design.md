# 04 – UI und Design

Status: Entwurf 4, mit dem Code abgeglichen in P08 (1. November 2026). **Entscheid: Variante A (OBS klassisch) ist die Grundlage des Hauptfensters.** Farben und Schrift der Programmoberfläche sind Platzhalter, bis ein Theme festgelegt ist.

## 1. Grundsätze

| ID | Regel |
|---|---|
| U-01 | Hauptschrift (Standard) aller sichtbaren Overlay-Elemente: Be Vietnam Pro, lokal eingebunden, kein CDN. Andere Schriften sind wählbar (F-38, F-39). |
| U-02 | Das Programm sieht grundsätzlich aus wie OBS Studio: Menüleiste, andockbare Bereiche (Docks), Vorschaufläche, Statuszeile. Standard-Theme dunkel. [ANNAHME dunkel] |
| U-06 | In den Einstellungen kann zwischen dunklem und hellem Design gewählt werden (F-06). Beide Themes erfüllen den Kontrast von mindestens 4,5:1. |
| U-03 | Modulumschalter oben: «Overlays» und «Chat-Bot». |
| U-04 | Verbindungszustände (Twitch, YouTube, OBS, NDI) sind immer sichtbar. Zustand durch Farbe des Buttons; Ausnahme von «nie nur durch Farbe» auf Wunsch des Nutzers (siehe Leistungsanzeige-Abschnitt): Zeichen «?» nur bei Fehler und unbekannt. Sie stehen mit den Modul-Reitern in einem festen Fensterkopf über der ganzen Fensterbreite und über allen Docks; kein Dock und keine Fenstergrösse verschiebt ihn. Jede Anzeige hat eine feste Breite. |
| U-05 | Begriffe: Overlay = Szene, Quelle = Source. Beschriftungen auf Deutsch (Schweizer Rechtschreibung, kein «ß»). |
| U-07 | Lage und Grösse von Quellen werden in ganzen Pixeln der Overlay-Auflösung angezeigt und gespeichert (F-65), nicht in Prozent. Die Prozentwerte in den Mockups sind überholt. |
| U-08 | Das Steuerung-Dock enthält pro Overlay die Wahl der Ausgabeart «Browserquelle» oder «NDI» (F-66). |

## 2. Modul «Overlays» (nach OBS-Vorbild)

| Bereich | Inhalt |
|---|---|
| Overlays | Liste der Overlays (wie Szenen): anlegen, kopieren, löschen |
| Quellen | Liste der Quellen des gewählten Overlays: hinzufügen, Reihenfolge, Sichtbarkeit |
| Vorschaufläche | Overlay in gewählter Auflösung, Quellen verschieben, skalieren, drehen |
| Eigenschaften | Werte der gewählten Quelle (Lage, Inhalt, Animation). Umgesetzt (P06): nur Lage, Grösse, Drehung; Inhalt folgt mit F-70, Animation mit F-20. |
| Steuerung | URL der Browserquelle kopieren, später NDI starten, Speichern. Umgesetzt (P06): kein «Speichern»; jede Änderung geht sofort an den Kern-Dienst (Abgleich P08). |

## 3. Hauptfenster: Variante A gewählt

Gewählt: **Variante A**. Aufbau: Menüleiste, fester, dezent umrahmter Fensterkopf (56 px hoch) mit Modul-Reitern (Overlays, Chat-Bot) links, rechts den Verbindungs-Buttons (Twitch, YouTube, OBS, NDI) und ganz rechts der Leistungsanzeige (CPU, RAM, LAN, siehe unten), Vorschaufläche in der Mitte (ohne Leiste darunter, auf Wunsch des Nutzers entfallen), unten vier Docks (Overlays, Quellen, Eigenschaften, Steuerung), Statuszeile. Die Varianten B und C sind verworfen und bleiben nur als Vergleich im Design-Artefakt «donstv_Studio UI-Vorschläge» erhalten.

| Variante | Idee | Stärke | Schwäche |
|---|---|---|---|
| A – OBS klassisch | Vorschaufläche oben, vier Docks unten (Overlays, Quellen, Eigenschaften, Steuerung); Modul-Reiter oben | Am nächsten an OBS, vertraut | Docks unten sind schmal, wenig Platz für Eigenschaften |
| B – Seitenleiste mit Baum | Linke Leiste mit Modulwahl, Baum Overlay → Quellen, Werkzeugleiste über der Fläche, Eigenschaften rechts | Alles sichtbar, viel Platz für Eigenschaften | Weicht stärker von OBS ab |
| C – Filmstreifen | Overlays als Vorschaukarten oben, Fläche in der Mitte, Quelle-hinzufügen-Leiste, rechts Reiter Quellen/Eigenschaften/Vorlagen | Overlays schnell erkennbar, gut für Vorlagen | Kein Quellenbaum, Platz für viele Overlays begrenzt |

### Leistungsanzeige im Fensterkopf (F-68)

Drei Felder ganz rechts im Kopf, rechts der Verbindungs-Buttons, jedes mit Beschriftung links, Wert rechts (immer als Text, U-04) und einem Verlauf der letzten 60 Sekunden (28 px hoch, Fläche mit Linie). Quelle des Aufbaus: `docs/referenz/vorbild-leistungsanzeige.png` (übernommen sind Aufbau und Inhalt, nicht Farben und Schrift).

| Feld | Wert | Quelle |
|---|---|---|
| CPU | «4 %» (alle Kerne) | `/proc/stat` |
| RAM | «5.3 / 15.5 GiB» (gesamt − `MemAvailable` / gesamt) | `/proc/meminfo` |
| LAN | «↓ 3  ↑ 99 kbit/s» (Summe ohne `lo` und virtuelle Schnittstellen) | `/proc/net/dev` |

Die drei Felder sind gleich breit (F-78): so breit wie das breiteste nötige Feld, gemessen an allen möglichen Texten (jede Einheit, jede Ziffer); die Breite ändert sich bei keinem Wert; der Kopf hat eine Mindestbreite, bei der alles nebeneinander Platz hat. Linienfarben je Feld im Theme (`perf_cpu`, `perf_ram`, `perf_lan`), Kontrast zur Fläche mindestens 3:1. Fehlt eine Datei, steht «–». Ein Zeitgeber, 1 Messung pro Sekunde, nicht bei minimiertem Fenster.

Die Verbindungen sind Buttons mit dem Dienst-Symbol (einfarbig, in der Textfarbe des Themes, PNG vor SVG; 20 px). Farbe des Buttons: grün = verbunden, rot = getrennt oder Fehler, orange = verbindet, grau (ausgegraut) = nicht eingerichtet oder unbekannt. Nur bei Fehler und unbekanntem Zustand erscheint oben rechts am Button ein kleines «?»; sonst zeigt allein die Farbe den Zustand, dazu der Text im Tipp. Das ist ein Entscheid des Nutzers und weicht von U-04 («nie nur durch Farbe») ab. Die Buttons haben noch keine Klick-Funktion.

### Editor und Docks (P06)

| Bereich | Inhalt |
|---|---|
| Vorschau | `QWebEngineView` lädt die Overlay-Seite mit dem Token des Overlays (Feld `url`, Host auf 127.0.0.1 gesetzt). Darunter Karo-Hintergrund (Qt), darüber Auswahlrahmen, Griffe, Raster und Hilfslinien (Qt). Lineale oben und links; Ziehen aus dem Lineal erzeugt eine Hilfslinie, zurück aufs Lineal ziehen löscht sie. Ohne Overlay bleibt die schwarze Leinwand mit Hinweis. |
| Zeigerposition (F-75) | «X: … Y: …» (Pixel unter dem Zeiger, ganze Overlay-Pixel) links unten in der Vorschaufläche, von Qt über der Webansicht gezeichnet (nicht in der Overlay-Seite; die Ausgabe in OBS bleibt gleich). Halbtransparenter Grund in der Flächenfarbe (Deckkraft 200/255), Text in der Textfarbe, feste Breite. Ausserhalb der Overlay-Fläche und ausserhalb der Vorschau «X: –   Y: –». |
| Statuszeile | Links von der Kern-Anzeige: Zoom-Auswahl (Einpassen, 25, 50, 100, 200, 400 %). Die Zeigerposition steht seit P06d nur noch in der Vorschau. |
| Docks | Wie OBS: Liste oder Felder, unten eine Schaltflächenleiste (26 × 26 px) mit einfarbigen Symbolen in der Textfarbe des Themes. Overlays: Plus, Papierkorb, Duplizieren (Umbenennen: Doppelklick oder F2). Quellen: Plus (Text, Bild), Papierkorb, Pfeil hoch/runter; Auge links schaltet die Sichtbarkeit, Ziehen ordnet um; Umbenennen über Rechtsklick «Umbenennen» oder F2 (auch mit Fokus in der Vorschau), nicht per Doppelklick (reserviert für das Quellenfenster, F-79). Eigenschaften: Name (F-74, oben), X, Y, Breite, Höhe, Drehung; Leiste mit sechs Ausrichten-Symbolen. Steuerung: URL mit «Kopieren», Ausgabeart, Bildrate und «Vorschau verkleinern», Einrasten, Raster samt Weite, «Hilfslinien löschen». |
| Tasten | Pfeile: 1 px, mit Umschalttaste 10 px (Fokus auf der Vorschau). Strg+Z / Strg+Y (auch Strg+Umschalt+Z): Rückgängig / Wiederholen. Strg+0: Einpassen. Alt+1: 100 %. Strg++ / Strg+-: Zoomstufe. Strg+Mausrad: Zoom. Mausrad / Umschalt+Mausrad: bewegen. |
| Maus | Klick wählt (oberste Quelle zuerst), Ziehen verschiebt, Eck- und Seitengriffe skalieren, Kreis über der Oberkante dreht (Umschalttaste: 15°-Schritte; ohne: ganze Grad). Bildquellen (F-77): Eckgriffe behalten das Seitenverhältnis vom Anfang des Ziehens (im Koordinatensystem der Quelle, auch gedreht), die Umschalttaste löst es; Seitengriffe sind frei. Ein neues Bild bekommt einen Rahmen im Seitenverhältnis des Bildes, verkleinert, bis er ins Overlay passt. |
| Bedienelemente (F-76) | Häkchen, Pfeile der Zahlenfelder und Auswahllisten und Rahmen der Eingabefelder mit eigenen Farben aus `ui/theme.py` (`control_border`, `arrow`, `check_bg`, `check_mark`), Kontrast mindestens 3:1 gegen den Untergrund in beiden Themes (Liste `CONTROL_PAIRS`). Häkchen und Pfeile sind PNG-Bilder, mit QPainter gezeichnet (`ui/indicators.py`), ohne Qt-SVG-Modul. |

## 4. Modul «Chat-Bot» (nach Streamer.bot-Vorbild)

Gezeigt in Vorschlag D (Gerüst von Variante A, auf B oder C übertragbar).

| Bereich | Inhalt |
|---|---|
| Reiter | Actions, Commands, Timer, Queues, Einstellungen |
| Chat-Dock | Live-Chat mit Eingabefeld und «Senden» |
| Commands | Tabelle: Name, Befehl, Berechtigung, Cooldown, Aktiv; Knöpfe Neu, Duplizieren, Löschen, Importieren |
| Command bearbeiten | Name, Befehl, Berechtigung, Cooldown (global, pro Nutzer), Antworttext |
| Protokoll | Liste der letzten Bot-Ereignisse |

Im Gerüst sind nur die Bereiche Chat und Commands gefüllt (dazu «Einstellungen»). Die Reiter Actions, Timer und Queues sind vorhanden und zeigen «Folgt in einem späteren Baustein (F-46 bis F-51)».

Umsetzung P07:

| Bereich | Inhalt |
|---|---|
| Reiter «Commands» | Links Tabelle (Name, Befehl, Berechtigung, Cooldown «global / pro Nutzer», Aktiv mit Haken), darunter «Neu», «Duplizieren», «Löschen» und «Importieren» (gesperrt, Hinweis «Importieren folgt»). Rechts «Command bearbeiten»: Name, Befehl, Berechtigung (Alle, Abonnenten, Moderatoren, Streamer), Cooldown global und pro Nutzer in Sekunden, Antworttext mit Zeichenzähler (höchstens 500, `{user}` = Anzeigename), «Aktiv», «Speichern». Ein neuer oder duplizierter Command ist inaktiv. |
| Reiter «Einstellungen» | «Twitch-Anwendung»: Client-ID, Kanal, «Speichern». «Bot-Konto»: Zustand, «Anmelden» (zeigt Adresse und Code, «Adresse öffnen», «Code kopieren»), «Abmelden». |
| Dock «Chat» | Rechts, nur im Modul «Chat-Bot». Zeit, Zeichen für Streamer (★) und Moderator (⚔), Name, Text; letzte 500 Nachrichten. Eingabefeld «Nachricht an den Chat» und «Senden» (auch Eingabetaste). |
| Dock «Protokoll» | Unten, nur im Modul «Chat-Bot». Zeit, Art (Command, Cooldown, Berechtigung, Verbindung, Sendefehler, Anmeldung), Meldung; letzte 500 Einträge. |
| Verbindung «Twitch» | Tipp mit Konto und Kanal, z. B. «Twitch: verbunden (donstvbot im Kanal donstv2020)». Grau bei «nicht eingerichtet: Client-ID fehlt» oder «… Bot-Konto nicht angemeldet». |

Die Docks «Chat» und «Protokoll» lassen sich verschieben und lösen, aber nicht schliessen. Die Layout-Version (`STATE_VERSION`) ist dafür auf 3 gestiegen; eine gespeicherte Dock-Anordnung aus P06 wird einmal verworfen.

## 5. Overlay-Gestaltung

| Element | Vorschlag |
|---|---|
| Hintergrund | transparent (Browserquelle) |
| Textfarbe | hell mit ausreichendem Kontrast auf Videohintergrund |
| Textstile | Comic, Comic dick, Schlicht, Ohne (aus overlay-game-tool) |
| Animationen | ruhige CSS-Animationen: Schweben, Atmen, Wiegen, Schreibmaschine, Schreibmaschine mit Löschen, Herzschlag |
| Schrift | Standard Be Vietnam Pro; pro Textquelle eine andere Schrift wählbar (installierte Schriften und eigene Schriftdateien) |
| Akzentfarbe, Schriftgrössen | [OFFEN] |

## 6. Barrierefreiheit

- Kontrast der Programmoberfläche mindestens 4,5:1 für normalen Text. [ANNAHME]

## 7. Offene Punkte

1. [OFFEN] Übernahmen aus B oder C in A (z. B. Vorlagen-Reiter aus C, Werkzeugleiste aus B)?
2. [OFFEN] Farbpalette und Logo («DonsTV»), jeweils für das dunkle und das helle Theme.
3. [OFFEN] Schriftwahl: Soll es zusätzlich eine globale Standardschrift für alle Overlays geben, die du ändern kannst, oder nur die Wahl pro Textquelle?
4. [OFFEN] Tastenkürzel.
5. [OFFEN] Die Docks unten in A sind schmal: Sollen sie in der Grösse veränderbar und verschiebbar sein (wie in OBS)? Stand des Codes (P08): Die Docks des Moduls «Overlays» lassen sich verschieben, lösen, schliessen und in der Grösse ändern (Qt-Docks); «Docks → Standardanordnung» stellt sie zurück.

## Quellen

- Schriftvorgabe: eigene Angabe des Nutzers.
- Textstile und Animationen: Repo https://github.com/donsimm/overlay-game-tool (`app/modules.py`).
- Aufbau Chat-Bot: https://docs.streamer.bot/guide/actions und https://streamer.bot/features
- Kontrastwert 4,5:1: WCAG 2.x, Erfolgskriterium 1.4.3 (https://www.w3.org/TR/WCAG21/#contrast-minimum).
