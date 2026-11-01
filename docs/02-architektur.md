# 02 – Architektur und Technik

Status: Entwurf 2. Entschieden vom Nutzer: Oberfläche mit Qt 6 und QtWebEngine; Software läuft auf dem Studio-Laptop (Debian 13), OBS auf dem Streaming-PC (Nobara); Verbindungen nur einmal; Ausgabe pro Overlay als Browserquelle oder NDI wählbar. Alles andere ist [ANNAHME] und wird mit dir bestätigt.

## 1. Übersicht

```
 Studio-Laptop (Debian 13)                                     Streaming-PC (Nobara)
┌──────────────────────────────────────────────┐              ┌───────────────────────┐
│ Oberfläche (Qt 6, QtWebEngine)               │              │ OBS                   │
│   Docks, Vorschau, Editor                    │              │  Browserquelle ──────────── HTTP/WS ──┐
│        │ lokal (127.0.0.1)                   │              │  NDI-Quelle  ◄────────────── NDI ─────┤
│        ▼                                     │              │  obs-websocket (4455) ◄───┐           │
│ Kern-Dienst (Python, asyncio)                │              └───────────────────────┘ │           │
│   Verbindungen: Twitch | YouTube | OBS ──────┼────────────────────────────────────────┘           │
│        ▼                                     │                                                    │
│   Ereignis-Bus                               │                                                    │
│    ├─ Overlay-Server (HTTP + WebSocket) ─────┼────────────────────────────────────────────────────┘
│    ├─ Bot (Commands, später Actions)         │
│    ├─ Speicher (SQLite)                      │
│    └─ Ausführungs-Schnittstelle (C# später)  │
│ Renderer-Prozess (Qt offscreen) → NDI [später]│
└──────────────────────────────────────────────┘
```

## 2. Bausteine

| Baustein | Aufgabe | Bemerkung |
|---|---|---|
| Kern-Dienst | Enthält Verbindungen, Ereignis-Bus, Overlay-Server, Bot, Speicher. Läuft ohne Oberfläche weiter. | Start als Benutzerdienst (`systemd --user`) mit automatischem Neustart [ANNAHME] |
| Oberfläche | Nur Bedienteil: Docks, Editor, Vorschau, Chat-Ansicht. Spricht lokal mit dem Kern. | Qt 6 mit QtWebEngine (entschieden). Bei Absturz läuft der Kern weiter. |
| Verbindungen (F-08) | Genau eine Verbindung pro Dienst: Twitch, YouTube, OBS, später weitere. | Zugangsdaten an einer Stelle |
| Ereignis-Bus | Verbindungen veröffentlichen normierte Ereignisse; Overlays, Bot und Oberfläche abonnieren sie. | Jedes Ereignis hat Kennung, Zeit, Quelle, Art, Nutzlast; doppelte Kennungen werden verworfen |
| Overlay-Server | Liefert jedes Overlay als Webseite und sendet Live-Daten per WebSocket. | Lauscht im Heimnetz, Token pro Overlay |
| Bot | Chat lesen und senden, Commands verwalten und ausführen (Gerüst). | Actions, Queues, Timer später |
| Ausführungs-Schnittstelle (F-57) | «Aktion ausführen» als austauschbarer Baustein. | C# nur vorgesehen: später getrennter .NET-Prozess, nur bei Bedarf |
| Renderer (F-36) | Zeichnet Overlays ohne Fenster (Qt offscreen) und sendet sie per NDI. | Erst nach Machbarkeitstest T-03 |
| Speicher | SQLite; automatische Sicherung der Konfiguration. | [ANNAHME] |

## 3. Datenmodell (Gerüst)

| Objekt | Felder |
|---|---|
| Overlay | Kennung, Name, Breite, Höhe (Standard 1920×1080), Ausgabeart (`browser` oder `ndi`), Token, Quellenliste |
| Quelle | Kennung, Art (Text, Bild, Chat-Box, Alert-Box …), x, y, Breite, Höhe (**ganze Pixel**, F-65), Drehung in Grad, Reihenfolge, sichtbar, optional sichtbar nur bei OBS-Szene (F-64), Eigenschaften je Art |
| Ereignis | Kennung, Zeit, Quelle, Art (z. B. `twitch.chat.message`, `obs.scene.changed`, `connection.status`), Nutzlast |
| Command | Name, Befehl, Berechtigung, Cooldown global/pro Nutzer, Antwort, aktiv |

## 4. Oberfläche und Darstellung

- Hauptfenster mit andockbaren Bereichen nach Variante A (`04-ui-design.md`).
- Vorschau: QtWebEngine lädt dieselbe Overlay-Seite wie die Browserquelle. Qt zeichnet Rahmen und Griffe darüber. Darstellung wird mit T-02 gegen OBS geprüft.
- Pixelgenau (F-65): ganze Pixel, Zoom 1:1 und mehr, Zahleneingabe, Pfeiltasten, Hilfslinien, Einrasten, Lineale.
- Vorschau-Bildrate begrenzbar, weil der Laptop schwach ist (T-01).

## 5. OBS-Anbindung (F-07, F-64)

- obs-websocket 5.x auf dem Streaming-PC, Port 4455, Passwort.
- Ereignisse abonnieren: Szenen (`CurrentProgramSceneChanged`, bei Studio-Modus `CurrentPreviewSceneChanged`), Szenenliste, Szenensammlung, Ausgaben (Streaming/Aufnahme), Beenden (`ExitStarted`).
- Beim Verbinden und nach jedem Wiederverbinden die aktive Szene abfragen. Wiederverbinden mit wachsender Wartezeit.
- Das Ereignis `obs.scene.changed` geht auf den Ereignis-Bus; Overlays und Bot lesen es dort.

## 6. Ausgabe pro Overlay (F-66, F-36)

| Ausgabeart | Wer zeichnet | Wo | Stand |
|---|---|---|---|
| Browserquelle | OBS (CEF) | Streaming-PC | Gerüst |
| NDI | Renderer-Prozess | Laptop | nach T-03 |

Beide Arten nutzen dieselbe Overlay-Seite. Ob ein Overlay beides gleichzeitig ausgeben darf, ist offen.

## 7. Technikwahl

| Bereich | Wahl | Status |
|---|---|---|
| Oberfläche | Qt 6, QtWebEngine | entschieden |
| Sprache Kern und Oberfläche | Python 3 (Debian 13 liefert 3.13.5), PyQt6 | [ANNAHME] |
| Kern-Server | FastAPI mit Uvicorn, asyncio | [ANNAHME] |
| Overlay-Seiten | HTML, CSS, JavaScript je Quellenart, Be Vietnam Pro lokal | Schrift: Vorgabe |
| Speicher | SQLite | [ANNAHME] |
| Zugangsdaten | Schlüsselbund (`keyring`) mit Ersatz, falls auf Debian nicht verfügbar | [ANNAHME], prüfen |
| Pakete | Soweit möglich aus Debian (Sicherheitsupdates), sonst `pip` in einer virtuellen Umgebung | [ANNAHME], Verfügbarkeit von PyQt6/QtWebEngine in Debian 13 vor Baubeginn prüfen |
| Tests | pytest; Machbarkeitstests T-01 bis T-04 | [ANNAHME] |

## 8. Offene Punkte

1. [ENTSCHIEDEN] Getrennter Kern-Dienst und Oberfläche.
2. [ENTSCHIEDEN] Ein Overlay darf Browserquelle und NDI gleichzeitig ausgeben (Datenmodell: `output` wird bei NDI-Ausbau zur Liste; im Gerüst P03 genügt ein Wert, die Änderung ist eine Migration).
3. [ENTSCHIEDEN] Der Laptop kann später durch bessere Hardware (Intel-Prozessor, Nvidia-Grafikkarte) ersetzt werden. Bildrate, Auflösung und Hardware-Beschleunigung von Vorschau und Renderer sind einstellbar und nicht auf den i7-4500U ausgelegt.
4. [ERLEDIGT] Auf dem Studio-Laptop (Debian 13, `apt-cache policy`, Quelle http://deb.debian.org/debian trixie/main amd64): `python3-pyqt6` 6.9.0-2 und `python3-pyqt6.qtwebengine` 6.9.0-1 sind als Installationskandidaten verfügbar. Noch nicht installiert und nicht getestet (T-01). Ebenso verfügbar (gleiche Quelle): python3-fastapi 0.115.11-4, python3-uvicorn 0.32.0-3, python3-websockets 15.0.1-1, python3-keyring 25.6.0-2, python3-httpx 0.28.1-1. Versionen von starlette und pydantic in Debian 13: noch nicht bekannt. Die Installation mit `pip install -e '.[dev]'` auf dem Laptop (Debian-Pakete, `--system-site-packages`) hat keine dieser Pakete nachgeladen.
5. [OFFEN] NDI-SDK: Lizenzbedingungen und Linux-Bezug prüfen (Hinweis «NDI® is a registered trademark of Vizrt NDI AB»).
6. [OFFEN] Zugangsdaten-Speicher auf dem Laptop (X11, ohne Desktop-Schlüsselbund?).

## Quellen

- obs-websocket-Protokoll: https://github.com/obsproject/obs-websocket/blob/release/5.0.0/docs/generated/protocol.md
- NDI-Dokumentation: https://docs.ndi.video/all/developing-with-ndi/sdk/performance-and-implementation und https://docs.ndi.video/docs/white-paper/bandwidth/ndi-high-bandwidth-based-on-speedhq7-8bit-4-2-2-4
- Python-Version auf dem Laptop (3.13.5): Datei `hardware-report.txt`.
- Twitch EventSub per WebSocket: https://dev.twitch.tv/docs/eventsub/handling-websocket-events/
- Entscheide: Nachrichten des Nutzers in dieser Sitzung.
