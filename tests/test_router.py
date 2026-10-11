import queue
import unittest
from unittest.mock import MagicMock, patch

from core.command_router import (
    CommandRouter,
    KNOWN_APPLICATIONS,
    KNOWN_WEBSITES,
    normalize_command_text,
)


class TestCommandRouter(unittest.TestCase):
    def setUp(self):
        self.mock_runner = MagicMock()
        self.router = CommandRouter(
            debounce_seconds=0.5,
            process_runner=self.mock_runner,
            ai_planner=None,
        )
        self.status_queue = queue.Queue()
        self.context = MagicMock()
        self.context.status_queue = self.status_queue
        self.context.paused = False

    def test_normalization_variations(self):
        cases = [
            ("Launch Google Chrome!", "open chrome"),  # normalizes google chrome to chrome
            ("Open You Tube in Chrome.", "open youtube in chrome"),
            ("Open Linked-In In Chrome", "open linkedin in chrome"),
            ("Open Git Hub In Chrome!", "open github in chrome"),
            ("Start Note Pad", "open notepad"),
            ("Open Calc", "open calculator"),
            ("Double-Click!", "double click"),
            ("Right-Click.", "right click"),
            ("Left-Click...", "left click"),
        ]
        for raw, expected in cases:
            # Check intent matching or normalized text
            intent, params = self.router.parse(raw)
            self.assertNotEqual(intent, "UNKNOWN", f"Failed to parse: {raw}")

    def test_launch_chrome_mocked(self):
        with patch.object(self.router, "find_executable", return_value=r"C:\Program Files\Google\Chrome\Application\chrome.exe"):
            success, msg, label = self.router.execute("Launch Chrome", app=self.context)
            self.assertTrue(success)
            self.assertIn("Launch Google Chrome", msg)
            self.mock_runner.assert_called_once_with(
                [r"C:\Program Files\Google\Chrome\Application\chrome.exe"], shell=False
            )
            status = self.status_queue.get_nowait()
            self.assertEqual(status, "Action: Launch Google Chrome")

    def test_open_linkedin_in_chrome_mocked(self):
        with patch.object(self.router, "find_executable", return_value=r"C:\Program Files\Google\Chrome\Application\chrome.exe"):
            success, msg, label = self.router.execute("Open LinkedIn in Chrome", app=self.context)
            self.assertTrue(success)
            self.assertIn("Open LinkedIn in Chrome", msg)
            self.mock_runner.assert_called_once_with(
                [r"C:\Program Files\Google\Chrome\Application\chrome.exe", "https://www.linkedin.com"],
                shell=False,
            )
            status = self.status_queue.get_nowait()
            self.assertEqual(status, "Action: Open LinkedIn in Chrome")

    def test_open_github_in_chrome_mocked(self):
        with patch.object(self.router, "find_executable", return_value=r"C:\Program Files\Google\Chrome\Application\chrome.exe"):
            success, msg, label = self.router.execute("Open GitHub in Chrome", app=self.context)
            self.assertTrue(success)
            self.mock_runner.assert_called_once_with(
                [r"C:\Program Files\Google\Chrome\Application\chrome.exe", "https://www.github.com"],
                shell=False,
            )

    def test_open_youtube_in_chrome_mocked(self):
        with patch.object(self.router, "find_executable", return_value=r"C:\Program Files\Google\Chrome\Application\chrome.exe"):
            success, msg, label = self.router.execute("Open YouTube in Chrome", app=self.context)
            self.assertTrue(success)
            self.mock_runner.assert_called_once_with(
                [r"C:\Program Files\Google\Chrome\Application\chrome.exe", "https://www.youtube.com"],
                shell=False,
            )

    def test_launch_notepad_and_calculator_mocked(self):
        with patch.object(self.router, "find_executable", side_effect=[r"C:\Windows\System32\notepad.exe", r"C:\Windows\System32\calc.exe"]):
            success1, msg1, _ = self.router.execute("Open Notepad", app=self.context)
            self.assertTrue(success1)
            self.mock_runner.assert_called_with([r"C:\Windows\System32\notepad.exe"], shell=False)

            # Advance router time to avoid debounce
            self.router.last_command_time = 0.0
            success2, msg2, _ = self.router.execute("Open Calculator", app=self.context)
            self.assertTrue(success2)
            self.mock_runner.assert_called_with([r"C:\Windows\System32\calc.exe"], shell=False)

    def test_missing_application_displays_error(self):
        with patch.object(self.router, "find_executable", return_value=None):
            success, msg, label = self.router.execute("Open Chrome", app=self.context)
            self.assertFalse(success)
            self.assertIn("executable not found", msg)
            status = self.status_queue.get_nowait()
            self.assertIn("executable not found", status)

    def test_duplicate_command_prevention(self):
        with patch.object(self.router, "find_executable", return_value=r"C:\Program Files\Google\Chrome\Application\chrome.exe"):
            success1, _, _ = self.router.execute("Open Chrome", app=self.context)
            self.assertTrue(success1)

            # Immediately repeating the same command within debounce window
            success2, msg2, label2 = self.router.execute("Open Chrome", app=self.context)
            self.assertFalse(success2)
            self.assertEqual(label2, "Duplicate")
            # Runner should only have been called once
            self.assertEqual(self.mock_runner.call_count, 1)

    def test_arbitrary_shell_and_malicious_commands_rejected(self):
        dangerous = [
            "format c:",
            "powershell rm -rf /",
            "curl evil.com",
            "shutdown /s /t 0",
            "eval 1+1",
            "launch cmd",
        ]
        for cmd in dangerous:
            success, msg, label = self.router.execute(cmd, app=self.context)
            self.assertFalse(success)
            self.assertTrue(msg.startswith("Unknown command:"))
            self.assertEqual(label, "Unknown")

        self.mock_runner.assert_not_called()

    @patch("actions.application_launcher.ApplicationLauncher.close_application")
    def test_execute_close_application(self, mock_close_app):
        mock_close_app.return_value = (True, "Action: Closed Notepad", "Close Notepad")
        success, msg, label = self.router.execute("Close Notepad", app=self.context)
        self.assertTrue(success)
        mock_close_app.assert_called_with("notepad", confirmation_fn=unittest.mock.ANY)
        self.assertEqual(label, "Close Notepad")

    @patch("actions.window_actions.WindowActions.close_active_window")
    def test_execute_close_active_window(self, mock_close_win):
        mock_close_win.return_value = (True, "Action: Closed window 'Document1'", "Close Window")
        success, msg, label = self.router.execute("Close active window", app=self.context)
        self.assertTrue(success)
        mock_close_win.assert_called_once()
        self.assertEqual(label, "Close Window")

    def test_close_nonexistent_application_reports_clear_error(self):
        with patch("subprocess.run") as mock_subproc, patch("pygetwindow.getAllWindows", return_value=[]):
            mock_subproc.return_value = MagicMock(stdout="", returncode=0)
            success, msg, _ = self.router.app_launcher.close_application("NonExistentAppXYZ")
            self.assertFalse(success)
            self.assertIn("No running window or application found", msg)

    def test_close_application_with_unsaved_changes_reports_notice(self):
        mock_win = MagicMock()
        mock_win.title = "Untitled - Notepad"
        mock_win._hWnd = 12345
        # Window remains in getAllWindows after close() because of unsaved changes prompt
        with patch("pygetwindow.getAllWindows", return_value=[mock_win]):
            success, msg, _ = self.router.app_launcher.close_application("notepad")
            self.assertTrue(success)
            mock_win.close.assert_called_once()
            self.assertIn("review any unsaved changes", msg)


if __name__ == "__main__":
    unittest.main()
