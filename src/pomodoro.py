from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QRectF
from PyQt6.QtGui import QPainter, QPen, QColor, QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy,
    QStyleOption, QStyle,
)

from .db import Store


# ---------- Defaults ---------------------------------------------------------

PRESETS_MIN = (15, 25, 45, 50)
SHORT_BREAK_S = 5 * 60
LONG_BREAK_S = 15 * 60
CYCLES_PER_LONG = 4


# ---------- Ring widget ------------------------------------------------------

class _Ring(QWidget):
    """Circular progress ring with mm:ss in the centre."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(220, 220)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._remaining = 25 * 60
        self._total = 25 * 60
        self._phase = "focus"
        self._dark = True

    def set_state(self, remaining: int, total: int, phase: str) -> None:
        self._remaining = remaining
        self._total = max(1, total)
        self._phase = phase
        self.update()

    def set_dark(self, dark: bool) -> None:
        self._dark = dark
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        bg = QColor("#000000") if self._dark else QColor("#ffffff")
        p.fillRect(self.rect(), bg)
        ink = QColor("#ffffff") if self._dark else QColor("#0a0a0a")
        line = QColor("#222222") if self._dark else QColor("#e6e6e2")
        muted = QColor("#9a9a96") if self._dark else QColor("#6b6b68")
        accent = QColor("#d8a85a")

        side = min(self.width(), self.height()) - 16
        rect = QRectF((self.width() - side) / 2, (self.height() - side) / 2, side, side)

        # track
        pen = QPen(line, 2)
        p.setPen(pen)
        p.drawArc(rect, 0, 360 * 16)

        # progress
        frac = max(0.0, min(1.0, self._remaining / self._total))
        span = int(360 * 16 * frac)
        pen2 = QPen(accent if self._phase != "focus" else ink, 2)
        pen2.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen2)
        p.drawArc(rect, 90 * 16, -span)

        # time
        mm = self._remaining // 60
        ss = self._remaining % 60
        big = QFont("Georgia", 38, QFont.Weight.Light)
        p.setFont(big)
        p.setPen(ink)
        text_rect = rect.adjusted(0, -10, 0, -10)
        p.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, f"{mm:02d}:{ss:02d}")

        small = QFont()
        small.setPointSize(8)
        small.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2.4)
        small.setCapitalization(QFont.Capitalization.AllUppercase)
        p.setFont(small)
        p.setPen(muted)
        label = {"focus": "Deep Focus", "break": "Short Break", "long": "Long Break"}[self._phase]
        p.drawText(rect.adjusted(0, 30, 0, 30), Qt.AlignmentFlag.AlignCenter, label)


# ---------- Panel ------------------------------------------------------------

@dataclass
class _ActiveSession:
    db_id: int
    started_at: float
    planned_s: int
    phase: str


class PomodoroPanel(QWidget):
    """
    Right-side pomodoro panel. Connect `phase_completed(str, int)` to surface
    a notification in the main window. Call `set_active_document(doc_id)` when
    a PDF is loaded so sessions are tied to the right book.
    """

    phase_completed = pyqtSignal(str, int)  # phase ("focus"|"break"|"long"), minutes

    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, p, self)

    def __init__(self, store: Store, parent=None):
        super().__init__(parent)
        self.store = store
        self._doc_id: Optional[str] = None
        self._preset = 25
        self._phase = "focus"
        self._cycle = 0
        self._total = self._preset * 60
        self._remaining = self._total
        self._running = False
        self._active: Optional[_ActiveSession] = None

        self._dark = True
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)

        self._build()
        self._apply_panel_style()
        self._refresh()

    # public API
    def set_active_document(self, doc_id: Optional[str]) -> None:
        self._doc_id = doc_id

    def set_dark_mode(self, dark: bool) -> None:
        self.ring.set_dark(dark)
        self._dark = dark
        self._apply_panel_style()
        self._refresh()

    def _apply_panel_style(self):
        dark   = self._dark
        bg     = "#000000" if dark else "#ffffff"
        ink    = "#f0f0f0" if dark else "#0a0a0a"
        border = "#1e1e1e" if dark else "#e4e4e0"
        hover  = "#181818" if dark else "#eaeae6"
        accent = "#d8a85a"
        # Use the panel's own stylesheet so it wins over the app-level sheet.
        # Every selector is scoped to children of this widget via descendant rules.
        self.setStyleSheet(f"""
            PomodoroPanel {{
                background:{bg};
            }}
            PomodoroPanel QLabel {{
                background:transparent;
                color:{ink};
            }}
            PomodoroPanel QPushButton {{
                background:transparent;
                color:{ink};
                border:1px solid {border};
                border-radius:5px;
                padding:6px 14px;
                font-size:14px;
            }}
            PomodoroPanel QPushButton:hover {{
                background:{hover};
            }}
            PomodoroPanel QPushButton:disabled {{
                color:{'#333333' if dark else '#cccccc'};
                border-color:{'#222' if dark else '#ddd'};
            }}
            PomodoroPanel QPushButton#playButton {{
                background:{accent};
                color:#000000;
                border:none;
                font-weight:600;
            }}
            PomodoroPanel QPushButton#playButton:hover {{
                background:#e8bb6a;
            }}
            PomodoroPanel QPushButton:checked {{
                background:{accent};
                color:#000000;
                border-color:{accent};
            }}
        """)

    # ---- layout ----
    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 24, 20, 16)
        outer.setSpacing(14)

        # phase pills
        self.pill_row = QHBoxLayout()
        self.pill_row.setSpacing(6)
        self._pills = []
        for i in range(CYCLES_PER_LONG):
            lab = QLabel(f"{i+1:02d}")
            lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lab.setFixedSize(36, 22)
            lab.setProperty("class", "pomPill")
            self.pill_row.addWidget(lab)
            self._pills.append(lab)
        self.pill_row.addStretch(1)
        self.pill_row.insertStretch(0, 1)
        outer.addLayout(self.pill_row)

        # ring
        self.ring = _Ring(self)
        outer.addWidget(self.ring, 1)

        # action row
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

        # presets
        presets = QHBoxLayout()
        presets.addStretch(1)
        self._preset_btns = []
        for m in PRESETS_MIN:
            b = QPushButton(f"{m} min")
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, mm=m: self.set_preset(mm))
            presets.addWidget(b)
            self._preset_btns.append((m, b))
        presets.addStretch(1)
        outer.addLayout(presets)
        outer.addStretch(1)

    # ---- controls ----
    def set_preset(self, minutes: int):
        if self._running:
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
            self.store.end_session(self._active.db_id, completed=False,
                                   actual_s=elapsed)
            self._active = None
        self._running = False
        self._remaining = self._total
        self._refresh()

    def skip(self):
        self._remaining = 0
        self._tick()  # forces phase advance

    # ---- internals ----
    def _start(self):
        if self._active is None:
            self._active = _ActiveSession(
                db_id=self.store.start_session(
                    self._doc_id or "unattached",
                    self._phase,
                    self._total,
                ),
                started_at=time.time(),
                planned_s=self._total,
                phase=self._phase,
            )
        self._running = True
        self._timer.start()
        self._refresh()

    def _pause(self):
        self._running = False
        self._timer.stop()
        self._refresh()

    def _tick(self):
        if self._remaining > 0:
            self._remaining -= 1
        if self._remaining <= 0:
            self._timer.stop()
            self._running = False
            self._finish_phase(completed=True)
        self._refresh()

    def _finish_phase(self, completed: bool):
        if self._active is not None:
            elapsed = int(time.time() - self._active.started_at)
            self.store.end_session(self._active.db_id, completed=completed,
                                   actual_s=elapsed)
            mins = max(1, round(elapsed / 60))
            self.phase_completed.emit(self._phase, mins)
            self._active = None
        # advance phase
        if self._phase == "focus":
            self._cycle += 1
            if self._cycle % CYCLES_PER_LONG == 0:
                self._phase, self._total = "long", LONG_BREAK_S
            else:
                self._phase, self._total = "break", SHORT_BREAK_S
        else:
            self._phase, self._total = "focus", self._preset * 60
        self._remaining = self._total

    def _refresh(self):
        self.ring.set_state(self._remaining, self._total, self._phase)
        self.btn_play.setText(
            "Pause" if self._running
            else ("Resume" if self._remaining < self._total else "Begin")
        )
        for m, b in self._preset_btns:
            b.setChecked(m == self._preset and self._phase == "focus")
        # pill colours follow dark/light theme
        _on_bg    = "#ffffff" if self._dark else "#0a0a0a"
        _on_fg    = "#000000" if self._dark else "#ffffff"
        _done_bg  = "#2a2a2a" if self._dark else "#e8e8e8"
        _done_fg  = "#666666" if self._dark else "#999999"
        _idle_col = "#444444" if self._dark else "#cccccc"
        _base = "border-radius:11px;font-family:monospace;font-size:10px;letter-spacing:2px;"
        for i, lab in enumerate(self._pills):
            done = i < (self._cycle % CYCLES_PER_LONG)
            on = i == (self._cycle % CYCLES_PER_LONG) and self._phase == "focus"
            if on:
                lab.setStyleSheet(f"background:{_on_bg};color:{_on_fg};{_base}")
            elif done:
                lab.setStyleSheet(f"background:{_done_bg};color:{_done_fg};{_base}")
            else:
                lab.setStyleSheet(f"background:transparent;color:{_idle_col};"
                                  f"border:1px solid {_idle_col};{_base}")
