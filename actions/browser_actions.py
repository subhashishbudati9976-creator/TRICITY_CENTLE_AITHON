"""
AirControl — Browser Automation & Web Navigation Subsystem
Handles Google/YouTube search queries, verified destination routing,
and tab/history navigation via safe hotkeys.
"""

import os
import shutil
import urllib.parse
import webbrowser
from typing import Callable, Dict, Optional, Tuple

import pyautogui


KNOWN_DESTINATIONS: Dict[str, Dict[str, str]] = {
    "linkedin": {
        "name": "LinkedIn",
        "url": "https://www.linkedin.com",
    },
    "github": {
        "name": "GitHub",
        "url": "https://www.github.com",
    },
    "youtube": {
        "name": "YouTube",
        "url": "https://www.youtube.com",
    },
    "gmail": {
        "name": "Gmail",
        "url": "https://mail.google.com",
    },
    "google drive": {
        "name": "Google Drive",
        "url": "https://drive.google.com",
    },
    "drive": {
        "name": "Google Drive",
        "url": "https://drive.google.com",
    },
    "google": {
        "name": "Google",
        "url": "https://www.google.com",
    },
}


class BrowserActions:
    """
    Executes web searches, opens allowlisted destinations,
    and performs tab/page navigation.
    """

    def __init__(
        self,
        process_runner: Optional[Callable] = None,
        chrome_path_resolver: Optional[Callable[[], Optional[str]]] = None,
    ):
        self.process_runner = process_runner
        self._chrome_resolver = chrome_path_resolver or self._find_chrome

    def _find_chrome(self) -> Optional[str]:
        candidates = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
            shutil.which("chrome"),
            shutil.which("google-chrome"),
        ]
        for c in candidates:
            if c and os.path.exists(c):
                return c
        return None

    def open_url(self, url: str, prefer_chrome: bool = True) -> Tuple[bool, str]:
        """Opens a validated HTTPS URL in Chrome or the default browser."""
        if not url.startswith("https://") and not url.startswith("http://"):
            return False, f"Invalid URL protocol: {url}"

        chrome_path = self._chrome_resolver() if prefer_chrome else None

        try:
            if chrome_path:
                if self.process_runner:
                    self.process_runner([chrome_path, url], shell=False)
                else:
                    import subprocess
                    subprocess.Popen([chrome_path, url], shell=False)
                return True, "Opened in Google Chrome"
            else:
                if self.process_runner:
                    self.process_runner([url], shell=False)
                else:
                    webbrowser.open_new_tab(url)
                return True, "Opened in default browser"
        except Exception as exc:
            return False, f"Error opening browser: {exc}"

    def search_google(self, query: str) -> Tuple[bool, str, str]:
        """Constructs an HTTPS Google search query and launches it."""
        clean_q = query.strip()
        if not clean_q:
            return False, "Empty search query", "Search Google"

        encoded = urllib.parse.quote_plus(clean_q)
        url = f"https://www.google.com/search?q={encoded}"
        ok, msg = self.open_url(url, prefer_chrome=True)
        if ok:
            return True, f"Action: Search Google for '{clean_q}'", f"Search Google: {clean_q}"
        return False, msg, "Search Google"

    def search_youtube(self, query: str) -> Tuple[bool, str, str]:
        """Constructs an HTTPS YouTube search query and launches it."""
        clean_q = query.strip()
        if not clean_q:
            return False, "Empty search query", "Search YouTube"

        encoded = urllib.parse.quote_plus(clean_q)
        url = f"https://www.youtube.com/results?search_query={encoded}"
        ok, msg = self.open_url(url, prefer_chrome=True)
        if ok:
            return True, f"Action: Search YouTube for '{clean_q}'", f"Search YouTube: {clean_q}"
        return False, msg, "Search YouTube"

    def open_destination(self, site_key: str, browser: str = "chrome") -> Tuple[bool, str, str]:
        """Opens a recognized domain destination."""
        dest = KNOWN_DESTINATIONS.get(site_key.lower().strip())
        if not dest:
            return False, f"Unknown web destination: {site_key}", f"Open {site_key}"

        prefer_chrome = (browser.lower() == "chrome")
        ok, msg = self.open_url(dest["url"], prefer_chrome=prefer_chrome)
        if ok:
            b_name = "Chrome" if prefer_chrome else "Browser"
            return True, f"Action: Open {dest['name']} in {b_name}", f"Open {dest['name']}"
        return False, msg, f"Open {dest['name']}"

    # Browser Tab and Page Navigation Actions
    def new_tab(self) -> Tuple[bool, str, str]:
        pyautogui.hotkey("ctrl", "t", interval=0.05)
        return True, "Action: Open New Tab", "New Tab"

    def close_tab(self) -> Tuple[bool, str, str]:
        pyautogui.hotkey("ctrl", "w", interval=0.05)
        return True, "Action: Close Tab", "Close Tab"

    def next_tab(self) -> Tuple[bool, str, str]:
        pyautogui.hotkey("ctrl", "pagedown", interval=0.05)
        return True, "Action: Switch to Next Tab", "Next Tab"

    def previous_tab(self) -> Tuple[bool, str, str]:
        pyautogui.hotkey("ctrl", "pageup", interval=0.05)
        return True, "Action: Switch to Previous Tab", "Previous Tab"

    def go_back(self) -> Tuple[bool, str, str]:
        pyautogui.hotkey("alt", "left", interval=0.05)
        return True, "Action: Browser Go Back", "Go Back"

    def go_forward(self) -> Tuple[bool, str, str]:
        pyautogui.hotkey("alt", "right", interval=0.05)
        return True, "Action: Browser Go Forward", "Go Forward"

    def refresh_page(self) -> Tuple[bool, str, str]:
        pyautogui.hotkey("ctrl", "r", interval=0.05)
        return True, "Action: Refresh Page", "Refresh Page"
