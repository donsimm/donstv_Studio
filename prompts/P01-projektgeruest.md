# P01 – Projektgerüst

Lies zuerst `CLAUDE.md` und `docs/01` bis `docs/05`.

## Aufgabe

Lege das Grundgerüst des Repos an. Noch keine Funktion der Software.

1. Ordnerstruktur:
   ```
   CLAUDE.md
   docs/            (die Dokumente 01 bis 05)
   prompts/         (die Prompts P01 bis P07)
   src/donstv_studio/{core,overlays,bot,ui}/
   src/donstv_studio/overlays/web/
   tests/
   pyproject.toml
   README.md
   ```
2. `pyproject.toml`: Paket `donstv_studio`, Python ab 3.12 (Ziel: 3.13), Entwicklungswerkzeuge `pytest`, `pytest-asyncio`, `ruff`. Laufzeitpakete noch nicht eintragen.
3. Einstiegspunkte als Platzhalter: `donstv-core` (Kern-Dienst) und `donstv-studio` (Oberfläche). Sie geben nur eine Startmeldung aus.
4. `README.md` auf Deutsch (Schweizer Rechtschreibung): Zweck, Umgebung (Debian 13, X11), Installation der Entwicklungsumgebung. Nenne die Debian-Pakete `python3-pyqt6` und `python3-pyqt6.qtwebengine` und die Anlage der virtuellen Umgebung mit `--system-site-packages`. Prüfe auf diesem Rechner mit `apt-cache policy`, ob die Pakete vorhanden sind, und schreibe das Ergebnis mit Versionsnummern in den Abschlussbericht. Wenn `apt` nicht verfügbar ist, schreibe «nicht geprüft».
5. `.gitignore` für Python, virtuelle Umgebung, Daten- und Konfigurationsordner.
6. Ein erster Test, der prüft, dass das Paket importierbar ist.

## Abnahme

- `pytest` und `ruff check` laufen ohne Fehler.
- `donstv-core` und `donstv-studio` starten und enden mit Startmeldung.
- Der Abschlussbericht nennt die Paketversionen aus Punkt 4.

## Nicht bauen

Keine Fenster, keine Server, keine Datenbank.
