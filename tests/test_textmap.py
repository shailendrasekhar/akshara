from __future__ import annotations

from akshara.textmap import PageText, split_sentences


def _w(text, x0, line, block=0, y=None):
    y = line * 20 if y is None else y
    return (x0, y, x0 + 10 * len(text), y + 12, text, block, line, 0)


def test_text_and_ranges_are_consistent():
    pt = PageText.from_words([_w("Hello", 0, 0), _w("world.", 60, 0), _w("Next", 0, 1)])
    assert pt.text == "Hello world. Next"
    for word, (s, e) in zip(pt.words, pt.ranges, strict=True):
        assert pt.text[s:e] == word.text


def test_line_end_hyphenation_is_joined():
    pt = PageText.from_words([_w("infor-", 0, 0), _w("mation", 0, 1), _w("age", 70, 1)])
    assert pt.text == "information age"
    # Both halves map into the joined word, so a highlight covers both lines.
    assert pt.words_in_range(0, len("information")) == [0, 1]


def test_hyphen_kept_mid_line_and_before_capital():
    pt = PageText.from_words([_w("well-", 0, 0), _w("Known", 0, 1)])
    assert pt.text == "well- Known"


def test_rects_merge_per_line():
    pt = PageText.from_words([_w("a", 0, 0), _w("b", 20, 0), _w("c", 0, 1)])
    rects = pt.rects_for_range(0, len(pt.text))
    assert len(rects) == 2
    assert rects[0][0] == 0 and rects[0][2] == 30


def test_find_is_whitespace_and_case_insensitive():
    pt = PageText.from_words([_w("The", 0, 0), _w("Quick", 40, 0), _w("fox", 0, 1)])
    assert pt.find("quick   FOX") == (4, 13)
    assert pt.find("absent") == (-1, -1)
    assert pt.find_all("the") == [(0, 3)]


def test_word_at_point_and_nearest():
    pt = PageText.from_words([_w("alpha", 0, 0), _w("beta", 100, 0)])
    assert pt.word_at_point(5, 5) == 0
    assert pt.word_at_point(500, 500) == -1
    assert pt.nearest_word(95, 5) == 1


def test_split_sentences_with_offsets():
    text = "Dr. Smith arrived. He said hi! Did J. R. R. Tolkien write e.g. this? Yes"
    sents = split_sentences(text)
    assert [s.text for s in sents] == [
        "Dr. Smith arrived.",
        "He said hi!",
        "Did J. R. R. Tolkien write e.g. this?",
        "Yes",
    ]
    for s in sents:
        assert text[s.start : s.end] == s.text


def test_split_sentences_from_offset():
    text = "One. Two. Three."
    assert [s.text for s in split_sentences(text, 5)] == ["Two.", "Three."]


def test_year_ends_sentence():
    assert len(split_sentences("It was 1984. Then it was not.")) == 2


def test_from_real_page(sample_pdf):
    import pymupdf

    with pymupdf.open(sample_pdf) as doc:
        pt = PageText.from_page(doc[0])
    assert pt.text.startswith("The quick brown fox")
    assert len(pt.sentences()) == 2
