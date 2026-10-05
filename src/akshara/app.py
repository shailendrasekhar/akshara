"""Application entry point."""

from __future__ import annotations

import argparse
import os
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication

from . import APP_ID, APP_NAME, __version__


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="akshara", description="Focused PDF reader with TTS")
    parser.add_argument("pdf", nargs="?", help="PDF file to open")
    parser.add_argument("--no-splash", action="store_true", help="skip the splash animation")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    # Qt consumes its own flags (e.g. -platform); ignore anything we don't know.
    args, _ = parser.parse_known_args(argv)
    return args


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv if argv is None else argv
    args = parse_args(argv[1:])

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setOrganizationName(APP_NAME)
    app.setDesktopFileName(APP_ID)

    font = QFont("Georgia", 10)
    font.setStyleHint(QFont.StyleHint.Serif)
    app.setFont(font)

    # Imported late so --help/--version work without building any widgets.
    from .main_window import MainWindow
    from .splash_screen import SplashController

    window = MainWindow()

    if args.pdf and os.path.isfile(args.pdf) and args.pdf.lower().endswith(".pdf"):
        window._load_pdf(os.path.abspath(args.pdf))

    if args.no_splash:
        window.showMaximized()
    else:
        splash = SplashController(window, dark_mode=window._dark_mode)
        splash.start()

    return app.exec()
