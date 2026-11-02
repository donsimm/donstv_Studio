# 02 – Architektur und Technik

Status: Entwurf 2. Entschieden vom Nutzer: Oberfläche mit Qt 6 und QtWebEngine; Software läuft auf dem Studio-Laptop (Debian 13), OBS auf dem Streaming-PC (Nobara); Verbindungen nur einmal; Ausgabe pro Overlay als Browserquelle oder NDI wählbar. Alles andere ist [ANNAHME] und wird mit dir bestätigt.

## 1. Übersicht

```
 Studio-Laptop (Debian 13)                                     Streaming-PC (Nobara)
┌──────────────────────────────────────────────┐              ┌───────────────────────┐
│ Oberfläche (Qt 6, QtWebEngine)               │              │ OBS                   │
│   Docks, Vorschau, Editor                    │              │  Browserquelle ──────────── HTTP/WS ──┐
│        │ lokal (127.0.0.1)                   │              │  NDI-Quelle  ◄────────────── NDI ─────┤
│        ▼                                     │              │  obs-websocket (4455) ◄───┐           │
│ Kern-Dienst (Python, asyncio)                │              └───────────────────────┘ │           │
│   Verbindungen: Twitch | YouTube | OBS ──────┼────────────────────────────────────────┘           │
│        ▼                                     │                                                    │
│   Ereignis-Bus                               │                                                    │
│    ├─ Overlay-Server (HTTP + WebSocket) ─────┼────────────────────────────────────────────────────┘
│    ├─ Bot (Commands, später Actions)         │
│    ├─ Speicher (SQLite)                      │
│    └─ Ausführungs-Schnittstelle (C# später)  │
│ Renderer-Prozess (Qt offscreen) → NDI [später]│
└──────────────────────────────────────────────┘
```

## 2. Bausteine

| Baustein | Aufgabe | Bemerkung |
|---|---|---|
| Kern-Dienst | Enthält Verbindungen, Ereignis-Bus, Overlay-Server, Bot, Speicher. Läuft ohne Oberfläche weiter. | Start als Benutzerdienst (`systemd --user`) mit automatischem Neustart [ANNAHME] |
| Oberfläche | Nur Bedienteil: Docks, Editor, Vorschau, Chat-Ansicht. Spricht lokal mit dem Kern. | Qt 6 mit QtWebEngine (entschieden). Bei Absturz läuft der Kern weiter. |
| Verbindungen (F-08) | Genau eine Verbindung pro Dienst: Twitch, YouTube, OBS, später weitere. | Zugangsdaten an einer Stelle |
| Ereignis-Bus | Verbindungen veröffentlichen normierte Ereignisse; Overlays, Bot und Oberfläche abonnieren sie. | Jedes Ereignis hat Kennung, Zeit, Quelle, Art, Nutzlast; doppelte Kennungen werden verworfen |
| Overlay-Server | Liefert jedes Overlay als Webseite und sendet Live-Daten per WebSocket. | Lauscht im Heimnetz, Token pro Overlay |
| Bot | Chat lesen und senden, Commands verwalten und ausführen (Gerüst). | Actions, Queues, Timer später |
| Ausführungs-Schnittstelle (F-57) | «Aktion ausführen» als austauschbarer Baustein. | C# nur vorgesehen: später getrennter .NET-Prozess, nur bei Bedarf |
| Renderer (F-36) | Zeichnet Overlays ohne Fenster (Qt offscreen) und sendet sie per NDI. | Erst nach Machbarkeitstest T-03 |
| Speicher | SQLite; automatische Sicherung der Konfiguration. | [ANNAHME] |

## 3. Datenmodell (Gerüst)

| Objekt | Felder |
|---|---|
| Overlay | Kennung, Name, Breite, Höhe (Standard 1920×1080), Ausgabeart (`browser` oder `ndi`), Token, Quellenliste |
| Quelle | Kennung, Art (Text, Bild, Chat-Box, Alert-Box …), x, y, Breite, Höhe (**ganze Pixel**, F-65), Drehung in Grad, Reihenfolge, sichtbar, optional sichtbar nur bei OBS-Szene (F-64), Eigenschaften je Art |
| Ereignis | Kennung, Zeit, Quelle, Art (z. B. `twitch.chat.message`, `obs.scene.changed`, `connection.status`), Nutzlast |
| Command | Name, Befehl, Berechtigung, Cooldown global/pro Nutzer, Antwort, aktiv |

## 4. Oberfläche und Darstellung

- Hauptfenster mit andockbaren Bereichen nach Variante A (`04-ui-design.md`).
- Vorschau: QtWebEngine lädt dieselbe Overlay-Seite wie die Browserquelle. Qt zeichnet Rahmen und Griffe darüber. Darstellung wird mit T-02 gegen OBS geprüft.
- Pixelgenau (F-65): ganze Pixel, Zoom 1:1 und mehr, Zahleneingabe, Pfeiltasten, Hilfslinien, Einrasten, Lineale.
- Vorschau-Bildrate begrenzbar, weil der Laptop schwach ist (T-01).

## 5. OBS-Anbindung (F-07, F-64)

- obs-websocket 5.x auf dem Streaming-PC, Port 4455, Passwort.
- Ereignisse abonnieren: Szenen (`CurrentProgramSceneChanged`, bei Studio-Modus `CurrentPreviewSceneChanged`), Szenenliste, Szenensammlung, Ausgaben (Streaming/Aufnahme), Beenden (`ExitStarted`).
- Beim Verbinden und nach jedem Wiederverbinden die aktive Szene abfragen. Wiederverbinden mit wachsender Wartezeit.
- Das Ereignis `obs.scene.changed` geht auf den Ereignis-Bus; Overlays und Bot lesen es dort.

## 5a. Twitch-Anbindung und Chat-Bot (P07, F-40 bis F-45)

| Teil | Umsetzung | Datei |
|---|---|---|
| Anmeldung | Device Code Grant Flow, Anwendung vom Typ «Public» (kein Client-Secret). Tokens je Rolle über `secrets.py` (`twitch.bot.access_token`, `twitch.bot.refresh_token`). Erneuerung automatisch bei 401 und kurz vor Ablauf; Prüfung (`/oauth2/validate`) beim Verbinden und stündlich. | `core/connections/twitch_auth.py` |
| Chat empfangen | EventSub über WebSocket (`wss://eventsub.wss.twitch.tv/ws`), Abo `channel.chat.message` v1 mit dem Benutzer-Token des Bot-Kontos (Scope `user:read:chat`). Keepalive-Überwachung, `session_reconnect`, Wiederverbinden mit wachsender Wartezeit (1 s bis 60 s). | `core/connections/twitch.py` |
| Chat senden | Helix `POST /helix/chat/messages` (Scope `user:write:chat`). | `core/connections/twitch.py` |
| Ereignis | `twitch.chat.message`: `message_id`, `user_id`, `user_login`, `display_name`, `text`, `badges`, `roles`, `ts`, `channel`, `color`, `from_bot`. Bus-Kennung `twitch.chat:<message_id>`: doppelte Nachrichten verwirft der Bus. | `core/connections/twitch.py` |
| Commands | Tabelle `bot_commands` (Migration 5), Ausführung über `ActionExecutor.run(action, context)` (Vorbereitung F-47/F-57). Schleifenschutz: Nachrichten des Bot-Kontos lösen nichts aus. | `bot/commands.py`, `bot/engine.py`, `bot/executor.py` |
| Protokoll | Tabelle `bot_log` (Migration 5, letzte 5000 Einträge), Ereignis `bot.log` über `/ws/events`. Texte geschwärzt. | `bot/log.py` |
| Testverbindung | `FakeTwitch`, im Kern mit `DONSTV_TWITCH_FAKE=1`. | `core/connections/fake_twitch.py` |

Quellen und Prüfstand: `docs/berichte/P07.md`, Abschnitt «Quellen». Die Seiten von dev.twitch.tv waren in der Sitzung von P07 nicht abrufbar; die Angaben sind dort als «nicht geprüft» gekennzeichnet.

## 6. Ausgabe pro Overlay (F-66, F-36)

| Ausgabeart | Wer zeichnet | Wo | Stand |
|---|---|---|---|
| Browserquelle | OBS (CEF) | Streaming-PC | Gerüst |
| NDI | Renderer-Prozess | Laptop | nach T-03 |

Beide Arten nutzen dieselbe Overlay-Seite. Ob ein Overlay beides gleichzeitig ausgeben darf, ist offen.

## 7. Technikwahl

| Bereich | Wahl | Status |
|---|---|---|
| Oberfläche | Qt 6, QtWebEngine | entschieden |
| Sprache Kern und Oberfläche | Python 3 (Debian 13 liefert 3.13.5), PyQt6 | [ANNAHME] |
| Kern-Server | FastAPI mit Uvicorn, asyncio | [ANNAHME] |
| Overlay-Seiten | HTML, CSS, JavaScript je Quellenart, Be Vietnam Pro lokal | Schrift: Vorgabe |
| Speicher | SQLite | [ANNAHME] |
| Zugangsdaten | Schlüsselbund (`keyring`) mit Ersatz, falls auf Debian nicht verfügbar | [ANNAHME], prüfen |
| Pakete | Soweit möglich aus Debian (Sicherheitsupdates), sonst `pip` in einer virtuellen Umgebung | [ANNAHME], Verfügbarkeit von PyQt6/QtWebEngine in Debian 13 vor Baubeginn prüfen |
| Tests | pytest; Machbarkeitstests T-01 bis T-04 | [ANNAHME] |

### Befund Debian 13: Absturz der Oberfläche (Qt 6.8.2 mit PyQt6 6.9.0)

Auf dem Studio-Laptop (Debian 13) stürzte die Oberfläche mit «Speicherzugriffsfehler» ab. `dpkg -l` zeigt dort die Qt-Bibliotheken in Version 6.8.2 (`libqt6core6t64`, `libqt6widgets6`, `libqt6webengine*`), die Python-Pakete (`python3-pyqt6`, `python3-pyqt6.qtwebengine`) aber in Version 6.9.0. Die Aufrufliste (`gdb`) endete in `QLayout::activate` und der Python-Anbindung `QtWidgets.abi3.so`. Die Ursachen, soweit belegt:

1. **Python-Objekte in Signalen des `TaskRunner`** (`pyqtSignal(object, …)`, Aufruf aus einem Hintergrundthread). Ersetzt durch eine Warteschlange und ein Signal ohne Daten. Behoben in Commit `9555c6c`. Ob dies allein den Absturz auslöste, ist nicht belegt; er trat nach dieser Änderung weiter auf, bis die zweite Ursache beseitigt war.
2. **Gespeicherter Layout-Zustand ohne Versionsmarke** (`ui.geometry`, `ui.dock_state` aus früheren Versionen). Das Wiederherstellen (`restoreGeometry`, `restoreState`) stürzte ab, sobald der Kern verbunden war. Beleg: Löschen dieser beiden Werte beseitigte den Absturz. Behoben in Commit `9475a43`: Werte tragen die Marke `v3:`, Werte ohne Marke werden nicht wiederhergestellt.

Warum Qt beim Wiederherstellen abstürzt, ist nicht geklärt; der Zusammenhang mit der Versionsmischung ist eine Vermutung. Unsere Testumgebungen (Qt 6.9.2 mit PyQt6 6.9.0 und Qt 6.12.0 mit PyQt6 6.12.0, Python 3.13) zeigten beide Ursachen nicht, weil dort Qt und PyQt zusammenpassen. Diagnose: `tools/diagnose_qt.py` (siehe README). Quellen: Commits `9555c6c` und `9475a43` in diesem Repository; Ausgabe von `dpkg -l` und `gdb` des Nutzers vom 1. November 2026.

### Befund Debian 13: Testsuite auf dem Laptop (P06c)

Stand Commit `f688d81`: 4 Fehler, 410 bestanden, danach Speicherzugriffsfehler beim Beenden von pytest (Exit-Code 139), vorher 18 Mal «Release of profile requested but WebEnginePage still not deleted. Expect troubles !».

1. **Qt-SVG-Modul fehlt** (`import PyQt6.QtSvg` schlägt fehl). Die Anwendung zeigt trotzdem die Dienst-Symbole, weil `assets/icons/connections/` PNG-Dateien enthält und PNG Vorrang hat; die Tests mit den echten Dateien liefen auf dem Laptop durch. Fehlgeschlagen sind nur Tests mit selbst erzeugten SVG-Testsymbolen. Seit P06c: Testsymbole als PNG, SVG-Fälle werden ohne Modul mit Begründung übersprungen.
2. **Unterprozess-Test bei `QT_SCALE_FACTOR=2`** lieferte weder stdout noch stderr. Ursache im Testskript `tests/editor_dpr_script.py` belegt: `os._exit(0)` im `finally` beendete den Prozess, bevor Python eine Ausnahme ausgeben konnte. Jede Ausnahme ergab daher Exit-Code 0 ohne Ausgabe. Seit P06c: Ausnahme mit Aufrufliste in stderr, Exit-Code 1, Schrittmeldungen, `-X faulthandler`, vollständige Ausgabe im Fehlerfall. Welche Ausnahme oder welcher Absturz auf dem Laptop auftritt, ist noch nicht bekannt; ein Überspringen für Qt unter 6.9 ist deshalb nicht eingebaut.
3. **Freigabe-Reihenfolge von QtWebEngine**: Ansicht vor Seite, Seite vor Profil, `QApplication` zuletzt. Das Profil der Vorschau war ein Python-Objekt ohne Eltern; Python konnte es beim Aufräumen vor der Seite löschen. Seit P06c ist das Profil ein Kind der Seite (Qt löscht Kinder nach dem Destruktor der Seite), `ui/main.py` gibt nach `app.exec()` Webansichten und Fenster frei, und `tests/conftest.py` tut dasselbe einmal am Ende der Testsitzung (`preview_web.release_web_views`). Quellen: https://doc.qt.io/qt-6/qwebenginepage.html, https://doc.qt.io/qt-6/qwebengineprofile.html, https://doc.qt.io/qt-6/qobject.html (in der Sitzung nicht abrufbar, Wortlaut nicht geprüft); Text der Meldung in `libQt6WebEngineCore.so.6` (Qt 6.8.2) mit `strings` gefunden. Ob damit der Absturz auf dem Laptop behoben ist, zeigt erst `tools/laptop_pruefung.sh` dort.

### Befund Debian 13: Absturz beim Start seit P06d (P06d2)

Messwerte und C++-Aufrufliste: `docs/befunde/absturz-p06d.md` (Exit-Code 139 in `QLayoutPrivate::doResize()` nach einer vom Fenstersystem gemeldeten Geometrieänderung; nur bei laufendem Kern; unter `gdb` nicht). In der Sitzung von P06d2 nicht nachstellbar (Qt 6.8.2 und 6.9.0 unter Xvfb, mit und ohne Fenstermanager). Gemessen wurde aber (Messfühler über `QApplication.notify`):

1. `PerfField.event()` setzte bei `Polish`/`FontChange`/`StyleChange` über `PerfBar.equalize()` mit `setFixedWidth` die Breite **aller drei** Leistungsfelder, also mitten in der Verarbeitung von Stil- und Layout-Ereignissen (82 Aufrufe in einem Testlauf, 3 beim Start der echten Oberfläche).
2. Mit gespeicherter Fensterlage wurde `restoreGeometry` zweimal angewandt: vor dem Anzeigen und noch einmal am **sichtbaren** Fenster nach dem Verbinden (`settings_loaded`), dazu `setMinimumWidth` am sichtbaren Fenster. Das erzeugt genau die Art Geometrieänderung vom Fenstersystem, in der der Absturz liegt.

Seit P06d2: Grösse, Mindestbreite und Lage werden nie in `event()`, `resizeEvent`, `changeEvent` oder während des Polierens gesetzt, sondern zusammengefasst über einen Zeitgeber mit 0 ms (`PerfBar.request_equalize`, `MainWindow._request_minimum_width`); dieselbe gespeicherte Lage wird nur einmal angewandt, und erst nach der Mindestbreite (`MainWindow._restore_geometry`). Regel: `CLAUDE.md`, Regel 16. Ob das den Absturz auf dem Laptop beseitigt, ist **nicht gemessen**. Diagnose: `tools/start_pruefung.sh` mit `DONSTV_OFF` (README, «Start prüfen»). Bewertung der Hypothesen: `docs/berichte/P06d2.md`. Qt-Verhalten (https://doc.qt.io/qt-6/qwidget.html, https://doc.qt.io/qt-6/qlayout.html): in der Sitzung nicht abrufbar, nicht geprüft.

### Befund Debian 13: Absturz beim ersten Laden der Daten (P06d3)

Nach P06d2 stürzt der Handtest mit echten Daten auf dem Laptop weiter ab (`docs/befunde/absturz-p06d.md`, «Nachtrag 2026-11-01»): Python-Aufrufliste `EditorModel._loaded` → `OverlaysDock.refresh` → `_ListWithHint.sync` → `QStackedWidget.setCurrentWidget`, also beim Wechsel der Seite «Hinweis» → «Liste», sobald die erste Overlay-Liste nicht leer ist. Die Startprüfung von P06d2 war grün, weil sie mit leerem Kern startete.

Lesart aus dem Qt-Quelltext 6.8.2 (nicht aus der Dokumentation; `doc.qt.io` ist in der Sitzung gesperrt): `QStackedLayout::setCurrentIndex` blendet die alte Seite aus und ruft `show()` der neuen (https://raw.githubusercontent.com/qt/qtbase/v6.8.2/src/widgets/kernel/qstackedlayout.cpp, Zeilen 262–320). `QWidgetPrivate::setVisible(true)` aktiviert dabei die Layouts **aller sichtbaren Eltern bis zum Fenster** (https://raw.githubusercontent.com/qt/qtbase/v6.8.2/src/widgets/kernel/qwidget.cpp, Zeilen 8354–8361). Der erste Seitenwechsel nach dem Start löst damit eine Anordnung des ganzen Hauptfensters aus (passt zu `QLayoutPrivate::doResize()` in der C++-Aufrufliste). Welcher Zustand dabei ungültig ist, ist **nicht belegt**.

In der Sitzung von P06d3 nicht nachstellbar (Qt 6.8.2 und 6.9.0 unter Xvfb, mit gefüllten Daten, schmaler Fensterlage, Reitern und schwebendem Dock, mit aktiver Barrierefreiheits-Schnittstelle AT-SPI, mit `MALLOC_PERTURB_` und unter Valgrind ohne ungültigen Zugriff in Qt Widgets). Werkzeuge für die Messung auf dem Laptop: Startprüfung mit Daten und mit einer Kopie der echten Daten (`tools/start_pruefung.sh … daten`, `… kopie`), Diagnose-Schalter für jede geänderte Datei (`ui/diagnose.py`), `tools/laptop_pruefung.sh eingrenzen`. Bewertung der Hypothesen: `docs/berichte/P06d3.md`. Seit P06d3 gilt `CLAUDE.md`, Regel 16, mit gefüllten Daten.

### Absturz eingegrenzt auf `main_window.py` und die echten Daten (P06d4)

Gemessen vom Nutzer (`docs/befunde/absturz-p06d.md`, Nachtrag 2026-11-02): `kopie` stürzt 5 von 5 Mal ab, `kopie,aus=window_changes` nicht. P06d4 teilt `window_changes` in `window_stylesheet`, `window_minwidth`, `window_geometry` und die echten Daten in `kopie_ohne_lage`, `kopie_ohne_geometrie`, `kopie_ohne_anordnung`, `kopie_ohne_quellen` (`tools/laptop_pruefung.sh fein`). Reihenfolge beim Start und die Lesart aus dem Qt-Quelltext 6.8.2: `docs/berichte/P06d4.md`, Abschnitt 6.

Format der gespeicherten Lage (für `tools/lage_beschreiben.py`, Qt-Quelltext 6.8.2): `QWidget::saveGeometry` in `src/widgets/kernel/qwidget.cpp`, Zeilen 7375–7399; `QMainWindow::saveState` in `src/widgets/widgets/qmainwindow.cpp`, Zeilen 1203–1212 (https://raw.githubusercontent.com/qt/qtbase/v6.8.2/src/…). Die Dock-Anordnung liest das Werkzeug nicht von Hand, sondern über `restoreState` in einem eigenen Prozess (offscreen).

### Massnahmen gegen den Absturz (P06d5)

Messung P06d4: Der Absturz braucht eine gespeicherte **maximierte** Fensterlage **und** eine Dock-Anordnung. Qt 6.8.2 (`src/widgets/widgets/qmainwindowlayout.cpp`, https://raw.githubusercontent.com/qt/qtbase/v6.8.2/src/widgets/widgets/qmainwindowlayout.cpp): `QMainWindowLayout::restoreState` am verborgenen, maximierten Fenster behält eine Anordnung, die nicht ins Fenster passt, als `restoredState` (Zeilen 3250–3258) und übernimmt sie in späteren `setGeometry`-Aufrufen (Zeilen 2321–2343). Ein zweites `restoreState` löscht die Einträge des bisherigen Zustands (Zeile 3261), `restoredState` hält sie weiter. Im Container mit `daten_laptop_breit` nachgestellt (Absturz in `QLayoutPrivate::doResize`, Aufrufliste wie auf dem Laptop, Bericht `docs/berichte/P06d5.md`).

Massnahmen in `ui/main_window.py` und `ui/editor_docks.py` (`# FIX (P06d5)`, Schalter in `ui/diagnose.py`):

1. `fix_state_once`: dieselbe Dock-Anordnung nur einmal anwenden (kein zweites `restoreState` beim Verbinden).
2. `fix_restore_after_show`: bei maximierter oder Vollbild-Lage die Anordnung erst nach dem Anzeigen anwenden, wenn das Fenster seine Endgrösse hat (Zeitgeber `RESTORE_SETTLE_MS` = 200 ms ohne Grössenänderung, höchstens `RESTORE_MAX_MS` = 2000 ms nach dem Anzeigen). Am sichtbaren Fenster legt Qt kein `restoredState` an (Zeilen 3244–3246).
3. `fix_list_after_restore`: Die Listen «Overlays» und «Quellen» wechseln die Seite (Hinweis ↔ Liste) erst nach `MainWindow.layout_restored`.

## 8. Offene Punkte

1. [ENTSCHIEDEN] Getrennter Kern-Dienst und Oberfläche.
2. [ENTSCHIEDEN] Ein Overlay darf Browserquelle und NDI gleichzeitig ausgeben (Datenmodell: `output` wird bei NDI-Ausbau zur Liste; im Gerüst P03 genügt ein Wert, die Änderung ist eine Migration).
3. [ENTSCHIEDEN] Der Laptop kann später durch bessere Hardware (Intel-Prozessor, Nvidia-Grafikkarte) ersetzt werden. Bildrate, Auflösung und Hardware-Beschleunigung von Vorschau und Renderer sind einstellbar und nicht auf den i7-4500U ausgelegt.
4. [ERLEDIGT] Auf dem Studio-Laptop (Debian 13, `apt-cache policy`, Quelle http://deb.debian.org/debian trixie/main amd64): `python3-pyqt6` 6.9.0-2 und `python3-pyqt6.qtwebengine` 6.9.0-1 sind als Installationskandidaten verfügbar. Noch nicht installiert und nicht getestet (T-01). Ebenso verfügbar (gleiche Quelle): python3-fastapi 0.115.11-4, python3-uvicorn 0.32.0-3, python3-websockets 15.0.1-1, python3-keyring 25.6.0-2, python3-httpx 0.28.1-1. Auf dem Laptop (Ausgabe `pip list` in der Umgebung mit `--system-site-packages`, 2026-11-01, Datei `laptop-ergebnis.txt`) sind installiert: starlette 0.46.1, pydantic 2.10.6, pydantic_core 2.27.2, PyQt6 6.9.0, PyQt6-WebEngine 6.9.0, PyQt6_sip 13.10.0. Es wurden keine Qt-Pakete aus PyPI nachgeladen. Die Installation mit `pip install -e '.[dev]'` auf dem Laptop (Debian-Pakete, `--system-site-packages`) hat keine dieser Pakete nachgeladen.
5. [OFFEN] NDI-SDK: Lizenzbedingungen und Linux-Bezug prüfen (Hinweis «NDI® is a registered trademark of Vizrt NDI AB»).
6. [OFFEN] Zugangsdaten-Speicher auf dem Laptop (X11, ohne Desktop-Schlüsselbund?).

## Quellen

- obs-websocket-Protokoll: https://github.com/obsproject/obs-websocket/blob/release/5.0.0/docs/generated/protocol.md
- NDI-Dokumentation: https://docs.ndi.video/all/developing-with-ndi/sdk/performance-and-implementation und https://docs.ndi.video/docs/white-paper/bandwidth/ndi-high-bandwidth-based-on-speedhq7-8bit-4-2-2-4
- Python-Version auf dem Laptop (3.13.5): Datei `hardware-report.txt`.
- Twitch EventSub per WebSocket: https://dev.twitch.tv/docs/eventsub/handling-websocket-events/
- Twitch Chat und Anmeldung (P07): https://dev.twitch.tv/docs/chat/, https://dev.twitch.tv/docs/authentication/getting-tokens-oauth/#device-code-grant-flow, https://dev.twitch.tv/docs/api/reference/#send-chat-message (nicht geprüft, siehe `docs/berichte/P07.md`)
- Entscheide: Nachrichten des Nutzers in dieser Sitzung.
