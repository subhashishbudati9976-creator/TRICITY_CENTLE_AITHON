"""
AirControl — Window Management Actions
Handles minimize, maximize, application switching, and show desktop.
"""

from typing import Tuple
import pyautogui


class WindowActions:
    """Controls window positioning and desktop state via safe OS hotkeys."""

    def minimize_window(self) -> Tuple[bool, str, str]:
        pyautogui.hotkey("win", "down", interval=0.05)
        return True, "Action: Minimize Window", "Minimize Window"

    def maximize_window(self) -> Tuple[bool, str, str]:
        pyautogui.hotkey("win", "up", interval=0.05)
        return True, "Action: Maximize Window", "Maximize Window"

    def switch_application(self) -> Tuple[bool, str, str]:
        pyautogui.hotkey("alt", "tab", interval=0.05)
        return True, "Action: Switch Application", "Switch App"

    def show_desktop(self) -> Tuple[bool, str, str]:
        pyautogui.hotkey("win", "d", interval=0.05)
        return True, "Action: Show Desktop", "Show Desktop"
