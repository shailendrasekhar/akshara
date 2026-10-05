"""
Page text model shared by the viewer, search, selection and TTS.

A :class:`PageText` is built once per page from PyMuPDF word boxes. It exposes
the page as one normalised string (single spaces, line-end hyphenation
joined) plus a mapping from every character range back to word rectangles.
TTS speaks slices of that exact string, so highlighting is a direct offset
lookup — no fuzzy re-searching of the text.

Coordinates are PDF points (unscaled); the viewer multiplies by its zoom.
"""

from __future__ import annotations

import bisect
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

Rect = tuple[float, float, float, float]  # x0, y0, x1, y1

# Words that end in '.' but do not end a sentence.
_ABBREVIATIONS = frozenset(
    [
        "mr",
        "mrs",
        "ms",
        "dr",
        "prof",
        "sr",
        "jr",
        "st",
        "vs",
        "etc",
        "e.g",
        "i.e",
        "cf",
        "fig",
        "figs",
        "eq",
        "eqs",
        "no",
        "vol",
        "vols",
        "ch",
        "sec",
        "pp",
        "p",
        "ed",
        "eds",
        "al",
        "approx",
        "dept",
        "est",
        "inc",
        "ltd",
        "co",
        "corp",
        "jan",
        "feb",
        "mar",
        "apr",
        "jun",
        "jul",
        "aug",
        "sep",
        "sept",
        "oct",
        "nov",
        "dec",
        "mt",
        "ft",
    ]
)

_SENTENCE_END = re.compile(r"[.!?…]+[\"'”’)\]]*(?=\s|$)")


@dataclass(frozen=True)
class Word:
    text: str
    rect: Rect
    block: int
    line: int


@dataclass(frozen=True)
class Sentence:
    start: int
    end: int
    text: str


@dataclass
class PageText:
    words: list[Word] = field(default_factory=list)
    text: str = ""
    # (start, end) char range in `text` for each word; parallel to `words`.
    ranges: list[tuple[int, int]] = field(default_factory=list)

    # ---- construction ----

    @classmethod
    def from_words(cls, raw: Iterable[Sequence]) -> PageText:
        """Build from PyMuPDF ``page.get_text("words", sort=True)`` tuples.

        Each tuple is ``(x0, y0, x1, y1, text, block_no, line_no, word_no)``.
        """
        words = [
            Word(
                str(w[4]),
                (float(w[0]), float(w[1]), float(w[2]), float(w[3])),
                int(w[5]),
                int(w[6]),
            )
            for w in raw
            if str(w[4]).strip()
        ]
        parts: list[str] = []
        ranges: list[tuple[int, int]] = []
        pos = 0
        for i, w in enumerate(words):
            token = w.text
            nxt = words[i + 1] if i + 1 < len(words) else None
            joined = (
                nxt is not None
                and token.endswith("-")
                and len(token) > 1
                and token[-2].isalpha()
                and (nxt.block, nxt.line) != (w.block, w.line)
                and nxt.text[:1].islower()
            )
            if joined:
                token = token[:-1]
            ranges.append((pos, pos + len(token)))
            parts.append(token)
            pos += len(token)
            if nxt is not None and not joined:
                parts.append(" ")
                pos += 1
        return cls(words=words, text="".join(parts), ranges=ranges)

    @classmethod
    def from_page(cls, page) -> PageText:  # page: pymupdf.Page
        return cls.from_words(page.get_text("words", sort=True))

    # ---- lookups ----

    def __bool__(self) -> bool:
        return bool(self.words)

    def word_at_offset(self, offset: int) -> int:
        """Index of the word containing (or nearest after) `offset`, or -1."""
        if not self.ranges:
            return -1
        starts = [r[0] for r in self.ranges]
        i = bisect.bisect_right(starts, offset) - 1
        return max(0, min(i, len(self.ranges) - 1))

    def words_in_range(self, start: int, end: int) -> list[int]:
        return [i for i, (s, e) in enumerate(self.ranges) if s < end and e > start]

    def word_at_point(self, x: float, y: float, tolerance: float = 0.0) -> int:
        """Index of the word whose box contains (x, y), or -1."""
        for i, w in enumerate(self.words):
            x0, y0, x1, y1 = w.rect
            if x0 - tolerance <= x <= x1 + tolerance and y0 - tolerance <= y <= y1 + tolerance:
                return i
        return -1

    def nearest_word(self, x: float, y: float) -> int:
        """Index of the word closest to (x, y) in reading terms, or -1."""
        best, best_d = -1, float("inf")
        for i, w in enumerate(self.words):
            x0, y0, x1, y1 = w.rect
            dx = 0.0 if x0 <= x <= x1 else min(abs(x - x0), abs(x - x1))
            dy = 0.0 if y0 <= y <= y1 else min(abs(y - y0), abs(y - y1))
            d = dy * 4 + dx  # prefer the right line over the right column
            if d < best_d:
                best, best_d = i, d
        return best

    def text_for_words(self, first: int, last: int) -> str:
        if not self.words:
            return ""
        first, last = sorted((first, last))
        return self.text[self.ranges[first][0] : self.ranges[last][1]]

    def range_for_words(self, first: int, last: int) -> tuple[int, int]:
        first, last = sorted((first, last))
        return self.ranges[first][0], self.ranges[last][1]

    def rects_for_range(self, start: int, end: int) -> list[Rect]:
        """Word boxes covering [start, end), merged into one box per line."""
        merged: dict[tuple[int, int], list[float]] = {}
        order: list[tuple[int, int]] = []
        for i in self.words_in_range(start, end):
            w = self.words[i]
            key = (w.block, w.line)
            if key not in merged:
                merged[key] = list(w.rect)
                order.append(key)
            else:
                r = merged[key]
                r[0], r[1] = min(r[0], w.rect[0]), min(r[1], w.rect[1])
                r[2], r[3] = max(r[2], w.rect[2]), max(r[3], w.rect[3])
        return [(r[0], r[1], r[2], r[3]) for r in (merged[k] for k in order)]

    def find(
        self, needle: str, start_from: int = 0, case_sensitive: bool = False
    ) -> tuple[int, int]:
        """Find `needle` (whitespace-normalised) in the page text. Returns (-1, -1) if absent."""
        needle = " ".join(needle.split())
        if not needle:
            return -1, -1
        hay = self.text if case_sensitive else self.text.lower()
        if not case_sensitive:
            needle = needle.lower()
        pos = hay.find(needle, start_from)
        return (pos, pos + len(needle)) if pos >= 0 else (-1, -1)

    def find_all(self, needle: str, case_sensitive: bool = False) -> list[tuple[int, int]]:
        out: list[tuple[int, int]] = []
        pos = 0
        while True:
            s, e = self.find(needle, pos, case_sensitive)
            if s < 0:
                return out
            out.append((s, e))
            pos = e

    def sentences(self, start: int = 0) -> list[Sentence]:
        return split_sentences(self.text, start)


def split_sentences(text: str, start: int = 0) -> list[Sentence]:
    """Split `text[start:]` into sentences, keeping offsets into `text`."""
    out: list[Sentence] = []
    seg_start = start
    for m in _SENTENCE_END.finditer(text, start):
        end = m.end()
        if m.group().startswith(".") and len(m.group()) == 1:
            # Look at the word that owns this period.
            word_start = text.rfind(" ", seg_start, m.start()) + 1
            word = text[word_start : m.start()].lower().strip("(\"'“‘")
            if word in _ABBREVIATIONS or (len(word) == 1 and word.isalpha()):
                continue
        _append(out, text, seg_start, end)
        seg_start = end
    _append(out, text, seg_start, len(text))
    return out


def _append(out: list[Sentence], text: str, s: int, e: int) -> None:
    while s < e and text[s].isspace():
        s += 1
    while e > s and text[e - 1].isspace():
        e -= 1
    if s < e:
        out.append(Sentence(s, e, text[s:e]))
