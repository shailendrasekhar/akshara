from __future__ import annotations


def test_main_window_opens_pdf(qtbot, sample_pdf):
    from akshara.main_window import MainWindow

    w = MainWindow()
    qtbot.addWidget(w)
    w._load_pdf(str(sample_pdf))
    assert w.pdf_doc.is_loaded
    assert w.pdf_doc.page_count == 3
    assert w.pdf_doc.title == "Sample Book"
    assert len(w.store.list_documents()) == 1
    w.close()


def test_cli_version(capsys):
    import pytest

    from akshara.app import parse_args

    with pytest.raises(SystemExit):
        parse_args(["--version"])
    assert "akshara" in capsys.readouterr().out


def test_reopen_resumes_last_page(qtbot, sample_pdf):
    from akshara.main_window import MainWindow

    w = MainWindow()
    qtbot.addWidget(w)
    w.resize(900, 700)
    w._load_pdf(str(sample_pdf))
    assert w.pdf_doc.author == "Jane Doe"
    w.pdf_viewer.go_to_page(2)
    qtbot.waitUntil(lambda: w.pdf_viewer.current_page == 2)
    w.close_document()
    assert w.store.list_documents()[0].last_page == 3

    w._load_pdf(str(sample_pdf))
    assert "Resumed at page 3" in w.status_label.text()
    qtbot.waitUntil(lambda: w.pdf_viewer.current_page == 2)


def test_pomodoro_before_pdf(qtbot):
    """Regression: Begin with no document open raised sqlite3.IntegrityError."""
    from akshara.main_window import MainWindow

    w = MainWindow()
    qtbot.addWidget(w)
    w.pomodoro.toggle()
    assert w.pomodoro.active_session_id is not None
    w.pomodoro.reset()


def test_splash_runs_to_completion(qtbot):
    from akshara.main_window import MainWindow
    from akshara.splash_screen import SplashController
    from akshara.ui.theme import SEPIA

    w = MainWindow()
    qtbot.addWidget(w)
    splash = SplashController(w, palette=SEPIA)
    with qtbot.waitSignal(splash.splash.finished, timeout=6000):
        splash.start()
    assert w.isVisible()
