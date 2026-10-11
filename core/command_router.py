"""
AirControl — Universal Desktop Command Router
Coordinates command parsing, application discovery, browser automation,
filesystem navigation, window management, and system actions.
"""

import os
import subprocess
import threading
import time
import logging
from typing import Callable, List, Optional, Tuple

import pyautogui

from actions.application_launcher import ApplicationLauncher
from actions.browser_actions import BrowserActions, KNOWN_DESTINATIONS
from actions.file_actions import FileActions
from actions.system_actions import SystemActions
from actions.window_actions import WindowActions
from voice.action_registry import (
    PlanValidationError,
    validate_plan,
)
from voice.command_parser import ActionRequest, CommandParser
from voice.gemini_interpreter import GeminiInterpreter, PlannerUnavailable
from voice.knowledge_base import local_answer


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


def _publish_assistant(context, message: str) -> None:
    """Publish task feedback on the UI-owned queue, if the context provides one."""
    values = getattr(context, "__dict__", None)
    if not isinstance(values, dict):
        return
    assistant_queue = values.get("assistant_queue")
    if assistant_queue is not None:
        assistant_queue.put(message)


def _task_cancel_event(context):
    values = getattr(context, "__dict__", None)
    if not isinstance(values, dict):
        return None
    event = values.get("task_cancel_event")
    return event if isinstance(event, threading.Event) else None


# For backward compatibility with existing tests
KNOWN_APPLICATIONS = {
    "chrome": {"name": "Google Chrome"},
    "notepad": {"name": "Notepad"},
    "calculator": {"name": "Calculator"},
}
KNOWN_WEBSITES = KNOWN_DESTINATIONS
normalize_command_text = CommandParser.normalize_text
logger = logging.getLogger(__name__)
_DEFAULT_AI_PLANNER = object()


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
        ai_planner=_DEFAULT_AI_PLANNER,
        confirmation_fn: Optional[Callable[[str], bool]] = None,
    ):
        self.app_context = app_context
        self.debounce_seconds = debounce_seconds
        self.process_runner = process_runner
        self.ai_planner = (
            GeminiInterpreter.from_environment()
            if ai_planner is _DEFAULT_AI_PLANNER
            else ai_planner
        )
        self.confirmation_fn = confirmation_fn

        # Modular components
        self.parser = CommandParser()
        self.app_launcher = ApplicationLauncher(
            launcher_fn=(lambda target: self.process_runner([target], shell=False) if self.process_runner else None)
        )
        self.browser = BrowserActions(process_runner=self.process_runner)
        self.file_actions = FileActions(
            opener_fn=(
                (lambda path: self.process_runner([path], shell=False))
                if self.process_runner else None
            )
        )
        self.window_actions = WindowActions()
        self.system_actions = SystemActions()

        self.last_command: Optional[str] = None
        self.last_command_time: float = 0.0
        self.conversation_history = []

    def _remember_turn(self, user_text: str, assistant_text: str) -> None:
        """Keep only a short in-memory context for conversational follow-ups."""
        self.conversation_history.extend(
            (
                {"role": "user", "content": user_text[:1000]},
                {"role": "assistant", "content": assistant_text[:1000]},
            )
        )
        self.conversation_history = self.conversation_history[-6:]

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
            elif req.intent == "OPEN_URL":
                return self.browser.open_url(req.params["url"])

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
            elif req.intent == "FIND_FILE":
                return self.file_actions.find_file(
                    req.params["query"],
                    req.params.get("folder_key", "documents"),
                    cancel_event=_task_cancel_event(context),
                )
            elif req.intent == "FIND_LATEST_SCREENSHOT":
                return self.file_actions.find_latest_screenshot()
            elif req.intent == "OPEN_RECYCLE_BIN":
                return self.file_actions.open_recycle_bin()

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
            elif req.intent == "CLOSE_ACTIVE_WINDOW":
                return self.window_actions.close_active_window()

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
            elif req.intent == "TYPE_TEXT":
                return self.system_actions.type_text(req.params["text"])
            elif req.intent == "OPEN_ACCESSIBILITY_SETTINGS":
                return self.system_actions.open_accessibility_settings()
            elif req.intent == "EXPLAIN_STATUS":
                return self.system_actions.explain_status(context)

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
            elif req.intent == "CANCEL_TASK":
                cancel_event = _task_cancel_event(context)
                if cancel_event is not None:
                    cancel_event.set()
                return True, "Cancellation requested.", "Cancel Task"

        # -------------------------------------------------------------
        # 7. Application Launch & Close Domain Actions
        # -------------------------------------------------------------
        if req.domain == "APPLICATION":
            if req.intent == "CLOSE_APP":
                app_name = req.params["app_name"]
                return self.app_launcher.close_application(app_name, confirmation_fn=self.confirmation_fn)
            elif req.intent == "LAUNCH_APP":
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

        if normalized in ("cancel task", "cancel current task", "stop current task", "cancel request"):
            cancel_event = _task_cancel_event(context)
            if cancel_event is not None:
                cancel_event.set()
            message = "Cancellation requested."
            _publish_assistant(context, f"FINAL:{message}")
            return True, message, "Cancel Task"

        # Check debounce
        if self.is_duplicate(normalized):
            return False, f"Ignored duplicate command: {normalized}", "Duplicate"

        # Parse compound requests
        requests: List[ActionRequest] = self.parser.parse(text)
        if not requests:
            message = f"Unknown command: {normalized}"
            if sq is not None:
                sq.put(message)
            return False, message, "Unknown"

        if any(request.domain == "REJECT" for request in requests):
            message = f"Unknown command: {text} (blocked by safety policy)"
            if sq is not None:
                sq.put(message)
            _publish_assistant(context, f"FINAL:{message}")
            return False, message, "Unknown"

        planner_note = "Using built-in deterministic intent parsing."
        planner_answer = ""
        if any(request.domain == "UNKNOWN" for request in requests):
            answer = local_answer(text)
            if answer:
                if sq is not None:
                    sq.put(f"Assistant: {answer}")
                _publish_assistant(context, f"REQUEST:{text}")
                _publish_assistant(context, f"FINAL:{answer}")
                self._remember_turn(text, answer)
                return True, answer, "Assistant Answer"

            voice_mode = str(_safe_get(context, "voice_mode", "online")).casefold()
            if self.ai_planner is None or voice_mode == "offline":
                if voice_mode == "offline":
                    message = (
                        f"Unknown command: {text}. AI interpretation is disabled in "
                        "Offline voice mode; use a built-in command or switch to Online mode."
                    )
                else:
                    message = (
                        f"Unknown command: {text}. Set AIRCONTROL_AI_API_KEY in the "
                        "project .env file to enable Gemini answers and flexible "
                        "interpretation of registered actions. AIRCONTROL_AI_MODEL "
                        "defaults to gemini-3.5-flash-lite."
                    )
                if sq is not None:
                    sq.put(message)
                _publish_assistant(context, f"FINAL:{message}")
                return False, message, "Unknown"

            _publish_assistant(context, "PLAN:Interpreting the request with the configured AI provider.")
            try:
                if isinstance(self.ai_planner, GeminiInterpreter):
                    action, answer, confident = self.ai_planner.interpret(
                        text, history=self.conversation_history
                    )
                    planner_answer = answer
                    if not confident:
                        message = answer or (
                            "I couldn't confidently understand that. Please rephrase it "
                            "or choose a supported AirControl action."
                        )
                        if sq is not None:
                            sq.put(message)
                        _publish_assistant(context, f"FINAL:{message}")
                        self._remember_turn(text, message)
                        return False, message, "Unsupported"
                    if action is None:
                        if sq is not None:
                            sq.put(f"Assistant: {planner_answer}")
                        _publish_assistant(context, f"REQUEST:{text}")
                        _publish_assistant(context, f"FINAL:{planner_answer}")
                        self._remember_turn(text, planner_answer)
                        return True, planner_answer, "Assistant Answer"
                    requests = [action]
                else:
                    requests = self.ai_planner.plan(text)
                if not requests:
                    message = "The configured AI provider did not return a supported action or answer."
                    _publish_assistant(context, f"FINAL:{message}")
                    return False, message, "Unsupported"
                planner_note = "Plan interpreted by the configured AI provider."
            except (PlannerUnavailable, PlanValidationError) as exc:
                message = f"AI interpretation unavailable: {exc}"
                if sq is not None:
                    sq.put(message)
                _publish_assistant(context, f"FINAL:{message}")
                return False, message, "AI Unavailable"

        try:
            capabilities = validate_plan(requests)
        except PlanValidationError as exc:
            message = (
                f"{planner_note} Unsupported or invalid request: {exc}. "
                "No actions were executed."
            )
            _publish_assistant(context, f"FINAL:{message}")
            return False, message, "Unsupported"

        _publish_assistant(context, f"REQUEST:{text}")
        plan_summary = " Then ".join(
            capability.description for capability in capabilities
        )
        if planner_answer:
            plan_summary = f"{planner_answer} Action plan: {plan_summary}"
        _publish_assistant(
            context, "PLAN:" + plan_summary
        )
        if planner_answer and sq is not None:
            sq.put(f"Assistant: {planner_answer}")

        overall_success = True
        messages: List[str] = []
        labels: List[str] = []

        for i, req in enumerate(requests):
            cancel_event = _task_cancel_event(context)
            if cancel_event is not None and cancel_event.is_set():
                overall_success = False
                messages.append("Task cancelled before the next action.")
                _publish_assistant(context, "FINAL:Task cancelled.")
                break

            capability = capabilities[i]
            _publish_assistant(
                context, f"STEP:{i + 1}/{len(requests)}:{capability.description}"
            )
            if hasattr(context, "__dict__") and isinstance(context.__dict__, dict):
                context.__dict__["current_action_description"] = capability.description

            if capability.requires_confirmation and (
                self.confirmation_fn is None
                or not self.confirmation_fn(f"Confirm this action: {capability.description}?")
            ):
                success, msg, label = False, "Action was not confirmed; task stopped.", capability.description
            else:
                try:
                    success, msg, label = self._execute_single_request(req, context)
                except Exception as exc:
                    logger.exception("Registered action %s.%s failed", req.domain, req.intent)
                    success, msg, label = False, f"Action failed: {exc}", capability.description
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

            # Keep multi-step actions responsive to the cancel control.
            if len(requests) > 1 and i < len(requests) - 1:
                if cancel_event is not None and cancel_event.wait(0.3):
                    overall_success = False
                    messages.append("Task cancelled before the next action.")
                    _publish_assistant(context, "FINAL:Task cancelled.")
                    break

        final_msg = " | ".join(messages)
        if planner_answer:
            final_msg = f"{planner_answer} {final_msg}"
        final_label = " + ".join(labels)
        cancel_event = _task_cancel_event(context)
        if overall_success and cancel_event is not None and cancel_event.is_set():
            overall_success = False
            final_msg = f"Current action finished before cancellation: {final_msg}"
        if overall_success:
            _publish_assistant(context, f"FINAL:Completed: {final_msg}")
        elif final_msg.startswith("Current action finished"):
            _publish_assistant(context, f"FINAL:{final_msg}")
        elif not any(message.startswith("Task cancelled") for message in messages):
            _publish_assistant(context, f"FINAL:Stopped: {final_msg}")
        self._remember_turn(text, final_msg)
        return overall_success, final_msg, final_label
