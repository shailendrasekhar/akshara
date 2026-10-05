"""
Library panel — every document the user has opened, with reading progress.

Cards show title, author and progress; a filter box and sort menu sit on
top. Right-click a card to remove it, reveal it in the file manager, or point
Akshara at a moved file.
"""

from __future__ import annotations

import os

from PyQt6.QtCore import QSize, Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QColor, QDesktopServices, QPainter
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .db import DocumentRow, Store, hash_file
from .ui.theme import DARK, MONO_FONT, Palette

SORTS = {"recent": "Recently opened", "title": "Title", "progress": "Progress"}


def sort_documents(docs: list[DocumentRow], key: str) -> list[DocumentRow]:
    if key == "title":
        return sorted(docs, key=lambda d: (d.title or "").casefold())
    if key == "progress":
        return sorted(docs, key=lambda d: d.progress, reverse=True)
    return sorted(docs, key=lambda d: d.last_opened or 0, reverse=True)


def filter_documents(docs: list[DocumentRow], text: str) -> list[DocumentRow]:
    needle = text.strip().casefold()
    if not needle:
        return docs
    return [
        d
        for d in docs
        if needle in (d.title or "").casefold()
        or needle in (d.author or "").casefold()
        or needle in os.path.basename(d.path).casefold()
    ]


# ---------- Single document card ---------------------------------------------


class _ProgressBar(QWidget):
    def __init__(self, fraction: float, palette: Palette, parent=None):
        super().__init__(parent)
        self._fraction = fraction
        self._palette = palette
        self.setFixedHeight(4)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_fraction(self, f: float) -> None:
        self._fraction = max(0.0, min(1.0, f))
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(self._palette.border_light))
        w = int(self.width() * self._fraction)
        if w > 0:
            r = self.rect()
            r.setWidth(w)
            p.fillRect(r, QColor(self._palette.accent))


class DocCard(QWidget):
    clicked = pyqtSignal(object)  # DocumentRow
    context = pyqtSignal(object, object)  # DocumentRow, global QPoint

    def __init__(self, doc: DocumentRow, palette: Palette, active: bool = False, parent=None):
        super().__init__(parent)
        self.doc = doc
        self._palette = palette
        self._active = active
        self._missing = not doc.exists
        self.setObjectName("docCard")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(doc.path + ("\n(file not found)" if self._missing else ""))

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 11, 14, 11)
        lay.setSpacing(4)
        self._title = QLabel(doc.title or os.path.basename(doc.path))
        self._title.setWordWrap(True)
        lay.addWidget(self._title)
        self._author = QLabel(doc.author or "")
        self._author.setVisible(bool(doc.author))
        lay.addWidget(self._author)

        row = QHBoxLayout()
        row.setSpacing(8)
        self._bar = _ProgressBar(doc.progress, palette)
        row.addWidget(self._bar, 1)
        self._pct = QLabel()
        row.addWidget(self._pct)
        lay.addLayout(row)
        self._pages = QLabel()
        lay.addWidget(self._pages)
        self.update_progress(doc.last_page)
        self._style()

    def update_progress(self, last_page: int) -> None:
        self.doc.last_page = last_page
        self._bar.set_fraction(self.doc.progress)
        self._pct.setText(f"{round(self.doc.progress * 100)}%")
        status = "  ·  missing" if self._missing else ""
        self._pages.setText(f"p. {last_page} / {self.doc.pages}{status}")

    def set_active(self, active: bool) -> None:
        self._active = active
        self._style()

    def _style(self) -> None:
        P = self._palette
        border = P.accent if self._active else P.border
        self.setStyleSheet(
            f"""
            QWidget#docCard {{ background:{P.bg_card}; border:1px solid {border}; border-radius:6px; }}
            QWidget#docCard:hover {{ background:{P.bg_hover}; border-color:{P.border_light if not self._active else P.accent}; }}
            """
        )
        ink = P.text_muted if self._missing else P.text
        self._title.setStyleSheet(
            f"font-size:14px;font-weight:600;color:{ink};background:transparent;border:none;"
        )
        mono = f"font-family:{MONO_FONT};font-size:12px;color:{P.text_muted};background:transparent;border:none;"
        self._author.setStyleSheet(
            f"font-size:12px;color:{P.text_secondary};background:transparent;border:none;"
        )
        self._pct.setStyleSheet(mono)
        self._pages.setStyleSheet(mono.replace(P.text_muted, P.error) if self._missing else mono)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.doc)
        super().mousePressEvent(event)

    def contextMenuEvent(self, event):
        self.context.emit(self.doc, event.globalPos())


# ---------- Panel ------------------------------------------------------------


class LibraryPanel(QWidget):
    open_document = pyqtSignal(str)
    document_removed = pyqtSignal(str)  # doc id
    sort_changed = pyqtSignal(str)

    def __init__(self, store: Store, palette: Palette = DARK, sort: str = "recent", parent=None):
        super().__init__(parent)
        self.store = store
        self._palette = palette
        self._sort = sort if sort in SORTS else "recent"
        self._active_path = ""
        self._cards: list[DocCard] = []
        self._docs: list[DocumentRow] = []
        self._build()
        self.refresh()

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 0)
        outer.setSpacing(8)

        top = QHBoxLayout()
        top.setSpacing(6)
        self.filter = QLineEdit()
        self.filter.setPlaceholderText("Filter library…")
        self.filter.setClearButtonEnabled(True)
        self.filter.textChanged.connect(lambda _: self._populate())
        top.addWidget(self.filter, 1)
        self.sort_box = QComboBox()
        for key, label in SORTS.items():
            self.sort_box.addItem(label, key)
        self.sort_box.setCurrentIndex(list(SORTS).index(self._sort))
        self.sort_box.currentIndexChanged.connect(self._on_sort)
        self.sort_box.setToolTip("Sort")
        top.addWidget(self.sort_box)
        outer.addLayout(top)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._cards_widget = QWidget()
        self._cards_layout = QVBoxLayout(self._cards_widget)
        self._cards_layout.setContentsMargins(0, 0, 0, 10)
        self._cards_layout.setSpacing(8)
        self._scroll.setWidget(self._cards_widget)
        outer.addWidget(self._scroll, 1)

    def sizeHint(self) -> QSize:
        return QSize(280, 400)

    # ---- public ----

    def set_palette(self, palette: Palette) -> None:
        self._palette = palette
        self._populate()

    def set_dark_mode(self, _dark: bool) -> None:  # legacy API
        self._populate()

    def set_active_path(self, path: str) -> None:
        self._active_path = path
        for c in self._cards:
            c.set_active(c.doc.path == path)

    def update_document_progress(self, file_path: str, last_page: int) -> None:
        for card in self._cards:
            if card.doc.path == file_path:
                card.update_progress(last_page)
                return

    def refresh(self) -> None:
        self._docs = self.store.list_documents()
        self._populate()

    @property
    def visible_documents(self) -> list[DocumentRow]:
        return [c.doc for c in self._cards]

    # ---- internals ----

    def _on_sort(self, idx: int) -> None:
        self._sort = self.sort_box.itemData(idx)
        self.sort_changed.emit(self._sort)
        self._populate()

    def _populate(self) -> None:
        while self._cards_layout.count():
            item = self._cards_layout.takeAt(0)
            if item is not None and (w := item.widget()) is not None:
                w.deleteLater()
        self._cards.clear()

        docs = sort_documents(filter_documents(self._docs, self.filter.text()), self._sort)
        for doc in docs:
            card = DocCard(doc, self._palette, active=doc.path == self._active_path)
            card.clicked.connect(self._on_click)
            card.context.connect(self._on_context)
            self._cards_layout.addWidget(card)
            self._cards.append(card)
        if not docs:
            msg = (
                "No documents yet.\nOpen a PDF to get started."
                if not self._docs
                else "Nothing matches the filter."
            )
            empty = QLabel(msg)
            empty.setObjectName("muted")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setContentsMargins(12, 24, 12, 24)
            self._cards_layout.addWidget(empty)
        self._cards_layout.addStretch(1)

    def _on_click(self, doc: DocumentRow) -> None:
        if doc.exists:
            self.open_document.emit(doc.path)
        else:
            self._locate(doc)

    def _on_context(self, doc: DocumentRow, global_pos) -> None:
        menu = QMenu(self)
        if doc.exists:
            menu.addAction("Open", lambda: self.open_document.emit(doc.path))
            menu.addAction(
                "Show in folder",
                lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(doc.path))),
            )
        else:
            menu.addAction("Locate file…", lambda: self._locate(doc))
        menu.addSeparator()
        menu.addAction("Remove from library", lambda: self._remove(doc))
        menu.exec(global_pos)

    def _remove(self, doc: DocumentRow) -> None:
        answer = QMessageBox.question(
            self,
            "Remove from library",
            f"Remove “{doc.title}” from the library?\n\n"
            "Bookmarks and highlights for it are deleted; reading-time statistics are kept. "
            "The PDF file itself is not touched.",
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.store.remove_document(doc.id)
            self.document_removed.emit(doc.id)
            self.refresh()

    def _locate(self, doc: DocumentRow) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, f"Locate “{doc.title}”", os.path.dirname(doc.path), "PDF Files (*.pdf)"
        )
        if not path:
            return
        if hash_file(path) != doc.id:
            QMessageBox.warning(
                self, "Different file", "That file's contents differ from the library entry."
            )
            return
        self.store.relocate_document(doc.id, path)
        self.refresh()
        self.open_document.emit(path)
