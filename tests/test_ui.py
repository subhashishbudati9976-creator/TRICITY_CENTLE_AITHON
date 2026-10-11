import unittest
from unittest.mock import MagicMock, patch

from ui.theme import (
    COLOR_CHARCOAL,
    COLOR_INDIGO,
    COLOR_IVORY,
    COLOR_SAGE,
    COLOR_STONE,
    COLOR_VERMILION,
    FONT_BODY,
    FONT_DISPLAY,
    FONT_MONO,
    FONT_SANS,
    FONT_SERIF,
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

    def test_typography_tokens(self):
        self.assertIn(FONT_DISPLAY, {"Neue Haas Grotesk", "Space Grotesk", "Segoe UI"})
        self.assertIn(FONT_BODY, {"Inter", "Segoe UI"})
        self.assertEqual(FONT_DISPLAY, FONT_SERIF)
        self.assertEqual(FONT_BODY, FONT_SANS)
        self.assertEqual(FONT_MONO, "Consolas")

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

    @patch("customtkinter.CTkFont")
    @patch("customtkinter.CTkToplevel")
    @patch("customtkinter.CTkFrame")
    @patch("customtkinter.CTkLabel")
    @patch("customtkinter.CTkButton")
    def test_fullscreen_webcam_open_exit_toggle(
        self, mock_btn, mock_lbl, mock_frame, mock_toplevel_cls, mock_font
    ):
        import main
        mock_top_inst = MagicMock()
        mock_toplevel_cls.return_value = mock_top_inst

        app = main.AirControlApp.__new__(main.AirControlApp)
        app.fullscreen_window = None
        app.fullscreen_label = None
        app.hand_var = MagicMock()
        app.control_var = MagicMock()
        app.focus_force = MagicMock()
        app.task_cancel_event = MagicMock()

        # Open fullscreen
        app._open_fullscreen_webcam()
        self.assertIsNotNone(app.fullscreen_window)
        mock_top_inst.attributes.assert_called_with("-fullscreen", True)
        mock_top_inst.bind.assert_any_call("<Escape>", unittest.mock.ANY)
        mock_top_inst.bind.assert_any_call("<q>", unittest.mock.ANY)

        # Calling toggle while open exits
        mock_top_inst.winfo_exists.return_value = True
        app._toggle_fullscreen_webcam()
        mock_top_inst.destroy.assert_called_once()
        self.assertIsNone(app.fullscreen_window)
        self.assertIsNone(app.fullscreen_label)

        # Repeated open and exit
        mock_top_inst.reset_mock()
        app._open_fullscreen_webcam()
        self.assertIsNotNone(app.fullscreen_window)
        app._exit_fullscreen_webcam()
        self.assertIsNone(app.fullscreen_window)


if __name__ == "__main__":
    unittest.main()
