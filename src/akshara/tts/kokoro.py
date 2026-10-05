"""
Kokoro-82M neural TTS backend.

Two long-lived worker threads form a pipeline:

    GUI thread ── jobs ──▶ synth thread ── audio ──▶ playback thread ──▶ speakers

The synth thread renders the *next* sentences while the current one plays,
so there is no gap between sentences. Every request carries a generation
number; ``stop()``/``speak()`` bump it, and workers silently drop anything
from an older generation. All signal emission and state changes are
marshalled back to the GUI thread through ``_post``.
"""

from __future__ import annotations

import importlib.util
import queue
import threading
from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

from .base import SpeechEngine, State, Utterance, Voice

SAMPLE_RATE = 24_000
BLOCK_FRAMES = 1024  # ~43 ms: upper bound on pause/stop latency
LOOKAHEAD = 3  # synthesised utterances buffered ahead of playback
REPO_ID = "hexgrad/Kokoro-82M"

VOICES: list[Voice] = [
    Voice("af_heart", "Heart (US, female)", "en-US"),
    Voice("af_bella", "Bella (US, female)", "en-US"),
    Voice("af_nicole", "Nicole (US, female)", "en-US"),
    Voice("af_sarah", "Sarah (US, female)", "en-US"),
    Voice("af_sky", "Sky (US, female)", "en-US"),
    Voice("am_adam", "Adam (US, male)", "en-US"),
    Voice("am_michael", "Michael (US, male)", "en-US"),
    Voice("am_fenrir", "Fenrir (US, male)", "en-US"),
    Voice("am_puck", "Puck (US, male)", "en-US"),
    Voice("bf_emma", "Emma (UK, female)", "en-GB"),
    Voice("bf_isabella", "Isabella (UK, female)", "en-GB"),
    Voice("bm_george", "George (UK, male)", "en-GB"),
    Voice("bm_lewis", "Lewis (UK, male)", "en-GB"),
]
DEFAULT_VOICE = "af_heart"


# ---------- Audio output -----------------------------------------------------


class AudioSink:
    """Blocking float32 mono output. Only ever touched from the playback thread."""

    def __init__(self, sample_rate: int = SAMPLE_RATE):
        import sounddevice as sd

        self._stream = sd.OutputStream(samplerate=sample_rate, channels=1, dtype="float32")
        self._stream.start()

    def write(self, block) -> None:
        self._stream.write(block.reshape(-1, 1))

    def pause(self) -> None:
        self._stream.abort()  # drop the device buffer so pause is immediate

    def resume(self) -> None:
        self._stream.start()

    def flush(self) -> None:
        self._stream.abort()
        self._stream.start()

    def close(self) -> None:
        self._stream.close()


def _default_pipeline_factory(lang_code: str):
    from kokoro import KPipeline

    return KPipeline(lang_code=lang_code, repo_id=REPO_ID)


# ---------- Engine -----------------------------------------------------------

_SHUTDOWN = object()


class KokoroEngine(SpeechEngine):
    label = "Neural (Kokoro)"

    _post = pyqtSignal(object)  # callable to run on the GUI thread

    def __init__(
        self,
        parent: QObject | None = None,
        pipeline_factory: Callable[[str], Any] | None = None,
        sink_factory: Callable[[], Any] | None = None,
    ):
        super().__init__(parent)
        self._voice = DEFAULT_VOICE
        self._pipeline_factory = pipeline_factory or _default_pipeline_factory
        self._sink_factory = sink_factory or AudioSink
        self._pipelines: dict[str, Any] = {}

        # Emitted from worker threads; AutoConnection queues onto the GUI thread.
        self._post.connect(self._run_posted)

        self._lock = threading.Lock()
        self._gen = 0
        self._pending = 0  # utterances queued but not yet fully played
        self._jobs: queue.Queue = queue.Queue()
        self._audio: queue.Queue = queue.Queue(maxsize=LOOKAHEAD)
        self._unpaused = threading.Event()
        self._unpaused.set()
        self._threads: list[threading.Thread] = []

    @pyqtSlot(object)
    def _run_posted(self, fn: Callable[[], None]) -> None:
        fn()

    # ---- availability ----

    @classmethod
    def is_available(cls) -> bool:
        return all(importlib.util.find_spec(m) for m in ("kokoro", "sounddevice", "numpy"))

    @classmethod
    def unavailable_reason(cls) -> str:
        missing = [m for m in ("kokoro", "sounddevice", "numpy") if not importlib.util.find_spec(m)]
        return f"missing Python packages: {', '.join(missing)} (install with the 'tts' extra)"

    def voices(self) -> list[Voice]:
        return list(VOICES)

    # ---- public API (GUI thread) ----

    def preload(self) -> None:
        self._ensure_threads()
        self._jobs.put(("load", self._voice))

    def speak(self, utterances: list[Utterance]) -> None:
        self.stop()
        self.enqueue(utterances)

    def enqueue(self, utterances: list[Utterance]) -> None:
        utterances = [u for u in utterances if u.text.strip()]
        if not utterances:
            if self._state == State.IDLE:
                self.finished.emit()
            return
        self._ensure_threads()
        with self._lock:
            gen = self._gen
            self._pending += len(utterances)
        if self._state == State.IDLE:
            self._set_state(State.LOADING if not self._pipelines else State.SPEAKING)
        voice, rate = self._voice, self._rate
        for u in utterances:
            self._jobs.put(("speak", gen, u, voice, rate))

    def pause(self) -> None:
        if self._state in (State.SPEAKING, State.LOADING):
            self._unpaused.clear()
            self._set_state(State.PAUSED)

    def resume(self) -> None:
        if self._state == State.PAUSED:
            self._unpaused.set()
            self._set_state(State.SPEAKING)

    def stop(self) -> None:
        with self._lock:
            self._gen += 1
            self._pending = 0
        _drain(self._jobs)
        _drain(self._audio)
        self._unpaused.set()
        self._set_state(State.IDLE)

    def shutdown(self) -> None:
        self.stop()
        if self._threads:
            self._jobs.put(_SHUTDOWN)
            for t in self._threads:
                t.join(timeout=2.0)
            self._threads = []

    # ---- workers ----

    def _ensure_threads(self) -> None:
        if self._threads:
            return
        self._threads = [
            threading.Thread(target=self._synth_loop, name="tts-synth", daemon=True),
            threading.Thread(target=self._play_loop, name="tts-play", daemon=True),
        ]
        for t in self._threads:
            t.start()

    def _current(self, gen: int) -> bool:
        return gen == self._gen

    def _pipeline(self, voice: str):
        lang = voice[:1] or "a"
        pipe = self._pipelines.get(lang)
        if pipe is None:
            pipe = self._pipeline_factory(lang)
            self._pipelines[lang] = pipe
        return pipe

    def _synth_loop(self) -> None:
        import numpy as np

        while True:
            job = self._jobs.get()
            if job is _SHUTDOWN:
                self._audio.put(_SHUTDOWN)
                return
            try:
                if job[0] == "load":
                    self._pipeline(job[1])
                    continue
                _, gen, utt, voice, rate = job
                if not self._current(gen):
                    continue
                pipe = self._pipeline(voice)
                chunks = []
                for result in pipe(utt.text, voice=voice, speed=rate):
                    if not self._current(gen):
                        break
                    audio = getattr(result, "audio", None)
                    if audio is None and isinstance(result, tuple):
                        audio = result[2]
                    if audio is None:
                        continue
                    arr = audio.cpu().numpy() if hasattr(audio, "cpu") else np.asarray(audio)
                    chunks.append(arr.astype(np.float32, copy=False))
                if not self._current(gen):
                    continue
                pcm = np.concatenate(chunks) if chunks else np.zeros(0, np.float32)
                self._put_audio((gen, utt, np.clip(pcm, -1.0, 1.0)))
            except Exception as e:  # report and keep the worker alive
                msg = f"TTS error: {e}"
                self._post.emit(lambda m=msg: self._fail(m))

    def _put_audio(self, item) -> None:
        gen = item[0]
        while self._current(gen):
            try:
                self._audio.put(item, timeout=0.1)
                return
            except queue.Full:
                continue

    def _play_loop(self) -> None:
        sink = None
        try:
            while True:
                item = self._audio.get()
                if item is _SHUTDOWN:
                    return
                gen, utt, pcm = item
                if not self._current(gen):
                    continue
                if sink is None:
                    sink = self._sink_factory()
                self._post.emit(lambda g=gen, u=utt: self._on_started(g, u))
                interrupted = False
                for pos in range(0, len(pcm), BLOCK_FRAMES):
                    if not self._unpaused.is_set():
                        sink.pause()
                        self._unpaused.wait()
                        if self._current(gen):
                            sink.resume()
                    if not self._current(gen):
                        interrupted = True
                        break
                    sink.write(pcm[pos : pos + BLOCK_FRAMES])
                if interrupted:
                    sink.flush()
                    continue
                self._post.emit(lambda g=gen: self._on_done(g))
        except Exception as e:
            msg = f"Audio output error: {e}"
            self._post.emit(lambda m=msg: self._fail(m))
        finally:
            if sink is not None:
                sink.close()

    # ---- GUI-thread callbacks ----

    def _on_started(self, gen: int, utt: Utterance) -> None:
        if not self._current(gen):
            return
        if self._state == State.LOADING:
            self._set_state(State.SPEAKING)
        self.utterance_started.emit(utt)

    def _on_done(self, gen: int) -> None:
        with self._lock:
            if gen != self._gen:
                return
            self._pending -= 1
            drained = self._pending <= 0
        if drained:
            self._set_state(State.IDLE)
            self.finished.emit()

    def _fail(self, message: str) -> None:
        self.stop()
        self.error_occurred.emit(message)


def _drain(q: queue.Queue) -> list:
    items: list = []
    while True:
        try:
            item = q.get_nowait()
        except queue.Empty:
            return items
        if item is _SHUTDOWN:  # never swallow shutdown
            q.put(item)
            return items
        items.append(item)
