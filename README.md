# donstv_Studio

## Zweck

donstv_Studio ist eine Desktop-Anwendung im Stil von OBS Studio mit den Modulen «Overlays» und «Chat-Bot». Sie läuft auf dem Studio-Laptop; OBS läuft auf einem anderen Rechner im Heimnetz. Anforderungen und Technik stehen unter `docs/`, die Reihenfolge der Arbeit in `docs/05-prompt-plan.md`.

Stand (November 2026, nach P06d): Version 0.1, Gerüst mit lauffähigen Teilen. Es gibt zwei Programme:

- `donstv-core`, der Kern-Dienst: Speicher (SQLite), Ereignis-Bus, lokale Schnittstelle mit Token, Overlay-Server für die Browserquelle in OBS (Text- und Bildquellen, Live-Aktualisierung) und eine Twitch-Verbindung für den Chat-Bot.
- `donstv-studio`, das Fenster im Stil von OBS mit den Modulen «Overlays» und «Chat-Bot».

Modul «Overlays»: Overlays anlegen, umbenennen, duplizieren, löschen; Text- und Bildquellen hinzufügen, umbenennen, ausblenden, ordnen; Vorschau mit derselben Seite wie in OBS, pixelgenaues Verschieben, Skalieren und Drehen mit Linealen, Hilfslinien, Raster, Einrasten, Zoom und Rückgängig. Modul «Chat-Bot»: Chat lesen und senden, Commands mit Berechtigung und Cooldown, Protokoll. Dazu im Fensterkopf der Zustand der Verbindungen und eine Leistungsanzeige (CPU, RAM, LAN).

Noch nicht gebaut sind unter anderem die OBS-Anbindung, NDI, das Quellenfenster und Actions, Timer, Queues. Was fertig ist und was folgt: `docs/01-funktionen.md` (Spalte «Stand») und `docs/05-prompt-plan.md`.

## Umgebung

- Debian 13, X11
- Python 3.13 (mindestens 3.12)
- Qt 6 mit QtWebEngine über PyQt6

## Entwicklungsumgebung einrichten

1. Debian-Pakete installieren:

   ```bash
   sudo apt install python3-venv python3-pyqt6 python3-pyqt6.qtwebengine
   ```

2. Virtuelle Umgebung mit Zugriff auf die Systempakete anlegen (damit PyQt6 aus Debian sichtbar ist):

   ```bash
   python3 -m venv --system-site-packages .venv
   . .venv/bin/activate
   ```

3. Projekt mit den Entwicklungswerkzeugen (`pytest`, `pytest-asyncio`, `ruff`) installieren:

   ```bash
   pip install -e ".[dev]"
   ```

## Prüfen und starten

```bash
pytest
ruff check
donstv-core
donstv-studio
```

## Kern-Dienst (P02)

`donstv-core` lauscht nur auf `127.0.0.1` (Port 8765, Einstellung `api.port`). Der Zugriff braucht das Token aus `~/.config/donstv_studio/api-token` (Header `Authorization: Bearer <Token>`). Eine Vorlage für `systemd --user` liegt unter `packaging/donstv-core.service`.

## Overlay-Server (P04)

Der Overlay-Server liefert die Overlay-Seite für die Browserquelle in OBS. Er läuft im Kern-Dienst auf einem eigenen Port, getrennt von der lokalen Schnittstelle.

| Einstellung | Standard | Bedeutung |
|---|---|---|
| `overlay.host` | `0.0.0.0` | Lauschadresse (alle Schnittstellen, Heimnetz) |
| `overlay.port` | `8080` | Port |
| `overlay.local_only` | `false` | «nur lokal»: `true` erzwingt `127.0.0.1` (gewinnt gegen `overlay.host`) |
| `overlay.public_host` | automatisch | Adresse oder Hostname des Laptops in der Browserquelle-URL |

Die Einstellungen werden über `POST /config/import` (siehe F-03) oder die Tabelle `settings` gesetzt; der Dienst muss danach neu gestartet werden. Die URL jedes Overlays steht im Feld `url` der Schnittstelle (`GET /overlays`). Sie enthält das Token des Overlays. Sie gehört in OBS als Browserquelle, Breite und Höhe wie das Overlay.

Die Schrift Be Vietnam Pro liegt lokal unter `src/donstv_studio/overlays/web/fonts/` (SIL Open Font License, Quelle und Lizenz dort).

### Tests mit Browser

`pytest` prüft die Pixelpositionen der Overlay-Seite in Chromium über Playwright. Ohne Playwright oder Chromium werden diese Tests mit Begründung übersprungen (`pytest -rs`). Einrichtung: `pip install -e ".[browser]"`; ein vorhandenes Chromium wird gefunden oder per `DONSTV_CHROMIUM=/Pfad/zu/chromium` angegeben.

## Oberfläche (P05)

`donstv-studio` ist das Hauptfenster (PyQt6, Variante A wie OBS). Es startet den Kern-Dienst nicht selbst, sondern verbindet sich lokal mit ihm (`127.0.0.1:8765`, Token aus `~/.config/donstv_studio/api-token`). Ist der Kern nicht erreichbar, zeigt das Fenster eine Meldung und versucht es mit wachsender Wartezeit erneut. Einen anderen Port des Kerns gibt `DONSTV_CORE_PORT` an.

Design (dunkel oder hell), Fensterposition und Dock-Anordnung merkt sich der Kern in seiner Datenbank (Einstellungen `ui.theme`, `ui.geometry`, `ui.dock_state`). Sie gelangen beim Beenden des Fensters dorthin.

PyQt6 ist ein Extra: `pip install -e ".[ui]"`. Unter Debian kommt es aus den Paketen `python3-pyqt6` und `python3-pyqt6.qtwebengine`. Tests mit Oberfläche laufen mit `QT_QPA_PLATFORM=offscreen` (setzt `tests/conftest.py`) und werden mit Begründung übersprungen, wenn PyQt6 fehlt.

### Auf dem Laptop starten

```bash
cd ~/donstv_Studio
git fetch origin claude/epic-faraday-4rfiwx && git checkout claude/epic-faraday-4rfiwx && git pull
sudo apt install python3-venv python3-pyqt6 python3-pyqt6.qtwebengine
python3 -m venv --system-site-packages .venv
. .venv/bin/activate
pip install -e ".[ui]"
```

Terminal 1, zuerst der Kern-Dienst:

```bash
cd ~/donstv_Studio && . .venv/bin/activate && donstv-core
```

Terminal 2, danach das Fenster:

```bash
cd ~/donstv_Studio && . .venv/bin/activate && donstv-studio
```

### Editor und Vorschau (P06)

Die Vorschau lädt dieselbe Overlay-Seite wie OBS in einer `QWebEngineView`. Qt zeichnet Rahmen und Griffe darüber, nicht in der Seite. Alle Werte sind ganze Pixel der Overlay-Auflösung; bei 100 % ist ein Overlay-Pixel ein Bildschirmpixel (auch bei devicePixelRatio 2). Bedienung und Tasten: `docs/04-ui-design.md`, Abschnitt «Editor und Docks (P06)».

- Das Layout (Fenster, Docks, Design) wird beim Schliessen und bei SIGTERM/SIGINT des Fensters gespeichert.
- Einstellungen des Editors (Einrasten, Raster, Zoom, Bildrate der Vorschau) und die Hilfslinien je Overlay liegen beim Kern unter `ui.editor.*` und `ui.guides.<Overlay-Kennung>`.
- QtWebEngine ist Teil des Extras `ui` (`PyQt6-WebEngine>=6.9.0`). Tests mit QtWebEngine werden mit Begründung übersprungen, wenn es sich nicht starten lässt (`pytest -rs`). Als root startet Chromium nur ohne Sandbox; `tests/conftest.py` und `donstv-studio` setzen dafür `QTWEBENGINE_CHROMIUM_FLAGS=--no-sandbox`, wenn die Benutzerkennung 0 ist. Unter Debian/Ubuntu ohne Desktop brauchen die Tests Systembibliotheken wie `libegl1`, `libnss3` und `libxkbcommon-x11-0`.
- Die Adresse mit Token wird nirgends protokolliert. Meldungen der Seite werden geschwärzt.

### Diagnose bei Absturz

Stürzt `donstv-studio` mit «Speicherzugriffsfehler» ab, hilft `tools/diagnose_qt.py`. Aufruf im Projektordner mit aktivierter Umgebung:

```bash
python tools/diagnose_qt.py
```

Das Skript meldet zuerst den Programmstand (Commit) und startet dann jede Widget-Klasse des Editors, das Hauptfenster mit und ohne Kern-Verbindung und mehrere Varianten mit jeweils einem abgeschalteten Teil einzeln in einem eigenen Prozess (ca. 1 Sekunde sichtbar). Jede Zeile heisst `OK` (mit Qt- und PyQt-Version) oder `ABSTURZ` (mit Rückgabecode, -11 = Speicherzugriffsfehler). Die Fälle `MainWindow_CoreLink_gestartet` und `CL:…` stürzen nur bei laufendem Kern ab, wenn die Ursache mit der Verbindung zusammenhängt; für ein aussagekräftiges Ergebnis das Skript einmal mit und einmal ohne laufenden `donstv-core` ausführen. Man braucht es, wenn die Oberfläche beim Start oder kurz danach abstürzt. Zusätzlich liefert `gdb -batch -ex run -ex bt --args python -c "from donstv_studio.ui.main import main; main()"` den Absturzort in Qt. Hintergrund und bisherige Ursachen: `docs/02-architektur.md`, «Befund Debian 13».

### Beenden prüfen (P06c)

`tools/beenden_pruefung.sh` startet fünfmal je in einem eigenen Prozess die echte Oberfläche mit Vorschau (offscreen, eigener Kern-Dienst in einem leeren Ordner), legt ein Overlay an, zeigt es, schliesst das Fenster und meldet den Exit-Code jedes Laufs, die letzten Zeilen von stderr und am Ende «N von 5 Läufen mit Exit-Code 0». Die Daten des Nutzers werden nicht berührt. `tools/laptop_pruefung.sh` ruft es nach der Testsuite auf.

```bash
tools/beenden_pruefung.sh
```

### Fensterkopf und Dienst-Symbole (P05b)

Die Modul-Reiter und die Verbindungsanzeigen (Twitch, YouTube, OBS, NDI) bilden einen festen Kopf über der ganzen Fensterbreite; Docks und Fenstergrösse verschieben ihn nicht. Die Symbole der Dienste legst du als `twitch.svg`, `youtube.svg`, `obs.svg` und `ndi.svg` unter `assets/icons/connections/` ab (siehe die README dort). PNG-Dateien gleichen Namens haben Vorrang und erscheinen auch ohne das Qt-SVG-Modul. Ohne Datei zeigt die Anzeige nur Zustandszeichen und Text.

## Chat-Bot (P07)

Modul «Chat-Bot»: Reiter «Commands» und «Einstellungen», Docks «Chat» und «Protokoll». Der Kern hält genau eine Twitch-Verbindung (EventSub über WebSocket zum Lesen, Helix-API zum Senden) mit dem Bot-Konto `donstvbot` im Kanal `donstv2020`. Einrichtung bei Twitch und Anmeldung: `docs/berichte/P07.md`, Abschnitt «Anleitung: Twitch einrichten».

| Einstellung | Standard | Bedeutung |
|---|---|---|
| `twitch.client_id` | leer | Client-ID der Twitch-Anwendung (kein Geheimnis), eingetragen unter «Chat-Bot → Einstellungen» |
| `twitch.channel` | `donstv2020` | Kanal, in dem der Bot liest und schreibt |

Die Tokens liegen nur im Schlüsselbund (oder in der Ersatzdatei `secrets.json`, Rechte 600), nie in Einstellungen, Export oder Protokoll.

### Testverbindung ohne Twitch

```bash
DONSTV_TWITCH_FAKE=1 donstv-core
```

Dann zeigt «Twitch» grün «Testverbindung». Testnachrichten wie aus dem Chat (in einem weiteren Terminal):

```bash
python tools/fake_chat.py "!test"
```

```bash
python tools/fake_chat.py --user Anna --badge moderator "!regeln"
```

## Arbeitsweise mit Claude Code

Der Nutzer startet jeden Auftrag in Claude Code mit demselben Satz (Repository `donsimm/donstv_Studio` als Quelle wählen):

> Das Repository ist donsimm/donstv_Studio. Hole den Zweig claude/epic-faraday-4rfiwx (git fetch origin claude/epic-faraday-4rfiwx && git checkout claude/epic-faraday-4rfiwx && git pull), lies CLAUDE.md und prompts/AKTUELL.md und führe den Auftrag aus.

Der Planer schreibt den jeweiligen Auftrag in `prompts/AKTUELL.md`. Claude Code legt den Bericht unter `docs/berichte/` ab. Der Nutzer muss nichts kopieren.
