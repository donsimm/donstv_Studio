#!/bin/sh
# Prüfung auf dem Studio-Laptop: Programmstand, Paketversionen, Testsuite mit den Debian-Paketen.
# Aufruf (im Ordner des Repos):  tools/laptop_pruefung.sh
# Ergebnis: Datei laptop-ergebnis.txt (im Chat an den Planer anhängen, nicht abtippen).
cd "$(dirname "$0")/.." || exit 1
. .venv/bin/activate
LOG=laptop-pytest-voll.log
{
  echo "== Datum"; date
  echo "== Programmstand"; git log -1 --format='%h %s'
  echo "== System"; uname -srm; . /etc/os-release 2>/dev/null && echo "$PRETTY_NAME"
  echo "== Qt- und Webpakete"; pip list 2>/dev/null | grep -i -E 'qt|sip|fastapi|uvicorn|websockets|keyring|starlette|pydantic'
  echo "== Tests (offscreen, kann mehrere Minuten dauern)"
} > laptop-ergebnis.txt
QT_QPA_PLATFORM=offscreen python -X faulthandler -m pytest -q -rfEs --tb=short -p no:cacheprovider > "$LOG" 2>&1
CODE=$?
{
  echo "== pytest Exit-Code: $CODE (139 bedeutet Speicherzugriffsfehler beim Beenden)"
  echo "== Zusammenfassung und Fehler (doppelte Zeilen entfernt)"
  awk '!seen[$0]++' "$LOG" | tail -150
} >> laptop-ergebnis.txt
cat laptop-ergebnis.txt
echo
echo "Fertig. Hänge die Datei laptop-ergebnis.txt im Chat an."
