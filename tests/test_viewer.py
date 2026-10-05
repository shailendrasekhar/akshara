from __future__ import annotations

import pytest
from PyQt6.QtCore import QPoint, QPointF, Qt

from akshara.pdf_handler import PDFDocument
from akshara.pdf_viewer import ZOOM_MAX, ZOOM_MIN, PDFViewerWidget


@pytest.fixture
def viewer(qtbot, sample_pdf):
    doc = PDFDocument()
    doc.load(str(sample_pdf))
    v = PDFViewerWidget()
    qtbot.addWidget(v)
    v.resize(800, 600)
    v.show()
    v.load(doc, fit_mode="width")
    qtbot.waitUntil(lambda: v.render_pending() == 0)
    return v, doc


def _word_center(v, doc, page, word_index):
    rect = v._page_rect(page)
    k = v._scale(page)
    x0, y0, x1, y1 = doc.page_text(page).words[word_index].rect
    return QPoint(int(rect.x() + (x0 + x1) / 2 * k), int(rect.y() + (y0 + y1) / 2 * k))


def test_fit_width_fills_viewport(qtbot, viewer):
    v, _ = viewer
    # Re-fits (debounced) once the vertical scrollbar narrows the viewport.
    qtbot.waitUntil(lambda: abs(v._page_rect(0).width() - (v.viewport().width() - 48)) < 2)


def test_zoom_steps_and_clamp(viewer):
    v, _ = viewer
    v.set_zoom(1.0)
    v.zoom_in()
    assert v.zoom > 1.0 and v.fit_mode == "custom"
    v.set_zoom(100)
    assert v.zoom == ZOOM_MAX
    v.set_zoom(0.0001)
    assert v.zoom == ZOOM_MIN


def test_go_to_page_updates_current(qtbot, viewer):
    v, _ = viewer
    v.set_zoom(1.0)
    v.go_to_page(2)
    qtbot.waitUntil(lambda: v.current_page == 2)


def test_reading_position_survives_zoom(viewer):
    v, _ = viewer
    v.set_zoom(1.0)
    v.go_to_page(1, 200)
    page, frac = v.reading_position()
    v.set_zoom(2.0)
    v.set_reading_position(page, frac)
    assert v.reading_position()[0] == 1


def test_drag_selects_words(qtbot, viewer):
    v, doc = viewer
    start = _word_center(v, doc, 0, 0)
    end = _word_center(v, doc, 0, 3)
    qtbot.mousePress(v.viewport(), Qt.MouseButton.LeftButton, pos=start)
    qtbot.mouseMove(v.viewport(), end)
    with qtbot.waitSignal(v.selection_changed) as blocker:
        qtbot.mouseRelease(v.viewport(), Qt.MouseButton.LeftButton, pos=end)
    assert blocker.args[0] == "The quick brown fox"
    assert v.selection_range() == (0, 0, len("The quick brown fox"))
    assert v.copy_selection()


def test_click_clears_selection(qtbot, viewer):
    v, doc = viewer
    v.select_all_on_page()
    assert v.selected_text()
    pos = _word_center(v, doc, 0, 1)
    qtbot.mouseClick(v.viewport(), Qt.MouseButton.LeftButton, pos=pos)
    assert v.selected_text() == ""


def test_double_click_selects_word(qtbot, viewer):
    v, doc = viewer
    qtbot.mouseDClick(v.viewport(), Qt.MouseButton.LeftButton, pos=_word_center(v, doc, 0, 2))
    assert v.selected_text() == "brown"


def test_context_menu_offers_actions(viewer):
    v, doc = viewer
    v.select_all_on_page()
    menu = v.build_context_menu(QPointF(_word_center(v, doc, 0, 1)))
    labels = [a.text() for a in menu.actions() if a.text()]
    for expected in (
        "Copy",
        "Read selection aloud",
        "Highlight",
        "Read aloud from here",
        "Bookmark this page",
    ):
        assert expected in labels


def test_context_requests_emit(qtbot, viewer):
    v, doc = viewer
    menu = v.build_context_menu(QPointF(_word_center(v, doc, 0, 4)))
    read_from = next(a for a in menu.actions() if a.text() == "Read aloud from here")
    with qtbot.waitSignal(v.read_from_requested) as blocker:
        read_from.trigger()
    page, offset = blocker.args
    assert page == 0 and doc.page_text(0).text[offset:].startswith("jumps")


def test_page_colors_invalidate_cache(viewer, qtbot):
    from akshara.render import PageColors
    from akshara.ui.theme import DARK

    v, _ = viewer
    assert len(v._cache) > 0
    v.set_palette(DARK, PageColors(0xEEEEEE, 0x111111))
    qtbot.waitUntil(lambda: v.render_pending() == 0)
    assert all(k[3] == (0xEEEEEE, 0x111111) for k in v._cache._items)


def test_paint_with_all_overlays(viewer):
    v, doc = viewer
    pt = doc.page_text(0)
    v.highlight_range(0, 0, 10)
    v.set_search_results({0: pt.find_all("fox")})
    v.set_current_match((0, *pt.find("fox")))
    v.set_bookmarked_pages({0})
    v.select_all_on_page()
    img = v.viewport().grab()
    assert not img.isNull()


def test_internal_link_navigates(qtbot, tmp_path):
    import pymupdf

    path = tmp_path / "links.pdf"
    d = pymupdf.open()
    for _ in range(3):
        d.new_page(width=300, height=400)
    d[0].insert_link(
        {
            "kind": pymupdf.LINK_GOTO,
            "from": pymupdf.Rect(10, 10, 100, 40),
            "page": 2,
            "to": pymupdf.Point(0, 0),
        }
    )
    d.save(str(path))

    doc = PDFDocument()
    doc.load(str(path))
    assert doc.links(0)[0].page == 2
    v = PDFViewerWidget()
    qtbot.addWidget(v)
    v.resize(500, 400)
    v.show()
    v.load(doc, zoom=1.0, fit_mode="custom")
    rect = v._page_rect(0)
    k = v._scale(0)
    qtbot.mouseClick(
        v.viewport(),
        Qt.MouseButton.LeftButton,
        pos=QPoint(int(rect.x() + 50 * k), int(rect.y() + 25 * k)),
    )
    qtbot.waitUntil(lambda: v.current_page == 2)
