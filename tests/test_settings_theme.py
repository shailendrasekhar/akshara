from __future__ import annotations

import datetime as dt

from akshara.settings import Settings
from akshara.ui.theme import DARK, LIGHT, PALETTES, SEPIA, resolve_palette, stylesheet


def test_settings_defaults_and_roundtrip(tmp_path):
    s = Settings(tmp_path / "s.ini")
    assert s.theme == "system"
    assert s.tts_rate == 1.0
    assert s.tts_continuous is True
    s.theme = "sepia"
    s.tts_rate = 1.25
    s.tts_continuous = False
    s.pomodoro_focus_min = 50
    s.sync()

    s2 = Settings(tmp_path / "s.ini")
    assert s2.theme == "sepia"
    assert s2.tts_rate == 1.25
    assert s2.tts_continuous is False
    assert s2.pomodoro_focus_min == 50


def test_recent_files_dedup_and_cap(tmp_path):
    s = Settings(tmp_path / "s.ini")
    for i in range(15):
        s.add_recent(f"/f{i}.pdf")
    s.add_recent("/f3.pdf")
    assert s.recent_files[0] == "/f3.pdf"
    assert len(s.recent_files) == Settings.MAX_RECENT
    assert s.recent_files.count("/f3.pdf") == 1
    s.clear_recent()
    assert s.recent_files == []


def test_single_recent_file_survives_ini_roundtrip(tmp_path):
    s = Settings(tmp_path / "s.ini")
    s.add_recent("/only.pdf")
    s.sync()
    assert Settings(tmp_path / "s.ini").recent_files == ["/only.pdf"]


def test_resolve_palette():
    assert resolve_palette("sepia") is SEPIA
    assert resolve_palette("dark") is DARK
    assert resolve_palette("time", dt.datetime(2026, 1, 1, 12)) is LIGHT
    assert resolve_palette("time", dt.datetime(2026, 1, 1, 22)) is DARK


def test_stylesheet_renders_for_every_palette():
    for p in PALETTES.values():
        css = stylesheet(p, 15)
        assert p.accent in css and "{" in css
