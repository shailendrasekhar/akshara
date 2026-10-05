"""Pomodoro timer panel (right dock)."""

from __future__ import annotations

import time
from dataclasses import dataclass

from PyQt6.QtCore import QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QStyle,
    QStyleOption,
    QVBoxLayout,
    QWidget,
)

from .db import Store
from .ui.theme import DARK, MONO_FONT, Palette

# ---------- Defaults ---------------------------------------------------------

PRESETS_MIN = (15, 25, 45, 50)
SHORT_BREAK_S = 5 * 60
LONG_BREAK_S = 15 * 60
CYCLES_PER_LONG = 4

PHASE_LABELS = {"focus": "Deep Focus", "break": "Short Break", "long": "Long Break"}


# ---------- Ring widget ------------------------------------------------------


class _Ring(QWidget):
    """Circular progress ring with mm:ss in the centre."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(200, 200)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._remaining = 25 * 60
        self._total = 25 * 60
        self._phase = "focus"
        self._palette = DARK

    def set_state(self, remaining: int, total: int, phase: str) -> None:
        self._remaining = remaining
        self._total = max(1, total)
        self._phase = phase
        self.update()

    def set_palette(self, palette: Palette) -> None:
        self._palette = palette
        self.update()

    def paintEvent(self, _):
        P = self._palette
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(P.bg))
        ink, line, muted, accent = (QColor(c) for c in (P.text, P.border, P.text_muted, P.accent))

        side = min(self.width(), self.height()) - 16
        rect = QRectF((self.width() - side) / 2, (self.height() - side) / 2, side, side)
        p.setPen(QPen(line, 2))
        p.drawArc(rect, 0, 360 * 16)

        frac = max(0.0, min(1.0, self._remaining / self._total))
        pen = QPen(accent if self._phase != "focus" else ink, 2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawArc(rect, 90 * 16, -int(360 * 16 * frac))

        mm, ss = divmod(self._remaining, 60)
        p.setFont(QFont("Georgia", max(18, int(side / 7)), QFont.Weight.Light))
        p.setPen(ink)
        p.drawText(
            rect.adjusted(0, -10, 0, -10), Qt.AlignmentFlag.AlignCenter, f"{mm:02d}:{ss:02d}"
        )

        small = QFont()
        small.setPointSize(8)
        small.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2.4)
        small.setCapitalization(QFont.Capitalization.AllUppercase)
        p.setFont(small)
        p.setPen(muted)
        p.drawText(
            rect.adjusted(0, 30 + side / 14, 0, 30 + side / 14),
            Qt.AlignmentFlag.AlignCenter,
            PHASE_LABELS[self._phase],
        )


# ---------- Panel ------------------------------------------------------------


@dataclass
class _ActiveSession:
    db_id: int
    started_at: float
    planned_s: int
    phase: str


class PomodoroPanel(QWidget):
    """
    Right-side pomodoro panel. `phase_completed(phase, minutes)` fires when a
    phase ends (naturally or skipped) and `next_phase(phase)` once the timer
    has advanced, so the window can notify the reader.
    """

    phase_completed = pyqtSignal(str, int)  # phase, minutes
    next_phase = pyqtSignal(str)
    running_changed = pyqtSignal(bool)

    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, p, self)

    def __init__(self, store: Store, parent=None):
        super().__init__(parent)
        self.store = store
        self._doc_id: str | None = None
        self._preset = 25
        self._short_s = SHORT_BREAK_S
        self._long_s = LONG_BREAK_S
        self._cycles = CYCLES_PER_LONG
        self._auto_break = False
        self._phase = "focus"
        self._cycle = 0
        self._total = self._preset * 60
        self._remaining = self._total
        self._running = False
        self._active: _ActiveSession | None = None
        self._palette = DARK

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)

        self._build()
        self._apply_panel_style()
        self._refresh()

    # ---- public API ----

    def configure(
        self,
        focus_min: int = 25,
        short_min: int = 5,
        long_min: int = 15,
        cycles: int = CYCLES_PER_LONG,
        auto_start_breaks: bool = False,
    ) -> None:
        self._short_s = max(1, short_min) * 60
        self._long_s = max(1, long_min) * 60
        self._cycles = max(1, cycles)
        self._auto_break = auto_start_breaks
        self._rebuild_pills()
        if not self._running and self._active is None:
            self.set_preset(max(1, focus_min))

    def set_active_document(self, doc_id: str | None) -> None:
        self._doc_id = doc_id
        if doc_id and self._active is not None:
            self.store.attach_session(self._active.db_id, doc_id)

    @property
    def active_session_id(self) -> int | None:
        return self._active.db_id if self._active else None

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def phase(self) -> str:
        return self._phase

    def set_palette(self, palette: Palette) -> None:
        self._palette = palette
        self.ring.set_palette(palette)
        self._apply_panel_style()
        self._refresh()

    def set_dark_mode(self, dark: bool) -> None:  # legacy API
        from .ui.theme import LIGHT

        self.set_palette(DARK if dark else LIGHT)

    def _apply_panel_style(self):
        P = self._palette
        self.setStyleSheet(
            f"""
            PomodoroPanel {{ background:{P.bg}; }}
            PomodoroPanel QLabel {{ background:transparent; color:{P.text}; }}
            PomodoroPanel QPushButton {{
                background:transparent; color:{P.text}; border:1px solid {P.border};
                border-radius:5px; padding:6px 12px; font-size:14px;
            }}
            PomodoroPanel QPushButton:hover {{ background:{P.bg_hover}; }}
            PomodoroPanel QPushButton:disabled {{ color:{P.text_muted}; border-color:{P.border}; }}
            PomodoroPanel QPushButton#playButton {{
                background:{P.accent}; color:{P.accent_text}; border:none; font-weight:600;
            }}
            PomodoroPanel QPushButton#playButton:hover {{ background:{P.accent_hover}; }}
            PomodoroPanel QPushButton:checked {{
                background:{P.accent}; color:{P.accent_text}; border-color:{P.accent};
            }}
            """
        )

    # ---- layout ----

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 24, 20, 16)
        outer.setSpacing(14)

        self.pill_row = QHBoxLayout()
        self.pill_row.setSpacing(6)
        self._pills: list[QLabel] = []
        outer.addLayout(self.pill_row)
        self._rebuild_pills()

        self.ring = _Ring(self)
        outer.addWidget(self.ring, 1)

        actions = QHBoxLayout()
        actions.addStretch(1)
        self.btn_reset = QPushButton("Reset")
        self.btn_reset.clicked.connect(self.reset)
        self.btn_play = QPushButton("Begin")
        self.btn_play.setObjectName("playButton")
        self.btn_play.clicked.connect(self.toggle)
        self.btn_skip = QPushButton("Skip")
        self.btn_skip.clicked.connect(self.skip)
        for b in (self.btn_reset, self.btn_play, self.btn_skip):
            actions.addWidget(b)
        actions.addStretch(1)
        outer.addLayout(actions)

        presets = QHBoxLayout()
        presets.addStretch(1)
        self._preset_btns: list[tuple[int, QPushButton]] = []
        for m in PRESETS_MIN:
            b = QPushButton(f"{m}m")
            b.setCheckable(True)
            b.setToolTip(f"{m}-minute focus")
            b.clicked.connect(lambda _=False, mm=m: self.set_preset(mm))
            presets.addWidget(b)
            self._preset_btns.append((m, b))
        presets.addStretch(1)
        outer.addLayout(presets)
        outer.addStretch(1)

    def _rebuild_pills(self) -> None:
        while self.pill_row.count():
            item = self.pill_row.takeAt(0)
            if item is not None and (w := item.widget()) is not None:
                w.deleteLater()
        self._pills = []
        self.pill_row.addStretch(1)
        for i in range(self._cycles):
            lab = QLabel(f"{i + 1:02d}")
            lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lab.setFixedSize(36, 22)
            self.pill_row.addWidget(lab)
            self._pills.append(lab)
        self.pill_row.addStretch(1)

    # ---- controls ----

    def set_preset(self, minutes: int):
        if self._running or self._active is not None:
            return
        self._preset = minutes
        self._phase = "focus"
        self._total = minutes * 60
        self._remaining = self._total
        self._refresh()

    def toggle(self):
        if self._running:
            self._pause()
        else:
            self._start()

    def reset(self):
        self._timer.stop()
        if self._active is not None:
            elapsed = int(time.time() - self._active.started_at)
            self.store.end_session(self._active.db_id, completed=False, actual_s=elapsed)
            self._active = None
        self._set_running(False)
        self._remaining = self._total
        self._refresh()

    def skip(self):
        self._timer.stop()
        self._set_running(False)
        self._finish_phase(completed=False)
        self._refresh()

    # ---- internals ----

    def _set_running(self, running: bool) -> None:
        if running != self._running:
            self._running = running
            self.running_changed.emit(running)

    def _start(self):
        if self._active is None:
            self._active = _ActiveSession(
                db_id=self.store.start_session(self._doc_id, self._phase, self._total),
                started_at=time.time(),
                planned_s=self._total,
                phase=self._phase,
            )
        self._set_running(True)
        self._timer.start()
        self._refresh()

    def _pause(self):
        self._set_running(False)
        self._timer.stop()
        self._refresh()

    def _tick(self):
        if self._remaining > 0:
            self._remaining -= 1
        if self._remaining <= 0:
            self._timer.stop()
            self._set_running(False)
            self._finish_phase(completed=True)
            if self._auto_break and self._phase != "focus":
                self._start()
        self._refresh()

    def _finish_phase(self, completed: bool):
        if self._active is not None:
            elapsed = int(time.time() - self._active.started_at)
            self.store.end_session(self._active.db_id, completed=completed, actual_s=elapsed)
            self.phase_completed.emit(self._phase, max(1, round(elapsed / 60)))
            self._active = None
        if self._phase == "focus":
            self._cycle += 1
            if self._cycle % self._cycles == 0:
                self._phase, self._total = "long", self._long_s
            else:
                self._phase, self._total = "break", self._short_s
        else:
            self._phase, self._total = "focus", self._preset * 60
        self._remaining = self._total
        self.next_phase.emit(self._phase)

    def _refresh(self):
        P = self._palette
        self.ring.set_state(self._remaining, self._total, self._phase)
        self.btn_play.setText(
            "Pause" if self._running else ("Resume" if self._active is not None else "Begin")
        )
        for m, b in self._preset_btns:
            b.setChecked(m == self._preset and self._phase == "focus")
            b.setEnabled(not self._running and self._active is None)
        base = f"border-radius:11px;font-family:{MONO_FONT};font-size:10px;letter-spacing:2px;"
        pos = self._cycle % self._cycles
        for i, lab in enumerate(self._pills):
            if i == pos and self._phase == "focus":
                lab.setStyleSheet(f"background:{P.text};color:{P.bg};{base}")
            elif i < pos:
                lab.setStyleSheet(f"background:{P.border_light};color:{P.text_muted};{base}")
            else:
                lab.setStyleSheet(
                    f"background:transparent;color:{P.text_muted};border:1px solid {P.border_light};{base}"
                )
