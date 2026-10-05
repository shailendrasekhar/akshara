"""
Page rasterisation and the rendered-page cache.

Pages are rendered at ``zoom × BASE_SCALE × devicePixelRatio`` so text stays
crisp on HiDPI screens. In "match theme" page mode the page is recoloured
(black → theme ink, white → theme paper) and embedded raster images are then
copied back from the untouched render, so photos are not inverted.

PyMuPDF is not thread-safe, so rendering happens on the GUI thread one page
per event-loop turn (see the viewer's render queue); the cache makes revisits
free.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass

import pymupdf
from PyQt6.QtGui import QImage

# 100 % zoom shows the page at its physical size on a 96-dpi display.
BASE_SCALE = 96 / 72


@dataclass(frozen=True)
class PageColors:
    """Recolouring for a page: None means render the PDF's own colours."""

    ink: int  # 0xRRGGBB
    paper: int

    @property
    def is_identity(self) -> bool:
        return self.ink == 0x000000 and self.paper == 0xFFFFFF


def render_page(
    page: pymupdf.Page,
    zoom: float,
    dpr: float = 1.0,
    colors: PageColors | None = None,
) -> QImage:
    scale = zoom * BASE_SCALE * dpr
    matrix = pymupdf.Matrix(scale, scale)
    pix = page.get_pixmap(matrix=matrix, alpha=False, colorspace=pymupdf.csRGB)
    if colors is not None and not colors.is_identity:
        original = pymupdf.Pixmap(pix, 0) if _has_images(page) else None  # 0: no alpha
        pix.tint_with(colors.ink, colors.paper)
        if original is not None:
            for info in page.get_image_info():
                box = (pymupdf.Rect(info["bbox"]) * matrix).irect & pix.irect
                if not box.is_empty:
                    pix.copy(original, box)
    img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888)
    img = img.copy()  # detach from the pixmap's buffer before it is freed
    img.setDevicePixelRatio(dpr)
    return img


def _has_images(page: pymupdf.Page) -> bool:
    try:
        return bool(page.get_images(full=False))
    except Exception:
        return False


class RenderCache:
    """LRU of rendered pages, bounded by approximate memory use."""

    def __init__(self, max_bytes: int = 384 * 1024 * 1024):
        self.max_bytes = max_bytes
        self._items: OrderedDict[tuple, QImage] = OrderedDict()
        self._bytes = 0

    def get(self, key: tuple) -> QImage | None:
        img = self._items.get(key)
        if img is not None:
            self._items.move_to_end(key)
        return img

    def put(self, key: tuple, img: QImage) -> None:
        old = self._items.pop(key, None)
        if old is not None:
            self._bytes -= old.sizeInBytes()
        self._items[key] = img
        self._bytes += img.sizeInBytes()
        while self._bytes > self.max_bytes and len(self._items) > 1:
            _, evicted = self._items.popitem(last=False)
            self._bytes -= evicted.sizeInBytes()

    def clear(self) -> None:
        self._items.clear()
        self._bytes = 0

    def __contains__(self, key: tuple) -> bool:
        return key in self._items

    def __len__(self) -> int:
        return len(self._items)

    @property
    def bytes_used(self) -> int:
        return self._bytes
