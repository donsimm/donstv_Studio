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
