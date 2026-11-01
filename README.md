# donstv_Studio

## Zweck

donstv_Studio ist eine Desktop-Anwendung im Stil von OBS Studio mit den Modulen «Overlays» und «Chat-Bot». Sie läuft auf dem Studio-Laptop; OBS läuft auf einem anderen Rechner im Heimnetz. Anforderungen und Technik stehen unter `docs/`, die Reihenfolge der Arbeit in `docs/05-prompt-plan.md`.

Stand: Version 0.1, Projektgerüst. Es gibt noch keine Funktion; die Einstiegspunkte geben nur eine Startmeldung aus.

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

### Fensterkopf und Dienst-Symbole (P05b)

Die Modul-Reiter und die Verbindungsanzeigen (Twitch, YouTube, OBS, NDI) bilden einen festen Kopf über der ganzen Fensterbreite; Docks und Fenstergrösse verschieben ihn nicht. Die Symbole der Dienste legst du als `twitch.svg`, `youtube.svg`, `obs.svg` und `ndi.svg` unter `assets/icons/connections/` ab (siehe die README dort). Ohne Datei zeigt die Anzeige nur Zustandszeichen und Text.
