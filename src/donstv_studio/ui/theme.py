"""Farben der Oberfläche (F-06). Alle Farbwerte stehen an dieser einen Stelle.

Dieses Modul braucht kein Qt: Palette, Kontrastberechnung und Stylesheet sind reiner Text,
damit Kontrast und Stylesheet auch ohne Oberfläche getestet werden können.

Kontrast nach WCAG 2.x, Erfolgskriterium 1.4.3 (mindestens 4,5:1 für normalen Text):
https://www.w3.org/TR/WCAG21/#contrast-minimum, Formel der relativen Leuchtdichte:
https://www.w3.org/TR/WCAG21/#dfn-relative-luminance
"""

from __future__ import annotations

DARK = "dark"
LIGHT = "light"
THEME_NAMES = {DARK: "Dunkel", LIGHT: "Hell"}
DEFAULT_THEME = DARK
MIN_CONTRAST = 4.5
MIN_GRAPH_CONTRAST = 3.0  # Grafik (Linie der Verläufe) gegen die Fläche: WCAG 1.4.11, https://www.w3.org/TR/WCAG21/#non-text-contrast
# Bedienelemente (Häkchen, Pfeile, Rahmen der Eingabefelder) gegen den Untergrund: ebenfalls WCAG 2.x, 1.4.11 (F-76)
MIN_CONTROL_CONTRAST = 3.0

# Schriftgrösse der Oberfläche. Die Schriftart bleibt die des Systems; nur die Grösse ist festgelegt.
# Gemessen in den Referenzbildern (docs/referenz, je 1920×1080): Der Text von OBS ist etwa 0,9-mal so
# breit wie der von donstv_Studio mit Systemgrösse 11 pt (Wort «Datei» 31 zu 35 px, «Quellen» ohne
# Fettschrift etwa 46 zu 52 px); Kappenhöhe 9 zu 11 Pixelzeilen. Das entspricht 10 pt bei OBS.
FONT_PT = 10

# Masse in Pixeln, gemessen im OBS-Bild (1920×1080): Dock-Titel 26, Listenzeile 26, Lücke zwischen
# den Docks 4, Statuszeile 29.
DOCK_TITLE_HEIGHT = 26
LIST_ROW_HEIGHT = 26
DOCK_GAP = 4
STATUS_BAR_HEIGHT = 29

# Fensterkopf (F-68): kräftiger als in P05b (dort etwa 30 px). Höhe des Kopfes inklusive unterer Linie;
# darin Leistungsfelder mit Beschriftungszeile und Verlaufsgrafik von 28 px.
HEADER_HEIGHT = 56
HEADER_MARGIN = 4  # Abstand des Kopfrahmens zum Fensterrand
CONN_BUTTON_WIDTH = 46  # Verbindungs-Buttons (F-04)
CONN_BUTTON_HEIGHT = 40
PERF_TEXT_ROW = 16
PERF_GRAPH_HEIGHT = 28

# Bedienelemente (F-76): Kästchen der Kontrollkästchen, Breite der Pfeil-Schaltflächen in Zahlenfeldern und Listen
CHECK_BOX = 14
SPIN_BUTTON_WIDTH = 12
COMBO_BUTTON_WIDTH = 16

# Dunkel: im OBS-Bild gemessene Farben (Fenster #1d1f26, Dockkörper #272a33, Titel und Rahmen
# #3c404d, Vorschau #13141a, Leinwand #000000, Auswahl #284cb8). Nebentext und Statusfarben sind
# so gewählt, dass der Kontrast mindestens 4,5:1 beträgt (Test in tests/test_ui_theme.py).
# Hell: keine Vorlage; sachliche Werte.
PALETTES: dict[str, dict[str, str]] = {
    DARK: {
        "bg": "#1d1f26",  # Fensterhintergrund, Lücken zwischen den Docks
        "surface": "#272a33",  # Dockkörper, Menüs, Eingabefelder, Statuszeile
        "title_bg": "#3c404d",  # Titelzeile der Docks, Schaltflächen
        "text": "#e6e6e6",
        "text_muted": "#b4b8c0",  # Nebentext
        "border": "#3c404d",
        "accent": "#4c8dff",  # aktiver Modul-Reiter, Fokus
        "accent_text": "#0b0b0c",  # Text auf accent
        "selection_bg": "#284cb8",  # gewählte Listenzeile
        "selection_text": "#ffffff",
        "ok": "#5fd38d",  # Statusfarben, nur zusammen mit Text und Symbol (U-04)
        "warn": "#f0b74a",
        "error": "#ff7b72",
        "preview_bg": "#13141a",  # Fläche um die Leinwand
        "canvas": "#000000",  # Leinwand der Vorschau
        "canvas_text": "#b4b8c0",  # Text auf der Leinwand (auch im hellen Design schwarzer Grund)
        "perf_cpu": "#5b9dff",  # Linien der Verläufe in der Leistungsanzeige (blau, violett, grün)
        "perf_ram": "#c58af9",
        "perf_lan": "#4fcf8a",
        "checker_a": "#2b2e38",  # Karo-Hintergrund hinter dem durchsichtigen Overlay (Editor)
        "checker_b": "#383c48",
        "guide": "#2dd4ff",  # Hilfslinien
        "snap": "#ff5ccf",  # Linie, an der gerade eingerastet wird
        # F-76: Bedienelemente, je mindestens 3:1 gegen ihren Untergrund (CONTROL_PAIRS)
        "control_border": "#8a8f9c",  # Rahmen von Eingabefeldern und Kontrollkästchen
        "arrow": "#e6e6e6",  # Pfeile in Zahlenfeldern und Auswahllisten
        "check_bg": "#4c8dff",  # gefülltes Kästchen, wenn angekreuzt
        "check_mark": "#0b0b0c",  # Häkchen auf check_bg
    },
    LIGHT: {
        "bg": "#f4f5f7",
        "surface": "#ffffff",
        "title_bg": "#e1e4ea",
        "text": "#1b1d21",
        "text_muted": "#4f5560",
        "border": "#c4c8cf",
        "accent": "#1d5fd1",
        "accent_text": "#ffffff",
        "selection_bg": "#1d5fd1",
        "selection_text": "#ffffff",
        "ok": "#17692f",
        "warn": "#7a4b00",
        "error": "#b3261e",
        "preview_bg": "#e4e6ea",
        "canvas": "#000000",
        "canvas_text": "#b4b8c0",
        "perf_cpu": "#1d5fd1",
        "perf_ram": "#7b3fb0",
        "perf_lan": "#17692f",
        "checker_a": "#cfd3da",
        "checker_b": "#eceef2",
        "guide": "#0a6fb3",
        "snap": "#b3126f",
        "control_border": "#767c88",
        "arrow": "#1b1d21",
        "check_bg": "#1d5fd1",
        "check_mark": "#ffffff",
    },
}

# Alle Kombinationen «Textfarbe auf Hintergrund», die in der Oberfläche vorkommen.
TEXT_PAIRS: tuple[tuple[str, str], ...] = (
    ("text", "bg"),
    ("text", "surface"),
    ("text", "title_bg"),
    ("text", "preview_bg"),
    ("text_muted", "bg"),
    ("text_muted", "surface"),
    ("text_muted", "title_bg"),
    ("text_muted", "preview_bg"),
    ("canvas_text", "canvas"),
    ("accent_text", "accent"),
    ("selection_text", "selection_bg"),
    ("bg", "ok"),  # Zustandszeichen auf dem farbigen Punkt der Verbindungs-Buttons
    ("bg", "warn"),
    ("bg", "error"),
    ("bg", "text_muted"),
    ("ok", "bg"),
    ("ok", "surface"),
    ("warn", "bg"),
    ("warn", "surface"),
    ("error", "bg"),
    ("error", "surface"),
)

# F-76: Bedienelemente gegen ihren Untergrund, mindestens MIN_CONTROL_CONTRAST. Eingabefelder haben den Grund «bg»
# und liegen in Docks («surface»); Kontrollkästchen liegen auf «surface», «bg» oder «title_bg».
CONTROL_PAIRS: tuple[tuple[str, str], ...] = (
    ("control_border", "surface"),  # Rahmen eines Feldes gegen das Dock
    ("control_border", "bg"),  # Rahmen gegen das Innere des Feldes und gegen den Fenstergrund
    ("control_border", "title_bg"),
    ("arrow", "bg"),  # Pfeile im Zahlenfeld und in der Auswahlliste (Grund des Feldes)
    ("arrow", "title_bg"),  # Pfeil-Schaltflächen unter dem Zeiger (Grund «title_bg»)
    ("check_mark", "check_bg"),  # Häkchen im angekreuzten Kästchen
    ("check_bg", "surface"),  # angekreuztes Kästchen gegen das Dock
    ("check_bg", "bg"),
    (
        "text",
        "surface",
    ),  # Symbole der Dock-Leisten, z. B. Pfeile der Reihenfolge (icons.py, Textfarbe)
    ("text_muted", "surface"),  # dieselben Symbole ausgegraut
)

# Grafik-Farben der Leistungsanzeige auf der Fläche des Verlaufs («surface»): mindestens 3:1.
GRAPH_PAIRS: tuple[tuple[str, str], ...] = (
    ("perf_cpu", "surface"),
    ("perf_ram", "surface"),
    ("perf_lan", "surface"),
)


def _channel(c: int) -> float:
    v = c / 255
    return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4


def luminance(color: str) -> float:
    r, g, b = (int(color[i : i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def contrast_ratio(fg: str, bg: str) -> float:
    a, b = luminance(fg), luminance(bg)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


def palette(theme: str) -> dict[str, str]:
    return PALETTES.get(theme, PALETTES[DEFAULT_THEME])


def control_images(images: dict[str, str] | None) -> str:
    """Regeln mit Bildern für Häkchen und Pfeile (F-76). `images`: Pfade aus `indicators.image_paths`."""
    if not images:
        return ""
    i = images
    return f"""
QCheckBox::indicator:checked {{ image: url({i["check"]}); }}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{ image: url({i["up"]}); }}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow, QComboBox::down-arrow {{ image: url({i["down"]}); }}
QSpinBox::up-arrow:disabled, QDoubleSpinBox::up-arrow:disabled {{ image: url({i["up_disabled"]}); }}
QSpinBox::down-arrow:disabled, QDoubleSpinBox::down-arrow:disabled,
QComboBox::down-arrow:disabled {{ image: url({i["down_disabled"]}); }}
"""


def stylesheet(theme: str, images: dict[str, str] | None = None) -> str:
    """Stylesheet des Designs. `images` (F-76): Bilder für Häkchen und Pfeile; ohne sie zeichnet Qt eigene."""
    c = palette(theme)
    return f"""
QWidget {{ background-color: {c["bg"]}; color: {c["text"]}; font-size: {FONT_PT}pt; }}
QMainWindow, QDialog {{ background-color: {c["bg"]}; }}
QMainWindow::separator {{ background-color: {c["bg"]}; width: {DOCK_GAP}px; height: {DOCK_GAP}px; }}
QLabel {{ background: transparent; }}
QLabel[muted="true"] {{ color: {c["text_muted"]}; }}

QMenuBar {{ background-color: {c["bg"]}; color: {c["text"]}; padding: 2px 0; spacing: 0; }}
QMenuBar::item {{ background: transparent; padding: 4px 7px; margin: 0; }}
QMenuBar::item:selected {{ background-color: {c["selection_bg"]}; color: {c["selection_text"]}; }}
QMenu {{ background-color: {c["surface"]}; color: {c["text"]}; border: 1px solid {c["border"]}; }}
QMenu::item {{ padding: 4px 24px 4px 12px; }}
QMenu::item:selected {{ background-color: {c["selection_bg"]}; color: {c["selection_text"]}; }}
QMenu::item:disabled {{ color: {c["text_muted"]}; }}
QMenu::separator {{ height: 1px; background: {c["border"]}; margin: 3px 0; }}

QWidget#header {{ background-color: {c["bg"]}; border: 1px solid {c["border"]}; border-radius: 4px; }}
QWidget#header QWidget {{ background-color: transparent; }}

QStatusBar {{ background-color: {c["surface"]}; color: {c["text"]}; border-top: 1px solid {c["border"]}; }}
QStatusBar::item {{ border: none; }}
QLabel#core_status {{ background-color: {c["surface"]}; border-left: 1px solid {c["border"]}; padding: 0 10px; }}

QWidget#dockTitle {{ background-color: {c["title_bg"]}; }}
QLabel#dockTitleText {{ background-color: transparent; font-weight: bold; }}
QWidget#dockTitle QToolButton {{ background-color: transparent; border: none; border-radius: 2px; }}
QWidget#dockTitle QToolButton:hover {{ background-color: {c["border"]}; }}
QWidget#dockTitle QToolButton:focus {{ border: 1px solid {c["accent"]}; }}
QFrame#dockbody {{ background-color: {c["surface"]}; border: 1px solid {c["border"]}; border-top: none; }}
QFrame#dockbody QLabel {{ background-color: {c["surface"]}; }}

QTabBar::tab {{ background-color: {c["surface"]}; color: {c["text"]}; padding: 4px 14px;
               border: 1px solid {c["border"]}; border-bottom: none; }}
/* Kein Fettdruck beim gewählten Reiter: sonst wäre er breiter und der Nachbar rückte (fester Kopf). */
QTabBar::tab:selected {{ background-color: {c["accent"]}; color: {c["accent_text"]}; }}
QTabBar::tab:hover:!selected {{ background-color: {c["selection_bg"]}; color: {c["selection_text"]}; }}
QTabWidget::pane {{ border: 1px solid {c["border"]}; background-color: {c["surface"]}; }}

QFrame#preview {{ background-color: {c["preview_bg"]}; border: none; }}
QFrame#canvas {{ background-color: {c["canvas"]}; border: none; }}
QFrame#canvas QLabel {{ background-color: {c["canvas"]}; color: {c["canvas_text"]}; }}
QFrame#banner {{ background-color: {c["surface"]}; border: 2px solid {c["warn"]}; }}
QFrame#banner QLabel {{ background-color: {c["surface"]}; color: {c["text"]}; }}

QPushButton {{ background-color: {c["surface"]}; color: {c["text"]}; border: 1px solid {c["border"]};
              padding: 3px 10px; }}
QPushButton:hover:enabled {{ background-color: {c["title_bg"]}; }}
QPushButton:disabled {{ color: {c["text_muted"]}; }}
QPushButton:focus, QRadioButton:focus {{ border: 2px solid {c["accent"]}; }}
QRadioButton {{ background: transparent; }}

QListView, QListWidget {{ background-color: {c["surface"]}; color: {c["text"]}; border: 1px solid {c["border"]};
                         outline: 0; }}
QListView::item, QListWidget::item {{ height: {LIST_ROW_HEIGHT}px; padding-left: 3px; }}
QListView::item:selected, QListWidget::item:selected {{ background-color: {c["selection_bg"]};
                                                       color: {c["selection_text"]}; }}
QWidget#dockBar {{ background-color: {c["surface"]}; border-top: 1px solid {c["border"]}; }}
QWidget#dockBar QToolButton {{ background-color: transparent; border: 1px solid transparent; border-radius: 2px; }}
QWidget#dockBar QToolButton:hover:enabled {{ background-color: {c["title_bg"]}; border: 1px solid {c["border"]}; }}
QWidget#dockBar QToolButton:pressed {{ background-color: {c["border"]}; }}
QWidget#dockBar QToolButton:focus {{ border: 1px solid {c["accent"]}; }}
QWidget#dockBar QToolButton::menu-indicator {{ image: none; }}
QWidget#dockInner {{ background-color: {c["surface"]}; }}
QFrame#dockbody QListWidget {{ border: none; }}
QSpinBox, QDoubleSpinBox, QLineEdit, QComboBox {{ background-color: {c["bg"]}; color: {c["text"]};
    border: 1px solid {c["control_border"]}; padding: 1px 4px; min-height: 18px; }}
QSpinBox, QDoubleSpinBox {{ padding: 1px 2px 1px 4px; }}
QSpinBox::up-button, QDoubleSpinBox::up-button {{ subcontrol-origin: padding; subcontrol-position: top right;
    width: {SPIN_BUTTON_WIDTH}px; background-color: {c["bg"]}; border-left: 1px solid {c["control_border"]}; }}
QSpinBox::down-button, QDoubleSpinBox::down-button {{ subcontrol-origin: padding; subcontrol-position: bottom right;
    width: {SPIN_BUTTON_WIDTH}px; background-color: {c["bg"]}; border-left: 1px solid {c["control_border"]}; }}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover, QSpinBox::down-button:hover,
QDoubleSpinBox::down-button:hover {{ background-color: {c["title_bg"]}; }}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow, QSpinBox::down-arrow, QDoubleSpinBox::down-arrow,
QComboBox::down-arrow {{ width: 9px; height: 6px; }}
QComboBox::drop-down {{ subcontrol-origin: padding; subcontrol-position: center right; width: {COMBO_BUTTON_WIDTH}px;
    border-left: 1px solid {c["control_border"]}; background-color: {c["bg"]}; }}
QSpinBox:focus, QDoubleSpinBox:focus, QLineEdit:focus, QComboBox:focus {{ border: 1px solid {c["accent"]}; }}
QSpinBox:disabled, QDoubleSpinBox:disabled, QLineEdit:disabled, QComboBox:disabled {{ color: {c["text_muted"]}; }}
QComboBox QAbstractItemView {{ background-color: {c["surface"]}; color: {c["text"]};
    selection-background-color: {c["selection_bg"]}; selection-color: {c["selection_text"]}; }}
QCheckBox {{ background: transparent; spacing: 6px; }}
QCheckBox:focus {{ border: 1px solid {c["accent"]}; }}
QCheckBox::indicator {{ width: {CHECK_BOX}px; height: {CHECK_BOX}px; background-color: {c["bg"]};
    border: 1px solid {c["control_border"]}; border-radius: 2px; }}
QCheckBox::indicator:checked {{ background-color: {c["check_bg"]}; border: 1px solid {c["check_bg"]}; }}
QCheckBox::indicator:disabled {{ border: 1px solid {c["text_muted"]}; }}
QWidget#editor_viewport {{ background-color: {c["preview_bg"]}; }}
QStatusBar QLabel {{ background: transparent; }}
QToolTip {{ background-color: {c["surface"]}; color: {c["text"]}; border: 1px solid {c["border"]}; }}
""" + control_images(images)
