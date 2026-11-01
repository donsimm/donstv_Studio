# 05 – Prompt-Plan

Status: Entwurf 2. Gilt für das **Gerüst (Version 0.1)**. Die Prompts liegen unter `prompts/`. Jeder Prompt wird in einer eigenen Claude-Code-Sitzung ausgeführt, in der angegebenen Reihenfolge. Nach jedem Baustein prüfst du das Ergebnis, dann folgt der nächste.

## 1. Bausteine

| Nr. | Prompt-Datei | Inhalt | Funktionen |
|---|---|---|---|
| P01 | `P01-projektgeruest.md` | Repo-Aufbau, Werkzeuge, Tests, Dokumente ins Repo | – |
| P02 | `P02-kern-dienst.md` | Kern-Dienst, Ereignis-Bus, Speicher, Konfiguration, Verbindungs-Verwaltung (leer), lokale Schnittstelle | F-03, F-08 |
| P03 | `P03-overlay-modell.md` | Overlay, Quelle, Ausgabeart, Schnittstelle für Anlegen/Ändern | F-10, F-11, F-12, F-66 |
| P04 | `P04-overlay-server.md` | Overlay-Seite, Browserquelle-URL, Live-Aktualisierung, Quellen Text und Bild, Schrift | F-15, F-16, F-17, F-18, F-19, F-38 |
| P05 | `P05-oberflaeche.md` | Hauptfenster (Variante A), Modulumschalter, Docks, Statusleiste, Theme dunkel/hell | F-01, F-02, F-04, F-06 |
| P06 | `P06-editor-vorschau.md` | Vorschau mit QtWebEngine, Rahmen und Griffe, Eigenschaften, pixelgenau | F-13, F-14, F-65 |
| P07 | `P07-chatbot-geruest.md` | Twitch-Anmeldung, Chat ansehen und senden, Commands, Protokoll | F-40 bis F-45 (Bericht `docs/berichte/P07.md`) |

Nachträge und Korrekturen (in der Reihenfolge der Ausführung, Stand P08):

| Nr. | Prompt-Datei | Inhalt | Funktionen |
|---|---|---|---|
| P04b | `P04b-textstile.md` | Textstile aus overlay-game-tool unverändert übernommen | F-15 |
| P04c | keine (nur Commit `0544d68`) | Grundregel der Textquelle (Gewicht 800, Zeilenhöhe 1.15, zentriert), Be Vietnam Pro ExtraBold lokal | F-15, F-19 (F-67 als SOLL eingetragen) |
| P05b | `P05b-fensterkopf-und-stil.md` | Fester Fensterkopf, YouTube-Status, Dienst-Symbole, Standardanordnung, Stil nach OBS | F-01, F-02, F-04, F-06 |
| P05c | `P05c-leistungsanzeige.md` | Leistungsanzeige (CPU, RAM, LAN) im Fensterkopf, Symbole in Textfarbe, PNG vor SVG | F-68, F-04 |
| P06c | `P06c-laptop-befunde.md` | Befunde vom Laptop: PNG-Testsymbole, sichtbare Fehler im Unterprozess-Test, Freigabe-Reihenfolge von QtWebEngine | F-01, F-04, F-65 (Bericht `docs/berichte/P06c.md`) |
| P08 | `P08-aufraeumen.md` | Aufräumen ohne Verhaltensänderung: Signale nach Regel 12, toter und doppelter Code, `ruff format`, Dokumente gegen Code, Testdauer | – (Bericht `docs/berichte/P08.md`) |

Berichte zu P01 bis P06 wurden nur im Chat geliefert; ab P06c liegen sie unter `docs/berichte/`.

Danach (nicht Teil des Gerüsts, einzeln beauftragen): OBS-Anbindung (nächster Baustein nach P08) mit Szenenwechsel (F-07, F-64), Machbarkeitstests T-01 bis T-04 aus `03-hardware-netzwerk.md`, NDI (F-36), Streamer.bot-Import (F-52), Animationen und weitere Quellen.

## 2. Abhängigkeiten

P01 → P02 → P03 → P04 → P06, P05 → P06, P02 → P07. P05 und P07 können nach P02 getrennt laufen.

## 3. Was du bereitstellen musst

| Wofür | Was | Wann |
|---|---|---|
| P04 | Schriftdateien Be Vietnam Pro (Lizenz prüfen und im Repo vermerken) | Claude Code lädt sie, wenn das Netz es erlaubt; sonst legst du sie ab |
| P07 | Twitch-Entwickler-Anwendung (Client-ID) auf dev.twitch.tv; Kanalname; Entscheid: gleiches Konto für Bot und Streamer oder getrenntes Bot-Konto | vor P07 |
| F-07 | OBS: obs-websocket einschalten, Passwort setzen, Port 4455 in der Firewall des Streaming-PCs freigeben | vor dem OBS-Baustein |
| F-52 | Export oder Ordner `data` der alten Streamer.bot-Installation | vor dem Import-Baustein |

## 4. Abnahme je Baustein

Der Abschlussbericht der Sitzung (siehe `CLAUDE.md`, Regel 11) wird von dir gelesen. Du startest die Software, wo der Prompt es verlangt, und bestätigst die Abnahmekriterien. Erst danach wird der nächste Prompt gestartet.

## 5. Annahmen, die du bestätigen musst

1. Bezeichner im Code englisch, Kommentare deutsch.
2. Python-Paketname `donstv_studio`, Quellordner `src/`.
3. Overlay-Server standardmässig im Heimnetz erreichbar (nicht nur lokal), mit Token pro Overlay.
4. Lizenz des Projekts: noch nicht festgelegt (Frage zum Verkauf bleibt offen).

## Quellen

- Anforderungen und Technik: `docs/01` bis `docs/04`.
- Twitch-Entwicklerkonsole: https://dev.twitch.tv/console
- obs-websocket: https://github.com/obsproject/obs-websocket
