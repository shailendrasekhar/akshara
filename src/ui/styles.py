"""
UI Styles Module
Minimalist black and white theme with classical typography.
"""

# Classical serif fonts - elegant and timeless
FONT_FAMILY = "'Georgia', 'Times New Roman', 'Garamond', 'Palatino', serif"
MONO_FONT = "'Ubuntu Mono', 'Courier New', 'Consolas', monospace"

# Pure minimalist dark theme - true black
DARK_COLORS = {
    "bg": "#000000",           # Pure black
    "bg_secondary": "#0a0a0a", # Near black
    "bg_elevated": "#141414",  # Slightly elevated
    "bg_hover": "#1a1a1a",     # Hover state
    
    "text": "#ffffff",         # Pure white
    "text_secondary": "#a0a0a0",
    "text_muted": "#666666",
    
    "border": "#222222",
    "border_light": "#333333",
    
    "accent": "#ffffff",       # White accent for minimalism
    "accent_hover": "#e0e0e0",
    
    "success": "#00ff88",
    "error": "#ff4444",
    "highlight": "#ffcc00",    # Yellow for TTS highlight
}

# Pure minimalist light theme - true white
LIGHT_COLORS = {
    "bg": "#ffffff",           # Pure white
    "bg_secondary": "#fafafa", # Near white
    "bg_elevated": "#f0f0f0",  # Slightly elevated
    "bg_hover": "#e8e8e8",     # Hover state
    
    "text": "#000000",         # Pure black
    "text_secondary": "#555555",
    "text_muted": "#999999",
    
    "border": "#e0e0e0",
    "border_light": "#cccccc",
    
    "accent": "#000000",       # Black accent for minimalism
    "accent_hover": "#333333",
    
    "success": "#00aa55",
    "error": "#cc0000",
    "highlight": "#ffee00",    # Yellow for TTS highlight
}


def get_main_stylesheet(dark_mode: bool = True) -> str:
    """Get minimalist application stylesheet."""
    C = DARK_COLORS if dark_mode else LIGHT_COLORS
    
    return f"""
    /* ===== Global Reset ===== */
    * {{
        font-family: {FONT_FAMILY};
    }}
    
    QMainWindow {{
        background-color: {C["bg"]};
    }}
    
    QWidget {{
        background-color: transparent;
        color: {C["text"]};
        font-size: 13px;
        font-weight: 400;
    }}
    
    /* ===== Toolbar - Ultra Minimal ===== */
    QToolBar {{
        background-color: {C["bg"]};
        border: none;
        border-bottom: 1px solid {C["border"]};
        padding: 12px 16px;
        spacing: 8px;
    }}
    
    QToolBar::separator {{
        background-color: {C["border"]};
        width: 1px;
        margin: 8px 12px;
    }}
    
    /* ===== Buttons - Clean and Minimal ===== */
    QToolButton {{
        background-color: transparent;
        color: {C["text"]};
        border: 1px solid {C["border"]};
        border-radius: 4px;
        padding: 8px 14px;
        font-weight: 500;
        font-size: 12px;
        letter-spacing: 0.5px;
    }}
    
    QToolButton:hover {{
        background-color: {C["bg_hover"]};
        border-color: {C["text_secondary"]};
    }}
    
    QToolButton:pressed {{
        background-color: {C["bg_elevated"]};
    }}
    
    QToolButton:disabled {{
        color: {C["text_muted"]};
        border-color: {C["border"]};
    }}
    
    /* Primary action - inverted colors */
    QToolButton#playButton {{
        background-color: {C["text"]};
        color: {C["bg"]};
        border: none;
        font-weight: 600;
        padding: 10px 18px;
    }}
    
    QToolButton#playButton:hover {{
        background-color: {C["text_secondary"]};
    }}
    
    /* Stop button - subtle red */
    QToolButton#stopButton {{
        background-color: transparent;
        color: {C["error"]};
        border-color: {C["error"]};
    }}
    
    QToolButton#stopButton:hover {{
        background-color: {C["error"]};
        color: {C["bg"]};
    }}
    
    /* Theme button */
    QToolButton#themeButton {{
        border: none;
        font-size: 18px;
        padding: 6px 10px;
    }}
    
    /* Zoom buttons */
    QToolButton#zoomButton {{
        padding: 6px 10px;
        min-width: 28px;
        font-size: 14px;
        font-weight: 600;
    }}
    
    /* ===== Push Buttons ===== */
    QPushButton {{
        background-color: transparent;
        color: {C["text"]};
        border: 1px solid {C["border"]};
        border-radius: 4px;
        padding: 10px 20px;
        font-weight: 500;
        letter-spacing: 0.5px;
    }}
    
    QPushButton:hover {{
        background-color: {C["bg_hover"]};
    }}
    
    QPushButton#openButton {{
        background-color: {C["text"]};
        color: {C["bg"]};
        border: none;
        border-radius: 6px;
        padding: 14px 36px;
        font-size: 14px;
        font-weight: 600;
        letter-spacing: 1px;
    }}
    
    QPushButton#openButton:hover {{
        background-color: {C["text_secondary"]};
    }}
    
    /* ===== Sliders - Minimal Line ===== */
    QSlider::groove:horizontal {{
        border: none;
        height: 2px;
        background: {C["border"]};
    }}
    
    QSlider::handle:horizontal {{
        background: {C["text"]};
        width: 12px;
        height: 12px;
        margin: -5px 0;
        border-radius: 6px;
    }}
    
    QSlider::handle:horizontal:hover {{
        background: {C["text_secondary"]};
    }}
    
    QSlider::sub-page:horizontal {{
        background: {C["text_secondary"]};
    }}
    
    /* ===== Spin Boxes ===== */
    QSpinBox {{
        background-color: {C["bg_secondary"]};
        color: {C["text"]};
        border: 1px solid {C["border"]};
        border-radius: 4px;
        padding: 6px 10px;
        min-width: 50px;
        font-family: {MONO_FONT};
    }}
    
    QSpinBox:focus {{
        border-color: {C["text_secondary"]};
    }}
    
    QSpinBox::up-button, QSpinBox::down-button {{
        background: transparent;
        border: none;
        width: 16px;
    }}
    
    /* ===== Labels ===== */
    QLabel {{
        color: {C["text"]};
        background: transparent;
        font-weight: 400;
    }}
    
    QLabel#speedLabel {{
        color: {C["text_secondary"]};
        font-family: {MONO_FONT};
        font-size: 11px;
        font-weight: 500;
    }}
    
    QLabel#zoomLabel {{
        color: {C["text_secondary"]};
        font-family: {MONO_FONT};
        font-size: 11px;
        min-width: 40px;
    }}
    
    /* ===== Scroll Bars - Near Invisible ===== */
    QScrollArea {{
        background-color: {C["bg"]};
        border: none;
    }}
    
    QScrollBar:vertical {{
        background: transparent;
        width: 8px;
        margin: 0;
    }}
    
    QScrollBar::handle:vertical {{
        background: {C["border"]};
        border-radius: 4px;
        min-height: 40px;
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
        height: 8px;
    }}
    
    QScrollBar::handle:horizontal {{
        background: {C["border"]};
        border-radius: 4px;
        min-width: 40px;
    }}
    
    QScrollBar::handle:horizontal:hover {{
        background: {C["text_muted"]};
    }}
    
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
        background: transparent;
        width: 0;
    }}
    
    /* ===== Status Bar ===== */
    QStatusBar {{
        background-color: {C["bg"]};
        border-top: 1px solid {C["border"]};
        color: {C["text_secondary"]};
        padding: 6px 16px;
        font-size: 11px;
    }}
    
    QStatusBar::item {{
        border: none;
    }}
    
    /* ===== Menu Bar ===== */
    QMenuBar {{
        background-color: {C["bg"]};
        color: {C["text"]};
        border-bottom: 1px solid {C["border"]};
        padding: 4px 8px;
        font-size: 12px;
    }}
    
    QMenuBar::item {{
        padding: 6px 12px;
        border-radius: 2px;
    }}
    
    QMenuBar::item:selected {{
        background-color: {C["bg_hover"]};
    }}
    
    QMenu {{
        background-color: {C["bg_secondary"]};
        border: 1px solid {C["border"]};
        padding: 4px;
    }}
    
    QMenu::item {{
        padding: 8px 24px;
        font-size: 12px;
    }}
    
    QMenu::item:selected {{
        background-color: {C["text"]};
        color: {C["bg"]};
    }}
    
    /* ===== Tooltips ===== */
    QToolTip {{
        background-color: {C["bg_secondary"]};
        color: {C["text"]};
        border: 1px solid {C["border"]};
        padding: 6px 10px;
        font-size: 11px;
    }}
    
    /* ===== Message Box ===== */
    QMessageBox {{
        background-color: {C["bg"]};
    }}
    """


def get_welcome_stylesheet(dark_mode: bool = True) -> str:
    """Get minimalist welcome screen stylesheet."""
    C = DARK_COLORS if dark_mode else LIGHT_COLORS
    
    return f"""
    QWidget#welcomeWidget {{
        background-color: {C["bg"]};
    }}
    
    QLabel#welcomeTitle {{
        font-size: 48px;
        font-weight: 300;
        letter-spacing: 8px;
        color: {C["text"]};
        background: transparent;
    }}
    
    QLabel#welcomeSubtitle {{
        font-size: 13px;
        font-weight: 400;
        letter-spacing: 2px;
        color: {C["text_secondary"]};
        background: transparent;
        text-transform: uppercase;
    }}
    
    QLabel#welcomeIcon {{
        font-size: 64px;
        color: {C["text"]};
        background: transparent;
    }}
    
    QPushButton#openButton {{
        background-color: {C["text"]};
        color: {C["bg"]};
        border: none;
        border-radius: 6px;
        padding: 16px 48px;
        font-size: 13px;
        font-weight: 600;
        letter-spacing: 2px;
        text-transform: uppercase;
    }}
    
    QPushButton#openButton:hover {{
        background-color: {C["text_secondary"]};
    }}
    """


def get_pdf_viewer_stylesheet(dark_mode: bool = True) -> str:
    """Get PDF viewer stylesheet."""
    C = DARK_COLORS if dark_mode else LIGHT_COLORS
    
    return f"""
    QScrollArea {{
        background-color: {C["bg"]};
        border: none;
    }}
    """
