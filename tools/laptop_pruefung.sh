#!/bin/sh
# Prüfung auf dem Studio-Laptop: Programmstand, Paketversionen, Qt-SVG-Modul, Testsuite mit den Debian-Paketen,
# danach das Beenden der Oberfläche (tools/beenden_pruefung.sh). Ein Aufruf, eine Ergebnisdatei.
# Aufruf (im Ordner des Repos):  tools/laptop_pruefung.sh
# Ergebnis: Datei laptop-ergebnis.txt.
cd "$(dirname "$0")/.." || exit 1
. .venv/bin/activate
LOG=laptop-pytest-voll.log
{
  echo "== Datum"; date
  echo "== Programmstand"; git log -1 --format='%h %s'
  echo "== System"; uname -srm; . /etc/os-release 2>/dev/null && echo "$PRETTY_NAME"
  echo "== Qt- und Webpakete"; pip list 2>/dev/null | grep -i -E 'qt|sip|fastapi|uvicorn|websockets|keyring|starlette|pydantic'
  echo "== Qt-Version zur Laufzeit"
  python -c "from PyQt6.QtCore import QT_VERSION_STR, PYQT_VERSION_STR; print('Qt', QT_VERSION_STR, 'PyQt6', PYQT_VERSION_STR)" 2>&1
  echo "== Qt-SVG-Modul (python -c 'import PyQt6.QtSvg')"
  if python -c "import PyQt6.QtSvg" 2>/dev/null; then echo "vorhanden"; else echo "FEHLT"; fi
  echo "== Debian-Pakete für SVG (Namen vermutet, nicht geprüft; apt-cache zeigt, ob es sie gibt)"
  for p in python3-pyqt6.qtsvg libqt6svg6; do
    echo "-- $p"; apt-cache policy "$p" 2>&1 | head -3
  done
  echo "== Tests (offscreen, kann mehrere Minuten dauern)"
} > laptop-ergebnis.txt
QT_QPA_PLATFORM=offscreen python -X faulthandler -m pytest -q -rfEs --tb=short -p no:cacheprovider > "$LOG" 2>&1
CODE=$?
{
  echo "== pytest Exit-Code: $CODE (139 bedeutet Speicherzugriffsfehler beim Beenden)"
  echo "== Zusammenfassung und Fehler (doppelte Zeilen entfernt)"
  awk '!seen[$0]++' "$LOG" | tail -150
  echo "== Meldung «WebEnginePage still not deleted» in der Testsuite: $(grep -c 'WebEnginePage still not deleted' "$LOG") Mal"
  echo "== Beenden der Oberfläche (tools/beenden_pruefung.sh, 5 Läufe)"
} >> laptop-ergebnis.txt
tools/beenden_pruefung.sh 5 >> laptop-ergebnis.txt 2>&1
echo "== beenden_pruefung Exit-Code: $?" >> laptop-ergebnis.txt
cat laptop-ergebnis.txt
echo
echo "Fertig. Hänge die Datei laptop-ergebnis.txt im Chat an."
