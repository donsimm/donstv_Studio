#!/bin/sh
# Startprüfung der echten Oberfläche mit echtem Fenstersystem (P06d2, P06d3, P06d4, CLAUDE.md Regel 16): mehrere Starts,
# je ein eigener Prozess mit eigenem Kern-Dienst in einem leeren Ordner; die Oberfläche beendet sich selbst.
# Aufruf (im Ordner des Repos):  tools/start_pruefung.sh [Anzahl Läufe, Standard 20] [Variante, Standard standard]
#   Varianten: standard | schmal | daten | daten_schmal | daten_leer | daten_overlays | daten_reiter |
#              daten_schwebend | daten_maximiert | kopie | kopie_ohne_lage | kopie_ohne_geometrie |
#              kopie_ohne_anordnung | kopie_ohne_quellen | aus=<Liste> | <Variante>,aus=<Liste>
#   Liste der Schalter: siehe src/donstv_studio/ui/diagnose.py (z. B. theme_changes,docks_changes oder in
#   Anführungszeichen mit Leerzeichen: "kopie,aus=window_stylesheet window_minwidth")
# Braucht ein DISPLAY (grafische Sitzung); ohne DISPLAY wird ein eigenes Xvfb versucht und das gemeldet.
# Ausgabe: Exit-Code und letzte Zeilen von stderr je Lauf, am Ende «N von M Läufen mit Exit-Code 0»; bei einem
# Absturz die ganze Aufrufliste von faulthandler und die Datei startpruefung-absturz-<Variante>-<Lauf>.txt.
cd "$(dirname "$0")/.." || exit 1
[ -f .venv/bin/activate ] && . .venv/bin/activate
python -X faulthandler tools/start_pruefung.py --laeufe "${1:-20}" --variante "${2:-standard}"
