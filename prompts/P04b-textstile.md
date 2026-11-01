# P04b – Textstile korrigieren

Lies `CLAUDE.md`, `prompts/P04-overlay-server.md` und `docs/referenz/textstile-overlay-game-tool.css`.

## Anlass

Im Bericht zu P04 steht: Die Textstile wurden nicht aus dem Repo overlay-game-tool übernommen (Zugriff verweigert), sondern nachgebaut. Das gilt als Abweichung vom Auftrag (F-15). Die Originalregeln liegen jetzt im Repo unter `docs/referenz/textstile-overlay-game-tool.css`. Du brauchst keinen Zugriff auf das fremde Repo.

## Aufgabe (F-15)

1. Ersetze die nachgebauten Stile in `src/donstv_studio/overlays/web/overlay.css` durch die Regeln aus der Referenzdatei (`.txt-comic`, `.txt-thick`, `.txt-plain`, dazu «Ohne» ohne Rand und Schatten). Übernimm die Regeln inhaltlich unverändert, also die Ränder aus `text-shadow` in `em` und die `filter: drop-shadow`-Zeilen.
2. Schlüssel der Stile: `comic`, `thick`, `plain`, `none` (wie im Original). Der bisherige Schlüssel `comic_thick` entfällt. Falls Daten oder Tests ihn enthalten: anpassen und eine Migration für bestehende Quellen schreiben (`comic_thick` → `thick`).
3. Standardstil einer neuen Textquelle: `comic` (wie im Original). Anzeigenamen in der Oberfläche: «Comic», «Comic dick», «Schlicht», «Ohne».
4. Die Schriftgrösse der Textquelle bleibt in Pixeln (`props.size`). Die Ränder in `em` skalieren dann mit.
5. Test im Browser (Playwright, wie in P04): Für jeden der vier Stile wird ein Text gerendert, und der Test prüft über `getComputedStyle`, dass `text-shadow` bzw. `filter` dem Wert der Referenzdatei entspricht (bei `none`: `none`). Ein Test prüft die Migration.
6. Zwei Umgebungen testen (neueste Pakete und Mindestversionen aus `pyproject.toml`) und beide Ergebnisse nennen.

## Nicht bauen

Keine Animationen (F-20), keine weiteren Quellenarten.

Halte dich an `CLAUDE.md`, Regel 11 (Abschlussbericht). Committe mit F-Nummer und pushe auf `claude/epic-faraday-4rfiwx`.
