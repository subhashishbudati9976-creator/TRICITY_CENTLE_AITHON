"""
AirControl — Natural Voice Command Parser & Intent Extractor
Supports multi-step compound commands, entity extraction, and domain classification.
"""

from dataclasses import dataclass, field
import re
import string
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
        """Strips punctuation, lowercases, and collapses colloquial speech artifacts."""
        if not text:
            return ""

        cleaned = text.lower().replace("-", " ")
        # Keep alphanumeric, spaces, and essential query characters
        cleaned = cleaned.translate(str.maketrans("", "", string.punctuation))
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
        # Pattern to split '... and (open|search|launch|show|minimize|take)...'
        cmd_verbs = r"(?:open|launch|start|search|show|minimize|maximize|take|switch|copy|paste|scroll|volume|lock)"
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
        if not cmd:
            return ActionRequest(domain="EMPTY", intent="EMPTY", raw_segment=segment)

        # -------------------------------------------------------------
        # 1. High-Impact Dangerous Commands (Safety Block)
        # -------------------------------------------------------------
        dangerous_matches = [
            r"\b(?:shutdown|shut down)\b",
            r"\b(?:restart|reboot)\b",
            r"\b(?:format c|delete all files|rm -rf)\b",
            r"\b(?:cmd|powershell|terminal|bash|curl|eval)\b",
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
        if cmd == "volume up":
            return ActionRequest(domain="SYSTEM", intent="VOLUME_UP", raw_segment=segment, description="Volume Up")
        if cmd == "volume down":
            return ActionRequest(domain="SYSTEM", intent="VOLUME_DOWN", raw_segment=segment, description="Volume Down")

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

        # -------------------------------------------------------------
        # 9. General Application Launch Commands (Dynamic Discovery)
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
        """
        segments = self.split_compound_commands(text)
        return [self.parse_single_segment(seg) for seg in segments]
