"""
Persistent user preferences (QSettings, INI format).

Stored at $XDG_CONFIG_HOME/akshara/settings.ini (overridable with the
AKSHARA_CONFIG env var). Each preference is a typed attribute with a default,
so callers never deal with QVariant conversions.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Generic, TypeVar, overload

from PyQt6.QtCore import QByteArray, QSettings

T = TypeVar("T")


def default_config_path() -> Path:
    override = os.environ.get("AKSHARA_CONFIG")
    if override:
        return Path(override).expanduser()
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "akshara" / "settings.ini"


class _Pref(Generic[T]):
    """Descriptor mapping an attribute onto a QSettings key."""

    def __init__(self, key: str, default: T):
        self.key = key
        self.default = default

    def __set_name__(self, owner, name):
        owner._prefs = {**getattr(owner, "_prefs", {}), name: self}

    @overload
    def __get__(self, obj: None, objtype: Any = None) -> _Pref[T]: ...
    @overload
    def __get__(self, obj: Settings, objtype: Any = None) -> T: ...
    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        raw = obj.qsettings.value(self.key, self.default)
        return _coerce(raw, self.default)

    def __set__(self, obj: Settings, value: T) -> None:
        obj.qsettings.setValue(self.key, value)


def _coerce(raw: Any, default: Any) -> Any:
    if raw is None:
        return default
    if isinstance(default, bool):
        if isinstance(raw, str):
            return raw.lower() in ("1", "true", "yes", "on")
        return bool(raw)
    if isinstance(default, int):
        try:
            return int(raw)
        except (TypeError, ValueError):
            return default
    if isinstance(default, float):
        try:
            return float(raw)
        except (TypeError, ValueError):
            return default
    if isinstance(default, list):
        if isinstance(raw, str):
            return [raw] if raw else []
        return list(raw) if raw is not None else default
    if isinstance(default, str):
        return str(raw)
    return raw


class Settings:
    # Appearance
    theme = _Pref("appearance/theme", "system")  # see ui.theme.THEME_MODES
    page_colors = _Pref("appearance/page_colors", "match")  # match | original
    text_size = _Pref("appearance/text_size", 1)  # index into TEXT_SIZES
    show_splash = _Pref("appearance/show_splash", True)

    # Viewer
    fit_mode = _Pref("viewer/fit_mode", "width")  # width | page | custom
    zoom = _Pref("viewer/zoom", 1.0)

    # Speech
    tts_engine = _Pref("speech/engine", "kokoro")  # kokoro | system
    tts_voice = _Pref("speech/voice", "")
    tts_rate = _Pref("speech/rate", 1.0)
    tts_continuous = _Pref("speech/continuous", True)
    tts_preload = _Pref("speech/preload", True)

    # Pomodoro
    pomodoro_focus_min = _Pref("pomodoro/focus_min", 25)
    pomodoro_short_min = _Pref("pomodoro/short_break_min", 5)
    pomodoro_long_min = _Pref("pomodoro/long_break_min", 15)
    pomodoro_cycles = _Pref("pomodoro/cycles_per_long", 4)
    pomodoro_auto_break = _Pref("pomodoro/auto_start_breaks", False)
    pomodoro_notify = _Pref("pomodoro/notify", True)

    # Session
    reopen_last = _Pref("session/reopen_last", True)
    last_document = _Pref("session/last_document", "")
    recent_files = _Pref("session/recent_files", [])  # type: ignore[var-annotated]
    library_sort = _Pref("library/sort", "recent")  # recent | title | progress

    MAX_RECENT = 10

    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path else default_config_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.qsettings = QSettings(str(self.path), QSettings.Format.IniFormat)

    # ---- window state (opaque blobs) ----

    def window_geometry(self) -> QByteArray | None:
        v = self.qsettings.value("window/geometry")
        return v if isinstance(v, QByteArray) else None

    def window_state(self) -> QByteArray | None:
        v = self.qsettings.value("window/state")
        return v if isinstance(v, QByteArray) else None

    def save_window(self, geometry: QByteArray, state: QByteArray) -> None:
        self.qsettings.setValue("window/geometry", geometry)
        self.qsettings.setValue("window/state", state)

    # ---- recent files ----

    def add_recent(self, path: str) -> None:
        recent = [p for p in self.recent_files if p != path]
        self.recent_files = [path, *recent][: self.MAX_RECENT]

    def clear_recent(self) -> None:
        self.recent_files = []

    def sync(self) -> None:
        self.qsettings.sync()

    def reset(self) -> None:
        self.qsettings.clear()
