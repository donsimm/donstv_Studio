#!/bin/sh
# Startprüfung der echten Oberfläche mit echtem Fenstersystem (P06d2, CLAUDE.md Regel 16): mehrere Starts,
# je ein eigener Prozess mit eigenem Kern-Dienst in einem leeren Ordner; die Oberfläche beendet sich selbst.
# Aufruf (im Ordner des Repos):  tools/start_pruefung.sh [Anzahl Läufe, Standard 20] [Variante, Standard standard]
#   Varianten: standard | schmal | aus=<Liste>   (Liste: perf_equalize,pointer_badge,qss_images,min_width,rename)
# Braucht ein DISPLAY (grafische Sitzung); ohne DISPLAY wird ein eigenes Xvfb versucht und das gemeldet.
# Ausgabe: Exit-Code und letzte Zeilen von stderr je Lauf, am Ende «N von M Läufen mit Exit-Code 0».
cd "$(dirname "$0")/.." || exit 1
[ -f .venv/bin/activate ] && . .venv/bin/activate
python -X faulthandler tools/start_pruefung.py --laeufe "${1:-20}" --variante "${2:-standard}"
