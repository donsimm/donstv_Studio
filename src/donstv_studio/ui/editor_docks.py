"""Inhalt der Docks «Overlays», «Quellen», «Eigenschaften» und «Steuerung» (F-12, F-13, F-14, F-66, F-65).

Stil nach OBS (docs/referenz/screenshot-obs-30.2.3.1.png): Liste oder Felder oben, unten eine Schaltflächenleiste mit
einfarbigen Symbolen (Plus, Papierkorb, Pfeile) in der Textfarbe des Themes.
"""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from donstv_studio.overlays.models import MAX_SOURCE_NAME
from donstv_studio.ui import diagnose, icons, theme
from donstv_studio.ui import geometry as geo
from donstv_studio.ui.editor_model import EditorModel, box_of, source_label
from donstv_studio.ui.editor_prefs import GRID_MAX, GRID_MIN, EditorPrefs
from donstv_studio.ui.geometry import Box
from donstv_studio.ui.preview_web import MAX_FPS, MIN_FPS

BAR_BUTTON = 26  # Grösse der Schaltflächen in der Leiste unten (OBS-Bild: 26)
COORD_RANGE = 100_000
SIDE_MAX = 16_384
EYE_ZONE = 24  # Breite des Bereichs links in der Quellenliste, in dem ein Klick die Sichtbarkeit umschaltet
OUTPUTS = (("browser", "Browserquelle"), ("ndi", "NDI"))


def ask_text(parent: QWidget, title: str, label: str, text: str = "", ok: str = "OK") -> str | None:
    """Fragt einen Text ab (Schaltflächen auf Deutsch). None bei Abbruch."""
    dlg = QInputDialog(parent)
    dlg.setWindowTitle(title)
    dlg.setLabelText(label)
    dlg.setTextValue(text)
    dlg.setOkButtonText(ok)
    dlg.setCancelButtonText("Abbrechen")
    return dlg.textValue() if dlg.exec() else None


def compact_spin(spin: QSpinBox) -> None:
    """Mindestbreite eines Zahlenfeldes: grösster Wert mit Einheit, Pfeil-Schaltflächen, Rand (F-76).

    Mit den eigenen Pfeil-Schaltflächen (Stylesheet) schlägt Qt deren Breite auf die Mindestbreite auf; ohne diese
    Grenze würde das Dock «Steuerung» breiter als die anderen und die Standardanordnung (P05b) ungleich.
    """
    text = f"{spin.prefix()}{spin.maximum()}{spin.suffix()}"
    spin.setMinimumWidth(spin.fontMetrics().horizontalAdvance(text) + theme.SPIN_BUTTON_WIDTH + 12)


def confirm(parent: QWidget, title: str, text: str, ok: str) -> bool:
    box = QMessageBox(
        QMessageBox.Icon.Question, title, text, QMessageBox.StandardButton.NoButton, parent
    )
    yes = box.addButton(ok, QMessageBox.ButtonRole.AcceptRole)
    box.addButton("Abbrechen", QMessageBox.ButtonRole.RejectRole)
    box.exec()
    return box.clickedButton() is yes


class IconButton(QToolButton):
    """Schaltfläche der Leiste unten: einfarbiges Symbol in der Textfarbe, Tipp und Name für Hilfsmittel."""

    def __init__(self, kind: str, tip: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.kind = kind
        self.setObjectName(f"btn_{kind}")
        self.setToolTip(tip)
        self.setAccessibleName(tip)
        self.setAutoRaise(True)
        self.setFixedSize(BAR_BUTTON, BAR_BUTTON)
        self.setIconSize(icons.icon_size())
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self._theme = theme.DEFAULT_THEME
        self.apply_theme(self._theme)

    def apply_theme(self, name: str) -> None:
        self._theme = name
        pal = theme.palette(name)
        icon = icons.make_icon(self.kind, pal["text"])
        # Ausgegraut: Nebentext-Farbe (Kontrast ≥ 4,5:1 zur Fläche, siehe theme.TEXT_PAIRS)
        from PyQt6.QtGui import QIcon

        disabled = icons.draw_icon(self.kind, pal["text_muted"])
        icon.addPixmap(disabled, QIcon.Mode.Disabled)
        self.setIcon(icon)


class ButtonBar(QWidget):
    """Leiste unten im Dock (wie bei OBS)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("dockBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.lay = QHBoxLayout(self)
        self.lay.setContentsMargins(3, 3, 3, 3)
        self.lay.setSpacing(2)
        self.buttons: list[IconButton] = []

    def add(self, kind: str, tip: str, slot: Callable | None = None) -> IconButton:
        b = IconButton(kind, tip, self)
        if slot is not None:
            b.clicked.connect(lambda _=False: slot())
        self.lay.addWidget(b)
        self.buttons.append(b)
        return b

    def finish(self) -> None:
        self.lay.addStretch(1)

    def apply_theme(self, name: str) -> None:
        for b in self.buttons:
            b.apply_theme(name)


def _body(parent: QWidget | None = None) -> tuple[QFrame, QVBoxLayout]:
    body = QFrame(parent)
    body.setObjectName("dockbody")
    lay = QVBoxLayout(body)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(0)
    return body, lay


def _hint(text: str) -> QLabel:
    label = QLabel(text)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setWordWrap(True)
    label.setProperty("muted", True)
    return label


class _ListWithHint(QStackedWidget):
    """Liste, die bei leerem Inhalt einen Hinweistext zeigt (wie «Sie haben keine Quellen hinzugefügt» bei OBS)."""

    def __init__(self, listing: QListWidget, hint: str) -> None:
        super().__init__()
        self.listing = listing
        self.setObjectName("dockInner")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.hint = _hint(hint)
        self.addWidget(listing)
        self.addWidget(self.hint)

    def sync(self) -> None:
        self.setCurrentWidget(self.listing if self.listing.count() else self.hint)


# --- Overlays --------------------------------------------------------------------------------------


class OverlaysDock(QWidget):
    def __init__(self, model: EditorModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.model = model
        self.ask_text = lambda *a, **k: ask_text(self, *a, **k)  # austauschbar (Tests)
        self.confirm = lambda *a, **k: confirm(self, *a, **k)
        self._updating = False
        self.list = QListWidget()
        self.list.setObjectName("overlay_list")
        self.list.setEditTriggers(
            QListWidget.EditTrigger.DoubleClicked | QListWidget.EditTrigger.EditKeyPressed
        )
        self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list.setAccessibleName("Overlays")
        self.stack = _ListWithHint(
            self.list, "Noch kein Overlay.\nKlicke auf +, um eines anzulegen."
        )
        self.bar = ButtonBar()
        self.add_button = self.bar.add("plus", "Overlay anlegen", self.add)
        self.delete_button = self.bar.add("trash", "Overlay löschen", self.remove)
        self.duplicate_button = self.bar.add("duplicate", "Overlay duplizieren", self.duplicate)
        self.bar.finish()
        self.body, lay = _body()
        lay.addWidget(self.stack, 1)
        lay.addWidget(self.bar)

        self.list.currentItemChanged.connect(self._current_changed)
        self.list.itemChanged.connect(self._renamed)
        self.list.customContextMenuRequested.connect(self._menu)
        model.overlays_changed.connect(self.refresh)
        model.current_changed.connect(self._sync_current)
        self.refresh()

    def refresh(self) -> None:
        self._updating = True
        ids = [self.list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.list.count())]
        if ids == [o["id"] for o in self.model.overlays]:
            # Nur die Namen können sich geändert haben. Die Liste darf hier nicht geleert werden: wir werden
            # womöglich aus `itemChanged` gerufen (Umbenennen), und das Element würde unter uns gelöscht.
            for i, o in enumerate(self.model.overlays):
                if self.list.item(i).text() != o["name"]:
                    self.list.item(i).setText(o["name"])
        else:
            self.list.clear()
            for o in self.model.overlays:
                item = QListWidgetItem(o["name"])
                item.setData(Qt.ItemDataRole.UserRole, o["id"])
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
                self.list.addItem(item)
        self._updating = False
        self._sync_current(self.model.current_id)
        self.stack.sync()
        self._enable()

    def _enable(self) -> None:
        has = self.model.available
        cur = self.model.current() is not None
        self.add_button.setEnabled(has)
        self.delete_button.setEnabled(cur)
        self.duplicate_button.setEnabled(cur)

    def _sync_current(self, overlay_id) -> None:
        self._updating = True
        for i in range(self.list.count()):
            if self.list.item(i).data(Qt.ItemDataRole.UserRole) == overlay_id:
                self.list.setCurrentRow(i)
                break
        else:
            self.list.setCurrentRow(-1)
        self._updating = False
        self._enable()

    def _current_changed(self, item, _prev) -> None:
        if not self._updating and item is not None:
            self.model.select_overlay(item.data(Qt.ItemDataRole.UserRole))

    def _renamed(self, item: QListWidgetItem) -> None:
        if self._updating:
            return
        oid = item.data(Qt.ItemDataRole.UserRole)
        self.model.rename_overlay(oid, item.text())
        o = self.model.overlay(oid)
        if (
            o is not None and item.text().strip() != o["name"]
        ):  # leerer Name: alten wiederherstellen
            self._updating = True
            item.setText(o["name"])
            self._updating = False

    def _next_name(self) -> str:
        names = {o["name"] for o in self.model.overlays}
        i = 1
        while f"Overlay {i}" in names:
            i += 1
        return f"Overlay {i}"

    def add(self) -> None:
        name = self.ask_text("Overlay anlegen", "Name des Overlays:", self._next_name(), "Anlegen")
        if name is not None and name.strip():
            self.model.create_overlay(name.strip())

    def rename_current(self) -> None:
        item = self.list.currentItem()
        if item is not None:
            self.list.editItem(item)

    def duplicate(self) -> None:
        if self.model.current_id:
            self.model.duplicate_overlay(self.model.current_id)

    def remove(self) -> None:
        o = self.model.current()
        if o is not None and self.confirm(
            "Overlay löschen", f"Overlay «{o['name']}» mit allen Quellen löschen?", "Löschen"
        ):
            self.model.delete_overlay(o["id"])

    def _menu(self, pos) -> None:
        if self.list.itemAt(pos) is None:
            return
        menu = QMenu(self)
        menu.addAction("Umbenennen", self.rename_current)
        menu.addAction("Duplizieren", self.duplicate)
        menu.addAction("Löschen", self.remove)
        menu.exec(self.list.mapToGlobal(pos))

    def apply_theme(self, name: str) -> None:
        self.bar.apply_theme(name)


# --- Quellen ---------------------------------------------------------------------------------------


class SourceList(QListWidget):
    """Quellenliste mit Augensymbol links (Klick schaltet die Sichtbarkeit) und Ziehen zum Umordnen."""

    visibility_clicked = pyqtSignal(str)
    reordered = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("source_list")
        self.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        # Doppelklick ist für das Quellenfenster (F-79) reserviert; umbenannt wird über Menü, F2 oder «Name».
        self.setEditTriggers(QListWidget.EditTrigger.NoEditTriggers)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.setIconSize(icons.icon_size())
        self.setAccessibleName("Quellen")
        self.model().rowsMoved.connect(lambda *_: self.reordered.emit())

    def mousePressEvent(self, e) -> None:
        item = self.itemAt(e.position().toPoint())
        if (
            item is not None
            and e.button() == Qt.MouseButton.LeftButton
            and e.position().x() < EYE_ZONE
        ):
            self.visibility_clicked.emit(item.data(Qt.ItemDataRole.UserRole))
            return
        super().mousePressEvent(e)


class SourcesDock(QWidget):
    def __init__(self, model: EditorModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.model = model
        self.pick_image = lambda: QFileDialog.getOpenFileName(
            self,
            "Bild wählen",
            "",
            "Bilder und Video (*.png *.jpg *.jpeg *.gif *.webp *.svg *.webm)",
        )[0]
        self.ask_text = lambda *a, **k: ask_text(self, *a, **k)
        self.confirm = lambda *a, **k: confirm(self, *a, **k)
        self._updating = False
        self._theme = theme.DEFAULT_THEME
        self.list = SourceList()
        self.stack = _ListWithHint(
            self.list,
            "Du hast noch keine Quellen.\nKlicke auf +, um eine\nText- oder Bildquelle hinzuzufügen.",
        )
        self.bar = ButtonBar()
        self.add_button = self.bar.add("plus", "Quelle hinzufügen")
        menu = QMenu(self.add_button)
        self.text_action = QAction("Text", menu)
        self.image_action = QAction("Bild …", menu)
        menu.addAction(self.text_action)
        menu.addAction(self.image_action)
        self.add_button.setMenu(menu)
        self.add_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.text_action.triggered.connect(self.add_text)
        self.image_action.triggered.connect(self.add_image)
        self.delete_button = self.bar.add("trash", "Quelle entfernen", self.remove)
        self.up_button = self.bar.add(
            "up", "Nach vorn (in der Liste nach oben)", lambda: self._move(+1)
        )
        self.down_button = self.bar.add(
            "down", "Nach hinten (in der Liste nach unten)", lambda: self._move(-1)
        )
        self.bar.finish()
        self.body, lay = _body()
        lay.addWidget(self.stack, 1)
        lay.addWidget(self.bar)
        # F-74: Umbenennen mit F2, solange der Fokus in der Quellenliste (oder in der Vorschau, siehe MainWindow) liegt
        self.rename_action = QAction("Umbenennen", self)
        self.rename_action.setObjectName("rename_source")
        self.rename_action.setShortcut(QKeySequence(Qt.Key.Key_F2))
        self.rename_action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.rename_action.triggered.connect(self.rename_current)
        if not diagnose.off("rename"):  # DIAGNOSE (P06d2): ohne Umbenennen wie P08
            self.list.addAction(self.rename_action)

        self.list.currentItemChanged.connect(self._current_changed)
        self.list.customContextMenuRequested.connect(self._menu)
        self.list.visibility_clicked.connect(self._toggle)
        self.list.reordered.connect(lambda: QTimer.singleShot(0, self._reordered))
        model.sources_changed.connect(self.refresh)
        model.selection_changed.connect(self._sync_selection)
        self.refresh()

    def refresh(self) -> None:
        self._updating = True
        self.list.clear()
        for s in reversed(self.model.sources()):  # vorderste Quelle oben, wie bei OBS
            item = QListWidgetItem(source_label(s, self.model.media_names))
            item.setData(Qt.ItemDataRole.UserRole, s["id"])
            item.setIcon(
                icons.make_icon("eye" if s.get("visible", True) else "eye_off", self._icon_color())
            )
            item.setToolTip(
                f"{'Sichtbar' if s.get('visible', True) else 'Ausgeblendet'} (Klick auf das Auge schaltet um)"
            )
            self.list.addItem(item)
        self._updating = False
        self._sync_selection(self.model.selected_id)
        self.stack.sync()
        self._enable()

    def _icon_color(self) -> str:
        return theme.palette(self._theme)["text"]

    def _enable(self) -> None:
        cur = self.model.current() is not None
        sel = self.model.selected_id is not None
        self.add_button.setEnabled(cur)
        self.delete_button.setEnabled(sel)
        ids = [s["id"] for s in self.model.sources()]
        i = ids.index(self.model.selected_id) if sel and self.model.selected_id in ids else -1
        self.up_button.setEnabled(sel and 0 <= i < len(ids) - 1)
        self.down_button.setEnabled(sel and i > 0)

    def _sync_selection(self, source_id) -> None:
        self._updating = True
        for i in range(self.list.count()):
            if self.list.item(i).data(Qt.ItemDataRole.UserRole) == source_id:
                self.list.setCurrentRow(i)
                break
        else:
            self.list.setCurrentRow(-1)
        self._updating = False
        self._enable()

    def _current_changed(self, item, _prev) -> None:
        if not self._updating:
            self.model.select_source(
                item.data(Qt.ItemDataRole.UserRole) if item is not None else None
            )

    def _toggle(self, source_id: str) -> None:
        s = self.model.source(source_id)
        if s is not None:
            self.model.set_visible(source_id, not s.get("visible", True))

    def _reordered(self) -> None:
        top_first = [
            self.list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.list.count())
        ]
        self.model.set_order(list(reversed(top_first)))
        self.refresh()

    def _move(self, direction: int) -> None:
        if self.model.selected_id:
            self.model.move_in_order(self.model.selected_id, direction)

    def add_text(self) -> None:
        text = self.ask_text("Textquelle hinzufügen", "Text:", "Text", "Hinzufügen")
        if text is not None:
            self.model.add_text_source(text.strip() or "Text")

    def add_image(self) -> None:
        path = self.pick_image()
        if not path:
            return
        from PyQt6.QtGui import QImageReader

        size = QImageReader(path).size()  # leer bei SVG oder Video; dann gilt die Standardgrösse
        self.model.add_image_source(path, (size.width(), size.height()) if size.isValid() else None)

    def remove(self) -> None:
        sid = self.model.selected_id
        if sid and self.confirm("Quelle entfernen", "Die gewählte Quelle entfernen?", "Entfernen"):
            self.model.delete_source(sid)

    def rename_current(self) -> None:
        """F-74: fragt den neuen Namen der gewählten Quelle ab. Leer wird abgelehnt (Meldung in der Statuszeile)."""
        s = self.model.selected()
        if s is None:
            return
        name = self.ask_text(
            "Quelle umbenennen", "Name der Quelle:", source_label(s, self.model.media_names), "OK"
        )
        if name is not None:
            self.model.rename_source(s["id"], name)

    def _menu(self, pos) -> None:
        item = self.list.itemAt(pos)
        if item is None:
            return
        self.model.select_source(item.data(Qt.ItemDataRole.UserRole))
        if diagnose.off("rename"):  # DIAGNOSE (P06d2): kein Kontextmenü wie P08
            return
        menu = QMenu(self)
        menu.addAction(self.rename_action)
        menu.exec(self.list.mapToGlobal(pos))

    def apply_theme(self, name: str) -> None:
        self._theme = name
        self.bar.apply_theme(name)
        self.refresh()


# --- Eigenschaften ---------------------------------------------------------------------------------


class PropertiesDock(QWidget):
    FIELDS = ("x", "y", "w", "h", "rot")

    def __init__(self, model: EditorModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.model = model
        self._updating = False
        self.fields: dict[str, QSpinBox | QDoubleSpinBox] = {}
        grid = QGridLayout()
        grid.setContentsMargins(8, 6, 8, 4)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(4)
        # F-74: Name oben, nur eine Bezeichnung. Übernommen mit Eingabe oder beim Verlassen des Feldes.
        self.name = QLineEdit()
        self.name.setObjectName("field_name")
        self.name.setAccessibleName("Name der Quelle")
        self.name.setMaxLength(MAX_SOURCE_NAME)
        self.name.editingFinished.connect(self._name_edited)
        if diagnose.off(
            "rename"
        ):  # DIAGNOSE (P06d2): kein Feld «Name» wie P08 (das Objekt bleibt unsichtbar)
            self.name.setParent(self)
            self.name.hide()
        else:
            grid.addWidget(QLabel("Name"), 0, 0)
            grid.addWidget(self.name, 0, 1, 1, 3)
        for row, (label, key, lo, hi) in enumerate(
            (("X", "x", -COORD_RANGE, COORD_RANGE), ("Breite", "w", 1, SIDE_MAX)), start=1
        ):
            grid.addWidget(QLabel(label), row, 0)
            grid.addWidget(self._spin(key, lo, hi), row, 1)
        for row, (label, key, lo, hi) in enumerate(
            (("Y", "y", -COORD_RANGE, COORD_RANGE), ("Höhe", "h", 1, SIDE_MAX)), start=1
        ):
            grid.addWidget(QLabel(label), row, 2)
            grid.addWidget(self._spin(key, lo, hi), row, 3)
        grid.addWidget(QLabel("Drehung"), 3, 0)
        rot = QDoubleSpinBox()
        rot.setRange(-360.0, 360.0)
        rot.setDecimals(1)
        rot.setSuffix(" °")
        rot.setObjectName("field_rot")
        rot.setAccessibleName("Drehung in Grad")
        rot.valueChanged.connect(lambda _v: self._edited("rot"))
        self.fields["rot"] = rot
        grid.addWidget(rot, 3, 1)
        self.hint = QLabel("Keine Quelle gewählt")
        self.hint.setProperty("muted", True)
        self.hint.setObjectName("properties_hint")
        grid.addWidget(self.hint, 3, 2, 1, 2)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)
        fields = QWidget()
        fields.setObjectName("dockInner")
        fields.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        fields.setLayout(grid)

        self.bar = ButtonBar()
        self.align_buttons: dict[str, IconButton] = {}
        for how in geo.ALIGNMENTS:
            self.align_buttons[how] = self.bar.add(
                f"align_{how}", geo.ALIGN_LABELS[how], lambda h=how: self.align(h)
            )
        self.bar.finish()
        self.body, lay = _body()
        lay.addWidget(fields)
        lay.addStretch(1)
        lay.addWidget(self.bar)

        model.box_changed.connect(lambda _id: self.refresh())
        model.selection_changed.connect(lambda _id: self.refresh())
        model.current_changed.connect(lambda _id: self.refresh())
        model.sources_changed.connect(self.refresh)
        self.refresh()

    def _spin(self, key: str, lo: int, hi: int) -> QSpinBox:
        s = QSpinBox()
        s.setRange(lo, hi)
        s.setSuffix(" px")
        s.setObjectName(f"field_{key}")
        s.setAccessibleName({"x": "X", "y": "Y", "w": "Breite", "h": "Höhe"}[key] + " in Pixeln")
        s.valueChanged.connect(lambda _v, k=key: self._edited(k))
        self.fields[key] = s
        return s

    def current_box(self) -> Box | None:
        s = self.model.selected()
        return box_of(s) if s else None

    def refresh(self) -> None:
        box = self.current_box()
        self._updating = True
        s = self.model.selected()
        self.name.setEnabled(s is not None)
        label = source_label(s, self.model.media_names) if s else ""
        if self.name.text() != label and not (self.name.hasFocus() and self.name.isModified()):
            self.name.setText(label)
            self.name.setModified(False)
        for f in self.fields.values():
            f.setEnabled(box is not None)
        if box is not None:
            for key, value in (
                ("x", box.x),
                ("y", box.y),
                ("w", box.w),
                ("h", box.h),
                ("rot", box.rot),
            ):
                f = self.fields[key]
                if f.value() != value:
                    f.setValue(value)
        self.hint.setVisible(box is None)
        for b in self.align_buttons.values():
            b.setEnabled(box is not None)
        self._updating = False

    def _name_edited(self) -> None:
        if self._updating:
            return
        s = self.model.selected()
        if s is None:
            return
        self.name.setModified(False)
        if not self.model.rename_source(s["id"], self.name.text()):
            # abgelehnt (leer): Meldung kam über model.error; alten Namen wieder anzeigen
            self.name.setText(source_label(s, self.model.media_names))

    def _edited(self, key: str) -> None:
        if self._updating:
            return
        box, s = self.current_box(), self.model.selected()
        if box is None or s is None:
            return
        f = self.fields
        new = Box(
            f["x"].value(), f["y"].value(), f["w"].value(), f["h"].value(), float(f["rot"].value())
        )
        self.model.change_box(s["id"], new, merge_key=f"field:{key}")

    def align(self, how: str) -> None:
        box, s = self.current_box(), self.model.selected()
        if box is None or s is None:
            return
        w, h = self.model.size()
        self.model.change_box(s["id"], geo.align_box(box, how, w, h))

    def apply_theme(self, name: str) -> None:
        self.bar.apply_theme(name)


# --- Steuerung -------------------------------------------------------------------------------------


class ControlDock(QWidget):
    copied = pyqtSignal()

    def __init__(
        self, model: EditorModel, prefs: EditorPrefs, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.model, self.prefs = model, prefs
        self._updating = False
        grid = QGridLayout()
        grid.setContentsMargins(8, 6, 8, 6)
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(5)

        grid.addWidget(QLabel("Browserquelle"), 0, 0)
        self.url = QLineEdit()
        self.url.setReadOnly(True)
        self.url.setObjectName("url_field")
        self.url.setAccessibleName("Adresse der Browserquelle")
        grid.addWidget(self.url, 0, 1, 1, 3)
        self.copy_button = QPushButton("Kopieren")
        self.copy_button.setObjectName("copy_url")
        self.copy_button.clicked.connect(self.copy_url)
        grid.addWidget(self.copy_button, 0, 4)

        grid.addWidget(QLabel("Ausgabe"), 1, 0)
        self.output = QComboBox()
        self.output.setObjectName("output_combo")
        self.output.setAccessibleName("Ausgabeart")
        for key, label in OUTPUTS:
            self.output.addItem(label, key)
        self.output.currentIndexChanged.connect(self._output_changed)
        grid.addWidget(self.output, 1, 1, 1, 2)
        self.output_status = QLabel()
        self.output_status.setObjectName("output_status")
        grid.addWidget(self.output_status, 1, 3, 1, 2)

        grid.addWidget(QLabel("Vorschau"), 2, 0)
        self.fps = QSpinBox()
        self.fps.setRange(MIN_FPS, MAX_FPS)
        self.fps.setSuffix(" Bilder/s")
        self.fps.setObjectName("preview_fps")
        self.fps.setAccessibleName("Bildrate der Vorschau")
        self.fps.valueChanged.connect(lambda v: not self._updating and prefs.set_fps(v))
        grid.addWidget(self.fps, 2, 1, 1, 2)
        self.shrink = QCheckBox("Vorschau verkleinern")
        self.shrink.setObjectName("preview_shrink")
        self.shrink.toggled.connect(lambda on: not self._updating and prefs.set_shrink(on))
        grid.addWidget(self.shrink, 2, 3, 1, 2)

        self.snap = QCheckBox("Einrasten")
        self.snap.setObjectName("snap")
        self.snap.toggled.connect(lambda on: not self._updating and prefs.set_snap(on))
        grid.addWidget(self.snap, 3, 0, 1, 2)
        self.grid_check = QCheckBox("Raster")
        self.grid_check.setObjectName("grid")
        self.grid_check.toggled.connect(lambda on: not self._updating and prefs.set_grid(on))
        grid.addWidget(self.grid_check, 3, 2)
        self.grid_size = QSpinBox()
        self.grid_size.setRange(GRID_MIN, GRID_MAX)
        self.grid_size.setSuffix(" px")
        self.grid_size.setObjectName("grid_size")
        self.grid_size.setAccessibleName("Rasterweite in Pixeln")
        self.grid_size.valueChanged.connect(lambda v: not self._updating and prefs.set_grid_size(v))
        compact_spin(self.grid_size)
        grid.addWidget(self.grid_size, 3, 3)
        self.clear_guides = QPushButton("Hilfslinien löschen")
        self.clear_guides.setObjectName("clear_guides")
        self.clear_guides.clicked.connect(lambda: model.set_guides([], []))
        grid.addWidget(self.clear_guides, 3, 4)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)

        self.body, lay = _body()
        wrap = QWidget()
        wrap.setObjectName("dockInner")
        wrap.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        wrap.setLayout(grid)
        lay.addWidget(wrap)
        lay.addStretch(1)

        model.current_changed.connect(lambda _id: self.refresh())
        model.meta_changed.connect(self.refresh)
        model.guides_changed.connect(self._guides_changed)
        prefs.changed.connect(lambda _k: self.refresh())
        self.refresh()

    def refresh(self) -> None:
        o = self.model.current()
        self._updating = True
        self.url.setText(
            self.model.preview_url() or ""
        )  # Anzeige für den Nutzer; nie ins Protokoll
        self.url.setCursorPosition(
            0
        )  # den Anfang der Adresse zeigen (Rechner und Port), nicht das Ende
        self.output.setCurrentIndex(max(0, self.output.findData(o["output"] if o else "browser")))
        self.output_status.setText(("Ausgabe: " + o["output_status"]) if o else "")
        has = o is not None
        for w in (self.url, self.copy_button, self.output):
            w.setEnabled(has)
        self.clear_guides.setEnabled(has and bool(self.model.guides()[0] or self.model.guides()[1]))
        self.fps.setValue(self.prefs.fps)
        self.shrink.setChecked(self.prefs.shrink)
        self.snap.setChecked(self.prefs.snap)
        self.grid_check.setChecked(self.prefs.grid)
        self.grid_size.setValue(self.prefs.grid_size)
        self.grid_size.setEnabled(self.prefs.grid)
        self._updating = False

    def _guides_changed(self) -> None:
        v, h = self.model.guides()
        self.clear_guides.setEnabled(self.model.current() is not None and bool(v or h))

    def _output_changed(self, _i: int) -> None:
        if self._updating or self.model.current_id is None:
            return
        self.model.set_output(self.model.current_id, self.output.currentData())

    def apply_theme(self, name: str) -> None:
        pass  # keine Symbole; Farben kommen aus dem Stylesheet

    def copy_url(self) -> None:
        url = self.model.preview_url()
        if url:
            QApplication.clipboard().setText(url)
            self.copied.emit()
