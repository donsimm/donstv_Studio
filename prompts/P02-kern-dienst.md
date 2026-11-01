# P02 – Kern-Dienst

Lies `CLAUDE.md` und `docs/02-architektur.md` (Abschnitte 1 bis 3 und 7).

## Aufgabe (F-03, F-08)

Baue den Kern-Dienst ohne Oberfläche in `src/donstv_studio/core/`.

1. **Ereignis-Bus** (`bus.py`): asynchron (asyncio). Ereignis mit `id`, `ts`, `source`, `type`, `payload`. Abonnieren nach Art (mit Platzhalter, z. B. `twitch.*`). Doppelte `id` werden verworfen. Ein abgestürzter Abonnent darf den Bus und andere Abonnenten nicht stoppen (Fehler protokollieren).
2. **Speicher** (`store.py`): SQLite mit WAL, Schema-Versionen und Migrationen. Tabelle `settings` (Schlüssel/Wert). Weitere Tabellen folgen in späteren Bausteinen über neue Migrationen. Automatische Sicherung der Datenbankdatei (täglich, die letzten 7 behalten) in einen Sicherungsordner.
3. **Konfiguration und Pfade** (`config.py`): Ordner für Daten, Sicherungen, Protokolle nach XDG-Konvention. Export und Import der gesamten Konfiguration als eine Datei (F-03), mit Versionsfeld. Kein Zugangsdaten-Inhalt im Export.
4. **Zugangsdaten** (`secrets.py`): Schnittstelle `get/set/delete`. Standard: Schlüsselbund über `keyring`. Ist auf dem System kein Schlüsselbund nutzbar, Ersatz: Datei mit Rechten 600 im Konfigurationsordner, und eine deutliche Warnung im Protokoll. Beides hinter derselben Schnittstelle, mit Tests für den Ersatz.
5. **Verbindungs-Verwaltung** (`connections/base.py`, `connections/manager.py`): Basisklasse `Connection` mit `name`, `start()`, `stop()`, `status` (`getrennt`, `verbindet`, `verbunden`, `Fehler`) und Veröffentlichung von `connection.status` auf dem Bus. Der Manager hält **genau eine Instanz pro Name** (F-08) und lehnt ein zweites Registrieren desselben Namens ab. Noch keine echte Verbindung.
6. **Lokale Schnittstelle** (`api.py`): FastAPI auf `127.0.0.1`, Port aus der Konfiguration. `GET /health`, `GET /connections`, `GET /config/export`, `POST /config/import`, WebSocket `/ws/events` (Ereignisse an die Oberfläche). Zugriff nur mit einem beim Start erzeugten Token (Datei mit Rechten 600). Der Kern-Dienst ist nach aussen (Heimnetz) in diesem Baustein nicht erreichbar.
7. **Dienst** (`service.py`, Einstiegspunkt `donstv-core`): startet alles, beendet sich sauber bei SIGTERM/SIGINT. Mitgeliefert: Vorlage einer `systemd --user`-Unit unter `packaging/donstv-core.service` mit `Restart=on-failure`.
8. Protokollierung mit Rotation. Keine Tokens oder Passwörter im Protokoll.

## Abnahme

- Tests: Bus (Zustellung, Duplikate, Abonnentenfehler), Speicher (Migration, Sicherung), Konfigurations-Export/-Import (Rundlauf), Zugangsdaten-Ersatz, Manager lehnt Doppelregistrierung ab, Schnittstelle verweigert Zugriff ohne Token.
- `donstv-core` startet, `GET /health` antwortet mit Token, ohne Token verweigert es.
- `systemd --user`-Unit startet den Dienst (falls auf dem Rechner prüfbar, sonst im Bericht «nicht geprüft»).

## Nicht bauen

Keine Overlays, kein Twitch, kein OBS, keine Oberfläche.
