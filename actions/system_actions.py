"""
AirControl — System & Keyboard Actions Subsystem
Handles keyboard shortcuts, volume, screenshots, and workstation lock.
Enforces strict safeguards rejecting dangerous or unconfirmed actions.
"""

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

    def mute(self) -> Tuple[bool, str, str]:
        pyautogui.press("volumemute")
        return True, "Action: Mute", "Mute"

    def scroll_up(self) -> Tuple[bool, str, str]:
        pyautogui.scroll(200)
        return True, "Action: Scroll Up", "Scroll Up"

    def scroll_down(self) -> Tuple[bool, str, str]:
        pyautogui.scroll(-200)
        return True, "Action: Scroll Down", "Scroll Down"

    def reject_high_impact(self, action_name: str) -> Tuple[bool, str, str]:
        """Prevents voice execution of dangerous commands (shutdown, restart, format, delete)."""
        msg = f"Action '{action_name}' rejected: High-impact action requires manual confirmation."
        return False, msg, "Safety Block"
