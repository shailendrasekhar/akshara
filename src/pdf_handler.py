"""
PDF Handler Module
Handles PDF loading, rendering, and text extraction using PyMuPDF.
"""

import fitz  # PyMuPDF
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtCore import QObject, pyqtSignal, QRectF
from typing import Optional, List
from dataclasses import dataclass


@dataclass
class TextSpan:
    """Represents a text span with its bounding box."""
    text: str
    bbox: QRectF  # In page coordinates


class PDFDocument(QObject):
    """
    Manages PDF document operations including loading, rendering, and text extraction.
    """
    
    document_loaded = pyqtSignal(int)  # Emits total page count
    page_rendered = pyqtSignal(QPixmap)  # Emits rendered page
    error_occurred = pyqtSignal(str)  # Emits error message
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._doc: Optional[fitz.Document] = None
        self._current_page: int = 0
        self._zoom: float = 1.0
        self._file_path: str = ""
        self._dark_mode: bool = True  # Dark mode for PDF rendering
    
    @property
    def is_loaded(self) -> bool:
        """Check if a document is currently loaded."""
        return self._doc is not None
    
    @property
    def page_count(self) -> int:
        """Get total number of pages."""
        return len(self._doc) if self._doc else 0
    
    @property
    def current_page(self) -> int:
        """Get current page number (0-indexed)."""
        return self._current_page
    
    @current_page.setter
    def current_page(self, value: int):
        """Set current page number with bounds checking."""
        if self._doc:
            self._current_page = max(0, min(value, self.page_count - 1))
    
    @property
    def zoom(self) -> float:
        """Get current zoom level."""
        return self._zoom
    
    @zoom.setter
    def zoom(self, value: float):
        """Set zoom level (0.5 to 3.0)."""
        self._zoom = max(0.5, min(value, 3.0))
    
    @property
    def dark_mode(self) -> bool:
        """Get dark mode setting for PDF rendering."""
        return self._dark_mode
    
    @dark_mode.setter
    def dark_mode(self, value: bool):
        """Set dark mode for PDF rendering."""
        self._dark_mode = value
    
    @property
    def file_path(self) -> str:
        """Get the path of the currently loaded file."""
        return self._file_path
    
    @property
    def title(self) -> str:
        """Get document title or filename."""
        if self._doc:
            metadata = self._doc.metadata
            if metadata and metadata.get("title"):
                return metadata["title"]
            return self._file_path.split("/")[-1] if self._file_path else "Untitled"
        return ""
    
    def load(self, file_path: str) -> bool:
        """
        Load a PDF document from the given file path.
        
        Args:
            file_path: Path to the PDF file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Close any existing document
            self.close()
            
            # Open the new document
            self._doc = fitz.open(file_path)
            self._file_path = file_path
            self._current_page = 0
            
            self.document_loaded.emit(self.page_count)
            return True
            
        except Exception as e:
            self.error_occurred.emit(f"Failed to load PDF: {str(e)}")
            return False
    
    def close(self):
        """Close the current document."""
        if self._doc:
            self._doc.close()
            self._doc = None
            self._file_path = ""
            self._current_page = 0
    
    def get_page_size(self, page_num: Optional[int] = None) -> tuple[float, float]:
        """
        Get the size of a page in points.
        
        Returns:
            Tuple of (width, height) in points
        """
        if not self._doc:
            return 0, 0
        
        if page_num is None:
            page_num = self._current_page
        
        try:
            page = self._doc[page_num]
            rect = page.rect
            return rect.width, rect.height
        except:
            return 0, 0
    
    def render_page(self, page_num: Optional[int] = None) -> tuple[Optional[QPixmap], List[TextSpan], float]:
        """
        Render a page as a QPixmap and extract text spans.
        
        Args:
            page_num: Page number to render (uses current page if None)
            
        Returns:
            Tuple of (QPixmap, list of TextSpans, scale factor)
        """
        if not self._doc:
            return None, [], 1.0
        
        if page_num is None:
            page_num = self._current_page
        
        try:
            page = self._doc[page_num]
            
            # Calculate scale for rendering
            # Base DPI is 72, we render at higher DPI for quality
            scale = self._zoom * 1.5
            mat = fitz.Matrix(scale, scale)
            
            # Render page to pixmap
            pix = page.get_pixmap(matrix=mat, alpha=False)
            
            # Apply dark mode inversion if enabled
            if self._dark_mode:
                pix.invert_irect()  # Invert colors for dark mode
            
            # Convert to QImage
            img = QImage(
                pix.samples,
                pix.width,
                pix.height,
                pix.stride,
                QImage.Format.Format_RGB888
            )
            
            # Convert to QPixmap
            pixmap = QPixmap.fromImage(img.copy())  # Copy to detach from pix.samples
            
            # Extract text spans with bounding boxes
            text_spans = self._extract_text_spans(page)
            
            return pixmap, text_spans, scale
            
        except Exception as e:
            self.error_occurred.emit(f"Failed to render page: {str(e)}")
            return None, [], 1.0
    
    def _extract_text_spans(self, page: fitz.Page) -> List[TextSpan]:
        """
        Extract text spans with bounding boxes from a page.
        """
        spans = []
        
        try:
            # Get text as dictionary with position info
            blocks = page.get_text("dict")["blocks"]
            
            for block in blocks:
                if block.get("type") != 0:  # Skip non-text blocks
                    continue
                
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = span.get("text", "").strip()
                        if not text:
                            continue
                        
                        bbox = span.get("bbox", [0, 0, 0, 0])
                        rect = QRectF(bbox[0], bbox[1], bbox[2] - bbox[0], bbox[3] - bbox[1])
                        
                        spans.append(TextSpan(text=text, bbox=rect))
            
        except Exception as e:
            self.error_occurred.emit(f"Failed to extract text: {str(e)}")
        
        return spans
    
    def extract_text(self, page_num: Optional[int] = None) -> str:
        """
        Extract plain text from a page.
        
        Args:
            page_num: Page number to extract from (uses current page if None)
            
        Returns:
            Extracted text string
        """
        if not self._doc:
            return ""
        
        if page_num is None:
            page_num = self._current_page
        
        try:
            page = self._doc[page_num]
            return page.get_text()
        except Exception as e:
            self.error_occurred.emit(f"Failed to extract text: {str(e)}")
            return ""
    
    def next_page(self) -> bool:
        """Go to the next page. Returns True if page changed."""
        if self._current_page < self.page_count - 1:
            self._current_page += 1
            return True
        return False
    
    def prev_page(self) -> bool:
        """Go to the previous page. Returns True if page changed."""
        if self._current_page > 0:
            self._current_page -= 1
            return True
        return False
    
    def go_to_page(self, page_num: int) -> bool:
        """
        Go to a specific page.
        
        Args:
            page_num: Page number (0-indexed)
            
        Returns:
            True if page changed
        """
        if 0 <= page_num < self.page_count and page_num != self._current_page:
            self._current_page = page_num
            return True
        return False
