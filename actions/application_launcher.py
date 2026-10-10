"""
AirControl — Dynamic Windows Application Discovery & Safe Launcher
Scans Start Menu shortcuts, WindowsApp aliases, and system tools.
Matches spoken application names, normalizes aliases, and launches without shell=True.
"""

import glob
import os
import re
import shutil
import subprocess
import time
from typing import Callable, Dict, List, Optional, Tuple


# Known Windows system applications & protocol handlers
SYSTEM_APPLICATIONS: Dict[str, Dict[str, any]] = {
    "settings": {
        "name": "Windows Settings",
        "target": "ms-settings:",
        "is_protocol": True,
        "aliases": ["settings", "windows settings", "system settings"],
    },
    "file explorer": {
        "name": "File Explorer",
        "target": "explorer.exe",
        "is_protocol": False,
        "aliases": ["file explorer", "explorer", "files", "my computer"],
    },
    "task manager": {
        "name": "Task Manager",
        "target": "taskmgr.exe",
        "is_protocol": False,
        "aliases": ["task manager", "taskmgr", "task monitor"],
    },
    "calculator": {
        "name": "Calculator",
        "target": "calc.exe",
        "is_protocol": False,
        "aliases": ["calculator", "calc", "calculate"],
    },
    "notepad": {
        "name": "Notepad",
        "target": "notepad.exe",
        "is_protocol": False,
        "aliases": ["notepad", "text editor", "note pad"],
    },
    "whatsapp": {
        "name": "WhatsApp",
        "target": "whatsapp:",
        "is_protocol": True,
        "aliases": ["whatsapp", "whats app"],
    },
}

COMMON_ALIASES: Dict[str, str] = {
    "vs code": "visual studio code",
    "vscode": "visual studio code",
    "code": "visual studio code",
    "ms word": "word",
    "microsoft word": "word",
    "winword": "word",
    "ms excel": "excel",
    "microsoft excel": "excel",
    "ms powerpoint": "powerpoint",
    "microsoft powerpoint": "powerpoint",
    "ppt": "powerpoint",
    "google chrome": "chrome",
    "chrome browser": "chrome",
    "ms edge": "edge",
    "microsoft edge": "edge",
}


class ApplicationLauncher:
    """
    Discovers installed Windows applications from the Start Menu,
    WindowsApps directory, and standard paths with caching and alias resolution.
    """

    def __init__(
        self,
        launcher_fn: Optional[Callable[[any], any]] = None,
        cache_ttl: float = 300.0,
    ):
        self.launcher_fn = launcher_fn
        self.cache_ttl = cache_ttl
        self._cached_apps: Dict[str, str] = {}
        self._last_scan_time: float = 0.0

    def refresh_cache(self) -> Dict[str, str]:
        """Scans Windows Start Menu and WindowsApps to index installed applications."""
        discovered: Dict[str, str] = {}

        # 1. System Applications & Protocol Handlers
        for key, info in SYSTEM_APPLICATIONS.items():
            discovered[key] = info["target"]
            for alias in info.get("aliases", []):
                discovered[alias] = info["target"]

        # 2. Start Menu Shortcuts (.lnk)
        start_menu_dirs = [
            r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs",
            os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"),
        ]

        for base_dir in start_menu_dirs:
            if os.path.exists(base_dir):
                pattern = os.path.join(base_dir, "**", "*.lnk")
                for lnk_file in glob.glob(pattern, recursive=True):
                    base_name = os.path.splitext(os.path.basename(lnk_file))[0].lower()
                    # Skip uninstaller shortcuts or auxiliary tools
                    if "uninstall" in base_name or "help" in base_name:
                        continue
                    # Clean punctuation
                    clean_name = re.sub(r"[^a-z0-9\s]", " ", base_name).strip()
                    clean_name = " ".join(clean_name.split())
                    if clean_name and clean_name not in discovered:
                        discovered[clean_name] = lnk_file

        # 3. WindowsApps Execution Aliases
        winapps_dir = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WindowsApps")
        if os.path.exists(winapps_dir):
            for file_name in os.listdir(winapps_dir):
                if file_name.lower().endswith(".exe"):
                    app_name = os.path.splitext(file_name)[0].lower()
                    clean_name = re.sub(r"[^a-z0-9\s]", " ", app_name).strip()
                    clean_name = " ".join(clean_name.split())
                    full_path = os.path.join(winapps_dir, file_name)
                    if clean_name and clean_name not in discovered:
                        discovered[clean_name] = full_path

        # 4. Standard Executable Locations (Chrome, Edge, etc.)
        candidates = {
            "chrome": [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
                shutil.which("chrome"),
            ],
            "edge": [
                r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
                shutil.which("msedge"),
            ],
            "spotify": [
                os.path.expandvars(r"%APPDATA%\Spotify\Spotify.exe"),
            ],
        }

        for app_key, paths in candidates.items():
            for p in paths:
                if p and os.path.exists(p):
                    discovered[app_key] = p
                    break

        self._cached_apps = discovered
        self._last_scan_time = time.monotonic()
        return self._cached_apps

    def get_applications(self) -> Dict[str, str]:
        """Returns the application dictionary, refreshing if the cache TTL has expired."""
        now = time.monotonic()
        if not self._cached_apps or (now - self._last_scan_time > self.cache_ttl):
            self.refresh_cache()
        return self._cached_apps

    def resolve_application(self, query: str) -> Tuple[Optional[str], Optional[str], List[str]]:
        """
        Resolves a spoken application query into a discovered app target.
        Returns: (matched_name, app_target, potential_matches)
        """
        if not query:
            return None, None, []

        apps = self.get_applications()
        q = query.strip().lower()

        # Apply common alias normalization
        if q in COMMON_ALIASES:
            q = COMMON_ALIASES[q]

        # 1. Exact match
        if q in apps:
            return q, apps[q], [q]

        # 2. Token / word boundary matching
        matches: List[Tuple[str, str]] = []
        for name, target in apps.items():
            # Check if query is an exact word or prefix in the app name
            if q == name or f" {q} " in f" {name} ":
                matches.append((name, target))
            elif name.startswith(q) or q in name:
                matches.append((name, target))

        if len(matches) == 1:
            matched_name, target = matches[0]
            return matched_name, target, [matched_name]

        if len(matches) > 1:
            # Check if there is an exact priority match
            for name, target in matches:
                if name == q:
                    return name, target, [name]
            # Return candidates for disambiguation
            candidate_names = [m[0] for m in matches[:5]]
            return None, None, candidate_names

        return None, None, []

    def focus_running_window(self, app_name: str) -> bool:
        """Attempts to bring an already running application window to the foreground."""
        try:
            import ctypes
            user32 = ctypes.windll.user32

            # Find matching window title
            found_hwnd = []

            def enum_windows_proc(hwnd, extra):
                if user32.IsWindowVisible(hwnd):
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buff = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buff, length + 1)
                        title = buff.value.lower()
                        if app_name.lower() in title:
                            found_hwnd.append(hwnd)
                return True

            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
            user32.EnumWindows(WNDENUMPROC(enum_windows_proc), 0)

            if found_hwnd:
                hwnd = found_hwnd[0]
                # Restore if minimized
                user32.ShowWindow(hwnd, 9)  # SW_RESTORE = 9
                user32.SetForegroundWindow(hwnd)
                return True
        except Exception:
            pass
        return False

    def launch(self, query: str) -> Tuple[bool, str, str]:
        """
        Safely launches or focuses an application matching the spoken query.
        Returns: (success: bool, status_message: str, action_label: str)
        """
        clean_query = query.strip()
        matched_name, target, candidates = self.resolve_application(clean_query)

        if not target:
            if candidates:
                cand_str = ", ".join(f"'{c}'" for c in candidates)
                return False, f"Ambiguous application '{clean_query}'. Did you mean: {cand_str}?", f"Launch {clean_query}"
            return False, f"Application '{clean_query}' not found on this system.", f"Launch {clean_query}"

        display_name = matched_name.title()

        # Try focusing existing window first
        if self.focus_running_window(matched_name):
            return True, f"Focused running application: {display_name}", f"Focus {display_name}"

        # Execute launcher
        try:
            if self.launcher_fn is not None:
                self.launcher_fn(target)
            else:
                if target.endswith(".exe"):
                    # Safe subprocess launch with explicit argument list
                    subprocess.Popen([target], shell=False)
                else:
                    # Safe Windows shell launch for .lnk shortcuts and protocol URIs
                    os.startfile(target)

            return True, f"Action: Launch {display_name}", f"Launch {display_name}"
        except Exception as exc:
            return False, f"Error launching {display_name}: {exc}", f"Launch {display_name}"
