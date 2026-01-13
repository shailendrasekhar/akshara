"""
Splash Screen Module
Animated splash with white blur reveal effect and accelerating logo.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QGraphicsOpacityEffect, QGraphicsBlurEffect
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtSignal, QSequentialAnimationGroup, QParallelAnimationGroup
from PyQt6.QtGui import QFont, QPainter, QColor


class SplashScreen(QWidget):
    """
    Animated splash screen with white blur reveal and accelerating logo.
    Supports dark/light mode color schemes.
    """
    
    finished = pyqtSignal()  # Emitted when animation completes
    
    def __init__(self, dark_mode: bool = True):
        super().__init__()
        
        self._dark_mode = dark_mode
        
        # Set colors based on mode
        if dark_mode:
            self._bg_color = "#000000"
            self._text_color = "#ffffff"
            self._text_rgb = "255,255,255"
            self._subtitle_color = "#a0a0a0"
            self._subtitle_rgb = "160,160,160"
        else:
            self._bg_color = "#ffffff"
            self._text_color = "#000000"
            self._text_rgb = "0,0,0"
            self._subtitle_color = "#666666"
            self._subtitle_rgb = "102,102,102"
        
        # Frameless, always on top during splash
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.SplashScreen
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        
        self._setup_ui()
        self._setup_animations()
    
    def _setup_ui(self):
        """Build the splash UI."""
        self.setFixedSize(500, 400)
        self.setStyleSheet(f"background-color: {self._bg_color};")
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(16)
        
        # Icon label
        self.icon_label = QLabel("📖")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setStyleSheet(f"font-size: 80px; background: transparent; color: {self._text_color};")
        layout.addWidget(self.icon_label)
        
        # Title label
        self.title_label = QLabel("AKSHARA")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont("Georgia", 42)
        font.setWeight(QFont.Weight.Light)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 12)
        self.title_label.setFont(font)
        self.title_label.setStyleSheet(f"background: transparent; color: {self._text_color};")
        layout.addWidget(self.title_label)
        
        # Subtitle
        self.subtitle_label = QLabel("PDF Reader with Text-to-Speech")
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitle_label.setStyleSheet(
            f"font-size: 13px; letter-spacing: 3px; background: transparent; color: {self._subtitle_color};"
        )
        layout.addWidget(self.subtitle_label)
        
        # --- Effects for blur reveal ---
        # Blur effect on icon
        self.icon_blur = QGraphicsBlurEffect()
        self.icon_blur.setBlurRadius(30)
        self.icon_label.setGraphicsEffect(self.icon_blur)
        
        # Blur effect on title
        self.title_blur = QGraphicsBlurEffect()
        self.title_blur.setBlurRadius(30)
        self.title_label.setGraphicsEffect(self.title_blur)
        
        # Blur effect on subtitle
        self.subtitle_blur = QGraphicsBlurEffect()
        self.subtitle_blur.setBlurRadius(30)
        self.subtitle_label.setGraphicsEffect(self.subtitle_blur)
        
        # Opacity for fade-in
        self.icon_opacity = QGraphicsOpacityEffect()
        self.icon_opacity.setOpacity(0)
        
        self.title_opacity = QGraphicsOpacityEffect()
        self.title_opacity.setOpacity(0)
        
        self.subtitle_opacity = QGraphicsOpacityEffect()
        self.subtitle_opacity.setOpacity(0)
        
        # Center on screen
        self._center_on_screen()
    
    def _center_on_screen(self):
        """Center the splash on the primary screen."""
        from PyQt6.QtWidgets import QApplication
        screen = QApplication.primaryScreen().availableGeometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)
    
    def _setup_animations(self):
        """Setup smooth blur-to-clear reveal with gentle easing."""
        # Animate blur radius from 40 -> 0 using QTimer steps
        # Combined with opacity fade-in for smoother feel
        
        self._blur_steps = 0
        self._max_blur_steps = 60  # More steps for smoother animation
        self._initial_blur = 40.0
        self._initial_opacity = 0.0
        
        # Timer for blur animation (consistent smooth timing)
        self._blur_timer = QTimer(self)
        self._blur_timer.timeout.connect(self._animate_blur_step)
        
        # Final finish timer
        self._finish_timer = QTimer(self)
        self._finish_timer.setSingleShot(True)
        self._finish_timer.timeout.connect(self._on_animation_complete)
    
    def start(self):
        """Start the splash animation."""
        # Start with elements invisible (using rgba with 0 alpha)
        self.icon_label.setStyleSheet(f"font-size: 80px; background: transparent; color: rgba({self._text_rgb},0);")
        self.title_label.setStyleSheet(f"background: transparent; color: rgba({self._text_rgb},0);")
        self.subtitle_label.setStyleSheet(f"font-size: 13px; letter-spacing: 3px; background: transparent; color: rgba({self._subtitle_rgb},0);")
        
        self.show()
        # Start blur reveal after a brief pause
        QTimer.singleShot(300, self._start_blur_animation)
    
    def _start_blur_animation(self):
        """Begin the smooth blur-to-clear animation."""
        self._blur_steps = 0
        # Consistent 25ms interval for smooth 60-step animation (~1.5s total)
        self._blur_timer.start(25)
    
    def _ease_out_cubic(self, t: float) -> float:
        """Cubic ease-out: fast start, gentle slow finish."""
        return 1 - pow(1 - t, 3)
    
    def _ease_in_out_sine(self, t: float) -> float:
        """Sine ease-in-out: very smooth and gentle."""
        import math
        return -(math.cos(math.pi * t) - 1) / 2
    
    def _animate_blur_step(self):
        """Animate one step of blur reduction with smooth easing."""
        self._blur_steps += 1
        progress = self._blur_steps / self._max_blur_steps
        
        # Use smooth ease-out curve for gentle deceleration
        eased_progress = self._ease_out_cubic(progress)
        
        # Calculate current blur radius (decreasing)
        current_blur = self._initial_blur * (1 - eased_progress)
        current_blur = max(0, current_blur)
        
        # Calculate opacity (increasing) - use sine for extra smoothness
        opacity_progress = self._ease_in_out_sine(min(progress * 1.2, 1.0))  # Slightly faster fade-in
        
        # Apply blur to all elements
        self.icon_blur.setBlurRadius(current_blur)
        self.title_blur.setBlurRadius(current_blur)
        self.subtitle_blur.setBlurRadius(current_blur)
        
        # Apply opacity via stylesheet color alpha
        icon_alpha = int(255 * opacity_progress)
        text_alpha = int(255 * opacity_progress)
        subtitle_alpha = int(255 * opacity_progress)
        
        self.icon_label.setStyleSheet(f"font-size: 80px; background: transparent; color: rgba({self._text_rgb},{icon_alpha});")
        self.title_label.setStyleSheet(f"background: transparent; color: rgba({self._text_rgb},{text_alpha});")
        self.subtitle_label.setStyleSheet(f"font-size: 13px; letter-spacing: 3px; background: transparent; color: rgba({self._subtitle_rgb},{subtitle_alpha});")
        
        if self._blur_steps >= self._max_blur_steps:
            self._blur_timer.stop()
            # Hold for a moment, then finish
            self._finish_timer.start(800)
    
    def _on_animation_complete(self):
        """Called when animation is done - emit signal and hide."""
        self.finished.emit()
        self.close()


class SplashController:
    """
    Controller to manage splash -> main window transition.
    """
    
    def __init__(self, main_window, dark_mode: bool = True):
        self.main_window = main_window
        self.splash = SplashScreen(dark_mode=dark_mode)
        self.splash.finished.connect(self._show_main_window)
    
    def start(self):
        """Show splash and start animation."""
        self.splash.start()
    
    def _show_main_window(self):
        """Show main window after splash completes."""
        self.main_window.show()
        # Optionally start minimized then restore for "taskbar sit" effect
        # self.main_window.showMinimized()
        # QTimer.singleShot(100, self.main_window.showNormal)
