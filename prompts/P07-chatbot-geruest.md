# P07 – Chat-Bot-Gerüst

Lies `CLAUDE.md`, `docs/01-funktionen.md` (5.1), `docs/02-architektur.md` und `docs/04-ui-design.md` (Abschnitt 4).

**Angaben des Nutzers (ersetzen die früheren Voraussetzungen):**
- Hauptkanal (Streamer): `donstv2020` (https://www.twitch.tv/donstv2020).
- Bot-Konto: `donstvbot` (https://www.twitch.tv/donstvbot), ein eigenes Konto. Der Bot liest und schreibt im Chat von `donstv2020` unter dem Konto `donstvbot`.
- Eine Twitch-Entwickler-Anwendung (Client-ID) gibt es noch nicht. Der Nutzer legt sie nach deiner Anleitung an und trägt die Client-ID in der Oberfläche ein. Bis dahin baust du alles andere mit der Testverbindung.

## Aufgabe (F-40 bis F-45)

1. **Twitch-Verbindung** als `Connection` (P02), genau eine Instanz (F-08).
   - Anmeldung (F-40): wähle den für eine Desktop-Anwendung passenden OAuth-Ablauf **nach der aktuellen Twitch-Dokumentation** (https://dev.twitch.tv/docs/authentication/) und nenne die Quelle im Code. Das Repo https://github.com/donsimm/overlay-game-tool (`app/oauth.py`) zeigt den bisherigen Ablauf; lies es als Vorlage, übernimm nur das Nötige. Token und Aktualisierungs-Token nur über `secrets.py` (P02). Token-Erneuerung automatisch.
   - Chat empfangen: Wähle den von Twitch aktuell empfohlenen Weg (https://dev.twitch.tv/docs/chat/ und https://dev.twitch.tv/docs/eventsub/) und begründe die Wahl im Bericht. Nachrichten werden in ein normiertes Ereignis `twitch.chat.message` übersetzt (Absender, Anzeigename, Text, Abzeichen/Rollen, Zeit, Nachrichten-Kennung) und auf den Bus gelegt. Doppelte Nachrichten-Kennungen werden verworfen.
   - Nachrichten senden (F-42) über den von Twitch vorgesehenen Weg.
   - Wiederverbinden mit wachsender Wartezeit; Status über `connection.status`.
2. **Commands** (F-43, F-44): Tabelle in der Datenbank (Migration). Felder: Name, Befehl (z. B. `!regeln`), Berechtigung (Alle, Abonnenten, Moderatoren, Streamer), Cooldown global und pro Nutzer, Antworttext, aktiv. Ausführung: Ein Chat-Ereignis, das mit dem Befehl beginnt, sendet die Antwort, wenn Berechtigung und Cooldown es erlauben. Antworttext darf `{user}` als Platzhalter enthalten. Der Bot antwortet nie auf eigene Nachrichten (keine Schleife).
3. **Ausführungs-Schnittstelle** (Vorbereitung für F-47/F-57): Klasse `ActionExecutor` mit `run(action, context)`. Im Gerüst führt sie nur «Chat-Antwort senden» aus. Commands rufen sie auf, nicht direkt den Chat.
4. **Protokoll** (F-45): Ereignisse des Bots (Command ausgelöst, abgelehnt wegen Cooldown/Berechtigung, Verbindungsstatus, Sendefehler) werden gespeichert und über `/ws/events` an die Oberfläche geliefert.
5. **Oberfläche**: Modul «Chat-Bot» nach `docs/04-ui-design.md` Abschnitt 4: Chat-Dock mit Live-Chat und Eingabefeld «Senden», Reiter «Commands» mit Tabelle und Schaltflächen (Neu, Duplizieren, Löschen; «Importieren» bleibt gesperrt mit Hinweis «folgt»), Bereich «Command bearbeiten», Protokoll-Dock. Chat-Verlauf im Speicher begrenzt (z. B. letzte 500 Nachrichten).
6. **Tests ohne Netz**: Eine `FakeTwitch`-Verbindung erzeugt Chat-Ereignisse. Tests für Berechtigung, Cooldown (global und pro Nutzer), Platzhalter, Schleifenschutz, Protokoll, doppelte Kennung.

## Abnahme

- Alle Tests ohne Netzzugriff laufen.
- Mit echten Zugangsdaten (macht der Nutzer): Anmeldung gelingt, Chat erscheint, Senden funktioniert, Command `!test` antwortet, Cooldown greift.
- Kein Token im Protokoll oder in der Konfiguration (Test durchsucht beides).

## Nicht bauen

Keine Actions mit Sub-Actions, keine Queues, keine Timer, kein Streamer.bot-Import, keine Twitch-Ereignisse wie Follow/Sub (F-54), kein YouTube.

## Zusätze

1. **Zwei Anmeldungen mit getrennten Rollen:** «bot» (donstvbot) und «broadcaster» (donstv2020). Die Tokens beider Konten liegen getrennt über `secrets.py` (Rolle im Schlüsselnamen). Für das Gerüst gilt: Chat lesen und senden über das Bot-Konto. Welche Berechtigung der Hauptkanal dafür erteilen muss (zum Beispiel eine Autorisierung des Bots für den Kanal oder Moderatorenstatus), ermittelst du aus der aktuellen Twitch-Dokumentation (https://dev.twitch.tv/docs/chat/ und https://dev.twitch.tv/docs/authentication/scopes/) und nennst die Quelle im Bericht. Die Anmeldung des Hauptkanals baust du nur, wenn sie dafür nötig ist. Ereignisse wie Follow und Sub (F-54) bleiben ausserhalb.
2. **Client-ID** wird in «Chat-Bot → Einstellungen» eingetragen (kein Geheimnis, in den Einstellungen des Kerns gespeichert). Ein Client-Secret, falls dein Ablauf eines braucht, kommt nur über `secrets.py` und nie in Konfiguration, Export oder Protokoll.
3. **Anleitung «Twitch einrichten»** im Bericht, für einen Laien: Wo auf dev.twitch.tv die Anwendung angelegt wird, welche Einstellungen (Typ, Kategorie, Redirect-URL falls nötig) genau einzutragen sind und warum, welcher Anmeldeablauf gewählt wurde und warum, und in welcher Reihenfolge sich `donstvbot` und `donstv2020` anmelden. Bei jeder Angabe die Quelle (URL). Angaben ohne Fundstelle in der Dokumentation als «nicht geprüft» kennzeichnen.
4. **Anzeige:** Im Verbindungsstatus «Twitch» nennt der Tipp-Text das verbundene Konto (zum Beispiel «donstvbot im Kanal donstv2020»).
5. Tests in zwei Umgebungen (neueste Pakete und Mindestversionen aus `pyproject.toml`), beide Ergebnisse nennen. Alle Signale tragen nur einfache Typen (`CLAUDE.md`, Regel 12).
6. Bericht nach `CLAUDE.md`, Regeln 11, 13 und 14. Am Ende «Auf dem Laptop prüfen», und die Angabe, was nur mit echten Zugangsdaten geprüft werden kann.
