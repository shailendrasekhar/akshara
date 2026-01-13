"""
PDF Viewer Widget
Custom widget that renders PDF with selectable text and sequential highlighting.
"""

import fitz  # PyMuPDF
from PyQt6.QtWidgets import QWidget, QScrollArea, QVBoxLayout, QApplication, QMenu
from PyQt6.QtCore import Qt, QRect, QPoint, QRectF, pyqtSignal
from PyQt6.QtGui import (
    QPainter, QImage, QPixmap, QColor, QPen, QBrush,
    QMouseEvent, QPaintEvent
)
from typing import Optional, List
from dataclasses import dataclass


@dataclass
class TextSpan:
    """Represents a text span with its bounding box."""
    text: str
    bbox: QRectF


class PDFPageWidget(QWidget):
    """
    Widget that displays a single PDF page with text selection and TTS highlighting.
    """
    
    text_selected = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._pixmap: Optional[QPixmap] = None
        self._text_spans: List[TextSpan] = []
        self._scale = 1.5
        
        # Full page text for position tracking
        self._full_text: str = ""
        
        # Selection state
        self._selection_start: Optional[QPoint] = None
        self._selection_end: Optional[QPoint] = None
        self._selected_spans: List[int] = []
        self._is_selecting = False
        self._show_selection = True
        
        # TTS highlight - now tracks character position
        self._tts_char_start: int = -1
        self._tts_char_end: int = -1
        self._tts_highlight_spans: List[int] = []
        
        # Colors
        self._selection_color = QColor(99, 102, 241, 80)
        self._tts_color = QColor(250, 204, 21, 150)
        
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.IBeamCursor)
    
    def set_page(self, pixmap: QPixmap, text_spans: List[TextSpan], scale: float):
        """Set the page content."""
        self._pixmap = pixmap
        self._text_spans = text_spans
        self._scale = scale
        
        # Build full text and character position map
        self._build_text_map()
        
        self.clear_selection()
        self.clear_tts_highlight()
        
        if pixmap:
            self.setFixedSize(pixmap.size())
        
        self.update()
    
    def _build_text_map(self):
        """Build full text and map span indices to character positions."""
        parts = []
        self._span_char_ranges = []  # (start, end) for each span
        
        char_pos = 0
        for span in self._text_spans:
            text = span.text
            start = char_pos
            end = char_pos + len(text)
            self._span_char_ranges.append((start, end))
            parts.append(text)
            char_pos = end + 1  # +1 for space between spans
        
        self._full_text = " ".join(parts)
    
    def clear(self):
        """Clear everything."""
        self._pixmap = None
        self._text_spans = []
        self._full_text = ""
        self.clear_selection()
        self.clear_tts_highlight()
        self.update()
    
    def clear_selection(self):
        """Clear user selection."""
        self._selection_start = None
        self._selection_end = None
        self._selected_spans = []
        self._is_selecting = False
        self._show_selection = True
        self.update()
    
    def clear_tts_highlight(self):
        """Clear TTS highlight."""
        self._tts_char_start = -1
        self._tts_char_end = -1
        self._tts_highlight_spans = []
        self.update()
    
    def hide_selection(self):
        """Hide selection during TTS."""
        self._show_selection = False
        self.update()
    
    def show_selection(self):
        """Show selection again."""
        self._show_selection = True
        self.update()
    
    def set_tts_highlight_by_position(self, char_start: int, char_end: int):
        """Highlight text by character position in the full text."""
        self._tts_char_start = char_start
        self._tts_char_end = char_end
        self._tts_highlight_spans = []
        
        if char_start < 0 or char_end < 0:
            self.update()
            return
        
        # Find spans that overlap with this character range
        for i, (span_start, span_end) in enumerate(self._span_char_ranges):
            # Check if ranges overlap
            if span_start < char_end and span_end > char_start:
                self._tts_highlight_spans.append(i)
        
        self.update()
    
    def find_text_position(self, search_text: str, start_from: int = 0) -> tuple[int, int]:
        """Find the position of text in the full document text."""
        search_clean = ' '.join(search_text.lower().split())
        full_clean = ' '.join(self._full_text.lower().split())
        
        # Find position
        pos = full_clean.find(search_clean, start_from)
        if pos >= 0:
            return pos, pos + len(search_clean)
        return -1, -1
    
    def get_selected_text(self) -> str:
        """Get selected text."""
        if not self._selected_spans:
            return ""
        texts = [self._text_spans[i].text for i in sorted(self._selected_spans)]
        return " ".join(texts)
    
    def paintEvent(self, event: QPaintEvent):
        """Paint the page."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        
        # Draw PDF page
        if self._pixmap:
            painter.drawPixmap(0, 0, self._pixmap)
        
        # Draw TTS highlight (yellow)
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
                        span.bbox.height() * self._scale
                    )
                    painter.drawRoundedRect(rect, 3, 3)
        
        # Draw selection (only if no TTS highlight)
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
                        span.bbox.height() * self._scale
                    )
                    painter.drawRoundedRect(rect, 2, 2)
        
        # Draw selection rectangle while dragging
        if self._is_selecting and self._selection_start and self._selection_end:
            painter.setBrush(QBrush(QColor(99, 102, 241, 30)))
            painter.setPen(QPen(QColor(99, 102, 241), 1, Qt.PenStyle.DashLine))
            rect = QRect(self._selection_start, self._selection_end).normalized()
            painter.drawRect(rect)
    
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
        """Double-click to select a word."""
        pos = event.pos()
        for i, span in enumerate(self._text_spans):
            scaled_rect = QRectF(
                span.bbox.x() * self._scale,
                span.bbox.y() * self._scale,
                span.bbox.width() * self._scale,
                span.bbox.height() * self._scale
            )
            if scaled_rect.contains(pos.toPointF()):
                self._selected_spans = [i]
                self._show_selection = True
                self.text_selected.emit(span.text)
                self.update()
                break
    
    def _update_selection(self):
        """Update selected spans based on rectangle."""
        if not self._selection_start or not self._selection_end:
            return
        
        sel_rect = QRect(self._selection_start, self._selection_end).normalized()
        self._selected_spans = []
        
        for i, span in enumerate(self._text_spans):
            span_rect = QRect(
                int(span.bbox.x() * self._scale),
                int(span.bbox.y() * self._scale),
                int(span.bbox.width() * self._scale),
                int(span.bbox.height() * self._scale)
            )
            if sel_rect.intersects(span_rect):
                self._selected_spans.append(i)
    
    def contextMenuEvent(self, event):
        """Right-click menu."""
        selected = self.get_selected_text()
        if selected:
            menu = QMenu(self)
            copy_action = menu.addAction("📋 Copy")
            copy_action.triggered.connect(lambda: self._copy_text(selected))
            menu.exec(event.globalPos())
    
    def _copy_text(self, text: str):
        QApplication.clipboard().setText(text)


class PDFViewerWidget(QWidget):
    """Scrollable PDF viewer with position-based TTS highlighting."""
    
    text_selected = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_read_position = 0  # Track reading position
        self._dark_mode = True
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._update_background()
        
        self.page_widget = PDFPageWidget()
        self.page_widget.text_selected.connect(self.text_selected.emit)
        
        self.scroll_area.setWidget(self.page_widget)
        layout.addWidget(self.scroll_area)
    
    def set_dark_mode(self, dark_mode: bool):
        """Update background color based on theme."""
        self._dark_mode = dark_mode
        self._update_background()
    
    def _update_background(self):
        """Set background to pure black or white."""
        bg_color = "#000000" if self._dark_mode else "#ffffff"
        self.scroll_area.setStyleSheet(f"""
            QScrollArea {{ background-color: {bg_color}; border: none; }}
        """)
    
    def display_page(self, pixmap: QPixmap, text_spans: List[TextSpan], scale: float):
        """Display a page."""
        self._current_read_position = 0
        self.page_widget.set_page(pixmap, text_spans, scale)
    
    def highlight_text(self, text: str):
        """Highlight text for TTS - finds position and highlights sequentially."""
        if not text:
            self.page_widget.show_selection()
            self.page_widget.clear_tts_highlight()
            self._current_read_position = 0
            return
        
        self.page_widget.hide_selection()
        
        # Find text position starting from current read position
        start, end = self.page_widget.find_text_position(text, self._current_read_position)
        
        if start >= 0:
            self.page_widget.set_tts_highlight_by_position(start, end)
            # Update position for next search (move past this chunk)
            self._current_read_position = end
        else:
            # If not found from current position, try from beginning
            start, end = self.page_widget.find_text_position(text, 0)
            if start >= 0:
                self.page_widget.set_tts_highlight_by_position(start, end)
                self._current_read_position = end
    
    def reset_read_position(self):
        """Reset reading position to start."""
        self._current_read_position = 0
    
    def get_selected_text(self) -> str:
        """Get selected text."""
        return self.page_widget.get_selected_text()
    
    def clear_selection(self):
        """Clear selection."""
        self.page_widget.clear_selection()
    
    def clear(self):
        """Clear display."""
        self._current_read_position = 0
        self.page_widget.clear()
