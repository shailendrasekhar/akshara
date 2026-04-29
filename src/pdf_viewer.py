import fitz  # PyMuPDF
from PyQt6.QtWidgets import (
    QWidget, QScrollArea, QVBoxLayout, QApplication, QMenu, QSizePolicy,
)
from PyQt6.QtCore import Qt, QRect, QPoint, QRectF, pyqtSignal, QTimer, QSize
from PyQt6.QtGui import (
    QPainter, QImage, QPixmap, QColor, QPen, QBrush,
    QMouseEvent, QPaintEvent,
)
from typing import Optional, List
from dataclasses import dataclass


@dataclass
class TextSpan:
    text: str
    bbox: QRectF


# ---------- Single-page widget -----------------------------------------------

class PDFPageWidget(QWidget):
    """
    Renders one PDF page with text selection and TTS highlighting.
    Instances are pooled and repositioned by PDFViewerWidget — never
    created more than RENDER_RADIUS*2+1 at a time regardless of page count.
    """

    text_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.page_index: int = -1
        self._pixmap: Optional[QPixmap] = None
        self._text_spans: List[TextSpan] = []
        self._scale: float = 1.5
        self._full_text: str = ""
        self._span_char_ranges: list[tuple[int, int]] = []

        self._selection_start: Optional[QPoint] = None
        self._selection_end: Optional[QPoint] = None
        self._selected_spans: List[int] = []
        self._is_selecting = False
        self._show_selection = True

        self._tts_char_start: int = -1
        self._tts_char_end: int = -1
        self._tts_highlight_spans: List[int] = []

        self._selection_color = QColor(99, 102, 241, 80)
        self._tts_color = QColor(250, 204, 21, 150)

        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.IBeamCursor)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    # ---- content ----

    def assign(self, page_index: int, pixmap: QPixmap,
               text_spans: List[TextSpan], scale: float):
        self.page_index = page_index
        self._pixmap = pixmap
        self._text_spans = text_spans
        self._scale = scale
        self._build_text_map()
        self.clear_selection()
        self.clear_tts_highlight()
        self.setFixedSize(pixmap.size())
        self.update()

    def release(self):
        self.page_index = -1
        self._pixmap = None
        self._text_spans = []
        self._full_text = ""
        self._span_char_ranges = []
        self.clear_selection()
        self.clear_tts_highlight()
        self.hide()

    def is_assigned(self) -> bool:
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

        if self._tts_highlight_spans:
            painter.setBrush(QBrush(self._tts_color))
            painter.setPen(QPen(QColor(234, 179, 8), 2))
            for idx in self._tts_highlight_spans:
                if 0 <= idx < len(self._text_spans):
                    span = self._text_spans[idx]
                    rect = QRectF(
                        span.bbox.x() * self._scale, span.bbox.y() * self._scale,
                        span.bbox.width() * self._scale, span.bbox.height() * self._scale,
                    )
                    painter.drawRoundedRect(rect, 3, 3)

        if self._show_selection and self._selected_spans and not self._tts_highlight_spans:
            painter.setBrush(QBrush(self._selection_color))
            painter.setPen(Qt.PenStyle.NoPen)
            for idx in self._selected_spans:
                if 0 <= idx < len(self._text_spans):
                    span = self._text_spans[idx]
                    rect = QRectF(
                        span.bbox.x() * self._scale, span.bbox.y() * self._scale,
                        span.bbox.width() * self._scale, span.bbox.height() * self._scale,
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
                span.bbox.x() * self._scale, span.bbox.y() * self._scale,
                span.bbox.width() * self._scale, span.bbox.height() * self._scale,
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
                int(span.bbox.x() * self._scale), int(span.bbox.y() * self._scale),
                int(span.bbox.width() * self._scale), int(span.bbox.height() * self._scale),
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


# ---------- Virtual-scroll canvas --------------------------------------------

PAGE_GAP = 12        # px between pages
RENDER_RADIUS = 2    # render current ±N pages
POOL_SIZE = RENDER_RADIUS * 2 + 1


class _Canvas(QWidget):
    """
    A single tall widget whose height equals the sum of all page heights.
    It paints placeholder rectangles for unrendered pages and hosts a small
    pool of PDFPageWidget children positioned over the rendered ones.
    """

    text_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._page_tops: List[int] = []      # y-offset of each page top
        self._page_sizes: List[tuple[int, int]] = []  # (w, h) per page
        self._bg = QColor("#000000")

        # Fixed pool of page widgets — reused, never recreated per page
        self._pool: List[PDFPageWidget] = []
        for _ in range(POOL_SIZE):
            pw = PDFPageWidget(self)
            pw.text_selected.connect(self.text_selected)
            pw.hide()
            self._pool.append(pw)

        # page_index → pool slot (or -1 = not in pool)
        self._slot_for_page: dict[int, int] = {}

    def setup(self, page_tops: List[int], page_sizes: List[tuple[int, int]],
              bg: QColor, total_w: int, total_h: int):
        self._page_tops = page_tops
        self._page_sizes = page_sizes
        self._bg = bg
        self._slot_for_page.clear()
        for pw in self._pool:
            pw.release()
        self.setFixedSize(total_w, total_h)

    def set_bg(self, bg: QColor):
        self._bg = bg
        self.update()

    def page_top(self, page_index: int) -> int:
        if 0 <= page_index < len(self._page_tops):
            return self._page_tops[page_index]
        return 0

    def page_at_y(self, y: int) -> int:
        """Binary search: return the page index whose rect contains y."""
        lo, hi = 0, len(self._page_tops) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if self._page_tops[mid] <= y:
                lo = mid
            else:
                hi = mid - 1
        return lo

    # ---- pool management ----

    def assign_slot(self, page_index: int, pixmap: QPixmap,
                    text_spans: List[TextSpan], scale: float):
        if page_index in self._slot_for_page:
            slot = self._slot_for_page[page_index]
            pw = self._pool[slot]
            pw.assign(page_index, pixmap, text_spans, scale)
            pw.move(
                (self.width() - pixmap.width()) // 2,
                self._page_tops[page_index],
            )
            pw.show()
            return

        # Find a free slot (prefer one not in use, then evict the farthest)
        used = set(self._slot_for_page.values())
        free = [i for i in range(POOL_SIZE) if i not in used]
        if free:
            slot = free[0]
        else:
            # evict the pool slot whose page_index is farthest from current
            evict_page = max(self._slot_for_page,
                             key=lambda p: abs(p - page_index))
            slot = self._slot_for_page.pop(evict_page)
            self._pool[slot].release()

        self._slot_for_page[page_index] = slot
        pw = self._pool[slot]
        pw.assign(page_index, pixmap, text_spans, scale)
        pw.move(
            (self.width() - pixmap.width()) // 2,
            self._page_tops[page_index],
        )
        pw.show()

    def release_page(self, page_index: int):
        if page_index in self._slot_for_page:
            slot = self._slot_for_page.pop(page_index)
            self._pool[slot].release()

    def is_assigned(self, page_index: int) -> bool:
        return page_index in self._slot_for_page

    def widget_for_page(self, page_index: int) -> Optional[PDFPageWidget]:
        slot = self._slot_for_page.get(page_index)
        if slot is not None:
            return self._pool[slot]
        return None

    def all_assigned_pages(self) -> list[int]:
        return list(self._slot_for_page.keys())

    # ---- paint (placeholder rects only — rendered pages are child widgets) ----

    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), self._bg)
        # Draw placeholder outlines for pages not in pool
        border = QColor("#1a1a1a") if self._bg == QColor("#000000") else QColor("#e0e0dc")
        p.setPen(QPen(border, 1))
        for i, (w, h) in enumerate(self._page_sizes):
            if not self.is_assigned(i):
                x = (self.width() - w) // 2
                y = self._page_tops[i]
                p.fillRect(x, y, w, h, self._bg)
                p.drawRect(x, y, w, h)


# ---------- Viewer widget ----------------------------------------------------

class PDFViewerWidget(QWidget):
    """
    Continuous-scroll PDF viewer with O(1) memory regardless of page count.

    Uses a virtual-scroll canvas: total document height is represented by one
    tall QWidget; only RENDER_RADIUS*2+1 page pixmaps exist at any time in a
    fixed pool that is repositioned as the user scrolls.
    """

    text_selected = pyqtSignal(str)
    current_page_changed = pyqtSignal(int)   # 0-indexed

    def __init__(self, parent=None):
        super().__init__(parent)
        self._dark_mode = True
        self._doc: Optional[fitz.Document] = None
        self._zoom: float = 1.0
        self._page_count: int = 0
        self._current_page: int = 0
        self._current_read_position: int = 0

        self._scroll_timer = QTimer(self)
        self._scroll_timer.setSingleShot(True)
        self._scroll_timer.setInterval(80)
        self._scroll_timer.timeout.connect(self._on_scroll_settled)

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(False)   # we size the canvas ourselves
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.verticalScrollBar().valueChanged.connect(
            self._on_scroll_value_changed
        )

        self._canvas = _Canvas()
        self._canvas.text_selected.connect(self.text_selected)
        self.scroll_area.setWidget(self._canvas)
        layout.addWidget(self.scroll_area)
        self._update_background()

    # ---- public API ----

    def load_document(self, doc: fitz.Document, zoom: float, dark_mode: bool):
        self._doc = doc
        self._zoom = zoom
        self._dark_mode = dark_mode
        self._current_page = 0
        self._current_read_position = 0
        self._page_count = len(doc)
        self._build_layout()
        self.scroll_area.verticalScrollBar().setValue(0)
        self._on_scroll_settled()

    def set_zoom(self, zoom: float):
        if self._zoom == zoom or self._doc is None:
            return
        self._zoom = zoom
        self._build_layout()
        self._on_scroll_settled()

    def set_dark_mode(self, dark_mode: bool):
        self._dark_mode = dark_mode
        self._update_background()
        if self._doc is not None:
            # Release all pool slots so they re-render with new colours
            for pi in list(self._canvas.all_assigned_pages()):
                self._canvas.release_page(pi)
            self._on_scroll_settled()

    def go_to_page(self, page_index: int):
        if self._doc is None or not (0 <= page_index < self._page_count):
            return
        y = self._canvas.page_top(page_index) - PAGE_GAP
        self.scroll_area.verticalScrollBar().setValue(max(0, y))

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

    # ---- TTS / selection ----

    def highlight_text(self, text: str):
        assigned = self._canvas.all_assigned_pages()
        if not text:
            for pi in assigned:
                pw = self._canvas.widget_for_page(pi)
                if pw:
                    pw.show_selection()
                    pw.clear_tts_highlight()
            self._current_read_position = 0
            return

        pages_to_search = (
            [p for p in assigned if p >= self._current_page] +
            [p for p in assigned if p < self._current_page]
        )
        for pi in pages_to_search:
            pw = self._canvas.widget_for_page(pi)
            if pw is None or not pw.is_assigned():
                continue
            pw.hide_selection()
            start_from = self._current_read_position if pi == self._current_page else 0
            start, end = pw.find_text_position(text, start_from)
            if start >= 0:
                for other_pi in assigned:
                    other_pw = self._canvas.widget_for_page(other_pi)
                    if other_pw and other_pw is not pw:
                        other_pw.clear_tts_highlight()
                pw.set_tts_highlight_by_position(start, end)
                self._current_read_position = end
                if pi != self._current_page:
                    self.go_to_page(pi)
                return
        self._current_read_position = 0

    def reset_read_position(self):
        self._current_read_position = 0

    def get_selected_text(self) -> str:
        for pi in self._canvas.all_assigned_pages():
            pw = self._canvas.widget_for_page(pi)
            if pw:
                t = pw.get_selected_text()
                if t:
                    return t
        return ""

    def clear_selection(self):
        for pi in self._canvas.all_assigned_pages():
            pw = self._canvas.widget_for_page(pi)
            if pw:
                pw.clear_selection()

    def clear(self):
        self._doc = None
        self._page_count = 0
        self._current_read_position = 0

    # ---- internal ----

    def _build_layout(self):
        """Compute page positions and resize the canvas. O(n) but only on load/zoom."""
        if self._doc is None:
            return
        scale = self._zoom * 1.5
        page_tops: List[int] = []
        page_sizes: List[tuple[int, int]] = []
        y = PAGE_GAP
        max_w = 0
        for i in range(self._page_count):
            try:
                rect = self._doc[i].rect
                pw = int(rect.width * scale)
                ph = int(rect.height * scale)
            except Exception:
                pw, ph = 600, 800
            page_tops.append(y)
            page_sizes.append((pw, ph))
            max_w = max(max_w, pw)
            y += ph + PAGE_GAP

        bg = QColor("#000000" if self._dark_mode else "#ffffff")
        total_w = max_w + 40   # horizontal padding
        total_h = y
        self._canvas.setup(page_tops, page_sizes, bg, total_w, total_h)

        # Release all pool slots — sizes may have changed
        for pi in list(self._canvas.all_assigned_pages()):
            self._canvas.release_page(pi)

    def _update_background(self):
        bg = "#000000" if self._dark_mode else "#ffffff"
        self.scroll_area.setStyleSheet(
            f"QScrollArea {{ background-color:{bg}; border:none; }}"
        )
        self._canvas.set_bg(QColor(bg))

    def _on_scroll_value_changed(self, _):
        self._scroll_timer.start()

    def _on_scroll_settled(self):
        if self._doc is None or self._page_count == 0:
            return

        scroll_y = self.scroll_area.verticalScrollBar().value()
        viewport_h = self.scroll_area.viewport().height()
        viewport_mid = scroll_y + viewport_h // 2

        visible = self._canvas.page_at_y(max(0, viewport_mid))
        if visible != self._current_page:
            self._current_page = visible
            self.current_page_changed.emit(visible)

        lo = max(0, visible - RENDER_RADIUS)
        hi = min(self._page_count - 1, visible + RENDER_RADIUS)

        # Release pages outside the window
        for pi in list(self._canvas.all_assigned_pages()):
            if not (lo <= pi <= hi):
                self._canvas.release_page(pi)

        # Render pages inside the window
        for pi in range(lo, hi + 1):
            if not self._canvas.is_assigned(pi):
                self._render_page(pi)

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
            self._canvas.assign_slot(page_index, pixmap, text_spans, scale)
        except Exception:
            pass

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
                        spans.append(TextSpan(
                            text=text,
                            bbox=QRectF(bbox[0], bbox[1],
                                        bbox[2] - bbox[0], bbox[3] - bbox[1]),
                        ))
        except Exception:
            pass
        return spans
