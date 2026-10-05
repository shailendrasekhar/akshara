"""
Analytics dialog — reads from db.Store and paints minimal, theme-aware charts.

All time series are calendar-aligned (days without sessions are shown as
empty), so the heatmap and weekly bars line up with real dates.
"""

from __future__ import annotations

import datetime as dt
from typing import ClassVar

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter
from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .db import Store
from .ui.theme import DARK, FONT_FAMILY, MONO_FONT, Palette

DAYS = 28


def _mix(a: QColor, b: QColor, t: float) -> QColor:
    t = max(0.0, min(1.0, t))
    return QColor(
        int(a.red() + (b.red() - a.red()) * t),
        int(a.green() + (b.green() - a.green()) * t),
        int(a.blue() + (b.blue() - a.blue()) * t),
    )


# ---------- Heatmap ----------------------------------------------------------


class _Heatmap(QWidget):
    """One square per day for the last 28 days, oldest at the left."""

    def __init__(self, series: list[dict], palette: Palette, parent=None):
        super().__init__(parent)
        self._series = series
        self._P = palette
        self.setMinimumHeight(64)
        self.setToolTip("Focused reading per day (darker/brighter = more)")

    def paintEvent(self, _):
        p = QPainter(self)
        cols = max(1, len(self._series))
        gap = 3
        size = min(40.0, (self.width() - gap * (cols - 1)) / cols)
        max_focus = max((d["focus_s"] for d in self._series), default=0) or 1
        empty = QColor(self._P.bg_elevated)
        full = QColor(self._P.accent)
        for i, d in enumerate(self._series):
            w = d["focus_s"] / max_focus
            col = empty if w == 0 else _mix(QColor(self._P.border_light), full, 0.25 + 0.75 * w)
            p.fillRect(QRectF(i * (size + gap), 0, size, size), col)
        p.setPen(QColor(self._P.text_muted))
        p.setFont(QFont("monospace", 8))
        if self._series:
            first = dt.date.fromisoformat(self._series[0]["d"]).strftime("%d %b")
            p.drawText(QRectF(0, size + 4, 80, 16), Qt.AlignmentFlag.AlignLeft, first)
            p.drawText(
                QRectF(self.width() - 80, size + 4, 80, 16), Qt.AlignmentFlag.AlignRight, "today"
            )


# ---------- Bar chart --------------------------------------------------------


class _Bars(QWidget):
    """Focus (solid) and break (muted) minutes for the last 7 days."""

    def __init__(self, series: list[dict], palette: Palette, parent=None):
        super().__init__(parent)
        self._series = series[-7:]
        self._P = palette
        self.setMinimumHeight(140)

    def paintEvent(self, _):
        p = QPainter(self)
        ink, muted, label = (
            QColor(c) for c in (self._P.text, self._P.border_light, self._P.text_muted)
        )
        bw = 18
        chart_h = self.height() - 24
        col_w = self.width() / max(1, len(self._series))
        max_total = max((d["focus_s"] + d["break_s"] for d in self._series), default=0) or 1
        p.setFont(QFont("monospace", 8))
        for i, d in enumerate(self._series):
            x = i * col_w + (col_w - bw) / 2
            f = d["focus_s"] / max_total * chart_h
            b = d["break_s"] / max_total * chart_h
            p.fillRect(QRectF(x, chart_h - f, bw, f), ink)
            p.fillRect(QRectF(x, chart_h - f - b, bw, b), muted)
            day = dt.date.fromisoformat(d["d"])
            p.setPen(label)
            p.drawText(
                QRectF(x - 6, chart_h + 4, bw + 12, 18),
                Qt.AlignmentFlag.AlignHCenter,
                "MTWTFSS"[day.weekday()],  # date.weekday(): Monday == 0
            )


# ---------- Histogram --------------------------------------------------------


class _Histogram(QWidget):
    BUCKETS: ClassVar[list[str]] = ["5–15 min", "15–25 min", "25–35 min", "35–45 min", "45+ min"]

    def __init__(self, hist: list[tuple[str, int]], palette: Palette, parent=None):
        super().__init__(parent)
        self._P = palette
        m = dict(hist)
        self._values = [(b, m.get(b, 0)) for b in self.BUCKETS]
        self.setMinimumHeight(len(self.BUCKETS) * 22 + 8)

    def paintEvent(self, _):
        p = QPainter(self)
        ink, track, text = (QColor(c) for c in (self._P.text, self._P.border, self._P.text_muted))
        labw, valw, rowh = 80, 36, 22
        max_v = max(v for _, v in self._values) or 1
        p.setFont(QFont("monospace", 9))
        for i, (label, v) in enumerate(self._values):
            y = i * rowh + 4
            p.setPen(text)
            p.drawText(QRectF(0, y, labw, rowh), Qt.AlignmentFlag.AlignVCenter, label)
            barx = labw + 8
            barw = self.width() - labw - valw - 16
            p.fillRect(QRectF(barx, y + 8, barw, 6), track)
            p.fillRect(QRectF(barx, y + 8, barw * (v / max_v), 6), ink)
            p.setPen(ink)
            p.drawText(
                QRectF(self.width() - valw, y, valw, rowh),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                str(v),
            )


# ---------- Building blocks --------------------------------------------------


def _stat_tile(value: str, suffix: str, label: str, sub: str, P: Palette) -> QWidget:
    w = QWidget()
    L = QVBoxLayout(w)
    L.setContentsMargins(0, 12, 16, 12)
    L.setSpacing(2)
    big = QLabel(value + (f" <small>{suffix}</small>" if suffix else ""))
    big.setTextFormat(Qt.TextFormat.RichText)
    big.setStyleSheet(f"font-family:{FONT_FAMILY};font-size:28px;color:{P.text};")
    k = QLabel(label.upper())
    k.setStyleSheet(f"font-size:10px;letter-spacing:2px;color:{P.text_secondary};margin-top:6px;")
    s = QLabel(sub)
    s.setStyleSheet(f"font-family:{MONO_FONT};font-size:10px;color:{P.text_muted};")
    for x in (big, k, s):
        L.addWidget(x)
    return w


def _section(title: str, sub: str, P: Palette) -> QWidget:
    w = QWidget()
    L = QHBoxLayout(w)
    L.setContentsMargins(0, 18, 0, 8)
    a = QLabel(title.upper())
    a.setStyleSheet(f"font-size:10px;letter-spacing:2.5px;color:{P.text_secondary};")
    b = QLabel(sub)
    b.setStyleSheet(f"font-family:{MONO_FONT};font-size:10px;color:{P.text_muted};")
    L.addWidget(a)
    L.addStretch(1)
    L.addWidget(b)
    return w


def _rule() -> QFrame:
    f = QFrame()
    f.setProperty("role", "rule")
    return f


def _fmt_hm(seconds: int) -> tuple[str, str]:
    minutes = seconds // 60
    return f"{minutes // 60}", f"h {minutes % 60}m"


# ---------- Dialog -----------------------------------------------------------


class AnalyticsDialog(QDialog):
    def __init__(self, store: Store, parent=None, palette: Palette = DARK):
        super().__init__(parent)
        self.store = store
        self.setWindowTitle("Akshara — Reading analytics")
        self.resize(700, 780)
        P = palette
        self.setStyleSheet(
            f"""
            QDialog {{ background:{P.bg}; }}
            QFrame[role="rule"] {{ background:{P.border}; max-height:1px; min-height:1px; border:none; }}
            """
        )

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        body = QWidget()
        scroll.setWidget(body)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        L = QVBoxLayout(body)
        L.setContentsMargins(28, 24, 28, 24)
        L.setSpacing(0)

        h = QLabel("Time, in depth")
        h.setStyleSheet(f"font-family:{FONT_FAMILY};font-size:26px;color:{P.text};")
        L.addWidget(h)
        sub = QLabel(f"LAST {DAYS} DAYS · LOCAL DATABASE")
        sub.setStyleSheet(
            f"font-size:10px;letter-spacing:2.5px;color:{P.text_muted};margin-bottom:12px;"
        )
        L.addWidget(sub)

        s = store.summary(DAYS)
        series = store.daily_series(DAYS)
        comp_pct = round(s["done"] / s["n"] * 100) if s["n"] else 0
        streak, best = store.streak_days(), store.best_streak_days()

        grid = QGridLayout()
        grid.setSpacing(0)
        hrs, rest = _fmt_hm(s["total_s"])
        tiles = [
            _stat_tile(hrs, rest, "Focused reading", f"{s['n']} sessions", P),
            _stat_tile(
                f"{s['avg_s'] // 60}", "min avg", "Per session", f"completion {comp_pct}%", P
            ),
            _stat_tile(f"{streak}", "days", "Current streak", f"best: {best}d", P),
            _stat_tile(f"{s['pages']}", "pages", "Pages read", "during focus sessions", P),
            _stat_tile(f"{s['words']:,}", "words", "Heard aloud", "via text-to-speech", P),
            _stat_tile(f"{len(store.list_documents())}", "books", "In library", "all time", P),
        ]
        for i, t in enumerate(tiles):
            grid.addWidget(t, i // 3, i % 3)
        L.addLayout(grid)
        L.addWidget(_rule())

        L.addWidget(_section("Activity heatmap", f"{DAYS} days", P))
        L.addWidget(_Heatmap(series, P))
        L.addWidget(_section("Last 7 days", "focus / break", P))
        L.addWidget(_Bars(series, P))
        L.addWidget(_section("Session length distribution", f"n = {s['n']}", P))
        L.addWidget(_Histogram(store.session_length_histogram(DAYS), P))

        L.addWidget(_section("Time per document", "all-time", P))
        docs = [d for d in store.per_document_time() if d["total_s"] > 0]
        if not docs:
            none = QLabel(
                "No focus sessions linked to a book yet — start the Pomodoro timer while reading."
            )
            none.setObjectName("muted")
            none.setWordWrap(True)
            L.addWidget(none)
        for doc in docs:
            row = QWidget()
            R = QHBoxLayout(row)
            R.setContentsMargins(0, 8, 0, 8)
            col = QVBoxLayout()
            name = QLabel(doc["title"])
            name.setStyleSheet(f"font-family:{FONT_FAMILY};font-size:13px;color:{P.text};")
            meta = QLabel(f"{doc['author'] or '—'} · {doc['session_n']} sessions")
            meta.setStyleSheet(f"font-family:{MONO_FONT};font-size:10px;color:{P.text_muted};")
            col.addWidget(name)
            col.addWidget(meta)
            R.addLayout(col, 1)
            num = QLabel(f"{doc['total_s'] / 3600:.1f}<small> HOURS</small>")
            num.setTextFormat(Qt.TextFormat.RichText)
            num.setStyleSheet(f"font-family:{FONT_FAMILY};font-size:16px;color:{P.text};")
            R.addWidget(num)
            L.addWidget(row)
            L.addWidget(_rule())

        L.addSpacing(16)
        foot = QHBoxLayout()
        info = QLabel(f"akshara.db · {store.file_size() // 1024} KB · {store.path}")
        info.setStyleSheet(f"font-family:{MONO_FONT};font-size:10px;color:{P.text_muted};")
        info.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        export = QPushButton("Export CSV…")
        export.setAutoDefault(False)
        export.clicked.connect(self._export)
        close = QPushButton("Close")
        close.setObjectName("accentButton")
        close.clicked.connect(self.accept)
        foot.addWidget(info, 1)
        foot.addWidget(export)
        foot.addWidget(close)
        L.addLayout(foot)

    def _export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Export sessions", "akshara-sessions.csv", "CSV files (*.csv)"
        )
        if path:
            n = self.store.export_sessions_csv(path)
            QMessageBox.information(self, "Exported", f"Wrote {n} sessions to {path}")
