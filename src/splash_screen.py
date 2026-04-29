from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve,
    pyqtSignal, QRect, QPoint, QSize,
    QSequentialAnimationGroup, QParallelAnimationGroup,
)
from PyQt6.QtGui import (
    QPainter, QColor, QFont, QPainterPath, QPen, QPixmap,
)
from PyQt6.QtWidgets import (
    QWidget, QApplication, QMainWindow, QGraphicsOpacityEffect,
)


# ---------- Logo widget (pure QPainter, no graphics effects on children) ------

class _Logo(QWidget):
    """
    Circular logo plate. Draws itself; no child widgets, so a single
    QGraphicsOpacityEffect on this widget is safe and unambiguous.
    """

    def __init__(self, size: int, dark: bool, image_path: Path | None = None, parent=None):
        super().__init__(parent)
        self._dark = dark
        self._pixmap: QPixmap | None = None
        if image_path and image_path.exists():
            pm = QPixmap(str(image_path))
            if not pm.isNull():
                self._pixmap = pm
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        ink  = QColor("#ffffff") if self._dark else QColor("#0a0a0a")
        bg   = QColor("#000000") if self._dark else QColor("#ffffff")
        rim  = QColor("#2a2a2a") if self._dark else QColor("#e0e0dc")

        d = min(self.width(), self.height()) - 2
        r = QRect(1, 1, d, d)

        # circle background
        path = QPainterPath()
        path.addEllipse(r.x(), r.y(), r.width(), r.height())
        p.fillPath(path, bg)
        p.setPen(QPen(rim, 1.5))
        p.drawEllipse(r)

        if self._pixmap:
            inset = int(d * 0.18)
            target = r.adjusted(inset, inset, -inset, -inset)
            scaled = self._pixmap.scaled(
                target.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            ox = target.x() + (target.width()  - scaled.width())  // 2
            oy = target.y() + (target.height() - scaled.height()) // 2
            p.drawPixmap(ox, oy, scaled)
        else:
            font = QFont("Georgia", max(10, int(d * 0.42)), QFont.Weight.Light)
            p.setFont(font)
            p.setPen(ink)
            p.drawText(r, Qt.AlignmentFlag.AlignCenter, "A")


# ---------- Full-screen splash overlay ----------------------------------------

class SplashScreen(QWidget):
    """
    Three-phase intro:
      1. Logo fades in, centred on screen.
      2. Brief hold.
      3. Logo shrinks + travels to top-left of main_window while the
         main window fades in beneath it; splash then closes.
    """

    finished = pyqtSignal()

    _LOGO_LARGE = 180   # px — centred phase
    _LOGO_SMALL = 46    # px — corner resting size
    # Logo lands at screen top-left + this offset (splash is a screen overlay)
    _CORNER_X   = 16
    _CORNER_Y   = 54    # below menu bar / title bar

    def __init__(self, main_window: QMainWindow, dark_mode: bool = True):
        super().__init__(None)
        self._win  = main_window
        self._dark = dark_mode

        bg = "#000000" if dark_mode else "#ffffff"
        self.setStyleSheet(f"background:{bg};")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.SplashScreen
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

        screen = QApplication.primaryScreen().availableGeometry()
        self._screen = screen
        self.setGeometry(screen)

        # Logo — large, centred
        logo_path = Path(__file__).resolve().parents[1] / "resources" / "icons" / "logo.png"
        self._logo = _Logo(self._LOGO_LARGE, dark_mode, logo_path, parent=self)

        cx = (screen.width()  - self._LOGO_LARGE) // 2
        cy = (screen.height() - self._LOGO_LARGE) // 2
        self._logo.move(cx, cy)
        self._logo_start_rect = QRect(cx, cy, self._LOGO_LARGE, self._LOGO_LARGE)

        # Wordmark below logo
        ink   = "#ffffff" if dark_mode else "#0a0a0a"
        muted = "#888888" if dark_mode else "#777777"
        from PyQt6.QtWidgets import QLabel
        self._title = QLabel("AKSHARA", self)
        self._title.setStyleSheet(
            f"font-family:Georgia,serif;font-size:36px;font-weight:300;"
            f"letter-spacing:12px;color:{ink};background:transparent;"
        )
        self._title.adjustSize()
        self._title.move(
            (screen.width() - self._title.width()) // 2,
            cy + self._LOGO_LARGE + 20,
        )

        self._sub = QLabel("PDF · FOCUS · ANALYTICS", self)
        self._sub.setStyleSheet(
            f"font-size:11px;letter-spacing:3.5px;color:{muted};background:transparent;"
        )
        self._sub.adjustSize()
        self._sub.move(
            (screen.width() - self._sub.width()) // 2,
            cy + self._LOGO_LARGE + 64,
        )

        # Opacity effect on logo
        self._logo_op = QGraphicsOpacityEffect()
        self._logo_op.setOpacity(0.0)
        self._logo.setGraphicsEffect(self._logo_op)

        self._text_op = QGraphicsOpacityEffect()
        self._text_op.setOpacity(0.0)
        self._title.setGraphicsEffect(self._text_op)

        self._sub_op = QGraphicsOpacityEffect()
        self._sub_op.setOpacity(0.0)
        self._sub.setGraphicsEffect(self._sub_op)

        # Main window opacity for fade-in
        self._win_op = QGraphicsOpacityEffect()
        self._win_op.setOpacity(0.0)
        target = self._win.centralWidget() or self._win
        target.setGraphicsEffect(self._win_op)

    def start(self):
        # Main window is already maximized (set in _setup_window), keep it hidden
        # until the travel phase reveals it
        self._win.hide()
        self.show()
        QTimer.singleShot(100, self._phase_fadein)

    # ---- phase 1: fade in logo + text ----

    def _phase_fadein(self):
        dur = 600

        a_logo = QPropertyAnimation(self._logo_op, b"opacity", self)
        a_logo.setDuration(dur)
        a_logo.setStartValue(0.0); a_logo.setEndValue(1.0)
        a_logo.setEasingCurve(QEasingCurve.Type.OutCubic)

        a_title = QPropertyAnimation(self._text_op, b"opacity", self)
        a_title.setDuration(dur); a_title.setStartValue(0.0); a_title.setEndValue(1.0)
        a_title.setEasingCurve(QEasingCurve.Type.OutCubic)

        a_sub = QPropertyAnimation(self._sub_op, b"opacity", self)
        a_sub.setDuration(dur); a_sub.setStartValue(0.0); a_sub.setEndValue(1.0)
        a_sub.setEasingCurve(QEasingCurve.Type.OutCubic)

        grp = QParallelAnimationGroup(self)
        grp.addAnimation(a_logo)
        grp.addAnimation(a_title)
        grp.addAnimation(a_sub)
        grp.finished.connect(lambda: QTimer.singleShot(500, self._phase_travel))
        grp.start()
        self._fadein_grp = grp

    # ---- phase 2: travel to top-left corner ----

    def _phase_travel(self):
        a_text = QPropertyAnimation(self._text_op, b"opacity", self)
        a_text.setDuration(300); a_text.setStartValue(1.0); a_text.setEndValue(0.0)

        a_sub = QPropertyAnimation(self._sub_op, b"opacity", self)
        a_sub.setDuration(300); a_sub.setStartValue(1.0); a_sub.setEndValue(0.0)

        # Logo travels to screen top-left (splash covers the full screen)
        end_rect = QRect(
            self._screen.x() + self._CORNER_X,
            self._screen.y() + self._CORNER_Y,
            self._LOGO_SMALL, self._LOGO_SMALL,
        )

        a_geom = QPropertyAnimation(self._logo, b"geometry", self)
        a_geom.setDuration(900)
        a_geom.setStartValue(self._logo_start_rect)
        a_geom.setEndValue(end_rect)
        a_geom.setEasingCurve(QEasingCurve.Type.InOutCubic)

        # Reveal maximized main window beneath the splash
        self._win.show()
        a_win = QPropertyAnimation(self._win_op, b"opacity", self)
        a_win.setDuration(900)
        a_win.setStartValue(0.0); a_win.setEndValue(1.0)
        a_win.setEasingCurve(QEasingCurve.Type.OutCubic)

        grp = QParallelAnimationGroup(self)
        grp.addAnimation(a_text)
        grp.addAnimation(a_sub)
        grp.addAnimation(a_geom)
        grp.addAnimation(a_win)
        grp.finished.connect(self._phase_done)
        grp.start()
        self._travel_grp = grp

    def _phase_done(self):
        target = self._win.centralWidget() or self._win
        target.setGraphicsEffect(None)
        self.finished.emit()
        self.close()


# ---------- Controller --------------------------------------------------------

class SplashController:
    def __init__(self, main_window: QMainWindow, dark_mode: bool = True):
        self.main_window = main_window
        self.splash = SplashScreen(main_window, dark_mode=dark_mode)
        self.splash.finished.connect(self._cleanup)

    def start(self):
        self.splash.start()

    def _cleanup(self):
        # Window is already shown and opacity effect removed in _phase_done
        pass
