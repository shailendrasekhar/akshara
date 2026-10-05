"""
System speech backend using Qt TextToSpeech (speech-dispatcher on Linux).

Lightweight fallback for when the neural engine is not installed: no model
download, no GPU, but robotic voices. Runs entirely on the GUI thread.
"""

from __future__ import annotations

import math
from collections import deque

from PyQt6.QtCore import QObject

from .base import SpeechEngine, State, Utterance, Voice

try:
    from PyQt6.QtTextToSpeech import QTextToSpeech

    _QT_TTS = True
except ImportError:  # pragma: no cover - depends on the PyQt6 build
    _QT_TTS = False


class SystemEngine(SpeechEngine):
    label = "System (speech-dispatcher)"

    def __init__(self, parent: QObject | None = None, engine_name: str | None = None):
        super().__init__(parent)
        if engine_name is None:
            engines = QTextToSpeech.availableEngines()
            engine_name = next((e for e in engines if e != "mock"), engines[0] if engines else "")
        self._tts = QTextToSpeech(engine_name, self) if engine_name else QTextToSpeech(self)
        self._tts.stateChanged.connect(self._on_tts_state)
        self._tts.errorOccurred.connect(self._on_tts_error)
        self._queue: deque[Utterance] = deque()
        self._current: Utterance | None = None
        self._voices = {v.name(): v for v in self._tts.availableVoices()}
        self._voice = next(iter(self._voices), "")

    @classmethod
    def is_available(cls) -> bool:
        return _QT_TTS and bool(QTextToSpeech.availableEngines())

    @classmethod
    def unavailable_reason(cls) -> str:
        if not _QT_TTS:
            return "this PyQt6 build has no QtTextToSpeech module"
        return "no Qt speech engine found (install speech-dispatcher)"

    def voices(self) -> list[Voice]:
        return [Voice(name, name, v.locale().name()) for name, v in self._voices.items()]

    def set_voice(self, voice_id: str) -> None:
        super().set_voice(voice_id)
        if voice_id in self._voices:
            self._tts.setVoice(self._voices[voice_id])

    def set_rate(self, multiplier: float) -> None:
        super().set_rate(multiplier)
        # Qt rate is -1..1 where 0 is normal; map the multiplier logarithmically.
        self._tts.setRate(max(-1.0, min(1.0, math.log2(self._rate))))

    # ---- queue ----

    def speak(self, utterances: list[Utterance]) -> None:
        self.stop()
        self.enqueue(utterances)

    def enqueue(self, utterances: list[Utterance]) -> None:
        self._queue.extend(u for u in utterances if u.text.strip())
        if self._current is None and self._state != State.PAUSED:
            self._next()

    def pause(self) -> None:
        if self._state == State.SPEAKING:
            self._tts.pause()
            self._set_state(State.PAUSED)

    def resume(self) -> None:
        if self._state == State.PAUSED:
            self._set_state(State.SPEAKING)
            self._tts.resume()

    def stop(self) -> None:
        self._queue.clear()
        self._current = None
        self._tts.stop()
        self._set_state(State.IDLE)

    # ---- internals ----

    def _next(self) -> None:
        if not self._queue:
            was_active = self._state != State.IDLE
            self._current = None
            self._set_state(State.IDLE)
            if was_active:
                self.finished.emit()
            return
        self._current = self._queue.popleft()
        self._set_state(State.SPEAKING)
        self.utterance_started.emit(self._current)
        self._tts.say(self._current.text)

    def _on_tts_state(self, state) -> None:
        if state == QTextToSpeech.State.Ready and self._current is not None:
            if self._state == State.PAUSED:
                return
            self._next()
        elif state == QTextToSpeech.State.Error:
            self._on_tts_error()

    def _on_tts_error(self, *_args) -> None:
        msg = self._tts.errorString() or "speech engine error"
        self.stop()
        self.error_occurred.emit(f"TTS error: {msg}")
