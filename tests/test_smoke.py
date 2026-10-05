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
