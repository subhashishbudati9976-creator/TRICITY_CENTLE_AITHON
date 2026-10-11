"""
AirControl — System & Keyboard Actions Subsystem
Handles keyboard shortcuts, volume, screenshots, and workstation lock.
Enforces strict safeguards rejecting dangerous or unconfirmed actions.
"""

import os
from typing import Tuple
import pyautogui


class SystemActions:
    """Executes validated system-level keyboard shortcuts and workstation controls."""

    def copy(self) -> Tuple[bool, str, str]:
        pyautogui.hotkey("ctrl", "c", interval=0.05)
        return True, "Action: Copy", "Copy"

    def paste(self) -> Tuple[bool, str, str]:
        pyautogui.hotkey("ctrl", "v", interval=0.05)
        return True, "Action: Paste", "Paste"

    def select_all(self) -> Tuple[bool, str, str]:
        pyautogui.hotkey("ctrl", "a", interval=0.05)
        return True, "Action: Select All", "Select All"

    def undo(self) -> Tuple[bool, str, str]:
        pyautogui.hotkey("ctrl", "z", interval=0.05)
        return True, "Action: Undo", "Undo"

    def press_enter(self) -> Tuple[bool, str, str]:
        pyautogui.press("enter")
        return True, "Action: Press Enter", "Enter"

    def press_escape(self) -> Tuple[bool, str, str]:
        pyautogui.press("escape")
        return True, "Action: Press Escape", "Escape"

    def take_screenshot(self) -> Tuple[bool, str, str]:
        pyautogui.hotkey("win", "prtsc", interval=0.05)
        return True, "Action: Take Screenshot", "Screenshot"

    def lock_workstation(self) -> Tuple[bool, str, str]:
        """Locks the Windows workstation using native user32 API without shell execution."""
        try:
            import ctypes
            ctypes.windll.user32.LockWorkStation()
            return True, "Action: Lock Workstation", "Lock PC"
        except Exception as exc:
            return False, f"Error locking workstation: {exc}", "Lock PC"

    def volume_up(self) -> Tuple[bool, str, str]:
        pyautogui.press("volumeup")
        return True, "Action: Volume Up", "Volume Up"

    def volume_down(self) -> Tuple[bool, str, str]:
        pyautogui.press("volumedown")
        return True, "Action: Volume Down", "Volume Down"

    def type_text(self, text: str) -> Tuple[bool, str, str]:
        """Type bounded ASCII text into the currently focused application."""
        if not text:
            return False, "No text was provided.", "Type Text"
        if not text.isascii():
            return False, "Typing non-ASCII text is not supported by the current keyboard backend.", "Type Text"
        try:
            pyautogui.write(text, interval=0.01)
            return True, "Action: Typed requested text", "Type Text"
        except Exception as exc:
            return False, f"Could not type the requested text: {exc}", "Type Text"

    def open_accessibility_settings(self) -> Tuple[bool, str, str]:
        """Open the Windows accessibility display settings page."""
        if os.name != "nt":
            return False, "Windows accessibility settings are unavailable on this system.", "Text Size Settings"
        try:
            os.startfile("ms-settings:easeofaccess-display")
            return True, "Action: Opened Windows text-size accessibility settings", "Text Size Settings"
        except OSError as exc:
            return False, f"Could not open accessibility settings: {exc}", "Text Size Settings"

    def explain_status(self, app) -> Tuple[bool, str, str]:
        """Summarize observable application state without accessing Tk widgets off-thread."""
        values = getattr(app, "__dict__", {}) if app is not None else {}
        if not isinstance(values, dict):
            values = {}
        running = bool(values.get("running", False))
        paused = bool(values.get("paused", True))
        camera_connected = bool(values.get("camera_connected", False))
        voice_mode = str(values.get("voice_mode", "unknown"))
        current_task = values.get("current_action_description")
        state = "running" if running else "stopped"
        mouse = "paused" if paused else "active"
        camera = "connected" if camera_connected else "not connected"
        message = (
            f"AirControl is {state}. Mouse control is {mouse}; camera is {camera}; "
            f"voice recognition is in {voice_mode} mode."
        )
        if current_task:
            message += f" Current action: {current_task}."
        return True, message, "Explain Status"

    def mute(self) -> Tuple[bool, str, str]:
        pyautogui.press("volumemute")
        return True, "Action: Mute", "Mute"

    def scroll_up(self) -> Tuple[bool, str, str]:
        pyautogui.scroll(200)
        return True, "Action: Scroll Up", "Scroll Up"

    def scroll_down(self) -> Tuple[bool, str, str]:
        pyautogui.scroll(-200)
        return True, "Action: Scroll Down", "Scroll Down"

    def zoom_in(self) -> Tuple[bool, str, str]:
        try:
            pyautogui.hotkey("ctrl", "+", interval=0.03)
        except Exception:
            pyautogui.hotkey("ctrl", "=", interval=0.03)
        return True, "Action: Zoom In", "Zoom In"

    def zoom_out(self) -> Tuple[bool, str, str]:
        pyautogui.hotkey("ctrl", "-", interval=0.03)
        return True, "Action: Zoom Out", "Zoom Out"

    def reject_high_impact(self, action_name: str) -> Tuple[bool, str, str]:
        """Prevents voice execution of dangerous commands (shutdown, restart, format, delete)."""
        msg = f"Action '{action_name}' rejected: High-impact action requires manual confirmation."
        return False, msg, "Safety Block"
