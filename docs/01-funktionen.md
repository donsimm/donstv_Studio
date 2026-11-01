# 01 – Funktionen und Anforderungen

Status: Entwurf 3 (ersetzt Entwurf 1 und 2). Die IDs in `02` bis `05` werden nach deiner Freigabe nachgeführt.

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

| ID | Anforderung | Prio | Quelle |
|---|---|---|---|
| F-01 | Hauptfenster im OBS-Stil: Menüleiste, Docks, Vorschaufläche, Statuszeile. | MUSS | Vorgabe |
| F-02 | Modulumschalter oben: «Overlays» und «Chat-Bot». | MUSS | Vorgabe |
| F-03 | Konfiguration als Datei speichern und laden, eigener Export und Import. | MUSS | |
| F-04 | Verbindungsstatus (Twitch, YouTube, OBS, NDI) jederzeit sichtbar, in einem festen Fensterkopf über allen Docks. YouTube hat im Gerüst keine echte Verbindung (F-55) und zeigt «getrennt, nicht eingerichtet». | MUSS | |
| F-68 | Leistungsanzeige (CPU, RAM, LAN) mit Verlauf der letzten 60 Sekunden im Fensterkopf, immer sichtbar, ohne Schalter. Werte des Studio-Laptops direkt aus `/proc`. | SOLL | Vorgabe, `docs/referenz/vorbild-leistungsanzeige.png` |
| F-69 | Leistungsdaten des Streaming-PCs aus OBS über die OBS-Verbindung (Anforderung `GetStats` von obs-websocket, ab v5.0.0). Achtung: `cpuUsage` und `memoryUsage` betreffen den OBS-Prozess, nicht den ganzen Rechner. Wird nicht gebaut. | KANN | Vorgabe; https://github.com/obsproject/obs-websocket/blob/master/docs/generated/protocol.md (Abschnitt GetStats) |
| F-05 | Programm kann beim Streamen im Hintergrund weiterlaufen und startet auf Wunsch automatisch. | SOLL | |
| F-06 | Einstellungen: Design der Programmoberfläche wählbar (dunkel oder hell). | MUSS | Vorgabe |
| F-07 | OBS-Anbindung (eine einzige Verbindung): erkennt den Szenenwechsel in OBS und stellt ihn als Ereignis «OBS-Szene gewechselt» für Overlays und Bot bereit; zeigt die aktive Szene an. | SOLL (wichtig) | Vorgabe |
| F-08 | Jeder Dienst (Twitch, YouTube, OBS, später weitere) wird über genau eine Verbindung angebunden und von Overlays und Bot gemeinsam genutzt. | MUSS | Vorgabe |

## 4. Modul «Overlays»

### 4.1 Overlays und Quellen (Gerüst)

| ID | Anforderung | Prio | Quelle |
|---|---|---|---|
| F-10 | Overlay-Liste (wie Szenen in OBS): anlegen, umbenennen, duplizieren, löschen. | MUSS | S1.2 |
| F-11 | Auflösung pro Overlay einstellbar (Breite × Höhe, Standard 1920×1080). | MUSS | S1.2 |
| F-12 | Quellen-Liste pro Overlay: hinzufügen, entfernen, Reihenfolge ändern, ein-/ausblenden. | MUSS | S1.4, S1.5 |
| F-13 | Vorschaufläche: Quellen per Maus verschieben, skalieren und drehen. | MUSS | S1.4 |
| F-14 | Eigenschaften-Dock: Position X/Y, Grösse, Drehung der gewählten Quelle. | MUSS | S1.4 |
| F-15 | Quelle «Text»: Inhalt, Farbe, Grösse, Schriftart (F-38), Stil (Comic, Comic dick, Schlicht, Ohne). | MUSS | S1.5 |
| F-16 | Quelle «Bild» mit Bibliothek (png, jpg, gif, webp, svg, webm; max. 25 MB; mehrfach verwendbar). | MUSS | S1.5, S1.6 |
| F-17 | Ausgabe als Browserquelle: pro Overlay eine URL, die in OBS eingefügt wird. | MUSS | S1.1 |
| F-18 | Speichern aktualisiert in OBS geöffnete Overlays sofort, ohne Neuladen. | MUSS | S1.4 |
| F-19 | Standardschrift (Hauptschrift) aller Overlays: Be Vietnam Pro, lokal eingebunden. | MUSS | S1.14 |
| F-38 | Schriftart pro Textquelle wählbar (installierte Schriften und Schriften aus F-39); Be Vietnam Pro bleibt der Standard. | MUSS | Vorgabe |
| F-39 | Eigene Schriftdateien hinzufügen (ttf, otf, woff2) und in der Bibliothek verwalten. | SOLL | Vorgabe |

### 4.2 Weitere Quellen und Funktionen (einzeln hinzufügbar)

| ID | Anforderung | Prio | Quelle |
|---|---|---|---|
| F-20 | Animationen pro Quelle: Schweben, Atmen, Wiegen (Text/Bild), Schreibmaschine, Schreibmaschine mit Löschen (nur Text), Herzschlag; Stärke einstellbar. | SOLL | S1.7 |
| F-21 | Quelle «Video/GIF» (webm, gif). | SOLL | S1.5 |
| F-22 | Quelle «Chat-Box» mit allen Anzeigefunktionen und Optionen. | SOLL | S1.10, S1.11, S2.2 |
| F-23 | Chat-Box: Verbindung nur aktiv, solange das Overlay in OBS offen ist; Zustand sichtbar. | SOLL | S1.12 |
| F-24 | Testereignisse ohne Twitch senden (z. B. Chat, Sub, Raid, Cheer). | SOLL | S1.13 |
| F-25 | Quelle «Alert-Box» (Follow, Sub, Spende, Raid, Cheer) mit Animation und Sound. | SOLL | S2.1 |
| F-26 | Quelle «Ereignisliste» mit Filter nach Eventtyp. | SOLL | S2.3 |
| F-27 | Quelle «Zielbalken» (Follower, Sub, Bits). | SOLL | S2.4 |
| F-28 | Quellen «Letzter Follow», «Letzter Sub», «Stream Labels» (z. B. Top-Spender). | SOLL | S1.15, S2.5 |
| F-29 | Overlay-Vorlagen: «Willkommen» und weitere fertige Overlays als Startpunkt. | SOLL | S1.9, S1.8, S2.10 |
| F-30 | Quelle «Tip Jar». | KANN | S2.6 |
| F-31 | Quelle «Abspann» (End Credits). | KANN | S2.7 |
| F-32 | Quelle «Glücksrad». | KANN | S2.8 |
| F-33 | Quelle «Media Share». | KANN | S2.9 |
| F-34 | Quelle «Logo-Loop». | KANN | S1.15 |
| F-35 | Quellen «Pflanze giessen» und «Katze streicheln» (Chat-/Kanalpunkte-Spiele). | KANN | S1.15 |
| F-36 | NDI-Ausgabe der Overlays mit Transparenz. Die Ausgabeart ist pro Overlay wählbar (Browserquelle oder NDI), siehe F-66. Die NDI-Ausgabe wird erst nach einem Machbarkeitstest auf dem Studio-Laptop gebaut. | KANN | S4.1, S4.2 |
| F-66 | Pro Overlay wählbare Ausgabeart «Browserquelle» oder «NDI». Das Gerüst enthält die Auswahl und die Browserquelle (URL im Heimnetz); NDI folgt mit F-36. | MUSS | Vorgabe |
| F-67 | Textquelle: Schriftgewicht und Ausrichtung (links, Mitte, rechts) einstellbar. Standard ist Gewicht 800 und Mitte (wie im overlay-game-tool). | SOLL | Vorgabe, P04c |
| F-37 | Weitere Plattform-Zielbalken (z. B. YouTube Super Chat). | KANN | S2.4 |

## 5. Modul «Chat-Bot»

### 5.1 Grundfunktionen (Gerüst)

| ID | Anforderung | Prio | Quelle |
|---|---|---|---|
| F-40 | Twitch-Anmeldung (OAuth), Token sicher speichern. | MUSS | S1.3, S3.22 |
| F-41 | Chat ansehen (Live-Ansicht im Programm). | MUSS | S3.15 |
| F-42 | Nachrichten in den Chat senden. | MUSS | S3.11 |
| F-43 | Commands verwalten: anlegen, bearbeiten, duplizieren, löschen, aktivieren/deaktivieren; Felder Name, Befehl, Berechtigung, Cooldown, Antwort. | MUSS | S3.6 |
| F-44 | Commands im Chat ausführen (Antwort senden, Cooldown beachten). | MUSS | S3.6 |
| F-45 | Protokoll der Bot-Aktivität. | MUSS | S3.3 |

### 5.2 Ausbau (einzeln hinzufügbar)

| ID | Anforderung | Prio | Quelle |
|---|---|---|---|
| F-46 | Aufbau wie Streamer.bot mit den Bereichen Actions, Commands, Timer, Queues, Einstellungen. | SOLL | S3.1–S3.3 |
| F-47 | Actions aus Sub-Actions, mit Gruppen, Queue-Wahl, Aktivierung. | SOLL | S3.1, S3.2 |
| F-48 | Queues (parallel und blockierend), Pending-Ansicht, Action History. | SOLL | S3.3 |
| F-49 | Variablen und Argumente, globale und Nutzer-Variablen. | SOLL | S3.5 |
| F-50 | Timer und geplante Ausführung. | SOLL | S3.7 |
| F-51 | Grundset an Triggers: Command, Follow, Sub, Cheer, Raid, Timer. | SOLL | S3.4 |
| F-52 | **Import der Gesamtkonfiguration einer früheren Streamer.bot-Installation** (Actions, Commands, Nutzerdaten). Tokens werden nicht importiert, Dienste werden neu verbunden. | SOLL (wichtig) | S3.20, S3.22 |
| F-53 | Import einzelner Actions (Community-Import). | SOLL | S3.21 |
| F-54 | Twitch-Ereignisse empfangen (Follow, Sub, Gift-Sub, Resub-Nachricht, Cheer, Raid) und an Overlays und Bot verteilen. | SOLL | |
| F-55 | YouTube-Anmeldung und Chat. | KANN | S1.3, S3.11 |
| F-56 | Kick-Anbindung. | KANN | S3.11 |
| F-57 | C#-Code-Actions. In der Architektur vorgesehen (austauschbarer Ausführungsbaustein), gebaut wird sie erst bei Bedarf. | KANN | S3.10 |
| F-64 | Overlay-Quellen an die aktive OBS-Szene koppeln (z. B. Quelle nur sichtbar, wenn OBS-Szene X aktiv ist); Bot-Trigger «OBS-Szene gewechselt». | SOLL | Vorgabe, F-07 |
| F-65 | Pixelgenaues Arbeiten im Overlay-Editor: Lage und Grösse in ganzen Pixeln der Overlay-Auflösung, Zahleneingabe, Pfeiltasten (1 px / 10 px), Hilfslinien, Einrasten, Raster, Lineale, Ausrichten/Verteilen, Zoom bis 1:1 und darüber, Anzeige der Pixelposition unter dem Zeiger. | MUSS | Vorgabe |
| F-70 | Eigenschaften-Dock: Inhaltsfelder der gewählten Quelle (Text, Farbe, Schriftgrösse, Schriftart, Stil der Textquelle; Bild wechseln). Die Daten und die Overlay-Seite gibt es seit P04 (F-15, F-16, F-38); P06 baut nur Lage, Grösse und Drehung. Beim Hinzufügen fragt der Editor lediglich den Text ab. | SOLL | P06 |
| F-71 | Editor: Verteilen (gleiche Abstände), Mehrfachauswahl, Entf-Taste für «Quelle entfernen», Alt-Taste schaltet Einrasten kurz aus, Rückgängig auch für Anlegen, Löschen und Reihenfolge, Hilfslinien mit Rückgängig. | KANN | P06 |
| F-58 | Hot Keys, Sprachsteuerung, MIDI. | KANN | S3.8 |
| F-59 | Credits-System und Quotes. | KANN | S3.9 |
| F-60 | OBS-Steuerung durch den Bot (Szenen, Quellen, Stream/Aufnahme). | KANN | S3.12 |
| F-61 | Integrationen (z. B. Discord, StreamElements, Ko-fi, Stream Deck). | KANN | S3.13 |
| F-62 | Eigene Schnittstellen (WebSocket-, HTTP-, UDP-Server). | KANN | S3.14 |
| F-63 | Decks (webbasierte Fernbedienung, auch für Moderatoren). | KANN | S3.16 |

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
