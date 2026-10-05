"""Text-to-speech engines and the read-aloud controller."""

from __future__ import annotations

from PyQt6.QtCore import QObject

from .base import SpeechEngine, State, Utterance, Voice
from .kokoro import KokoroEngine
from .system import SystemEngine

ENGINES: dict[str, type[SpeechEngine]] = {
    "kokoro": KokoroEngine,
    "system": SystemEngine,
}


def create_engine(preferred: str = "kokoro", parent: QObject | None = None) -> SpeechEngine | None:
    """Instantiate `preferred` if usable, else the first available engine, else None."""
    order = [preferred, *(k for k in ENGINES if k != preferred)]
    for key in order:
        cls = ENGINES.get(key)
        if cls is not None and cls.is_available():
            try:
                return cls(parent)
            except Exception:  # backend present but unusable (e.g. no audio daemon)
                continue
    return None


def engine_key(engine: SpeechEngine) -> str:
    return next((k for k, cls in ENGINES.items() if isinstance(engine, cls)), "")


__all__ = [
    "ENGINES",
    "KokoroEngine",
    "SpeechEngine",
    "State",
    "SystemEngine",
    "Utterance",
    "Voice",
    "create_engine",
    "engine_key",
]
