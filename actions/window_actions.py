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

    def close_active_window(self) -> Tuple[bool, str, str]:
        """Gracefully request close of the currently focused active window."""
        try:
            import pygetwindow as gw
            active = gw.getActiveWindow()
            if active:
                title = active.title or "Active Window"
                # Prevent closing AirControl itself via active window shortcut unless intended
                if "aircontrol" in title.lower():
                    return False, "Refusing to close AirControl main window automatically.", "Close Window"
                active_hwnd = getattr(active, "_hWnd", None)
                active.close()
                import time
                time.sleep(0.4)
                still_open = False
                for check_w in gw.getAllWindows():
                    try:
                        if (active_hwnd and getattr(check_w, "_hWnd", None) == active_hwnd) or (check_w.title and check_w.title == title):
                            still_open = True
                            break
                    except Exception:
                        pass
                if still_open:
                    return True, f"Close request sent to '{title}'. Please review any unsaved changes.", "Close Window"
                return True, f"Action: Closed window '{title}'", "Close Window"
        except Exception:
            pass
        pyautogui.hotkey("alt", "f4", interval=0.05)
        return True, "Action: Close requested for active window", "Close Window"
