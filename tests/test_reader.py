from __future__ import annotations

from akshara.textmap import PageText
from akshara.tts.base import SpeechEngine, State, Utterance
from akshara.tts.reader import ReadAloud


class ScriptedEngine(SpeechEngine):
    """Synchronous engine: `advance()` plays the next queued utterance."""

    def __init__(self):
        super().__init__()
        self.queue: list[Utterance] = []
        self.spoken: list[Utterance] = []

    def speak(self, utterances):
        self.stop()
        self.enqueue(utterances)

    def enqueue(self, utterances):
        self.queue.extend(utterances)
        self._set_state(State.SPEAKING)

    def pause(self):
        self._set_state(State.PAUSED)

    def resume(self):
        self._set_state(State.SPEAKING)

    def stop(self):
        self.queue.clear()
        self._set_state(State.IDLE)

    def advance(self) -> bool:
        if not self.queue:
            return False
        u = self.queue.pop(0)
        self.spoken.append(u)
        self.utterance_started.emit(u)
        if not self.queue:
            self._set_state(State.IDLE)
            self.finished.emit()
        return True

    def run(self):
        while self.advance():
            pass


def _page(text: str) -> PageText:
    words = [(i * 10, 0, i * 10 + 9, 10, w, 0, 0, i) for i, w in enumerate(text.split())]
    return PageText.from_words(words)


PAGES = [_page("Page one first. Page one second."), _page(""), _page("Page three only.")]


def _reader():
    engine = ScriptedEngine()
    r = ReadAloud(engine, page_text=lambda i: PAGES[i], page_count=lambda: len(PAGES))
    return engine, r


def test_continuous_reading_skips_empty_pages():
    engine, r = _reader()
    highlights: list[tuple[int, int, int]] = []
    pages: list[int] = []
    r.highlight.connect(lambda p, s, e: highlights.append((p, s, e)))
    r.page_changed.connect(pages.append)
    assert r.read_page(0)
    engine.run()
    assert [u.text for u in engine.spoken] == [
        "Page one first.",
        "Page one second.",
        "Page three only.",
    ]
    assert pages == [0, 2]
    assert highlights[0] == (0, 0, len("Page one first."))
    assert highlights[-1] == (-1, -1, -1)  # cleared on finish


def test_next_page_is_queued_while_last_sentence_plays():
    engine, r = _reader()
    r.read_page(0)
    engine.advance()  # first sentence
    assert all(u.page == 0 for u in engine.queue)
    engine.advance()  # last sentence of page 0 starts -> page 2 queued
    assert [u.page for u in engine.queue] == [2]


def test_non_continuous_stops_at_page_end():
    engine, r = _reader()
    r.continuous = False
    r.read_page(0)
    engine.run()
    assert len(engine.spoken) == 2


def test_read_from_offset():
    engine, r = _reader()
    offset = PAGES[0].text.index("Page one second")
    r.read_page(0, offset)
    engine.advance()
    assert engine.spoken[0].text == "Page one second."


def test_read_range_trims_to_selection():
    engine, r = _reader()
    end = PAGES[0].text.index("second") + len("second")
    r.read_range(0, 0, end)
    engine.run()
    assert [u.text for u in engine.spoken] == ["Page one first.", "Page one second"]


def test_empty_document_returns_false():
    engine = ScriptedEngine()
    r = ReadAloud(engine, page_text=lambda i: PageText(), page_count=lambda: 3)
    assert not r.read_page(0)


def test_words_spoken_counts():
    engine, r = _reader()
    words: list[int] = []
    r.words_spoken.connect(words.append)
    r.read_page(0)
    engine.run()
    assert sum(words) == 9
