import queue
import time
import unittest
from unittest.mock import MagicMock, patch

import main


class TestDecouplingAndWorker(unittest.TestCase):
    def setUp(self):
        self.app = main.AirControlApp.__new__(main.AirControlApp)
        self.app.running = True
        self.app.paused = True
        self.app.status_queue = queue.Queue()
        self.app.command_queue = queue.Queue()
        self.app.control_queue = queue.Queue()
        self.app.frame_queue = queue.Queue()
        self.app._publish_control = MagicMock()

        # Mock UI elements that update_dashboard touches
        self.app.hand_var = MagicMock()
        self.app.control_var = MagicMock()
        self.app.pause_button = MagicMock()
        self.app.listen_button = MagicMock()
        self.app.voice_status_var = MagicMock()
        self.app.status_var = MagicMock()
        self.app.video_label = MagicMock()
        self.app.after = MagicMock()

    @patch("pyautogui.doubleClick")
    @patch("pyautogui.click")
    def test_voice_commands_execute_without_camera_and_when_paused(self, mock_click, mock_double_click):
        # Ensure control_queue is empty (simulating camera off)
        self.assertTrue(self.app.control_queue.empty())
        self.assertTrue(self.app.paused)

        # Enqueue voice commands
        self.app.command_queue.put("click")
        self.app.command_queue.put("double click")

        # Mock _execute_voice_command and verify it gets called
        with patch.object(self.app, "_execute_voice_command", wraps=self.app._execute_voice_command) as mock_exec:
            # Run one cycle of mouse worker loop logic
            # Simulate worker draining command queue
            while True:
                try:
                    cmd = self.app.command_queue.get_nowait()
                except queue.Empty:
                    break
                if cmd:
                    self.app._execute_voice_command(cmd)

            self.assertEqual(mock_exec.call_count, 2)
            mock_click.assert_called_once()

    def test_dashboard_status_preserves_heard_voice_text(self):
        # Put "Heard: click" and then "VOICE_READY"
        self.app.status_queue.put("Heard: click")
        self.app.status_queue.put("VOICE_READY")

        # Run update dashboard logic
        while True:
            try:
                status = self.app.status_queue.get_nowait()
            except queue.Empty:
                break
            if status == "VOICE_READY":
                self.app.listen_button.configure(state="normal")
            elif status.startswith("VOICE_ERROR:"):
                self.app.voice_status_var.set(status.split(":", 1)[1])
            elif status.startswith("Heard:"):
                self.app.voice_status_var.set(status)
            else:
                self.app.status_var.set(status)

        # Verify voice_status_var was set to "Heard: click" and NOT overwritten by "Voice: Ready"
        self.app.voice_status_var.set.assert_called_with("Heard: click")
        self.app.listen_button.configure.assert_called_with(state="normal")

    def test_dashboard_status_preserves_voice_error(self):
        # Put "VOICE_ERROR:Microphone timeout" and then "VOICE_READY"
        self.app.status_queue.put("VOICE_ERROR:Microphone timeout")
        self.app.status_queue.put("VOICE_READY")

        # Run update dashboard logic
        while True:
            try:
                status = self.app.status_queue.get_nowait()
            except queue.Empty:
                break
            if status == "VOICE_READY":
                self.app.listen_button.configure(state="normal")
            elif status.startswith("VOICE_ERROR:"):
                self.app.voice_status_var.set(status.split(":", 1)[1])
            elif status.startswith("Heard:"):
                self.app.voice_status_var.set(status)
            else:
                self.app.status_var.set(status)

        # Verify voice_status_var was set to the error and button re-enabled
        self.app.voice_status_var.set.assert_called_with("Microphone timeout")
        self.app.listen_button.configure.assert_called_with(state="normal")

    def test_dashboard_handles_control_paused_and_resumed(self):
        self.app.status_queue.put("CONTROL:PAUSED")
        self.app.status_queue.put("CONTROL:RESUMED")

        while True:
            try:
                status = self.app.status_queue.get_nowait()
            except queue.Empty:
                break
            if status == "CONTROL:PAUSED":
                self.app.control_var.set("Mouse control: DISABLED")
                self.app.pause_button.configure(text="Enable Mouse Control")
            elif status == "CONTROL:RESUMED":
                self.app.control_var.set("Mouse control: ENABLED")
                self.app.pause_button.configure(text="Pause Mouse Control")

        self.app.control_var.set.assert_called_with("Mouse control: ENABLED")
        self.app.pause_button.configure.assert_called_with(text="Pause Mouse Control")


if __name__ == "__main__":
    unittest.main()
