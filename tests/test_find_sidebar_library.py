from __future__ import annotations

from akshara.db import DocumentRow
from akshara.findbar import DocumentSearch, FindBar
from akshara.library import LibraryPanel, filter_documents, sort_documents
from akshara.pdf_handler import LoadResult, OutlineItem, PDFDocument
from akshara.sidebar import NotesPanel, OutlinePanel


def _doc(sample_pdf):
    d = PDFDocument()
    assert d.load(str(sample_pdf)) == LoadResult.OK
    return d


def test_search_finds_all_and_cycles(qtbot, sample_pdf):
    s = DocumentSearch(_doc(sample_pdf))
    with qtbot.waitSignal(s.results_changed, check_params_cb=lambda r, t, done: done):
        s.start("page")
    assert s.total == 2  # "Second page text", "Third page"
    first = s.next(from_page=1)
    assert first is not None and first[0] == 1
    seen = {s.next(1) for _ in range(s.total)}
    assert len(seen) == s.total
    s.start("PAGE", case_sensitive=True)
    s.run_to_completion()
    assert s.total == 0


def test_search_previous_wraps(sample_pdf):
    s = DocumentSearch(_doc(sample_pdf))
    s.start("the")
    s.run_to_completion()
    last = s.previous(from_page=0)
    assert last == s._flat[-1]


def test_findbar_status_text(qtbot):
    fb = FindBar()
    qtbot.addWidget(fb)
    fb.edit.setText("x")
    fb.set_status(-1, 0, True)
    assert fb.status.text() == "No matches"
    fb.set_status(1, 5, False)
    assert fb.status.text() == "2 of 5+ matches"


def test_outline_tree_and_current_marker(qtbot):
    p = OutlinePanel()
    qtbot.addWidget(p)
    p.set_outline([OutlineItem(1, "One", 0), OutlineItem(2, "One.a", 1), OutlineItem(1, "Two", 5)])
    assert p.tree.topLevelItemCount() == 2
    assert p.tree.topLevelItem(0).childCount() == 1
    p.mark_current(3)
    assert p.tree.currentItem().text(0) == "One.a"
    with qtbot.waitSignal(p.navigate) as blocker:
        p._activated(p.tree.topLevelItem(1))
    assert blocker.args == [5]


def test_outline_from_pdf(tmp_path):
    import pymupdf

    path = tmp_path / "toc.pdf"
    d = pymupdf.open()
    for _ in range(3):
        d.new_page()
    d.set_toc([[1, "Intro", 1], [1, "End", 3]])
    d.save(str(path))
    doc = PDFDocument()
    doc.load(str(path))
    assert [(o.title, o.page) for o in doc.outline()] == [("Intro", 0), ("End", 2)]


def test_password_protected_pdf(tmp_path):
    import pymupdf

    path = tmp_path / "secret.pdf"
    d = pymupdf.open()
    d.new_page()
    d.save(str(path), encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="pw", owner_pw="own")
    doc = PDFDocument()
    assert doc.load(str(path)) == LoadResult.NEEDS_PASSWORD
    assert doc.load(str(path), "nope") == LoadResult.WRONG_PASSWORD
    assert doc.load(str(path), "pw") == LoadResult.OK


def test_notes_panel_lists_highlights(qtbot, store, sample_pdf):
    doc_id = store.upsert_document(str(sample_pdf), "T", None, 3)
    store.add_highlight(doc_id, 1, "Second  page\ntext", [(1, 2, 3, 4)], note="why")
    p = NotesPanel()
    qtbot.addWidget(p)
    p.set_highlights(store.list_highlights(doc_id))
    assert p.list.count() == 1
    assert "“Second page text”" in p.list.item(0).text()
    with qtbot.waitSignal(p.navigate) as blocker:
        p._activated(p.list.item(0))
    assert blocker.args == [1, 2.0]


def _row(title, last_opened, progress, path="/nonexistent.pdf"):
    return DocumentRow("id" + title, title, None, path, 100, int(progress * 100), last_opened)


def test_library_sort_and_filter():
    docs = [_row("beta", 3, 0.1), _row("Alpha", 1, 0.9), _row("gamma", 2, 0.5)]
    assert [d.title for d in sort_documents(docs, "title")] == ["Alpha", "beta", "gamma"]
    assert [d.title for d in sort_documents(docs, "recent")] == ["beta", "gamma", "Alpha"]
    assert [d.title for d in sort_documents(docs, "progress")] == ["Alpha", "gamma", "beta"]
    assert [d.title for d in filter_documents(docs, "AL")] == ["Alpha"]


def test_library_panel_marks_missing_files(qtbot, store, sample_pdf):
    store.upsert_document(str(sample_pdf), "Here", None, 3)
    gone = store.upsert_document(str(sample_pdf), "Gone", None, 3, doc_id="gone")
    store.relocate_document(gone, "/does/not/exist.pdf")
    panel = LibraryPanel(store)
    qtbot.addWidget(panel)
    cards = {c.doc.title: c for c in panel._cards}
    assert not cards["Gone"].doc.exists
    assert "missing" in cards["Gone"]._pages.text()
    assert cards["Here"].doc.exists
