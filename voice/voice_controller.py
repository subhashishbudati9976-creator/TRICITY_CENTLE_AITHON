from pathlib import Path

import speech_recognition as sr


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL_PATH = PROJECT_ROOT / "models" / "vosk-model-en-us-0.22-lgraph"


class VoiceController:
    """One-shot online/offline speech recognition for AirControl."""

    def __init__(self, model_path=None):
        self.recognizer = sr.Recognizer()
        self.model_path = Path(model_path) if model_path else DEFAULT_MODEL_PATH
        self._vosk_model = None
        self._vosk_load_error = None

    def _load_vosk_model(self):
        if self._vosk_model is not None:
            return self._vosk_model
        if self._vosk_load_error:
            raise RuntimeError(self._vosk_load_error)
        try:
            from vosk import Model
            if not self.model_path.exists():
                raise FileNotFoundError(
                    f"Vosk model not found: {self.model_path}. "
                    "Place the extracted model folder inside the project's models folder."
                )
            self._vosk_model = Model(str(self.model_path))
            return self._vosk_model
        except Exception as exc:
            self._vosk_load_error = str(exc)
            raise

    def listen_once(self, mode="online"):
        """Return (recognized_text, error_message)."""
        mode = (mode or "online").lower().strip()
        try:
            with sr.Microphone() as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.35)
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=6)

            if mode == "offline":
                try:
                    model = self._load_vosk_model()
                except Exception as exc:
                    return "", f"Offline model error: {exc}"
                from vosk import KaldiRecognizer
                import json
                pcm_data = audio.get_raw_data(convert_rate=16000, convert_width=2)
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
                    return "", "Speech was unclear. Please try again."
                except sr.RequestError as exc:
                    return "", f"Online recognition unavailable: {exc}"

            return "", f"Unknown voice mode: {mode}"

        except sr.WaitTimeoutError:
            return "", "No speech detected before timeout. Try again."
        except sr.UnknownValueError:
            return "", "Speech was unclear. Please try again."
        except OSError as exc:
            return "", f"Microphone error: {exc}"
        except Exception as exc:
            return "", str(exc)

    def close(self):
        """Cleanly release cached model resources."""
        self._vosk_model = None
        self._vosk_load_error = None
