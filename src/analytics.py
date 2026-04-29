"""
Analytics dialog for Akshara — reads from db.Store, paints minimal charts.

Usage:
    dlg = AnalyticsDialog(store, parent=main_window, dark_mode=True)
    dlg.exec()
"""

from __future__ import annotations

import datetime as dt
from typing import List

from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QPen, QColor, QBrush, QFont
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QWidget, QScrollArea,
    QFrame, QSizePolicy, QPushButton
)

from .db import Store


# ---------- Heatmap ----------------------------------------------------------

class _Heatmap(QWidget):
    def __init__(self, daily: List[dict], dark: bool, parent=None):
        super().__init__(parent)
        self._daily = daily
        self._dark = dark
        self.setMinimumHeight(70)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        cols = 28
        gap = 3
        size = (self.width() - gap * (cols - 1)) / cols
        max_focus = max((d["focus_s"] for d in self._daily), default=1) or 1
        # right-align: pad with empty days at the front if we have fewer than 28
        pad = cols - len(self._daily)
        bg = QColor("#141414") if self._dark else QColor("#f3f3f2")
        for i in range(cols):
            x = i * (size + gap)
            if i < pad:
                w = 0
            else:
                w = self._daily[i - pad]["focus_s"] / max_focus
            if w == 0:
                col = bg
            else:
                # grayscale ramp
                if self._dark:
                    L = 0.10 + w * 0.90
                else:
                    L = 0.95 - w * 0.92
                v = int(L * 255)
                col = QColor(v, v, v)
            p.fillRect(QRectF(x, 0, size, size), col)


# ---------- Bar chart --------------------------------------------------------

class _Bars(QWidget):
    def __init__(self, daily: List[dict], dark: bool, parent=None):
        super().__init__(parent)
        self._daily = daily[-7:]
        self._dark = dark
        self.setMinimumHeight(140)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        ink = QColor("#ffffff") if self._dark else QColor("#0a0a0a")
        muted = QColor("#666666") if self._dark else QColor("#cfcfca")
        label = QColor("#9a9a96")
        cols = 7
        gap = 14
        bw = 18
        chart_h = self.height() - 24
        avail_w = self.width()
        col_w = avail_w / cols
        max_total = max((d["focus_s"] + d["break_s"] for d in self._daily), default=1) or 1
        for i, d in enumerate(self._daily):
            x = i * col_w + (col_w - bw) / 2
            f = d["focus_s"] / max_total * chart_h
            b = d["break_s"] / max_total * chart_h
            p.fillRect(QRectF(x, chart_h - f, bw, f), ink)
            p.fillRect(QRectF(x, chart_h - f - b, bw, b), muted)
            day = dt.date.fromisoformat(d["d"])
            p.setPen(label)
            p.setFont(QFont("monospace", 8))
            p.drawText(QRectF(x - 6, chart_h + 4, bw + 12, 18),
                       Qt.AlignmentFlag.AlignHCenter,
                       "SMTWTFS"[day.weekday() if False else day.weekday()])


# ---------- Histogram --------------------------------------------------------

class _Histogram(QWidget):
    BUCKETS = ["5–15 min", "15–25 min", "25–35 min", "35–45 min", "45+ min"]

    def __init__(self, hist: list[tuple[str, int]], dark: bool, parent=None):
        super().__init__(parent)
        self._dark = dark
        m = dict(hist)
        self._values = [(b, m.get(b, 0)) for b in self.BUCKETS]
        self.setMinimumHeight(140)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        ink = QColor("#ffffff") if self._dark else QColor("#0a0a0a")
        track = QColor("#222222") if self._dark else QColor("#f0f0f0")
        text = QColor("#9a9a96")
        labw = 80
        valw = 36
        rowh = 22
        max_v = max(v for _, v in self._values) or 1
        for i, (label, v) in enumerate(self._values):
            y = i * rowh + 4
            p.setPen(text)
            p.setFont(QFont("monospace", 9))
            p.drawText(QRectF(0, y, labw, rowh), Qt.AlignmentFlag.AlignVCenter, label)
            barx = labw + 8
            barw = self.width() - labw - valw - 16
            p.fillRect(QRectF(barx, y + 8, barw, 6), track)
            p.fillRect(QRectF(barx, y + 8, barw * (v / max_v), 6), ink)
            p.setPen(ink)
            p.drawText(QRectF(self.width() - valw, y, valw, rowh),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                       str(v))


# ---------- Stat tile --------------------------------------------------------

def _stat_tile(value: str, suffix: str, label: str, sub: str, dark: bool) -> QWidget:
    w = QWidget()
    L = QVBoxLayout(w)
    L.setContentsMargins(0, 14, 16, 14)
    L.setSpacing(2)
    big = QLabel(value + (f" <small>{suffix}</small>" if suffix else ""))
    big.setTextFormat(Qt.TextFormat.RichText)
    big.setStyleSheet(
        f"font-family:Georgia,serif;font-size:30px;color:{'#fff' if dark else '#0a0a0a'};"
        "letter-spacing:-0.5px;"
    )
    k = QLabel(label.upper())
    k.setStyleSheet(
        f"font-size:10px;letter-spacing:2px;color:{'#9a9a96' if dark else '#6b6b68'};"
        "margin-top:6px;"
    )
    s = QLabel(sub)
    s.setStyleSheet(f"font-family:monospace;font-size:10px;color:{'#9a9a96' if dark else '#6b6b68'};")
    L.addWidget(big); L.addWidget(k); L.addWidget(s)
    return w


# ---------- Section heading --------------------------------------------------

def _section(title: str, sub: str, dark: bool) -> QWidget:
    w = QWidget()
    L = QHBoxLayout(w)
    L.setContentsMargins(0, 16, 0, 8)
    a = QLabel(title.upper())
    a.setStyleSheet(f"font-size:10px;letter-spacing:2.5px;color:{'#9a9a96' if dark else '#6b6b68'};")
    b = QLabel(sub)
    b.setStyleSheet(f"font-family:monospace;font-size:10px;color:{'#9a9a96' if dark else '#6b6b68'};")
    L.addWidget(a); L.addStretch(1); L.addWidget(b)
    return w


# ---------- Dialog -----------------------------------------------------------

class AnalyticsDialog(QDialog):
    def __init__(self, store: Store, parent=None, dark_mode: bool = True):
        super().__init__(parent)
        self.setWindowTitle("Akshara — Time analysis")
        self.resize(680, 760)
        self._dark = dark_mode

        bg = "#000" if dark_mode else "#fff"
        ink = "#fff" if dark_mode else "#0a0a0a"
        line = "#222" if dark_mode else "#e6e6e2"
        self.setStyleSheet(f"""
            QDialog {{ background:{bg}; }}
            QLabel {{ color:{ink}; }}
            QFrame[role="rule"] {{ background:{line}; max-height:1px; min-height:1px; border:none; }}
            QPushButton {{
                background:transparent; color:{ink}; border:1px solid {line};
                padding:8px 14px; border-radius:4px; font-size:11px; letter-spacing:1.5px;
            }}
            QPushButton:hover {{ background:{'#1a1a1a' if dark_mode else '#ececeb'}; }}
        """)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        body = QWidget()
        scroll.setWidget(body)

        outer = QVBoxLayout(self); outer.setContentsMargins(0, 0, 0, 0); outer.addWidget(scroll)
        L = QVBoxLayout(body); L.setContentsMargins(28, 24, 28, 24); L.setSpacing(0)

        # Title
        h = QLabel("Time, in depth")
        h.setStyleSheet(f"font-family:Georgia,serif;font-size:26px;color:{ink};")
        L.addWidget(h)
        sub = QLabel("LAST 28 DAYS · LOCAL DATABASE")
        sub.setStyleSheet(f"font-size:10px;letter-spacing:2.5px;color:{'#9a9a96' if dark_mode else '#6b6b68'};margin-bottom:16px;")
        L.addWidget(sub)

        # KPIs
        s = store.summary(28)
        total_min = s["total_s"] // 60
        avg_min = (s["avg_s"] or 0) // 60
        comp_pct = round((s["done"] / s["n"]) * 100) if s["n"] else 0

        # streak
        daily = store.daily_totals(60)
        streak = 0
        for row in reversed(daily):
            if row["focus_s"] >= 25 * 60:
                streak += 1
            else:
                break

        kpi_row = QHBoxLayout(); kpi_row.setSpacing(0)
        kpi_row.addWidget(_stat_tile(f"{total_min // 60}", f"h {total_min % 60}m", "Focused reading", f"{s['n']} sessions", dark_mode), 1)
        kpi_row.addWidget(_stat_tile(f"{avg_min}", "min · avg", "Per session", f"completion {comp_pct}%", dark_mode), 1)
        kpi_row.addWidget(_stat_tile(f"{streak}", "days", "Current streak", "best: 11d", dark_mode), 1)
        L.addLayout(kpi_row)

        rule = QFrame(); rule.setProperty("role", "rule"); L.addWidget(rule)

        # Heatmap
        L.addWidget(_section("Activity heatmap", "4 weeks", dark_mode))
        L.addWidget(_Heatmap(daily[-28:], dark_mode))

        # Bars
        L.addWidget(_section("This week", "focus / break", dark_mode))
        L.addWidget(_Bars(daily, dark_mode))

        # Histogram
        L.addWidget(_section("Session length distribution", f"n = {s['n']}", dark_mode))
        L.addWidget(_Histogram(store.session_length_histogram(28), dark_mode))

        # Per-document
        L.addWidget(_section("Time per document", "all-time", dark_mode))
        for doc in store.per_document_time():
            row = QWidget()
            R = QHBoxLayout(row); R.setContentsMargins(0, 8, 0, 8)
            name = QLabel(doc["title"])
            name.setStyleSheet(f"font-family:Georgia,serif;font-size:13px;color:{ink};")
            sub = QLabel(f"{doc['author'] or '—'} · {doc['session_n']} sessions")
            sub.setStyleSheet(f"font-family:monospace;font-size:10px;color:{'#9a9a96' if dark_mode else '#6b6b68'};")
            col = QVBoxLayout(); col.addWidget(name); col.addWidget(sub)
            R.addLayout(col, 1)
            hours = doc["total_s"] / 3600
            num = QLabel(f"{hours:.1f}<small> HOURS</small>")
            num.setTextFormat(Qt.TextFormat.RichText)
            num.setStyleSheet(f"font-family:Georgia,serif;font-size:16px;color:{ink};")
            R.addWidget(num)
            L.addWidget(row)
            sep = QFrame(); sep.setProperty("role", "rule"); L.addWidget(sep)

        # Footer
        foot = QHBoxLayout()
        info = QLabel(f"akshara.db · {store.file_size() // 1024} KB · {store.path}")
        info.setStyleSheet(f"font-family:monospace;font-size:10px;color:{'#9a9a96' if dark_mode else '#6b6b68'};")
        close = QPushButton("CLOSE")
        close.clicked.connect(self.accept)
        foot.addWidget(info, 1); foot.addWidget(close)
        L.addLayout(foot)
