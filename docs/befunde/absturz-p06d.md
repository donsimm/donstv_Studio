# Befund: Absturz beim Start seit P06d (Stand 1. November 2026, 22:20)

Gemessen vom Nutzer auf dem Studio-Laptop (Debian 13, Qt 6.8.2, PyQt6 6.9.0, X11), mit der echten Anwendung (`donstv-core` läuft, dann `python -X faulthandler -c "from donstv_studio.ui.main import main; main()"`).

| Stand | Ergebnis |
|---|---|
| `368e4ad` (P06c) | Handtest vom Nutzer in Ordnung (bis auf das Diagnoseskript, siehe unten) |
| `6dc8f44` (P08) | Fenster bleibt offen, Programmwechsel und Schliessen mit dem X, Exit-Code 0 |
| `c3509cb` (P06d) | Fenster geht auf und stürzt sofort ab, Exit-Code 139, mehrfach reproduziert |
| `c3509cb` unter `gdb` | läuft, kein Absturz (Timing-abhängig, Wettlauf) |
| `c3509cb` mit `ulimit -c unlimited` | Absturz, Core-Datei 168 MB |

Der Absturz tritt nur bei laufendem Kern auf (laut `tools/diagnose_qt.py`: `MainWindow_CoreLink_gestartet` und alle `CL:`-Fälle). Das Skript stürzt aber auch bei P06c und P08 ab, ohne dass die echte Anwendung dort abstürzt: das Skript beendet nicht geordnet und ist kein treuer Nachbau. Bei P06d zusätzlich: `MainWindow_Signale` und `CL:direkter_runner` stürzen ab (bei P06c und P08 in Ordnung).

Python-Aufrufliste (faulthandler): Hauptthread in `ui/main.py`, Zeile 55 (`app.exec()`); die anderen Threads warten (Anfragen an den Kern in `backend.py`).

C++-Aufrufliste aus der Core-Datei (`gdb -batch -ex "bt 40" /usr/bin/python3.13 core.6947`, Debian-Pakete ohne Symbole):

```
#0  libc.so.6 (raise)
#2  <signal handler called>
#3  libQt6Widgets.so.6 (ohne Symbol)
#4  libQt6Widgets.so.6 (ohne Symbol)
#5  libQt6Widgets.so.6 (ohne Symbol)
#6  libQt6Widgets.so.6 (ohne Symbol)
#7  QLayoutPrivate::doResize()
#8  QApplicationPrivate::notify_helper(QObject*, QEvent*)
#9  PyQt6/QtWidgets.abi3.so
#10 QCoreApplication::notifyInternal2(QObject*, QEvent*)
#11 libQt6Widgets.so.6 (ohne Symbol)
#12 QApplicationPrivate::notify_helper(QObject*, QEvent*)
#13 PyQt6/QtWidgets.abi3.so
#14 QCoreApplication::notifyInternal2(QObject*, QEvent*)
#15 QGuiApplicationPrivate::processGeometryChangeEvent(...)
#16 QWindowSystemInterface::sendWindowSystemEvents(...)
#17 libQt6XcbQpa.so.6
#20 g_main_context_iteration
#21 QEventDispatcherGlib::processEvents(...)
#22 QEventLoop::exec(...)
#23 QCoreApplication::exec()
```

Lesart: Der Absturz geschieht beim Anpassen der Anordnung (Layout) nach einer Änderung der Fenstergeometrie, die das Fenstersystem (X11) meldet, innerhalb der Ereignisschleife, in Qt-Widgets-Code, der sich vom Layout aus auf Widgets des Fensters stützt. Er ist vom Timing abhängig (unter `gdb` nicht reproduzierbar).

Unbewiesene Hypothesen (alle aus `git diff 6dc8f44..c3509cb -- src`):

1. `ui/widgets.py`: `PerfField.event()` ruft bei `FontChange`, `StyleChange`, `PolishRequest` `update_width()`, das über `PerfBar.equalize()` mit `setFixedWidth` die Breite der Felder ändert, also während der Verarbeitung von Stil- und Layoutereignissen (Wiedereintritt).
2. `ui/main_window.py`: `_update_minimum_width()` und die Mindestbreite des Fensters (986 → 1209 px laut Bericht P06d). Eine gespeicherte, schmalere Fenstergeometrie wird beim Start durch die neue Mindestbreite verändert.
3. `ui/editor_view.py`: `PointerBadge` (neues Widget über der Vorschau).
4. `ui/theme.py`, `ui/indicators.py`: Stylesheet mit Bildern (`indicators.image_paths`), Neuberechnung des Aussehens aller Widgets beim ersten `setStyleSheet`.
5. `ui/editor_docks.py`: Feld «Name» und Aktionen.

## Nachtrag 2026-11-01 (nach P06d2): Absturz im Handtest mit echten Daten

Laptop, Stand `54f6696` (P06d2), Qt 6.8.2, PyQt6 6.9.0, Sitzung Wayland (XWayland unter `DISPLAY=:0`).

| Lauf | Bedingungen | Ergebnis |
|---|---|---|
| `tools/laptop_pruefung.sh kurz` | Beenden-Prüfung 5×, Startprüfung `standard` 5× (`xcb`, **leerer Kern**) | alle Exit-Code 0 |
| Handtest | `python -X faulthandler -c "from donstv_studio.ui.main import main; main()"`, Plattform nicht gesetzt, **echte Daten** | Exit-Code 139 |
| Handtest | wie oben mit `QT_QPA_PLATFORM=xcb` | Exit-Code 139 |
| Handtest | wie oben mit `DONSTV_OFF="perf_equalize pointer_badge qss_images min_width rename"` | Exit-Code 139 |

Schlüsse:

1. Die Startprüfung bildet den Handtest nicht ab: Sie startet mit **leeren Daten** (kein Overlay, keine Quelle, keine gespeicherte Lage ausser Variante `schmal`). Der Handtest läuft mit echten Daten.
2. Die Plattform (Wayland oder `xcb`) ist nicht die Ursache.
3. Die fünf Diagnose-Schalter aus P06d2 sind **nicht** die Ursache; die Ursache liegt in einem anderen Teil der P06d-Änderungen (`git diff 6dc8f44..54f6696 -- src/donstv_studio/ui`: `editor_view.py`, `editor_model.py`, `geometry.py`, `theme.py`, `indicators.py`, `perf.py`, `widgets.py`, `editor_docks.py`, `main_window.py`) oder in deren Zusammenspiel mit den Daten.
4. Python-Aufrufliste des Hauptthreads beim Absturz (`faulthandler`, Lauf mit allen Schaltern aus):

```
File ".../ui/editor_docks.py", line 169 in sync          (self.setCurrentWidget(...) im QStackedWidget _ListWithHint)
File ".../ui/editor_docks.py", line 226 in refresh       (OverlaysDock.refresh)
File ".../ui/editor_model.py", line 153 in _loaded
File ".../ui/backend.py", line 244 in _drain
File ".../ui/main.py", line 60 in main                    (app.exec())
```

   Der Absturz geschieht also beim **ersten Laden der Overlay-Liste** nach dem Start, wenn die Liste nicht mehr leer ist und die Seite des `QStackedWidget` von «Hinweis» auf «Liste» wechselt. Das löst ein Layout aus (passt zur C++-Aufrufliste: `QLayoutPrivate::doResize()`). `_ListWithHint.sync` ist seit P06 (`4d9a1c4`) unverändert; die Ursache liegt daher im Zustand, den P06d davor erzeugt hat. Das ist eine Lesart, kein Beweis.
5. Offen: ob der Absturz mit leerer Datenbank ausbleibt (spricht für 1.) und ob schon die Overlay-Liste allein genügt oder erst Quellen nötig sind.
