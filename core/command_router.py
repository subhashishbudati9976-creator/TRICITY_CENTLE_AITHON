"""
AirControl — Universal Desktop Command Router
Coordinates command parsing, application discovery, browser automation,
filesystem navigation, window management, and system actions.
"""

import os
import subprocess
import time
from typing import Callable, List, Optional, Tuple

import pyautogui

from actions.application_launcher import ApplicationLauncher
from actions.browser_actions import BrowserActions, KNOWN_DESTINATIONS
from actions.file_actions import FileActions
from actions.system_actions import SystemActions
from actions.window_actions import WindowActions
from voice.command_parser import ActionRequest, CommandParser


def _safe_get(obj: any, attr_name: str, default: any = None) -> any:
    """Safely retrieves attribute without triggering Tkinter __getattr__ recursion on uninitialized instances."""
    if obj is None:
        return default
    obj_dict = getattr(obj, "__dict__", None)
    if isinstance(obj_dict, dict) and attr_name in obj_dict:
        return obj_dict[attr_name]
    try:
        return getattr(obj, attr_name, default)
    except Exception:
        return default


# For backward compatibility with existing tests
KNOWN_APPLICATIONS = {
    "chrome": {"name": "Google Chrome"},
    "notepad": {"name": "Notepad"},
    "calculator": {"name": "Calculator"},
}
KNOWN_WEBSITES = KNOWN_DESTINATIONS
normalize_command_text = CommandParser.normalize_text


class CommandRouter:
    """
    Universal Command Router that validates action requests and
    delegates to specialized modular action handlers.
    """

    def __init__(
        self,
        app_context=None,
        debounce_seconds: float = 0.6,
        process_runner: Optional[Callable] = None,
    ):
        self.app_context = app_context
        self.debounce_seconds = debounce_seconds
        self.process_runner = process_runner

        # Modular components
        self.parser = CommandParser()
        self.app_launcher = ApplicationLauncher(
            launcher_fn=(lambda target: self.process_runner([target], shell=False) if self.process_runner else None)
        )
        self.browser = BrowserActions(process_runner=self.process_runner)
        self.file_actions = FileActions(
            opener_fn=(lambda path: self.process_runner([path], shell=False) if self.process_runner else None)
        )
        self.window_actions = WindowActions()
        self.system_actions = SystemActions()

        self.last_command: Optional[str] = None
        self.last_command_time: float = 0.0

    def find_executable(self, app_key: str) -> Optional[str]:
        """Backward-compatibility helper: resolves application target."""
        name, target, _ = self.app_launcher.resolve_application(app_key)
        return target

    def is_duplicate(self, normalized_cmd: str, now: Optional[float] = None) -> bool:
        """Determines if a command is an unintended rapid duplicate trigger."""
        if now is None:
            now = time.monotonic()

        if normalized_cmd == self.last_command and (now - self.last_command_time < self.debounce_seconds):
            return True

        self.last_command = normalized_cmd
        self.last_command_time = now
        return False

    def parse(self, text: str) -> Tuple[str, Optional[dict]]:
        """Backward-compatible helper returning legacy (intent, params) for single segment."""
        requests = self.parser.parse(text)
        if not requests:
            return "EMPTY", None
        req = requests[0]
        return req.intent, req.params

    def _execute_single_request(self, req: ActionRequest, context) -> Tuple[bool, str, str]:
        """Dispatches an individual ActionRequest to the appropriate action domain."""
        sq = _safe_get(context, "status_queue")

        # -------------------------------------------------------------
        # 1. Safety Blocked Commands
        # -------------------------------------------------------------
        if req.domain == "REJECT":
            raw_cmd = req.params.get("raw", req.raw_segment)
            return False, f"Unknown command: {raw_cmd}", "Unknown"

        # -------------------------------------------------------------
        # 2. Browser Domain Actions
        # -------------------------------------------------------------
        if req.domain == "BROWSER":
            if req.intent == "SEARCH_GOOGLE":
                return self.browser.search_google(req.params["query"])
            elif req.intent == "SEARCH_YOUTUBE":
                return self.browser.search_youtube(req.params["query"])
            elif req.intent == "OPEN_DESTINATION":
                site_key = req.params["site_key"]
                browser_choice = req.params.get("browser", "chrome")
                return self.browser.open_destination(site_key, browser=browser_choice)
            elif req.intent == "NEW_TAB":
                return self.browser.new_tab()
            elif req.intent == "CLOSE_TAB":
                return self.browser.close_tab()
            elif req.intent == "NEXT_TAB":
                return self.browser.next_tab()
            elif req.intent == "PREV_TAB":
                return self.browser.previous_tab()
            elif req.intent == "GO_BACK":
                return self.browser.go_back()
            elif req.intent == "GO_FORWARD":
                return self.browser.go_forward()
            elif req.intent == "REFRESH_PAGE":
                return self.browser.refresh_page()

        # -------------------------------------------------------------
        # 3. File System Domain Actions
        # -------------------------------------------------------------
        if req.domain == "FILE_SYSTEM":
            if req.intent == "OPEN_FOLDER":
                return self.file_actions.open_known_folder(req.params["folder_key"])
            elif req.intent == "OPEN_LATEST_SCREENSHOT":
                return self.file_actions.open_latest_screenshot()
            elif req.intent == "OPEN_FILE":
                return self.file_actions.open_specific_file(req.params["filename"])

        # -------------------------------------------------------------
        # 4. Window Management Domain Actions
        # -------------------------------------------------------------
        if req.domain == "WINDOW":
            if req.intent == "MINIMIZE":
                return self.window_actions.minimize_window()
            elif req.intent == "MAXIMIZE":
                return self.window_actions.maximize_window()
            elif req.intent == "SWITCH_APP":
                return self.window_actions.switch_application()
            elif req.intent == "SHOW_DESKTOP":
                return self.window_actions.show_desktop()

        # -------------------------------------------------------------
        # 5. System & Keyboard Domain Actions
        # -------------------------------------------------------------
        if req.domain == "SYSTEM":
            if req.intent == "COPY":
                return self.system_actions.copy()
            elif req.intent == "PASTE":
                return self.system_actions.paste()
            elif req.intent == "SELECT_ALL":
                return self.system_actions.select_all()
            elif req.intent == "UNDO":
                return self.system_actions.undo()
            elif req.intent == "PRESS_ENTER":
                return self.system_actions.press_enter()
            elif req.intent == "PRESS_ESCAPE":
                return self.system_actions.press_escape()
            elif req.intent == "SCREENSHOT":
                return self.system_actions.take_screenshot()
            elif req.intent == "LOCK_PC":
                return self.system_actions.lock_workstation()
            elif req.intent == "SCROLL_UP":
                return self.system_actions.scroll_up()
            elif req.intent == "SCROLL_DOWN":
                return self.system_actions.scroll_down()
            elif req.intent == "ZOOM_IN":
                pyautogui.hotkey("ctrl", "+", interval=0.05)
                return True, "Action: Zoom In", "Zoom In"
            elif req.intent == "ZOOM_OUT":
                pyautogui.hotkey("ctrl", "-", interval=0.05)
                return True, "Action: Zoom Out", "Zoom Out"
            elif req.intent == "MUTE":
                return self.system_actions.mute()
            elif req.intent == "VOLUME_UP":
                return self.system_actions.volume_up()
            elif req.intent == "VOLUME_DOWN":
                return self.system_actions.volume_down()
            elif req.intent == "MOVE_CURSOR":
                pyautogui.move(req.params["dx"], req.params["dy"])
                name = req.params["name"]
                return True, f"Action: {name}", name

        # -------------------------------------------------------------
        # 6. Gesture & Tracking Controls
        # -------------------------------------------------------------
        if req.domain == "GESTURE":
            if req.intent == "CLICK":
                pyautogui.click()
                return True, "Action: Click", "Click"
            elif req.intent == "DOUBLE_CLICK":
                pyautogui.doubleClick()
                return True, "Action: Double Click", "Double Click"
            elif req.intent == "RIGHT_CLICK":
                pyautogui.rightClick()
                return True, "Action: Right Click", "Right Click"
            elif req.intent == "PAUSE_CONTROL":
                if context:
                    context.paused = True
                    if sq is not None:
                        sq.put("CONTROL:PAUSED")
                        sq.put("Mouse control paused")
                    pub = _safe_get(context, "_publish_control")
                    if callable(pub):
                        pub((None, None, False))
                    gp = _safe_get(context, "gesture_processor")
                    if gp is not None and hasattr(gp, "reset"):
                        gp.reset()
                return True, "Mouse control paused", "Pause Control"
            elif req.intent == "RESUME_CONTROL":
                if context:
                    context.paused = False
                    if sq is not None:
                        sq.put("CONTROL:RESUMED")
                        sq.put("Mouse control active")
                return True, "Mouse control active", "Resume Control"

        # -------------------------------------------------------------
        # 7. Application Launch Domain Actions
        # -------------------------------------------------------------
        if req.domain == "APPLICATION" and req.intent == "LAUNCH_APP":
            app_name = req.params["app_name"]
            # Handle Chrome naming explicitly for backward compatibility
            if app_name.lower() in ("chrome", "google chrome"):
                chrome_path = self.find_executable("chrome")
                if not chrome_path:
                    return False, "Error: Google Chrome executable not found on this system", "Launch Chrome"
                runner = self.process_runner or subprocess.Popen
                runner([chrome_path], shell=False)
                return True, "Action: Launch Google Chrome", "Launch Chrome"

            # Check target via find_executable first (for backwards compatibility & tests)
            target = self.find_executable(app_name)
            if not target:
                _, target, _ = self.app_launcher.resolve_application(app_name)

            if not target:
                return False, f"Unknown command: open {app_name}", "Unknown"

            disp_name = app_name.title()
            runner = self.process_runner or subprocess.Popen
            if target.endswith(".exe"):
                runner([target], shell=False)
            else:
                if self.process_runner:
                    self.process_runner([target], shell=False)
                else:
                    os.startfile(target)
            return True, f"Action: Launch {disp_name}", f"Launch {disp_name}"

        # -------------------------------------------------------------
        # 8. Unknown Commands
        # -------------------------------------------------------------
        raw_cmd = req.params.get("raw", req.raw_segment)
        return False, f"Unknown command: {raw_cmd}", "Unknown"

    def execute(self, text: str, app=None) -> Tuple[bool, str, str]:
        """
        Executes a voice command (or multi-step sequence) safely.
        Returns: (success: bool, status_message: str, action_label: str)
        """
        context = app or self.app_context
        sq = _safe_get(context, "status_queue")

        normalized = self.parser.normalize_text(text)
        if not normalized:
            return False, "Ignored: Empty command", "None"

        # Check debounce
        if self.is_duplicate(normalized):
            return False, f"Ignored duplicate command: {normalized}", "Duplicate"

        # Parse compound requests
        requests: List[ActionRequest] = self.parser.parse(text)
        if not requests:
            return False, f"Unknown command: {normalized}", "Unknown"

        overall_success = True
        messages: List[str] = []
        labels: List[str] = []

        for i, req in enumerate(requests):
            success, msg, label = self._execute_single_request(req, context)
            messages.append(msg)
            labels.append(label)

            if sq is not None:
                sq.put(msg)

            if not success:
                overall_success = False
                # Halt execution of subsequent multi-step commands on error
                if len(requests) > 1 and i < len(requests) - 1:
                    stop_msg = f"Multi-step halted: step {i+1} failed"
                    messages.append(stop_msg)
                    if sq is not None:
                        sq.put(stop_msg)
                break

            # Brief interval between sequential steps for desktop stability
            if len(requests) > 1 and i < len(requests) - 1:
                time.sleep(0.3)

        final_msg = " | ".join(messages)
        final_label = " + ".join(labels)
        return overall_success, final_msg, final_label
