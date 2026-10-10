import queue
import unittest
from unittest.mock import MagicMock, patch

import main


class TestCommandExecution(unittest.TestCase):
    def setUp(self):
        # Create a mock app instance with queues and state
        self.app = main.AirControlApp.__new__(main.AirControlApp)
        self.app.paused = True
        self.app.running = True
        self.app.status_queue = queue.Queue()
        self.app.command_queue = queue.Queue()
        self.app.control_queue = queue.Queue()
        self.app._publish_control = MagicMock()

    @patch("pyautogui.click")
    def test_click_command_when_paused(self, mock_click):
        self.app.paused = True
        self.app._execute_voice_command("click")
        mock_click.assert_called_once()
        status = self.app.status_queue.get_nowait()
        self.assertEqual(status, "Action: Click")

    @patch("pyautogui.click")
    def test_left_click_normalized_punctuation(self, mock_click):
        self.app.paused = False
        self.app._execute_voice_command("Left Click.")
        mock_click.assert_called_once()
        status = self.app.status_queue.get_nowait()
        self.assertEqual(status, "Action: Click")

    @patch("pyautogui.doubleClick")
    def test_double_click_hyphenated(self, mock_double_click):
        self.app.paused = True
        self.app._execute_voice_command("Double-Click!")
        mock_double_click.assert_called_once()
        status = self.app.status_queue.get_nowait()
        self.assertEqual(status, "Action: Double Click")

    @patch("pyautogui.rightClick")
    def test_right_click(self, mock_right_click):
        self.app.paused = True
        self.app._execute_voice_command("right click")
        mock_right_click.assert_called_once()
        status = self.app.status_queue.get_nowait()
        self.assertEqual(status, "Action: Right Click")

    @patch("pyautogui.scroll")
    def test_scroll_up_and_down(self, mock_scroll):
        self.app.paused = True
        self.app._execute_voice_command("scroll up")
        mock_scroll.assert_called_with(200)

        self.app._execute_voice_command("scroll down")
        mock_scroll.assert_called_with(-200)

    @patch("pyautogui.hotkey")
    def test_zoom_in_and_out(self, mock_hotkey):
        self.app.paused = True
        self.app._execute_voice_command("Zoom In.")
        mock_hotkey.assert_called_with("ctrl", "+", interval=0.05)

        self.app._execute_voice_command("Zoom Out.")
        mock_hotkey.assert_called_with("ctrl", "-", interval=0.05)

    @patch("pyautogui.press")
    def test_volume_controls_and_mute(self, mock_press):
        self.app.paused = True
        self.app._execute_voice_command("volume up")
        mock_press.assert_called_with("volumeup")

        self.app._execute_voice_command("volume down")
        mock_press.assert_called_with("volumedown")

        self.app._execute_voice_command("mute")
        mock_press.assert_called_with("volumemute")

    @patch("pyautogui.move")
    def test_move_cursor_by_voice(self, mock_move):
        self.app.paused = True
        self.app._execute_voice_command("move cursor left")
        mock_move.assert_called_with(-100, 0)

        self.app._execute_voice_command("move cursor right")
        mock_move.assert_called_with(100, 0)

        self.app._execute_voice_command("move cursor up")
        mock_move.assert_called_with(0, -100)

        self.app._execute_voice_command("move cursor down")
        mock_move.assert_called_with(0, 100)

    def test_pause_and_resume_control(self):
        self.app.paused = False
        self.app._execute_voice_command("pause control")
        self.assertTrue(self.app.paused)
        statuses = []
        while not self.app.status_queue.empty():
            statuses.append(self.app.status_queue.get_nowait())
        self.assertIn("CONTROL:PAUSED", statuses)
        self.assertIn("Mouse control paused", statuses)

        self.app._execute_voice_command("resume control")
        self.assertFalse(self.app.paused)
        statuses = []
        while not self.app.status_queue.empty():
            statuses.append(self.app.status_queue.get_nowait())
        self.assertIn("CONTROL:RESUMED", statuses)
        self.assertIn("Mouse control active", statuses)

    @patch("pyautogui.click")
    @patch("pyautogui.press")
    @patch("pyautogui.scroll")
    @patch("pyautogui.hotkey")
    @patch("pyautogui.move")
    def test_unknown_and_malicious_commands_rejected(
        self, mock_move, mock_hotkey, mock_scroll, mock_press, mock_click
    ):
        dangerous_commands = [
            "delete all files",
            "format c:",
            "powershell rm -rf",
            "eval 1+1",
            "unknown gesture",
            "open terminal",
        ]
        for cmd in dangerous_commands:
            self.app._execute_voice_command(cmd)
            status = self.app.status_queue.get_nowait()
            self.assertTrue(status.startswith("Unknown command:"))

        mock_click.assert_not_called()
        mock_press.assert_not_called()
        mock_scroll.assert_not_called()
        mock_hotkey.assert_not_called()
        mock_move.assert_not_called()

    @patch("subprocess.Popen")
    @patch("core.command_router.CommandRouter.find_executable")
    def test_open_chrome_and_websites_in_chrome(self, mock_find_exe, mock_popen):
        mock_find_exe.return_value = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

        # 1. Open Chrome
        self.app._execute_voice_command("Open Chrome")
        mock_popen.assert_called_with([r"C:\Program Files\Google\Chrome\Application\chrome.exe"], shell=False)
        status = self.app.status_queue.get_nowait()
        self.assertEqual(status, "Action: Launch Google Chrome")

        # 2. Open LinkedIn in Chrome
        self.app.command_router.last_command_time = 0.0
        self.app._execute_voice_command("Open LinkedIn in Chrome")
        mock_popen.assert_called_with(
            [r"C:\Program Files\Google\Chrome\Application\chrome.exe", "https://www.linkedin.com"],
            shell=False,
        )
        status = self.app.status_queue.get_nowait()
        self.assertEqual(status, "Action: Open LinkedIn in Chrome")

        # 3. Open GitHub in Chrome
        self.app.command_router.last_command_time = 0.0
        self.app._execute_voice_command("Open GitHub in Chrome")
        mock_popen.assert_called_with(
            [r"C:\Program Files\Google\Chrome\Application\chrome.exe", "https://www.github.com"],
            shell=False,
        )
        status = self.app.status_queue.get_nowait()
        self.assertEqual(status, "Action: Open GitHub in Chrome")

        # 4. Open YouTube in Chrome
        self.app.command_router.last_command_time = 0.0
        self.app._execute_voice_command("Open YouTube in Chrome")
        mock_popen.assert_called_with(
            [r"C:\Program Files\Google\Chrome\Application\chrome.exe", "https://www.youtube.com"],
            shell=False,
        )
        status = self.app.status_queue.get_nowait()
        self.assertEqual(status, "Action: Open YouTube in Chrome")

    @patch("subprocess.Popen")
    @patch("core.command_router.CommandRouter.find_executable")
    def test_open_notepad_and_calculator(self, mock_find_exe, mock_popen):
        mock_find_exe.side_effect = [r"C:\Windows\System32\notepad.exe", r"C:\Windows\System32\calc.exe"]

        self.app._execute_voice_command("Launch Notepad")
        mock_popen.assert_called_with([r"C:\Windows\System32\notepad.exe"], shell=False)
        status = self.app.status_queue.get_nowait()
        self.assertEqual(status, "Action: Launch Notepad")

        self.app.command_router.last_command_time = 0.0
        self.app._execute_voice_command("Launch Calculator")
        mock_popen.assert_called_with([r"C:\Windows\System32\calc.exe"], shell=False)
        status = self.app.status_queue.get_nowait()
        self.assertEqual(status, "Action: Launch Calculator")


if __name__ == "__main__":
    unittest.main()

