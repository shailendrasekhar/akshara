from __future__ import annotations

import pymupdf
from PyQt6.QtGui import QColor, QImage

from akshara.render import BASE_SCALE, PageColors, RenderCache, render_page


def _doc_with_image():
    doc = pymupdf.open()
    page = doc.new_page(width=200, height=200)
    page.insert_text((20, 40), "Hello", fontsize=20)
    # A solid red 40x40 image at (100, 100)
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 40, 40), False)
    pix.set_rect(pix.irect, (255, 0, 0))
    page.insert_image(pymupdf.Rect(100, 100, 140, 140), pixmap=pix)
    return doc


def test_render_size_respects_zoom_and_dpr(qapp):
    doc = _doc_with_image()
    img = render_page(doc[0], zoom=1.0, dpr=2.0)
    assert abs(img.width() - 200 * BASE_SCALE * 2) <= 1
    assert img.devicePixelRatio() == 2.0


def test_recolor_keeps_images(qapp):
    doc = _doc_with_image()
    k = BASE_SCALE
    dark = PageColors(ink=0xEEEEEE, paper=0x101010)
    img = render_page(doc[0], zoom=1.0, colors=dark)
    paper = QColor(img.pixel(int(5 * k), int(5 * k)))
    assert paper.red() < 0x30  # background went dark
    inside_image = QColor(img.pixel(int(120 * k), int(120 * k)))
    assert (inside_image.red(), inside_image.green()) == (255, 0)  # photo untouched


def test_identity_colors_are_noop(qapp):
    doc = _doc_with_image()
    a = render_page(doc[0], 1.0)
    b = render_page(doc[0], 1.0, colors=PageColors(0x000000, 0xFFFFFF))
    assert a == b


def test_cache_evicts_lru_by_bytes():
    img = QImage(100, 100, QImage.Format.Format_RGB888)
    cache = RenderCache(max_bytes=img.sizeInBytes() * 2)
    cache.put(("a",), img)
    cache.put(("b",), img)
    cache.get(("a",))  # a is now most recent
    cache.put(("c",), img)
    assert ("a",) in cache and ("c",) in cache and ("b",) not in cache
    assert cache.bytes_used == img.sizeInBytes() * 2
