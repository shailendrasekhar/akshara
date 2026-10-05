"""Preferences dialog (Ctrl+,)."""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .settings import Settings
from .tts import ENGINES, KokoroEngine, Voice
from .ui.theme import TEXT_SIZES, THEME_MODES


class SettingsDialog(QDialog):
    preview_voice = pyqtSignal(str, str, float)  # engine key, voice id, rate

    def __init__(
        self,
        settings: Settings,
        voices_for: Callable[[str], list[Voice]],
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.setMinimumWidth(520)
        self.s = settings
        self._voices_for = voices_for

        tabs = QTabWidget()
        tabs.addTab(self._appearance(), "APPEARANCE")
        tabs.addTab(self._speech(), "READ ALOUD")
        tabs.addTab(self._pomodoro(), "POMODORO")
        tabs.addTab(self._general(), "GENERAL")

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.addWidget(tabs)
        lay.addWidget(buttons)

    # ---- tabs ----

    @staticmethod
    def _form() -> tuple[QWidget, QFormLayout]:
        w = QWidget()
        f = QFormLayout(w)
        f.setContentsMargins(16, 16, 16, 16)
        f.setSpacing(10)
        return w, f

    def _appearance(self) -> QWidget:
        w, f = self._form()
        self.theme = QComboBox()
        for key, label in THEME_MODES.items():
            self.theme.addItem(label, key)
        self.theme.setCurrentIndex(max(0, self.theme.findData(self.s.theme)))
        f.addRow("Theme", self.theme)

        self.page_colors = QComboBox()
        self.page_colors.addItem("Match theme (images keep their colours)", "match")
        self.page_colors.addItem("Original PDF colours", "original")
        self.page_colors.setCurrentIndex(max(0, self.page_colors.findData(self.s.page_colors)))
        f.addRow("Page colours", self.page_colors)

        self.text_size = QComboBox()
        for i, (label, _pt, _px) in enumerate(TEXT_SIZES):
            self.text_size.addItem({"S": "Small", "M": "Medium", "L": "Large"}[label], i)
        self.text_size.setCurrentIndex(min(len(TEXT_SIZES) - 1, max(0, self.s.text_size)))
        f.addRow("Interface text", self.text_size)

        self.fit_mode = QComboBox()
        self.fit_mode.addItem("Fit width", "width")
        self.fit_mode.addItem("Fit page", "page")
        self.fit_mode.addItem("Remember zoom per book", "custom")
        self.fit_mode.setCurrentIndex(max(0, self.fit_mode.findData(self.s.fit_mode)))
        f.addRow("Default zoom", self.fit_mode)

        self.splash = QCheckBox("Show splash animation at startup")
        self.splash.setChecked(self.s.show_splash)
        f.addRow("", self.splash)
        return w

    def _speech(self) -> QWidget:
        w, f = self._form()
        self.engine = QComboBox()
        self._fill_engines()
        self.engine.currentIndexChanged.connect(self._fill_voices)
        f.addRow("Engine", self.engine)

        self.addon_btn = QPushButton("Install neural voices…")
        self.addon_btn.setToolTip(
            "Download the Kokoro engine (about 1 GB) into your user data folder"
        )
        self.addon_btn.clicked.connect(self._install_addon)
        self.addon_btn.setVisible(not KokoroEngine.is_available())
        f.addRow("", self.addon_btn)

        self.voice = QComboBox()
        f.addRow("Voice", self.voice)
        self._fill_voices()

        rate_row = QHBoxLayout()
        self.rate = QSlider(Qt.Orientation.Horizontal)
        self.rate.setRange(50, 200)
        self.rate.setValue(round(self.s.tts_rate * 100))
        self.rate_label = QLabel()
        self.rate_label.setObjectName("mono")
        self.rate.valueChanged.connect(lambda v: self.rate_label.setText(f"{v / 100:.2f}×"))
        self.rate_label.setText(f"{self.rate.value() / 100:.2f}×")
        rate_row.addWidget(self.rate, 1)
        rate_row.addWidget(self.rate_label)
        f.addRow("Speed", rate_row)

        preview = QPushButton("Preview voice")
        preview.clicked.connect(
            lambda: self.preview_voice.emit(
                self.engine.currentData(), self.voice.currentData() or "", self.rate.value() / 100
            )
        )
        f.addRow("", preview)

        self.continuous = QCheckBox("Keep reading onto the next page")
        self.continuous.setChecked(self.s.tts_continuous)
        f.addRow("", self.continuous)
        self.preload = QCheckBox("Load the voice model at startup (faster first play)")
        self.preload.setChecked(self.s.tts_preload)
        f.addRow("", self.preload)
        return w

    def _fill_engines(self) -> None:
        current = self.engine.currentData() or self.s.tts_engine
        self.engine.blockSignals(True)
        self.engine.clear()
        for key, cls in ENGINES.items():
            ok = cls.is_available()
            self.engine.addItem(cls.label + ("" if ok else "  (unavailable)"), key)
            if not ok:
                idx = self.engine.count() - 1
                self.engine.setItemData(idx, cls.unavailable_reason(), Qt.ItemDataRole.ToolTipRole)
        self.engine.setCurrentIndex(max(0, self.engine.findData(current)))
        self.engine.blockSignals(False)

    def _install_addon(self) -> None:
        from .addon_dialog import AddonInstallDialog

        dlg = AddonInstallDialog(self)
        dlg.installed.connect(self._on_addon_installed)
        dlg.exec()

    def _on_addon_installed(self) -> None:
        self.addon_btn.setVisible(not KokoroEngine.is_available())
        self.engine.setCurrentIndex(-1)
        self._fill_engines()
        self.engine.setCurrentIndex(max(0, self.engine.findData("kokoro")))
        self._fill_voices()

    def _fill_voices(self) -> None:
        key = self.engine.currentData()
        self.voice.clear()
        voices = self._voices_for(key) if key else []
        for v in voices:
            self.voice.addItem(v.name, v.id)
        idx = self.voice.findData(self.s.tts_voice)
        self.voice.setCurrentIndex(idx if idx >= 0 else 0)
        self.voice.setEnabled(bool(voices))

    def _pomodoro(self) -> QWidget:
        w, f = self._form()

        def spin(value: int, lo: int, hi: int, suffix: str = " min") -> QSpinBox:
            s = QSpinBox()
            s.setRange(lo, hi)
            s.setValue(value)
            s.setSuffix(suffix)
            return s

        self.focus_min = spin(self.s.pomodoro_focus_min, 1, 180)
        self.short_min = spin(self.s.pomodoro_short_min, 1, 60)
        self.long_min = spin(self.s.pomodoro_long_min, 1, 120)
        self.cycles = spin(self.s.pomodoro_cycles, 1, 12, " focus sessions")
        f.addRow("Focus length", self.focus_min)
        f.addRow("Short break", self.short_min)
        f.addRow("Long break", self.long_min)
        f.addRow("Long break after", self.cycles)
        self.auto_break = QCheckBox("Start breaks automatically")
        self.auto_break.setChecked(self.s.pomodoro_auto_break)
        f.addRow("", self.auto_break)
        self.notify = QCheckBox("Desktop notification when a phase ends")
        self.notify.setChecked(self.s.pomodoro_notify)
        f.addRow("", self.notify)
        return w

    def _general(self) -> QWidget:
        w, f = self._form()
        self.reopen = QCheckBox("Reopen the last document at startup")
        self.reopen.setChecked(self.s.reopen_last)
        f.addRow("", self.reopen)
        clear = QPushButton("Clear recent files")
        clear.clicked.connect(self.s.clear_recent)
        f.addRow("", clear)
        path = QLabel(f"Settings file: {self.s.path}")
        path.setObjectName("mono")
        path.setWordWrap(True)
        f.addRow(path)
        return w

    # ---- save ----

    def accept(self) -> None:
        s = self.s
        s.theme = self.theme.currentData()
        s.page_colors = self.page_colors.currentData()
        s.text_size = self.text_size.currentData()
        s.fit_mode = self.fit_mode.currentData()
        s.show_splash = self.splash.isChecked()
        s.tts_engine = self.engine.currentData()
        if self.voice.currentData():
            s.tts_voice = self.voice.currentData()
        s.tts_rate = self.rate.value() / 100
        s.tts_continuous = self.continuous.isChecked()
        s.tts_preload = self.preload.isChecked()
        s.pomodoro_focus_min = self.focus_min.value()
        s.pomodoro_short_min = self.short_min.value()
        s.pomodoro_long_min = self.long_min.value()
        s.pomodoro_cycles = self.cycles.value()
        s.pomodoro_auto_break = self.auto_break.isChecked()
        s.pomodoro_notify = self.notify.isChecked()
        s.reopen_last = self.reopen.isChecked()
        s.sync()
        super().accept()
