import { useState, useCallback, useRef } from 'react';
import * as Speech from 'expo-speech';

export type TTSState = 'idle' | 'speaking' | 'paused';

export function useTTS() {
  const [state, setState] = useState<TTSState>('idle');
  const [speed, setSpeedState] = useState(1.0);
  const [currentSentenceIdx, setCurrentSentenceIdx] = useState(-1);
  const sentencesRef = useRef<string[]>([]);
  const stateRef = useRef<TTSState>('idle');
  const speedRef = useRef(1.0);

  const updateState = (s: TTSState) => {
    stateRef.current = s;
    setState(s);
  };

  const splitSentences = (text: string): string[] => {
    return text
      .split(/(?<=[.!?])\s+/)
      .map(s => s.trim())
      .filter(s => s.length > 0);
  };

  const speakFrom = useCallback((sentences: string[], startIdx: number) => {
    if (startIdx >= sentences.length) {
      updateState('idle');
      setCurrentSentenceIdx(-1);
      return;
    }

    setCurrentSentenceIdx(startIdx);
    updateState('speaking');

    Speech.speak(sentences[startIdx], {
      rate: speedRef.current,
      onDone: () => {
        if (stateRef.current === 'speaking') {
          speakFrom(sentences, startIdx + 1);
        }
      },
      onStopped: () => {
        // handled externally
      },
      onError: () => {
        updateState('idle');
        setCurrentSentenceIdx(-1);
      },
    });
  }, []);

  const speak = useCallback((text: string) => {
    Speech.stop();
    const sentences = splitSentences(text);
    sentencesRef.current = sentences;
    if (sentences.length === 0) return;
    speakFrom(sentences, 0);
  }, [speakFrom]);

  const pause = useCallback(async () => {
    if (stateRef.current === 'speaking') {
      await Speech.pause();
      updateState('paused');
    }
  }, []);

  const resume = useCallback(async () => {
    if (stateRef.current === 'paused') {
      await Speech.resume();
      updateState('speaking');
    }
  }, []);

  const stop = useCallback(() => {
    Speech.stop();
    updateState('idle');
    setCurrentSentenceIdx(-1);
    sentencesRef.current = [];
  }, []);

  const setSpeed = useCallback((s: number) => {
    speedRef.current = s;
    setSpeedState(s);
  }, []);

  return {
    state,
    speed,
    currentSentenceIdx,
    sentences: sentencesRef.current,
    speak,
    pause,
    resume,
    stop,
    setSpeed,
    isIdle: state === 'idle',
    isSpeaking: state === 'speaking',
    isPaused: state === 'paused',
  };
}
