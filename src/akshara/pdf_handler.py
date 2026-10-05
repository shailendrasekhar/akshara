"""PDF document model (PyMuPDF): metadata, page geometry, text, links, outline."""

from __future__ import annotations

import enum
import os
from collections import OrderedDict
from dataclasses import dataclass

import pymupdf
from PyQt6.QtCore import QObject, pyqtSignal

from .textmap import PageText

TEXT_CACHE_PAGES = 256


class LoadResult(enum.Enum):
    OK = "ok"
    NEEDS_PASSWORD = "needs_password"
    WRONG_PASSWORD = "wrong_password"
    ERROR = "error"


@dataclass(frozen=True)
class Link:
    rect: tuple[float, float, float, float]
    page: int = -1  # internal destination (0-based), or -1
    y: float = 0.0  # destination y on that page, in points
    uri: str = ""  # external destination


@dataclass(frozen=True)
class OutlineItem:
    level: int
    title: str
    page: int  # 0-based; -1 if the entry has no destination


class PDFDocument(QObject):
    document_loaded = pyqtSignal(int)
    error_occurred = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._doc: pymupdf.Document | None = None
        self._file_path = ""
        self._sizes: list[tuple[float, float]] = []
        self._text_cache: OrderedDict[int, PageText] = OrderedDict()
        self._link_cache: dict[int, list[Link]] = {}

    # ---- loading ----

    def load(self, file_path: str, password: str | None = None) -> LoadResult:
        self.close()
        try:
            doc = pymupdf.open(file_path)
        except Exception as e:
            self.error_occurred.emit(f"Failed to open {os.path.basename(file_path)}: {e}")
            return LoadResult.ERROR
        if doc.needs_pass:
            if password is None:
                doc.close()
                return LoadResult.NEEDS_PASSWORD
            if not doc.authenticate(password):
                doc.close()
                return LoadResult.WRONG_PASSWORD
        if not doc.is_pdf and doc.page_count == 0:
            doc.close()
            self.error_occurred.emit("The file has no pages")
            return LoadResult.ERROR
        self._doc = doc
        self._file_path = file_path
        self._sizes = []
        for i in range(doc.page_count):
            r = doc[i].rect  # honours /Rotate, unlike the raw mediabox
            self._sizes.append((r.width, r.height))
        self.document_loaded.emit(self.page_count)
        return LoadResult.OK

    def close(self) -> None:
        if self._doc:
            self._doc.close()
        self._doc = None
        self._file_path = ""
        self._sizes = []
        self._text_cache.clear()
        self._link_cache.clear()

    # ---- metadata ----

    @property
    def is_loaded(self) -> bool:
        return self._doc is not None

    @property
    def document(self) -> pymupdf.Document | None:
        return self._doc

    @property
    def file_path(self) -> str:
        return self._file_path

    @property
    def page_count(self) -> int:
        return len(self._sizes)

    @property
    def title(self) -> str:
        if not self._doc:
            return ""
        meta = self._doc.metadata or {}
        title = (meta.get("title") or "").strip()
        return title or os.path.splitext(os.path.basename(self._file_path))[0] or "Untitled"

    @property
    def author(self) -> str | None:
        if not self._doc:
            return None
        meta = self._doc.metadata or {}
        return (meta.get("author") or "").strip() or None

    # ---- geometry ----

    def page_size(self, page_num: int) -> tuple[float, float]:
        """Page (width, height) in points."""
        if 0 <= page_num < len(self._sizes):
            return self._sizes[page_num]
        return 0.0, 0.0

    @property
    def page_sizes(self) -> list[tuple[float, float]]:
        return list(self._sizes)

    def page(self, page_num: int) -> pymupdf.Page:
        assert self._doc is not None
        return self._doc[page_num]

    # ---- text ----

    def page_text(self, page_num: int) -> PageText:
        """Word-mapped text of a page (cached; shared by viewer, search and TTS)."""
        if not self._doc or not (0 <= page_num < self.page_count):
            return PageText()
        cached = self._text_cache.get(page_num)
        if cached is not None:
            self._text_cache.move_to_end(page_num)
            return cached
        try:
            cached = PageText.from_page(self._doc[page_num])
        except Exception:
            cached = PageText()
        self._text_cache[page_num] = cached
        if len(self._text_cache) > TEXT_CACHE_PAGES:
            self._text_cache.popitem(last=False)
        return cached

    def extract_text(self, page_num: int) -> str:
        return self.page_text(page_num).text

    # ---- links & outline ----

    def links(self, page_num: int) -> list[Link]:
        if not self._doc or not (0 <= page_num < self.page_count):
            return []
        cached = self._link_cache.get(page_num)
        if cached is None:
            cached = []
            try:
                for ln in self._doc[page_num].get_links():
                    r = ln["from"]
                    rect = (r.x0, r.y0, r.x1, r.y1)
                    if ln.get("kind") == pymupdf.LINK_GOTO and ln.get("page", -1) >= 0:
                        to = ln.get("to")
                        cached.append(Link(rect, page=ln["page"], y=float(to.y) if to else 0.0))
                    elif ln.get("kind") == pymupdf.LINK_URI and ln.get("uri"):
                        cached.append(Link(rect, uri=ln["uri"]))
                    elif ln.get("kind") == pymupdf.LINK_NAMED and ln.get("page", -1) >= 0:
                        cached.append(Link(rect, page=ln["page"]))
            except Exception:
                cached = []
            self._link_cache[page_num] = cached
        return cached

    def outline(self) -> list[OutlineItem]:
        if not self._doc:
            return []
        try:
            toc = self._doc.get_toc(simple=True)
        except Exception:
            return []
        return [OutlineItem(int(lvl), str(title), int(page) - 1) for lvl, title, page in toc]
