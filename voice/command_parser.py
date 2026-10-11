"""
AirControl — Natural Voice Command Parser & Intent Extractor
Supports multi-step compound commands, entity extraction, and domain classification.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class ActionRequest:
    """Structured representation of an extracted voice command intent."""
    domain: str                     # APPLICATION, BROWSER, FILE_SYSTEM, WINDOW, SYSTEM, GESTURE, REJECT
    intent: str                     # specific action intent
    params: Dict[str, Any] = field(default_factory=dict)
    raw_segment: str = ""
    description: str = ""


class CommandParser:
    """Parses natural spoken phrases into validated, structured action requests."""

    def __init__(self):
        pass

    @staticmethod
    def normalize_text(text: Optional[str]) -> str:
        """Normalize command phrasing while retaining query text and URL characters."""
        if not text:
            return ""

        cleaned = text.lower().strip()
        cleaned = re.sub(r"[!?;,.]+$", "", cleaned)
        cleaned = re.sub(r"\b(linked|git|you)[- ](in|hub|tube)\b", r"\1 \2", cleaned)
        cleaned = re.sub(r"\b(double|right|left)[- ]?click\b", r"\1 click", cleaned)
        cleaned = re.sub(r"[^\w\s+#:/@?&=.%'\-]", " ", cleaned)
        tokens = cleaned.split()
        normalized = " ".join(tokens)

        replacements = [
            (r"\bgoogle chrome\b", "chrome"),
            (r"\byou tube\b", "youtube"),
            (r"\blinked in\b", "linkedin"),
            (r"\bgit hub\b", "github"),
            (r"\bnote pad\b", "notepad"),
            (r"\bvs code\b", "visual studio code"),
            (r"\bvscode\b", "visual studio code"),
            (r"\bcalc\b", "calculator"),
            (r"\bcalculate\b", "calculator"),
            (r"\bdoubleclick\b", "double click"),
            (r"\brightclick\b", "right click"),
            (r"\bleftclick\b", "left click"),
        ]
        for pattern, repl in replacements:
            normalized = re.sub(pattern, repl, normalized)

        return " ".join(normalized.split())

    def split_compound_commands(self, text: str) -> List[str]:
        """
        Splits compound natural instructions into sequential steps.
        E.g. 'Open VS Code and search Google for Python tutorials' -> ['Open VS Code', 'search Google for Python tutorials']
        """
        if not text:
            return []

        # Split on explicit connectors like ';', ' and then ', ' then '
        text = text.replace(";", " and then ")
        segments = re.split(r"\s+(?:and then|then)\s+", text, flags=re.IGNORECASE)

        final_segments: List[str] = []
        # Pattern to split '... and (open|close|search|launch|show|minimize|take)...'
        cmd_verbs = r"(?:open|close|quit|exit|launch|start|search|show|find|locate|look|type|write|minimize|maximize|take|switch|copy|paste|scroll|volume|lock)"
        and_verb_pattern = re.compile(rf"\s+and\s+(?={cmd_verbs}\b)", re.IGNORECASE)

        for seg in segments:
            parts = and_verb_pattern.split(seg)
            for p in parts:
                cleaned = p.strip()
                if cleaned:
                    final_segments.append(cleaned)

        return final_segments if final_segments else [text.strip()]

    def parse_single_segment(self, segment: str) -> ActionRequest:
        """Classifies a single normalized instruction into an ActionRequest."""
        cmd = self.normalize_text(segment)
        cmd = re.sub(r"^please\s+", "", cmd)
        if not cmd:
            return ActionRequest(domain="EMPTY", intent="EMPTY", raw_segment=segment)

        # -------------------------------------------------------------
        # 1. High-Impact Dangerous Commands (Safety Block)
        # -------------------------------------------------------------
        dangerous_matches = [
            r"^(?:shutdown|shut down|restart|reboot)\b",
            r"^(?:format c(?::|\\)?|delete all files|remove all files|rm\s+-rf)(?:\s|$)",
            r"^(?:open|launch|start)\s+(?:cmd(?:\.exe)?|command prompt|powershell|windows terminal|terminal|bash|python(?:\.exe)?)\b",
            r"^(?:run|execute)\s+(?:a\s+)?(?:shell|command|script|powershell|cmd)\b",
        ]
        for dm in dangerous_matches:
            if re.search(dm, cmd):
                return ActionRequest(
                    domain="REJECT",
                    intent="HIGH_IMPACT_BLOCKED",
                    params={"raw": segment},
                    raw_segment=segment,
                    description=f"Unknown command: {segment}",
                )

        # -------------------------------------------------------------
        # 2. Browser Search Queries
        # -------------------------------------------------------------
        # e.g. "search google for java arrays", "google java arrays"
        google_search = re.search(r"^(?:search google for|search on google for|google)\s+(.+)$", cmd)
        if google_search:
            query = google_search.group(1).strip()
            return ActionRequest(
                domain="BROWSER",
                intent="SEARCH_GOOGLE",
                params={"query": query},
                raw_segment=segment,
                description=f"Search Google: '{query}'",
            )

        # e.g. "search youtube for mediapipe tutorials"
        yt_search = re.search(r"^(?:search youtube for|search on youtube for)\s+(.+)$", cmd)
        if yt_search:
            query = yt_search.group(1).strip()
            return ActionRequest(
                domain="BROWSER",
                intent="SEARCH_YOUTUBE",
                params={"query": query},
                raw_segment=segment,
                description=f"Search YouTube: '{query}'",
            )

        site_search = re.search(
            r"^(?:search(?: for)?|look up)\s+(.+?)\s+(?:on|using)\s+(google|youtube)$",
            cmd,
        )
        if site_search:
            query, site = site_search.groups()
            intent = "SEARCH_YOUTUBE" if site == "youtube" else "SEARCH_GOOGLE"
            return ActionRequest(
                domain="BROWSER",
                intent=intent,
                params={"query": query.strip()},
                raw_segment=segment,
                description=f"Search {site.title()}: '{query.strip()}'",
            )

        general_search = re.search(
            r"^(?:search(?: the web)?(?: for)?|look up|google)\s+(.+)$", cmd
        )
        if general_search:
            query = general_search.group(1).strip()
            return ActionRequest(
                domain="BROWSER",
                intent="SEARCH_GOOGLE",
                params={"query": query},
                raw_segment=segment,
                description=f"Search Google: '{query}'",
            )

        url_match = re.match(r"^(?:open|go to|navigate to)\s+(https?://\S+)$", cmd)
        if url_match:
            return ActionRequest(
                domain="BROWSER",
                intent="OPEN_URL",
                params={"url": url_match.group(1)},
                raw_segment=segment,
                description=f"Open {url_match.group(1)}",
            )

        # -------------------------------------------------------------
        # 3. Browser Tab & Navigation Controls
        # -------------------------------------------------------------
        tab_nav_map = {
            "open a new tab": "NEW_TAB",
            "open new tab": "NEW_TAB",
            "new tab": "NEW_TAB",
            "close this tab": "CLOSE_TAB",
            "close tab": "CLOSE_TAB",
            "switch to the next tab": "NEXT_TAB",
            "switch to next tab": "NEXT_TAB",
            "next tab": "NEXT_TAB",
            "switch to the previous tab": "PREV_TAB",
            "switch to previous tab": "PREV_TAB",
            "previous tab": "PREV_TAB",
            "go back": "GO_BACK",
            "back": "GO_BACK",
            "go forward": "GO_FORWARD",
            "forward": "GO_FORWARD",
            "refresh this page": "REFRESH_PAGE",
            "refresh page": "REFRESH_PAGE",
            "refresh": "REFRESH_PAGE",
        }
        if cmd in tab_nav_map:
            return ActionRequest(
                domain="BROWSER",
                intent=tab_nav_map[cmd],
                raw_segment=segment,
                description=tab_nav_map[cmd].replace("_", " ").title(),
            )

        # -------------------------------------------------------------
        # 4. Known Web Destinations (e.g. "Open LinkedIn in Chrome")
        # -------------------------------------------------------------
        dest_match = re.search(
            r"^(?:open|launch|navigate to)\s+([a-z\s]+?)(?:\s+(?:in|on)\s+(chrome|browser))?$", cmd
        )
        if dest_match:
            candidate_site = dest_match.group(1).strip()
            browser_target = dest_match.group(2) or "chrome"
            known_sites = {"linkedin", "github", "youtube", "gmail", "google drive", "drive", "google"}
            if candidate_site in known_sites:
                return ActionRequest(
                    domain="BROWSER",
                    intent="OPEN_DESTINATION",
                    params={"site_key": candidate_site, "browser": browser_target},
                    raw_segment=segment,
                    description=f"Open {candidate_site.title()} in {browser_target.title()}",
                )

        # -------------------------------------------------------------
        # 5. File & Known Folder Navigation
        # -------------------------------------------------------------
        # Specific latest screenshot
        if cmd in ("open the latest screenshot", "open latest screenshot", "show latest screenshot"):
            return ActionRequest(
                domain="FILE_SYSTEM",
                intent="OPEN_LATEST_SCREENSHOT",
                raw_segment=segment,
                description="Open Latest Screenshot",
            )

        if cmd in (
            "find the latest screenshot",
            "find latest screenshot",
            "locate the latest screenshot",
            "find my latest screenshot",
        ):
            return ActionRequest(
                domain="FILE_SYSTEM",
                intent="FIND_LATEST_SCREENSHOT",
                raw_segment=segment,
                description="Find Latest Screenshot",
            )

        file_search = re.search(
            r"^(?:find|locate|look for)\s+(?:my|the|a|an)\s+(.+?)"
            r"(?:\s+in\s+(downloads|documents|desktop|pictures|screenshots|project))?"
            r"(?:\s+folder)?$",
            cmd,
        )
        if file_search:
            query, folder = file_search.groups()
            return ActionRequest(
                domain="FILE_SYSTEM",
                intent="FIND_FILE",
                params={"query": query.strip(), "folder_key": (folder or "documents").removesuffix(" folder")},
                raw_segment=segment,
                description=f"Find '{query.strip()}'",
            )

        # Known folders (Downloads, Documents, Desktop, Screenshots, Project Folder)
        folder_match = re.search(r"^(?:open|show)\s+(downloads|documents|desktop|pictures|screenshots|my project folder|project folder|project)$", cmd)
        if folder_match:
            f_key = folder_match.group(1).strip()
            return ActionRequest(
                domain="FILE_SYSTEM",
                intent="OPEN_FOLDER",
                params={"folder_key": f_key},
                raw_segment=segment,
                description=f"Open {f_key.title()}",
            )

        if cmd in ("open recycle bin", "open the recycle bin", "show recycle bin"):
            return ActionRequest(
                domain="FILE_SYSTEM",
                intent="OPEN_RECYCLE_BIN",
                raw_segment=segment,
                description="Open Recycle Bin",
            )

        # Specific file e.g. "open this pdf", "open report pdf"
        file_match = re.search(r"^(?:open|show)\s+(.+?\.(?:pdf|txt|docx|xlsx|png|jpg))$", cmd)
        if file_match:
            filename = file_match.group(1).strip()
            return ActionRequest(
                domain="FILE_SYSTEM",
                intent="OPEN_FILE",
                params={"filename": filename},
                raw_segment=segment,
                description=f"Open File: {filename}",
            )

        # -------------------------------------------------------------
        # 6. Window Management
        # -------------------------------------------------------------
        if cmd in ("minimize this window", "minimize window", "minimize"):
            return ActionRequest(domain="WINDOW", intent="MINIMIZE", raw_segment=segment, description="Minimize Window")
        if cmd in ("maximize this window", "maximize window", "maximize"):
            return ActionRequest(domain="WINDOW", intent="MAXIMIZE", raw_segment=segment, description="Maximize Window")
        if cmd in ("switch application", "switch app", "switch window"):
            return ActionRequest(domain="WINDOW", intent="SWITCH_APP", raw_segment=segment, description="Switch Application")
        if cmd in ("show desktop", "desktop"):
            return ActionRequest(domain="WINDOW", intent="SHOW_DESKTOP", raw_segment=segment, description="Show Desktop")
        if cmd in (
            "close the active window",
            "close active window",
            "close current window",
            "close the current window",
            "close this window",
            "close active application",
            "close the current application",
            "close current application",
            "close active app",
            "close the current app",
            "close current app",
        ):
            return ActionRequest(domain="WINDOW", intent="CLOSE_ACTIVE_WINDOW", raw_segment=segment, description="Close Active Window")

        # -------------------------------------------------------------
        # 7. System & Keyboard Controls
        # -------------------------------------------------------------
        if cmd in ("take a screenshot", "take screenshot", "screenshot"):
            return ActionRequest(domain="SYSTEM", intent="SCREENSHOT", raw_segment=segment, description="Take Screenshot")
        if cmd == "copy":
            return ActionRequest(domain="SYSTEM", intent="COPY", raw_segment=segment, description="Copy")
        if cmd == "paste":
            return ActionRequest(domain="SYSTEM", intent="PASTE", raw_segment=segment, description="Paste")
        if cmd in ("select all", "select everything"):
            return ActionRequest(domain="SYSTEM", intent="SELECT_ALL", raw_segment=segment, description="Select All")
        if cmd == "undo":
            return ActionRequest(domain="SYSTEM", intent="UNDO", raw_segment=segment, description="Undo")
        if cmd in ("press enter", "enter"):
            return ActionRequest(domain="SYSTEM", intent="PRESS_ENTER", raw_segment=segment, description="Press Enter")
        if cmd in ("press escape", "escape"):
            return ActionRequest(domain="SYSTEM", intent="PRESS_ESCAPE", raw_segment=segment, description="Press Escape")
        if cmd in ("lock my pc", "lock the pc", "lock computer", "lock screen"):
            return ActionRequest(domain="SYSTEM", intent="LOCK_PC", raw_segment=segment, description="Lock Workstation")

        if cmd == "scroll up":
            return ActionRequest(domain="SYSTEM", intent="SCROLL_UP", raw_segment=segment, description="Scroll Up")
        if cmd == "scroll down":
            return ActionRequest(domain="SYSTEM", intent="SCROLL_DOWN", raw_segment=segment, description="Scroll Down")
        if cmd in ("zoom in", "zoom in."):
            return ActionRequest(domain="SYSTEM", intent="ZOOM_IN", raw_segment=segment, description="Zoom In")
        if cmd in ("zoom out", "zoom out."):
            return ActionRequest(domain="SYSTEM", intent="ZOOM_OUT", raw_segment=segment, description="Zoom Out")
        if cmd in ("mute", "unmute"):
            return ActionRequest(domain="SYSTEM", intent="MUTE", raw_segment=segment, description="Mute / Unmute")
        if cmd in ("volume up", "turn volume up", "turn the volume up", "increase volume", "raise volume"):
            return ActionRequest(domain="SYSTEM", intent="VOLUME_UP", raw_segment=segment, description="Volume Up")
        if cmd in ("volume down", "turn volume down", "turn the volume down", "decrease volume", "lower volume"):
            return ActionRequest(domain="SYSTEM", intent="VOLUME_DOWN", raw_segment=segment, description="Volume Down")

        if cmd in ("increase text size", "make text bigger", "larger text", "text size up"):
            return ActionRequest(
                domain="SYSTEM",
                intent="OPEN_ACCESSIBILITY_SETTINGS",
                raw_segment=segment,
                description="Open Windows accessibility text-size settings",
            )

        type_text = re.match(
            r"^(?:please\s+)?(?:type|write)\s+(.+?)\s*$", segment, flags=re.IGNORECASE
        )
        if type_text:
            return ActionRequest(
                domain="SYSTEM",
                intent="TYPE_TEXT",
                params={"text": type_text.group(1)},
                raw_segment=segment,
                description="Type requested text",
            )

        if cmd in (
            "what is happening",
            "what is happening in the application",
            "explain what is happening",
            "explain what is happening in the application",
            "explain the current status",
            "what is aircontrol doing",
        ):
            return ActionRequest(
                domain="SYSTEM",
                intent="EXPLAIN_STATUS",
                raw_segment=segment,
                description="Explain AirControl status",
            )

        if cmd in ("move cursor left", "move left", "mouse left"):
            return ActionRequest(domain="SYSTEM", intent="MOVE_CURSOR", params={"dx": -100, "dy": 0, "name": "Move Left"}, raw_segment=segment)
        if cmd in ("move cursor right", "move right", "mouse right"):
            return ActionRequest(domain="SYSTEM", intent="MOVE_CURSOR", params={"dx": 100, "dy": 0, "name": "Move Right"}, raw_segment=segment)
        if cmd in ("move cursor up", "move up", "mouse up"):
            return ActionRequest(domain="SYSTEM", intent="MOVE_CURSOR", params={"dx": 0, "dy": -100, "name": "Move Up"}, raw_segment=segment)
        if cmd in ("move cursor down", "move down", "mouse down"):
            return ActionRequest(domain="SYSTEM", intent="MOVE_CURSOR", params={"dx": 0, "dy": 100, "name": "Move Down"}, raw_segment=segment)

        # -------------------------------------------------------------
        # 8. Gesture Controls (Clicks & Pause/Resume)
        # -------------------------------------------------------------
        if cmd in ("left click", "click"):
            return ActionRequest(domain="GESTURE", intent="CLICK", raw_segment=segment, description="Left Click")
        if cmd == "double click":
            return ActionRequest(domain="GESTURE", intent="DOUBLE_CLICK", raw_segment=segment, description="Double Click")
        if cmd == "right click":
            return ActionRequest(domain="GESTURE", intent="RIGHT_CLICK", raw_segment=segment, description="Right Click")
        if cmd in ("pause control", "pause", "pause mouse", "pause tracking"):
            return ActionRequest(domain="GESTURE", intent="PAUSE_CONTROL", raw_segment=segment, description="Pause Mouse Control")
        if cmd in ("resume control", "resume", "resume mouse", "resume tracking"):
            return ActionRequest(domain="GESTURE", intent="RESUME_CONTROL", raw_segment=segment, description="Resume Mouse Control")
        if cmd in ("cancel task", "cancel current task", "stop current task", "cancel request"):
            return ActionRequest(domain="GESTURE", intent="CANCEL_TASK", raw_segment=segment, description="Cancel Current Task")

        # -------------------------------------------------------------
        # 9. General Application Launch & Close Commands (Dynamic Discovery)
        # -------------------------------------------------------------
        # e.g. "open spotify", "launch visual studio code", "start calculator"
        app_match = re.search(r"^(?:open|launch|start)\s+(.+)$", cmd)
        if app_match:
            app_name = app_match.group(1).strip()
            return ActionRequest(
                domain="APPLICATION",
                intent="LAUNCH_APP",
                params={"app_name": app_name},
                raw_segment=segment,
                description=f"Launch Application: {app_name.title()}",
            )

        # e.g. "close notepad", "close calculator", "quit chrome", "close it"
        close_app_match = re.search(r"^(?:close|quit|exit|terminate)\s+(.+)$", cmd)
        if close_app_match:
            target = close_app_match.group(1).strip()
            if target in (
                "active window",
                "the active window",
                "current window",
                "the current window",
                "this window",
                "active application",
                "the active application",
                "current application",
                "the current application",
                "active app",
                "the active app",
            ):
                return ActionRequest(
                    domain="WINDOW",
                    intent="CLOSE_ACTIVE_WINDOW",
                    raw_segment=segment,
                    description="Close Active Window",
                )
            if target in ("tab", "current tab", "this tab", "the tab"):
                return ActionRequest(
                    domain="BROWSER",
                    intent="CLOSE_TAB",
                    raw_segment=segment,
                    description="Close Browser Tab",
                )
            return ActionRequest(
                domain="APPLICATION",
                intent="CLOSE_APP",
                params={"app_name": target},
                raw_segment=segment,
                description=f"Close Application: {target.title()}",
            )

        # -------------------------------------------------------------
        # 10. Unknown / Unrecognized Command
        # -------------------------------------------------------------
        return ActionRequest(
            domain="UNKNOWN",
            intent="UNKNOWN",
            params={"raw": cmd},
            raw_segment=segment,
            description=f"Unknown command: '{cmd}'",
        )

    def parse(self, text: str) -> List[ActionRequest]:
        """
        Parses input speech (potentially multi-step) into a sequence of ActionRequests.
        Resolves follow-up pronouns (e.g. 'open vs code and then close it').
        """
        segments = self.split_compound_commands(text)
        requests: List[ActionRequest] = []
        last_app: Optional[str] = None

        for seg in segments:
            req = self.parse_single_segment(seg)
            if req.domain == "APPLICATION" and req.intent == "LAUNCH_APP":
                last_app = req.params.get("app_name")
            elif req.domain == "APPLICATION" and req.intent == "CLOSE_APP":
                app_target = req.params.get("app_name", "").lower()
                if app_target in ("it", "this", "that", "this app", "the app") and last_app:
                    req.params["app_name"] = last_app
                    req.description = f"Close Application: {last_app.title()}"
            requests.append(req)

        return requests

