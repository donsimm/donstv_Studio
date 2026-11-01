# 03 – Hardware und Netzwerk

Status: Entwurf 2. Zwei Rechner im Heimnetz, verbunden über Gbit-Leitung (Angabe des Nutzers). Alles ohne Quelle ist mit [ANNAHME] markiert.

## 1. Rechner

| | Studio-Laptop | Streaming-PC |
|---|---|---|
| Aufgabe | Läuft nur donstv_Studio (Kern-Dienst und Oberfläche) | Läuft OBS |
| Betriebssystem | Debian 13.7, Kernel 6.12.107, X11 | Nobara (Angabe des Nutzers) |
| Gerät | HP EliteBook 850 G1, Hostname `debian-test` | Eigenbau |
| CPU | Intel Core i7-4500U, 2 Kerne / 4 Threads, 1.8 GHz, AVX2 vorhanden | Intel Core i9-14900KF, 24 Kerne / 32 Threads |
| RAM | 16 GB DDR3 | 64 GB DDR5 |
| Grafik | Intel HD 4400, AMD Radeon HD 8730M (Treiber `radeon`) | NVIDIA RTX 4090, 24 GB |
| Netz | Ethernet Intel I218-LM (`enp0s25`, Treiber `e1000e`); WLAN Broadcom BCM43228 | Ethernet Intel I226-V |
| Datenträger | 480 GB SATA-SSD | 2 TB und 1 TB NVMe |
| Quelle | Datei `hardware-report.txt` (Nutzer) | Angaben des Nutzers (HardInfo-Bericht des früheren Zorin-Systems) |

Befunde aus dem Bericht des Laptops:

- Die Netzwerkkarte war beim Erstellen des Berichts **nicht verbunden** (`enp0s25` Zustand DOWN, NO-CARRIER). Für den Betrieb ist Kabel nötig.
- Das WLAN (Broadcom BCM43228) meldet im Kernel-Protokoll einen Fehler: die Firmware für den Treiber `b43` fehlt. WLAN ist deshalb nicht nutzbar, und wir planen es nicht ein.
- Der Laptop hat einen schwachen Prozessor. Dort laufen Oberfläche, Vorschau (Chromium), Bot, Overlay-Server und ggf. NDI-Ausgabe. Das ist ein Risiko und wird gemessen (Abschnitt 4).

## 2. Netzwerk und Ports

Alle Ports sind [ANNAHME], bis der Bausteinplan sie festlegt.

| Richtung | Zweck | Protokoll / Port | Bemerkung |
|---|---|---|---|
| OBS-PC → Laptop | Browserquelle lädt das Overlay | HTTP, TCP 8080 [ANNAHME] | URL mit geheimem Token pro Overlay |
| OBS-PC → Laptop | Overlay-Seite erhält Live-Daten | WebSocket auf demselben Port | wie oben |
| Laptop → OBS-PC | Steuerung und Szenenwechsel (F-07) | WebSocket, TCP 4455 (Standard von obs-websocket 5.x) | Passwort nötig; Port in der Firewall des OBS-PCs freigeben |
| Laptop → Internet | Twitch-Chat, EventSub, API | HTTPS / WSS | eine Verbindung pro Dienst (F-08) |
| Laptop → Internet | YouTube (später) | HTTPS | nicht im Gerüst |
| Laptop → OBS-PC | NDI-Stream (F-36) | NDI, TCP/UDP | Entdeckung und Ports noch nicht geprüft |

Sicherheit im Heimnetz [ANNAHME]:

- Der Overlay-Server lauscht nur im Heimnetz, nicht im Internet. Kein Port wird am Router weitergeleitet.
- Jede Overlay-URL enthält einen zufälligen Token. Anfragen ohne gültigen Token werden abgelehnt.
- Kennwörter und Tokens (OBS, Twitch) liegen nicht im Klartext in der Konfiguration.
- Feste IP-Adresse oder feste DHCP-Zuweisung für den Laptop, damit die URLs in OBS gültig bleiben.

## 3. Last und Bandbreite

- Browserquelle: OBS (CEF) zeichnet das Overlay auf dem **Streaming-PC**. Der Laptop liefert nur HTML, Bilder und Live-Daten. Last auf dem Laptop gering. [ANNAHME]
- NDI: Das Overlay wird auf dem **Laptop** gezeichnet und als Stream gesendet. Laut NDI-Dokumentation braucht «NDI High Bandwidth» (SpeedHQ7, 8 Bit 4:2:2:4, also mit Alpha) bei 1080p60 **165.17 Mbit/s**. Auf einer Gbit-Leitung sind das etwa 17 %. NDI codiert jedes Bild einzeln (I-Frame only).
- NDI-SDK-Hinweise zur Leistung: UYVA/UYVY sind die schnellsten Sendeformate; BGRA/BGRX kosten wegen Umwandlung mehr Leistung; asynchrones Senden bringt «fast immer» einen deutlichen Vorteil; das SDK nutzt AVX2 (Intel).
- Ob der i7-4500U mit der Chromium-Darstellung (Radeon `radeon`-Treiber, vermutlich ohne gute GPU-Beschleunigung) plus NDI-Codierung 1080p mit 30 oder 60 Bildern pro Sekunde schafft, ist **nicht bekannt** und wird mit dem Machbarkeitstest gemessen.

## 4. Machbarkeitstests (vor dem Bau)

| Nr. | Test | Entscheid |
|---|---|---|
| T-01 | Laptop: Qt-6-Fenster mit QtWebEngine zeigt ein 1920×1080-Overlay mit Animationen; CPU-Last und Bildrate messen | Bildrate der Vorschau begrenzen (z. B. 30), oder Vorschau verkleinern |
| T-02 | Gleiches Overlay in der Vorschau und in einer OBS-Browserquelle als Bild vergleichen, Pixel-Differenz bestimmen | Bestätigt «Vorschau = OBS» (F-65) |
| T-03 | Laptop: Overlay offscreen zeichnen und per NDI senden (1080p30, danach 1080p60); CPU, Verluste und Verzögerung im OBS-PC messen | Entscheidet über F-36 |
| T-04 | OBS-PC → Laptop über Gbit: Browserquelle laden, obs-websocket-Verbindung, Wiederverbinden nach OBS-Neustart | Bestätigt F-07 |

## Quellen

- Laptop: Datei `hardware-report.txt` des Nutzers (CPU-Flags inkl. `avx2`, Netzwerkkarte I218-LM, Zustand DOWN, `b43`-Fehler).
- Streaming-PC: Angaben des Nutzers in früheren Nachrichten (i9-14900KF, RTX 4090, 64 GB; Ethernet Intel I226-V aus dessen HardInfo-Bericht). Das Betriebssystem Nobara ist die Angabe des Nutzers.
- Heimnetz mit Gbit-Leitung: Angabe des Nutzers.
- obs-websocket-Standardport 4455 und Ereignisse: https://github.com/obsproject/obs-websocket/blob/release/5.0.0/docs/generated/protocol.md
- NDI-Bandbreite 165.17 Mbit/s (1080p60, mit Alpha): https://docs.ndi.video/docs/white-paper/bandwidth/ndi-high-bandwidth-based-on-speedhq7-8bit-4-2-2-4
- NDI-SDK Leistungshinweise: https://docs.ndi.video/all/developing-with-ndi/sdk/performance-and-implementation
