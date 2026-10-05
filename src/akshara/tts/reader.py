"""
Read-aloud controller: turns pages into utterances and keeps the engine fed.

It speaks sentence by sentence from a starting point, queues the following
page while the last sentence of the current one is playing (so continuous
reading has no gap), and reports exactly which character range is being
spoken so the viewer can highlight it.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable

from PyQt6.QtCore import QObject, pyqtSignal

from ..textmap import PageText
from .base import SpeechEngine, State, Utterance

# Skip at most this many consecutive empty pages (scans, blank pages) when
# continuing to read before giving up.
MAX_EMPTY_SKIP = 5


class ReadAloud(QObject):
    highlight = pyqtSignal(int, int, int)  # page, start, end
    page_changed = pyqtSignal(int)  # reading moved onto a new page
    words_spoken = pyqtSignal(int)
    finished = pyqtSignal()
    state_changed = pyqtSignal(int)
    error_occurred = pyqtSignal(str)

    def __init__(
        self,
        engine: SpeechEngine,
        page_text: Callable[[int], PageText],
        page_count: Callable[[], int],
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self._page_text = page_text
        self._page_count = page_count
        self.continuous = True
        self._queued_through = -1  # last page whose sentences are queued
        self._last_on_page: dict[int, int] = {}  # page -> id of its last utterance
        self._page = -1
        self.engine = engine
        self._connect(engine)

    # ---- engine ----

    def set_engine(self, engine: SpeechEngine) -> None:
        self.stop()
        self._disconnect(self.engine)
        self.engine = engine
        self._connect(engine)

    def _connect(self, e: SpeechEngine) -> None:
        e.utterance_started.connect(self._on_started)
        e.finished.connect(self._on_finished)
        e.state_changed.connect(self.state_changed)
        e.error_occurred.connect(self.error_occurred)

    def _disconnect(self, e: SpeechEngine) -> None:
        for sig, slot in (
            (e.utterance_started, self._on_started),
            (e.finished, self._on_finished),
            (e.state_changed, self.state_changed),
            (e.error_occurred, self.error_occurred),
        ):
            with contextlib.suppress(TypeError):
                sig.disconnect(slot)

    # ---- control ----

    @property
    def state(self) -> State:
        return self.engine.state

    @property
    def is_active(self) -> bool:
        return self.engine.is_speaking

    def read_page(self, page: int, offset: int = 0) -> bool:
        """Read from `offset` on `page` onward (continuing to later pages)."""
        utts = self._utterances(page, offset)
        if not utts:
            nxt = self._next_page_with_text(page)
            if nxt < 0:
                return False
            page, utts = nxt, self._utterances(nxt, 0)
        self._reset()
        self._queued_through = page
        self._remember(page, utts)
        self.engine.speak(utts)
        return True

    def read_range(self, page: int, start: int, end: int) -> bool:
        """Read just [start, end) of `page` (e.g. the selection), then stop."""
        pt = self._page_text(page)
        utts = [
            Utterance(s.text, page, s.start, s.end) for s in pt.sentences(start) if s.start < end
        ]
        if utts and utts[-1].end > end:
            last = utts[-1]
            utts[-1] = Utterance(pt.text[last.start : end], page, last.start, end)
        if not utts:
            return False
        self._reset()
        self._queued_through = 10**9  # never auto-continue a range read
        self.engine.speak(utts)
        return True

    def read_text(self, text: str) -> None:
        """Read arbitrary text with no page mapping."""
        self._reset()
        self._queued_through = 10**9
        self.engine.speak([Utterance(text)])

    def toggle_pause(self) -> None:
        if self.engine.state == State.PAUSED:
            self.engine.resume()
        elif self.engine.is_speaking:
            self.engine.pause()

    def stop(self) -> None:
        self.engine.stop()
        self._reset()

    # ---- internals ----

    def _reset(self) -> None:
        self._queued_through = -1
        self._last_on_page.clear()
        self._page = -1

    def _utterances(self, page: int, offset: int) -> list[Utterance]:
        if not (0 <= page < self._page_count()):
            return []
        pt = self._page_text(page)
        return [Utterance(s.text, page, s.start, s.end) for s in pt.sentences(max(0, offset))]

    def _remember(self, page: int, utts: list[Utterance]) -> None:
        if utts:
            self._last_on_page[page] = utts[-1].id

    def _next_page_with_text(self, after: int) -> int:
        n = self._page_count()
        for p in range(after + 1, min(n, after + 1 + MAX_EMPTY_SKIP)):
            if self._page_text(p):
                return p
        return -1

    def _on_started(self, utt: Utterance) -> None:
        if utt.page >= 0:
            if utt.page != self._page:
                self._page = utt.page
                self.page_changed.emit(utt.page)
            self.highlight.emit(utt.page, utt.start, utt.end)
        self.words_spoken.emit(utt.word_count)
        # Starting the last sentence of the furthest queued page: queue the next
        # page now so it is synthesised while this sentence plays.
        if (
            self.continuous
            and utt.page == self._queued_through
            and self._last_on_page.get(utt.page) == utt.id
        ):
            nxt = self._next_page_with_text(utt.page)
            if nxt >= 0:
                utts = self._utterances(nxt, 0)
                self._queued_through = nxt
                self._remember(nxt, utts)
                self.engine.enqueue(utts)

    def _on_finished(self) -> None:
        self._reset()
        self.highlight.emit(-1, -1, -1)
        self.finished.emit()
