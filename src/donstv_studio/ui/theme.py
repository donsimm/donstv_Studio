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

# Sachliche Werte, keine Vorgabe aus den Mockups (docs/04: Farben sind Platzhalter).
PALETTES: dict[str, dict[str, str]] = {
    DARK: {
        "bg": "#1e1f22",           # Fensterhintergrund
        "surface": "#2b2d31",      # Docks, Menüs, Eingabefelder
        "text": "#e6e6e6",
        "text_muted": "#a9adb3",   # Nebentext
        "border": "#43464d",
        "accent": "#4c8dff",       # aktiver Reiter, Fokus
        "accent_text": "#0b0b0c",  # Text auf accent
        "selection_bg": "#3b5fa8",
        "selection_text": "#ffffff",
        "ok": "#5fd38d",           # Statusfarben, nur zusammen mit Text und Symbol (U-04)
        "warn": "#f0b74a",
        "error": "#ff7b72",
        "preview_bg": "#101113",   # Fläche der Vorschau
    },
    LIGHT: {
        "bg": "#f4f5f7",
        "surface": "#ffffff",
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
    },
}

# Alle Kombinationen «Textfarbe auf Hintergrund», die in der Oberfläche vorkommen.
TEXT_PAIRS: tuple[tuple[str, str], ...] = (
    ("text", "bg"),
    ("text", "surface"),
    ("text", "preview_bg"),
    ("text_muted", "bg"),
    ("text_muted", "surface"),
    ("text_muted", "preview_bg"),
    ("accent_text", "accent"),
    ("selection_text", "selection_bg"),
    ("ok", "bg"),
    ("ok", "surface"),
    ("warn", "bg"),
    ("warn", "surface"),
    ("error", "bg"),
    ("error", "surface"),
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


def stylesheet(theme: str) -> str:
    c = palette(theme)
    return f"""
QWidget {{ background-color: {c["bg"]}; color: {c["text"]}; }}
QMainWindow, QDialog {{ background-color: {c["bg"]}; }}
QLabel {{ background: transparent; }}
QLabel[muted="true"] {{ color: {c["text_muted"]}; }}
QMenuBar {{ background-color: {c["surface"]}; color: {c["text"]}; }}
QMenuBar::item:selected {{ background-color: {c["selection_bg"]}; color: {c["selection_text"]}; }}
QMenu {{ background-color: {c["surface"]}; color: {c["text"]}; border: 1px solid {c["border"]}; }}
QMenu::item:selected {{ background-color: {c["selection_bg"]}; color: {c["selection_text"]}; }}
QMenu::item:disabled {{ color: {c["text_muted"]}; }}
QStatusBar {{ background-color: {c["surface"]}; color: {c["text"]}; border-top: 1px solid {c["border"]}; }}
QStatusBar::item {{ border: none; }}
QDockWidget {{ color: {c["text"]}; }}
QDockWidget::title {{ background-color: {c["surface"]}; padding: 4px 8px; border: 1px solid {c["border"]}; }}
QDockWidget > QWidget {{ background-color: {c["surface"]}; }}
QTabBar::tab {{ background-color: {c["surface"]}; color: {c["text"]}; padding: 6px 16px;
               border: 1px solid {c["border"]}; border-bottom: none; }}
QTabBar::tab:selected {{ background-color: {c["accent"]}; color: {c["accent_text"]}; font-weight: bold; }}
QTabBar::tab:hover:!selected {{ background-color: {c["selection_bg"]}; color: {c["selection_text"]}; }}
QTabWidget::pane {{ border: 1px solid {c["border"]}; background-color: {c["surface"]}; }}
QFrame#preview {{ background-color: {c["preview_bg"]}; border: 1px solid {c["border"]}; }}
QFrame#preview QLabel {{ background-color: {c["preview_bg"]}; color: {c["text_muted"]}; }}
QFrame#banner {{ background-color: {c["surface"]}; border: 2px solid {c["warn"]}; }}
QFrame#banner QLabel {{ background-color: {c["surface"]}; color: {c["text"]}; }}
QPushButton {{ background-color: {c["surface"]}; color: {c["text"]}; border: 1px solid {c["border"]};
              padding: 4px 12px; }}
QPushButton:focus, QRadioButton:focus {{ border: 2px solid {c["accent"]}; }}
QRadioButton {{ background: transparent; }}
QToolTip {{ background-color: {c["surface"]}; color: {c["text"]}; border: 1px solid {c["border"]}; }}
"""
