from __future__ import annotations

import threading
import time

import numpy as np
import pytest

from akshara.tts import State, SystemEngine, Utterance
from akshara.tts.kokoro import KokoroEngine


class FakeSink:
    def __init__(self, delay: float = 0.0):
        self.blocks: list[np.ndarray] = []
        self.delay = delay
        self.paused = 0
        self.closed = False

    def write(self, block):
        self.blocks.append(block)
        if self.delay:
            time.sleep(self.delay)

    def pause(self):
        self.paused += 1

    def resume(self):
        pass

    def flush(self):
        pass

    def close(self):
        self.closed = True


def fake_pipeline_factory(fail_on: str | None = None, frames: int = 4096):
    def factory(lang):
        def pipe(text, voice, speed):
            if fail_on and fail_on in text:
                raise RuntimeError("boom")
            yield ("g", "p", np.full(frames, 0.1, dtype=np.float32))

        return pipe

    return factory


def _engine(qtbot, sink=None, **kw):
    sink = sink or FakeSink()
    e = KokoroEngine(pipeline_factory=fake_pipeline_factory(**kw), sink_factory=lambda: sink)
    return e, sink


def test_kokoro_plays_queue_in_order(qtbot):
    e, sink = _engine(qtbot)
    started: list[str] = []
    e.utterance_started.connect(lambda u: started.append(u.text))
    utts = [Utterance("One."), Utterance("Two."), Utterance("Three.")]
    with qtbot.waitSignal(e.finished, timeout=5000):
        e.speak(utts)
    assert started == ["One.", "Two.", "Three."]
    assert e.state == State.IDLE
    assert sum(len(b) for b in sink.blocks) == 3 * 4096
    e.shutdown()
    assert sink.closed


def test_kokoro_stop_discards_pending(qtbot):
    e, _sink = _engine(qtbot, sink=FakeSink(delay=0.02))
    started: list[str] = []
    finished = []
    e.utterance_started.connect(lambda u: started.append(u.text))
    e.finished.connect(lambda: finished.append(True))
    e.speak([Utterance(f"S{i}.") for i in range(10)])
    qtbot.waitUntil(lambda: len(started) >= 1, timeout=5000)
    e.stop()
    count = len(started)
    qtbot.wait(300)
    assert len(started) == count  # nothing from the old generation starts
    assert not finished
    assert e.state == State.IDLE
    e.shutdown()


def test_kokoro_pause_and_resume(qtbot):
    e, sink = _engine(qtbot, sink=FakeSink(delay=0.01))
    e.speak([Utterance("Long sentence.")])
    qtbot.waitUntil(lambda: e.state == State.SPEAKING, timeout=5000)
    e.pause()
    assert e.state == State.PAUSED
    qtbot.waitUntil(lambda: sink.paused >= 1, timeout=2000)
    n = len(sink.blocks)
    qtbot.wait(100)
    assert len(sink.blocks) == n  # no audio while paused
    with qtbot.waitSignal(e.finished, timeout=5000):
        e.resume()
    e.shutdown()


def test_kokoro_reports_synthesis_errors(qtbot):
    e, _ = _engine(qtbot, fail_on="bad")
    with qtbot.waitSignal(e.error_occurred, timeout=5000) as blocker:
        e.speak([Utterance("bad input.")])
    assert "boom" in blocker.args[0]
    assert e.state == State.IDLE
    e.shutdown()


def test_kokoro_rate_is_clamped():
    e = KokoroEngine(pipeline_factory=fake_pipeline_factory(), sink_factory=FakeSink)
    e.set_rate(5)
    assert e.rate == 2.0
    e.set_rate(0.1)
    assert e.rate == 0.5


def test_workers_are_daemons(qtbot):
    e, _ = _engine(qtbot)
    e.preload()
    assert all(t.daemon for t in e._threads)
    assert threading.active_count() >= 3
    e.shutdown()


@pytest.mark.skipif(not SystemEngine.is_available(), reason="no Qt speech engine")
def test_system_engine_with_mock_backend(qtbot):
    from PyQt6.QtTextToSpeech import QTextToSpeech

    if "mock" not in QTextToSpeech.availableEngines():
        pytest.skip("Qt mock speech engine not present")
    e = SystemEngine(engine_name="mock")
    started: list[str] = []
    e.utterance_started.connect(lambda u: started.append(u.text))
    with qtbot.waitSignal(e.finished, timeout=10000):
        e.speak([Utterance("Hi there."), Utterance("Bye.")])
    assert started == ["Hi there.", "Bye."]
    assert e.state == State.IDLE
