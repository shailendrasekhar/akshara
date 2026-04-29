import fitz
from PyQt6.QtCore import QObject, pyqtSignal
from typing import Optional


class PDFDocument(QObject):
    document_loaded = pyqtSignal(int)
    error_occurred = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._doc: Optional[fitz.Document] = None
        self._current_page: int = 0
        self._zoom: float = 1.0
        self._file_path: str = ""
        self.dark_mode: bool = True

    @property
    def is_loaded(self) -> bool:
        return self._doc is not None

    @property
    def page_count(self) -> int:
        return len(self._doc) if self._doc else 0

    @property
    def current_page(self) -> int:
        return self._current_page

    @property
    def zoom(self) -> float:
        return self._zoom

    @zoom.setter
    def zoom(self, value: float):
        self._zoom = max(0.5, min(value, 3.0))

    @property
    def title(self) -> str:
        if self._doc:
            meta = self._doc.metadata
            if meta and meta.get("title"):
                return meta["title"]
            return self._file_path.split("/")[-1] if self._file_path else "Untitled"
        return ""

    def load(self, file_path: str) -> bool:
        try:
            self.close()
            self._doc = fitz.open(file_path)
            self._file_path = file_path
            self._current_page = 0
            self.document_loaded.emit(self.page_count)
            return True
        except Exception as e:
            self.error_occurred.emit(f"Failed to load PDF: {e}")
            return False

    def close(self):
        if self._doc:
            self._doc.close()
            self._doc = None
            self._file_path = ""
            self._current_page = 0

    def get_page_size(self, page_num: Optional[int] = None) -> tuple[float, float]:
        if not self._doc:
            return 0.0, 0.0
        try:
            page = self._doc[page_num if page_num is not None else self._current_page]
            return page.rect.width, page.rect.height
        except Exception:
            return 0.0, 0.0

    def extract_text(self, page_num: Optional[int] = None) -> str:
        if not self._doc:
            return ""
        try:
            return self._doc[page_num if page_num is not None else self._current_page].get_text()
        except Exception as e:
            self.error_occurred.emit(f"Failed to extract text: {e}")
            return ""
