from __future__ import annotations

from akshara.pomodoro import CYCLES_PER_LONG, LONG_BREAK_S, SHORT_BREAK_S, PomodoroPanel


def _panel(qtbot, store, doc_id):
    p = PomodoroPanel(store)
    qtbot.addWidget(p)
    p.set_active_document(doc_id)
    return p


def test_focus_then_short_break(qtbot, store, sample_pdf):
    doc_id = store.upsert_document(str(sample_pdf), "T", None, 3)
    p = _panel(qtbot, store, doc_id)
    p.set_preset(25)
    p.toggle()
    assert p._running
    p.skip()
    assert p._phase == "break"
    assert p._total == SHORT_BREAK_S
    assert store.summary()["n"] == 1


def test_long_break_after_cycles(qtbot, store, sample_pdf):
    doc_id = store.upsert_document(str(sample_pdf), "T", None, 3)
    p = _panel(qtbot, store, doc_id)
    for _ in range(CYCLES_PER_LONG):
        p.toggle()
        p.skip()  # focus -> break
        if p._phase == "long":
            break
        p.toggle()
        p.skip()  # break -> focus
    assert p._phase == "long"
    assert p._total == LONG_BREAK_S


def test_preset_ignored_while_running(qtbot, store, sample_pdf):
    doc_id = store.upsert_document(str(sample_pdf), "T", None, 3)
    p = _panel(qtbot, store, doc_id)
    p.toggle()
    p.set_preset(50)
    assert p._preset == 25
