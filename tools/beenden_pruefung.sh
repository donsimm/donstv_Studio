#!/bin/sh
# Prüfung des Beendens der echten Oberfläche mit Vorschau (P06c): mehrere Läufe, je ein eigener Prozess.
# Aufruf (im Ordner des Repos):  tools/beenden_pruefung.sh [Anzahl Läufe, Standard 5]
# Ausgabe: Exit-Code und letzte Zeilen von stderr je Lauf, am Ende «N von M Läufen mit Exit-Code 0».
cd "$(dirname "$0")/.." || exit 1
[ -f .venv/bin/activate ] && . .venv/bin/activate
QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-offscreen}" python -X faulthandler tools/beenden_pruefung.py --laeufe "${1:-5}"
