import json
from pathlib import Path
import re
from typing import Optional, Tuple

import speech_recognition as sr


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL_PATH = PROJECT_ROOT / "models" / "vosk-model-en-us-0.22-lgraph"

# Restricted Vosk grammar for wake phrase detection in offline mode
WAKE_VOSK_GRAMMAR = json.dumps([
    "hey air control start listening",
    "hey aircontrol start listening",
    "air control start listening",
    "start listening",
    "hey air control",
    "hey aircontrol",
    "hay air control",
    "hay aircontrol",
    "air control start",
    "[unk]",
])


def normalize_wake_text(text: Optional[str]) -> str:
    """Normalizes phrasing for robust fuzzy wake word comparison."""
    if not text:
        return ""
    cleaned = text.lower().strip()
    cleaned = re.sub(r"[^\w\s]", " ", cleaned)
    tokens = cleaned.split()
    normalized = " ".join(tokens)
    # Common variations and phonetics
    normalized = normalized.replace("aircontrol", "air control")
    normalized = re.sub(r"\bhay\b", "hey", normalized)
    normalized = re.sub(r"\bstart listen\b", "start listening", normalized)
    normalized = re.sub(r"\bstop listen\b", "stop listening", normalized)
    return " ".join(normalized.split())


def match_start_wake_phrase(text: Optional[str]) -> bool:
    """
    Fuzzy matching for start wake phrases:
    "Hey AirControl, start listening", "hey air control", "hey aircontrol",
    "hay air control", "air control start listening", "start listening".
    """
    norm = normalize_wake_text(text)
    if not norm:
        return False

    if "start listening" in norm:
        return True
    if "hey air control" in norm:
        return True
    if "air control start" in norm:
        return True
    if norm in ("start", "start listen"):
        return True
    return False


def match_stop_wake_phrase(text: Optional[str]) -> bool:
    """
    Fuzzy matching for stop wake phrases:
    "Hey AirControl, stop listening", "stop listening", "hey aircontrol stop listening", etc.
    """
    norm = normalize_wake_text(text)
    if not norm:
        return False

    if "stop listening" in norm:
        return True
    if "air control stop" in norm:
        return True
    if norm in ("stop listen", "stop listening now"):
        return True
    return False


class VoiceController:
    """One-shot and wake-word online/offline speech recognition for AirControl."""

    def __init__(self, model_path=None):
        self.recognizer = sr.Recognizer()
        # Tune recognition thresholds for responsive desktop voice control
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.energy_threshold = 300
        self.recognizer.pause_threshold = 0.8
        self.recognizer.phrase_threshold = 0.1
        self.recognizer.non_speaking_duration = 0.3

        self.model_path = Path(model_path) if model_path else DEFAULT_MODEL_PATH
        self._vosk_model = None
        self._vosk_load_error = None
        self._calibrated = False

    def calibrate_microphone(self, source, duration=0.2):
        """Calibrate ambient noise once with safe energy threshold bounds."""
        if not self._calibrated:
            try:
                self.recognizer.adjust_for_ambient_noise(source, duration=duration)
                # Clamp threshold to prevent becoming deaf if speech occurred during calibration
                self.recognizer.energy_threshold = max(80, min(self.recognizer.energy_threshold, 1000))
            except Exception:
                pass
            self._calibrated = True

    def _load_vosk_model(self):
        if self._vosk_model is not None:
            return self._vosk_model
        if self._vosk_load_error:
            raise RuntimeError(self._vosk_load_error)
        try:
            from vosk import Model
            if not self.model_path.exists():
                raise FileNotFoundError(
                    f"Vosk model not found at {self.model_path}. "
                    "Switch to Online mode or verify models folder."
                )
            self._vosk_model = Model(str(self.model_path))
            return self._vosk_model
        except Exception as exc:
            self._vosk_load_error = str(exc)
            raise

    def listen_wake_phrase(
        self, mode="online", on_status=None, timeout=3, phrase_time_limit=3
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Lightweight listener checking strictly for start wake phrases.
        Returns: (detected: bool, phrase: str, error: Optional[str])
        """
        mode = (mode or "online").lower().strip()
        model = None
        if mode == "offline":
            try:
                model = self._load_vosk_model()
            except Exception as exc:
                return False, "", f"Offline model error: {exc}"

        try:
            with sr.Microphone() as source:
                self.calibrate_microphone(source, duration=0.15)
                audio = self.recognizer.listen(
                    source, timeout=timeout, phrase_time_limit=phrase_time_limit
                )

            if mode == "offline" and model:
                from vosk import KaldiRecognizer
                pcm_data = audio.get_raw_data(convert_rate=16000, convert_width=2)
                if not pcm_data or len(pcm_data) < 1600:
                    return False, "", None
                # Use restricted grammar for speed
                vosk_recognizer = KaldiRecognizer(model, 16000, WAKE_VOSK_GRAMMAR)
                vosk_recognizer.AcceptWaveform(pcm_data)
                result = json.loads(vosk_recognizer.FinalResult())
                text = result.get("text", "").strip()
                if match_start_wake_phrase(text):
                    return True, text, None
                return False, text, None

            if mode == "online":
                try:
                    text = self.recognizer.recognize_google(audio)
                    text = " ".join(text.split()).strip()
                    if match_start_wake_phrase(text):
                        return True, text, None
                    return False, text, None
                except (sr.UnknownValueError, sr.WaitTimeoutError):
                    return False, "", None
                except sr.RequestError as exc:
                    return False, "", f"Online recognition network error: {exc}"

        except (sr.WaitTimeoutError, sr.UnknownValueError):
            return False, "", None
        except OSError as exc:
            return False, "", f"Microphone error: {exc}"
        except Exception as exc:
            return False, "", str(exc)

        return False, "", None

    def listen_once(self, mode="online", on_status=None, max_retries=1):
        """Return (recognized_text, error_message)."""
        mode = (mode or "online").lower().strip()
        if mode not in ("online", "offline"):
            return "", f"Unknown voice mode: {mode}"

        if mode == "offline":
            try:
                model = self._load_vosk_model()
            except Exception as exc:
                return "", f"Offline model error: {exc}"

        attempts = 0
        while attempts <= max_retries:
            attempts += 1
            try:
                with sr.Microphone() as source:
                    # Calibrate once if needed without consuming speech on every attempt
                    self.calibrate_microphone(source, duration=0.2)
                    if on_status:
                        on_status("Listening...")
                    audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=5)

                if on_status:
                    on_status("Recognizing...")

                if mode == "offline":
                    from vosk import KaldiRecognizer
                    pcm_data = audio.get_raw_data(convert_rate=16000, convert_width=2)
                    if not pcm_data or len(pcm_data) < 1600:
                        return "", "No speech recognized. Try speaking clearly and again."
                    vosk_recognizer = KaldiRecognizer(model, 16000)
                    vosk_recognizer.AcceptWaveform(pcm_data)
                    result = json.loads(vosk_recognizer.FinalResult())
                    text = result.get("text", "")
                    text = " ".join(text.split()).strip()
                    if not text:
                        return "", "No speech recognized. Try speaking clearly and again."
                    return text, None

                if mode == "online":
                    try:
                        text = self.recognizer.recognize_google(audio)
                        text = " ".join(text.split()).strip()
                        if not text:
                            return "", "No speech recognized. Try speaking clearly and again."
                        return text, None
                    except sr.UnknownValueError:
                        if attempts <= max_retries:
                            if on_status:
                                on_status("Speech unclear. Listening again...")
                            continue
                        return "", "Speech was unclear. Please speak clearly near the microphone."
                    except sr.RequestError as exc:
                        return "", f"Online recognition unavailable: {exc}. Switch to Offline mode or check network."

            except sr.WaitTimeoutError:
                return "", "No speech detected before timeout. Click Listen and speak clearly."
            except sr.UnknownValueError:
                if attempts <= max_retries:
                    if on_status:
                        on_status("Speech unclear. Listening again...")
                    continue
                return "", "Speech was unclear. Please speak clearly near the microphone."
            except OSError as exc:
                return "", f"Microphone error: {exc}. Please check your audio input device and permissions."
            except Exception as exc:
                return "", str(exc)

        return "", "Speech was unclear. Please speak clearly near the microphone."

    def close(self):
        """Cleanly release cached model resources."""
        self._vosk_model = None
        self._vosk_load_error = None
