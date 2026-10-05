from __future__ import annotations

import os
from pathlib import Path

import pytest

# Headless Qt for CI and containers. Must be set before QApplication exists.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(autouse=True)
def _isolated_data_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep every test away from the real user database and settings."""
    monkeypatch.setenv("AKSHARA_DB", str(tmp_path / "akshara.db"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))


@pytest.fixture
def store(tmp_path: Path):
    from akshara.db import Store

    s = Store(tmp_path / "test.db")
    yield s
    s.close()


def make_pdf(path: Path, pages: list[str], title: str = "Sample Book", author: str = "") -> Path:
    import pymupdf

    doc = pymupdf.open()
    for text in pages:
        page = doc.new_page(width=595, height=842)
        page.insert_textbox(pymupdf.Rect(72, 72, 523, 770), text, fontsize=12)
    doc.set_metadata({"title": title, "author": author})
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    return make_pdf(
        tmp_path / "sample.pdf",
        [
            "The quick brown fox jumps over the lazy dog. It was a sunny day.",
            "Second page text. Reading is a pleasure!",
            "Third page. Is this the end? Yes it is.",
        ],
        author="Jane Doe",
    )
