import os
import time
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QToolBar, QStatusBar, QFileDialog, QSlider,
    QSpinBox, QToolButton, QMessageBox, QApplication,
    QStackedWidget, QPushButton, QDockWidget, QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSlot, QTimer, QSize
from PyQt6.QtGui import QAction, QKeySequence

from .pdf_handler import PDFDocument
from .pdf_viewer import PDFViewerWidget
from .tts_engine import TTSEngine
from .ui.styles import get_main_stylesheet
from .db import Store
from .pomodoro import PomodoroPanel
from .analytics import AnalyticsDialog
from .library import LibraryPanel


class WelcomeWidget(QWidget):
    """Welcome screen — shown when no PDF is loaded."""

    def __init__(self, dark_mode: bool = True, parent=None):
        super().__init__(parent)
        self._dark_mode = dark_mode
        self.setObjectName("welcomeWidget")
        self._setup_ui()
        self._apply_theme()

    def set_dark_mode(self, dark_mode: bool):
        self._dark_mode = dark_mode
        self._apply_theme()

    def _apply_theme(self):
        from PyQt6.QtGui import QPalette, QColor as QC
        dark = self._dark_mode
        bg      = "#000000" if dark else "#ffffff"
        ink     = "#f0f0f0" if dark else "#0a0a0a"
        muted   = "#555555" if dark else "#aaaaaa"
        accent  = "#d8a85a"
        hint    = "#2a2a2a" if dark else "#eeeeea"

        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QC(bg))
        self.setPalette(palette)
        self.setAutoFillBackground(True)

        self.icon_label.setStyleSheet(
            f"font-size:60px;background:transparent;color:{ink};"
        )
        self.title_label.setStyleSheet(
            f"font-family:Georgia,serif;font-size:44px;font-weight:300;"
            f"letter-spacing:10px;color:{ink};background:transparent;"
        )
        self.subtitle_label.setStyleSheet(
            f"font-size:11px;letter-spacing:3px;color:{muted};background:transparent;"
        )
        self.open_button.setStyleSheet(f"""
            QPushButton {{
                background-color:{accent};
                color:#000000;
                border:none;
                border-radius:6px;
                padding:14px 44px;
                font-size:12px;
                font-weight:700;
                letter-spacing:2px;
            }}
            QPushButton:hover {{ background-color:#e8bb6a; }}
        """)
        self.hint_label.setStyleSheet(
            f"font-family:'Ubuntu Mono','Courier New',monospace;"
            f"font-size:11px;color:{muted};background:transparent;"
        )
        self.shortcuts_widget.setStyleSheet(
            f"background:{hint};border-radius:8px;"
        )
        for label in self._shortcut_labels:
            label.setStyleSheet(
                f"font-family:'Ubuntu Mono','Courier New',monospace;"
                f"font-size:11px;color:{muted};background:transparent;"
            )

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.setSpacing(0)

        self.icon_label = QLabel("📖")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(self.icon_label)
        outer.addSpacing(16)

        self.title_label = QLabel("AKSHARA")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(self.title_label)
        outer.addSpacing(8)

        self.subtitle_label = QLabel("PDF · FOCUS · ANALYTICS")
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(self.subtitle_label)
        outer.addSpacing(36)

        self.open_button = QPushButton("Open PDF")
        self.open_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_button.setFixedWidth(200)
        outer.addWidget(self.open_button, alignment=Qt.AlignmentFlag.AlignCenter)
        outer.addSpacing(10)

        self.hint_label = QLabel("or drag a PDF onto this window")
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(self.hint_label)
        outer.addSpacing(40)

        # Keyboard shortcuts cheatsheet
        self.shortcuts_widget = QWidget()
        self.shortcuts_widget.setFixedWidth(340)
        sc_layout = QVBoxLayout(self.shortcuts_widget)
        sc_layout.setContentsMargins(20, 16, 20, 16)
        sc_layout.setSpacing(6)
        self._shortcut_labels = []
        shortcuts = [
            ("Space",          "Play / pause reading"),
            ("← →",           "Previous / next page"),
            ("Ctrl+R",         "Read current page"),
            ("Ctrl+Shift+R",   "Read selection"),
            ("Ctrl+T",         "Toggle dark / light"),
            ("Ctrl+Shift+A",   "Analytics"),
            ("L",              "Show / hide library"),
        ]
        for key, desc in shortcuts:
            row = QHBoxLayout()
            k = QLabel(key)
            d = QLabel(desc)
            row.addWidget(k)
            row.addStretch(1)
            row.addWidget(d)
            sc_layout.addLayout(row)
            self._shortcut_labels.extend([k, d])

        outer.addWidget(self.shortcuts_widget, alignment=Qt.AlignmentFlag.AlignCenter)


class MainWindow(QMainWindow):
    """Main application window."""
    
    # Text size presets: (label, app font pt, stylesheet base px)
    _TEXT_SIZES = [
        ("S",  10, 13),
        ("M",  12, 15),
        ("L",  14, 17),
    ]
    _TEXT_SIZE_IDX = 1   # default: Medium

    def __init__(self):
        super().__init__()

        # Theme state - based on local time (6-18 is light, otherwise dark)
        from datetime import datetime
        current_hour = datetime.now().hour
        self._dark_mode = not (6 <= current_hour < 18)
        self._text_size_idx = self._TEXT_SIZE_IDX
        
        # Initialize components
        self.pdf_doc = PDFDocument(self)
        self.tts_engine = TTSEngine(self)
        
        self.tts_engine.enable_hf(True, voice="af_heart", lang_code="a")

        self.store = Store()
        self._active_doc_id: str | None = None
        self._page_dwell_started_at: float | None = None

        self.pomodoro = PomodoroPanel(self.store)
        self.pomodoro.phase_completed.connect(self._on_phase_completed)

        self._pomodoro_dock = QDockWidget("POMODORO", self)
        self._pomodoro_dock.setObjectName("pomodoroDock")
        self._pomodoro_dock.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea)
        self._pomodoro_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable |
            QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )
        self._pomodoro_dock.setWidget(self.pomodoro)
        self._pomodoro_dock.setMinimumWidth(240)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._pomodoro_dock)

        self.library = LibraryPanel(self.store, dark=self._dark_mode)
        self.library.open_document.connect(self._load_pdf)

        self._library_dock = QDockWidget("LIBRARY", self)
        self._library_dock.setObjectName("libraryDock")
        self._library_dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea)
        self._library_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable |
            QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )
        self._library_dock.setWidget(self.library)
        self._library_dock.setMinimumWidth(220)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self._library_dock)

        self._setup_window()
        self._setup_menu()
        self._setup_toolbar()
        self._setup_central_widget()
        self._setup_status_bar()
        self._connect_signals()
        
        # Apply initial theme and text size
        self._apply_theme()
        label, _, _ = self._TEXT_SIZES[self._text_size_idx]
        self.text_size_btn.setText(f"T{label}")

        # Enable drag and drop
        self.setAcceptDrops(True)
    
    def _setup_window(self):
        self.setWindowTitle("AKSHARA - PDF Reader")
        self.setMinimumSize(800, 600)
        self.showMaximized()
    
    def _setup_menu(self):
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("&File")
        
        open_action = QAction("&Open PDF...", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self._open_file_dialog)
        file_menu.addAction(open_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # View menu
        view_menu = menubar.addMenu("&View")
        
        zoom_in_action = QAction("Zoom &In", self)
        zoom_in_action.setShortcut(QKeySequence.StandardKey.ZoomIn)
        zoom_in_action.triggered.connect(self._zoom_in)
        view_menu.addAction(zoom_in_action)
        
        zoom_out_action = QAction("Zoom &Out", self)
        zoom_out_action.setShortcut(QKeySequence.StandardKey.ZoomOut)
        zoom_out_action.triggered.connect(self._zoom_out)
        view_menu.addAction(zoom_out_action)
        
        view_menu.addSeparator()
        
        self.theme_action = QAction("Switch to &Light Mode", self)
        self.theme_action.setShortcut(QKeySequence("Ctrl+T"))
        self.theme_action.triggered.connect(self._toggle_theme)
        view_menu.addAction(self.theme_action)

        text_size_action = QAction("Cycle &Text Size", self)
        text_size_action.setShortcut(QKeySequence("Ctrl+Shift+T"))
        text_size_action.triggered.connect(self._cycle_text_size)
        view_menu.addAction(text_size_action)

        analytics_action = QAction("&Analytics…", self)
        analytics_action.setShortcut(QKeySequence("Ctrl+Shift+A"))
        analytics_action.triggered.connect(self._show_analytics)
        view_menu.addAction(analytics_action)

        library_action = QAction("&Library", self)
        library_action.setShortcut(QKeySequence("L"))
        library_action.triggered.connect(self._toggle_library)
        view_menu.addAction(library_action)

        # Speech menu
        speech_menu = menubar.addMenu("&Speech")
        
        read_page_action = QAction("Read &Page", self)
        read_page_action.setShortcut(QKeySequence("Ctrl+R"))
        read_page_action.triggered.connect(self._play_page)
        speech_menu.addAction(read_page_action)
        
        read_selection_action = QAction("Read &Selection", self)
        read_selection_action.setShortcut(QKeySequence("Ctrl+Shift+R"))
        read_selection_action.triggered.connect(self._play_selection)
        speech_menu.addAction(read_selection_action)
        
        speech_menu.addSeparator()
        
        pause_action = QAction("&Pause/Resume", self)
        pause_action.setShortcut(QKeySequence("Space"))
        pause_action.triggered.connect(self._toggle_pause)
        speech_menu.addAction(pause_action)
        
        stop_action = QAction("S&top", self)
        stop_action.setShortcut(QKeySequence("Escape"))
        stop_action.triggered.connect(self._stop)
        speech_menu.addAction(stop_action)
        
        # Help menu
        help_menu = menubar.addMenu("&Help")
        
        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)
    
    def _setup_toolbar(self):
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        toolbar.setIconSize(QSize(16, 16))
        self.addToolBar(toolbar)

        # ── Open ──────────────────────────────────────────────────────────────
        self.open_btn = QToolButton()
        self.open_btn.setText("Open")
        self.open_btn.setObjectName("tbOpen")
        self.open_btn.setToolTip("Open PDF  Ctrl+O")
        self.open_btn.clicked.connect(self._open_file_dialog)
        toolbar.addWidget(self.open_btn)

        toolbar.addSeparator()

        # ── Navigation pill group ─────────────────────────────────────────────
        nav = QWidget()
        nav.setObjectName("tbGroup")
        nav_lay = QHBoxLayout(nav)
        nav_lay.setContentsMargins(2, 2, 2, 2)
        nav_lay.setSpacing(0)

        self.prev_btn = QToolButton()
        self.prev_btn.setText("‹")
        self.prev_btn.setObjectName("tbGroupLeft")
        self.prev_btn.setToolTip("Previous page  ←")
        self.prev_btn.setEnabled(False)
        self.prev_btn.clicked.connect(self._prev_page)
        nav_lay.addWidget(self.prev_btn)

        self.page_spin = QSpinBox()
        self.page_spin.setObjectName("tbSpin")
        self.page_spin.setMinimum(1)
        self.page_spin.setMaximum(1)
        self.page_spin.setEnabled(False)
        self.page_spin.setFixedWidth(52)
        self.page_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_spin.valueChanged.connect(self._go_to_page)
        nav_lay.addWidget(self.page_spin)

        self.page_total_label = QLabel("/ 1")
        self.page_total_label.setObjectName("tbMuted")
        self.page_total_label.setContentsMargins(4, 0, 6, 0)
        nav_lay.addWidget(self.page_total_label)

        self.next_btn = QToolButton()
        self.next_btn.setText("›")
        self.next_btn.setObjectName("tbGroupRight")
        self.next_btn.setToolTip("Next page  →")
        self.next_btn.setEnabled(False)
        self.next_btn.clicked.connect(self._next_page)
        nav_lay.addWidget(self.next_btn)

        toolbar.addWidget(nav)
        toolbar.addSeparator()

        # ── TTS pill group ────────────────────────────────────────────────────
        tts = QWidget()
        tts.setObjectName("tbGroup")
        tts_lay = QHBoxLayout(tts)
        tts_lay.setContentsMargins(2, 2, 2, 2)
        tts_lay.setSpacing(0)

        self.play_btn = QToolButton()
        self.play_btn.setText("▶  Read")
        self.play_btn.setObjectName("tbAccent")
        self.play_btn.setToolTip("Read page  Ctrl+R")
        self.play_btn.setEnabled(False)
        self.play_btn.clicked.connect(self._play_page)
        tts_lay.addWidget(self.play_btn)

        self.play_sel_btn = QToolButton()
        self.play_sel_btn.setText("⌦  Selection")
        self.play_sel_btn.setObjectName("tbGroupMid")
        self.play_sel_btn.setToolTip("Read selection  Ctrl+Shift+R")
        self.play_sel_btn.setEnabled(False)
        self.play_sel_btn.clicked.connect(self._play_selection)
        tts_lay.addWidget(self.play_sel_btn)

        self.pause_btn = QToolButton()
        self.pause_btn.setText("⏸")
        self.pause_btn.setObjectName("tbGroupMid")
        self.pause_btn.setToolTip("Pause / Resume  Space")
        self.pause_btn.setEnabled(False)
        self.pause_btn.clicked.connect(self._toggle_pause)
        tts_lay.addWidget(self.pause_btn)

        self.stop_btn = QToolButton()
        self.stop_btn.setText("■")
        self.stop_btn.setObjectName("tbStop")
        self.stop_btn.setToolTip("Stop  Esc")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop)
        tts_lay.addWidget(self.stop_btn)

        toolbar.addWidget(tts)
        toolbar.addSeparator()

        # ── Speed ─────────────────────────────────────────────────────────────
        speed_wrap = QWidget()
        speed_wrap.setObjectName("tbGroup")
        speed_lay = QHBoxLayout(speed_wrap)
        speed_lay.setContentsMargins(8, 0, 8, 0)
        speed_lay.setSpacing(6)

        speed_lbl = QLabel("Speed")
        speed_lbl.setObjectName("tbMuted")
        speed_lay.addWidget(speed_lbl)

        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setMinimum(50)
        self.speed_slider.setMaximum(200)
        self.speed_slider.setValue(100)
        self.speed_slider.setFixedWidth(88)
        self.speed_slider.setToolTip("Reading speed")
        self.speed_slider.valueChanged.connect(self._update_speed)
        speed_lay.addWidget(self.speed_slider)

        self.speed_value_label = QLabel("1.0×")
        self.speed_value_label.setObjectName("speedLabel")
        self.speed_value_label.setFixedWidth(36)
        speed_lay.addWidget(self.speed_value_label)

        toolbar.addWidget(speed_wrap)

        # ── Stretch ───────────────────────────────────────────────────────────
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)

        # ── Zoom pill group ───────────────────────────────────────────────────
        zoom = QWidget()
        zoom.setObjectName("tbGroup")
        zoom_lay = QHBoxLayout(zoom)
        zoom_lay.setContentsMargins(2, 2, 2, 2)
        zoom_lay.setSpacing(0)

        self.zoom_out_btn = QToolButton()
        self.zoom_out_btn.setText("−")
        self.zoom_out_btn.setObjectName("tbGroupLeft")
        self.zoom_out_btn.setToolTip("Zoom out  Ctrl+−")
        self.zoom_out_btn.setEnabled(False)
        self.zoom_out_btn.clicked.connect(self._zoom_out)
        zoom_lay.addWidget(self.zoom_out_btn)

        self.zoom_label = QLabel("100%")
        self.zoom_label.setObjectName("tbZoomLabel")
        self.zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.zoom_label.setFixedWidth(46)
        zoom_lay.addWidget(self.zoom_label)

        self.zoom_in_btn = QToolButton()
        self.zoom_in_btn.setText("+")
        self.zoom_in_btn.setObjectName("tbGroupRight")
        self.zoom_in_btn.setToolTip("Zoom in  Ctrl++")
        self.zoom_in_btn.setEnabled(False)
        self.zoom_in_btn.clicked.connect(self._zoom_in)
        zoom_lay.addWidget(self.zoom_in_btn)

        toolbar.addWidget(zoom)

        toolbar.addSeparator()

        # ── Text size toggle ──────────────────────────────────────────────────
        self.text_size_btn = QToolButton()
        self.text_size_btn.setObjectName("textSizeButton")
        self.text_size_btn.setToolTip("Cycle text size: S → M → L  Ctrl+Shift+T")
        self.text_size_btn.clicked.connect(self._cycle_text_size)
        toolbar.addWidget(self.text_size_btn)

        toolbar.addSeparator()

        # ── Theme toggle ──────────────────────────────────────────────────────
        self.theme_btn = QToolButton()
        self.theme_btn.setText("☀")
        self.theme_btn.setObjectName("themeButton")
        self.theme_btn.setToolTip("Toggle theme  Ctrl+T")
        self.theme_btn.clicked.connect(self._toggle_theme)
        toolbar.addWidget(self.theme_btn)
    
    def _setup_central_widget(self):
        self.stacked_widget = QStackedWidget()
        self.welcome_widget = WelcomeWidget(dark_mode=self._dark_mode)
        self.welcome_widget.open_button.clicked.connect(self._open_file_dialog)
        self.stacked_widget.addWidget(self.welcome_widget)
        self.pdf_viewer = PDFViewerWidget()
        self.pdf_viewer.text_selected.connect(self._on_text_selected)
        self.pdf_viewer.current_page_changed.connect(self._on_visible_page_changed)
        self.stacked_widget.addWidget(self.pdf_viewer)
        self.stacked_widget.setCurrentWidget(self.welcome_widget)
        self.setCentralWidget(self.stacked_widget)

    def _setup_status_bar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_label = QLabel("Ready — open a PDF to get started")
        self.status_bar.addWidget(self.status_label, 1)
        self.tts_status_label = QLabel("")
        self.status_bar.addPermanentWidget(self.tts_status_label)

    def _connect_signals(self):
        self.pdf_doc.document_loaded.connect(self._on_document_loaded)
        self.pdf_doc.error_occurred.connect(self._on_error)
        self.tts_engine.speech_started.connect(self._on_speech_started)
        self.tts_engine.speech_finished.connect(self._on_speech_finished)
        self.tts_engine.word_changed.connect(self._on_word_changed)
        self.tts_engine.error_occurred.connect(self._on_error)
    
    def _toggle_theme(self):
        self._dark_mode = not self._dark_mode
        self._apply_theme()

    def _apply_theme(self):
        self.pdf_doc.dark_mode = self._dark_mode
        _, _, base_px = self._TEXT_SIZES[self._text_size_idx]
        self.setStyleSheet(get_main_stylesheet(self._dark_mode, base_px))
        self.welcome_widget.set_dark_mode(self._dark_mode)
        self.pdf_viewer.set_dark_mode(self._dark_mode)
        self.pomodoro.set_dark_mode(self._dark_mode)
        self.library.set_dark_mode(self._dark_mode)
        if self._dark_mode:
            self.theme_btn.setText("☀️")
            self.theme_btn.setToolTip("Switch to Light Mode (Ctrl+T)")
            self.theme_action.setText("Switch to &Light Mode")
        else:
            self.theme_btn.setText("🌙")
            self.theme_btn.setToolTip("Switch to Dark Mode (Ctrl+T)")
            self.theme_action.setText("Switch to &Dark Mode")

    def _cycle_text_size(self):
        self._text_size_idx = (self._text_size_idx + 1) % len(self._TEXT_SIZES)
        self._apply_text_size()

    def _apply_text_size(self):
        label, pt, px = self._TEXT_SIZES[self._text_size_idx]
        self.text_size_btn.setText(f"T{label}")
        font = QApplication.font()
        font.setPointSize(pt)
        QApplication.setFont(font)
        _, _, base_px = self._TEXT_SIZES[self._text_size_idx]
        self.setStyleSheet(get_main_stylesheet(self._dark_mode, base_px))
    
    def _open_file_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open PDF", "", "PDF Files (*.pdf);;All Files (*)"
        )
        if file_path:
            self._load_pdf(file_path)
    
    def _load_pdf(self, file_path: str):
        self.status_label.setText(f"Loading: {os.path.basename(file_path)}...")
        QApplication.processEvents()
        
        if self.pdf_doc.load(file_path):
            self._active_doc_id = self.store.upsert_document(
                file_path=file_path,
                title=self.pdf_doc.title,
                author=getattr(self.pdf_doc, "author", None),
                pages=self.pdf_doc.page_count,
            )
            self.pomodoro.set_active_document(self._active_doc_id)
            self._page_dwell_started_at = time.time()
            self.library.refresh()
            self.stacked_widget.setCurrentWidget(self.pdf_viewer)
            QTimer.singleShot(50, self._fit_and_load)

    def _fit_and_load(self):
        self._fit_to_width()
        self.pdf_viewer.load_document(
            self.pdf_doc._doc,
            self.pdf_doc.zoom,
            self._dark_mode,
        )
    
    def _prev_page(self):
        cur = self.pdf_viewer.current_page
        if cur > 0:
            self.pdf_viewer.go_to_page(cur - 1)

    def _next_page(self):
        cur = self.pdf_viewer.current_page
        if self.pdf_doc.is_loaded and cur < self.pdf_doc.page_count - 1:
            self.pdf_viewer.go_to_page(cur + 1)

    def _go_to_page(self, page_num: int):
        self.pdf_viewer.go_to_page(page_num - 1)

    @pyqtSlot(int)
    def _on_visible_page_changed(self, page_index: int):
        self.page_spin.blockSignals(True)
        self.page_spin.setValue(page_index + 1)
        self.page_spin.blockSignals(False)

        if self._active_doc_id and self._page_dwell_started_at and self.pomodoro._active:
            elapsed = int(time.time() - self._page_dwell_started_at)
            if elapsed > 0:
                self.store.add_page_view(
                    self.pomodoro._active.db_id,
                    page_index + 1,
                    elapsed,
                )
        self._page_dwell_started_at = time.time()

        if self._active_doc_id:
            self.store.update_last_page(self._active_doc_id, page_index + 1)
            self.library.update_document_progress(
                self.pdf_doc._file_path, page_index + 1
            )
    
    def _zoom_in(self):
        if self.pdf_doc.zoom < 3.0:
            self.pdf_doc.zoom = round(self.pdf_doc.zoom + 0.25, 2)
            self._update_zoom_label()
            self.pdf_viewer.set_zoom(self.pdf_doc.zoom)

    def _zoom_out(self):
        if self.pdf_doc.zoom > 0.5:
            self.pdf_doc.zoom = round(self.pdf_doc.zoom - 0.25, 2)
            self._update_zoom_label()
            self.pdf_viewer.set_zoom(self.pdf_doc.zoom)

    def _update_zoom_label(self):
        self.zoom_label.setText(f"{int(self.pdf_doc.zoom * 100)}%")

    def _fit_to_width(self):
        page_width, _ = self.pdf_doc.get_page_size()
        if page_width <= 0:
            return
        viewer_width = self.pdf_viewer.scroll_area.viewport().width() - 40
        if viewer_width <= 0:
            viewer_width = 800
        optimal_zoom = viewer_width / (page_width * 1.5)
        optimal_zoom = max(0.5, min(round(optimal_zoom * 4) / 4, 3.0))
        self.pdf_doc.zoom = optimal_zoom
        self._update_zoom_label()
    
    def _play_page(self):
        if not self.pdf_doc.is_loaded:
            return
        text = self.pdf_doc.extract_text(self.pdf_viewer.current_page)
        if text.strip():
            self.pdf_viewer.reset_read_position()
            self.tts_engine.speak(text)
        else:
            self.status_label.setText("No text found on this page")
    
    def _play_selection(self):
        selected = self.pdf_viewer.get_selected_text()
        if selected.strip():
            self.pdf_viewer.reset_read_position()
            self.tts_engine.speak(selected)
        else:
            self.status_label.setText("Select text on the PDF first")
    
    def _toggle_pause(self):
        if self.tts_engine.is_speaking:
            if self.tts_engine.is_paused:
                self.tts_engine.resume()
                self.pause_btn.setText("⏸ Pause")
                self.tts_status_label.setText("🔊 Reading...")
            else:
                self.tts_engine.pause()
                self.pause_btn.setText("▶ Resume")
                self.tts_status_label.setText("⏸ Paused")
    
    def _stop(self):
        self.tts_engine.stop()
        self._update_tts_buttons(False)
        self.pdf_viewer.highlight_text("")
        self.tts_status_label.setText("")
    
    def _update_speed(self, value: int):
        speed = value / 100.0
        self.speed_value_label.setText(f"{speed:.1f}x")
        self.tts_engine.set_rate_multiplier(speed)

    def _update_tts_buttons(self, playing: bool):
        self.pause_btn.setEnabled(playing)
        self.stop_btn.setEnabled(playing)
        self.pause_btn.setText("⏸ Pause")
    
    @pyqtSlot(int)
    def _on_document_loaded(self, page_count: int):
        self.setWindowTitle(f"AKSHARA - {self.pdf_doc.title}")
        
        self.page_spin.setMaximum(page_count)
        self.page_spin.setValue(1)
        self.page_spin.setEnabled(True)
        self.page_total_label.setText(f" / {page_count}")
        
        self.prev_btn.setEnabled(True)
        self.next_btn.setEnabled(True)
        self.play_btn.setEnabled(True)
        self.play_sel_btn.setEnabled(True)
        self.zoom_in_btn.setEnabled(True)
        self.zoom_out_btn.setEnabled(True)
        
        self.status_label.setText(f"Loaded: {self.pdf_doc.title} ({page_count} pages)")
    
    @pyqtSlot(str)
    def _on_text_selected(self, text: str):
        self.status_label.setText(f"Selected {len(text.split())} words — right-click to copy")
    
    @pyqtSlot()
    def _on_speech_started(self):
        self._update_tts_buttons(True)
        self.tts_status_label.setText("🔊 Reading...")
    
    @pyqtSlot()
    def _on_speech_finished(self):
        self._update_tts_buttons(False)
        self.pdf_viewer.highlight_text("")
        self.tts_status_label.setText("✓ Done")
        QTimer.singleShot(2000, lambda: self.tts_status_label.setText(""))
    
    @pyqtSlot(str)
    def _on_word_changed(self, word_chunk: str):
        self.pdf_viewer.highlight_text(word_chunk)

    @pyqtSlot(str)
    def _on_error(self, message: str):
        self.status_label.setText(f"Error: {message}")

    def _toggle_library(self):
        if self._library_dock.isVisible():
            self._library_dock.hide()
        else:
            self.library.refresh()
            self._library_dock.show()

    def _show_analytics(self):
        AnalyticsDialog(self.store, parent=self, dark_mode=self._dark_mode).exec()

    def _on_phase_completed(self, phase: str, minutes: int):
        self.status_label.setText(
            f"✓ {phase.title()} session — {minutes} min recorded to akshara.db"
        )

    def _show_about(self):
        QMessageBox.about(
            self,
            "About AKSHARA",
            "<h2>AKSHARA</h2>"
            "<p>PDF Reader with Text-to-Speech</p>"
            "<p><b>Features:</b></p>"
            "<ul>"
            "<li>Select text directly on the PDF</li>"
            "<li>Right-click to copy selected text</li>"
            "<li>Read entire page or just selection</li>"
            "<li>Text highlighting while reading</li>"
            "<li>Adjustable reading speed</li>"
            "<li>Light/Dark mode toggle</li>"
            "</ul>"
        )
    
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls and urls[0].toLocalFile().lower().endswith('.pdf'):
                event.acceptProposedAction()
    
    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            if file_path.lower().endswith('.pdf'):
                self._load_pdf(file_path)
    
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Left:
            self._prev_page()
        elif event.key() == Qt.Key.Key_Right:
            self._next_page()
        elif event.key() == Qt.Key.Key_Space:
            if self.tts_engine.is_speaking:
                self._toggle_pause()
            elif self.pdf_doc.is_loaded:
                self._play_page()
        elif event.key() == Qt.Key.Key_Escape:
            self._stop()
        elif event.key() == Qt.Key.Key_L:
            self._toggle_library()
        else:
            super().keyPressEvent(event)
    
    def closeEvent(self, event):
        self.tts_engine.cleanup()
        self.pdf_doc.close()
        self.pomodoro.reset()
        self.store.close()
        event.accept()
