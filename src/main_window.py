"""
Main Window Module
The primary application window with PDF viewer and TTS controls.
"""

import sys
import os
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QToolBar, QStatusBar, QFileDialog, QSlider,
    QSpinBox, QToolButton, QMessageBox, QApplication,
    QStackedWidget, QPushButton
)
from PyQt6.QtCore import Qt, QSize, pyqtSlot, QTimer
from PyQt6.QtGui import QAction, QKeySequence, QPixmap

from .pdf_handler import PDFDocument
from .pdf_viewer import PDFViewerWidget, TextSpan
from .tts_engine import TTSEngine
from .ui.styles import get_main_stylesheet, get_welcome_stylesheet, get_pdf_viewer_stylesheet


class WelcomeWidget(QWidget):
    """Welcome screen shown when no PDF is loaded."""
    
    def __init__(self, dark_mode: bool = True, parent=None):
        super().__init__(parent)
        self._dark_mode = dark_mode
        self.setObjectName("welcomeWidget")
        self._setup_ui()
        self._apply_theme()
    
    def set_dark_mode(self, dark_mode: bool):
        """Update theme."""
        self._dark_mode = dark_mode
        self._apply_theme()
    
    def _apply_theme(self):
        """Apply theme colors directly to widgets."""
        if self._dark_mode:
            bg = "#000000"
            text = "#ffffff"
            text_secondary = "#a0a0a0"
            btn_bg = "#ffffff"
            btn_text = "#000000"
        else:
            bg = "#ffffff"
            text = "#000000"
            text_secondary = "#555555"
            btn_bg = "#000000"
            btn_text = "#ffffff"
        
        # Set background using palette for reliability
        from PyQt6.QtGui import QPalette, QColor as QC
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QC(bg))
        self.setPalette(palette)
        self.setAutoFillBackground(True)
        
        # Apply to labels with !important-like specificity
        self.icon_label.setStyleSheet(f"QLabel {{ font-size: 64px; color: {text}; background-color: {bg}; }}")
        self.title_label.setStyleSheet(f"QLabel {{ font-size: 48px; font-weight: 300; letter-spacing: 8px; color: {text}; background-color: {bg}; }}")
        self.subtitle_label.setStyleSheet(f"QLabel {{ font-size: 13px; font-weight: 400; letter-spacing: 2px; color: {text_secondary}; background-color: {bg}; }}")
        self.instructions_label.setStyleSheet(f"QLabel {{ font-size: 13px; color: {text_secondary}; background-color: {bg}; margin-top: 40px; }}")
        
        # Apply to button
        self.open_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {btn_bg};
                color: {btn_text};
                border: none;
                border-radius: 6px;
                padding: 16px 48px;
                font-size: 13px;
                font-weight: 600;
                letter-spacing: 2px;
            }}
            QPushButton:hover {{
                background-color: {text_secondary};
            }}
        """)
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(24)
        
        # Icon
        self.icon_label = QLabel("📖")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.icon_label)
        
        # Title
        self.title_label = QLabel("AKSHARA")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label)
        
        # Subtitle
        self.subtitle_label = QLabel("PDF Reader with Text-to-Speech")
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.subtitle_label)
        
        layout.addSpacing(32)
        
        # Open button
        self.open_button = QPushButton("📂  Open PDF")
        self.open_button.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(self.open_button, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Instructions
        self.instructions_label = QLabel(
            "• Select text on the PDF by clicking and dragging\n"
            "• Right-click to copy selected text\n"
            "• Press Space to play/pause reading\n"
            "• Toggle 🌙/☀️ for dark/light mode"
        )
        self.instructions_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.instructions_label)


class MainWindow(QMainWindow):
    """Main application window."""
    
    def __init__(self):
        super().__init__()
        
        # Theme state - based on local time (6-18 is light, otherwise dark)
        from datetime import datetime
        current_hour = datetime.now().hour
        self._dark_mode = not (6 <= current_hour < 18)
        
        # Initialize components
        self.pdf_doc = PDFDocument(self)
        self.tts_engine = TTSEngine(self)
        
        # State
        self._current_speed = 1.0
        
        # Setup UI
        self._setup_window()
        self._setup_menu()
        self._setup_toolbar()
        self._setup_central_widget()
        self._setup_status_bar()
        self._connect_signals()
        
        # Apply initial theme
        self._apply_theme()
        
        # Enable drag and drop
        self.setAcceptDrops(True)
    
    def _setup_window(self):
        """Configure the main window."""
        self.setWindowTitle("AKSHARA - PDF Reader")
        self.setMinimumSize(800, 600)
        self.resize(1100, 750)
        
        # Center on screen
        screen = QApplication.primaryScreen().availableGeometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)
    
    def _setup_menu(self):
        """Setup the menu bar."""
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
        """Setup the main toolbar."""
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(24, 24))
        toolbar.setFloatable(False)
        # Allow toolbar to wrap when window is narrow
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBar(toolbar)
        self.toolbar = toolbar  # Store reference for resizeEvent
        
        # Open button
        self.open_btn = QToolButton()
        self.open_btn.setText("📂 Open")
        self.open_btn.setToolTip("Open PDF (Ctrl+O)")
        self.open_btn.clicked.connect(self._open_file_dialog)
        toolbar.addWidget(self.open_btn)
        
        toolbar.addSeparator()
        
        # Navigation
        self.prev_btn = QToolButton()
        self.prev_btn.setText("◀")
        self.prev_btn.setToolTip("Previous page")
        self.prev_btn.clicked.connect(self._prev_page)
        self.prev_btn.setEnabled(False)
        toolbar.addWidget(self.prev_btn)
        
        self.page_spin = QSpinBox()
        self.page_spin.setMinimum(1)
        self.page_spin.setMaximum(1)
        self.page_spin.setEnabled(False)
        self.page_spin.valueChanged.connect(self._go_to_page)
        toolbar.addWidget(self.page_spin)
        
        self.page_total_label = QLabel(" / 1")
        toolbar.addWidget(self.page_total_label)
        
        self.next_btn = QToolButton()
        self.next_btn.setText("▶")
        self.next_btn.setToolTip("Next page")
        self.next_btn.clicked.connect(self._next_page)
        self.next_btn.setEnabled(False)
        toolbar.addWidget(self.next_btn)
        
        toolbar.addSeparator()
        
        # TTS Controls
        self.play_btn = QToolButton()
        self.play_btn.setText("▶ Read Page")
        self.play_btn.setObjectName("playButton")
        self.play_btn.setToolTip("Read entire page (Ctrl+R)")
        self.play_btn.clicked.connect(self._play_page)
        self.play_btn.setEnabled(False)
        toolbar.addWidget(self.play_btn)
        
        self.play_sel_btn = QToolButton()
        self.play_sel_btn.setText("📖 Read Selection")
        self.play_sel_btn.setToolTip("Read selected text (Ctrl+Shift+R)")
        self.play_sel_btn.clicked.connect(self._play_selection)
        self.play_sel_btn.setEnabled(False)
        toolbar.addWidget(self.play_sel_btn)
        
        self.pause_btn = QToolButton()
        self.pause_btn.setText("⏸ Pause")
        self.pause_btn.setToolTip("Pause/Resume (Space)")
        self.pause_btn.clicked.connect(self._toggle_pause)
        self.pause_btn.setEnabled(False)
        toolbar.addWidget(self.pause_btn)
        
        self.stop_btn = QToolButton()
        self.stop_btn.setText("⏹ Stop")
        self.stop_btn.setObjectName("stopButton")
        self.stop_btn.setToolTip("Stop reading (Escape)")
        self.stop_btn.clicked.connect(self._stop)
        self.stop_btn.setEnabled(False)
        toolbar.addWidget(self.stop_btn)
        
        toolbar.addSeparator()
        
        # Speed control
        speed_label = QLabel("  Speed: ")
        toolbar.addWidget(speed_label)
        
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setMinimum(50)
        self.speed_slider.setMaximum(200)
        self.speed_slider.setValue(100)
        self.speed_slider.setFixedWidth(100)
        self.speed_slider.setToolTip("Adjust reading speed")
        self.speed_slider.valueChanged.connect(self._update_speed)
        toolbar.addWidget(self.speed_slider)
        
        self.speed_value_label = QLabel("1.0x")
        self.speed_value_label.setObjectName("speedLabel")
        self.speed_value_label.setFixedWidth(40)
        toolbar.addWidget(self.speed_value_label)
        
        toolbar.addSeparator()
        
        # Zoom controls
        zoom_label = QLabel("  Zoom: ")
        toolbar.addWidget(zoom_label)
        
        self.zoom_out_btn = QToolButton()
        self.zoom_out_btn.setText("−")
        self.zoom_out_btn.setObjectName("zoomButton")
        self.zoom_out_btn.setToolTip("Zoom out (Ctrl+-)")
        self.zoom_out_btn.clicked.connect(self._zoom_out)
        self.zoom_out_btn.setEnabled(False)
        toolbar.addWidget(self.zoom_out_btn)
        
        self.zoom_label = QLabel("100%")
        self.zoom_label.setObjectName("zoomLabel")
        self.zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        toolbar.addWidget(self.zoom_label)
        
        self.zoom_in_btn = QToolButton()
        self.zoom_in_btn.setText("+")
        self.zoom_in_btn.setObjectName("zoomButton")
        self.zoom_in_btn.setToolTip("Zoom in (Ctrl++)")
        self.zoom_in_btn.clicked.connect(self._zoom_in)
        self.zoom_in_btn.setEnabled(False)
        toolbar.addWidget(self.zoom_in_btn)
        
        toolbar.addSeparator()
        
        # Theme toggle button
        self.theme_btn = QToolButton()
        self.theme_btn.setText("☀️")  # Sun for switching to light
        self.theme_btn.setObjectName("themeButton")
        self.theme_btn.setToolTip("Switch to Light Mode (Ctrl+T)")
        self.theme_btn.clicked.connect(self._toggle_theme)
        toolbar.addWidget(self.theme_btn)
    
    def _setup_central_widget(self):
        """Setup the central widget."""
        self.stacked_widget = QStackedWidget()
        
        # Welcome screen
        self.welcome_widget = WelcomeWidget(dark_mode=self._dark_mode)
        self.welcome_widget.open_button.clicked.connect(self._open_file_dialog)
        self.stacked_widget.addWidget(self.welcome_widget)
        
        # PDF viewer
        self.pdf_viewer = PDFViewerWidget()
        self.pdf_viewer.text_selected.connect(self._on_text_selected)
        self.stacked_widget.addWidget(self.pdf_viewer)
        
        self.stacked_widget.setCurrentWidget(self.welcome_widget)
        self.setCentralWidget(self.stacked_widget)
    
    def _setup_status_bar(self):
        """Setup the status bar."""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        self.status_label = QLabel("Ready - Open a PDF to get started")
        self.status_bar.addWidget(self.status_label, 1)
        
        self.tts_status_label = QLabel("")
        self.status_bar.addPermanentWidget(self.tts_status_label)
    
    def _connect_signals(self):
        """Connect signals."""
        # PDF signals
        self.pdf_doc.document_loaded.connect(self._on_document_loaded)
        self.pdf_doc.error_occurred.connect(self._on_error)
        
        # TTS signals
        self.tts_engine.speech_started.connect(self._on_speech_started)
        self.tts_engine.speech_finished.connect(self._on_speech_finished)
        self.tts_engine.word_changed.connect(self._on_word_changed)
        self.tts_engine.error_occurred.connect(self._on_error)
    
    # ===== Theme =====
    
    def _toggle_theme(self):
        """Toggle between light and dark mode."""
        self._dark_mode = not self._dark_mode
        self._apply_theme()
        
        # Re-render PDF with new theme
        if self.pdf_doc.is_loaded:
            self._render_current_page()
    
    def _apply_theme(self):
        """Apply current theme to all widgets."""
        # Update PDF handler
        self.pdf_doc.dark_mode = self._dark_mode
        
        # Update stylesheets
        self.setStyleSheet(get_main_stylesheet(self._dark_mode))
        self.welcome_widget.set_dark_mode(self._dark_mode)
        self.pdf_viewer.set_dark_mode(self._dark_mode)
        
        # Update button and menu text
        if self._dark_mode:
            self.theme_btn.setText("☀️")
            self.theme_btn.setToolTip("Switch to Light Mode (Ctrl+T)")
            self.theme_action.setText("Switch to &Light Mode")
        else:
            self.theme_btn.setText("🌙")
            self.theme_btn.setToolTip("Switch to Dark Mode (Ctrl+T)")
            self.theme_action.setText("Switch to &Dark Mode")
    
    # ===== File Operations =====
    
    def _open_file_dialog(self):
        """Open file dialog."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open PDF", "", "PDF Files (*.pdf);;All Files (*)"
        )
        if file_path:
            self._load_pdf(file_path)
    
    def _load_pdf(self, file_path: str):
        """Load a PDF file."""
        self.status_label.setText(f"Loading: {os.path.basename(file_path)}...")
        QApplication.processEvents()
        
        if self.pdf_doc.load(file_path):
            self.stacked_widget.setCurrentWidget(self.pdf_viewer)
            # Delay fit-to-width to ensure viewport is sized
            QTimer.singleShot(50, self._fit_and_render)
    
    def _fit_and_render(self):
        """Fit to width and render after viewport is ready."""
        self._fit_to_width()
        self._render_current_page()
    
    # ===== Navigation =====
    
    def _prev_page(self):
        if self.pdf_doc.prev_page():
            self._render_current_page()
            self._update_page_indicator()
    
    def _next_page(self):
        if self.pdf_doc.next_page():
            self._render_current_page()
            self._update_page_indicator()
    
    def _go_to_page(self, page_num: int):
        if self.pdf_doc.go_to_page(page_num - 1):
            self._render_current_page()
    
    def _render_current_page(self):
        """Render the current page."""
        result = self.pdf_doc.render_page()
        if result[0]:  # pixmap exists
            pixmap, text_spans, scale = result
            self.pdf_viewer.display_page(pixmap, text_spans, scale)
    
    def _update_page_indicator(self):
        self.page_spin.blockSignals(True)
        self.page_spin.setValue(self.pdf_doc.current_page + 1)
        self.page_spin.blockSignals(False)
    
    # ===== Zoom =====
    
    def _zoom_in(self):
        if self.pdf_doc.zoom < 3.0:
            self.pdf_doc.zoom = self.pdf_doc.zoom + 0.25
            self._update_zoom_label()
            self._render_current_page()
    
    def _zoom_out(self):
        if self.pdf_doc.zoom > 0.5:
            self.pdf_doc.zoom = self.pdf_doc.zoom - 0.25
            self._update_zoom_label()
            self._render_current_page()
    
    def _update_zoom_label(self):
        """Update the zoom percentage label."""
        zoom_percent = int(self.pdf_doc.zoom * 100)
        self.zoom_label.setText(f"{zoom_percent}%")
    
    def _fit_to_width(self):
        """Calculate zoom to fit page width to viewer width."""
        page_width, page_height = self.pdf_doc.get_page_size()
        if page_width <= 0:
            return
        
        # Get viewer width (with some padding)
        viewer_width = self.pdf_viewer.scroll_area.viewport().width() - 40
        if viewer_width <= 0:
            viewer_width = 800  # Default if not yet visible
        
        # Calculate zoom: viewer_width = page_width * zoom * 1.5 (render scale)
        # So zoom = viewer_width / (page_width * 1.5)
        optimal_zoom = viewer_width / (page_width * 1.5)
        
        # Clamp to valid range
        optimal_zoom = max(0.5, min(optimal_zoom, 3.0))
        
        # Round to nearest 0.25
        optimal_zoom = round(optimal_zoom * 4) / 4
        
        self.pdf_doc.zoom = optimal_zoom
        self._update_zoom_label()
    
    # ===== TTS Controls =====
    
    def _play_page(self):
        """Read the entire page."""
        if not self.pdf_doc.is_loaded:
            return
        
        text = self.pdf_doc.extract_text()
        if text.strip():
            self.pdf_viewer.reset_read_position()
            self.tts_engine.speak(text)
        else:
            self.status_label.setText("No text found on this page")
    
    def _play_selection(self):
        """Read selected text."""
        selected = self.pdf_viewer.get_selected_text()
        if selected.strip():
            self.pdf_viewer.reset_read_position()
            self.tts_engine.speak(selected)
        else:
            self.status_label.setText("Select text on the PDF first")
    
    def _toggle_pause(self):
        """Toggle pause/resume."""
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
        """Stop reading."""
        self.tts_engine.stop()
        self._update_tts_buttons(False)
        self.pdf_viewer.highlight_text("")
        self.tts_status_label.setText("")
    
    def _update_speed(self, value: int):
        """Update TTS speed."""
        self._current_speed = value / 100.0
        self.speed_value_label.setText(f"{self._current_speed:.1f}x")
        self.tts_engine.set_rate_multiplier(self._current_speed)
    
    def _update_tts_buttons(self, playing: bool):
        """Update TTS button states."""
        self.pause_btn.setEnabled(playing)
        self.stop_btn.setEnabled(playing)
        self.pause_btn.setText("⏸ Pause")
    
    # ===== Signal Handlers =====
    
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
        """Handle text selection."""
        word_count = len(text.split())
        self.status_label.setText(f"Selected {word_count} words - Right-click to copy")
    
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
        """Highlight current words on PDF."""
        self.pdf_viewer.highlight_text(word_chunk)
    
    @pyqtSlot(str)
    def _on_error(self, message: str):
        self.status_label.setText(f"Error: {message}")
    
    # ===== Dialogs =====
    
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
    
    # ===== Drag and Drop =====
    
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
    
    # ===== Keyboard =====
    
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
        else:
            super().keyPressEvent(event)
    
    # ===== Window Events =====
    
    def resizeEvent(self, event):
        """Handle window resize - recalculate fit-to-width if needed."""
        super().resizeEvent(event)
        # Optionally re-fit to width on resize (commented out to preserve manual zoom)
        # if self.pdf_doc.is_loaded:
        #     self._fit_to_width()
        #     self._render_current_page()
    
    # ===== Cleanup =====
    
    def closeEvent(self, event):
        self.tts_engine.cleanup()
        self.pdf_doc.close()
        event.accept()
