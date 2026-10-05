"""Welcome screen shown when no document is open."""

from __future__ import annotations

import os

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from .ui.theme import DARK, FONT_FAMILY, MONO_FONT, Palette

SHORTCUTS = [
    ("Ctrl+O", "Open a PDF"),
    ("Space", "Play / pause reading"),
    ("Ctrl+F", "Find in document"),
    ("Ctrl+B", "Bookmark page"),
    ("F9", "Sidebar"),
    ("Ctrl+,", "Preferences"),
    ("F1", "All shortcuts"),
]


class WelcomeWidget(QWidget):
    open_requested = pyqtSignal()
    open_path = pyqtSignal(str)

    def __init__(self, palette: Palette = DARK, parent=None):
        super().__init__(parent)
        self.setObjectName("welcomeWidget")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._palette = palette
        self._recent: list[str] = []

        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.setSpacing(0)

        self.title = QLabel("AKSHARA")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(self.title)
        outer.addSpacing(8)
        self.subtitle = QLabel("PDF · FOCUS · ANALYTICS")
        self.subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(self.subtitle)
        outer.addSpacing(32)

        self.open_button = QPushButton("Open PDF")
        self.open_button.setObjectName("accentButton")
        self.open_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_button.setFixedWidth(200)
        self.open_button.clicked.connect(self.open_requested)
        outer.addWidget(self.open_button, alignment=Qt.AlignmentFlag.AlignCenter)
        outer.addSpacing(10)
        self.hint = QLabel("or drop a PDF onto this window")
        self.hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(self.hint)
        outer.addSpacing(28)

        self.recent_box = QWidget()
        self.recent_box.setFixedWidth(380)
        self._recent_layout = QVBoxLayout(self.recent_box)
        self._recent_layout.setContentsMargins(0, 0, 0, 0)
        self._recent_layout.setSpacing(2)
        outer.addWidget(self.recent_box, alignment=Qt.AlignmentFlag.AlignCenter)
        outer.addSpacing(24)

        self.shortcuts = QWidget()
        self.shortcuts.setObjectName("shortcutCard")
        self.shortcuts.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.shortcuts.setFixedWidth(380)
        sc = QVBoxLayout(self.shortcuts)
        sc.setContentsMargins(20, 14, 20, 14)
        sc.setSpacing(5)
        self._sc_labels: list[QLabel] = []
        for key, desc in SHORTCUTS:
            row = QHBoxLayout()
            k, d = QLabel(key), QLabel(desc)
            row.addWidget(k)
            row.addStretch(1)
            row.addWidget(d)
            sc.addLayout(row)
            self._sc_labels += [k, d]
        outer.addWidget(self.shortcuts, alignment=Qt.AlignmentFlag.AlignCenter)
        self._apply()

    def set_palette(self, palette: Palette) -> None:
        self._palette = palette
        self._apply()

    def set_recent(self, paths: list[str]) -> None:
        self._recent = [p for p in paths if os.path.isfile(p)][:5]
        while self._recent_layout.count():
            item = self._recent_layout.takeAt(0)
            if item is not None and (w := item.widget()) is not None:
                w.deleteLater()
        if self._recent:
            head = QLabel("RECENT")
            head.setObjectName("sectionLabel")
            self._recent_layout.addWidget(head)
        for path in self._recent:
            b = QPushButton(os.path.basename(path))
            b.setToolTip(path)
            b.setObjectName("recentButton")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, p=path: self.open_path.emit(p))
            self._recent_layout.addWidget(b)
        self.recent_box.setVisible(bool(self._recent))
        self._apply()

    def _apply(self) -> None:
        P = self._palette
        self.setStyleSheet(
            f"""
            QWidget#welcomeWidget {{ background:{P.bg}; }}
            QWidget#shortcutCard {{ background:{P.bg_elevated}; border-radius:8px; }}
            QPushButton#recentButton {{
                text-align:left; border:none; padding:6px 8px; color:{P.text_secondary};
            }}
            QPushButton#recentButton:hover {{ background:{P.bg_hover}; color:{P.text}; }}
            """
        )
        self.title.setStyleSheet(
            f"font-family:{FONT_FAMILY};font-size:44px;font-weight:300;letter-spacing:10px;color:{P.text};"
        )
        self.subtitle.setStyleSheet(f"font-size:11px;letter-spacing:3.5px;color:{P.text_muted};")
        self.hint.setStyleSheet(f"font-family:{MONO_FONT};font-size:11px;color:{P.text_muted};")
        for lab in self._sc_labels:
            lab.setStyleSheet(f"font-family:{MONO_FONT};font-size:11px;color:{P.text_secondary};")
