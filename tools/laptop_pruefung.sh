#!/bin/sh
# Prüfung auf dem Studio-Laptop. Ein Aufruf, eine Ergebnisdatei (laptop-ergebnis.txt).
# Aufruf (im Ordner des Repos):
#   tools/laptop_pruefung.sh        voll: Programmstand, Paketversionen, Qt-SVG-Modul, Testsuite mit den Debian-Paketen,
#                                   Beenden der Oberfläche (5 Läufe), Startprüfung (je 20 Läufe, Varianten
#                                   «standard», «schmal», «daten» und «daten_schmal», echtes Fenstersystem)
#   tools/laptop_pruefung.sh kurz   nur Qt-Version, Beenden-Prüfung und Startprüfung (je 5 Läufe: «standard», «daten»,
#                                   «daten_schmal»), ohne Testsuite
#   tools/laptop_pruefung.sh eingrenzen [daten|kopie]
#                                   P06d3: Startprüfung je 5 Läufe mit leerer Liste, nur Overlays, mit Quellen und mit
#                                   einer Kopie der echten Daten, danach die Grundvariante (Vorgabe «kopie») mit jedem
#                                   Diagnose-Schalter einzeln (src/donstv_studio/ui/diagnose.py). Dauer: etwa 15 Minuten.
#   tools/laptop_pruefung.sh fein   P06d4: je 5 Läufe mit der Kopie der echten Daten: ohne Schalter, mit den drei Teilen
#                                   von «window_changes» einzeln und paarweise, danach die vier Kopien mit einer Änderung
#                                   (ohne Lage, ohne Fensterlage, ohne Dock-Anordnung, ohne Quellen). Vorher die
#                                   Beschreibung der Lage (tools/lage_beschreiben.py). Dauer: etwa 10 Minuten.
# Alle Arten: höchstens zwei Absturzdateien je Variante, am Ende zusammen in startpruefung-absturz-zusammen.txt.
cd "$(dirname "$0")/.." || exit 1
. .venv/bin/activate
MODE="${1:-voll}"
BASE="${2:-kopie}"
LOG=laptop-pytest-voll.log
OUT=laptop-ergebnis.txt
if [ "$MODE" = "voll" ]; then RUNS_END=5; RUNS_START=20; else RUNS_END=5; RUNS_START=5; fi
ALL=startpruefung-absturz-zusammen.txt
rm -f startpruefung-absturz-*.txt  # Aufruflisten früherer Läufe (von tools/start_pruefung.py erzeugt), auch $ALL

collect_crashes() {  # P06d4: alle Absturzdateien in eine Datei, damit eine Anlage genügt
  rm -f "$ALL"
  for f in startpruefung-absturz-*.txt; do
    [ -f "$f" ] || continue
    [ "$f" = "$ALL" ] && continue
    { echo "======== $f"; cat "$f"; echo; } >> "$ALL"
  done
  if [ -f "$ALL" ]; then
    echo "== Absturzdateien: $(ls startpruefung-absturz-*.txt | grep -v -x "$ALL" | tr '\n' ' ')"
    echo "== zusammen in: $ALL"
  else
    echo "== Absturzdateien: keine"
  fi
}

summary() {  # Zusammenfassung aller Startprüfungen in $OUT
  echo "== Zusammenfassung (Variante: Läufe mit Exit-Code 0)"
  grep "^== Zusammenfassung Startprüfung" "$OUT" | sed 's/^== Zusammenfassung Startprüfung //'
  collect_crashes
}

start_check() {  # $1 = Variante
  echo "== Startprüfung (tools/start_pruefung.sh $RUNS_START $1, echtes Fenstersystem)"
  tools/start_pruefung.sh "$RUNS_START" "$1"
  echo "== start_pruefung $1 Exit-Code: $? (0 = alle Läufe in Ordnung, 2 = kein Fenstersystem)"
}

{
  echo "== Datum"; date
  echo "== Art der Prüfung: $MODE"
  echo "== Programmstand"; git log -1 --format='%h %s'
  echo "== System"; uname -srm; . /etc/os-release 2>/dev/null && echo "$PRETTY_NAME"
  echo "== Qt-Version zur Laufzeit"
  python -c "from PyQt6.QtCore import QT_VERSION_STR, PYQT_VERSION_STR; print('Qt', QT_VERSION_STR, 'PyQt6', PYQT_VERSION_STR)" 2>&1
  echo "== Fenstersystem: DISPLAY=${DISPLAY:-(leer)} XDG_SESSION_TYPE=${XDG_SESSION_TYPE:-(leer)}"
  if [ -z "$DISPLAY" ]; then
    echo "!! KEIN DISPLAY: Die Startprüfung braucht die grafische Sitzung des Laptops. Bitte das Skript in einem"
    echo "!! Terminal der Arbeitsfläche starten (nicht über ssh ohne X). Ohne DISPLAY versucht sie Xvfb; das ist"
    echo "!! nicht das echte Fenstersystem und zählt nicht als Startprüfung nach CLAUDE.md Regel 16."
  fi
} > "$OUT"

if [ "$MODE" = "eingrenzen" ]; then
  {
    for v in daten_leer daten_overlays daten kopie; do start_check "$v" 2>&1; done
    for s in perf_equalize pointer_badge qss_images min_width rename editor_view_changes editor_model_changes \
             geometry_changes theme_changes indicators_changes docks_changes window_changes; do
      start_check "$BASE,aus=$s" 2>&1
    done
  } >> "$OUT"
  summary >> "$OUT"
  cat "$OUT"
  echo
  echo "Fertig. Hänge die Datei $OUT im Chat an (und $ALL, falls vorhanden)."
  exit 0
fi

if [ "$MODE" = "fein" ]; then
  {
    echo "== Lage der echten Daten (tools/lage_beschreiben.py, nur lesend, ohne Geheimnisse)"
    python tools/lage_beschreiben.py 2>&1
    echo "== gdb: $(command -v gdb || echo 'fehlt (sudo apt install gdb)')"
    for v in kopie \
             "kopie,aus=window_stylesheet" "kopie,aus=window_minwidth" "kopie,aus=window_geometry" \
             "kopie,aus=window_stylesheet window_minwidth" "kopie,aus=window_stylesheet window_geometry" \
             "kopie,aus=window_minwidth window_geometry" \
             kopie_ohne_lage kopie_ohne_geometrie kopie_ohne_anordnung kopie_ohne_quellen; do
      start_check "$v" 2>&1
    done
  } >> "$OUT"
  summary >> "$OUT"
  cat "$OUT"
  echo
  echo "Fertig. Hänge die Dateien $OUT und $ALL (falls vorhanden) im Chat an."
  exit 0
fi

if [ "$MODE" = "voll" ]; then
  {
    echo "== Qt- und Webpakete"; pip list 2>/dev/null | grep -i -E 'qt|sip|fastapi|uvicorn|websockets|keyring|starlette|pydantic'
    echo "== Qt-SVG-Modul (python -c 'import PyQt6.QtSvg')"
    if python -c "import PyQt6.QtSvg" 2>/dev/null; then echo "vorhanden"; else echo "FEHLT"; fi
    echo "== Debian-Pakete für SVG (Namen vermutet, nicht geprüft; apt-cache zeigt, ob es sie gibt)"
    for p in python3-pyqt6.qtsvg libqt6svg6; do
      echo "-- $p"; apt-cache policy "$p" 2>&1 | head -3
    done
    echo "== Tests (offscreen, kann mehrere Minuten dauern)"
  } >> "$OUT"
  QT_QPA_PLATFORM=offscreen python -X faulthandler -m pytest -q -rfEs --tb=short -p no:cacheprovider > "$LOG" 2>&1
  CODE=$?
  {
    echo "== pytest Exit-Code: $CODE (139 bedeutet Speicherzugriffsfehler beim Beenden)"
    echo "== Zusammenfassung und Fehler (doppelte Zeilen entfernt)"
    awk '!seen[$0]++' "$LOG" | tail -150
    echo "== Meldung «WebEnginePage still not deleted» in der Testsuite: $(grep -c 'WebEnginePage still not deleted' "$LOG") Mal"
  } >> "$OUT"
fi

{
  echo "== Beenden der Oberfläche (tools/beenden_pruefung.sh, $RUNS_END Läufe)"
  tools/beenden_pruefung.sh "$RUNS_END" 2>&1
  echo "== beenden_pruefung Exit-Code: $?"
  start_check standard 2>&1
  [ "$MODE" = "voll" ] && start_check schmal 2>&1
  start_check daten 2>&1
  start_check daten_schmal 2>&1
} >> "$OUT"
summary >> "$OUT"

cat "$OUT"
echo
echo "Fertig. Hänge die Datei $OUT im Chat an (und $ALL, falls vorhanden)."
