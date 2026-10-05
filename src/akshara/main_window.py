"""Main application window: wires the document, viewer, speech and panels together."""

from __future__ import annotations

import os
import time
from collections.abc import Callable

from PyQt6.QtCore import QSize, Qt, QTimer, pyqtSlot
from PyQt6.QtGui import QAction, QActionGroup, QCloseEvent, QKeySequence
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QDockWidget,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QStatusBar,
    QTabWidget,
    QTextBrowser,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from . import APP_NAME, __version__
from .analytics import AnalyticsDialog
from .db import Store
from .findbar import DocumentSearch, FindBar
from .library import LibraryPanel
from .notify import notify
from .pdf_handler import LoadResult, PDFDocument
from .pdf_viewer import PDFViewerWidget
from .pomodoro import PHASE_LABELS, PomodoroPanel
from .settings import Settings
from .settings_dialog import SettingsDialog
from .sidebar import BookmarksPanel, NotesPanel, OutlinePanel
from .tts import ENGINES, SpeechEngine, State, Utterance, Voice, create_engine
from .tts.kokoro import VOICES as KOKORO_VOICES
from .tts.reader import ReadAloud
from .ui.theme import (
    TEXT_SIZES,
    THEME_MODES,
    Palette,
    page_colors_for,
    resolve_palette,
    stylesheet,
)
from .welcome import WelcomeWidget

HIGHLIGHT_COLORS = {
    "Yellow": "#facc15",
    "Green": "#4ade80",
    "Blue": "#60a5fa",
    "Pink": "#f472b6",
}


def _checkable_action(text: str, parent) -> QAction:
    act = QAction(text, parent)
    act.setCheckable(True)
    return act


def _add_menu(parent, title: str) -> QMenu:
    menu = parent.addMenu(title)
    assert menu is not None
    return menu


class MainWindow(QMainWindow):
    def __init__(self, settings: Settings | None = None, store: Store | None = None):
        super().__init__()
        self.settings = settings or Settings()
        self.store = store or Store()
        self.pdf_doc = PDFDocument(self)
        self.palette_: Palette = resolve_palette(self.settings.theme)

        self._active_doc_id: str | None = None
        self._page_dwell_started_at: float | None = None
        self._dwell_page = 0
        self._closed = False
        self._focus_mode = False
        self._pre_focus_state: tuple[bool, bool, bool, bool] | None = None
        self._actions: dict[str, QAction] = {}
        self._bookmarked: set[int] = set()
        self._pending_resume: int | None = None

        # Speech
        self.tts_engine: SpeechEngine | None = None
        self.reader: ReadAloud | None = None
        self._init_speech()

        # Panels & widgets
        self.pomodoro = PomodoroPanel(self.store)
        self._configure_pomodoro()
        self.library = LibraryPanel(self.store, self.palette_, sort=self.settings.library_sort)
        self.outline = OutlinePanel()
        self.bookmarks = BookmarksPanel()
        self.notes = NotesPanel()
        self.search = DocumentSearch(self.pdf_doc, self)

        self._save_pos_timer = QTimer(self)
        self._save_pos_timer.setSingleShot(True)
        self._save_pos_timer.setInterval(800)
        self._save_pos_timer.timeout.connect(self._save_position)
        # Owned by the window so it can never fire after the window is gone.
        self._tts_status_timer = QTimer(self)
        self._tts_status_timer.setSingleShot(True)
        self._tts_status_timer.setInterval(2500)
        self._tts_status_timer.timeout.connect(self._clear_tts_status)

        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(820, 560)
        self.setAcceptDrops(True)
        self._build_central()
        self._build_docks()
        self._build_actions()
        self._build_menus()
        self._build_toolbar()
        self._build_status_bar()
        self._connect()

        self._apply_theme()
        self._apply_text_size()
        self._restore_window()
        self._update_doc_actions()
        self.welcome.set_recent(self.settings.recent_files)

        # Follow the desktop's light/dark switch live.
        hints = QApplication.styleHints()
        if hints is not None:
            hints.colorSchemeChanged.connect(lambda _: self._on_system_scheme())

    # ======================================================================
    # Construction
    # ======================================================================

    def _init_speech(self) -> None:
        engine = create_engine(self.settings.tts_engine, self)
        self._set_engine(engine)

    def _set_engine(self, engine: SpeechEngine | None) -> None:
        old = self.tts_engine
        self.tts_engine = engine
        if engine is None:
            if self.reader is not None:
                self.reader.stop()
            self.reader = None
        else:
            voice = self.settings.tts_voice
            if voice and any(v.id == voice for v in engine.voices()):
                engine.set_voice(voice)
            engine.set_rate(self.settings.tts_rate)
            if self.reader is None:
                self.reader = ReadAloud(
                    engine,
                    page_text=self.pdf_doc.page_text,
                    page_count=lambda: self.pdf_doc.page_count,
                    parent=self,
                )
            else:
                self.reader.set_engine(engine)
            self.reader.continuous = self.settings.tts_continuous
            if self.settings.tts_preload:
                engine.preload()
        if old is not None and old is not engine:
            old.shutdown()
            old.deleteLater()

    def _configure_pomodoro(self) -> None:
        s = self.settings
        self.pomodoro.configure(
            s.pomodoro_focus_min,
            s.pomodoro_short_min,
            s.pomodoro_long_min,
            s.pomodoro_cycles,
            s.pomodoro_auto_break,
        )

    def _build_central(self) -> None:
        self.welcome = WelcomeWidget(self.palette_)
        self.pdf_viewer = PDFViewerWidget()
        self.pdf_viewer.set_highlight_provider(self._highlights_for_page)
        self.find_bar = FindBar()
        self.find_bar.hide()

        reader_page = QWidget()
        lay = QVBoxLayout(reader_page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self.find_bar)
        lay.addWidget(self.pdf_viewer, 1)

        self.stacked_widget = QStackedWidget()
        self.stacked_widget.addWidget(self.welcome)
        self.stacked_widget.addWidget(reader_page)
        self._reader_page = reader_page
        self.setCentralWidget(self.stacked_widget)

    def _build_docks(self) -> None:
        self.sidebar_tabs = QTabWidget()
        self.sidebar_tabs.setDocumentMode(True)
        tab_bar = self.sidebar_tabs.tabBar()
        if tab_bar is not None:
            tab_bar.setExpanding(True)
            tab_bar.setUsesScrollButtons(False)
            tab_bar.setElideMode(Qt.TextElideMode.ElideRight)
        self.sidebar_tabs.addTab(self.library, "LIBRARY")
        self.sidebar_tabs.addTab(self.outline, "CONTENTS")
        self.sidebar_tabs.addTab(self.bookmarks, "MARKS")
        self.sidebar_tabs.addTab(self.notes, "NOTES")

        self._sidebar_dock = self._dock("SIDEBAR", "sidebarDock", self.sidebar_tabs, 260)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self._sidebar_dock)
        self._pomodoro_dock = self._dock("POMODORO", "pomodoroDock", self.pomodoro, 240)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._pomodoro_dock)
        # Kept for compatibility with code/tests that referred to the old dock.
        self._library_dock = self._sidebar_dock

    def _dock(self, title: str, name: str, widget: QWidget, min_w: int) -> QDockWidget:
        dock = QDockWidget(title, self)
        dock.setObjectName(name)
        dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
            | QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        dock.setWidget(widget)
        dock.setMinimumWidth(min_w)
        return dock

    # ---- actions ----

    def _act(
        self,
        key: str,
        text: str,
        slot: Callable | None = None,
        shortcut: str | QKeySequence | QKeySequence.StandardKey | list | None = None,
        checkable: bool = False,
        tip: str = "",
    ) -> QAction:
        a = QAction(text, self)
        if shortcut is not None:
            if isinstance(shortcut, list):
                a.setShortcuts([QKeySequence(s) for s in shortcut])
            else:
                a.setShortcut(QKeySequence(shortcut))
        a.setCheckable(checkable)
        if tip:
            a.setStatusTip(tip)
        if slot is not None:
            a.triggered.connect(slot)
        # Window-wide shortcuts even when focus is in a dock.
        a.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
        self.addAction(a)
        self._actions[key] = a
        return a

    def action(self, key: str) -> QAction:
        return self._actions[key]

    def _build_actions(self) -> None:
        A = self._act
        SK = QKeySequence.StandardKey
        # File
        A("open", "&Open…", self._open_file_dialog, SK.Open)
        A("close_doc", "&Close Document", self.close_document, SK.Close)
        A("export_notes", "&Export Notes as Markdown…", self._export_notes)
        A("quit", "&Quit", self.close, SK.Quit)
        # Edit
        A("copy", "&Copy", self._copy, SK.Copy)
        A("select_all", "Select &All on Page", self.pdf_viewer.select_all_on_page, SK.SelectAll)
        A("find", "&Find…", self._open_find, SK.Find)
        A("find_next", "Find &Next", self._find_next, "F3")
        A("find_prev", "Find &Previous", self._find_prev, "Shift+F3")
        A("prefs", "&Preferences…", self._show_preferences, "Ctrl+,")
        # View
        A("zoom_in", "Zoom &In", self.pdf_viewer.zoom_in, [SK.ZoomIn, "Ctrl+="])
        A("zoom_out", "Zoom &Out", self.pdf_viewer.zoom_out, SK.ZoomOut)
        A("zoom_reset", "&Actual Size", lambda: self.pdf_viewer.set_zoom(1.0), "Ctrl+0")
        A("fit_width", "Fit &Width", lambda: self._set_fit("width"), "Ctrl+1", checkable=True)
        A("fit_page", "Fit &Page", lambda: self._set_fit("page"), "Ctrl+2", checkable=True)
        fit_group = QActionGroup(self)
        for k in ("fit_width", "fit_page"):
            fit_group.addAction(self.action(k))
        fit_group.setExclusionPolicy(QActionGroup.ExclusionPolicy.ExclusiveOptional)
        A("toggle_theme", "Cycle &Theme", self._cycle_theme, "Ctrl+T")
        A("page_colors", "&Recolour Pages to Match Theme", self._toggle_page_colors, checkable=True)
        A("text_size", "Cycle Interface &Text Size", self._cycle_text_size, "Ctrl+Shift+T")
        A("sidebar", "&Sidebar", self._toggle_sidebar, "F9", checkable=True)
        A("show_pomodoro", "&Pomodoro Panel", self._toggle_pomodoro_dock, "F10", checkable=True)
        A("fullscreen", "&Full Screen", self._toggle_fullscreen, "F11", checkable=True)
        A("focus_mode", "F&ocus Mode", self._toggle_focus_mode, "Ctrl+Shift+F", checkable=True)
        # Go
        A("prev_page", "&Previous Page", self._prev_page, [Qt.Key.Key_Left, "Ctrl+Up"])
        A("next_page", "&Next Page", self._next_page, [Qt.Key.Key_Right, "Ctrl+Down"])
        A("first_page", "&First Page", lambda: self.pdf_viewer.go_to_page(0), "Ctrl+Home")
        A(
            "last_page",
            "&Last Page",
            lambda: self.pdf_viewer.go_to_page(self.pdf_doc.page_count - 1),
            "Ctrl+End",
        )
        A("goto_page", "&Go to Page…", self._ask_page, "Ctrl+G")
        A(
            "bookmark",
            "Toggle &Bookmark",
            lambda: self._toggle_bookmark(self.pdf_viewer.current_page),
            "Ctrl+B",
        )
        A("next_bookmark", "Next Bookmark", lambda: self._jump_bookmark(+1), "Ctrl+Alt+Down")
        A("prev_bookmark", "Previous Bookmark", lambda: self._jump_bookmark(-1), "Ctrl+Alt+Up")
        # Speech
        A("play_pause", "&Play / Pause", self._play_or_pause, "Space")
        A("read_page", "Read &Page", self._play_page, "Ctrl+R")
        A("read_selection", "Read &Selection", self._play_selection, "Ctrl+Shift+R")
        A("stop", "S&top / Close", self._escape, "Escape")
        A("faster", "&Faster", lambda: self._nudge_speed(+0.1), "Ctrl+]")
        A("slower", "S&lower", lambda: self._nudge_speed(-0.1), "Ctrl+[")
        A("continuous", "&Continue onto Next Page", self._toggle_continuous, checkable=True)
        # Tools
        A("analytics", "&Analytics…", self._show_analytics, "Ctrl+Shift+A")
        A("pomodoro", "Start / Pause &Pomodoro", self.pomodoro.toggle, "Ctrl+P")
        # Help
        A("shortcuts", "&Keyboard Shortcuts", self._show_shortcuts, SK.HelpContents)
        A("about", "&About Akshara", self._show_about)

        self.action("page_colors").setChecked(self.settings.page_colors == "match")
        self.action("continuous").setChecked(self.settings.tts_continuous)

    def _build_menus(self) -> None:
        mb = self.menuBar()
        a = self.action

        file_menu = _add_menu(mb, "&File")
        file_menu.addAction(a("open"))
        self.recent_menu = _add_menu(file_menu, "Open &Recent")
        self.recent_menu.aboutToShow.connect(self._fill_recent_menu)
        file_menu.addAction(a("close_doc"))
        file_menu.addSeparator()
        file_menu.addAction(a("export_notes"))
        file_menu.addSeparator()
        file_menu.addAction(a("quit"))

        edit = _add_menu(mb, "&Edit")
        self._fill_menu(
            edit, ("copy", "select_all", None, "find", "find_next", "find_prev", None, "prefs")
        )

        view = _add_menu(mb, "&View")
        self._fill_menu(view, ("zoom_in", "zoom_out", "zoom_reset", "fit_width", "fit_page", None))
        self.theme_menu = _add_menu(view, "T&heme")
        self._theme_group = QActionGroup(self)
        for key, label in THEME_MODES.items():
            act = _checkable_action(label, self)
            act.setData(key)
            act.setChecked(self.settings.theme == key)
            act.triggered.connect(lambda _=False, k=key: self._set_theme(k))
            self._theme_group.addAction(act)
            self.theme_menu.addAction(act)
        self._fill_menu(
            view,
            (
                "toggle_theme",
                "page_colors",
                "text_size",
                None,
                "sidebar",
                "show_pomodoro",
                "fullscreen",
                "focus_mode",
            ),
        )

        go = _add_menu(mb, "&Go")
        self._fill_menu(
            go,
            (
                "prev_page",
                "next_page",
                "first_page",
                "last_page",
                "goto_page",
                None,
                "bookmark",
                "next_bookmark",
                "prev_bookmark",
            ),
        )

        speech = _add_menu(mb, "&Speech")
        self._fill_menu(
            speech,
            (
                "play_pause",
                "read_page",
                "read_selection",
                "stop",
                None,
                "faster",
                "slower",
                "continuous",
            ),
        )
        self.voice_menu = _add_menu(speech, "&Voice")
        self.voice_menu.aboutToShow.connect(self._fill_voice_menu)

        tools = _add_menu(mb, "&Tools")
        tools.addAction(a("analytics"))
        tools.addAction(a("pomodoro"))

        help_menu = _add_menu(mb, "&Help")
        help_menu.addAction(a("shortcuts"))
        help_menu.addAction(a("about"))

    def _fill_menu(self, menu: QMenu, keys: tuple) -> None:
        for k in keys:
            if k is None:
                menu.addSeparator()
            else:
                menu.addAction(self.action(k))

    def _tool_button(
        self, text: str, tip: str, slot=None, name: str = "", checkable=False
    ) -> QToolButton:
        b = QToolButton()
        b.setText(text)
        b.setToolTip(tip)
        b.setCheckable(checkable)
        if name:
            b.setObjectName(name)
        if slot is not None:
            b.clicked.connect(slot)
        return b

    def _build_toolbar(self) -> None:
        tb = QToolBar("Main toolbar")
        tb.setObjectName("mainToolbar")
        tb.setMovable(False)
        tb.setFloatable(False)
        tb.setIconSize(QSize(16, 16))
        self.addToolBar(tb)
        self._toolbar = tb

        self.sidebar_btn = self._tool_button(
            "☰", "Sidebar  F9", self._toggle_sidebar, "flatButton", True
        )
        tb.addWidget(self.sidebar_btn)
        self.open_btn = self._tool_button("Open", "Open PDF  Ctrl+O", self._open_file_dialog)
        tb.addWidget(self.open_btn)
        tb.addSeparator()

        self.prev_btn = self._tool_button("‹", "Previous page  ←", self._prev_page)
        tb.addWidget(self.prev_btn)
        self.page_spin = QSpinBox()
        self.page_spin.setRange(1, 1)
        self.page_spin.setFixedWidth(64)
        self.page_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.page_spin.setKeyboardTracking(False)
        self.page_spin.valueChanged.connect(self._go_to_page)
        tb.addWidget(self.page_spin)
        self.page_total_label = QLabel("/ –")
        self.page_total_label.setObjectName("mono")
        tb.addWidget(self.page_total_label)
        self.next_btn = self._tool_button("›", "Next page  →", self._next_page)
        tb.addWidget(self.next_btn)
        tb.addSeparator()

        self.play_btn = self._tool_button(
            "▶  Read", "Read aloud from this page  Space", self._play_or_pause, "accentButton"
        )
        tb.addWidget(self.play_btn)
        self.stop_btn = self._tool_button("■", "Stop  Esc", self._stop, "stopButton")
        tb.addWidget(self.stop_btn)
        speed = QWidget()
        sl = QHBoxLayout(speed)
        sl.setContentsMargins(8, 0, 4, 0)
        sl.setSpacing(6)
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(50, 200)
        self.speed_slider.setFixedWidth(88)
        self.speed_slider.setToolTip("Reading speed  Ctrl+[ / Ctrl+]")
        self.speed_slider.setValue(round(self.settings.tts_rate * 100))
        self.speed_slider.valueChanged.connect(self._update_speed)
        sl.addWidget(self.speed_slider)
        self.speed_value_label = QLabel(f"{self.settings.tts_rate:.1f}×")
        self.speed_value_label.setObjectName("mono")
        self.speed_value_label.setFixedWidth(40)
        sl.addWidget(self.speed_value_label)
        tb.addWidget(speed)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)

        self.find_btn = self._tool_button(
            "Find", "Find in document  Ctrl+F", self._open_find, "flatButton"
        )
        tb.addWidget(self.find_btn)
        self.bookmark_btn = self._tool_button(
            "☆",
            "Bookmark page  Ctrl+B",
            lambda: self._toggle_bookmark(self.pdf_viewer.current_page),
            "flatButton",
        )
        tb.addWidget(self.bookmark_btn)
        tb.addSeparator()

        self.zoom_out_btn = self._tool_button("−", "Zoom out  Ctrl+−", self.pdf_viewer.zoom_out)
        tb.addWidget(self.zoom_out_btn)
        self.zoom_btn = self._tool_button("100%", "Zoom options", name="flatButton")
        self.zoom_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        zoom_menu = QMenu(self.zoom_btn)
        for k in ("fit_width", "fit_page", "zoom_reset"):
            zoom_menu.addAction(self.action(k))
        zoom_menu.addSeparator()
        for z in (0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0):
            zoom_menu.addAction(f"{int(z * 100)}%", lambda zz=z: self.pdf_viewer.set_zoom(zz))
        self.zoom_btn.setMenu(zoom_menu)
        self.zoom_btn.setMinimumWidth(58)
        tb.addWidget(self.zoom_btn)
        self.zoom_in_btn = self._tool_button("+", "Zoom in  Ctrl++", self.pdf_viewer.zoom_in)
        tb.addWidget(self.zoom_in_btn)
        tb.addSeparator()

        self.text_size_btn = self._tool_button(
            "TM", "Interface text size  Ctrl+Shift+T", self._cycle_text_size, "flatButton"
        )
        tb.addWidget(self.text_size_btn)
        self.theme_btn = self._tool_button(
            "◐", "Cycle theme  Ctrl+T", self._cycle_theme, "flatButton"
        )
        tb.addWidget(self.theme_btn)

    def _build_status_bar(self) -> None:
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_label = QLabel("Ready — open a PDF to get started")
        self.status_bar.addWidget(self.status_label, 1)
        self.tts_status_label = QLabel("")
        self.status_bar.addPermanentWidget(self.tts_status_label)
        self.pomodoro_status = QLabel("")
        self.status_bar.addPermanentWidget(self.pomodoro_status)
        self.progress_label = QLabel("")
        self.status_bar.addPermanentWidget(self.progress_label)

    def _connect(self) -> None:
        v = self.pdf_viewer
        self.pdf_doc.error_occurred.connect(self._on_error)
        v.current_page_changed.connect(self._on_visible_page_changed)
        v.zoom_changed.connect(self._on_zoom_changed)
        v.selection_changed.connect(self._on_selection_changed)
        v.read_from_requested.connect(self._read_from)
        v.read_range_requested.connect(self._read_range)
        v.highlight_requested.connect(self._add_highlight)
        v.highlight_edit_requested.connect(self._edit_highlight_note)
        v.highlight_remove_requested.connect(self._remove_highlight)
        v.search_requested.connect(lambda t: self._open_find(t))
        v.bookmark_toggle_requested.connect(self._toggle_bookmark)

        self.welcome.open_requested.connect(self._open_file_dialog)
        self.welcome.open_path.connect(self._load_pdf)
        self.library.open_document.connect(self._load_pdf)
        self.library.document_removed.connect(self._on_document_removed)
        self.library.sort_changed.connect(lambda s: setattr(self.settings, "library_sort", s))
        self.outline.navigate.connect(lambda p: self.pdf_viewer.go_to_page(p))
        self.bookmarks.navigate.connect(lambda p: self.pdf_viewer.go_to_page(p))
        self.bookmarks.remove_requested.connect(self._toggle_bookmark)
        self.bookmarks.note_changed.connect(self._set_bookmark_note)
        self.notes.navigate.connect(lambda p, y: self.pdf_viewer.go_to_page(p, max(0.0, y - 24)))
        self.notes.edit_requested.connect(self._edit_highlight_note)
        self.notes.remove_requested.connect(self._remove_highlight)

        self.find_bar.search_changed.connect(self.search.start)
        self.find_bar.next_requested.connect(self._find_next)
        self.find_bar.previous_requested.connect(self._find_prev)
        self.find_bar.closed.connect(self._close_find)
        self.search.results_changed.connect(self._on_search_results)
        self.search.current_changed.connect(self._on_search_current)

        self.pomodoro.phase_completed.connect(self._on_phase_completed)
        self.pomodoro.next_phase.connect(self._on_next_phase)
        self.pomodoro.running_changed.connect(lambda _: self._update_pomodoro_status())
        self._pomodoro_tick = QTimer(self)
        self._pomodoro_tick.setInterval(1000)
        self._pomodoro_tick.timeout.connect(self._update_pomodoro_status)
        self._pomodoro_tick.start()

        self._sidebar_dock.visibilityChanged.connect(self._sync_toggle_states)
        self._pomodoro_dock.visibilityChanged.connect(self._sync_toggle_states)
        self._connect_reader()

    def _connect_reader(self) -> None:
        if self.reader is None:
            return
        r = self.reader
        r.state_changed.connect(self._on_tts_state)
        r.finished.connect(self._on_speech_finished)
        r.highlight.connect(self.pdf_viewer.highlight_range)
        r.words_spoken.connect(self._on_words_spoken)
        r.error_occurred.connect(self._on_error)
        self._on_tts_state(int(r.state))

    # ======================================================================
    # Documents
    # ======================================================================

    def _open_file_dialog(self) -> None:
        start = os.path.dirname(self.settings.recent_files[0]) if self.settings.recent_files else ""
        path, _ = QFileDialog.getOpenFileName(
            self, "Open PDF", start, "PDF Files (*.pdf);;All Files (*)"
        )
        if path:
            self._load_pdf(path)

    def open_file(self, file_path: str) -> bool:
        return self._load_pdf(file_path)

    def _load_pdf(self, file_path: str) -> bool:
        file_path = os.path.abspath(file_path)
        if not os.path.isfile(file_path):
            self._on_error(f"File not found: {file_path}")
            return False
        self._leave_document()
        self.status_label.setText(f"Opening {os.path.basename(file_path)}…")

        result = self.pdf_doc.load(file_path)
        password: str | None = None
        while result in (LoadResult.NEEDS_PASSWORD, LoadResult.WRONG_PASSWORD):
            prompt = (
                "This PDF is password protected."
                if result == LoadResult.NEEDS_PASSWORD
                else "Wrong password — try again."
            )
            password, ok = QInputDialog.getText(
                self, "Password required", prompt, QLineEdit.EchoMode.Password
            )
            if not ok:
                self.status_label.setText("Opening cancelled")
                return False
            result = self.pdf_doc.load(file_path, password)
        if result != LoadResult.OK:
            return False

        self._active_doc_id = self.store.upsert_document(
            file_path=file_path,
            title=self.pdf_doc.title,
            author=self.pdf_doc.author,
            pages=self.pdf_doc.page_count,
        )
        row = self.store.get_document(self._active_doc_id)
        self.pomodoro.set_active_document(self._active_doc_id)
        self.settings.add_recent(file_path)
        self.settings.last_document = file_path
        self.welcome.set_recent(self.settings.recent_files)

        self.stacked_widget.setCurrentWidget(self._reader_page)
        fit = self.settings.fit_mode
        zoom = row.zoom if (fit == "custom" and row and row.zoom) else None
        self.pdf_viewer.load(self.pdf_doc, zoom=zoom, fit_mode=fit)
        self._apply_page_colors()

        count = self.pdf_doc.page_count
        self.page_spin.blockSignals(True)
        self.page_spin.setRange(1, count)
        self.page_spin.setValue(1)
        self.page_spin.blockSignals(False)
        self.page_total_label.setText(f"/ {count}")
        self.setWindowTitle(f"{self.pdf_doc.title} — {APP_NAME}")

        self.outline.set_outline(self.pdf_doc.outline())
        self._refresh_bookmarks()
        self._refresh_notes()
        self.library.refresh()
        self.library.set_active_path(file_path)
        self._update_doc_actions()

        self._dwell_page = 0
        self._page_dwell_started_at = time.time()
        self.status_label.setText(f"{self.pdf_doc.title} — {count} pages")
        # Resume where the reader left off (last_page is stored 1-based).
        if row and 1 < row.last_page <= count:
            # Defer until the viewport has its final size so fit-zoom is right.
            self._pending_resume = row.last_page - 1
            QTimer.singleShot(0, self._apply_resume)
            self.status_label.setText(f"Resumed at page {row.last_page}")
        return True

    def _apply_resume(self) -> None:
        if self._pending_resume is not None and not self._closed:
            self.pdf_viewer.go_to_page(self._pending_resume)
        self._pending_resume = None

    def _leave_document(self) -> None:
        """Flush state for the current document before switching or closing."""
        if self.reader is not None:
            self.reader.stop()
        self._record_dwell(self._dwell_page)
        self._save_position()
        self.search.clear()
        self.find_bar.hide()

    def close_document(self) -> None:
        if not self.pdf_doc.is_loaded:
            return
        self._leave_document()
        self.pdf_viewer.clear()
        self.pdf_doc.close()
        self._active_doc_id = None
        self.pomodoro.set_active_document(None)
        self.settings.last_document = ""
        self.outline.set_outline([])
        self.bookmarks.set_bookmarks([])
        self.notes.set_highlights([])
        self.library.set_active_path("")
        self.stacked_widget.setCurrentWidget(self.welcome)
        self.setWindowTitle(APP_NAME)
        self.progress_label.setText("")
        self.page_total_label.setText("/ –")
        self.status_label.setText("Ready — open a PDF to get started")
        self._update_doc_actions()

    def _on_document_removed(self, doc_id: str) -> None:
        if doc_id == self._active_doc_id:
            self.close_document()

    def _update_doc_actions(self) -> None:
        loaded = self.pdf_doc.is_loaded
        for k in (
            "close_doc",
            "export_notes",
            "copy",
            "select_all",
            "find",
            "find_next",
            "find_prev",
            "zoom_in",
            "zoom_out",
            "zoom_reset",
            "fit_width",
            "fit_page",
            "prev_page",
            "next_page",
            "first_page",
            "last_page",
            "goto_page",
            "bookmark",
            "next_bookmark",
            "prev_bookmark",
            "read_page",
            "read_selection",
        ):
            self.action(k).setEnabled(loaded)
        for w in (
            self.prev_btn,
            self.next_btn,
            self.page_spin,
            self.find_btn,
            self.bookmark_btn,
            self.zoom_in_btn,
            self.zoom_out_btn,
            self.zoom_btn,
        ):
            w.setEnabled(loaded)
        self.play_btn.setEnabled(loaded and self.reader is not None)
        if self.reader is None:
            self.stop_btn.setEnabled(False)
        if self.reader is None:
            self.play_btn.setToolTip("Text-to-speech unavailable — see Preferences ▸ Read aloud")

    # ======================================================================
    # Navigation & position
    # ======================================================================

    def _prev_page(self) -> None:
        cur = self.pdf_viewer.current_page
        if cur > 0:
            self.pdf_viewer.go_to_page(cur - 1)

    def _next_page(self) -> None:
        cur = self.pdf_viewer.current_page
        if self.pdf_doc.is_loaded and cur < self.pdf_doc.page_count - 1:
            self.pdf_viewer.go_to_page(cur + 1)

    def _go_to_page(self, page_num: int) -> None:
        self.pdf_viewer.go_to_page(page_num - 1)

    def _ask_page(self) -> None:
        if not self.pdf_doc.is_loaded:
            return
        page, ok = QInputDialog.getInt(
            self,
            "Go to page",
            f"Page (1–{self.pdf_doc.page_count}):",
            self.pdf_viewer.current_page + 1,
            1,
            self.pdf_doc.page_count,
        )
        if ok:
            self.pdf_viewer.go_to_page(page - 1)

    @pyqtSlot(int)
    def _on_visible_page_changed(self, page_index: int) -> None:
        self.page_spin.blockSignals(True)
        self.page_spin.setValue(page_index + 1)
        self.page_spin.blockSignals(False)
        self._record_dwell(self._dwell_page)
        self._dwell_page = page_index
        self._update_progress_label()
        self._update_bookmark_button()
        self.outline.mark_current(page_index)
        self._save_pos_timer.start()

    def _record_dwell(self, page_index: int) -> None:
        """Credit time on `page_index` (the page being left) to the running session."""
        session_id = self.pomodoro.active_session_id
        if self._active_doc_id and self._page_dwell_started_at and session_id:
            elapsed = int(time.time() - self._page_dwell_started_at)
            if elapsed > 0:
                self.store.add_page_view(session_id, page_index + 1, elapsed)
        self._page_dwell_started_at = time.time()

    def _save_position(self) -> None:
        if self._closed or not self._active_doc_id or not self.pdf_doc.is_loaded:
            return
        page = self.pdf_viewer.current_page
        self.store.update_last_page(self._active_doc_id, page + 1)
        if self.pdf_viewer.fit_mode == "custom":
            self.store.update_zoom(self._active_doc_id, self.pdf_viewer.zoom)
        self.library.update_document_progress(self.pdf_doc.file_path, page + 1)

    def _update_progress_label(self) -> None:
        if not self.pdf_doc.is_loaded:
            self.progress_label.setText("")
            return
        n = self.pdf_doc.page_count
        p = self.pdf_viewer.current_page + 1
        self.progress_label.setText(f"p. {p} / {n} · {round(p / n * 100)}%")

    # ---- zoom ----

    def _set_fit(self, mode: str) -> None:
        self.pdf_viewer.set_fit_mode(mode)
        self._on_zoom_changed(self.pdf_viewer.zoom)

    @pyqtSlot(float)
    def _on_zoom_changed(self, zoom: float) -> None:
        mode = self.pdf_viewer.fit_mode
        label = {"width": "Width", "page": "Page"}.get(mode)
        self.zoom_btn.setText(label or f"{round(zoom * 100)}%")
        self.zoom_btn.setToolTip(f"Zoom {round(zoom * 100)}%")
        self.action("fit_width").setChecked(mode == "width")
        self.action("fit_page").setChecked(mode == "page")
        if mode == "custom":
            self._save_pos_timer.start()

    # ======================================================================
    # Selection, find, bookmarks, highlights
    # ======================================================================

    def _copy(self) -> None:
        focus = QApplication.focusWidget()
        if isinstance(focus, QLineEdit):
            focus.copy()
        elif self.pdf_viewer.copy_selection():
            self.status_label.setText("Copied to clipboard")

    @pyqtSlot(str)
    def _on_selection_changed(self, text: str) -> None:
        if text:
            n = len(text.split())
            self.status_label.setText(
                f"Selected {n} word{'s' if n != 1 else ''} — right-click for options"
            )

    def _open_find(self, text: str | None = None) -> None:
        if self.pdf_doc.is_loaded:
            self.find_bar.open_bar(text or self.pdf_viewer.selected_text() or None)

    def _close_find(self) -> None:
        self.search.clear()
        self.pdf_viewer.setFocus()

    def _find_next(self) -> None:
        if not self.find_bar.isVisible():
            self._open_find()
            return
        self.search.next(self.pdf_viewer.current_page)

    def _find_prev(self) -> None:
        if not self.find_bar.isVisible():
            self._open_find()
            return
        self.search.previous(self.pdf_viewer.current_page)

    def _on_search_results(self, results: dict, total: int, finished: bool) -> None:
        self.pdf_viewer.set_search_results(results)
        self.find_bar.set_status(self.search.index, total, finished)

    def _on_search_current(self, match) -> None:
        self.pdf_viewer.set_current_match(match)
        self.find_bar.set_status(self.search.index, self.search.total, self.search.finished)

    def _refresh_bookmarks(self) -> None:
        rows = self.store.list_bookmarks(self._active_doc_id) if self._active_doc_id else []
        self.bookmarks.set_bookmarks(rows)
        self.pdf_viewer.set_bookmarked_pages({b.page_no for b in rows})
        self._bookmarked = {b.page_no for b in rows}
        self._update_bookmark_button()

    def _update_bookmark_button(self) -> None:
        marked = self.pdf_viewer.current_page in self._bookmarked
        self.bookmark_btn.setText("★" if marked else "☆")
        self.bookmark_btn.setChecked(marked)

    def _toggle_bookmark(self, page: int) -> None:
        if not self._active_doc_id:
            return
        added = self.store.toggle_bookmark(self._active_doc_id, page)
        self._refresh_bookmarks()
        self.status_label.setText(
            f"{'Bookmarked' if added else 'Removed bookmark on'} page {page + 1}"
        )

    def _set_bookmark_note(self, bookmark_id: int, note: str) -> None:
        self.store.set_bookmark_note(bookmark_id, note or None)
        self._refresh_bookmarks()

    def _jump_bookmark(self, direction: int) -> None:
        pages = sorted(self._bookmarked)
        if not pages:
            self.status_label.setText("No bookmarks in this document")
            return
        cur = self.pdf_viewer.current_page
        if direction > 0:
            target = next((p for p in pages if p > cur), pages[0])
        else:
            target = next((p for p in reversed(pages) if p < cur), pages[-1])
        self.pdf_viewer.go_to_page(target)

    def _highlights_for_page(self, page: int):
        if not self._active_doc_id:
            return []
        return self.store.list_highlights(self._active_doc_id, page)

    def _refresh_notes(self) -> None:
        rows = self.store.list_highlights(self._active_doc_id) if self._active_doc_id else []
        self.notes.set_highlights(rows)
        self.pdf_viewer.refresh_highlights()

    def _add_highlight(self, page: int, start: int, end: int, with_note: bool) -> None:
        if not self._active_doc_id:
            return
        pt = self.pdf_doc.page_text(page)
        text = pt.text[start:end]
        note = None
        if with_note:
            note, ok = QInputDialog.getMultiLineText(self, "Highlight note", f"“{text[:80]}”")
            if not ok:
                return
            note = note.strip() or None
        color = self.settings.qsettings.value("highlight/color", HIGHLIGHT_COLORS["Yellow"])
        self.store.add_highlight(
            self._active_doc_id, page, text, pt.rects_for_range(start, end), str(color), note
        )
        self.pdf_viewer.clear_selection()
        self._refresh_notes()
        self.status_label.setText("Highlight saved")

    def _edit_highlight_note(self, highlight_id: int) -> None:
        if not self._active_doc_id:
            return
        row = next(
            (h for h in self.store.list_highlights(self._active_doc_id) if h.id == highlight_id),
            None,
        )
        if row is None:
            return
        note, ok = QInputDialog.getMultiLineText(
            self, "Highlight note", f"“{row.text[:80]}”", row.note or ""
        )
        if ok:
            self.store.set_highlight_note(highlight_id, note.strip() or None)
            self._refresh_notes()

    def _remove_highlight(self, highlight_id: int) -> None:
        self.store.remove_highlight(highlight_id)
        self._refresh_notes()

    def notes_markdown(self) -> str:
        """Bookmarks and highlights of the open document as Markdown."""
        if not self._active_doc_id:
            return ""
        lines = [f"# {self.pdf_doc.title}", ""]
        if self.pdf_doc.author:
            lines += [f"*{self.pdf_doc.author}*", ""]
        marks = self.store.list_bookmarks(self._active_doc_id)
        if marks:
            lines += ["## Bookmarks", ""]
            lines += [f"- Page {b.page_no + 1}" + (f" — {b.note}" if b.note else "") for b in marks]
            lines.append("")
        highs = self.store.list_highlights(self._active_doc_id)
        if highs:
            lines += ["## Highlights", ""]
            for h in highs:
                lines.append(f"> {h.text}")
                lines.append(">")
                lines.append(f"> — page {h.page_no + 1}")
                if h.note:
                    lines += ["", h.note]
                lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    def _export_notes(self) -> None:
        if not self._active_doc_id:
            return
        default = os.path.splitext(self.pdf_doc.file_path)[0] + " — notes.md"
        path, _ = QFileDialog.getSaveFileName(self, "Export notes", default, "Markdown (*.md)")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.notes_markdown())
            self.status_label.setText(f"Notes exported to {os.path.basename(path)}")

    # ======================================================================
    # Speech
    # ======================================================================

    def _require_reader(self) -> ReadAloud | None:
        if self.reader is None:
            reasons = "; ".join(
                f"{cls.label}: {cls.unavailable_reason()}" for cls in ENGINES.values()
            )
            self.status_label.setText("Text-to-speech unavailable — " + reasons)
        return self.reader

    def _play_page(self) -> None:
        reader = self._require_reader()
        if reader is None or not self.pdf_doc.is_loaded:
            return
        if not reader.read_page(self.pdf_viewer.current_page):
            self.status_label.setText("No readable text from this page onward (scanned PDF?)")

    def _read_from(self, page: int, offset: int) -> None:
        reader = self._require_reader()
        if reader is not None:
            reader.read_page(page, offset)

    def _read_range(self, page: int, start: int, end: int) -> None:
        reader = self._require_reader()
        if reader is not None:
            reader.read_range(page, start, end)

    def _play_selection(self) -> None:
        sel = self.pdf_viewer.selection_range()
        if sel:
            self._read_range(*sel)
        else:
            self.status_label.setText("Select text on the page first")

    def _play_or_pause(self) -> None:
        if self.reader is not None and self.reader.is_active:
            self.reader.toggle_pause()
        elif self.pdf_doc.is_loaded:
            self._play_page()

    def _toggle_pause(self) -> None:
        if self.reader is not None:
            self.reader.toggle_pause()

    def _stop(self) -> None:
        if self.reader is not None:
            self.reader.stop()
        self.pdf_viewer.highlight_range(-1, -1, -1)

    def _escape(self) -> None:
        """Esc: close the find bar, else stop speech, else leave focus mode, else deselect."""
        if self.find_bar.isVisible():
            self.find_bar.close_bar()
        elif self.reader is not None and self.reader.is_active:
            self._stop()
        elif self._focus_mode:
            self._toggle_focus_mode()
        elif self.isFullScreen():
            self._toggle_fullscreen()
        else:
            self.pdf_viewer.clear_selection()

    def _update_speed(self, value: int) -> None:
        speed = value / 100.0
        self.speed_value_label.setText(f"{speed:.1f}×")
        self.settings.tts_rate = speed
        if self.tts_engine is not None:
            self.tts_engine.set_rate(speed)

    def _nudge_speed(self, delta: float) -> None:
        self.speed_slider.setValue(self.speed_slider.value() + int(delta * 100))

    def _toggle_continuous(self) -> None:
        on = self.action("continuous").isChecked()
        self.settings.tts_continuous = on
        if self.reader is not None:
            self.reader.continuous = on

    def _fill_voice_menu(self) -> None:
        self.voice_menu.clear()
        if self.tts_engine is None:
            act = self.voice_menu.addAction("Speech unavailable")
            if act is not None:
                act.setEnabled(False)
            return
        group = QActionGroup(self.voice_menu)
        for v in self.tts_engine.voices():
            act = _checkable_action(v.name, self.voice_menu)
            act.setChecked(v.id == self.tts_engine.voice)
            act.triggered.connect(lambda _=False, vid=v.id: self._set_voice(vid))
            group.addAction(act)
            self.voice_menu.addAction(act)

    def _set_voice(self, voice_id: str) -> None:
        self.settings.tts_voice = voice_id
        if self.tts_engine is not None:
            self.tts_engine.set_voice(voice_id)

    def _voices_for(self, key: str) -> list[Voice]:
        if self.tts_engine is not None and isinstance(
            self.tts_engine, ENGINES.get(key, type(None))
        ):
            return self.tts_engine.voices()
        if key == "kokoro":
            return list(KOKORO_VOICES)
        cls = ENGINES.get(key)
        if cls is None or not cls.is_available():
            return []
        tmp = cls()
        voices = tmp.voices()
        tmp.deleteLater()
        return voices

    def _preview_voice(self, key: str, voice: str, rate: float) -> None:
        if self.tts_engine is None or not isinstance(self.tts_engine, ENGINES.get(key, type(None))):
            self.status_label.setText("Apply the engine change first to preview it")
            return
        if self.reader is not None:
            self.reader.stop()
        # The dialog restores the saved voice/rate when it closes (see _show_preferences).
        if voice:
            self.tts_engine.set_voice(voice)
        self.tts_engine.set_rate(rate)
        self.tts_engine.speak([Utterance("This is how I will read your books.")])

    @pyqtSlot(int)
    def _on_tts_state(self, state: int) -> None:
        st = State(state)
        active = st != State.IDLE
        self.stop_btn.setEnabled(active)
        self.play_btn.setText(
            {
                State.SPEAKING: "⏸  Pause",
                State.PAUSED: "▶  Resume",
                State.LOADING: "⏳  Loading",
            }.get(st, "▶  Read")
        )
        self.tts_status_label.setText(
            {
                State.LOADING: "Loading voice…",
                State.SPEAKING: "Reading aloud",
                State.PAUSED: "Paused",
            }.get(st, "")
        )

    @pyqtSlot()
    def _on_speech_finished(self) -> None:
        self.tts_status_label.setText("Finished reading")
        self._tts_status_timer.start()

    def _clear_tts_status(self) -> None:
        if self.reader is None or not self.reader.is_active:
            self.tts_status_label.setText("")

    @pyqtSlot(int)
    def _on_words_spoken(self, n: int) -> None:
        session_id = self.pomodoro.active_session_id
        if session_id:
            self.store.add_words_heard(session_id, n)

    @pyqtSlot(str)
    def _on_error(self, message: str) -> None:
        self.status_label.setText(f"⚠ {message}")

    # ======================================================================
    # Appearance
    # ======================================================================

    def _set_theme(self, mode: str) -> None:
        self.settings.theme = mode
        for act in self._theme_group.actions():
            act.setChecked(act.data() == mode)
        self._apply_theme()

    def _cycle_theme(self) -> None:
        order = ["dark", "light", "sepia"]
        cur = self.palette_.name
        self._set_theme(order[(order.index(cur) + 1) % len(order)] if cur in order else "dark")

    def _on_system_scheme(self) -> None:
        if self.settings.theme == "system":
            self._apply_theme()

    def _apply_theme(self) -> None:
        self.palette_ = resolve_palette(self.settings.theme)
        P = self.palette_
        _label, _pt, base_px = TEXT_SIZES[self._text_size_idx()]
        self.setStyleSheet(stylesheet(P, base_px))
        self.welcome.set_palette(P)
        self.library.set_palette(P)
        self.pomodoro.set_palette(P)
        self._apply_page_colors()
        self.theme_btn.setText({"dark": "☾", "light": "☀", "sepia": "◐"}[P.name])
        self.theme_btn.setToolTip(f"Theme: {P.name} — Ctrl+T to cycle")

    def _apply_page_colors(self) -> None:
        self.pdf_viewer.set_palette(
            self.palette_, page_colors_for(self.palette_, self.settings.page_colors)
        )

    def _toggle_page_colors(self) -> None:
        self.settings.page_colors = (
            "match" if self.action("page_colors").isChecked() else "original"
        )
        self._apply_page_colors()

    def _text_size_idx(self) -> int:
        return min(len(TEXT_SIZES) - 1, max(0, self.settings.text_size))

    def _cycle_text_size(self) -> None:
        self.settings.text_size = (self._text_size_idx() + 1) % len(TEXT_SIZES)
        self._apply_text_size()

    def _apply_text_size(self) -> None:
        label, pt, base_px = TEXT_SIZES[self._text_size_idx()]
        self.text_size_btn.setText(f"T{label}")
        font = QApplication.font()
        font.setPointSize(pt)
        QApplication.setFont(font)
        self.setStyleSheet(stylesheet(self.palette_, base_px))

    # ---- docks, fullscreen, focus mode ----

    def _toggle_sidebar(self) -> None:
        self._sidebar_dock.setVisible(not self._sidebar_dock.isVisible())

    def _toggle_library(self) -> None:  # legacy name
        self._toggle_sidebar()

    def _toggle_pomodoro_dock(self) -> None:
        self._pomodoro_dock.setVisible(not self._pomodoro_dock.isVisible())

    def _sync_toggle_states(self, *_args) -> None:
        self.action("sidebar").setChecked(self._sidebar_dock.isVisible())
        self.sidebar_btn.setChecked(self._sidebar_dock.isVisible())
        self.action("show_pomodoro").setChecked(self._pomodoro_dock.isVisible())

    def _toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showMaximized() if self._was_maximized else self.showNormal()
        else:
            self._was_maximized = self.isMaximized()
            self.showFullScreen()
        self.action("fullscreen").setChecked(self.isFullScreen())

    _was_maximized = True

    def _toggle_focus_mode(self) -> None:
        """Distraction-free reading: hide every bar and panel."""
        if not self._focus_mode:
            self._pre_focus_state = (
                self._sidebar_dock.isVisible(),
                self._pomodoro_dock.isVisible(),
                self.menuBar().isVisible(),
                self.statusBar().isVisible(),
            )
            for w in (
                self._sidebar_dock,
                self._pomodoro_dock,
                self._toolbar,
                self.menuBar(),
                self.statusBar(),
            ):
                w.hide()
            self._focus_mode = True
            self.status_bar.showMessage("Focus mode — press Esc or Ctrl+Shift+F to exit", 3000)
        else:
            sidebar, pomodoro, menu, status = self._pre_focus_state or (True, True, True, True)
            self._sidebar_dock.setVisible(sidebar)
            self._pomodoro_dock.setVisible(pomodoro)
            self.menuBar().setVisible(menu)
            self.statusBar().setVisible(status)
            self._toolbar.show()
            self._focus_mode = False
        self.action("focus_mode").setChecked(self._focus_mode)

    # ======================================================================
    # Dialogs
    # ======================================================================

    def _show_preferences(self) -> None:
        before = (self.settings.tts_engine,)
        dlg = SettingsDialog(self.settings, self._voices_for, self)
        dlg.preview_voice.connect(self._preview_voice)
        accepted = dlg.exec() == QDialog.DialogCode.Accepted
        if not accepted:
            # Undo any voice preview.
            if self.tts_engine is not None:
                if self.settings.tts_voice:
                    self.tts_engine.set_voice(self.settings.tts_voice)
                self.tts_engine.set_rate(self.settings.tts_rate)
            return
        self.apply_settings(engine_changed=(self.settings.tts_engine,) != before)

    def apply_settings(self, engine_changed: bool = False) -> None:
        s = self.settings
        for act in self._theme_group.actions():
            act.setChecked(act.data() == s.theme)
        self.action("page_colors").setChecked(s.page_colors == "match")
        self.action("continuous").setChecked(s.tts_continuous)
        self._apply_theme()
        self._apply_text_size()
        self._configure_pomodoro()
        if engine_changed:
            had_reader = self.reader is not None
            self._set_engine(create_engine(s.tts_engine, self))
            if not had_reader:
                self._connect_reader()
        elif self.tts_engine is not None:
            if s.tts_voice:
                self.tts_engine.set_voice(s.tts_voice)
            self.tts_engine.set_rate(s.tts_rate)
        if self.reader is not None:
            self.reader.continuous = s.tts_continuous
        self.speed_slider.blockSignals(True)
        self.speed_slider.setValue(round(s.tts_rate * 100))
        self.speed_slider.blockSignals(False)
        self.speed_value_label.setText(f"{s.tts_rate:.1f}×")
        if self.pdf_doc.is_loaded and s.fit_mode != "custom":
            self._set_fit(s.fit_mode)
        self._update_doc_actions()

    def _show_analytics(self) -> None:
        AnalyticsDialog(self.store, parent=self, palette=self.palette_).exec()

    def _show_shortcuts(self) -> None:
        rows = []
        for act in self._actions.values():
            keys = ", ".join(
                s.toString(QKeySequence.SequenceFormat.NativeText) for s in act.shortcuts()
            )
            if keys:
                rows.append(
                    f"<tr><td style='padding:3px 18px 3px 0'><code>{keys}</code></td><td>{act.text().replace('&', '')}</td></tr>"
                )
        dlg = QDialog(self)
        dlg.setWindowTitle("Keyboard shortcuts")
        dlg.resize(520, 600)
        view = QTextBrowser(dlg)
        view.setHtml("<table>" + "".join(rows) + "</table>")
        lay = QVBoxLayout(dlg)
        lay.addWidget(view)
        dlg.exec()

    def _show_about(self) -> None:
        engines = ", ".join(
            f"{cls.label}: {'available' if cls.is_available() else cls.unavailable_reason()}"
            for cls in ENGINES.values()
        )
        QMessageBox.about(
            self,
            f"About {APP_NAME}",
            f"<h2>{APP_NAME} {__version__}</h2>"
            "<p>A focused PDF reader with neural text-to-speech, a Pomodoro timer "
            "and reading analytics. Everything stays on your computer.</p>"
            f"<p><small>Speech engines — {engines}</small></p>"
            f"<p><small>Library: {self.store.path}<br>Settings: {self.settings.path}</small></p>",
        )

    def _fill_recent_menu(self) -> None:
        self.recent_menu.clear()
        recent = [p for p in self.settings.recent_files if os.path.isfile(p)]
        for path in recent:
            self.recent_menu.addAction(os.path.basename(path), lambda p=path: self._load_pdf(p))
        if not recent:
            act = self.recent_menu.addAction("No recent files")
            if act is not None:
                act.setEnabled(False)
        else:
            self.recent_menu.addSeparator()
            self.recent_menu.addAction("Clear", self.settings.clear_recent)

    # ======================================================================
    # Pomodoro
    # ======================================================================

    def _on_phase_completed(self, phase: str, minutes: int) -> None:
        self.status_label.setText(f"✓ {PHASE_LABELS[phase]} — {minutes} min recorded")

    def _on_next_phase(self, phase: str) -> None:
        if not self.settings.pomodoro_notify:
            return
        body = {
            "focus": "Break's over — back to reading.",
            "break": "Nice work. Take a short break.",
            "long": "Great session! Time for a long break.",
        }[phase]
        notify(f"{APP_NAME} · {PHASE_LABELS[phase]}", body)

    def _update_pomodoro_status(self) -> None:
        p = self.pomodoro
        if p.is_running or p.active_session_id is not None:
            mm, ss = divmod(p._remaining, 60)
            state = "" if p.is_running else " (paused)"
            self.pomodoro_status.setText(f"{PHASE_LABELS[p.phase]} {mm:02d}:{ss:02d}{state}")
        else:
            self.pomodoro_status.setText("")

    # ======================================================================
    # Window state
    # ======================================================================

    def _restore_window(self) -> None:
        geom, state = self.settings.window_geometry(), self.settings.window_state()
        if geom is not None:
            self.restoreGeometry(geom)
        else:
            self.resize(1280, 820)
            self.setWindowState(Qt.WindowState.WindowMaximized)
        if state is not None:
            self.restoreState(state)
        self._sync_toggle_states()

    def restore_session(self) -> None:
        """Reopen the last document if the user wants that."""
        last = self.settings.last_document
        if (
            self.settings.reopen_last
            and last
            and os.path.isfile(last)
            and not self.pdf_doc.is_loaded
        ):
            self._load_pdf(last)

    def dragEnterEvent(self, event) -> None:
        urls = event.mimeData().urls()
        if urls and urls[0].toLocalFile().lower().endswith(".pdf"):
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if path.lower().endswith(".pdf"):
                self._load_pdf(path)

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self._closed:
            if self._focus_mode:
                self._toggle_focus_mode()
            self._leave_document()
            self._closed = True
            self._save_pos_timer.stop()
            self._pomodoro_tick.stop()
            self.settings.save_window(self.saveGeometry(), self.saveState())
            self.settings.sync()
            if self.tts_engine is not None:
                self.tts_engine.shutdown()
            # Stop the viewer first so no deferred signal can reach the store after it closes.
            self.pdf_viewer.current_page_changed.disconnect(self._on_visible_page_changed)
            self.pdf_viewer.clear()
            self.pdf_doc.close()
            self.pomodoro.reset()
            self.store.close()
        event.accept()
