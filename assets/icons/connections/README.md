# Dienst-Symbole der Verbindungsleiste

Die Verbindungsleiste im Fensterkopf zeigt vor jedem Dienst dessen Symbol (F-04). Die Dateien
legt der Nutzer hier ab. Es sind die **offiziellen Logos der Anbieter**; sie sind nicht Teil des
Programms und werden nicht von der Software erzeugt oder geladen.

| Dienst | Dateiname |
|---|---|
| Twitch | `twitch.svg` |
| YouTube | `youtube.svg` |
| OBS | `obs.svg` |
| NDI | `ndi.svg` |

Format: PNG (`twitch.png` usw.) mit Transparenz, mindestens 64 × 64 Pixel, wird zuerst verwendet und braucht kein Qt-SVG-Modul. SVG nur, wenn keine PNG-Datei da ist.
Gezeigt wird das Symbol in 16 Pixeln Grösse vor dem Text, in der Textfarbe des Themes eingefärbt (nur die Form zählt, die Farbe der Datei nicht).

Fehlt eine Datei, zeigt die Anzeige nur das Zustandszeichen und den Text; der Platz für das
Symbol bleibt frei, damit sich nichts verschiebt, wenn die Datei später dazukommt.

## Nutzungsregeln

Für jedes Logo gelten die Nutzungsregeln des jeweiligen Anbieters (Twitch, YouTube, OBS Project,
Vizrt NDI AB). Sie sind vor der Verwendung zu prüfen.

Zu NDI: Sobald `ndi.svg` (oder `ndi.png`) vorhanden ist, zeigt «Hilfe → Über donstv_Studio»
den Hinweis «NDI® is a registered trademark of Vizrt NDI AB».

## Herkunft der mitgelieferten Dateien (Stand 2026-11-01)

`twitch`, `youtube`, `obs` (Quelle: «OBS Studio») und `ndi` stammen als einfarbige SVG-Dateien aus dem
Projekt Simple Icons (https://github.com/simple-icons/simple-icons, Ordner `icons/`, Dateien
`twitch.svg`, `youtube.svg`, `obsstudio.svg`, `ndi.svg`). Das Projekt steht unter CC0 1.0 (Datei
`LICENSE.md`). Sein eigener Hinweis (`DISCLAIMER.md`) sagt aber, dass CC0 nicht für alle Symbole
gleich gelten muss, und die **Marken bleiben Eigentum der Anbieter**. Es sind keine offiziellen
Dateien der Anbieter. Die PNG-Dateien (128 × 128, weiss, transparent) wurden aus den SVG-Dateien
erzeugt. Die Symbole sind einfarbig: die Oberfläche färbt sie in der Textfarbe des Themes ein.
Wer die offiziellen Dateien der Anbieter verwenden will, ersetzt sie unter gleichem Namen.
