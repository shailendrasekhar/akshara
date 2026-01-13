"""
Text-to-Speech Engine Module
Uses subprocess-based approach with word-by-word progress tracking.
"""

import subprocess
import threading
import re
import os
import signal
from typing import Optional, List
from PyQt6.QtCore import QObject, pyqtSignal


class TTSEngine(QObject):
    """
    TTS Engine using espeak-ng subprocess for true pause/stop control.
    Provides word-by-word progress for highlighting.
    """
    
    speech_started = pyqtSignal()
    speech_finished = pyqtSignal()
    word_changed = pyqtSignal(str)  # Current word being spoken
    error_occurred = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._process: Optional[subprocess.Popen] = None
        self._words: List[str] = []
        self._current_index = 0
        self._is_speaking = False
        self._is_paused = False
        self._should_stop = False
        self._rate = 175  # espeak default
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()  # Prevent race conditions
    
    def speak(self, text: str):
        """Start speaking the given text."""
        # First, fully stop any existing speech
        self._full_stop()
        
        if not text.strip():
            return
        
        # Split into words for word-by-word highlighting
        self._words = self._split_into_words(text)
        if not self._words:
            return
        
        self._current_index = 0
        self._should_stop = False
        self._is_paused = False
        self._is_speaking = True
        
        # Start speaking in a thread
        self._thread = threading.Thread(target=self._speak_loop, daemon=True)
        self._thread.start()
    
    def _split_into_words(self, text: str) -> List[str]:
        """Split text into words/phrases for speaking."""
        # Clean up text
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Split into small chunks (groups of 3-5 words for natural speech)
        words = text.split()
        chunks = []
        
        chunk_size = 4  # Words per chunk for balance of speed and highlighting
        for i in range(0, len(words), chunk_size):
            chunk = ' '.join(words[i:i + chunk_size])
            if chunk.strip():
                chunks.append(chunk)
        
        return chunks
    
    def _speak_loop(self):
        """Main speaking loop."""
        self.speech_started.emit()
        
        try:
            while self._current_index < len(self._words) and not self._should_stop:
                # Check for pause
                while self._is_paused and not self._should_stop:
                    threading.Event().wait(0.1)
                
                if self._should_stop:
                    break
                
                word_chunk = self._words[self._current_index]
                self.word_changed.emit(word_chunk)
                
                # Speak this chunk
                with self._lock:
                    if self._should_stop:
                        break
                    
                    try:
                        self._process = subprocess.Popen(
                            ['espeak-ng', '-s', str(self._rate), word_chunk],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL
                        )
                    except FileNotFoundError:
                        try:
                            self._process = subprocess.Popen(
                                ['espeak', '-s', str(self._rate), word_chunk],
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL
                            )
                        except FileNotFoundError:
                            self.error_occurred.emit("espeak-ng not found")
                            break
                
                # Wait for process to complete (outside lock)
                if self._process:
                    self._process.wait()
                
                if self._should_stop:
                    break
                
                self._current_index += 1
                
        finally:
            self._is_speaking = False
            self._is_paused = False
            with self._lock:
                self._process = None
            self.speech_finished.emit()
    
    def _full_stop(self):
        """Completely stop all speech and wait for thread to finish."""
        self._should_stop = True
        self._is_paused = False
        
        # Kill any running process
        with self._lock:
            if self._process:
                try:
                    self._process.terminate()
                    try:
                        self._process.wait(timeout=0.3)
                    except subprocess.TimeoutExpired:
                        self._process.kill()
                        self._process.wait(timeout=0.3)
                except:
                    pass
                self._process = None
        
        # Wait for thread to finish
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
            with self._lock:
                if self._process:
                    try:
                        self._process.terminate()
                    except:
                        pass
    
    def resume(self):
        """Resume speaking."""
        if self._is_paused:
            self._is_paused = False
    
    def set_rate_multiplier(self, multiplier: float):
        """Set speech rate (0.5x to 2.0x)."""
        self._rate = int(175 * multiplier)
        self._rate = max(80, min(self._rate, 400))
    
    @property
    def is_speaking(self) -> bool:
        return self._is_speaking
    
    @property
    def is_paused(self) -> bool:
        return self._is_paused
    
    def cleanup(self):
        """Clean up resources."""
        self._full_stop()
