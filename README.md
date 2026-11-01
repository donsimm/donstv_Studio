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
