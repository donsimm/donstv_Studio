# 01 – Funktionen und Anforderungen

Status: Entwurf 3 (ersetzt Entwurf 1 und 2). Die IDs in `02` bis `05` werden nach deiner Freigabe nachgeführt.

Spalte «Stand (P08)»: Abgleich mit dem Code am 1. November 2026 (Baustein P08). «gebaut» = Anforderung umgesetzt und mit Tests belegt; «teilweise» = nur der genannte Teil; «offen» = nicht gebaut.

## 1. Zielbild

`donstv_Studio` ist eine Desktop-Anwendung im Stil von OBS Studio mit zwei Modulen, die über einen Umschalter oben erreichbar sind:

1. **Overlays**: aufgebaut wie OBS. Ein **Overlay** entspricht einer **Szene**. Es wird aus **Quellen** (Text, Bild, Chat-Box, Alert-Box usw.) zusammengesetzt. Die Ausgabe erfolgt als Browserquelle, später zusätzlich über NDI.
2. **Chat-Bot**: aufgebaut wie Streamer.bot (Actions, Commands, Timer, Queues). Daten aus einer früheren Streamer.bot-Installation sollen importierbar sein.

Vorgehen: Zuerst wird ein **Gerüst** gebaut. Funktionen werden danach einzeln hinzugefügt.

[OFFEN] Ein Satz, was die Software am Ende leisten soll, in deinen Worten.

## 2. Prioritäten

| Stufe | Bedeutung |
|---|---|
| MUSS | Gehört zum Gerüst (Version 0.1) |
| SOLL | Erste Ausbaustufe (Version 1.0), einzeln hinzufügbar |
| KANN | Später, nur bei Bedarf |

Die Spalte «Quelle» verweist auf die Nummern aus der Funktionsliste (S1 overlay-game-tool, S2 Streamlabs, S3 Streamer.bot, S4 NDI).

## 3. Anwendung (Gerüst)

| ID | Anforderung | Prio | Quelle | Stand (P08) |
|---|---|---|---|---|
| F-01 | Hauptfenster im OBS-Stil: Menüleiste, Docks, Vorschaufläche, Statuszeile. | MUSS | Vorgabe | gebaut (P05, P05b, P06) |
| F-02 | Modulumschalter oben: «Overlays» und «Chat-Bot». | MUSS | Vorgabe | gebaut (P05, P07) |
| F-03 | Konfiguration als Datei speichern und laden, eigener Export und Import. | MUSS | | teilweise: Export und Import über die Schnittstelle (`/config/export`, `/config/import`); kein Menüpunkt in der Oberfläche |
| F-04 | Verbindungsstatus (Twitch, YouTube, OBS, NDI) jederzeit sichtbar, in einem festen Fensterkopf über allen Docks. YouTube hat im Gerüst keine echte Verbindung (F-55) und zeigt «getrennt, nicht eingerichtet». | MUSS | | gebaut (P05b): Twitch echt (P07), YouTube immer «nicht eingerichtet», OBS und NDI ohne Verbindung im Kern (unbekannt) |
| F-68 | Leistungsanzeige (CPU, RAM, LAN) mit Verlauf der letzten 60 Sekunden im Fensterkopf, immer sichtbar, ohne Schalter. Werte des Studio-Laptops direkt aus `/proc`. | SOLL | Vorgabe, `docs/referenz/vorbild-leistungsanzeige.png` | gebaut (P05c) |
| F-69 | Leistungsdaten des Streaming-PCs aus OBS über die OBS-Verbindung (Anforderung `GetStats` von obs-websocket, ab v5.0.0). Achtung: `cpuUsage` und `memoryUsage` betreffen den OBS-Prozess, nicht den ganzen Rechner. Wird nicht gebaut. | KANN | Vorgabe; https://github.com/obsproject/obs-websocket/blob/master/docs/generated/protocol.md (Abschnitt GetStats) | offen (wird nicht gebaut) |
| F-05 | Programm kann beim Streamen im Hintergrund weiterlaufen und startet auf Wunsch automatisch. | SOLL | | teilweise: Kern läuft ohne Oberfläche, Vorlage `packaging/donstv-core.service` (`systemd --user`); kein automatischer Start eingerichtet |
| F-06 | Einstellungen: Design der Programmoberfläche wählbar (dunkel oder hell). | MUSS | Vorgabe | gebaut (P05) |
| F-07 | OBS-Anbindung (eine einzige Verbindung): erkennt den Szenenwechsel in OBS und stellt ihn als Ereignis «OBS-Szene gewechselt» für Overlays und Bot bereit; zeigt die aktive Szene an. | SOLL (wichtig) | Vorgabe | offen (nächster Baustein) |
| F-08 | Jeder Dienst (Twitch, YouTube, OBS, später weitere) wird über genau eine Verbindung angebunden und von Overlays und Bot gemeinsam genutzt. | MUSS | Vorgabe | gebaut (P02, P07): eine Verbindung je Dienst im Verbindungs-Verwalter; bisher nur Twitch echt |

## 4. Modul «Overlays»

### 4.1 Overlays und Quellen (Gerüst)

| ID | Anforderung | Prio | Quelle | Stand (P08) |
|---|---|---|---|---|
| F-10 | Overlay-Liste (wie Szenen in OBS): anlegen, umbenennen, duplizieren, löschen. | MUSS | S1.2 | gebaut (P03, P06) |
| F-11 | Auflösung pro Overlay einstellbar (Breite × Höhe, Standard 1920×1080). | MUSS | S1.2 | teilweise: Kern und Schnittstelle (P03); in der Oberfläche keine Eingabe der Auflösung |
| F-12 | Quellen-Liste pro Overlay: hinzufügen, entfernen, Reihenfolge ändern, ein-/ausblenden. | MUSS | S1.4, S1.5 | gebaut (P03, P06) |
| F-13 | Vorschaufläche: Quellen per Maus verschieben, skalieren und drehen. | MUSS | S1.4 | gebaut (P06) |
| F-14 | Eigenschaften-Dock: Position X/Y, Grösse, Drehung der gewählten Quelle. | MUSS | S1.4 | gebaut (P06) |
| F-15 | Quelle «Text»: Inhalt, Farbe, Grösse, Schriftart (F-38), Stil (Comic, Comic dick, Schlicht, Ohne). | MUSS | S1.5 | teilweise: Kern und Overlay-Seite (P04, P04b, P04c); in der Oberfläche nur der Text beim Anlegen (F-70) |
| F-16 | Quelle «Bild» mit Bibliothek (png, jpg, gif, webp, svg, webm; max. 25 MB; mehrfach verwendbar). | MUSS | S1.5, S1.6 | gebaut (P04, P06: «Bild …» in Quellen) |
| F-17 | Ausgabe als Browserquelle: pro Overlay eine URL, die in OBS eingefügt wird. | MUSS | S1.1 | gebaut (P04) |
| F-18 | Speichern aktualisiert in OBS geöffnete Overlays sofort, ohne Neuladen. | MUSS | S1.4 | gebaut (P04) |
| F-19 | Standardschrift (Hauptschrift) aller Overlays: Be Vietnam Pro, lokal eingebunden. | MUSS | S1.14 | gebaut (P04, P04c) |
| F-38 | Schriftart pro Textquelle wählbar (installierte Schriften und Schriften aus F-39); Be Vietnam Pro bleibt der Standard. | MUSS | Vorgabe | teilweise: Kern und Seite (Feld `font`, Liste über `fc-list`); keine Auswahl in der Oberfläche (F-70) |
| F-39 | Eigene Schriftdateien hinzufügen (ttf, otf, woff2) und in der Bibliothek verwalten. | SOLL | Vorgabe | offen |

### 4.2 Weitere Quellen und Funktionen (einzeln hinzufügbar)

| ID | Anforderung | Prio | Quelle | Stand (P08) |
|---|---|---|---|---|
| F-20 | Animationen pro Quelle: Schweben, Atmen, Wiegen (Text/Bild), Schreibmaschine, Schreibmaschine mit Löschen (nur Text), Herzschlag; Stärke einstellbar. | SOLL | S1.7 | offen |
| F-21 | Quelle «Video/GIF» (webm, gif). | SOLL | S1.5 | offen |
| F-22 | Quelle «Chat-Box» mit allen Anzeigefunktionen und Optionen. | SOLL | S1.10, S1.11, S2.2 | offen |
| F-23 | Chat-Box: Verbindung nur aktiv, solange das Overlay in OBS offen ist; Zustand sichtbar. | SOLL | S1.12 | offen |
| F-24 | Testereignisse ohne Twitch senden (z. B. Chat, Sub, Raid, Cheer). | SOLL | S1.13 | offen |
| F-25 | Quelle «Alert-Box» (Follow, Sub, Spende, Raid, Cheer) mit Animation und Sound. | SOLL | S2.1 | offen |
| F-26 | Quelle «Ereignisliste» mit Filter nach Eventtyp. | SOLL | S2.3 | offen |
| F-27 | Quelle «Zielbalken» (Follower, Sub, Bits). | SOLL | S2.4 | offen |
| F-28 | Quellen «Letzter Follow», «Letzter Sub», «Stream Labels» (z. B. Top-Spender). | SOLL | S1.15, S2.5 | offen |
| F-29 | Overlay-Vorlagen: «Willkommen» und weitere fertige Overlays als Startpunkt. | SOLL | S1.9, S1.8, S2.10 | offen |
| F-30 | Quelle «Tip Jar». | KANN | S2.6 | offen |
| F-31 | Quelle «Abspann» (End Credits). | KANN | S2.7 | offen |
| F-32 | Quelle «Glücksrad». | KANN | S2.8 | offen |
| F-33 | Quelle «Media Share». | KANN | S2.9 | offen |
| F-34 | Quelle «Logo-Loop». | KANN | S1.15 | offen |
| F-35 | Quellen «Pflanze giessen» und «Katze streicheln» (Chat-/Kanalpunkte-Spiele). | KANN | S1.15 | offen |
| F-36 | NDI-Ausgabe der Overlays mit Transparenz. Die Ausgabeart ist pro Overlay wählbar (Browserquelle oder NDI), siehe F-66. Die NDI-Ausgabe wird erst nach einem Machbarkeitstest auf dem Studio-Laptop gebaut. | KANN | S4.1, S4.2 | offen |
| F-66 | Pro Overlay wählbare Ausgabeart «Browserquelle» oder «NDI». Das Gerüst enthält die Auswahl und die Browserquelle (URL im Heimnetz); NDI folgt mit F-36. | MUSS | Vorgabe | gebaut (P03, P06): Auswahl im Dock «Steuerung»; NDI wird gespeichert, ist aber «nicht verfügbar» |
| F-67 | Textquelle: Schriftgewicht und Ausrichtung (links, Mitte, rechts) einstellbar. Standard ist Gewicht 800 und Mitte (wie im overlay-game-tool). | SOLL | Vorgabe, P04c | teilweise: fester Standard Gewicht 800 und Mitte (P04c); nicht einstellbar |
| F-37 | Weitere Plattform-Zielbalken (z. B. YouTube Super Chat). | KANN | S2.4 | offen |

## 5. Modul «Chat-Bot»

### 5.1 Grundfunktionen (Gerüst)

| ID | Anforderung | Prio | Quelle | Stand (P08) |
|---|---|---|---|---|
| F-40 | Twitch-Anmeldung (OAuth), Token sicher speichern. | MUSS | S1.3, S3.22 | gebaut (P07), mit echtem Twitch nicht geprüft |
| F-41 | Chat ansehen (Live-Ansicht im Programm). | MUSS | S3.15 | gebaut (P07), mit echtem Twitch nicht geprüft |
| F-42 | Nachrichten in den Chat senden. | MUSS | S3.11 | gebaut (P07), mit echtem Twitch nicht geprüft |
| F-43 | Commands verwalten: anlegen, bearbeiten, duplizieren, löschen, aktivieren/deaktivieren; Felder Name, Befehl, Berechtigung, Cooldown, Antwort. | MUSS | S3.6 | gebaut (P07); «Importieren» gesperrt |
| F-44 | Commands im Chat ausführen (Antwort senden, Cooldown beachten). | MUSS | S3.6 | gebaut (P07), mit echtem Twitch nicht geprüft |
| F-45 | Protokoll der Bot-Aktivität. | MUSS | S3.3 | gebaut (P07) |

### 5.2 Ausbau (einzeln hinzufügbar)

| ID | Anforderung | Prio | Quelle | Stand (P08) |
|---|---|---|---|---|
| F-46 | Aufbau wie Streamer.bot mit den Bereichen Actions, Commands, Timer, Queues, Einstellungen. | SOLL | S3.1–S3.3 | offen |
| F-47 | Actions aus Sub-Actions, mit Gruppen, Queue-Wahl, Aktivierung. | SOLL | S3.1, S3.2 | offen |
| F-48 | Queues (parallel und blockierend), Pending-Ansicht, Action History. | SOLL | S3.3 | offen |
| F-49 | Variablen und Argumente, globale und Nutzer-Variablen. | SOLL | S3.5 | offen |
| F-50 | Timer und geplante Ausführung. | SOLL | S3.7 | offen |
| F-51 | Grundset an Triggers: Command, Follow, Sub, Cheer, Raid, Timer. | SOLL | S3.4 | offen |
| F-52 | **Import der Gesamtkonfiguration einer früheren Streamer.bot-Installation** (Actions, Commands, Nutzerdaten). Tokens werden nicht importiert, Dienste werden neu verbunden. | SOLL (wichtig) | S3.20, S3.22 | offen |
| F-53 | Import einzelner Actions (Community-Import). | SOLL | S3.21 | offen |
| F-54 | Twitch-Ereignisse empfangen (Follow, Sub, Gift-Sub, Resub-Nachricht, Cheer, Raid) und an Overlays und Bot verteilen. | SOLL | | offen |
| F-55 | YouTube-Anmeldung und Chat. | KANN | S1.3, S3.11 | offen |
| F-56 | Kick-Anbindung. | KANN | S3.11 | offen |
| F-57 | C#-Code-Actions. In der Architektur vorgesehen (austauschbarer Ausführungsbaustein), gebaut wird sie erst bei Bedarf. | KANN | S3.10 | offen |
| F-64 | Overlay-Quellen an die aktive OBS-Szene koppeln (z. B. Quelle nur sichtbar, wenn OBS-Szene X aktiv ist); Bot-Trigger «OBS-Szene gewechselt». | SOLL | Vorgabe, F-07 | offen |
| F-72 | Sendebegrenzung des Bots nach den Twitch-Grenzen (Nachrichten pro 30 Sekunden, abhängig von Moderatorenstatus), mit Warteschlange statt Verwerfen. Aus P07, dort nicht gebaut. | SOLL | P07 | offen |
| F-73 | Anmeldung des Hauptkanals (Rolle «broadcaster») für Ereignisse, die eine Berechtigung des Kanals brauchen (F-54). Im Gerüst nicht nötig (siehe `docs/berichte/P07.md`). | SOLL | P07 | offen (Ablage nach Rolle vorbereitet) |
| F-65 | Pixelgenaues Arbeiten im Overlay-Editor: Lage und Grösse in ganzen Pixeln der Overlay-Auflösung, Zahleneingabe, Pfeiltasten (1 px / 10 px), Hilfslinien, Einrasten, Raster, Lineale, Ausrichten/Verteilen, Zoom bis 1:1 und darüber, Anzeige der Pixelposition unter dem Zeiger. | MUSS | Vorgabe | gebaut (P06); Verteilen gehört zu F-71 |
| F-70 | Eigenschaften-Dock: Inhaltsfelder der gewählten Quelle (Text, Farbe, Schriftgrösse, Schriftart, Stil der Textquelle; Bild wechseln). Die Daten und die Overlay-Seite gibt es seit P04 (F-15, F-16, F-38); P06 baut nur Lage, Grösse und Drehung. Beim Hinzufügen fragt der Editor lediglich den Text ab. | SOLL | P06 | offen |
| F-71 | Editor: Verteilen (gleiche Abstände), Mehrfachauswahl, Entf-Taste für «Quelle entfernen», Alt-Taste schaltet Einrasten kurz aus, Rückgängig auch für Anlegen, Löschen und Reihenfolge, Hilfslinien mit Rückgängig. | KANN | P06 | offen |
| F-74 | Quellen umbenennen: Rechtsklick «Umbenennen», Taste F2 und Feld «Name» im Dock «Eigenschaften». Der Name ist nur eine Bezeichnung, die Ausgabe ändert sich nicht. Doppelklick ist für das Quellenfenster (F-79) reserviert. | MUSS | Nutzer (P06) | offen (P06d) |
| F-75 | Zeigerposition (X/Y in Overlay-Pixeln) links unten in der Vorschaufläche, von Qt über der Webansicht gezeichnet; aus der Statuszeile entfernt. Ausserhalb der Fläche «–». | MUSS | Nutzer, F-65 | offen (P06d) |
| F-76 | Bedienelemente in beiden Themes gut erkennbar: Häkchen, Pfeile der Zahlenfelder und Listen, Rahmen von Eingabefeldern. Kontrast mindestens 3:1 gegen den Untergrund (Text bleibt 4.5:1). Symbole werden ohne Qt-SVG-Modul gezeichnet. | MUSS | Nutzer | offen (P06d) |
| F-77 | Bildquellen: Eckgriffe behalten das Seitenverhältnis, die Umschalttaste löst es. Beim Anlegen passt der Rahmen zum Seitenverhältnis des Bildes. | MUSS | Nutzer | offen (P06d) |
| F-78 | Leistungsanzeige: CPU, RAM und LAN sind gleich breit und bleiben es bei jedem Wert (Fensterkopf verschiebt sich nie). | MUSS | Nutzer, F-68 | offen (P06d) |
| F-79 | Quellenfenster: Doppelklick auf eine Quelle (Liste oder Vorschau) öffnet ein eigenes, nicht blockierendes Fenster mit allen Einstellungen der Quellenart ausser der Transformation. Änderungen wirken sofort und sind rückgängig machbar (kein OK/Abbrechen). Textquelle: Text, Schrift, Grösse, Farbe, Stil, Rand, Schatten, Gewicht und Ausrichtung (F-67). Bildquelle: Bild wechseln, «Einpassen / Füllen / Strecken / Original». | MUSS | Nutzer | offen (P06f) |
| F-80 | Transformation (X, Y, Breite, Höhe, Drehung) gilt für alle Quellenarten; «Kopieren» und «Einfügen» übertragen alle fünf Werte auf eine andere Quelle (gesperrte Quellen lehnen das Einfügen ab). Rückgängig macht es zurück. | MUSS | Nutzer | offen (P06e) |
| F-81 | Quellen sperren: Schloss neben dem Auge. Gesperrt = Transformation nicht änderbar (Maus, Tasten, Felder, Ausrichten, Einfügen, Rückgängig), in der Vorschau nicht wählbar (Klick geht durch), in der Liste wählbar. Name, Sichtbarkeit, Löschen (mit Rückfrage), Reihenfolge und das Quellenfenster bleiben möglich. Kopie einer gesperrten Quelle ist entsperrt. Wird gespeichert. | MUSS | Nutzer | offen (P06e) |
| F-82 | Ausgabe pro Overlay mit zwei getrennten Schaltern «Browserquelle» (Standard an) und «NDI» (Standard aus, gesperrt bis F-36). Browserquelle aus: Overlay-Server liefert dieses Overlay nicht aus, die Editor-Vorschau funktioniert weiter. Ersetzt die Auswahl aus F-66; `output` wird zur Liste (Migration). | MUSS | Nutzer, F-66 | offen (P06e) |
| F-83 | Leinwandgrösse pro Overlay im Dock «Steuerung» einstellbar: Breite 1 bis 1920, Höhe 1 bis 1080, ganze Pixel, Auswahl gängiger Grössen, Hinweis für die Browserquelle in OBS. Quellen bleiben unverändert. Höchstwerte als einzelne Konstante. | MUSS | Nutzer, F-11 | offen (P06e) |
| F-84 | Zahlenwerte im Dock «Eigenschaften» als «Feld ist Regler» (Balken im Feld): Ziehen ändert, Klick tippt, Umschalt = Einerschritte, Pfeiltasten ±1 / ±10, Reset-Schaltfläche pro Feld (Drehung 0°, Grösse = ursprüngliche Grösse der Quelle, X/Y zentriert). Gleiches Bauteil später im Quellenfenster. | MUSS | Nutzer | offen (P06e) |
| F-58 | Hot Keys, Sprachsteuerung, MIDI. | KANN | S3.8 | offen |
| F-59 | Credits-System und Quotes. | KANN | S3.9 | offen |
| F-60 | OBS-Steuerung durch den Bot (Szenen, Quellen, Stream/Aufnahme). | KANN | S3.12 | offen |
| F-61 | Integrationen (z. B. Discord, StreamElements, Ko-fi, Stream Deck). | KANN | S3.13 | offen |
| F-62 | Eigene Schnittstellen (WebSocket-, HTTP-, UDP-Server). | KANN | S3.14 | offen |
| F-63 | Decks (webbasierte Fernbedienung, auch für Moderatoren). | KANN | S3.16 | offen |

## 6. Nicht-funktionale Anforderungen

| ID | Anforderung |
|---|---|
| N-01 | Ereignis (Twitch) bis Anzeige im Overlay: Ziel unter 2 s. [ANNAHME] |
| N-02 | Läuft stabil während Streams von mehreren Stunden ohne manuellen Neustart. |
| N-03 | Keine Secrets im Repo; Tokens in der Schlüsselverwaltung des Betriebssystems. |
| N-04 | Verbindungsabbrüche werden automatisch wiederhergestellt und im UI angezeigt. |
| N-05 | Logdateien mit Rotation. |
| N-06 | Overlay-Server nur lokal erreichbar; schreibende Anfragen fremder Webseiten werden abgelehnt (aus overlay-game-tool übernommen). |

## 7. Gestrichen gegenüber Entwurf 1

Folgende Punkte hatte ich aus deinem Setup abgeleitet, du hast sie nicht verlangt. Sie sind nicht mehr enthalten: Statusanzeige RØDECaster, ATEM-Mini-Integration, OBS-Dock, separater Moduleditor mit Manifest-Optionen als eigene Oberfläche (ersetzt durch Quellen und Eigenschaften nach OBS-Vorbild).

## 8. Offene Punkte

1. [OFFEN] Gesamtziel in einem Satz.
2. [OFFEN] Soll der Bot importierte Actions ausführen können (F-52, Umfang von F-47 bis F-57)? Das bestimmt den Aufwand des Moduls.
3. [OFFEN] Spenden, Tip Jar und Merch (F-25, F-30) brauchen einen Zahlungsdienst: gewünscht?
4. [ENTSCHIEDEN] NDI und Browserquelle sind pro Overlay wählbar (F-66), auch beides gleichzeitig.
5. [OFFEN] Soll die Software später verkauft oder veröffentlicht werden?
6. [OFFEN] Streamer.bot-Export deiner alten Installation (Ordner `data` oder Backup-`.zip`) für F-52 bereitstellen.
