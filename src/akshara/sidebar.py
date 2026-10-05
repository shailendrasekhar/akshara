"""Document sidebar: table of contents, bookmarks, and highlights & notes."""

from __future__ import annotations

import datetime as dt

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QStackedWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .db import BookmarkRow, HighlightRow
from .pdf_handler import OutlineItem

ROLE = Qt.ItemDataRole.UserRole


def _empty_label(text: str) -> QLabel:
    lab = QLabel(text)
    lab.setObjectName("muted")
    lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lab.setWordWrap(True)
    lab.setContentsMargins(16, 24, 16, 24)
    return lab


class _Panel(QWidget):
    """A list view with an empty-state message."""

    def __init__(self, view: QWidget, empty_text: str, parent: QWidget | None = None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self._stack = QStackedWidget()
        self._stack.addWidget(_empty_label(empty_text))
        self._stack.addWidget(view)
        lay.addWidget(self._stack)

    def set_empty(self, empty: bool) -> None:
        self._stack.setCurrentIndex(0 if empty else 1)


class OutlinePanel(_Panel):
    navigate = pyqtSignal(int)  # page

    def __init__(self, parent: QWidget | None = None):
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setColumnCount(2)
        self.tree.setIndentation(14)
        self.tree.setUniformRowHeights(True)
        self.tree.itemActivated.connect(self._activated)
        self.tree.itemClicked.connect(self._activated)
        super().__init__(self.tree, "This document has no table of contents.", parent)
        self.set_empty(True)

    def set_outline(self, items: list[OutlineItem]) -> None:
        self.tree.clear()
        parents: list[QTreeWidgetItem | None] = [None]
        for it in items:
            level = max(1, it.level)
            del parents[level:]
            while len(parents) < level:
                parents.append(parents[-1])
            parent = parents[level - 1]
            node = QTreeWidgetItem([it.title, str(it.page + 1) if it.page >= 0 else ""])
            node.setData(0, ROLE, it.page)
            node.setTextAlignment(1, Qt.AlignmentFlag.AlignRight)
            node.setToolTip(0, it.title)
            if parent is None:
                self.tree.addTopLevelItem(node)
            else:
                parent.addChild(node)
            parents.append(node)
        self.tree.expandToDepth(0)
        header = self.tree.header()
        if header is not None:
            header.setStretchLastSection(False)
            header.setSectionResizeMode(0, header.ResizeMode.Stretch)
            header.setSectionResizeMode(1, header.ResizeMode.ResizeToContents)
        self.set_empty(not items)

    def mark_current(self, page: int) -> None:
        """Select the deepest outline entry starting at or before `page`."""
        best: QTreeWidgetItem | None = None
        best_page = -1
        stack = [self.tree.topLevelItem(i) for i in range(self.tree.topLevelItemCount())]
        while stack:
            node = stack.pop()
            if node is None:
                continue
            p = node.data(0, ROLE)
            if p is not None and best_page <= p <= page:
                best, best_page = node, p
            stack.extend(node.child(i) for i in range(node.childCount()))
        if best is not None and best is not self.tree.currentItem():
            self.tree.blockSignals(True)
            self.tree.setCurrentItem(best)
            self.tree.blockSignals(False)

    def _activated(self, item: QTreeWidgetItem, _col: int = 0) -> None:
        page = item.data(0, ROLE)
        if page is not None and page >= 0:
            self.navigate.emit(page)


class BookmarksPanel(_Panel):
    navigate = pyqtSignal(int)
    remove_requested = pyqtSignal(int)  # page
    note_changed = pyqtSignal(int, str)  # bookmark id, note

    def __init__(self, parent: QWidget | None = None):
        self.list = QListWidget()
        self.list.itemActivated.connect(self._activated)
        self.list.itemClicked.connect(self._activated)
        self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._menu)
        super().__init__(self.list, "No bookmarks yet.\nPress Ctrl+B to bookmark a page.", parent)
        self.set_empty(True)

    def set_bookmarks(self, rows: list[BookmarkRow]) -> None:
        self.list.clear()
        for b in rows:
            label = f"Page {b.page_no + 1}"
            if b.note:
                label += f" — {b.note}"
            item = QListWidgetItem(label)
            item.setData(ROLE, (b.id, b.page_no, b.note or ""))
            self.list.addItem(item)
        self.set_empty(not rows)

    def _activated(self, item: QListWidgetItem) -> None:
        self.navigate.emit(item.data(ROLE)[1])

    def _menu(self, pos) -> None:
        item = self.list.itemAt(pos)
        if item is None:
            return
        bid, page, note = item.data(ROLE)
        menu = QMenu(self)
        menu.addAction("Edit note…", lambda: self._edit(bid, note))
        menu.addAction("Remove bookmark", lambda: self.remove_requested.emit(page))
        menu.exec(self.list.mapToGlobal(pos))

    def _edit(self, bid: int, note: str) -> None:
        text, ok = QInputDialog.getText(self, "Bookmark note", "Note:", text=note)
        if ok:
            self.note_changed.emit(bid, text.strip())


class NotesPanel(_Panel):
    navigate = pyqtSignal(int, float)  # page, y in points
    edit_requested = pyqtSignal(int)  # highlight id
    remove_requested = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None):
        self.list = QListWidget()
        self.list.setWordWrap(True)
        self.list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.list.setSpacing(2)
        self.list.itemActivated.connect(self._activated)
        self.list.itemClicked.connect(self._activated)
        self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._menu)
        super().__init__(
            self.list, "No highlights yet.\nSelect text and right-click ▸ Highlight.", parent
        )
        self.set_empty(True)

    def set_highlights(self, rows: list[HighlightRow]) -> None:
        self.list.clear()
        for h in rows:
            text = " ".join(h.text.split())
            quote = text if len(text) <= 160 else text[:160] + "…"
            when = dt.datetime.fromtimestamp(h.created_at).strftime("%d %b %Y")
            label = f"p. {h.page_no + 1} · {when}\n“{quote}”"
            if h.note:
                label += f"\n✎ {h.note}"
            item = QListWidgetItem(label)
            y = h.rects[0][1] if h.rects else 0.0
            item.setData(ROLE, (h.id, h.page_no, y))
            item.setToolTip(h.text)
            self.list.addItem(item)
        self.set_empty(not rows)

    def _activated(self, item: QListWidgetItem) -> None:
        _hid, page, y = item.data(ROLE)
        self.navigate.emit(page, y)

    def _menu(self, pos) -> None:
        item = self.list.itemAt(pos)
        if item is None:
            return
        hid = item.data(ROLE)[0]
        menu = QMenu(self)
        menu.addAction("Edit note…", lambda: self.edit_requested.emit(hid))
        menu.addAction("Remove highlight", lambda: self.remove_requested.emit(hid))
        menu.exec(self.list.mapToGlobal(pos))
