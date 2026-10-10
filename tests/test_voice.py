import json
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

import speech_recognition as sr
from voice.voice_controller import VoiceController


class TestVoiceController(unittest.TestCase):
    def setUp(self):
        self.vc = VoiceController()
        # Mock adjust_for_ambient_noise to avoid needing actual PyAudio audio streams in tests
        self.vc.recognizer.adjust_for_ambient_noise = MagicMock()

    def test_default_model_path_exists(self):
        # Verify the project's Vosk model folder is configured
        self.assertTrue(
            self.vc.model_path.exists(),
            f"Vosk model path not found at {self.vc.model_path}",
        )

    def test_missing_model_path_handled_gracefully(self):
        bad_vc = VoiceController(model_path="non_existent_model_directory_12345")
        text, error = bad_vc.listen_once(mode="offline")
        self.assertEqual(text, "")
        self.assertIn("Offline model error", error)

    @patch("speech_recognition.Microphone")
    def test_microphone_timeout(self, mock_mic):
        mock_source = MagicMock(spec=sr.AudioSource)
        mock_mic.return_value.__enter__.return_value = mock_source
        self.vc.recognizer.listen = MagicMock(side_effect=sr.WaitTimeoutError("timed out"))

        text, error = self.vc.listen_once(mode="online")
        self.assertEqual(text, "")
        self.assertIn("No speech detected before timeout", error)

    @patch("speech_recognition.Microphone")
    def test_microphone_os_error(self, mock_mic):
        mock_mic.side_effect = OSError("No default input device")
        text, error = self.vc.listen_once(mode="online")
        self.assertEqual(text, "")
        self.assertIn("Microphone error", error)

    @patch("speech_recognition.Microphone")
    def test_online_recognition_success(self, mock_mic):
        mock_source = MagicMock(spec=sr.AudioSource)
        mock_mic.return_value.__enter__.return_value = mock_source
        fake_audio = MagicMock()
        self.vc.recognizer.listen = MagicMock(return_value=fake_audio)
        self.vc.recognizer.recognize_google = MagicMock(return_value="Click")

        text, error = self.vc.listen_once(mode="online")
        self.assertIsNone(error)
        self.assertEqual(text, "Click")

    @patch("speech_recognition.Microphone")
    def test_online_unclear_speech(self, mock_mic):
        mock_source = MagicMock(spec=sr.AudioSource)
        mock_mic.return_value.__enter__.return_value = mock_source
        fake_audio = MagicMock()
        self.vc.recognizer.listen = MagicMock(return_value=fake_audio)
        self.vc.recognizer.recognize_google = MagicMock(side_effect=sr.UnknownValueError())

        text, error = self.vc.listen_once(mode="online")
        self.assertEqual(text, "")
        self.assertIn("Speech was unclear", error)

    @patch("speech_recognition.Microphone")
    def test_offline_recognition_success(self, mock_mic):
        mock_source = MagicMock(spec=sr.AudioSource)
        mock_mic.return_value.__enter__.return_value = mock_source
        fake_audio = MagicMock()
        fake_audio.get_raw_data.return_value = b"\x00" * 3200
        self.vc.recognizer.listen = MagicMock(return_value=fake_audio)

        with patch("vosk.KaldiRecognizer") as mock_kaldi_cls:
            mock_kaldi_instance = MagicMock()
            mock_kaldi_instance.FinalResult.return_value = json.dumps({"text": "scroll down"})
            mock_kaldi_cls.return_value = mock_kaldi_instance

            # Ensure model can load
            self.vc._load_vosk_model = MagicMock(return_value=MagicMock())

            text, error = self.vc.listen_once(mode="offline")
            self.assertIsNone(error)
            self.assertEqual(text, "scroll down")

    def test_close_releases_resources(self):
        self.vc._vosk_model = "mock_model"
        self.vc.close()
        self.assertIsNone(self.vc._vosk_model)


if __name__ == "__main__":
    unittest.main()
