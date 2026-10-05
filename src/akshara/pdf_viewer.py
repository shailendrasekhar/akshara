"""
Continuous-scroll PDF viewer.

A single QAbstractScrollArea paints every visible page straight onto its
viewport (no per-page child widgets). Pages are rasterised lazily, one per
event-loop turn, visible pages first; rendered images live in an LRU cache so
scrolling back is free. While a re-render at a new zoom is pending, the last
image of that page is drawn scaled so zooming feels immediate.

Overlays drawn on top of the page image, in PDF-point coordinates mapped
through the page's scale factor:
    user highlights → search hits → selection → read-aloud sentence
"""

from __future__ import annotations

import bisect
from collections.abc import Callable

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QContextMenuEvent,
    QDesktopServices,
    QGuiApplication,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QPolygonF,
    QResizeEvent,
    QWheelEvent,
)
from PyQt6.QtWidgets import QAbstractScrollArea, QMenu, QWidget

from .db import HighlightRow
from .pdf_handler import Link, PDFDocument
from .render import BASE_SCALE, PageColors, RenderCache, render_page
from .textmap import PageText
from .ui.theme import DARK, Palette, qcolor

PAGE_GAP = 14  # px between pages
MARGIN = 24  # px either side of the widest page
PREFETCH = 1  # extra pages rendered above/below the viewport
ZOOM_MIN, ZOOM_MAX = 0.25, 5.0
ZOOM_STEPS = [0.25, 0.33, 0.5, 0.67, 0.75, 0.9, 1.0, 1.1, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0, 4.0, 5.0]
DRAG_THRESHOLD = 4

Selection = tuple[int, int, int]  # page, anchor word, focus word


class PDFViewerWidget(QAbstractScrollArea):
    current_page_changed = pyqtSignal(int)  # 0-based
    zoom_changed = pyqtSignal(float)
    selection_changed = pyqtSignal(str)

    # Context-menu requests, handled by the main window.
    read_from_requested = pyqtSignal(int, int)  # page, char offset
    read_range_requested = pyqtSignal(int, int, int)  # page, start, end
    highlight_requested = pyqtSignal(int, int, int, bool)  # page, start, end, with note
    highlight_edit_requested = pyqtSignal(int)  # highlight id
    highlight_remove_requested = pyqtSignal(int)
    search_requested = pyqtSignal(str)
    bookmark_toggle_requested = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFrameShape(QAbstractScrollArea.Shape.NoFrame)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.viewport().setMouseTracking(True)
        self.horizontalScrollBar().setSingleStep(24)
        self.verticalScrollBar().setSingleStep(36)
        self.verticalScrollBar().valueChanged.connect(self._on_scrolled)
        self.horizontalScrollBar().valueChanged.connect(lambda _: self.viewport().update())

        self._doc: PDFDocument | None = None
        self._zoom = 1.0
        self._fit_mode = "width"  # width | page | custom
        self._palette: Palette = DARK
        self._page_colors: PageColors | None = None

        # Layout (logical px)
        self._tops: list[float] = []
        self._sizes_px: list[tuple[float, float]] = []
        self._content_w = 0.0
        self._content_h = 0.0
        self._current_page = 0

        # Rendering
        self._cache = RenderCache()
        self._last_key: dict[int, tuple] = {}  # page -> latest cache key (scaled preview)
        self._queue: list[int] = []
        self._render_timer = QTimer(self)
        self._render_timer.setSingleShot(True)
        self._render_timer.setInterval(0)
        self._render_timer.timeout.connect(self._render_next)

        self._refit_timer = QTimer(self)
        self._refit_timer.setSingleShot(True)
        self._refit_timer.setInterval(60)
        self._refit_timer.timeout.connect(self._apply_fit)

        # Overlays
        self._selection: Selection | None = None
        self._tts: tuple[int, int, int] = (-1, -1, -1)
        self._search: dict[int, list[tuple[int, int]]] = {}
        self._search_current: tuple[int, int, int] | None = None
        self._bookmarks: set[int] = set()
        self._highlight_provider: Callable[[int], list[HighlightRow]] | None = None
        self._highlights: dict[int, list[HighlightRow]] = {}

        # Mouse
        self._press_pos: QPointF | None = None
        self._dragging = False

    # ======================================================================
    # Public API
    # ======================================================================

    def load(self, doc: PDFDocument, zoom: float | None = None, fit_mode: str | None = None):
        self._doc = doc
        self._cache.clear()
        self._last_key.clear()
        self._queue.clear()
        self._selection = None
        self._tts = (-1, -1, -1)
        self._search = {}
        self._search_current = None
        self._highlights.clear()
        self._current_page = 0
        if fit_mode:
            self._fit_mode = fit_mode
        if zoom is not None:
            self._zoom = _clamp_zoom(zoom)
        if self._fit_mode != "custom":
            self._zoom = self._fit_zoom()
        self._relayout()
        self.verticalScrollBar().setValue(0)
        self._schedule_visible()
        self.viewport().update()
        self.zoom_changed.emit(self._zoom)
        self.current_page_changed.emit(0)

    def clear(self) -> None:
        self._render_timer.stop()
        self._refit_timer.stop()
        self._doc = None
        self._cache.clear()
        self._last_key.clear()
        self._queue.clear()
        self._tops = []
        self._sizes_px = []
        self._selection = None
        self.viewport().update()

    @property
    def is_loaded(self) -> bool:
        return self._doc is not None and self._doc.is_loaded

    @property
    def page_count(self) -> int:
        return self._doc.page_count if self._doc else 0

    @property
    def current_page(self) -> int:
        return self._current_page

    # ---- zoom ----

    @property
    def zoom(self) -> float:
        return self._zoom

    @property
    def fit_mode(self) -> str:
        return self._fit_mode

    def set_zoom(self, zoom: float, anchor: QPointF | None = None) -> None:
        self._fit_mode = "custom"
        self._change_zoom(_clamp_zoom(zoom), anchor)

    def set_fit_mode(self, mode: str) -> None:
        self._fit_mode = mode
        if mode != "custom":
            self._change_zoom(self._fit_zoom())

    def zoom_in(self) -> None:
        self.set_zoom(next((z for z in ZOOM_STEPS if z > self._zoom + 1e-3), ZOOM_MAX))

    def zoom_out(self) -> None:
        self.set_zoom(next((z for z in reversed(ZOOM_STEPS) if z < self._zoom - 1e-3), ZOOM_MIN))

    # ---- navigation ----

    def go_to_page(self, page: int, y_pts: float | None = None) -> None:
        if not self.is_loaded or not (0 <= page < self.page_count):
            return
        y = self._tops[page] - PAGE_GAP
        if y_pts is not None:
            y += y_pts * self._scale(page)
        self.verticalScrollBar().setValue(int(max(0, y)))
        # Make current_page reflect the explicit jump even when the scroll
        # position cannot move (e.g. last page already fully visible).
        if page != self._current_page and self.verticalScrollBar().value() == int(max(0, y)):
            self._current_page = page
            self.current_page_changed.emit(page)

    def reading_position(self) -> tuple[int, float]:
        """(page, fraction of that page scrolled past) — survives zoom/resizes."""
        if not self._tops:
            return 0, 0.0
        y = self.verticalScrollBar().value() + PAGE_GAP
        page = self._page_at_y(y)
        h = self._sizes_px[page][1] or 1
        return page, max(0.0, min(1.0, (y - self._tops[page]) / h))

    def set_reading_position(self, page: int, frac: float) -> None:
        if not self._tops or not (0 <= page < len(self._tops)):
            return
        y = self._tops[page] + frac * self._sizes_px[page][1] - PAGE_GAP
        self.verticalScrollBar().setValue(int(max(0, y)))

    # ---- appearance ----

    def set_palette(self, palette: Palette, page_colors: PageColors | None) -> None:
        if page_colors != self._page_colors:
            self._cache.clear()
            self._last_key.clear()
        self._palette = palette
        self._page_colors = page_colors
        self._schedule_visible()
        self.viewport().update()

    # ---- overlays ----

    def highlight_range(self, page: int, start: int, end: int) -> None:
        """Read-aloud highlight: [start, end) of `page`'s text; page < 0 clears."""
        self._tts = (page, start, end)
        if page >= 0:
            self._ensure_range_visible(page, start, end)
        self.viewport().update()

    def set_search_results(self, matches: dict[int, list[tuple[int, int]]]) -> None:
        self._search = matches
        self.viewport().update()

    def set_current_match(self, match: tuple[int, int, int] | None) -> None:
        self._search_current = match
        if match:
            self._ensure_range_visible(*match)
        self.viewport().update()

    def set_bookmarked_pages(self, pages: set[int]) -> None:
        self._bookmarks = set(pages)
        self.viewport().update()

    def set_highlight_provider(self, provider: Callable[[int], list[HighlightRow]] | None) -> None:
        self._highlight_provider = provider
        self.refresh_highlights()

    def refresh_highlights(self) -> None:
        self._highlights.clear()
        self.viewport().update()

    # ---- selection ----

    def selection_range(self) -> tuple[int, int, int] | None:
        if not self._selection or not self._doc:
            return None
        page, a, b = self._selection
        pt = self._doc.page_text(page)
        if not pt:
            return None
        s, e = pt.range_for_words(a, b)
        return page, s, e

    def selected_text(self) -> str:
        if not self._selection or not self._doc:
            return ""
        page, a, b = self._selection
        return self._doc.page_text(page).text_for_words(a, b)

    def selection_rects(self) -> list[tuple[float, float, float, float]]:
        sel = self.selection_range()
        if not sel or not self._doc:
            return []
        return self._doc.page_text(sel[0]).rects_for_range(sel[1], sel[2])

    def clear_selection(self) -> None:
        if self._selection:
            self._selection = None
            self.selection_changed.emit("")
            self.viewport().update()

    def select_all_on_page(self) -> None:
        if not self._doc:
            return
        pt = self._doc.page_text(self._current_page)
        if pt:
            self._selection = (self._current_page, 0, len(pt.words) - 1)
            self.selection_changed.emit(self.selected_text())
            self.viewport().update()

    def copy_selection(self) -> bool:
        text = self.selected_text()
        if text:
            clipboard = QGuiApplication.clipboard()
            if clipboard is not None:
                clipboard.setText(text)
        return bool(text)

    # ======================================================================
    # Layout
    # ======================================================================

    def _scale(self, page: int) -> float:
        """Logical px per PDF point (uniform today; per-page hook for the future)."""
        return self._zoom * BASE_SCALE

    def _relayout(self) -> None:
        self._tops = []
        self._sizes_px = []
        if not self._doc:
            return
        k = self._zoom * BASE_SCALE
        y = float(PAGE_GAP)
        max_w = 0.0
        for w, h in self._doc.page_sizes:
            pw, ph = w * k, h * k
            self._tops.append(y)
            self._sizes_px.append((pw, ph))
            max_w = max(max_w, pw)
            y += ph + PAGE_GAP
        self._content_w = max_w + 2 * MARGIN
        self._content_h = y
        self._update_scrollbars()

    def _update_scrollbars(self) -> None:
        vp = self.viewport().size()
        self.verticalScrollBar().setPageStep(vp.height())
        self.verticalScrollBar().setRange(0, max(0, int(self._content_h - vp.height())))
        self.horizontalScrollBar().setPageStep(vp.width())
        self.horizontalScrollBar().setRange(0, max(0, int(self._content_w - vp.width())))

    def _page_rect(self, page: int) -> QRectF:
        """Page rectangle in viewport coordinates."""
        w, h = self._sizes_px[page]
        content_w = max(self._content_w, self.viewport().width())
        x = (content_w - w) / 2 - self.horizontalScrollBar().value()
        y = self._tops[page] - self.verticalScrollBar().value()
        return QRectF(x, y, w, h)

    def _page_at_y(self, y: float) -> int:
        if not self._tops:
            return 0
        return max(0, bisect.bisect_right(self._tops, y) - 1)

    def _visible_pages(self, extra: int = 0) -> range:
        if not self._tops:
            return range(0)
        top = self.verticalScrollBar().value()
        first = self._page_at_y(top)
        last = self._page_at_y(top + self.viewport().height())
        return range(max(0, first - extra), min(len(self._tops), last + 1 + extra))

    def _fit_zoom(self) -> float:
        if not self._doc or not self._doc.page_count:
            return self._zoom
        sizes = self._doc.page_sizes
        vp = self.viewport().size()
        avail_w = max(100, vp.width() - 2 * MARGIN)
        zoom = avail_w / (max(w for w, _ in sizes) * BASE_SCALE)
        if self._fit_mode == "page":
            max_h = max(h for _, h in sizes) * BASE_SCALE
            zoom = min(zoom, max(100, vp.height() - 2 * PAGE_GAP) / max_h)
        return _clamp_zoom(zoom)

    def _apply_fit(self) -> None:
        if self._fit_mode != "custom" and self.is_loaded:
            self._change_zoom(self._fit_zoom())

    def _change_zoom(self, zoom: float, anchor: QPointF | None = None) -> None:
        if not self.is_loaded:
            self._zoom = zoom
            return
        if abs(zoom - self._zoom) < 1e-4:
            return
        # Keep the document point under `anchor` (default: viewport top-centre) fixed.
        ax = anchor.x() if anchor else self.viewport().width() / 2
        ay = anchor.y() if anchor else 0.0
        doc_y = self.verticalScrollBar().value() + ay
        page = self._page_at_y(doc_y)
        within = (doc_y - self._tops[page]) / self._scale(page)
        width = max(1.0, max(self._content_w, self.viewport().width()))
        rel_x = (self.horizontalScrollBar().value() + ax) / width

        self._zoom = zoom
        self._relayout()

        self.verticalScrollBar().setValue(
            int(max(0, self._tops[page] + within * self._scale(page) - ay))
        )
        new_width = max(self._content_w, self.viewport().width())
        self.horizontalScrollBar().setValue(int(max(0, rel_x * new_width - ax)))
        self._queue.clear()
        self._schedule_visible()
        self.viewport().update()
        self.zoom_changed.emit(self._zoom)

    # ======================================================================
    # Rendering
    # ======================================================================

    def _key(self, page: int) -> tuple:
        colors = (self._page_colors.ink, self._page_colors.paper) if self._page_colors else None
        return (page, round(self._zoom, 4), self.devicePixelRatioF(), colors)

    def _schedule_visible(self) -> None:
        if not self.is_loaded:
            return
        visible = list(self._visible_pages())
        around = [p for p in self._visible_pages(PREFETCH) if p not in visible]
        self._queue = [p for p in visible + around if self._key(p) not in self._cache]
        if self._queue:
            self._render_timer.start()

    def _render_next(self) -> None:
        if not self._queue or not self._doc or not self._doc.is_loaded:
            return
        page = self._queue.pop(0)
        key = self._key(page)
        if key not in self._cache:
            try:
                img = render_page(
                    self._doc.page(page), self._zoom, self.devicePixelRatioF(), self._page_colors
                )
                self._cache.put(key, img)
                self._last_key[page] = key
            except Exception:
                pass
            if page in self._visible_pages(PREFETCH):
                self.viewport().update()
        if self._queue:
            self._render_timer.start()

    def render_pending(self) -> int:
        """Pages still waiting to be rendered (for tests and diagnostics)."""
        return len(self._queue)

    # ======================================================================
    # Painting
    # ======================================================================

    def paintEvent(self, event: QPaintEvent) -> None:
        p = QPainter(self.viewport())
        P = self._palette
        p.fillRect(self.viewport().rect(), QColor(P.bg))
        if not self.is_loaded or not self._tops:
            return
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        paper = QColor(f"#{self._page_colors.paper:06x}") if self._page_colors else QColor("white")
        border = QColor(P.border_light)

        for page in self._visible_pages():
            rect = self._page_rect(page)
            img = self._cache.get(self._key(page))
            if img is None:
                stale = self._last_key.get(page)
                img = self._cache.get(stale) if stale else None
            if img is not None:
                p.drawImage(rect, img)
            else:
                p.fillRect(rect, paper)
            p.setPen(QPen(border, 1))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(rect.adjusted(-0.5, -0.5, 0.5, 0.5))
            self._paint_overlays(p, page, rect)

    def _paint_overlays(self, p: QPainter, page: int, rect: QRectF) -> None:
        assert self._doc is not None
        P = self._palette
        k = self._scale(page)
        pt = self._doc.page_text(page)
        p.setPen(Qt.PenStyle.NoPen)

        def box(r) -> QRectF:
            return QRectF(
                rect.x() + r[0] * k, rect.y() + r[1] * k, (r[2] - r[0]) * k, (r[3] - r[1]) * k
            )

        def fill_range(start: int, end: int, color: QColor, radius: float = 2.0) -> None:
            p.setBrush(color)
            for r in pt.rects_for_range(start, end):
                p.drawRoundedRect(box(r).adjusted(-1, -1, 1, 1), radius, radius)

        # User highlights (with a dot marking an attached note)
        for h in self._page_highlights(page):
            c = QColor(h.color)
            c.setAlpha(110 if P.is_dark else 90)
            p.setBrush(c)
            for r in h.rects:
                p.drawRect(box(r))
            if h.note and h.rects:
                last = h.rects[-1]
                p.setBrush(QColor(h.color))
                p.drawEllipse(QPointF(rect.x() + last[2] * k + 5, rect.y() + last[1] * k + 3), 3, 3)

        # Search hits
        for s, e in self._search.get(page, ()):
            fill_range(s, e, qcolor(P.search_hit))
        if self._search_current and self._search_current[0] == page:
            fill_range(self._search_current[1], self._search_current[2], qcolor(P.search_current))

        # Selection
        sel = self.selection_range()
        if sel and sel[0] == page:
            fill_range(sel[1], sel[2], qcolor(P.selection), 1.0)

        # Read-aloud sentence
        tp, ts, te = self._tts
        if tp == page and ts >= 0:
            p.setPen(QPen(qcolor(P.tts_stroke), 1.5))
            fill_range(ts, te, qcolor(P.tts_fill), 3.0)
            p.setPen(Qt.PenStyle.NoPen)

        # Bookmark ribbon
        if page in self._bookmarks:
            w, x, top = 14.0, rect.right() - 28, rect.top()
            p.setBrush(QColor(P.accent))
            p.drawPolygon(
                QPolygonF(
                    [
                        QPointF(x, top),
                        QPointF(x + w, top),
                        QPointF(x + w, top + 22),
                        QPointF(x + w / 2, top + 16),
                        QPointF(x, top + 22),
                    ]
                )
            )

    def _page_highlights(self, page: int) -> list[HighlightRow]:
        if self._highlight_provider is None:
            return []
        rows = self._highlights.get(page)
        if rows is None:
            rows = self._highlight_provider(page)
            self._highlights[page] = rows
        return rows

    # ======================================================================
    # Events
    # ======================================================================

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._update_scrollbars()
        if self._fit_mode != "custom":
            self._refit_timer.start()
        self._schedule_visible()

    def _on_scrolled(self, _value: int) -> None:
        if not self._tops:
            return
        mid = self.verticalScrollBar().value() + self.viewport().height() / 2
        page = self._page_at_y(mid)
        if page != self._current_page:
            self._current_page = page
            self.current_page_changed.emit(page)
        self._schedule_visible()
        self.viewport().update()

    def wheelEvent(self, event: QWheelEvent) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            steps = event.angleDelta().y() / 120
            if steps:
                self.set_zoom(self._zoom * (1.1**steps), anchor=event.position())
            event.accept()
            return
        super().wheelEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        if key == Qt.Key.Key_Home:
            self.verticalScrollBar().setValue(0)
        elif key == Qt.Key.Key_End:
            self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())
        else:
            super().keyPressEvent(event)

    # ---- hit testing ----

    def _hit(self, pos: QPointF) -> tuple[int, float, float] | None:
        """Map a viewport point to (page, x_pts, y_pts) if it lies on a page."""
        if not self._tops:
            return None
        page = self._page_at_y(pos.y() + self.verticalScrollBar().value())
        rect = self._page_rect(page)
        if not rect.contains(pos):
            return None
        k = self._scale(page)
        return page, (pos.x() - rect.x()) / k, (pos.y() - rect.y()) / k

    def _hit_on_page(self, pos: QPointF, page: int) -> tuple[float, float]:
        rect = self._page_rect(page)
        k = self._scale(page)
        x = min(max(pos.x(), rect.left()), rect.right())
        y = min(max(pos.y(), rect.top()), rect.bottom())
        return (x - rect.x()) / k, (y - rect.y()) / k

    def _link_at(self, page: int, x: float, y: float) -> Link | None:
        assert self._doc is not None
        for ln in self._doc.links(page):
            x0, y0, x1, y1 = ln.rect
            if x0 <= x <= x1 and y0 <= y <= y1:
                return ln
        return None

    def _highlight_at(self, page: int, x: float, y: float) -> HighlightRow | None:
        for h in self._page_highlights(page):
            for x0, y0, x1, y1 in h.rects:
                if x0 <= x <= x1 and y0 <= y <= y1:
                    return h
        return None

    def _page_text(self, page: int) -> PageText:
        assert self._doc is not None
        return self._doc.page_text(page)

    # ---- mouse ----

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton or not self.is_loaded:
            super().mousePressEvent(event)
            return
        self.setFocus()
        self._press_pos = event.position()
        self._dragging = False
        hit = self._hit(event.position())
        if hit:
            page, x, y = hit
            w = self._page_text(page).word_at_point(x, y, tolerance=2)
            if w >= 0:
                self._selection = (page, w, w)
                self._dragging = True
                return
        self.clear_selection()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._press_pos is not None and self._selection and self._dragging:
            page, anchor, _ = self._selection
            x, y = self._hit_on_page(event.position(), page)
            focus = self._page_text(page).nearest_word(x, y)
            if focus >= 0:
                self._selection = (page, anchor, focus)
                self.viewport().update()
            return
        hit = self._hit(event.position())
        cursor = Qt.CursorShape.ArrowCursor
        if hit:
            page, x, y = hit
            if self._link_at(page, x, y):
                cursor = Qt.CursorShape.PointingHandCursor
            elif self._page_text(page).word_at_point(x, y, tolerance=2) >= 0:
                cursor = Qt.CursorShape.IBeamCursor
        self.viewport().setCursor(cursor)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton or self._press_pos is None:
            super().mouseReleaseEvent(event)
            return
        moved = (event.position() - self._press_pos).manhattanLength() > DRAG_THRESHOLD
        self._press_pos = None
        self._dragging = False
        if not moved:
            # A click, not a drag: follow a link, otherwise drop the 1-word selection.
            hit = self._hit(event.position())
            link = self._link_at(*hit) if hit else None
            self._selection = None
            self.viewport().update()
            self.selection_changed.emit("")
            if link is not None:
                self._follow(link)
            return
        self.selection_changed.emit(self.selected_text())

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        hit = self._hit(event.position())
        if hit:
            page, x, y = hit
            w = self._page_text(page).word_at_point(x, y, tolerance=2)
            if w >= 0:
                self._selection = (page, w, w)
                self.viewport().update()
                self.selection_changed.emit(self.selected_text())

    def _follow(self, link: Link) -> None:
        if link.page >= 0:
            self.go_to_page(link.page, link.y)
        elif link.uri:
            QDesktopServices.openUrl(QUrl(link.uri))

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        if not self.is_loaded:
            return
        menu = self.build_context_menu(QPointF(event.pos()))
        if not menu.isEmpty():
            menu.exec(event.globalPos())

    def build_context_menu(self, pos: QPointF) -> QMenu:
        hit = self._hit(pos)
        menu = QMenu(self)
        sel = self.selection_range()
        text = self.selected_text()

        if sel and text:
            menu.addAction("Copy", self.copy_selection)
            menu.addAction("Read selection aloud", lambda: self.read_range_requested.emit(*sel))
            menu.addSeparator()
            menu.addAction("Highlight", lambda: self.highlight_requested.emit(*sel, False))
            menu.addAction(
                "Highlight with note…", lambda: self.highlight_requested.emit(*sel, True)
            )
            short = text if len(text) <= 30 else text[:30] + "…"
            menu.addAction(f"Search for “{short}”", lambda: self.search_requested.emit(text))
            menu.addSeparator()

        if hit:
            page, x, y = hit
            h = self._highlight_at(page, x, y)
            if h is not None:
                hid = h.id
                menu.addAction(
                    "Edit note…" if h.note else "Add note…",
                    lambda: self.highlight_edit_requested.emit(hid),
                )
                menu.addAction(
                    "Remove highlight", lambda: self.highlight_remove_requested.emit(hid)
                )
                menu.addSeparator()
            pt = self._page_text(page)
            w = pt.word_at_point(x, y, tolerance=2)
            if w < 0:
                w = pt.nearest_word(x, y)
            if w >= 0:
                offset = pt.ranges[w][0]
                menu.addAction(
                    "Read aloud from here", lambda: self.read_from_requested.emit(page, offset)
                )
            menu.addAction(
                "Remove bookmark" if page in self._bookmarks else "Bookmark this page",
                lambda: self.bookmark_toggle_requested.emit(page),
            )
            menu.addAction("Select all on page", self.select_all_on_page)
        return menu

    # ---- helpers ----

    def _ensure_range_visible(self, page: int, start: int, end: int) -> None:
        if not self._tops or not (0 <= page < len(self._tops)) or not self._doc:
            return
        k = self._scale(page)
        rects = self._doc.page_text(page).rects_for_range(start, end)
        top = self._tops[page]
        if rects:
            y0 = top + min(r[1] for r in rects) * k
            y1 = top + max(r[3] for r in rects) * k
        else:
            y0 = y1 = top
        bar = self.verticalScrollBar()
        view_h = self.viewport().height()
        if y0 < bar.value() or y1 > bar.value() + view_h:
            bar.setValue(int(max(0, y0 - view_h / 3)))


def _clamp_zoom(z: float) -> float:
    return max(ZOOM_MIN, min(ZOOM_MAX, float(z)))
