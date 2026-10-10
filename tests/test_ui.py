import unittest
from unittest.mock import MagicMock, patch

from ui.theme import (
    COLOR_CHARCOAL,
    COLOR_INDIGO,
    COLOR_IVORY,
    COLOR_SAGE,
    COLOR_STONE,
    COLOR_VERMILION,
)
from ui.dashboard import SectionHeader, TelemetryLog, ValueSlider


class TestUIThemeAndComponents(unittest.TestCase):
    def test_theme_color_tokens(self):
        self.assertEqual(COLOR_IVORY, "#F2EFE7")
        self.assertEqual(COLOR_CHARCOAL, "#20211F")
        self.assertEqual(COLOR_INDIGO, "#273449")
        self.assertEqual(COLOR_VERMILION, "#C74735")
        self.assertEqual(COLOR_STONE, "#B9B5AA")
        self.assertEqual(COLOR_SAGE, "#7C8B78")

    @patch("customtkinter.CTkTextbox")
    @patch("customtkinter.CTkFrame")
    @patch("customtkinter.CTkLabel")
    def test_telemetry_log_formatting(self, mock_label, mock_frame, mock_textbox_cls):
        mock_textbox_inst = MagicMock()
        mock_textbox_cls.return_value = mock_textbox_inst

        master = MagicMock()
        log = TelemetryLog.__new__(TelemetryLog)
        log.textbox = mock_textbox_inst

        log.append_entry("VOICE", "Launch Chrome", "SUCCESS")
        mock_textbox_inst.insert.assert_called()
        inserted_str = mock_textbox_inst.insert.call_args[0][1]
        self.assertIn("[VOICE ", inserted_str)
        self.assertIn("Launch Chrome", inserted_str)
        self.assertIn("[SUCCESS]", inserted_str)

    def test_value_slider_callback(self):
        callback = MagicMock()
        slider = ValueSlider.__new__(ValueSlider)
        slider.unit = "x"
        slider.on_change = callback
        slider.val_label = MagicMock()

        slider._handle_change(1.85)
        slider.val_label.configure.assert_called_with(text="1.85 x")
        callback.assert_called_once_with(1.85)


if __name__ == "__main__":
    unittest.main()
