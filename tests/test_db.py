from __future__ import annotations

from akshara.db import Store, default_db_path


def test_default_db_path_respects_env(monkeypatch, tmp_path):
    monkeypatch.setenv("AKSHARA_DB", str(tmp_path / "x.db"))
    assert default_db_path() == tmp_path / "x.db"


def test_upsert_document_is_idempotent_by_content(store: Store, sample_pdf):
    a = store.upsert_document(str(sample_pdf), "Title", "Author", 3)
    b = store.upsert_document(str(sample_pdf), "Renamed", None, 3)
    assert a == b
    docs = store.list_documents()
    assert len(docs) == 1
    assert docs[0].title == "Renamed"


def test_last_page_roundtrip(store: Store, sample_pdf):
    doc_id = store.upsert_document(str(sample_pdf), "T", None, 3)
    store.update_last_page(doc_id, 2)
    assert store.list_documents()[0].last_page == 2


def test_sessions_feed_summary_and_daily_totals(store: Store, sample_pdf):
    doc_id = store.upsert_document(str(sample_pdf), "T", None, 3)
    sid = store.start_session(doc_id, "focus", 1500)
    store.end_session(sid, completed=True, actual_s=1500, pages_read=2)
    brk = store.start_session(doc_id, "break", 300)
    store.end_session(brk, completed=True, actual_s=300)

    summary = store.summary()
    assert summary["n"] == 1
    assert summary["done"] == 1
    assert summary["total_s"] == 1500

    daily = store.daily_totals()
    assert len(daily) == 1
    assert daily[0]["focus_s"] == 1500
    assert daily[0]["break_s"] == 300

    hist = dict(store.session_length_histogram())
    assert hist == {"15–25 min": 1}

    per_doc = store.per_document_time()
    assert per_doc[0]["total_s"] == 1500
    assert per_doc[0]["session_n"] == 1


def test_page_views_accumulate(store: Store, sample_pdf):
    doc_id = store.upsert_document(str(sample_pdf), "T", None, 3)
    sid = store.start_session(doc_id, "focus", 1500)
    store.add_page_view(sid, 1, 10)
    store.add_page_view(sid, 1, 5)
    row = store._conn.execute(
        "SELECT dwell_s FROM page_views WHERE session_id=? AND page_no=1", (sid,)
    ).fetchone()
    assert row["dwell_s"] == 15
