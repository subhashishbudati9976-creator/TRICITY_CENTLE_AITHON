"""
AirControl — Comprehensive Tests for Universal Command Subsystems
Tests application discovery, browser search, file navigation, window management,
system shortcuts, multi-step compound commands, and safety reject behaviour.
"""

import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock
from typing import Optional

from voice.command_parser import CommandParser, ActionRequest
from actions.application_launcher import ApplicationLauncher, SYSTEM_APPLICATIONS, COMMON_ALIASES
from actions.browser_actions import BrowserActions, KNOWN_DESTINATIONS
from actions.file_actions import FileActions, KNOWN_FOLDERS
from actions.window_actions import WindowActions
from actions.system_actions import SystemActions
from core.command_router import CommandRouter


# ============================================================
# 1. Application Discovery & Resolution
# ============================================================
class TestApplicationDiscovery(unittest.TestCase):
    """Tests ApplicationLauncher.resolve_application and system app registry."""

    def setUp(self):
        self.launcher = ApplicationLauncher(launcher_fn=MagicMock())
        # Pre-populate cache with known entries to avoid filesystem scan
        self.launcher._cached_apps = {
            "settings": "ms-settings:",
            "file explorer": "explorer.exe",
            "task manager": "taskmgr.exe",
            "calculator": "calc.exe",
            "notepad": "notepad.exe",
            "visual studio code": r"C:\Users\test\AppData\Local\Programs\Microsoft VS Code\Code.exe",
            "word": r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE",
            "excel": r"C:\Program Files\Microsoft Office\root\Office16\EXCEL.EXE",
            "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            "spotify": r"C:\Users\test\AppData\Roaming\Spotify\Spotify.exe",
        }
        self.launcher._last_scan_time = 1e15  # prevent TTL refresh

    def test_exact_match_system_apps(self):
        name, target, _ = self.launcher.resolve_application("calculator")
        self.assertEqual(target, "calc.exe")

        name, target, _ = self.launcher.resolve_application("notepad")
        self.assertEqual(target, "notepad.exe")

        name, target, _ = self.launcher.resolve_application("settings")
        self.assertEqual(target, "ms-settings:")

        name, target, _ = self.launcher.resolve_application("file explorer")
        self.assertEqual(target, "explorer.exe")

    def test_alias_resolution_vs_code(self):
        """COMMON_ALIASES maps 'vs code' -> 'visual studio code'."""
        name, target, _ = self.launcher.resolve_application("vs code")
        self.assertIn("Code.exe", target)

    def test_alias_resolution_ms_word(self):
        """COMMON_ALIASES maps 'ms word' -> 'word'."""
        name, target, _ = self.launcher.resolve_application("ms word")
        self.assertIn("WINWORD.EXE", target)

    def test_unknown_app_returns_none(self):
        name, target, candidates = self.launcher.resolve_application("nonexistent app xyz")
        self.assertIsNone(target)

    def test_empty_query_returns_none(self):
        name, target, _ = self.launcher.resolve_application("")
        self.assertIsNone(target)

    def test_system_applications_registry_completeness(self):
        """Verify SYSTEM_APPLICATIONS contains essential built-in tools."""
        required = ["settings", "file explorer", "task manager", "calculator", "notepad"]
        for key in required:
            self.assertIn(key, SYSTEM_APPLICATIONS, f"Missing system app: {key}")

    def test_common_aliases_mapping(self):
        """COMMON_ALIASES covers VS Code, Office, and browser aliases."""
        self.assertEqual(COMMON_ALIASES["vs code"], "visual studio code")
        self.assertEqual(COMMON_ALIASES["vscode"], "visual studio code")
        self.assertEqual(COMMON_ALIASES["ms word"], "word")
        self.assertEqual(COMMON_ALIASES["ms excel"], "excel")
        self.assertEqual(COMMON_ALIASES["google chrome"], "chrome")


# ============================================================
# 2. Browser Search URL Generation
# ============================================================
class TestBrowserSearchURLs(unittest.TestCase):
    """Tests BrowserActions search URL construction and destination routing."""

    def setUp(self):
        self.mock_runner = MagicMock()
        self.browser = BrowserActions(
            process_runner=self.mock_runner,
            chrome_path_resolver=lambda: r"C:\chrome.exe",
        )

    def test_google_search_url_encoding(self):
        success, msg, label = self.browser.search_google("Python tutorials")
        self.assertTrue(success)
        self.assertIn("Python tutorials", msg)
        # Verify URL was passed with proper encoding
        call_args = self.mock_runner.call_args[0][0]
        self.assertIn("google.com/search?q=Python+tutorials", call_args[1])

    def test_youtube_search_url_encoding(self):
        success, msg, label = self.browser.search_youtube("mediapipe hand tracking")
        self.assertTrue(success)
        self.assertIn("mediapipe hand tracking", msg)
        call_args = self.mock_runner.call_args[0][0]
        self.assertIn("youtube.com/results?search_query=mediapipe+hand+tracking", call_args[1])

    def test_empty_google_search_rejected(self):
        success, msg, _ = self.browser.search_google("")
        self.assertFalse(success)

    def test_empty_youtube_search_rejected(self):
        success, msg, _ = self.browser.search_youtube("")
        self.assertFalse(success)

    def test_known_destinations_linkedin(self):
        success, msg, _ = self.browser.open_destination("linkedin", browser="chrome")
        self.assertTrue(success)
        call_args = self.mock_runner.call_args[0][0]
        self.assertIn("linkedin.com", call_args[1])

    def test_known_destinations_github(self):
        success, msg, _ = self.browser.open_destination("github")
        self.assertTrue(success)

    def test_unknown_destination_rejected(self):
        success, msg, _ = self.browser.open_destination("fakeSite123")
        self.assertFalse(success)
        self.assertIn("Unknown web destination", msg)

    def test_known_destinations_registry(self):
        """KNOWN_DESTINATIONS includes essential web services."""
        required = ["linkedin", "github", "youtube", "gmail", "google"]
        for key in required:
            self.assertIn(key, KNOWN_DESTINATIONS, f"Missing destination: {key}")


# ============================================================
# 3. Known Folders Navigation
# ============================================================
class TestKnownFolders(unittest.TestCase):
    """Tests FileActions.open_known_folder resolution."""

    def setUp(self):
        self.mock_opener = MagicMock()
        self.file_actions = FileActions(opener_fn=self.mock_opener)

    def test_downloads_folder_exists(self):
        path = KNOWN_FOLDERS.get("downloads")
        self.assertIsNotNone(path)
        # Path should resolve to user's Downloads
        self.assertIn("Downloads", str(path))

    def test_documents_folder_exists(self):
        path = KNOWN_FOLDERS.get("documents")
        self.assertIsNotNone(path)

    def test_desktop_folder_exists(self):
        path = KNOWN_FOLDERS.get("desktop")
        self.assertIsNotNone(path)

    def test_screenshots_folder_path(self):
        path = KNOWN_FOLDERS.get("screenshots")
        self.assertIsNotNone(path)
        self.assertIn("Screenshots", str(path))

    def test_project_folder_registered(self):
        path = KNOWN_FOLDERS.get("project")
        self.assertIsNotNone(path)

    @patch("actions.file_actions.KNOWN_FOLDERS", {"downloads": Path(os.path.expanduser("~/Downloads"))})
    def test_open_downloads_calls_opener(self):
        downloads_path = Path(os.path.expanduser("~/Downloads"))
        if downloads_path.exists():
            success, msg, _ = self.file_actions.open_known_folder("downloads")
            self.assertTrue(success)
            self.mock_opener.assert_called_once_with(str(downloads_path))

    def test_open_nonexistent_folder_fails(self):
        success, msg, _ = self.file_actions.open_known_folder("nonexistent_xyz_folder")
        self.assertFalse(success)


# ============================================================
# 4. Window Management
# ============================================================
class TestWindowManagement(unittest.TestCase):
    """Tests WindowActions hotkey actions."""

    @patch("pyautogui.hotkey")
    def test_minimize_window(self, mock_hotkey):
        wa = WindowActions()
        success, msg, label = wa.minimize_window()
        self.assertTrue(success)
        mock_hotkey.assert_called_once_with("win", "down", interval=0.05)
        self.assertEqual(label, "Minimize Window")

    @patch("pyautogui.hotkey")
    def test_maximize_window(self, mock_hotkey):
        wa = WindowActions()
        success, msg, label = wa.maximize_window()
        self.assertTrue(success)
        mock_hotkey.assert_called_once_with("win", "up", interval=0.05)

    @patch("pyautogui.hotkey")
    def test_switch_application(self, mock_hotkey):
        wa = WindowActions()
        success, msg, label = wa.switch_application()
        self.assertTrue(success)
        mock_hotkey.assert_called_once_with("alt", "tab", interval=0.05)

    @patch("pyautogui.hotkey")
    def test_show_desktop(self, mock_hotkey):
        wa = WindowActions()
        success, msg, label = wa.show_desktop()
        self.assertTrue(success)
        mock_hotkey.assert_called_once_with("win", "d", interval=0.05)


# ============================================================
# 5. System Shortcuts
# ============================================================
class TestSystemShortcuts(unittest.TestCase):
    """Tests SystemActions keyboard shortcuts."""

    def setUp(self):
        self.sa = SystemActions()

    @patch("pyautogui.hotkey")
    def test_copy(self, mock_hotkey):
        success, msg, label = self.sa.copy()
        self.assertTrue(success)
        mock_hotkey.assert_called_once_with("ctrl", "c", interval=0.05)

    @patch("pyautogui.hotkey")
    def test_paste(self, mock_hotkey):
        success, msg, label = self.sa.paste()
        self.assertTrue(success)
        mock_hotkey.assert_called_once_with("ctrl", "v", interval=0.05)

    @patch("pyautogui.hotkey")
    def test_select_all(self, mock_hotkey):
        success, msg, label = self.sa.select_all()
        self.assertTrue(success)
        mock_hotkey.assert_called_once_with("ctrl", "a", interval=0.05)

    @patch("pyautogui.hotkey")
    def test_undo(self, mock_hotkey):
        success, msg, label = self.sa.undo()
        self.assertTrue(success)
        mock_hotkey.assert_called_once_with("ctrl", "z", interval=0.05)

    @patch("pyautogui.press")
    def test_volume_up(self, mock_press):
        success, msg, label = self.sa.volume_up()
        self.assertTrue(success)
        mock_press.assert_called_once_with("volumeup")

    @patch("pyautogui.press")
    def test_volume_down(self, mock_press):
        success, msg, label = self.sa.volume_down()
        self.assertTrue(success)
        mock_press.assert_called_once_with("volumedown")

    @patch("pyautogui.press")
    def test_mute(self, mock_press):
        success, msg, label = self.sa.mute()
        self.assertTrue(success)
        mock_press.assert_called_once_with("volumemute")

    @patch("pyautogui.scroll")
    def test_scroll_up(self, mock_scroll):
        success, msg, label = self.sa.scroll_up()
        self.assertTrue(success)
        mock_scroll.assert_called_once_with(200)

    @patch("pyautogui.scroll")
    def test_scroll_down(self, mock_scroll):
        success, msg, label = self.sa.scroll_down()
        self.assertTrue(success)
        mock_scroll.assert_called_once_with(-200)


# ============================================================
# 6. Multi-Step Compound Commands (Parser)
# ============================================================
class TestMultiStepCommands(unittest.TestCase):
    """Tests CommandParser multi-step splitting and domain classification."""

    def setUp(self):
        self.parser = CommandParser()

    def test_split_and_then(self):
        segments = self.parser.split_compound_commands("open notepad and then search google for python")
        self.assertEqual(len(segments), 2)

    def test_split_semicolon(self):
        segments = self.parser.split_compound_commands("open notepad; search google for python")
        self.assertEqual(len(segments), 2)

    def test_split_and_verb(self):
        segments = self.parser.split_compound_commands("open notepad and open calculator")
        self.assertEqual(len(segments), 2)

    def test_single_command_not_split(self):
        segments = self.parser.split_compound_commands("open notepad")
        self.assertEqual(len(segments), 1)

    def test_empty_input(self):
        segments = self.parser.split_compound_commands("")
        self.assertEqual(len(segments), 0)

    def test_parse_google_search_domain(self):
        requests = self.parser.parse("search google for machine learning")
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0].domain, "BROWSER")
        self.assertEqual(requests[0].intent, "SEARCH_GOOGLE")
        self.assertEqual(requests[0].params["query"], "machine learning")

    def test_parse_youtube_search_domain(self):
        requests = self.parser.parse("search youtube for mediapipe tutorials")
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0].domain, "BROWSER")
        self.assertEqual(requests[0].intent, "SEARCH_YOUTUBE")

    def test_parse_open_app_domain(self):
        requests = self.parser.parse("open spotify")
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0].domain, "APPLICATION")
        self.assertEqual(requests[0].intent, "LAUNCH_APP")
        self.assertEqual(requests[0].params["app_name"], "spotify")

    def test_parse_minimize_window(self):
        requests = self.parser.parse("minimize window")
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0].domain, "WINDOW")
        self.assertEqual(requests[0].intent, "MINIMIZE")

    def test_parse_copy_command(self):
        requests = self.parser.parse("copy")
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0].domain, "SYSTEM")
        self.assertEqual(requests[0].intent, "COPY")

    def test_parse_unknown_falls_through(self):
        requests = self.parser.parse("xyzzy nonsense gibberish")
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0].domain, "UNKNOWN")

    def test_compound_open_and_search(self):
        """Multi-step: 'Open VS Code and search Google for Python tutorials'."""
        requests = self.parser.parse("open visual studio code and search google for python tutorials")
        self.assertEqual(len(requests), 2)
        self.assertEqual(requests[0].domain, "APPLICATION")
        self.assertEqual(requests[0].intent, "LAUNCH_APP")
        self.assertEqual(requests[1].domain, "BROWSER")
        self.assertEqual(requests[1].intent, "SEARCH_GOOGLE")


# ============================================================
# 7. Safety & Reject Handling via Router
# ============================================================
class TestSafetyBlocks(unittest.TestCase):
    """Tests that dangerous commands are rejected and malicious inputs blocked."""

    def setUp(self):
        self.mock_runner = MagicMock()
        self.router = CommandRouter(process_runner=self.mock_runner)
        self.context = MagicMock()
        self.context.status_queue = MagicMock()
        self.context.paused = False

    def test_shutdown_rejected(self):
        success, msg, label = self.router.execute("shutdown now", app=self.context)
        self.assertFalse(success)
        self.assertTrue(msg.startswith("Unknown command:"))

    def test_powershell_rejected(self):
        success, msg, label = self.router.execute("powershell rm -rf /", app=self.context)
        self.assertFalse(success)
        self.assertTrue(msg.startswith("Unknown command:"))

    def test_curl_rejected(self):
        success, msg, label = self.router.execute("curl evil.com", app=self.context)
        self.assertFalse(success)
        self.assertTrue(msg.startswith("Unknown command:"))

    def test_eval_rejected(self):
        success, msg, label = self.router.execute("eval 1+1", app=self.context)
        self.assertFalse(success)
        self.assertTrue(msg.startswith("Unknown command:"))

    def test_cmd_rejected(self):
        success, msg, label = self.router.execute("launch cmd", app=self.context)
        self.assertFalse(success)
        self.assertTrue(msg.startswith("Unknown command:"))
        self.mock_runner.assert_not_called()

    def test_unknown_gibberish_rejected(self):
        success, msg, label = self.router.execute("flibbertigibbet xyzzy", app=self.context)
        self.assertFalse(success)
        self.assertIn("Unknown command:", msg)


# ============================================================
# 8. End-to-End Router Tests (New Subsystems)
# ============================================================
class TestRouterEndToEnd(unittest.TestCase):
    """End-to-end tests routing voice commands through CommandRouter.execute()."""

    def setUp(self):
        self.mock_runner = MagicMock()
        self.router = CommandRouter(process_runner=self.mock_runner)
        self.context = MagicMock()
        self.context.status_queue = MagicMock()
        self.context.paused = False

    @patch("actions.browser_actions.BrowserActions.search_google", return_value=(True, "Action: Search Google for 'test'", "Search Google: test"))
    def test_route_google_search(self, mock_search):
        success, msg, label = self.router.execute("search google for test", app=self.context)
        self.assertTrue(success)
        mock_search.assert_called_once()

    @patch("actions.window_actions.WindowActions.minimize_window", return_value=(True, "Action: Minimize Window", "Minimize Window"))
    def test_route_minimize(self, mock_min):
        success, msg, label = self.router.execute("minimize window", app=self.context)
        self.assertTrue(success)
        mock_min.assert_called_once()

    @patch("actions.system_actions.SystemActions.copy", return_value=(True, "Action: Copy", "Copy"))
    def test_route_copy(self, mock_copy):
        success, msg, label = self.router.execute("copy", app=self.context)
        self.assertTrue(success)
        mock_copy.assert_called_once()

    @patch("actions.system_actions.SystemActions.paste", return_value=(True, "Action: Paste", "Paste"))
    def test_route_paste(self, mock_paste):
        success, msg, label = self.router.execute("paste", app=self.context)
        self.assertTrue(success)
        mock_paste.assert_called_once()

    def test_route_debounce_duplicate(self):
        """Rapid duplicate commands are suppressed."""
        with patch("actions.system_actions.SystemActions.copy", return_value=(True, "Action: Copy", "Copy")):
            self.router.execute("copy", app=self.context)
            # Immediate duplicate should be blocked
            success, msg, label = self.router.execute("copy", app=self.context)
            self.assertFalse(success)
            self.assertIn("duplicate", msg.lower())


if __name__ == "__main__":
    unittest.main()
