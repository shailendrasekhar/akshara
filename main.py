#!/usr/bin/env python3
"""
AKSHARA - PDF Reader with Text-to-Speech
Main application entry point.
"""

import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from src.main_window import MainWindow
from src.splash_screen import SplashController


def main():
    """Main application entry point."""
    # Enable high DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    
    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName("AKSHARA")
    app.setApplicationDisplayName("AKSHARA - PDF Reader")
    app.setOrganizationName("AKSHARA")
    
    # Set default font - classical serif
    font = QFont("Georgia", 10)
    font.setStyleHint(QFont.StyleHint.Serif)
    app.setFont(font)
    
    # Create main window (hidden initially)
    window = MainWindow()
    
    # Handle command line arguments (open PDF directly)
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
        if os.path.isfile(pdf_path) and pdf_path.lower().endswith('.pdf'):
            window._load_pdf(pdf_path)
    
    # Show splash screen with matching theme, then reveal main window
    splash_controller = SplashController(window, dark_mode=window._dark_mode)
    splash_controller.start()
    
    # Run application
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
