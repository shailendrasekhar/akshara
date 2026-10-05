from __future__ import annotations

import pytest

from akshara.main_window import MainWindow
from akshara.tts.base import State
from tests.test_reader import ScriptedEngine


@pytest.fixture
def window(qtbot, sample_pdf):
    w = MainWindow()
    qtbot.addWidget(w)
    w.resize(1200, 800)
    assert w._load_pdf(str(sample_pdf))
    yield w
    w.close()


def test_bookmark_toggle_and_navigation(window):
    w = window
    w._toggle_bookmark(2)
    assert w._bookmarked == {2}
    assert w.bookmarks.list.count() == 1
    w._jump_bookmark(+1)
    assert w.pdf_viewer.current_page == 2 or w.pdf_viewer.reading_position()[0] >= 1
    w._toggle_bookmark(2)
    assert w._bookmarked == set()


def test_highlight_and_markdown_export(window, tmp_path):
    w = window
    pt = w.pdf_doc.page_text(0)
    s, e = pt.find("quick brown fox")
    w._add_highlight(0, s, e, with_note=False)
    rows = w.store.list_highlights(w._active_doc_id)
    assert [h.text for h in rows] == ["quick brown fox"]
    assert w.notes.list.count() == 1
    w.store.set_highlight_note(rows[0].id, "lovely")
    w._toggle_bookmark(1)
    md = w.notes_markdown()
    assert md.startswith("# Sample Book")
    assert "*Jane Doe*" in md
    assert "> quick brown fox" in md and "lovely" in md
    assert "- Page 2" in md
    w._remove_highlight(rows[0].id)
    assert w.notes.list.count() == 0


def test_theme_cycle_and_persistence(window):
    w = window
    w._set_theme("dark")
    w._cycle_theme()
    assert w.palette_.name == "light"
    w._cycle_theme()
    assert w.palette_.name == "sepia"
    assert w.settings.theme == "sepia"
    w.action("page_colors").setChecked(False)
    w._toggle_page_colors()
    assert w.settings.page_colors == "original"
    assert w.pdf_viewer._page_colors is None


def test_text_size_cycles(window):
    w = window
    before = w.settings.text_size
    w._cycle_text_size()
    assert w.settings.text_size == (before + 1) % 3


def test_focus_mode_and_escape(window):
    w = window
    w.show()
    w._toggle_focus_mode()
    assert w._focus_mode and not w.menuBar().isVisible()
    w._escape()
    assert not w._focus_mode and w.menuBar().isVisible()


def test_escape_closes_find_first(window):
    w = window
    w.show()
    w._open_find("fox")
    assert w.find_bar.isVisible()
    w._escape()
    assert not w.find_bar.isVisible()


def test_find_flow(qtbot, window):
    w = window
    w.show()
    w._open_find("page")
    w.find_bar._emit_search()
    w.search.run_to_completion()
    w._find_next()
    assert w.pdf_viewer._search_current is not None
    assert "of 2" in w.find_bar.status.text()


def test_close_document_returns_to_welcome(window):
    w = window
    w.close_document()
    assert not w.pdf_doc.is_loaded
    assert w.stacked_widget.currentWidget() is w.welcome
    assert not w.action("find").isEnabled()


def test_reading_with_engine(qtbot, window):
    w = window
    engine = ScriptedEngine()
    w._set_engine(engine)
    w._connect_reader()
    w._update_doc_actions()
    w._play_or_pause()
    assert engine.state == State.SPEAKING
    assert w.stop_btn.isEnabled()
    engine.advance()
    assert w.pdf_viewer._tts[0] == 0
    w._play_or_pause()  # pause
    assert engine.state == State.PAUSED
    w._escape()  # stops speech
    assert engine.state == State.IDLE


def test_words_heard_recorded_in_session(window):
    w = window
    engine = ScriptedEngine()
    w._set_engine(engine)
    w._connect_reader()
    w.pomodoro.toggle()
    w._play_page()
    engine.run()
    sid = w.pomodoro.active_session_id
    words = w.store._conn.execute("SELECT words_heard FROM sessions WHERE id=?", (sid,)).fetchone()[
        0
    ]
    assert words > 0
    w.pomodoro.reset()


def test_settings_survive_restart(qtbot, sample_pdf):
    w = MainWindow()
    qtbot.addWidget(w)
    w._set_theme("sepia")
    w._load_pdf(str(sample_pdf))
    w.close()
    w2 = MainWindow()
    qtbot.addWidget(w2)
    assert w2.palette_.name == "sepia"
    assert w2.settings.recent_files == [str(sample_pdf)]
    w2.restore_session()
    assert w2.pdf_doc.is_loaded
    w2.close()


def test_shortcuts_have_no_duplicates(window):
    seen: dict[str, str] = {}
    for key, act in window._actions.items():
        for seq in act.shortcuts():
            s = seq.toString()
            assert s not in seen, f"{s} bound to both {seen[s]} and {key}"
            seen[s] = key


def test_open_missing_file_reports_error(window):
    assert not window._load_pdf("/nope/missing.pdf")
    assert "not found" in window.status_label.text()
