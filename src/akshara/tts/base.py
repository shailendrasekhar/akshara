"""Speech engine interface shared by all TTS backends."""

from __future__ import annotations

import enum
import itertools
from dataclasses import dataclass, field

from PyQt6.QtCore import QObject, pyqtSignal

_ids = itertools.count(1)


class State(enum.IntEnum):
    IDLE = 0
    LOADING = 1  # model is being loaded/downloaded before speech can start
    SPEAKING = 2
    PAUSED = 3


@dataclass(frozen=True)
class Voice:
    id: str
    name: str
    language: str = ""


@dataclass(frozen=True)
class Utterance:
    """One unit of speech (normally a sentence) and where it came from."""

    text: str
    page: int = -1
    start: int = -1  # char offsets into the page's PageText.text
    end: int = -1
    id: int = field(default_factory=lambda: next(_ids))

    @property
    def word_count(self) -> int:
        return len(self.text.split())


class SpeechEngine(QObject):
    """
    Abstract TTS engine. Engines own a FIFO of utterances and report progress
    with signals that are always delivered on the GUI thread.

    Subclasses implement the ``_do_*`` hooks; this class keeps the public
    surface identical across backends.
    """

    state_changed = pyqtSignal(int)  # State
    utterance_started = pyqtSignal(object)  # Utterance
    finished = pyqtSignal()  # queue drained naturally (not on stop())
    error_occurred = pyqtSignal(str)

    #: Human-readable backend name for the UI.
    label = "Speech"

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._state = State.IDLE
        self._rate = 1.0
        self._voice = ""

    # ---- availability ----

    @classmethod
    def is_available(cls) -> bool:
        return True

    @classmethod
    def unavailable_reason(cls) -> str:
        return ""

    # ---- queue control ----

    def speak(self, utterances: list[Utterance]) -> None:
        """Replace whatever is playing with `utterances`."""
        raise NotImplementedError

    def enqueue(self, utterances: list[Utterance]) -> None:
        """Append to the current queue without interrupting it."""
        raise NotImplementedError

    def pause(self) -> None:
        raise NotImplementedError

    def resume(self) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError

    def preload(self) -> None:
        """Warm up models in the background. Optional."""

    def shutdown(self) -> None:
        self.stop()

    # ---- parameters ----

    def voices(self) -> list[Voice]:
        return []

    @property
    def voice(self) -> str:
        return self._voice

    def set_voice(self, voice_id: str) -> None:
        self._voice = voice_id

    @property
    def rate(self) -> float:
        return self._rate

    def set_rate(self, multiplier: float) -> None:
        """Speech rate multiplier, clamped to 0.5–2.0."""
        self._rate = max(0.5, min(float(multiplier), 2.0))

    # ---- state ----

    @property
    def state(self) -> State:
        return self._state

    @property
    def is_speaking(self) -> bool:
        return self._state in (State.SPEAKING, State.PAUSED, State.LOADING)

    @property
    def is_paused(self) -> bool:
        return self._state == State.PAUSED

    def _set_state(self, state: State) -> None:
        if state != self._state:
            self._state = state
            self.state_changed.emit(int(state))
