
import json
import os
from pathlib import Path

import speech_recognition as sr


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL_PATH = (
    PROJECT_ROOT / "models" / "vosk-model-en-us-0.22-lgraph"
)


class VoiceController:
    def __init__(self, model_path=None):
        self.recognizer = sr.Recognizer()
        self.model_path = Path(model_path or DEFAULT_MODEL_PATH)
        self._vosk_model = None

    def listen_once(self, mode="online"):
        """
        Listen for one spoken command.
        Returns (recognized_text, error_message).
        """
        try:
            with sr.Microphone() as source:
                self.recognizer.adjust_for_ambient_noise(
                    source, duration=0.4
                )
                audio = self.recognizer.listen(
                    source,
                    timeout=5,
                    phrase_time_limit=5,
                )

            if mode == "offline":
                if not self.model_path.exists():
                    return None, (
                        "Offline model missing: "
                        + str(self.model_path)
                    )

                if self._vosk_model is None:
                    from vosk import Model
                    self._vosk_model = Model(str(self.model_path))

                import wave
                import io
                from vosk import KaldiRecognizer

                # SpeechRecognition AudioData is normally 16-bit PCM.
                pcm_data = audio.get_raw_data(
                    convert_rate=16000,
                    convert_width=2,
                )

                vosk_recognizer = KaldiRecognizer(
                    self._vosk_model,
                    16000,
                )
                vosk_recognizer.AcceptWaveform(pcm_data)

                result = json.loads(vosk_recognizer.FinalResult())
                text = result.get("text", "").strip()

            else:
                # Audio is sent to Google's online recognizer.
                text = self.recognizer.recognize_google(
                    audio,
                    language="en-US",
                ).strip()

            if not text:
                return None, "No speech recognized"

            return text.lower(), None

        except sr.WaitTimeoutError:
            return None, "No speech detected before timeout"

        except sr.UnknownValueError:
            return None, "Speech was unclear"

        except sr.RequestError as exc:
            return None, f"Speech service error: {exc}"

        except OSError as exc:
            return None, f"Microphone error: {exc}"

        except Exception as exc:
            return None, f"Voice recognition error: {exc}"
