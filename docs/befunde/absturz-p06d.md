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

## Nachtrag 2026-11-02: Reproduzierer gefunden (`tools/laptop_pruefung.sh eingrenzen`, P06d3, Stand 963ca96)

Laptop, Qt 6.8.2, PyQt6 6.9.0, `QT_QPA_PLATFORM=xcb`, `DISPLAY=:0`, je 5 Läufe (Quelle: `laptop-ergebnis.txt` vom 2.11.2026).

| Variante | Läufe mit Exit-Code 0 |
|---|---|
| `daten_leer`, `daten_overlays`, `daten` | 5 von 5 |
| `kopie` (Kopie der echten Daten des Nutzers) | **0 von 5** (alle −11) |
| `kopie,aus=` je einer von `perf_equalize`, `pointer_badge`, `qss_images`, `min_width`, `rename`, `editor_view_changes`, `editor_model_changes`, `geometry_changes`, `theme_changes`, `indicators_changes`, `docks_changes` | je **0 von 5** |
| `kopie,aus=window_changes` | **5 von 5** |

Schluss: Der Absturz hängt an den **echten Daten** (nicht an den erfundenen) und an mindestens einem der drei Teile, die `window_changes` zusammen auf den Stand P08 zurücksetzt (`ui/main_window.py`):

1. Stylesheet bei jedem Aufruf von `_apply_theme_style` setzen (statt nur bei Änderung),
2. Mindestbreite sofort setzen (statt über den Zeitgeber `_request_minimum_width` bei sichtbarem Fenster),
3. gespeicherte Fensterlage direkt mit `restoreGeometry` anwenden (auch am sichtbaren Fenster, ohne «dieselbe Lage nur einmal», ohne Anpassung der Breite).

Unbekannt ist, welcher der drei Teile genügt und welcher Teil der echten Daten (gespeicherte Fensterlage `geometry`, Dock-Zustand `state`, Theme, Inhalt) den Absturz auslöst. Die Daten `daten` und `daten_schmal` (Fensterlage 1300 bzw. 1000 px, Standard-Anordnung) lösen ihn nicht aus.

## Nachtrag 2026-11-02 (2): Messung `fein` (P06d4, Stand 50011ad)

Laptop, Qt 6.8.2, PyQt6 6.9.0, `QT_QPA_PLATFORM=xcb`, `DISPLAY=:0` (Sitzung Wayland, XWayland), `gdb` installiert, je 5 Läufe (Quelle: `laptop-ergebnis.txt` vom 2.11.2026, 08:23).

Lage der echten Daten (aus `tools/lage_beschreiben.py`): Theme `dark`, 2 Overlays, 3 Quellen; Fenster **maximiert** auf 1920 × 1080 (normal 1918 × 1011), Bildschirm 0; Dock-Anordnung Version 3, angenommen, **0 Reiterpaare**, keine schwebenden Docks, 4 sichtbare Docks.

| Variante | Läufe mit Exit-Code 0 |
|---|---|
| `kopie` | 0 von 5 |
| `kopie,aus=window_stylesheet` | **5 von 5** |
| `kopie,aus=window_minwidth` | 0 von 5 |
| `kopie,aus=window_geometry` | 0 von 5 |
| `kopie,aus=window_stylesheet window_minwidth` | 3 von 5 |
| `kopie,aus=window_stylesheet window_geometry` | 3 von 5 |
| `kopie,aus=window_minwidth window_geometry` | 0 von 5 |
| `kopie_ohne_lage` | **5 von 5** |
| `kopie_ohne_geometrie` | **5 von 5** |
| `kopie_ohne_anordnung` | **5 von 5** |
| `kopie_ohne_quellen` | 0 von 5 |

Schlüsse (aus den Messwerten; Deutung nicht bewiesen):

1. Der Absturz braucht **gleichzeitig** eine gespeicherte Fensterlage (maximiert) **und** eine gespeicherte Dock-Anordnung: fehlt eine von beiden, läuft alles 5 von 5, auch ohne jeden Schalter. Das passt zu Lesart C des Berichts P06d4 (aufgeschobene Anordnung `restoredState` in `QMainWindowLayout` bei maximiertem Fenster).
2. Die Quellen sind nicht nötig (`kopie_ohne_quellen` stürzt weiter); die gefüllte Overlay-Liste genügt.
3. `window_stylesheet` allein verhindert den Absturz, aber zusammen mit einem zweiten P08-Teil (`window_minwidth` oder `window_geometry`) stürzt es wieder in 2 von 5 Läufen. Das Verhalten ist also **nicht monoton**, sondern vom Zeitpunkt abhängig. Das Zurücksetzen von `window_stylesheet` ist darum **keine Behebung**, sondern verschiebt nur den Zeitpunkt.
4. Beide C++-Aufruflisten (`gdb`, Debian-Bibliotheken ohne Symbole) enden in `QLayoutPrivate::doResize()` → Zeiger 0 oder ungültig in `libQt6Widgets`. Weg 1: `QLayout::activate()` aus einem aufgeschobenen Ereignis (`sendPostedEvents`). Weg 2: `QStackedLayout::setCurrentIndex` → `QWidgetPrivate::setVisible` → `QLayout::activate` (das ist `_ListWithHint.sync`). Beide Wege treffen dieselbe Stelle: ein Layout mit einem ungültigen Eintrag.
5. Unterschied zum Container: dort (Bildschirm 1366 × 768, 2 Reiterpaare, `openbox`) stürzt nichts ab. Die echte Lage hat Bildschirm 1920 × 1080, maximiert, 0 Reiterpaare.
