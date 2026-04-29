"""
Library panel — left dock showing all documents the user has ever opened.

Signals:
    open_document(str)  — file path the user wants to open
"""

from __future__ import annotations

import os
from typing import Callable, Optional

from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QColor, QPainter, QFont, QPen
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QSizePolicy,
)

from .db import Store, DocumentRow


# ---------- Single document card ---------------------------------------------

class _DocCard(QWidget):
    clicked = pyqtSignal(str)   # file path

    def __init__(self, doc: DocumentRow, dark: bool, parent=None):
        super().__init__(parent)
        self._path = doc.path
        self._dark = dark
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("docCard")
        self._build(doc)
        self._apply_theme(dark)

    def _build(self, doc: DocumentRow):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)

        # Title row
        title_row = QHBoxLayout()
        title_row.setSpacing(8)

        self._title = QLabel(doc.title or os.path.basename(doc.path))
        self._title.setWordWrap(True)
        self._title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        title_row.addWidget(self._title, 1)

        layout.addLayout(title_row)

        # Author
        author_text = doc.author or ""
        self._author = QLabel(author_text)
        layout.addWidget(self._author)

        # Progress bar row
        prog_row = QHBoxLayout()
        prog_row.setSpacing(8)

        self._progress_bar = _ProgressBar(doc.last_page, doc.pages, dark=self._dark)
        prog_row.addWidget(self._progress_bar, 1)

        pct = round(doc.last_page / doc.pages * 100) if doc.pages > 0 else 0
        self._pct_label = QLabel(f"{pct}%")
        prog_row.addWidget(self._pct_label)

        layout.addLayout(prog_row)

        # Page count
        self._pages_label = QLabel(f"p. {doc.last_page} / {doc.pages}")
        layout.addWidget(self._pages_label)

    def _apply_theme(self, dark: bool):
        self._dark = dark
        bg       = "#0d0d0d" if dark else "#f7f7f6"
        bg_hover = "#1a1a1a" if dark else "#eeeeec"
        border   = "#222222" if dark else "#e0e0dc"
        ink      = "#ffffff" if dark else "#0a0a0a"
        muted    = "#666666" if dark else "#999999"

        self.setStyleSheet(f"""
            QWidget#docCard {{
                background:{bg};
                border:1px solid {border};
                border-radius:6px;
            }}
            QWidget#docCard:hover {{
                background:{bg_hover};
                border-color:{'#444' if dark else '#bbb'};
            }}
        """)
        self._title.setStyleSheet(
            f"font-family:Georgia,serif;font-size:14px;font-weight:600;"
            f"color:{ink};background:transparent;border:none;"
        )
        self._author.setStyleSheet(
            f"font-size:12px;letter-spacing:0.5px;color:{muted};"
            f"background:transparent;border:none;"
        )
        self._pct_label.setStyleSheet(
            f"font-family:monospace;font-size:12px;color:{muted};"
            f"background:transparent;border:none;"
        )
        self._pages_label.setStyleSheet(
            f"font-family:monospace;font-size:12px;color:{muted};"
            f"background:transparent;border:none;"
        )
        self._progress_bar.set_dark(dark)

    def set_dark_mode(self, dark: bool):
        self._apply_theme(dark)

    def update_progress(self, last_page: int):
        """Update the progress bar and labels without rebuilding the card."""
        self._progress_bar._current = last_page
        self._progress_bar.update()
        pct = round(last_page / self._progress_bar._total * 100)
        self._pct_label.setText(f"{pct}%")
        self._pages_label.setText(f"p. {last_page} / {self._progress_bar._total}")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if os.path.isfile(self._path):
                self.clicked.emit(self._path)
        super().mousePressEvent(event)


class _ProgressBar(QWidget):
    def __init__(self, current: int, total: int, dark: bool, parent=None):
        super().__init__(parent)
        self._current = current
        self._total = max(1, total)
        self._dark = dark
        self.setFixedHeight(4)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_dark(self, dark: bool):
        self._dark = dark
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        track = QColor("#2a2a2a") if self._dark else QColor("#e0e0dc")
        fill  = QColor("#d8a85a")   # warm amber accent — same as ring
        p.fillRect(self.rect(), track)
        w = int(self.width() * min(1.0, self._current / self._total))
        if w > 0:
            r = self.rect()
            r.setWidth(w)
            p.fillRect(r, fill)


# ---------- Panel ------------------------------------------------------------

class LibraryPanel(QWidget):
    open_document = pyqtSignal(str)

    def __init__(self, store: Store, dark: bool = True, parent=None):
        super().__init__(parent)
        self.store = store
        self._dark = dark
        self._cards: list[_DocCard] = []
        self._build()
        self.refresh()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Scroll area
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._cards_widget = QWidget()
        self._cards_widget.setObjectName("libCardsWidget")
        self._cards_layout = QVBoxLayout(self._cards_widget)
        self._cards_layout.setContentsMargins(10, 10, 10, 10)
        self._cards_layout.setSpacing(8)
        self._cards_layout.addStretch(1)

        self._scroll.setWidget(self._cards_widget)
        outer.addWidget(self._scroll, 1)

        self._apply_theme()

    def _apply_theme(self):
        dark = self._dark
        bg   = "#000000" if dark else "#ffffff"
        ink  = "#ffffff" if dark else "#0a0a0a"

        self.setStyleSheet(f"""
            QWidget {{ background:{bg}; color:{ink}; }}
            QWidget#libCardsWidget {{ background:{bg}; }}
            QScrollBar:vertical {{
                background:transparent;width:6px;margin:0;
            }}
            QScrollBar::handle:vertical {{
                background:{'#2a2a2a' if dark else '#d0d0cc'};
                border-radius:3px;min-height:30px;
            }}
            QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical,
            QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical {{
                background:transparent;height:0;
            }}
        """)

    def set_dark_mode(self, dark: bool):
        self._dark = dark
        self._apply_theme()
        for card in self._cards:
            card.set_dark_mode(dark)

    def update_document_progress(self, file_path: str, last_page: int):
        """Update only the matching card's progress bar — no DB query needed."""
        for card in self._cards:
            if card._path == file_path:
                card.update_progress(last_page)
                return

    def refresh(self):
        # clear old cards
        for card in self._cards:
            self._cards_layout.removeWidget(card)
            card.deleteLater()
        self._cards.clear()

        docs = self.store.list_documents()
        stretch_item = self._cards_layout.takeAt(self._cards_layout.count() - 1)

        for doc in docs:
            card = _DocCard(doc, self._dark)
            card.clicked.connect(self.open_document)
            self._cards_layout.addWidget(card)
            self._cards.append(card)

        self._cards_layout.addStretch(1)

        if not docs:
            empty = QLabel("No documents yet.\nOpen a PDF to get started.")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet("color:#555;font-size:11px;padding:24px;background:transparent;")
            self._cards_layout.insertWidget(self._cards_layout.count() - 1, empty)
