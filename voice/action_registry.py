"""Schemas for the computer actions the assistant is allowed to execute."""

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Tuple
from pathlib import Path
from urllib.parse import urlparse

from voice.command_parser import ActionRequest


@dataclass(frozen=True)
class Capability:
    domain: str
    intent: str
    params: Mapping[str, type]
    required_params: frozenset
    description: str
    requires_confirmation: bool = False


_CAPABILITY_ROWS = (
    ("BROWSER", "SEARCH_GOOGLE", {"query": str}, "Search Google"),
    ("BROWSER", "SEARCH_YOUTUBE", {"query": str}, "Search YouTube"),
    ("BROWSER", "OPEN_DESTINATION", {"site_key": str, "browser": str}, "Open a known website", False, {"browser"}),
    ("BROWSER", "OPEN_URL", {"url": str}, "Open a web URL"),
    ("BROWSER", "NEW_TAB", {}, "Open a browser tab"),
    ("BROWSER", "CLOSE_TAB", {}, "Close the current browser tab", True),
    ("BROWSER", "NEXT_TAB", {}, "Switch to the next browser tab"),
    ("BROWSER", "PREV_TAB", {}, "Switch to the previous browser tab"),
    ("BROWSER", "GO_BACK", {}, "Navigate back in the browser"),
    ("BROWSER", "GO_FORWARD", {}, "Navigate forward in the browser"),
    ("BROWSER", "REFRESH_PAGE", {}, "Refresh the current browser page"),
    ("FILE_SYSTEM", "OPEN_FOLDER", {"folder_key": str}, "Open a known folder"),
    ("FILE_SYSTEM", "OPEN_LATEST_SCREENSHOT", {}, "Open the latest screenshot"),
    ("FILE_SYSTEM", "FIND_LATEST_SCREENSHOT", {}, "Find the latest screenshot"),
    ("FILE_SYSTEM", "OPEN_FILE", {"filename": str}, "Open a uniquely matched file"),
    ("FILE_SYSTEM", "FIND_FILE", {"query": str, "folder_key": str}, "Search bounded user folders for files", False, {"folder_key"}),
    ("FILE_SYSTEM", "OPEN_RECYCLE_BIN", {}, "Open the Windows Recycle Bin"),
    ("WINDOW", "MINIMIZE", {}, "Minimize the current window"),
    ("WINDOW", "MAXIMIZE", {}, "Maximize the current window"),
    ("WINDOW", "SWITCH_APP", {}, "Switch to another application"),
    ("WINDOW", "SHOW_DESKTOP", {}, "Show the desktop"),
    ("SYSTEM", "COPY", {}, "Copy the current selection"),
    ("SYSTEM", "PASTE", {}, "Paste from the clipboard"),
    ("SYSTEM", "SELECT_ALL", {}, "Select all"),
    ("SYSTEM", "UNDO", {}, "Undo the last edit"),
    ("SYSTEM", "PRESS_ENTER", {}, "Press Enter"),
    ("SYSTEM", "PRESS_ESCAPE", {}, "Press Escape"),
    ("SYSTEM", "SCREENSHOT", {}, "Take a screenshot"),
    ("SYSTEM", "LOCK_PC", {}, "Lock the workstation", True),
    ("SYSTEM", "SCROLL_UP", {}, "Scroll up"),
    ("SYSTEM", "SCROLL_DOWN", {}, "Scroll down"),
    ("SYSTEM", "ZOOM_IN", {}, "Zoom in"),
    ("SYSTEM", "ZOOM_OUT", {}, "Zoom out"),
    ("SYSTEM", "MUTE", {}, "Toggle mute"),
    ("SYSTEM", "VOLUME_UP", {}, "Raise system volume"),
    ("SYSTEM", "VOLUME_DOWN", {}, "Lower system volume"),
    ("SYSTEM", "MOVE_CURSOR", {"dx": int, "dy": int, "name": str}, "Move the cursor"),
    ("SYSTEM", "TYPE_TEXT", {"text": str}, "Type user-provided text"),
    ("SYSTEM", "OPEN_ACCESSIBILITY_SETTINGS", {}, "Open Windows accessibility display settings"),
    ("SYSTEM", "EXPLAIN_STATUS", {}, "Explain the current AirControl status"),
    ("GESTURE", "CLICK", {}, "Click at the current cursor position"),
    ("GESTURE", "DOUBLE_CLICK", {}, "Double-click at the current cursor position"),
    ("GESTURE", "RIGHT_CLICK", {}, "Right-click at the current cursor position"),
    ("GESTURE", "PAUSE_CONTROL", {}, "Pause hand-controlled mouse movement"),
    ("GESTURE", "RESUME_CONTROL", {}, "Resume hand-controlled mouse movement"),
    ("GESTURE", "CANCEL_TASK", {}, "Cancel the current assistant task"),
    ("WINDOW", "CLOSE_ACTIVE_WINDOW", {}, "Close the currently active window"),
    ("APPLICATION", "LAUNCH_APP", {"app_name": str}, "Launch an installed application"),
    ("APPLICATION", "CLOSE_APP", {"app_name": str}, "Close an open application"),
)

def _build_capabilities() -> Dict[Tuple[str, str], Capability]:
    capabilities = {}
    for row in _CAPABILITY_ROWS:
        domain, intent, params, description = row[:4]
        requires_confirmation = row[4] if len(row) > 4 else False
        optional_params = frozenset(row[5]) if len(row) > 5 else frozenset()
        capabilities[(domain, intent)] = Capability(
            domain=domain,
            intent=intent,
            params=params,
            required_params=frozenset(params) - optional_params,
            description=description,
            requires_confirmation=requires_confirmation,
        )
    return capabilities


CAPABILITIES = _build_capabilities()


class PlanValidationError(ValueError):
    """Raised when a plan asks for an unsupported or malformed capability."""


def validate_request(request: ActionRequest) -> Capability:
    key = (request.domain, request.intent)
    capability = CAPABILITIES.get(key)
    if capability is None:
        raise PlanValidationError(
            f"Unsupported action: {request.domain}.{request.intent}"
        )

    provided = request.params
    missing = capability.required_params - set(provided)
    if missing:
        raise PlanValidationError(
            f"Missing parameters for {request.intent}: {', '.join(sorted(missing))}"
        )
    unknown = set(provided) - set(capability.params)
    if unknown:
        raise PlanValidationError(
            f"Unexpected parameters for {request.intent}: {', '.join(sorted(unknown))}"
        )

    for name, expected_type in capability.params.items():
        if name not in provided:
            continue
        value = provided[name]
        if expected_type is int:
            valid_type = isinstance(value, int) and not isinstance(value, bool)
        else:
            valid_type = isinstance(value, expected_type)
        if not valid_type:
            raise PlanValidationError(
                f"Parameter '{name}' for {request.intent} must be {expected_type.__name__}"
            )
        if isinstance(value, str) and not value.strip():
            raise PlanValidationError(f"Parameter '{name}' cannot be empty")

    if request.intent == "OPEN_URL":
        url = request.params["url"].strip()
        parsed = urlparse(url)
        if (
            parsed.scheme not in ("http", "https")
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise PlanValidationError("Only valid HTTP or HTTPS URLs can be opened")

    if request.intent == "OPEN_FILE":
        allowed_extensions = {".pdf", ".txt", ".doc", ".docx", ".xls", ".xlsx", ".png", ".jpg", ".jpeg"}
        if Path(request.params["filename"]).suffix.casefold() not in allowed_extensions:
            raise PlanValidationError("Only document and image file types may be opened by voice")

    if request.intent == "LAUNCH_APP":
        app_name = request.params["app_name"].strip().lower()
        blocked_apps = {
            "cmd", "cmd.exe", "command prompt", "powershell",
            "powershell.exe", "windows terminal", "terminal", "bash",
            "python", "python.exe", "wscript", "cscript",
        }
        if app_name in blocked_apps:
            raise PlanValidationError(
                "Command interpreters and script hosts cannot be launched by voice"
            )

    if request.intent == "TYPE_TEXT":
        text = request.params["text"]
        if len(text) > 500:
            raise PlanValidationError("Text input is limited to 500 characters")

    return capability


def validate_plan(requests: Iterable[ActionRequest]) -> List[Capability]:
    return [validate_request(request) for request in requests]


def capability_descriptions() -> List[Dict[str, str]]:
    """Return the public, non-executable action catalogue for an optional planner."""
    return [
        {
            "domain": capability.domain,
            "intent": capability.intent,
            "params": ", ".join(
                f"{name}: {kind.__name__}" for name, kind in capability.params.items()
            ),
            "description": capability.description,
        }
        for capability in CAPABILITIES.values()
    ]


def requests_from_plan(payload: Any) -> List[ActionRequest]:
    """Convert strictly shaped planner JSON into ActionRequests for validation."""
    if not isinstance(payload, dict) or not isinstance(payload.get("steps"), list):
        raise PlanValidationError("Planner response must contain a steps array")
    steps = payload["steps"]
    if not steps or len(steps) > 8:
        raise PlanValidationError("A plan must contain between 1 and 8 steps")

    requests: List[ActionRequest] = []
    for index, step in enumerate(steps, 1):
        if not isinstance(step, dict):
            raise PlanValidationError(f"Plan step {index} must be an object")
        if set(step) - {"domain", "intent", "params"}:
            raise PlanValidationError(f"Plan step {index} contains unsupported fields")
        domain, intent, params = step.get("domain"), step.get("intent"), step.get("params", {})
        if not isinstance(domain, str) or not isinstance(intent, str) or not isinstance(params, dict):
            raise PlanValidationError(f"Plan step {index} has an invalid structure")
        request = ActionRequest(
            domain=domain.upper(),
            intent=intent.upper(),
            params=params,
            raw_segment=f"AI plan step {index}",
        )
        validate_request(request)
        requests.append(request)
    return requests
