"""DIAGNOSE (P06d3): Stand P08 (`6dc8f44`) einzelner Funktionen, unverändert übernommen, nur für `DONSTV_OFF`.

- `source_label`: aus `ui/editor_model.py` (Schalter `editor_model_changes`)
- `stylesheet`: aus `ui/theme.py` (Schalter `theme_changes`)

Nicht für den Betrieb. Wird entfernt, sobald der Start auf dem Laptop stabil ist (siehe `ui/diagnose.py`).
"""

from __future__ import annotations

from donstv_studio.ui.theme import DOCK_GAP, FONT_PT, LIST_ROW_HEIGHT, palette


def source_label(source: dict, media_names: dict[str, str] | None = None) -> str:
    """Anzeigename in der Quellenliste (Quellen haben im Datenmodell keinen eigenen Namen)."""
    props = source.get("props") or {}
    if source["kind"] == "text":
        first = (props.get("text") or "").strip().splitlines()
        text = first[0] if first else ""
        return f"Text: {text[:30]}{'…' if len(text) > 30 else ''}" if text else "Text"
    name = (media_names or {}).get(props.get("media_id", ""), "")
    return f"Bild: {name}" if name else "Bild"


def stylesheet(theme: str) -> str:
    """Stylesheet von P08 (ohne Bilder, ohne Regeln für Bedienelemente aus F-76)."""
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
    border: 1px solid {c["border"]}; padding: 1px 4px; min-height: 18px; }}
QSpinBox:focus, QDoubleSpinBox:focus, QLineEdit:focus, QComboBox:focus {{ border: 1px solid {c["accent"]}; }}
QSpinBox:disabled, QDoubleSpinBox:disabled, QLineEdit:disabled, QComboBox:disabled {{ color: {c["text_muted"]}; }}
QComboBox QAbstractItemView {{ background-color: {c["surface"]}; color: {c["text"]};
    selection-background-color: {c["selection_bg"]}; selection-color: {c["selection_text"]}; }}
QCheckBox {{ background: transparent; }}
QCheckBox:focus {{ border: 1px solid {c["accent"]}; }}
QWidget#editor_viewport {{ background-color: {c["preview_bg"]}; }}
QStatusBar QLabel {{ background: transparent; }}
QToolTip {{ background-color: {c["surface"]}; color: {c["text"]}; border: 1px solid {c["border"]}; }}
"""
