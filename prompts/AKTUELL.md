# Aktueller Auftrag

Der Planer überschreibt diese Datei vor jedem neuen Auftrag. Der Nutzer startet jeden Auftrag mit demselben Satz (siehe `README.md`, Abschnitt «Arbeitsweise»).

## Auftrag: P06d5 – Absturz beheben: Lage und Anordnung nur einmal, in fester Reihenfolge

- **Sitzung:** neue Claude-Code-Sitzung.
- **Aufgabe:** Führe `prompts/P06d5-beheben.md` vollständig aus. Grundlage: `docs/befunde/absturz-p06d.md` mit allen Nachträgen, besonders «Nachtrag 2026-11-02 (2)», und `docs/berichte/P06d4.md`.
- **Zweig:** `claude/epic-faraday-4rfiwx`, kein neuer Zweig, kein Pull Request.
- **Bericht:** nach `CLAUDE.md`, Regeln 11, 13 und 14, als `docs/berichte/P06d5.md`, gepusht.
- **Danach:** Messung `tools/laptop_pruefung.sh beheben` und drei Handtests durch den Nutzer; dann P06e und P06f, dann die OBS-Anbindung.
