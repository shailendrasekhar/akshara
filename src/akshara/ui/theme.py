"""
Theme tokens and the application stylesheet.

Every colour in the UI comes from a :class:`Palette`; widgets never hardcode
hex values. Three palettes ship: dark, light and sepia. The active palette is
chosen from the user's theme setting (explicit, follow-system, or by time of
day).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

FONT_FAMILY = "'Georgia', 'Times New Roman', serif"
MONO_FONT = "'Ubuntu Mono', 'DejaVu Sans Mono', 'Courier New', monospace"


@dataclass(frozen=True)
class Palette:
    name: str
    is_dark: bool

    bg: str
    bg_secondary: str
    bg_elevated: str
    bg_hover: str
    bg_card: str

    text: str
    text_secondary: str
    text_muted: str

    border: str
    border_light: str

    accent: str
    accent_hover: str
    accent_text: str  # text drawn on top of the accent colour

    success: str
    error: str

    tts_fill: str  # rgba() — sentence being read aloud
    tts_stroke: str
    selection: str  # rgba()
    search_hit: str  # rgba()
    search_current: str  # rgba()

    # Page rendering: how black/white map onto the page in "match theme" mode.
    page_ink: int  # 0xRRGGBB
    page_paper: int


ACCENT = "#d8a85a"
ACCENT_HOVER = "#e8bb6a"

DARK = Palette(
    name="dark",
    is_dark=True,
    bg="#000000",
    bg_secondary="#0a0a0a",
    bg_elevated="#111111",
    bg_hover="#181818",
    bg_card="#0d0d0d",
    text="#f0f0f0",
    text_secondary="#a0a0a0",
    text_muted="#5c5c5c",
    border="#1e1e1e",
    border_light="#2a2a2a",
    accent=ACCENT,
    accent_hover=ACCENT_HOVER,
    accent_text="#000000",
    success="#3ecf8e",
    error="#f06060",
    tts_fill="rgba(250, 204, 21, 110)",
    tts_stroke="rgba(234, 179, 8, 220)",
    selection="rgba(99, 102, 241, 110)",
    search_hit="rgba(56, 189, 248, 90)",
    search_current="rgba(249, 115, 22, 150)",
    page_ink=0xE6E6E6,
    page_paper=0x0B0B0B,
)

LIGHT = Palette(
    name="light",
    is_dark=False,
    bg="#ffffff",
    bg_secondary="#fafaf8",
    bg_elevated="#f2f2ef",
    bg_hover="#eaeae6",
    bg_card="#f7f7f5",
    text="#0a0a0a",
    text_secondary="#5a5a5a",
    text_muted="#9a9a9a",
    border="#e4e4e0",
    border_light="#d0d0cc",
    accent=ACCENT,
    accent_hover=ACCENT_HOVER,
    accent_text="#000000",
    success="#1a8c5a",
    error="#cc3333",
    tts_fill="rgba(250, 204, 21, 130)",
    tts_stroke="rgba(202, 138, 4, 220)",
    selection="rgba(99, 102, 241, 80)",
    search_hit="rgba(14, 165, 233, 70)",
    search_current="rgba(249, 115, 22, 130)",
    page_ink=0x000000,
    page_paper=0xFFFFFF,
)

SEPIA = Palette(
    name="sepia",
    is_dark=False,
    bg="#f4ecd8",
    bg_secondary="#efe5cc",
    bg_elevated="#ebe0c4",
    bg_hover="#e4d7b7",
    bg_card="#f0e6cf",
    text="#3b2f20",
    text_secondary="#6b5a43",
    text_muted="#a08d70",
    border="#e0d2b0",
    border_light="#cdbb93",
    accent="#b5793a",
    accent_hover="#c98c4c",
    accent_text="#fffaf0",
    success="#4f7a3a",
    error="#a83b2b",
    tts_fill="rgba(214, 158, 46, 120)",
    tts_stroke="rgba(160, 110, 20, 220)",
    selection="rgba(120, 90, 200, 70)",
    search_hit="rgba(14, 140, 200, 60)",
    search_current="rgba(220, 100, 20, 120)",
    page_ink=0x3B2F20,
    page_paper=0xF4ECD8,
)

PALETTES: dict[str, Palette] = {p.name: p for p in (DARK, LIGHT, SEPIA)}

THEME_MODES = {
    "system": "Follow system",
    "time": "By time of day (light 6:00–18:00)",
    "light": "Light",
    "dark": "Dark",
    "sepia": "Sepia",
}


def resolve_palette(mode: str, now: dt.datetime | None = None) -> Palette:
    """Map a theme mode setting to a concrete palette."""
    if mode in PALETTES:
        return PALETTES[mode]
    if mode == "system":
        scheme = _system_scheme()
        if scheme is not None:
            return DARK if scheme else LIGHT
    hour = (now or dt.datetime.now()).hour
    return LIGHT if 6 <= hour < 18 else DARK


def _system_scheme() -> bool | None:
    """True if the desktop prefers dark, False if light, None if unknown."""
    try:
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QGuiApplication

        hints = QGuiApplication.styleHints()
        if hints is None:
            return None
        scheme = hints.colorScheme()
        if scheme == Qt.ColorScheme.Dark:
            return True
        if scheme == Qt.ColorScheme.Light:
            return False
    except Exception:
        pass
    return None


# ---------- Text sizes -------------------------------------------------------

# (label, application font pt, stylesheet base px)
TEXT_SIZES: list[tuple[str, int, int]] = [("S", 10, 13), ("M", 12, 15), ("L", 14, 17)]


# ---------- Stylesheet -------------------------------------------------------


def stylesheet(C: Palette, base_px: int = 15) -> str:
    sm = max(base_px - 2, 9)
    md = base_px
    return f"""
    * {{ font-family: {FONT_FAMILY}; outline: none; }}

    QWidget {{ background-color: transparent; color: {C.text}; font-size: {md}px; }}
    /* After the QWidget rule: equal specificity, so order decides. */
    QMainWindow, QDialog, QMessageBox, QInputDialog {{ background-color: {C.bg}; }}

    /* ----- Toolbar ----- */
    QToolBar {{
        background-color: {C.bg}; border: none; border-bottom: 1px solid {C.border};
        padding: 6px 12px; spacing: 6px;
    }}
    QToolBar::separator {{ background-color: {C.border}; width: 1px; margin: 6px 8px; }}

    QToolButton {{
        background-color: transparent; color: {C.text};
        border: 1px solid {C.border}; border-radius: 5px;
        padding: 5px 11px; font-size: {md}px;
    }}
    QToolButton:hover {{ background-color: {C.bg_hover}; border-color: {C.border_light}; }}
    QToolButton:pressed, QToolButton:checked {{ background-color: {C.bg_elevated}; }}
    QToolButton:disabled {{ color: {C.text_muted}; border-color: {C.border}; }}
    QToolButton::menu-indicator {{ image: none; width: 0; }}

    QToolButton#accentButton {{
        background-color: {C.accent}; color: {C.accent_text}; border: none; font-weight: 600;
    }}
    QToolButton#accentButton:hover {{ background-color: {C.accent_hover}; }}
    QToolButton#accentButton:disabled {{ background-color: {C.border}; color: {C.text_muted}; }}
    QToolButton#stopButton:enabled {{ color: {C.error}; border-color: {C.error}; }}
    QToolButton#stopButton:enabled:hover {{ background-color: {C.error}; color: {C.bg}; }}
    QToolButton#flatButton {{ border: none; padding: 5px 8px; }}
    QToolButton#flatButton:hover {{ background-color: {C.bg_hover}; }}
    QToolButton#flatButton:checked {{ color: {C.accent}; }}

    /* ----- Buttons ----- */
    QPushButton {{
        background-color: transparent; color: {C.text};
        border: 1px solid {C.border}; border-radius: 5px; padding: 7px 16px;
    }}
    QPushButton:hover {{ background-color: {C.bg_hover}; border-color: {C.border_light}; }}
    QPushButton:checked {{ background-color: {C.accent}; color: {C.accent_text}; border-color: {C.accent}; }}
    QPushButton:disabled {{ color: {C.text_muted}; border-color: {C.border}; }}
    QPushButton#accentButton, QPushButton:default {{
        background-color: {C.accent}; color: {C.accent_text}; border: none; font-weight: 600;
    }}
    QPushButton#accentButton:hover, QPushButton:default:hover {{ background-color: {C.accent_hover}; }}

    /* ----- Inputs ----- */
    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
        background-color: {C.bg_elevated}; color: {C.text};
        border: 1px solid {C.border}; border-radius: 4px; padding: 4px 8px;
        selection-background-color: {C.accent}; selection-color: {C.accent_text};
    }}
    QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{ border-color: {C.accent}; }}
    QSpinBox, QDoubleSpinBox {{ font-family: {MONO_FONT}; }}
    QSpinBox::up-button, QSpinBox::down-button,
    QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{ background: transparent; border: none; width: 14px; }}
    QComboBox::drop-down {{ border: none; width: 18px; }}
    QComboBox QAbstractItemView {{
        background-color: {C.bg_elevated}; border: 1px solid {C.border_light};
        selection-background-color: {C.accent}; selection-color: {C.accent_text};
    }}
    QCheckBox, QRadioButton {{ spacing: 8px; }}
    QCheckBox::indicator, QRadioButton::indicator {{
        width: 14px; height: 14px; border: 1px solid {C.border_light}; background: {C.bg_elevated};
    }}
    QCheckBox::indicator {{ border-radius: 3px; }}
    QRadioButton::indicator {{ border-radius: 7px; }}
    QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
        background: {C.accent}; border-color: {C.accent};
    }}
    QGroupBox {{
        border: 1px solid {C.border}; border-radius: 6px; margin-top: 14px; padding: 12px 10px 8px 10px;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin; left: 10px; padding: 0 4px; color: {C.text_secondary};
        letter-spacing: 1.5px; font-size: {sm}px;
    }}

    /* ----- Sliders ----- */
    QSlider::groove:horizontal {{ border: none; height: 2px; background: {C.border}; border-radius: 1px; }}
    QSlider::handle:horizontal {{
        background: {C.accent}; width: 11px; height: 11px; margin: -5px 0; border-radius: 6px;
    }}
    QSlider::handle:horizontal:hover {{ background: {C.accent_hover}; }}
    QSlider::sub-page:horizontal {{ background: {C.accent}; border-radius: 1px; }}

    /* ----- Labels ----- */
    QLabel {{ color: {C.text}; background: transparent; }}
    QLabel#muted {{ color: {C.text_muted}; }}
    QLabel#secondary {{ color: {C.text_secondary}; }}
    QLabel#mono {{ color: {C.text_secondary}; font-family: {MONO_FONT}; font-size: {sm}px; }}
    QLabel#heading {{ font-size: {md + 3}px; letter-spacing: 1px; }}
    QLabel#sectionLabel {{ color: {C.text_muted}; font-size: {sm - 1}px; letter-spacing: 2.5px; }}

    /* ----- Lists, trees, tabs ----- */
    QListView, QTreeView, QListWidget, QTreeWidget {{
        background-color: {C.bg}; border: none; padding: 4px;
    }}
    QListView::item, QTreeView::item {{ padding: 5px 6px; border-radius: 4px; }}
    QListView::item:hover, QTreeView::item:hover {{ background-color: {C.bg_hover}; }}
    QListView::item:selected, QTreeView::item:selected {{
        background-color: {C.bg_elevated}; color: {C.accent};
    }}
    QTreeView::branch {{ background: transparent; }}
    QHeaderView::section {{ background: {C.bg}; color: {C.text_muted}; border: none; padding: 4px; }}

    QMainWindow::separator {{ background: {C.border}; width: 1px; height: 1px; }}
    QMainWindow::separator:hover {{ background: {C.accent}; }}
    QTreeView::branch:selected, QTreeView::branch:hover {{ background: transparent; }}
    QTabBar QToolButton {{ background: {C.bg}; border: none; padding: 0 2px; }}

    QTabWidget::pane {{ border: none; border-top: 1px solid {C.border}; }}
    QTabBar {{ background: {C.bg}; qproperty-drawBase: 0; }}
    QTabBar::tab {{
        background: transparent; color: {C.text_muted}; padding: 7px 6px;
        border: none; border-bottom: 2px solid transparent;
        font-size: {sm}px; letter-spacing: 1.5px;
    }}
    QTabBar::tab:hover {{ color: {C.text}; }}
    QTabBar::tab:selected {{ color: {C.text}; border-bottom-color: {C.accent}; }}

    /* ----- Docks ----- */
    QDockWidget {{ color: {C.text_muted}; titlebar-close-icon: none; titlebar-normal-icon: none; }}
    QDockWidget::title {{
        background-color: {C.bg}; border-bottom: 1px solid {C.border};
        padding: 8px 14px; text-align: left; font-size: {sm - 2}px; letter-spacing: 3px;
    }}
    QDockWidget > QWidget {{ background-color: {C.bg}; border: none; }}

    /* ----- Scrolling ----- */
    QScrollArea, QAbstractScrollArea {{ background-color: {C.bg}; border: none; }}
    QAbstractScrollArea::corner {{ background: {C.bg}; border: none; }}
    QWidget#qt_scrollarea_viewport {{ background-color: {C.bg}; }}
    QScrollBar:vertical {{ background: {C.bg}; width: 8px; margin: 0; }}
    QScrollBar::handle:vertical {{ background: {C.border_light}; border-radius: 4px; min-height: 36px; }}
    QScrollBar::handle:vertical:hover {{ background: {C.text_muted}; }}
    QScrollBar:horizontal {{ background: {C.bg}; height: 8px; }}
    QScrollBar::handle:horizontal {{ background: {C.border_light}; border-radius: 4px; min-width: 36px; }}
    QScrollBar::handle:horizontal:hover {{ background: {C.text_muted}; }}
    QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{
        background: transparent; height: 0; width: 0;
    }}

    /* ----- Status, menus, tooltips ----- */
    QStatusBar {{
        background-color: {C.bg}; border-top: 1px solid {C.border}; color: {C.text_secondary};
        font-size: {sm}px; font-family: {MONO_FONT};
    }}
    QStatusBar QLabel {{ color: {C.text_secondary}; padding: 0 8px; }}
    QStatusBar::item {{ border: none; }}

    QMenuBar {{ background-color: {C.bg}; color: {C.text}; border-bottom: 1px solid {C.border}; padding: 2px 6px; }}
    QMenuBar::item {{ padding: 5px 10px; border-radius: 3px; }}
    QMenuBar::item:selected {{ background-color: {C.bg_hover}; }}
    QMenu {{ background-color: {C.bg_elevated}; border: 1px solid {C.border_light}; padding: 4px; border-radius: 6px; }}
    QMenu::item {{ padding: 6px 22px; border-radius: 3px; }}
    QMenu::item:selected {{ background-color: {C.accent}; color: {C.accent_text}; }}
    QMenu::item:disabled {{ color: {C.text_muted}; }}
    QMenu::separator {{ height: 1px; background: {C.border}; margin: 4px 8px; }}

    QToolTip {{
        background-color: {C.bg_elevated}; color: {C.text}; border: 1px solid {C.border_light};
        padding: 5px 9px; border-radius: 4px;
    }}

    /* ----- Find bar ----- */
    QWidget#findBar {{ background-color: {C.bg_secondary}; border-bottom: 1px solid {C.border}; }}
    QLabel#findStatus {{ color: {C.text_muted}; font-family: {MONO_FONT}; font-size: {sm}px; }}
    """


def qcolor(css: str):
    """QColor from '#rrggbb' or 'rgba(r, g, b, a)' (a in 0–255)."""
    from PyQt6.QtGui import QColor

    css = css.strip()
    if css.startswith("rgba(") and css.endswith(")"):
        r, g, b, a = (int(float(x)) for x in css[5:-1].split(","))
        return QColor(r, g, b, a)
    return QColor(css)


def page_colors_for(palette: Palette, mode: str):
    """PageColors for the viewer given the 'page_colors' setting (match | original)."""
    from ..render import PageColors

    if mode != "match":
        return None
    colors = PageColors(palette.page_ink, palette.page_paper)
    return None if colors.is_identity else colors
