from __future__ import annotations

import csv
import time

from akshara.analytics import AnalyticsDialog
from akshara.settings import Settings
from akshara.settings_dialog import SettingsDialog
from akshara.tts.kokoro import VOICES


def test_analytics_dialog_builds_with_data(qtbot, store, sample_pdf, tmp_path):
    doc_id = store.upsert_document(str(sample_pdf), "Book", "Me", 3)
    now = int(time.time())
    store._conn.execute(
        "INSERT INTO sessions (document_id, started_at, phase, duration_s, completed, pages_read, words_heard) "
        "VALUES (?, ?, 'focus', 1500, 1, 4, 300)",
        (doc_id, now),
    )
    dlg = AnalyticsDialog(store)
    qtbot.addWidget(dlg)
    assert len(store.daily_series(28)) == 28
    assert store.daily_series(28)[-1]["focus_s"] == 1500

    out = tmp_path / "s.csv"
    assert store.export_sessions_csv(str(out)) == 1
    rows = list(csv.DictReader(out.open()))
    assert rows[0]["title"] == "Book" and rows[0]["words_heard"] == "300"


def test_analytics_dialog_empty_db(qtbot, store):
    dlg = AnalyticsDialog(store)
    qtbot.addWidget(dlg)
    assert store.best_streak_days() == 0


def test_settings_dialog_saves(qtbot, tmp_path):
    s = Settings(tmp_path / "s.ini")
    dlg = SettingsDialog(s, lambda key: list(VOICES) if key == "kokoro" else [])
    qtbot.addWidget(dlg)
    dlg.theme.setCurrentIndex(dlg.theme.findData("sepia"))
    dlg.focus_min.setValue(40)
    dlg.continuous.setChecked(False)
    dlg.rate.setValue(150)
    dlg.accept()
    assert s.theme == "sepia"
    assert s.pomodoro_focus_min == 40
    assert s.tts_continuous is False
    assert s.tts_rate == 1.5
