# P03 – Overlay-Modell

Lies `CLAUDE.md`, `docs/02-architektur.md` (Abschnitt 3) und `docs/01-funktionen.md` (4.1).

## Aufgabe (F-10, F-11, F-12, F-66)

Baue Datenmodell, Speicherung und Schnittstelle für Overlays und Quellen in `src/donstv_studio/overlays/`.

1. **Modell**
   - `Overlay`: `id`, `name`, `width`, `height` (Standard 1920×1080), `output` (`browser` oder `ndi`, Standard `browser`), `token` (zufällig, mindestens 128 Bit, erzeugt beim Anlegen), `sources` (geordnete Liste).
   - `Source`: `id`, `kind` (zunächst `text`, `image`), `x`, `y`, `width`, `height` als **ganze Pixel**, `rotation` (Grad, Dezimalzahl erlaubt), `z` (Reihenfolge), `visible`, `props` (je Art).
   - Prüfung: Breite und Höhe der Overlays ≥ 1; Quellen mit Breite/Höhe ≥ 1; Lage darf teilweise ausserhalb des Overlays liegen. Fehler als klare Meldung.
2. **Speicher**: Migration mit Tabellen für Overlays und Quellen. Duplizieren eines Overlays kopiert alle Quellen mit neuen Kennungen und **neuem Token**.
3. **Schnittstelle** (im Kern-Dienst, mit dem Token aus P02): Overlays anlegen, umbenennen, duplizieren, löschen; Auflösung ändern; Quellen hinzufügen, ändern, löschen, Reihenfolge ändern, ein-/ausblenden; Ausgabeart wählen. Jede Änderung veröffentlicht ein Ereignis `overlay.changed` (mit `overlay_id`) auf dem Bus.
4. **Ausgabeart `ndi`**: darf gespeichert werden, ist aber noch nicht aktiv. Die Schnittstelle liefert für ein NDI-Overlay `output_status: "nicht verfügbar"`. (NDI folgt in einem späteren Baustein, F-36.)

## Abnahme

- Tests: Anlegen/Ändern/Löschen, Duplizieren erzeugt neuen Token, Reihenfolge, Prüfregeln, Ereignis `overlay.changed` kommt bei jeder Änderung, Rundlauf durch Datenbank.
- Es gibt keine Prozentwerte im Modell.

## Nicht bauen

Keine Overlay-Seite (P04), keine Oberfläche.
