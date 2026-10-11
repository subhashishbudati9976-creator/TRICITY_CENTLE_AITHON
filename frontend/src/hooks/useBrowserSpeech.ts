import { useState, useEffect, useRef, useCallback } from 'react';

export interface SpeechSettings {
  voiceURI: string;
  rate: number;
  pitch: number;
  enabled: boolean;
}

const STORAGE_KEY = 'aircontrol_speech_settings';

export function cleanTextForSpeech(rawText: string): string {
  if (!rawText) return '';

  let cleaned = rawText;

  // 1. Remove markdown code blocks
  cleaned = cleaned.replace(/```[\s\S]*?```/g, ' ');

  // 2. Remove inline code
  cleaned = cleaned.replace(/`([^`]+)`/g, '$1');

  // 3. Remove URLs
  cleaned = cleaned.replace(/https?:\/\/\S+/gi, ' ');

  // 4. Convert markdown links [text](url) -> text
  cleaned = cleaned.replace(/\[([^\]]+)\]\([^)]+\)/g, '$1');

  // 5. Remove markdown headers, list markers, blockquotes
  cleaned = cleaned.replace(/^[#>\-*+]\s+/gm, ' ');

  // 6. Remove bold/italics markers
  cleaned = cleaned.replace(/[*_]{1,3}([^*_]+)[*_]{1,3}/g, '$1');

  // 7. Remove emojis and symbols
  cleaned = cleaned.replace(
    /[\u{1F600}-\u{1F64F}\u{1F300}-\u{1F5FF}\u{1F680}-\u{1F6FF}\u{1F1E0}-\u{1F1FF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}\u{FE00}-\u{FE0F}]/gu,
    ''
  );

  // 8. Collapse whitespace
  cleaned = cleaned.replace(/\s+/g, ' ').trim();
  return cleaned;
}

export function chunkTextForSpeech(text: string, maxLen = 180): string[] {
  const clean = cleanTextForSpeech(text);
  if (!clean) return [];

  if (clean.length <= maxLen) return [clean];

  const chunks: string[] = [];
  // Split on sentence boundaries
  const sentences = clean.split(/(?<=[.?!])\s+/);

  let currentChunk = '';

  for (const sentence of sentences) {
    if ((currentChunk + ' ' + sentence).trim().length <= maxLen) {
      currentChunk = (currentChunk + ' ' + sentence).trim();
    } else {
      if (currentChunk) {
        chunks.push(currentChunk);
        currentChunk = '';
      }
      if (sentence.length <= maxLen) {
        currentChunk = sentence;
      } else {
        // Sentence itself is long, split on commas or spaces
        const parts = sentence.split(/(?<=[,;:])\s+/);
        for (const p of parts) {
          if ((currentChunk + ' ' + p).trim().length <= maxLen) {
            currentChunk = (currentChunk + ' ' + p).trim();
          } else {
            if (currentChunk) chunks.push(currentChunk);
            currentChunk = p;
          }
        }
      }
    }
  }

  if (currentChunk) {
    chunks.push(currentChunk);
  }

  return chunks.filter((c) => c.trim().length > 0);
}

export function useBrowserSpeech(onSpeakingChange?: (speaking: boolean) => void) {
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);
  const [selectedVoice, setSelectedVoice] = useState<SpeechSynthesisVoice | null>(null);
  const [rate, setRate] = useState<number>(1.0);
  const [pitch, setPitch] = useState<number>(1.0);
  const [speakerEnabled, setSpeakerEnabled] = useState<boolean>(true);
  const [isUnlocked, setIsUnlocked] = useState<boolean>(false);
  const [isSpeaking, setIsSpeaking] = useState<boolean>(false);

  const queueRef = useRef<string[]>([]);
  const currentChunkIndexRef = useRef<number>(0);
  const endTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isSpeakingRef = useRef<boolean>(false);

  // Safely read from localStorage
  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved) as Partial<SpeechSettings>;
        if (typeof parsed.rate === 'number') setRate(parsed.rate);
        if (typeof parsed.pitch === 'number') setPitch(parsed.pitch);
        if (typeof parsed.enabled === 'boolean') setSpeakerEnabled(parsed.enabled);
      }
    } catch {
      // Ignore localStorage access failures
    }
  }, []);

  // Save settings safely
  const saveSettings = useCallback(
    (newSettings: Partial<SpeechSettings>) => {
      try {
        const current: SpeechSettings = {
          voiceURI: selectedVoice?.voiceURI || '',
          rate,
          pitch,
          enabled: speakerEnabled,
          ...newSettings,
        };
        localStorage.setItem(STORAGE_KEY, JSON.stringify(current));
      } catch {
        // Ignore localStorage access failures
      }
    },
    [selectedVoice, rate, pitch, speakerEnabled]
  );

  // Load and select voices
  useEffect(() => {
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) return;

    const synth = window.speechSynthesis;

    const loadVoices = () => {
      const available = synth.getVoices();
      if (!available || available.length === 0) return;
      setVoices(available);

      // Check saved voice URI
      let preferredVoice: SpeechSynthesisVoice | undefined;
      try {
        const saved = localStorage.getItem(STORAGE_KEY);
        if (saved) {
          const parsed = JSON.parse(saved);
          if (parsed.voiceURI) {
            preferredVoice = available.find((v) => v.voiceURI === parsed.voiceURI);
          }
        }
      } catch {
        // Ignore
      }

      if (!preferredVoice) {
        // Preference: Natural Chrome English voices
        preferredVoice =
          available.find((v) => v.name.includes('Google US English')) ||
          available.find((v) => v.name.includes('Google UK English Female')) ||
          available.find((v) => v.lang === 'en-US' && v.name.toLowerCase().includes('natural')) ||
          available.find((v) => v.lang === 'en-IN') ||
          available.find((v) => v.lang === 'en-US') ||
          available.find((v) => v.lang.startsWith('en')) ||
          available[0];
      }

      if (preferredVoice) {
        setSelectedVoice(preferredVoice);
      }
    };

    loadVoices();
    synth.onvoiceschanged = loadVoices;

    return () => {
      synth.onvoiceschanged = null;
    };
  }, []);

  // One-time click unlock for browser autoplay policy
  const unlockAudio = useCallback(() => {
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) return;
    try {
      const synth = window.speechSynthesis;
      // Utterance with silent space to prime Chrome Web Speech engine
      const prime = new SpeechSynthesisUtterance(' ');
      prime.volume = 0.01;
      prime.rate = 2.0;
      synth.speak(prime);
      setIsUnlocked(true);
    } catch {
      setIsUnlocked(true);
    }
  }, []);

  useEffect(() => {
    const handleFirstClick = () => {
      unlockAudio();
      window.removeEventListener('click', handleFirstClick);
    };
    window.addEventListener('click', handleFirstClick, { once: true });
    return () => window.removeEventListener('click', handleFirstClick);
  }, [unlockAudio]);

  const notifySpeaking = useCallback(
    (speaking: boolean) => {
      isSpeakingRef.current = speaking;
      setIsSpeaking(speaking);
      if (onSpeakingChange) {
        onSpeakingChange(speaking);
      }
    },
    [onSpeakingChange]
  );

  // Stop current speech
  const stopSpeaking = useCallback(() => {
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) return;
    if (endTimeoutRef.current) {
      clearTimeout(endTimeoutRef.current);
      endTimeoutRef.current = null;
    }
    window.speechSynthesis.cancel();
    queueRef.current = [];
    currentChunkIndexRef.current = 0;
    notifySpeaking(false);
  }, [notifySpeaking]);

  // Play next chunk in queue
  const playNextChunk = useCallback(() => {
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) return;
    const synth = window.speechSynthesis;

    if (currentChunkIndexRef.current >= queueRef.current.length) {
      // Finished all chunks - apply 500ms grace period before backend unmutes microphone
      if (endTimeoutRef.current) clearTimeout(endTimeoutRef.current);
      endTimeoutRef.current = setTimeout(() => {
        notifySpeaking(false);
      }, 500);
      return;
    }

    const chunk = queueRef.current[currentChunkIndexRef.current];
    currentChunkIndexRef.current += 1;

    try {
      const utterance = new SpeechSynthesisUtterance(chunk);
      if (selectedVoice) utterance.voice = selectedVoice;
      utterance.rate = rate;
      utterance.pitch = pitch;

      utterance.onstart = () => {
        if (!isSpeakingRef.current) {
          notifySpeaking(true);
        }
      };

      utterance.onend = () => {
        playNextChunk();
      };

      utterance.onerror = (e) => {
        console.warn('SpeechSynthesis error:', e);
        playNextChunk();
      };

      synth.speak(utterance);
    } catch (err) {
      console.error('Speech utterance failed:', err);
      playNextChunk();
    }
  }, [selectedVoice, rate, pitch, notifySpeaking]);

  // Main speak function
  const speakText = useCallback(
    (rawText: string) => {
      if (!speakerEnabled || !rawText) return;
      if (typeof window === 'undefined' || !('speechSynthesis' in window)) return;

      // Cancel any ongoing speech when new answer arrives
      if (endTimeoutRef.current) {
        clearTimeout(endTimeoutRef.current);
        endTimeoutRef.current = null;
      }
      window.speechSynthesis.cancel();

      const chunks = chunkTextForSpeech(rawText);
      if (chunks.length === 0) return;

      queueRef.current = chunks;
      currentChunkIndexRef.current = 0;

      // Notify speaking immediately to block mic echo
      notifySpeaking(true);
      playNextChunk();
    },
    [speakerEnabled, notifySpeaking, playNextChunk]
  );

  const toggleSpeaker = useCallback(() => {
    setSpeakerEnabled((prev) => {
      const next = !prev;
      saveSettings({ enabled: next });
      if (!next) {
        stopSpeaking();
      }
      return next;
    });
  }, [saveSettings, stopSpeaking]);

  const updateVoice = useCallback(
    (voiceURI: string) => {
      const found = voices.find((v) => v.voiceURI === voiceURI);
      if (found) {
        setSelectedVoice(found);
        saveSettings({ voiceURI });
      }
    },
    [voices, saveSettings]
  );

  const updateRate = useCallback(
    (newRate: number) => {
      setRate(newRate);
      saveSettings({ rate: newRate });
    },
    [saveSettings]
  );

  const updatePitch = useCallback(
    (newPitch: number) => {
      setPitch(newPitch);
      saveSettings({ pitch: newPitch });
    },
    [saveSettings]
  );

  return {
    voices,
    selectedVoice,
    rate,
    pitch,
    speakerEnabled,
    isUnlocked,
    isSpeaking,
    speakText,
    stopSpeaking,
    toggleSpeaker,
    unlockAudio,
    updateVoice,
    updateRate,
    updatePitch,
  };
}
