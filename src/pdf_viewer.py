import fitz  # PyMuPDF
from PyQt6.QtWidgets import (
    QWidget, QScrollArea, QVBoxLayout, QApplication, QMenu, QSizePolicy,
)
from PyQt6.QtCore import Qt, QRect, QPoint, QRectF, pyqtSignal, QTimer
from PyQt6.QtGui import (
    QPainter, QImage, QPixmap, QColor, QPen, QBrush,
    QMouseEvent, QPaintEvent,
)
from typing import Optional, List
from dataclasses import dataclass


@dataclass
class TextSpan:
    """Represents a text span with its bounding box."""
    text: str
    bbox: QRectF


# ---------- Single-page widget -----------------------------------------------

class PDFPageWidget(QWidget):
    """
    Displays one PDF page with text selection and TTS highlighting.
    When `_pixmap` is None the widget paints a blank placeholder (so the
    scroll area knows the correct total height even before rendering).
    """

    text_selected = pyqtSignal(str)

    def __init__(self, page_index: int, placeholder_height: int, parent=None):
        super().__init__(parent)
        self.page_index = page_index
        self._pixmap: Optional[QPixmap] = None
        self._text_spans: List[TextSpan] = []
        self._scale = 1.5
        self._full_text: str = ""
        self._span_char_ranges: list[tuple[int, int]] = []

        # Selection
        self._selection_start: Optional[QPoint] = None
        self._selection_end: Optional[QPoint] = None
        self._selected_spans: List[int] = []
        self._is_selecting = False
        self._show_selection = True

        # TTS highlight
        self._tts_char_start: int = -1
        self._tts_char_end: int = -1
        self._tts_highlight_spans: List[int] = []

        self._selection_color = QColor(99, 102, 241, 80)
        self._tts_color = QColor(250, 204, 21, 150)

        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.IBeamCursor)
        # Start with placeholder height; updated once rendered
        self.setFixedHeight(placeholder_height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    # ---- content ----

    def set_page(self, pixmap: QPixmap, text_spans: List[TextSpan], scale: float):
        self._pixmap = pixmap
        self._text_spans = text_spans
        self._scale = scale
        self._build_text_map()
        self.clear_selection()
        self.clear_tts_highlight()
        if pixmap:
            self.setFixedSize(pixmap.size())
        self.update()

    def unload(self):
        """Release rendered pixmap but keep the widget sized (placeholder)."""
        if self._pixmap is not None:
            h = self._pixmap.height()
            self._pixmap = None
            self._text_spans = []
            self._full_text = ""
            self._span_char_ranges = []
            self.clear_selection()
            self.clear_tts_highlight()
            self.setFixedHeight(h)   # keep height so scroll position is stable
            self.update()

    def is_rendered(self) -> bool:
        return self._pixmap is not None

    # ---- text map ----

    def _build_text_map(self):
        parts = []
        self._span_char_ranges = []
        char_pos = 0
        for span in self._text_spans:
            start = char_pos
            end = char_pos + len(span.text)
            self._span_char_ranges.append((start, end))
            parts.append(span.text)
            char_pos = end + 1
        self._full_text = " ".join(parts)

    # ---- selection / highlight ----

    def clear_selection(self):
        self._selection_start = None
        self._selection_end = None
        self._selected_spans = []
        self._is_selecting = False
        self._show_selection = True
        self.update()

    def clear_tts_highlight(self):
        self._tts_char_start = -1
        self._tts_char_end = -1
        self._tts_highlight_spans = []
        self.update()

    def hide_selection(self):
        self._show_selection = False
        self.update()

    def show_selection(self):
        self._show_selection = True
        self.update()

    def set_tts_highlight_by_position(self, char_start: int, char_end: int):
        self._tts_char_start = char_start
        self._tts_char_end = char_end
        self._tts_highlight_spans = []
        if char_start < 0 or char_end < 0:
            self.update()
            return
        for i, (s, e) in enumerate(self._span_char_ranges):
            if s < char_end and e > char_start:
                self._tts_highlight_spans.append(i)
        self.update()

    def find_text_position(self, search_text: str, start_from: int = 0) -> tuple[int, int]:
        search_clean = " ".join(search_text.lower().split())
        full_clean   = " ".join(self._full_text.lower().split())
        pos = full_clean.find(search_clean, start_from)
        if pos >= 0:
            return pos, pos + len(search_clean)
        return -1, -1

    def get_selected_text(self) -> str:
        if not self._selected_spans:
            return ""
        return " ".join(self._text_spans[i].text for i in sorted(self._selected_spans))

    # ---- paint ----

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        if self._pixmap:
            painter.drawPixmap(0, 0, self._pixmap)
        else:
            # blank placeholder — background already set by parent stylesheet
            pass

        if self._tts_highlight_spans:
            painter.setBrush(QBrush(self._tts_color))
            painter.setPen(QPen(QColor(234, 179, 8), 2))
            for idx in self._tts_highlight_spans:
                if 0 <= idx < len(self._text_spans):
                    span = self._text_spans[idx]
                    rect = QRectF(
                        span.bbox.x() * self._scale,
                        span.bbox.y() * self._scale,
                        span.bbox.width() * self._scale,
                        span.bbox.height() * self._scale,
                    )
                    painter.drawRoundedRect(rect, 3, 3)

        if self._show_selection and self._selected_spans and not self._tts_highlight_spans:
            painter.setBrush(QBrush(self._selection_color))
            painter.setPen(Qt.PenStyle.NoPen)
            for idx in self._selected_spans:
                if 0 <= idx < len(self._text_spans):
                    span = self._text_spans[idx]
                    rect = QRectF(
                        span.bbox.x() * self._scale,
                        span.bbox.y() * self._scale,
                        span.bbox.width() * self._scale,
                        span.bbox.height() * self._scale,
                    )
                    painter.drawRoundedRect(rect, 2, 2)

        if self._is_selecting and self._selection_start and self._selection_end:
            painter.setBrush(QBrush(QColor(99, 102, 241, 30)))
            painter.setPen(QPen(QColor(99, 102, 241), 1, Qt.PenStyle.DashLine))
            rect = QRect(self._selection_start, self._selection_end).normalized()
            painter.drawRect(rect)

    # ---- mouse ----

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_selecting = True
            self._selection_start = event.pos()
            self._selection_end = event.pos()
            self._selected_spans = []
            self._show_selection = True
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._is_selecting:
            self._selection_end = event.pos()
            self._update_selection()
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and self._is_selecting:
            self._is_selecting = False
            self._selection_end = event.pos()
            self._update_selection()
            selected = self.get_selected_text()
            if selected:
                self.text_selected.emit(selected)
            self.update()

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        pos = event.pos()
        for i, span in enumerate(self._text_spans):
            scaled = QRectF(
                span.bbox.x() * self._scale,
                span.bbox.y() * self._scale,
                span.bbox.width() * self._scale,
                span.bbox.height() * self._scale,
            )
            if scaled.contains(pos.toPointF()):
                self._selected_spans = [i]
                self._show_selection = True
                self.text_selected.emit(span.text)
                self.update()
                break

    def _update_selection(self):
        if not self._selection_start or not self._selection_end:
            return
        sel_rect = QRect(self._selection_start, self._selection_end).normalized()
        self._selected_spans = []
        for i, span in enumerate(self._text_spans):
            span_rect = QRect(
                int(span.bbox.x() * self._scale),
                int(span.bbox.y() * self._scale),
                int(span.bbox.width() * self._scale),
                int(span.bbox.height() * self._scale),
            )
            if sel_rect.intersects(span_rect):
                self._selected_spans.append(i)

    def contextMenuEvent(self, event):
        selected = self.get_selected_text()
        if selected:
            menu = QMenu(self)
            copy_action = menu.addAction("📋 Copy")
            copy_action.triggered.connect(lambda: QApplication.clipboard().setText(selected))
            menu.exec(event.globalPos())


# ---------- Continuous-scroll container --------------------------------------

PAGE_GAP = 12   # pixels between pages


class PDFViewerWidget(QWidget):
    """
    Continuous-scroll PDF viewer.

    All pages are represented as PDFPageWidget instances stacked vertically.
    Only the pages within RENDER_RADIUS pages of the visible viewport are
    actually rendered; the rest are kept as sized placeholders.

    Public API is backward-compatible with the old single-page viewer so
    main_window.py needs minimal changes.
    """

    text_selected = pyqtSignal(str)
    # Emitted when the topmost visible page changes (0-indexed)
    current_page_changed = pyqtSignal(int)

    RENDER_RADIUS = 2   # render current ±2 pages

    def __init__(self, parent=None):
        super().__init__(parent)
        self._dark_mode = True
        self._doc: Optional[fitz.Document] = None
        self._zoom: float = 1.0
        self._page_widgets: List[PDFPageWidget] = []
        self._current_page: int = 0
        self._current_read_position = 0

        # debounce scroll events so we don't render on every pixel
        self._scroll_timer = QTimer(self)
        self._scroll_timer.setSingleShot(True)
        self._scroll_timer.setInterval(80)
        self._scroll_timer.timeout.connect(self._on_scroll_settled)

        self._setup_ui()

    # ---- setup ----

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.scroll_area.verticalScrollBar().valueChanged.connect(
            self._on_scroll_value_changed
        )
        self._update_background()

        # Container that holds all page widgets
        self._container = QWidget()
        self._container.setObjectName("pdfContainer")
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setContentsMargins(0, PAGE_GAP, 0, PAGE_GAP)
        self._container_layout.setSpacing(PAGE_GAP)
        self._container_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self.scroll_area.setWidget(self._container)
        layout.addWidget(self.scroll_area)

    # ---- public API (backward-compatible) ----

    def load_document(self, doc: fitz.Document, zoom: float, dark_mode: bool):
        """
        Called by main_window after a PDF is opened. Builds one placeholder
        widget per page and renders the first window.
        """
        self._doc = doc
        self._zoom = zoom
        self._dark_mode = dark_mode
        self._current_page = 0
        self._current_read_position = 0
        self._rebuild_pages()

    def set_zoom(self, zoom: float):
        """Update zoom and re-render all currently visible pages."""
        if self._zoom == zoom or self._doc is None:
            return
        self._zoom = zoom
        # Unload everything; widths will update on next render pass
        for pw in self._page_widgets:
            pw.unload()
        self._on_scroll_settled()

    def set_dark_mode(self, dark_mode: bool):
        self._dark_mode = dark_mode
        self._update_background()
        if self._doc is not None:
            for pw in self._page_widgets:
                pw.unload()
            self._on_scroll_settled()

    def go_to_page(self, page_index: int):
        """Scroll so that the top of page_index is visible."""
        if not self._page_widgets or page_index < 0 or page_index >= len(self._page_widgets):
            return
        pw = self._page_widgets[page_index]
        # mapTo gives position relative to scroll_area viewport
        pos = pw.mapTo(self._container, QPoint(0, 0))
        self.scroll_area.verticalScrollBar().setValue(pos.y() - PAGE_GAP)

    def get_page_size(self) -> tuple[float, float]:
        if self._doc is None:
            return 0.0, 0.0
        try:
            page = self._doc[0]
            return page.rect.width, page.rect.height
        except Exception:
            return 0.0, 0.0

    @property
    def current_page(self) -> int:
        return self._current_page

    # --- TTS / selection (per-page, forwarded to current page widget) ---

    def highlight_text(self, text: str):
        if not text:
            for pw in self._page_widgets:
                pw.show_selection()
                pw.clear_tts_highlight()
            self._current_read_position = 0
            return

        # Search the current page first, then pages after it
        pages_to_search = list(range(self._current_page, len(self._page_widgets))) + \
                          list(range(0, self._current_page))
        for pi in pages_to_search:
            pw = self._page_widgets[pi]
            if not pw.is_rendered():
                continue
            pw.hide_selection()
            start_from = self._current_read_position if pi == self._current_page else 0
            start, end = pw.find_text_position(text, start_from)
            if start >= 0:
                # clear other pages
                for other in self._page_widgets:
                    if other is not pw:
                        other.clear_tts_highlight()
                pw.set_tts_highlight_by_position(start, end)
                self._current_read_position = end
                # scroll to make the highlight visible
                if pi != self._current_page:
                    self.go_to_page(pi)
                return
        # not found anywhere
        self._current_read_position = 0

    def reset_read_position(self):
        self._current_read_position = 0

    def get_selected_text(self) -> str:
        for pw in self._page_widgets:
            t = pw.get_selected_text()
            if t:
                return t
        return ""

    def clear_selection(self):
        for pw in self._page_widgets:
            pw.clear_selection()

    def clear(self):
        self._doc = None
        self._current_read_position = 0
        self._clear_page_widgets()

    # ---- internal ----

    def _rebuild_pages(self):
        self._clear_page_widgets()
        if self._doc is None:
            return
        scale = self._zoom * 1.5
        for i in range(len(self._doc)):
            try:
                page = self._doc[i]
                ph = int(page.rect.height * scale)
                pw = int(page.rect.width * scale)
            except Exception:
                ph, pw = 800, 600
            w = PDFPageWidget(i, ph)
            w.setFixedWidth(pw)
            w.text_selected.connect(self._on_text_selected)
            self._page_widgets.append(w)
            self._container_layout.addWidget(w, alignment=Qt.AlignmentFlag.AlignHCenter)

        self._on_scroll_settled()

    def _clear_page_widgets(self):
        for pw in self._page_widgets:
            self._container_layout.removeWidget(pw)
            pw.deleteLater()
        self._page_widgets.clear()

    def _update_background(self):
        bg = "#000000" if self._dark_mode else "#ffffff"
        self.scroll_area.setStyleSheet(
            f"QScrollArea {{ background-color:{bg}; border:none; }}"
        )
        if hasattr(self, "_container"):
            self._container.setStyleSheet(f"background-color:{bg};")

    def _on_scroll_value_changed(self, _value: int):
        self._scroll_timer.start()

    def _on_scroll_settled(self):
        """Render pages near viewport, unload distant ones, update current page."""
        if not self._page_widgets or self._doc is None:
            return

        visible_page = self._visible_page_index()
        if visible_page != self._current_page:
            self._current_page = visible_page
            self.current_page_changed.emit(visible_page)

        lo = max(0, visible_page - self.RENDER_RADIUS)
        hi = min(len(self._page_widgets) - 1, visible_page + self.RENDER_RADIUS)

        for i, pw in enumerate(self._page_widgets):
            if lo <= i <= hi:
                if not pw.is_rendered():
                    self._render_page(i)
            else:
                pw.unload()

    def _visible_page_index(self) -> int:
        """Return the index of the page whose top edge is closest to the viewport top."""
        vbar = self.scroll_area.verticalScrollBar()
        scroll_y = vbar.value()
        viewport_h = self.scroll_area.viewport().height()
        viewport_mid = scroll_y + viewport_h // 2

        best, best_dist = 0, float("inf")
        for i, pw in enumerate(self._page_widgets):
            pos_y = pw.mapTo(self._container, QPoint(0, 0)).y()
            centre = pos_y + pw.height() // 2
            dist = abs(centre - viewport_mid)
            if dist < best_dist:
                best, best_dist = i, dist
        return best

    def _render_page(self, page_index: int):
        if self._doc is None:
            return
        try:
            page = self._doc[page_index]
            scale = self._zoom * 1.5
            mat = fitz.Matrix(scale, scale)
            pix = page.get_pixmap(matrix=mat, alpha=False)

            if self._dark_mode:
                pix.invert_irect()

            img = QImage(
                pix.samples, pix.width, pix.height, pix.stride,
                QImage.Format.Format_RGB888,
            )
            pixmap = QPixmap.fromImage(img.copy())
            text_spans = self._extract_text_spans(page)
            self._page_widgets[page_index].set_page(pixmap, text_spans, scale)
        except Exception as e:
            pass   # leave as placeholder; will retry on next scroll settle

    def _extract_text_spans(self, page: fitz.Page) -> List[TextSpan]:
        spans = []
        try:
            for block in page.get_text("dict")["blocks"]:
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = span.get("text", "").strip()
                        if not text:
                            continue
                        bbox = span.get("bbox", [0, 0, 0, 0])
                        rect = QRectF(
                            bbox[0], bbox[1],
                            bbox[2] - bbox[0], bbox[3] - bbox[1],
                        )
                        spans.append(TextSpan(text=text, bbox=rect))
        except Exception:
            pass
        return spans

    def _on_text_selected(self, text: str):
        self.text_selected.emit(text)
