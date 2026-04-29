"""
UI Styles — minimalist black/white with warm-amber accent.
"""

FONT_FAMILY = "'Georgia', 'Times New Roman', serif"
MONO_FONT   = "'Ubuntu Mono', 'Courier New', monospace"

ACCENT      = "#d8a85a"   # warm amber — used in ring, progress bars, active states
ACCENT_DIM  = "#8a6530"   # dimmed amber for borders

DARK_COLORS = {
    "bg":           "#000000",
    "bg_secondary": "#0a0a0a",
    "bg_elevated":  "#111111",
    "bg_hover":     "#181818",
    "bg_card":      "#0d0d0d",

    "text":            "#f0f0f0",
    "text_secondary":  "#a0a0a0",
    "text_muted":      "#555555",

    "border":       "#1e1e1e",
    "border_light": "#2a2a2a",

    "accent":       ACCENT,
    "accent_dim":   ACCENT_DIM,

    "success":   "#3ecf8e",
    "error":     "#f06060",
    "highlight": "#ffd54f",
}

LIGHT_COLORS = {
    "bg":           "#ffffff",
    "bg_secondary": "#fafaf8",
    "bg_elevated":  "#f2f2ef",
    "bg_hover":     "#eaeae6",
    "bg_card":      "#f7f7f5",

    "text":            "#0a0a0a",
    "text_secondary":  "#5a5a5a",
    "text_muted":      "#aaaaaa",

    "border":       "#e4e4e0",
    "border_light": "#d0d0cc",

    "accent":       ACCENT,
    "accent_dim":   "#e8c880",

    "success":   "#1a8c5a",
    "error":     "#cc3333",
    "highlight": "#ffe066",
}


def get_main_stylesheet(dark_mode: bool = True, base_px: int = 15) -> str:
    C = DARK_COLORS if dark_mode else LIGHT_COLORS
    sm  = max(base_px - 2, 9)   # small  (labels, muted text)
    md  = base_px               # medium (base)
    lg  = base_px + 2           # large  (buttons, menus)

    return f"""
    /* ===== Global ===== */
    * {{
        font-family: {FONT_FAMILY};
        outline: none;
    }}

    QMainWindow, QDialog {{
        background-color: {C["bg"]};
    }}

    QWidget {{
        background-color: transparent;
        color: {C["text"]};
        font-size: {md}px;
    }}

    /* ===== Toolbar ===== */
    QToolBar {{
        background-color: {C["bg"]};
        border: none;
        border-bottom: 1px solid {C["border"]};
        padding: 8px 14px;
        spacing: 6px;
    }}

    QToolBar::separator {{
        background-color: {C["border"]};
        width: 1px;
        margin: 6px 10px;
    }}

    /* ===== Tool buttons ===== */
    QToolButton {{
        background-color: transparent;
        color: {C["text"]};
        border: 1px solid {C["border"]};
        border-radius: 5px;
        padding: 6px 12px;
        font-size: {md}px;
        letter-spacing: 0.3px;
    }}

    QToolButton:hover {{
        background-color: {C["bg_hover"]};
        border-color: {C["border_light"]};
    }}

    QToolButton:pressed {{
        background-color: {C["bg_elevated"]};
    }}

    QToolButton:disabled {{
        color: {C["text_muted"]};
        border-color: {C["border"]};
    }}

    QToolButton#playButton {{
        background-color: {C["accent"]};
        color: #000000;
        border: none;
        font-weight: 600;
        padding: 7px 16px;
        border-radius: 5px;
        letter-spacing: 0.5px;
    }}

    QToolButton#playButton:hover {{
        background-color: #e8bb6a;
    }}

    QToolButton#playButton:disabled {{
        background-color: {C["border"]};
        color: {C["text_muted"]};
    }}

    QToolButton#stopButton {{
        color: {C["error"]};
        border-color: {C["error"]};
    }}

    QToolButton#stopButton:hover {{
        background-color: {C["error"]};
        color: {C["bg"]};
    }}

    QToolButton#themeButton {{
        border: none;
        font-size: 17px;
        padding: 5px 8px;
        border-radius: 5px;
    }}

    QToolButton#themeButton:hover {{
        background-color: {C["bg_hover"]};
    }}

    QToolButton#zoomButton {{
        padding: 5px 9px;
        min-width: 26px;
        font-size: 14px;
        font-weight: 600;
    }}

    /* ===== Push buttons ===== */
    QPushButton {{
        background-color: transparent;
        color: {C["text"]};
        border: 1px solid {C["border"]};
        border-radius: 5px;
        padding: 8px 18px;
        font-size: {md}px;
        letter-spacing: 0.3px;
    }}

    QPushButton:hover {{
        background-color: {C["bg_hover"]};
        border-color: {C["border_light"]};
    }}

    QPushButton:checked {{
        background-color: {C["accent"]};
        color: #000000;
        border-color: {C["accent"]};
    }}

    QPushButton:disabled {{
        color: {C["text_muted"]};
        border-color: {C["border"]};
    }}

    QPushButton#playButton {{
        background-color: {C["accent"]};
        color: #000000;
        border: none;
        font-weight: 600;
        letter-spacing: 0.5px;
    }}

    QPushButton#playButton:hover {{
        background-color: #e8bb6a;
    }}

    /* ===== Dock widgets ===== */
    QDockWidget {{
        color: {C["text_secondary"]};
        font-size: 10px;
        letter-spacing: 2.5px;
        titlebar-close-icon: none;
        titlebar-normal-icon: none;
    }}

    QDockWidget::title {{
        background-color: {C["bg"]};
        border-bottom: 1px solid {C["border"]};
        padding: 8px 14px;
        text-align: left;
        font-size: 10px;
        letter-spacing: 3px;
        color: {C["text_muted"]};
    }}

    QDockWidget > QWidget {{
        background-color: {C["bg"]};
        border: none;
    }}

    /* ===== Sliders ===== */
    QSlider::groove:horizontal {{
        border: none;
        height: 2px;
        background: {C["border"]};
        border-radius: 1px;
    }}

    QSlider::handle:horizontal {{
        background: {C["accent"]};
        width: 11px;
        height: 11px;
        margin: -5px 0;
        border-radius: 6px;
    }}

    QSlider::handle:horizontal:hover {{
        background: #e8bb6a;
    }}

    QSlider::sub-page:horizontal {{
        background: {C["accent"]};
        border-radius: 1px;
    }}

    /* ===== Spin boxes ===== */
    QSpinBox {{
        background-color: {C["bg_elevated"]};
        color: {C["text"]};
        border: 1px solid {C["border"]};
        border-radius: 4px;
        padding: 4px 8px;
        min-width: 48px;
        font-family: {MONO_FONT};
        font-size: {md}px;
    }}

    QSpinBox:focus {{
        border-color: {C["accent"]};
    }}

    QSpinBox::up-button, QSpinBox::down-button {{
        background: transparent;
        border: none;
        width: 14px;
    }}

    /* ===== Labels ===== */
    QLabel {{
        color: {C["text"]};
        background: transparent;
    }}

    QLabel#speedLabel, QLabel#zoomLabel {{
        color: {C["text_secondary"]};
        font-family: {MONO_FONT};
        font-size: {sm}px;
        min-width: 38px;
    }}

    /* ===== Scroll bars ===== */
    QScrollArea {{
        background-color: {C["bg"]};
        border: none;
    }}

    QScrollBar:vertical {{
        background: transparent;
        width: 6px;
        margin: 0;
    }}

    QScrollBar::handle:vertical {{
        background: {C["border_light"]};
        border-radius: 3px;
        min-height: 36px;
    }}

    QScrollBar::handle:vertical:hover {{
        background: {C["text_muted"]};
    }}

    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
        background: transparent;
        height: 0;
    }}

    QScrollBar:horizontal {{
        background: transparent;
        height: 6px;
    }}

    QScrollBar::handle:horizontal {{
        background: {C["border_light"]};
        border-radius: 3px;
        min-width: 36px;
    }}

    QScrollBar::handle:horizontal:hover {{
        background: {C["text_muted"]};
    }}

    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
        background: transparent;
        width: 0;
    }}

    /* ===== Status bar ===== */
    QStatusBar {{
        background-color: {C["bg"]};
        border-top: 1px solid {C["border"]};
        color: {C["text_secondary"]};
        padding: 4px 16px;
        font-size: {sm}px;
        font-family: {MONO_FONT};
    }}

    QStatusBar::item {{ border: none; }}

    /* ===== Menu bar ===== */
    QMenuBar {{
        background-color: {C["bg"]};
        color: {C["text"]};
        border-bottom: 1px solid {C["border"]};
        padding: 3px 6px;
        font-size: {md}px;
    }}

    QMenuBar::item {{
        padding: 5px 10px;
        border-radius: 3px;
    }}

    QMenuBar::item:selected {{
        background-color: {C["bg_hover"]};
    }}

    QMenu {{
        background-color: {C["bg_elevated"]};
        border: 1px solid {C["border_light"]};
        padding: 4px;
        border-radius: 6px;
    }}

    QMenu::item {{
        padding: 7px 22px;
        font-size: {md}px;
        border-radius: 3px;
    }}

    QMenu::item:selected {{
        background-color: {C["accent"]};
        color: #000000;
    }}

    QMenu::separator {{
        height: 1px;
        background: {C["border"]};
        margin: 4px 8px;
    }}

    /* ===== Tooltips ===== */
    QToolTip {{
        background-color: {C["bg_elevated"]};
        color: {C["text"]};
        border: 1px solid {C["border_light"]};
        padding: 5px 9px;
        font-size: 11px;
        border-radius: 4px;
    }}

    /* ===== Message box ===== */
    QMessageBox {{
        background-color: {C["bg"]};
    }}

    QMessageBox QLabel {{
        color: {C["text"]};
    }}
    """


def get_welcome_stylesheet(dark_mode: bool = True) -> str:
    C = DARK_COLORS if dark_mode else LIGHT_COLORS
    return f"""
    QWidget#welcomeWidget {{
        background-color: {C["bg"]};
    }}
    """


def get_pdf_viewer_stylesheet(dark_mode: bool = True) -> str:
    C = DARK_COLORS if dark_mode else LIGHT_COLORS
    return f"""
    QScrollArea {{
        background-color: {C["bg"]};
        border: none;
    }}
    """
