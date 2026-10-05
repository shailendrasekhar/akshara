from __future__ import annotations

import sqlite3

import pytest

from akshara.db import _V1, SCHEMA_VERSION, Store


def _legacy_db(path, sample_pdf):
    """A database exactly as the pre-migration app left it (user_version 0)."""
    conn = sqlite3.connect(path)
    conn.executescript(_V1)
    conn.execute(
        "INSERT INTO documents (id, title, author, path, pages, added_at, last_opened, last_page) "
        "VALUES ('abc', 'Old Book', NULL, ?, 10, 1, 1, 4)",
        (str(sample_pdf),),
    )
    conn.execute(
        "INSERT INTO sessions (document_id, started_at, phase, duration_s, completed) "
        "VALUES ('abc', strftime('%s','now'), 'focus', 1500, 1)"
    )
    conn.execute("INSERT INTO page_views VALUES (1, 3, 42)")
    conn.execute("INSERT INTO bookmarks (document_id, page_no, created_at) VALUES ('abc', 2, 1)")
    conn.commit()
    conn.close()


def test_fresh_db_is_at_latest_version(store: Store):
    assert store.schema_version == SCHEMA_VERSION


def test_legacy_db_upgrades_and_keeps_data(tmp_path, sample_pdf):
    path = tmp_path / "legacy.db"
    _legacy_db(path, sample_pdf)

    s = Store(path)
    assert s.schema_version == SCHEMA_VERSION
    docs = s.list_documents()
    assert [d.title for d in docs] == ["Old Book"]
    assert docs[0].last_page == 4
    assert s.summary()["total_s"] == 1500
    assert [b.page_no for b in s.list_bookmarks("abc")] == [2]
    assert s._conn.execute("SELECT dwell_s FROM page_views").fetchone()[0] == 42
    assert s._conn.execute("PRAGMA foreign_key_check").fetchall() == []
    s.close()

    # Re-opening is a no-op.
    Store(path).close()


def test_newer_schema_is_refused(tmp_path):
    path = tmp_path / "future.db"
    conn = sqlite3.connect(path)
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}")
    conn.close()
    with pytest.raises(RuntimeError, match="newer"):
        Store(path)


def test_session_without_document(store: Store):
    """Regression: starting a pomodoro before opening a PDF violated the FK."""
    sid = store.start_session(None, "focus", 1500)
    store.end_session(sid, completed=True, actual_s=1500)
    assert store.summary()["n"] == 1


def test_attach_session_and_remove_document(store: Store, sample_pdf):
    sid = store.start_session(None, "focus", 1500)
    doc_id = store.upsert_document(str(sample_pdf), "T", None, 3)
    store.attach_session(sid, doc_id)
    store.add_page_view(sid, 1, 30)
    store.end_session(sid, completed=True, actual_s=1500)
    assert store.per_document_time()[0]["total_s"] == 1500
    # pages_read is derived from page views when not given explicitly
    assert store._conn.execute("SELECT pages_read FROM sessions").fetchone()[0] == 1

    store.toggle_bookmark(doc_id, 2)
    store.add_highlight(doc_id, 1, "quick", [(1, 2, 3, 4)])
    store.remove_document(doc_id)
    assert store.list_documents() == []
    assert store.list_bookmarks(doc_id) == []
    assert store.list_highlights(doc_id) == []
    # Sessions survive (detached) so historical totals are preserved.
    assert store.summary()["total_s"] == 1500


def test_bookmark_toggle(store: Store, sample_pdf):
    doc_id = store.upsert_document(str(sample_pdf), "T", None, 3)
    assert store.toggle_bookmark(doc_id, 2) is True
    assert [b.page_no for b in store.list_bookmarks(doc_id)] == [2]
    assert store.toggle_bookmark(doc_id, 2) is False
    assert store.list_bookmarks(doc_id) == []


def test_highlight_roundtrip(store: Store, sample_pdf):
    doc_id = store.upsert_document(str(sample_pdf), "T", None, 3)
    hid = store.add_highlight(doc_id, 0, "fox", [(1.0, 2.0, 3.0, 4.0)], note="n")
    [h] = store.list_highlights(doc_id, page_no=0)
    assert h.id == hid and h.rects == [(1.0, 2.0, 3.0, 4.0)] and h.note == "n"
    store.set_highlight_note(hid, "changed")
    assert store.list_highlights(doc_id)[0].note == "changed"


def test_streak(store: Store):
    import time

    now = int(time.time())
    for days_ago in (0, 1, 2, 5):
        store._conn.execute(
            "INSERT INTO sessions (started_at, phase, duration_s) VALUES (?, 'focus', 60)",
            (now - days_ago * 86400,),
        )
    assert store.streak_days() == 3
