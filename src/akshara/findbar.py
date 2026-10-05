"""Find bar (Ctrl+F) and the incremental document search behind it."""

from __future__ import annotations

import bisect

from PyQt6.QtCore import QObject, Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import QApplication, QHBoxLayout, QLabel, QLineEdit, QToolButton, QWidget

from .pdf_handler import PDFDocument

PAGES_PER_TICK = 15

Match = tuple[int, int, int]  # page, start, end


class DocumentSearch(QObject):
    """Scans the document a few pages per event-loop turn so the UI never blocks."""

    results_changed = pyqtSignal(object, int, bool)  # {page: [(s, e)]}, total, finished
    current_changed = pyqtSignal(object)  # Match | None

    def __init__(self, doc: PDFDocument, parent: QObject | None = None):
        super().__init__(parent)
        self._doc = doc
        self._needle = ""
        self._case = False
        self._next_page = 0
        self._results: dict[int, list[tuple[int, int]]] = {}
        self._flat: list[Match] = []
        self._index = -1
        self._timer = QTimer(self)
        self._timer.setInterval(0)
        self._timer.timeout.connect(self._step)

    @property
    def needle(self) -> str:
        return self._needle

    @property
    def total(self) -> int:
        return len(self._flat)

    @property
    def index(self) -> int:
        return self._index

    @property
    def finished(self) -> bool:
        return not self._timer.isActive()

    def start(self, needle: str, case_sensitive: bool = False) -> None:
        self._timer.stop()
        self._needle = " ".join(needle.split())
        self._case = case_sensitive
        self._next_page = 0
        self._results = {}
        self._flat = []
        self._index = -1
        if not self._needle or not self._doc.is_loaded:
            self.results_changed.emit({}, 0, True)
            self.current_changed.emit(None)
            return
        self._timer.start()

    def clear(self) -> None:
        self.start("")

    def _step(self) -> None:
        end = min(self._doc.page_count, self._next_page + PAGES_PER_TICK)
        for page in range(self._next_page, end):
            hits = self._doc.page_text(page).find_all(self._needle, self._case)
            if hits:
                self._results[page] = hits
                self._flat.extend((page, s, e) for s, e in hits)
        self._next_page = end
        done = end >= self._doc.page_count
        if done:
            self._timer.stop()
        self.results_changed.emit(dict(self._results), len(self._flat), done)

    def run_to_completion(self) -> None:
        """Finish the scan synchronously (used by tests and 'next' before results)."""
        while self._timer.isActive():
            self._step()

    def next(self, from_page: int = 0) -> Match | None:
        return self._move(+1, from_page)

    def previous(self, from_page: int = 0) -> Match | None:
        return self._move(-1, from_page)

    def _move(self, direction: int, from_page: int) -> Match | None:
        if not self._flat and not self.finished:
            self.run_to_completion()
        if not self._flat:
            self.current_changed.emit(None)
            return None
        if self._index < 0:
            # Start from the reader's current page rather than page 1.
            pos = bisect.bisect_left(self._flat, (from_page, -1, -1))
            self._index = pos if direction > 0 else pos - 1
        else:
            self._index += direction
        self._index %= len(self._flat)
        match = self._flat[self._index]
        self.current_changed.emit(match)
        return match


class FindBar(QWidget):
    search_changed = pyqtSignal(str, bool)  # text, case sensitive
    next_requested = pyqtSignal()
    previous_requested = pyqtSignal()
    closed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("findBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 6, 12, 6)
        lay.setSpacing(6)

        self.edit = QLineEdit()
        self.edit.setPlaceholderText("Find in document…")
        self.edit.setClearButtonEnabled(True)
        self.edit.setMinimumWidth(150)
        self.edit.setMaximumWidth(320)
        self.edit.returnPressed.connect(self._on_return)
        self.edit.textChanged.connect(lambda _: self._debounce.start())
        lay.addWidget(self.edit)

        self.case_btn = QToolButton()
        self.case_btn.setText("Aa")
        self.case_btn.setCheckable(True)
        self.case_btn.setObjectName("flatButton")
        self.case_btn.setToolTip("Match case")
        self.case_btn.toggled.connect(lambda _: self._emit_search())
        lay.addWidget(self.case_btn)

        self.prev_btn = QToolButton()
        self.prev_btn.setText("↑")
        self.prev_btn.setToolTip("Previous match  Shift+Enter")
        self.prev_btn.clicked.connect(self.previous_requested)
        lay.addWidget(self.prev_btn)

        self.next_btn = QToolButton()
        self.next_btn.setText("↓")
        self.next_btn.setToolTip("Next match  Enter")
        self.next_btn.clicked.connect(self.next_requested)
        lay.addWidget(self.next_btn)

        self.status = QLabel("")
        self.status.setObjectName("findStatus")
        self.status.setMinimumWidth(110)
        lay.addWidget(self.status)
        lay.addStretch(1)

        close = QToolButton()
        close.setText("✕")
        close.setObjectName("flatButton")
        close.setToolTip("Close  Esc")
        close.clicked.connect(self.close_bar)
        lay.addWidget(close)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(220)
        self._debounce.timeout.connect(self._emit_search)

    def open_bar(self, text: str | None = None) -> None:
        self.show()
        if text:
            self.edit.setText(text)
            self._emit_search()
        self.edit.setFocus()
        self.edit.selectAll()

    def close_bar(self) -> None:
        self.hide()
        self.closed.emit()

    def set_status(self, index: int, total: int, finished: bool) -> None:
        if not self.edit.text().strip():
            self.status.setText("")
        elif total == 0:
            self.status.setText("No matches" if finished else "Searching…")
        else:
            pos = f"{index + 1} of " if index >= 0 else ""
            more = "" if finished else "+"
            self.status.setText(f"{pos}{total}{more} matches")

    def _emit_search(self) -> None:
        self._debounce.stop()
        self.search_changed.emit(self.edit.text(), self.case_btn.isChecked())

    def _on_return(self) -> None:
        if self._debounce.isActive():
            self._emit_search()
        if QApplication.keyboardModifiers() & Qt.KeyboardModifier.ShiftModifier:
            self.previous_requested.emit()
        else:
            self.next_requested.emit()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.close_bar()
        else:
            super().keyPressEvent(event)
