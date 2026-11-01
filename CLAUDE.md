# CLAUDE.md – Regeln für Claude Code im Projekt donstv_Studio

Diese Datei liegt im Repo-Hauptordner. Lies sie zu Beginn jeder Sitzung, danach die Dokumente unter `docs/`.

## Projekt

donstv_Studio ist eine Desktop-Anwendung im Stil von OBS Studio mit den Modulen «Overlays» und «Chat-Bot». Anforderungen: `docs/01-funktionen.md`. Technik: `docs/02-architektur.md`. Hardware und Netz: `docs/03-hardware-netzwerk.md`. Oberfläche: `docs/04-ui-design.md`. Reihenfolge der Arbeit: `docs/05-prompt-plan.md`.

## Umgebung

- Die Software läuft auf einem Studio-Laptop mit Debian 13 (X11, Python 3.13). OBS läuft auf einem anderen Rechner (Nobara) im Heimnetz.
- Der Laptop ist schwach (i7-4500U, 2 Kerne). Später kann bessere Hardware (Intel-Prozessor, Nvidia-Grafikkarte) dazukommen. Bildrate, Auflösung und Hardware-Beschleunigung sind deshalb **einstellbar**, nicht fest eingebaut.
- Qt 6 mit QtWebEngine (PyQt6). Pakete wenn möglich aus Debian (`apt`), sonst `pip` in einer virtuellen Umgebung mit `--system-site-packages`.

## Regeln

1. Baue nur, was im aktuellen Prompt steht. Alles andere gehört in `docs/01-funktionen.md` mit Priorität SOLL oder KANN und wird nicht vorweggenommen.
2. Funktions-IDs (F-xx) aus `docs/01-funktionen.md` stehen in Commit-Meldungen und Testnamen.
3. Eine Verbindung pro Dienst (F-08). Kein Baustein öffnet eine eigene Verbindung zu Twitch, YouTube oder OBS; alle lesen vom Ereignis-Bus.
4. Lage und Grösse von Quellen sind ganze Pixel (F-65). Keine Prozentwerte im Datenmodell.
5. Oberflächentexte auf Deutsch in Schweizer Rechtschreibung (kein «ß», «Grösse», «ss»).
6. Bezeichner im Code auf Englisch, Kommentare und Dokumentation auf Deutsch. [ANNAHME]
7. Zugangsdaten (Twitch-Token, OBS-Passwort) nie im Klartext in Konfiguration, Protokoll oder Tests.
8. Jeder Baustein hat Tests (pytest). Ein Baustein gilt erst als fertig, wenn die Tests laufen und die Abnahmekriterien des Prompts erfüllt sind.
9. Wenn eine Angabe fehlt oder falsch scheint: nicht raten. Als `[OFFEN]` in den Abschlussbericht schreiben.
10. Externe Aussagen (API-Verhalten, Protokolle) gegen die aktuelle Dokumentation prüfen und die Quelle (URL) im Code-Kommentar oder in `docs/` nennen.
11. Der Abschlussbericht jedes Bausteins nennt: geänderte Dateien, ausgeführte Tests mit Ergebnis, nicht erledigte Punkte, getroffene Annahmen.
