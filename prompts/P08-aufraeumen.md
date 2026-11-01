# P08 – Aufräumen und Qualität (kein neuer Funktionsumfang)

Lies `CLAUDE.md` (neu: Regel 15), `docs/02-architektur.md`, `docs/berichte/P06c.md`, `docs/berichte/P07.md`.

**Anlass:** Der Laptop-Lauf von P06c ist sauber (484 bestanden, 5 übersprungen, Exit-Code 0, Beenden 5 von 5 in Ordnung). Bevor weitere Funktionen dazukommen, soll sich kein Ballast im Code ansammeln. Dieser Baustein **ändert kein Verhalten**.

## Aufgaben

1. **Signale (Regel 12):** `CoreLink.statuses_loaded` und `settings_loaded` tragen `dict` über Threads. Auf `pyqtSignal(str)` mit JSON-Text umstellen, Empfänger und Tests anpassen. Danach alle `pyqtSignal(...)` im Projekt auflisten (Datei, Signatur) und bestätigen, dass keine mit `dict`, `list` oder eigenen Objekten übrig sind.
2. **Toter Code:** Ungenutzte Funktionen, Klassen, Importe, Dateien und Testhilfen suchen (`ruff check --select F401,F841,ARG`, `vulture` falls aus Debian oder pip verfügbar, sonst von Hand mit Suche). Nur entfernen, was nachweislich unbenutzt ist; Liste mit Beleg im Bericht. Unsicheres als `[OFFEN]` melden, nicht löschen.
3. **Doppelter Code:** Offensichtliche Dopplungen (z. B. Hilfsfunktionen in `ui/`, Test-Fixtures) zusammenführen, soweit ohne Verhaltensänderung möglich. Im Bericht nennen, was zusammengeführt wurde und was bewusst bleibt.
4. **Formatierung:** `ruff format` meldete Abweichungen in 68 Dateien. Einmal `ruff format` über das Projekt, in einem **eigenen Commit** ohne andere Änderungen, damit der Unterschied lesbar bleibt. Danach `ruff check` und alle Tests.
5. **Dokumente und Code abgleichen:** `docs/01-funktionen.md` (Status jeder F-ID: gebaut / teilweise / offen), `docs/05-prompt-plan.md` (P04b, P04c, P05b, P05c, P06c, P07, P08 nachtragen) und `docs/04-ui-design.md` gegen den Code prüfen. Abweichungen beheben oder als `[OFFEN]` melden.
6. **Testdauer:** Die Testsuite braucht auf dem Laptop 17 Minuten. Die 25 langsamsten Tests mit `--durations=25` auflisten, Ursachen nennen (z. B. Kern-Dienst pro Test neu gestartet) und nur ohne Qualitätsverlust beschleunigen (z. B. gemeinsame Fixtures mit Sitzungsumfang). Keine Tests löschen oder abschwächen.
7. **Debian-13-Umgebung:** Prüfen, ob in der Sitzung eine Debian-13-Umgebung nachstellbar ist (`debootstrap`, Container, `apt` aus trixie). Falls ja: Testsuite dort mit den Debian-Paketen laufen lassen und Ergebnis berichten. Falls nein: Grund nennen, nichts erfinden.
8. **Hinweise aus dem Laptop-Lauf:** «MESA-INTEL: Haswell Vulkan support is incomplete», «Compositor returned null texture», «This plugin does not support propagateSizeHints()» und die Deprecation-Warnungen von `websockets.legacy`. Für jede: Ist sie harmlos oder ein Risiko? Mit Beleg (Quelle nennen, Regel 10) oder `[OFFEN]`. Nichts am Verhalten ändern.
9. **Intel/Nvidia:** Im Code nach festen Annahmen zur Grafik suchen (Software-Rendering, Chromium-Schalter, `QT_QUICK_BACKEND` o. ä.). Auflisten, wo Hardware-Beschleunigung einstellbar ist und wo nicht. Nur berichten, noch nichts bauen.

## Abnahme

- Alle Tests in den Umgebungen von P06c grün, `ruff check` ohne Befunde, `ruff format --check` ohne Abweichung.
- Keine `pyqtSignal(dict)`/`list`/Objekte mehr.
- Bericht `docs/berichte/P08.md` mit den Listen aus 1 bis 9, am Ende «Auf dem Laptop prüfen».

## Nicht bauen

Keine neuen Funktionen, keine Änderung der Oberfläche, keine OBS-Anbindung, kein NDI.
