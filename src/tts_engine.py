import threading
import re
from typing import Optional, List
from PyQt6.QtCore import QObject, pyqtSignal

# Kokoro TTS dependencies
_KOKORO_IMPORT_ERROR = ""
try:
    from kokoro import KPipeline
    import torch
    import numpy as np
    import simpleaudio as sa
    _KOKORO_AVAILABLE = True
except ImportError as e:
    _KOKORO_AVAILABLE = False
    _KOKORO_IMPORT_ERROR = str(e)


def split_into_sentences(text: str) -> List[str]:
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]


class TTSEngine(QObject):
    
    speech_started = pyqtSignal()
    speech_finished = pyqtSignal()
    word_changed = pyqtSignal(str)  # Current phrase being spoken
    error_occurred = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_speaking = False
        self._is_paused = False
        self._should_stop = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._play_obj = None
        
        # Kokoro settings
        self._pipeline = None
        self._voice = "af_heart"
        self._lang_code = "a"
        self._ready = False
        self._speed = 1.0
        
        # Text to speak
        self._text = ""
    
    def enable_hf(self, enabled: bool = True, voice: Optional[str] = None, lang_code: Optional[str] = None):
        if voice:
            self._voice = voice
        if lang_code:
            self._lang_code = lang_code
        self._ready = False
    
    def _ensure_ready(self):
        """Lazy-load the Kokoro pipeline."""
        if self._ready:
            return
        
        if not _KOKORO_AVAILABLE:
            raise RuntimeError(f"Kokoro TTS not available: {_KOKORO_IMPORT_ERROR}")
        
        self._pipeline = KPipeline(lang_code=self._lang_code, repo_id='hexgrad/Kokoro-82M')
        self._ready = True
    
    def speak(self, text: str):
        """Start speaking the given text."""
        self._full_stop()
        
        text = re.sub(r'\s+', ' ', text).strip()
        if not text:
            return
        
        self._text = text
        self._should_stop = False
        self._is_paused = False
        self._is_speaking = True
        
        self._thread = threading.Thread(target=self._speak_thread, daemon=True)
        self._thread.start()
    
    def _speak_thread(self):
        """Main speaking thread."""
        self.speech_started.emit()
        
        try:
            self._ensure_ready()
            sentences = split_into_sentences(self._text) or [self._text]

            for sentence in sentences:
                if self._should_stop:
                    break
                while self._is_paused and not self._should_stop:
                    threading.Event().wait(0.1)
                if self._should_stop:
                    break

                self.word_changed.emit(sentence)
                generator = self._pipeline(sentence, voice=self._voice, speed=self._speed)

                for _graphemes, _phonemes, audio in generator:
                    if self._should_stop:
                        break
                    while self._is_paused and not self._should_stop:
                        threading.Event().wait(0.1)
                    if self._should_stop:
                        break

                    arr = audio.cpu().numpy() if hasattr(audio, 'cpu') else np.asarray(audio)
                    arr16 = (np.clip(arr, -1.0, 1.0) * 32767).astype(np.int16)

                    with self._lock:
                        if self._should_stop:
                            break
                        try:
                            if self._play_obj is not None:
                                self._play_obj.stop()
                        except Exception:
                            pass
                        self._play_obj = sa.play_buffer(arr16.tobytes(), 1, 2, 24000)

                    while True:
                        with self._lock:
                            if self._play_obj is None or not self._play_obj.is_playing():
                                break
                        if self._should_stop:
                            with self._lock:
                                if self._play_obj:
                                    try:
                                        self._play_obj.stop()
                                    except Exception:
                                        pass
                            break
                        if self._is_paused:
                            with self._lock:
                                if self._play_obj:
                                    try:
                                        self._play_obj.stop()
                                    except Exception:
                                        pass
                            while self._is_paused and not self._should_stop:
                                threading.Event().wait(0.1)
                            break
                        threading.Event().wait(0.02)
                    
        except Exception as e:
            self.error_occurred.emit(f"TTS error: {e}")
        finally:
            self._is_speaking = False
            self._is_paused = False
            with self._lock:
                self._play_obj = None
            self.speech_finished.emit()
    
    def _full_stop(self):
        """Stop all speech and wait for thread."""
        self._should_stop = True
        self._is_paused = False
        
        with self._lock:
            if self._play_obj:
                try:
                    self._play_obj.stop()
                except Exception:
                    pass
                self._play_obj = None
        
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

        self._is_speaking = False
        self._thread = None

    def stop(self):
        """Stop speaking immediately."""
        self._full_stop()
    
    def pause(self):
        """Pause speaking."""
        if self._is_speaking and not self._is_paused:
            self._is_paused = True
    
    def resume(self):
        """Resume speaking."""
        if self._is_paused:
            self._is_paused = False
    
    def set_rate_multiplier(self, multiplier: float):
        """Set speech rate (0.5x to 2.0x)."""
        self._speed = max(0.5, min(multiplier, 2.0))
    
    @property
    def is_speaking(self) -> bool:
        return self._is_speaking
    
    @property
    def is_paused(self) -> bool:
        return self._is_paused
    
    def cleanup(self):
        """Clean up resources."""
        self._full_stop()
